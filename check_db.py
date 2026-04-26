# fix_user_data.py
import sqlite3

conn = sqlite3.connect("data/waimai.db")
cursor = conn.cursor()

# 查看当前数据
cursor.execute("SELECT id, username, phone FROM users")
users = cursor.fetchall()
print("修复前:")
for user in users:
    print(f"  ID: {user[0]}, username: '{user[1]}', phone: '{user[2]}'")

# 交换 username 和 phone
cursor.execute("UPDATE users SET username = phone, phone = username")
conn.commit()

# 验证修复结果
cursor.execute("SELECT id, username, phone FROM users")
users = cursor.fetchall()
print("\n修复后:")
for user in users:
    print(f"  ID: {user[0]}, username: '{user[1]}', phone: '{user[2]}'")

conn.close()
print("\n修复完成！")