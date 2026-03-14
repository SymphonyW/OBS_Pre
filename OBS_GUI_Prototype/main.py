import sys
import cv2
import time
import subprocess
from PyQt6.QtWidgets import (QApplication, QMainWindow, QLabel, QVBoxLayout, 
                             QHBoxLayout, QWidget, QPushButton, QComboBox, 
                             QGroupBox, QFormLayout)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QImage, QPixmap

class VideoCaptureThread(QThread):
    change_pixmap_signal = pyqtSignal(QImage)
    status_signal = pyqtSignal(str)
    
    def __init__(self, camera_index=0):
        super().__init__()
        self.camera_index = camera_index
        self._run_flag = True
        self.current_frame = None

    def run(self):
        # 打开指定的视频采集设备 (Windows 上使用 DirectShow 后端)
        cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        
        if not cap.isOpened():
            self.status_signal.emit(f"错误: 无法打开设备索引 {self.camera_index}")
            return
            
        # 尝试设置高分辨率和高帧率
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        cap.set(cv2.CAP_PROP_FPS, 60)
            
        self.status_signal.emit(f"设备打开成功 | 分辨率: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")

        while self._run_flag:
            ret, cv_img = cap.read()
            if ret:
                self.current_frame = cv_img.copy()
                # OpenCV 使用 BGR 格式，但 PyQt 需要 RGB 格式
                rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb_image.shape
                bytes_per_line = ch * w
                convert_to_Qt_format = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
                self.change_pixmap_signal.emit(convert_to_Qt_format)
            else:
                time.sleep(0.01)
                
        cap.release()

    def get_current_frame(self):
        return self.current_frame

    def stop(self):
        """立即中断死循环，等待释放，防止直接导致QT崩溃"""
        self._run_flag = False
        # 不调用强制 wait，否则在主线程的点击事件中可能会引起 GUI 阻塞甚至死锁崩溃退出
        # self.wait()

class OBSCloneWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OBS 视频采集卡抓取工具 - 旗舰版")
        self.resize(1024, 768)

        # 获取系统中真实的视频捕获设备列表
        self.available_cameras = self.get_available_cameras()

        # 主控件和布局
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)

        # 左侧：视频显示区域
        self.video_label = QLabel("画面等待载入...")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet("background-color: black; color: white;")
        self.main_layout.addWidget(self.video_label, stretch=3)

        # 右侧：控制面板
        self.control_panel = QWidget()
        self.control_layout = QVBoxLayout(self.control_panel)
        self.main_layout.addWidget(self.control_panel, stretch=1)
        
        # --- 构建 UI ---
        
        # 1. 设备选择
        self.device_group = QGroupBox("采集设备控制")
        device_layout = QFormLayout()
        
        self.device_combo = QComboBox()
        
        # 动态将实际获取到的设备名称填入下拉框
        if not self.available_cameras:
            self.device_combo.addItem("未检测到任何视频设备")
            self.device_combo.setEnabled(False)
        else:
            for i, cam_name in enumerate(self.available_cameras):
                self.device_combo.addItem(f"设备 [{i}]: {cam_name}")
            
        self.start_btn = QPushButton("开启视频采集")
        self.start_btn.clicked.connect(self.toggle_capture)
        if not self.available_cameras:
            self.start_btn.setEnabled(False)
        
        device_layout.addRow("选择源:", self.device_combo)
        device_layout.addRow(self.start_btn)
        self.device_group.setLayout(device_layout)
        self.control_layout.addWidget(self.device_group)

        # 2. 截图设置
        self.capture_group = QGroupBox("截图控制 (按 V 键)")
        capture_layout = QVBoxLayout()
        
        self.screenshot_btn = QPushButton("手动截图 [或按 V]")
        self.screenshot_btn.setMinimumHeight(50)
        self.screenshot_btn.setStyleSheet("background-color: #2b78e4; color: white; font-weight: bold;")
        self.screenshot_btn.clicked.connect(self.take_screenshot)
        
        self.status_label = QLabel("状态: 等待操作...")
        self.status_label.setWordWrap(True)
        
        capture_layout.addWidget(self.screenshot_btn)
        capture_layout.addWidget(self.status_label)
        self.capture_group.setLayout(capture_layout)
        self.control_layout.addWidget(self.capture_group)
        
        self.control_layout.addStretch()

        # 后端变量
        self.video_thread = None
        self.is_capturing = False

    def get_available_cameras(self):
        """
        通过调用 Windows 底层的 PowerShell WMI 类 (Camera 和 Image) 获取真实的硬件名称信息。
        这能避免因为环境库缺失而列出无效设备。
        """
        devices = []
        try:
            # 搜索传统的摄像头和UVC设备
            out_camera = subprocess.check_output(
                ['powershell', '-Command', 'Get-PnpDevice -Class Camera -Status OK | Select-Object -ExpandProperty FriendlyName'],
                stderr=subprocess.STDOUT
            ).decode('gbk', errors='ignore')
            for line in out_camera.strip().split('\r\n'):
                if line.strip(): devices.append(line.strip())
        except Exception:
            pass

        try:
            # 搜索捕获卡/图像设备 (Capture cards usually fall into Image class)
            out_image = subprocess.check_output(
                ['powershell', '-Command', 'Get-PnpDevice -Class Image -Status OK | Select-Object -ExpandProperty FriendlyName'],
                stderr=subprocess.STDOUT
            ).decode('gbk', errors='ignore')
            for line in out_image.strip().split('\r\n'):
                if line.strip() and line.strip() not in devices: 
                    devices.append(line.strip())
        except Exception:
            pass
            
        # 如果以上底层查询都失败了或者没查到，为了让 UI 能点击，还是给出默认的 0 和 1 两个通道以做备用
        if not devices:
            devices = ["默认主摄像头 (索引0)", "未知扩展采集卡 (索引1)"]
            
        return devices

    def toggle_capture(self):
        if not self.is_capturing:
            device_idx = self.device_combo.currentIndex()
            self.video_thread = VideoCaptureThread(camera_index=device_idx)
            self.video_thread.change_pixmap_signal.connect(self.update_image)
            self.video_thread.status_signal.connect(self.update_status)
            self.video_thread.start()
            
            self.start_btn.setText("关闭采集")
            self.start_btn.setStyleSheet("background-color: #e04343; color: white;")
            self.is_capturing = True
            
            # 请求焦点以确保能监听到 V 键按下的事件
            self.setFocus()
        else:
            if self.video_thread:
                # 优雅地停止线程，避免出现阻塞或未处理的事件导致程序崩溃退出
                self.video_thread.stop()
                self.video_thread = None
                
            self.start_btn.setText("开启视频采集")
            self.start_btn.setStyleSheet("")
            self.video_label.clear()
            self.video_label.setText("画面已关闭")
            self.is_capturing = False

    def update_image(self, qt_image):
        # 调整大小时保持宽高比
        scaled_pixmap = QPixmap.fromImage(qt_image).scaled(
            self.video_label.width(), 
            self.video_label.height(), 
            Qt.AspectRatioMode.KeepAspectRatio
        )
        self.video_label.setPixmap(scaled_pixmap)

    def update_status(self, msg):
        self.status_label.setText(f"状态: {msg}")

    # 重写全局按键按下事件以捕获 'V' 键
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_V:
            self.take_screenshot()
        else:
            super().keyPressEvent(event)

    def take_screenshot(self):
        if self.video_thread and self.video_thread.isRunning():
            frame = self.video_thread.get_current_frame()
            if frame is not None:
                timestamp = int(time.time() * 1000)
                filename = f"capture_{timestamp}.png"
                cv2.imwrite(filename, frame)
                self.update_status(f"截图成功: {filename}")
                return
        
        self.update_status("截图失败: 视频源未开启或无画面")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 类似 OBS 的现代暗黑主题
    app.setStyle("Fusion")
    
    window = OBSCloneWindow()
    window.show()
    sys.exit(app.exec())