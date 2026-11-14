import os
import sqlite3
import bcrypt
import pyotp

from datetime import datetime
from flask_login import UserMixin

# Путь привязан к расположению этого файла, а не к текущей рабочей
# директории процесса. Раньше DB_NAME было просто "database.db" —
# относительный путь резолвится от того места, откуда ты запустил
# `python app.py`, а не от папки проекта. Если запустить сервер не из
# корня проекта (другой cwd в IDE, другой терминал и т.п.), файл базы
# создавался где-то ещё — и любой скрипт, который ищет database.db
# рядом с проектом (включая exploits/_lab_client.py), его не находил.
DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database.db")


def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE,
        email_verified INTEGER NOT NULL DEFAULT 0,
        password_hash TEXT NOT NULL,
        totp_secret TEXT,
        role TEXT NOT NULL DEFAULT 'user',
        balance REAL NOT NULL DEFAULT 10000.0,
        bio TEXT NOT NULL DEFAULT ''
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS portfolio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            asset TEXT NOT NULL,
            amount REAL NOT NULL DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE (user_id, asset)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            asset TEXT NOT NULL,
            order_type TEXT NOT NULL,
            amount REAL NOT NULL,
            price REAL NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    conn.commit()

    cols = [r["name"] for r in conn.execute("PRAGMA table_info(users)")]
    if "email" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
        conn.execute("ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 0")
        conn.commit()
    if "bio" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN bio TEXT NOT NULL DEFAULT ''")
        conn.commit()

    conn.close()


def create_user(username, email, password):
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    totp_secret = pyotp.random_base32()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (username, email, password_hash, totp_secret) VALUES (?, ?, ?, ?)",
        (username, email, password_hash, totp_secret)
    )
    conn.commit()
    conn.close()
    return totp_secret


def get_user_by_username(username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()
    return user


def get_user_by_email(email):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()
    return user


def get_user_by_id(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user


def get_all_users():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, role, balance FROM users ORDER BY id")
    rows = cursor.fetchall()
    conn.close()
    return rows


def mark_email_verified(email):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET email_verified = 1 WHERE email = ?", (email,))
    conn.commit()
    conn.close()


def update_bio(user_id, bio):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET bio = ? WHERE id = ?", (bio, user_id))
    conn.commit()
    conn.close()


class User(UserMixin):
    def __init__(self, row):
        self.id = row["id"]
        self.username = row["username"]
        self.password_hash = row["password_hash"]
        self.role = row["role"]
        self.balance = row["balance"]
        self.bio = row["bio"] if "bio" in row.keys() else ""


def get_portfolio_for_user(user_id):
    """Холдинги пользователя — агрегированные из таблицы portfolio."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT asset, amount FROM portfolio WHERE user_id = ? AND amount > 0 ORDER BY asset",
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def _get_holding(cursor, user_id, asset):
    cursor.execute(
        "SELECT amount FROM portfolio WHERE user_id = ? AND asset = ?",
        (user_id, asset)
    )
    row = cursor.fetchone()
    return row["amount"] if row else 0.0


def _apply_portfolio_delta(cursor, user_id, asset, delta):
    """delta > 0 при покупке, delta < 0 при продаже."""
    existing = _get_holding(cursor, user_id, asset)
    new_amount = existing + delta
    cursor.execute("""
        INSERT INTO portfolio (user_id, asset, amount) VALUES (?, ?, ?)
        ON CONFLICT (user_id, asset) DO UPDATE SET amount = excluded.amount
    """, (user_id, asset, new_amount))


def create_order(user_id, asset, order_type, amount, price):
    """Возвращает (ok: bool, error: str | None)."""
    conn = get_connection()
    cursor = conn.cursor()
    total_cost = amount * price

    if order_type == "buy":
        cursor.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
        balance = cursor.fetchone()["balance"]
        if balance < total_cost:
            conn.close()
            return False, "Недостаточно средств на балансе"
    else:
        held = _get_holding(cursor, user_id, asset)
        if held < amount:
            conn.close()
            return False, f"Недостаточно {asset} в портфеле (есть {held})"

    timestamp = datetime.now().isoformat()
    cursor.execute(
        "INSERT INTO orders (user_id, asset, order_type, amount, price, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, asset, order_type, amount, price, timestamp)
    )

    if order_type == "buy":
        cursor.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (total_cost, user_id))
        _apply_portfolio_delta(cursor, user_id, asset, amount)
    else:
        cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (total_cost, user_id))
        _apply_portfolio_delta(cursor, user_id, asset, -amount)

    conn.commit()
    conn.close()
    return True, None


def get_orders_for_user(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY timestamp DESC", (user_id,))
    orders = cursor.fetchall()
    conn.close()
    return orders
