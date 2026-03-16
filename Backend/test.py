import pymysql

# 1. 建立数据库连接
connection = pymysql.connect(
    host='localhost',       # 数据库地址，本地就是 localhost
    user='root',            # 用户名
    password='123456',      # 密码
    database='bysy',        # 数据库名
    charset='utf8mb4',      # 推荐使用 utf8mb4，完美支持中文和 Emoji
    cursorclass=pymysql.cursors.DictCursor  # 游标设置：让查询结果以字典 {字段名: 值} 形式返回，非常方便读取
)

try:
    # 2. 创建一个游标对象 (Cursor)，用来执行 SQL 语句
    with connection.cursor() as cursor:
        
        # --- 测试连接：查询 MySQL 版本 ---
        sql = "SELECT VERSION() AS version;"
        cursor.execute(sql)
        
        # 获取第一条查询结果
        result = cursor.fetchone()
        print(f"数据库连接成功！当前 MySQL 版本为: {result['version']}")

        query = "SELECT name FROM test WHERE id=1;"
        cursor.execute(query)

        result = cursor.fetchone()
        print(f"{result}")

        # --- 如果你想尝试建表和插入数据，可以取消下面代码的注释 ---
        # create_table_sql = """
        # CREATE TABLE IF NOT EXISTS users (
        #     id INT AUTO_INCREMENT PRIMARY KEY,
        #     username VARCHAR(50) NOT NULL,
        #     email VARCHAR(100)
        # )
        # """
        # cursor.execute(create_table_sql)
        # 
        # insert_sql = "INSERT INTO users (username, email) VALUES (%s, %s)"
        # cursor.execute(insert_sql, ('admin', 'admin@example.com'))
        # connection.commit() # 增、删、改 操作必须加上 commit() 才会真正保存到数据库！
        # print("成功插入一条测试数据！")

except Exception as e:
    print(f"执行出错了: {e}")

finally:
    # 3. 无论成功还是失败，最后一定要养成关闭连接的好习惯，释放资源
    connection.close()
    print("数据库连接已关闭。")