"""ฟังก์ชันติดต่อฐานข้อมูล MySQL"""
from contextlib import contextmanager

import mysql.connector
from mysql.connector import pooling

from config import DB_CONFIG

_pool = pooling.MySQLConnectionPool(pool_name="parking", pool_size=5, **DB_CONFIG)


@contextmanager
def get_cursor(commit: bool = False):
    conn = _pool.get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        yield cur
        if commit:
            conn.commit()
    except mysql.connector.Error:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


# ---------------- slots ----------------
def update_slot(slot_id: int, occupied: bool):
    with get_cursor(commit=True) as cur:
        cur.execute(
            """INSERT INTO parking_slots (slot_id, is_occupied) VALUES (%s,%s)
               ON DUPLICATE KEY UPDATE is_occupied=VALUES(is_occupied)""",
            (slot_id, int(occupied)),
        )


def list_slots():
    with get_cursor() as cur:
        cur.execute("SELECT * FROM parking_slots ORDER BY slot_id")
        return cur.fetchall()


def count_free_slots() -> int:
    with get_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM parking_slots WHERE is_occupied=0")
        return int(cur.fetchone()["n"])


# ---------------- logs ----------------
def find_open_log(plate: str):
    """หา log ที่รถคันนี้เข้าแล้วแต่ยังไม่ออก"""
    with get_cursor() as cur:
        cur.execute(
            """SELECT * FROM parking_logs
               WHERE plate_number=%s AND exit_time IS NULL
               ORDER BY entry_time DESC LIMIT 1""",
            (plate,),
        )
        return cur.fetchone()


def insert_entry(plate: str) -> int:
    with get_cursor(commit=True) as cur:
        cur.execute("INSERT INTO parking_logs (plate_number) VALUES (%s)", (plate,))
        return cur.lastrowid


def mark_exit(log_id: int):
    with get_cursor(commit=True) as cur:
        cur.execute("UPDATE parking_logs SET exit_time=NOW() WHERE id=%s", (log_id,))


def list_logs(limit: int = 50):
    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM parking_logs ORDER BY entry_time DESC LIMIT %s", (limit,)
        )
        return cur.fetchall()
