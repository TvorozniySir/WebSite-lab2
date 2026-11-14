from models import get_connection

conn = get_connection()
cursor = conn.cursor()
cursor.execute("UPDATE users SET role = ? WHERE username = ?", ("admin", "1234567"))
conn.commit()
conn.close()
print("Готово")