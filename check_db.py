# check_db.py
import sqlite3

conn = sqlite3.connect("./data/waimai.db")
cursor = conn.cursor()

cursor.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 5")
rows = cursor.fetchall()

print("最近的订单:")
for row in rows:
    print(row)

conn.close()