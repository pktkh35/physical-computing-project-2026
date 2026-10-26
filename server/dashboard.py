"""
Dashboard: หน้าเว็บแสดงสถานะลานจอดจาก MySQL

ใช้ได้ 2 แบบ
  1) รวมกับ server หลัก (main.py include_router ไว้แล้ว)
       uvicorn main:app --host 0.0.0.0 --port 8000
  2) รันเฉพาะ dashboard (ไม่ต้องมี MQTT / กล้อง / YOLO) เหมาะกับตอนทดสอบด้วย mock data
       uvicorn dashboard:app --host 0.0.0.0 --port 8000

แล้วเปิด http://localhost:8000/dashboard
"""
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.responses import FileResponse, RedirectResponse

from db import get_cursor

STATIC = Path(__file__).resolve().parent / "static"

router = APIRouter()


def _q(sql: str, params: tuple = ()):
    with get_cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


@router.get("/dashboard", include_in_schema=False)
def dashboard_page():
    return FileResponse(STATIC / "dashboard.html")


@router.get("/api/dashboard", tags=["dashboard"])
def dashboard_data(days: int = 14):
    """ข้อมูลทั้งหมดที่หน้า dashboard ใช้ (เรียกครั้งเดียวต่อการรีเฟรช)"""
    days = max(1, min(days, 90))

    now = _q("SELECT NOW() AS now")[0]["now"]

    slots = _q("SELECT slot_id, is_occupied, updated_at FROM parking_slots ORDER BY slot_id")

    inside = _q(
        """SELECT plate_number, entry_time,
                  TIMESTAMPDIFF(MINUTE, entry_time, NOW()) AS minutes
           FROM parking_logs ORDER BY entry_time"""
    )

    today = _q("SELECT COUNT(*) AS n FROM entry_history WHERE entry_time >= CURDATE()")[0]["n"]
    # เมื่อวาน "ถึงเวลาเดียวกับตอนนี้" เพื่อเทียบกันได้แฟร์
    yesterday_same_time = _q(
        """SELECT COUNT(*) AS n FROM entry_history
           WHERE entry_time >= CURDATE() - INTERVAL 1 DAY
             AND entry_time <  NOW()      - INTERVAL 1 DAY"""
    )[0]["n"]

    hourly_today = _q(
        """SELECT HOUR(entry_time) AS h, COUNT(*) AS n FROM entry_history
           WHERE entry_time >= CURDATE() GROUP BY h"""
    )
    hourly_week = _q(
        """SELECT HOUR(entry_time) AS h, COUNT(*) AS n FROM entry_history
           WHERE entry_time >= CURDATE() - INTERVAL 7 DAY AND entry_time < CURDATE()
           GROUP BY h"""
    )
    t = {r["h"]: int(r["n"]) for r in hourly_today}
    w = {r["h"]: int(r["n"]) for r in hourly_week}
    hourly = [{"hour": h, "today": t.get(h, 0), "avg7": round(w.get(h, 0) / 7, 2)}
              for h in range(24)]

    daily_rows = _q(
        """SELECT DATE(entry_time) AS d, COUNT(*) AS n FROM entry_history
           WHERE entry_time >= CURDATE() - INTERVAL %s DAY
           GROUP BY d ORDER BY d""",
        (days - 1,),
    )
    # เติมวันที่ไม่มีรถให้เป็น 0 (กราฟจะได้ไม่ขาดช่วง)
    from datetime import timedelta
    counts = {r["d"]: int(r["n"]) for r in daily_rows}
    start = now.date() - timedelta(days=days - 1)
    daily = [{"date": start + timedelta(days=i), "count": counts.get(start + timedelta(days=i), 0)}
             for i in range(days)]

    recent = _q(
        "SELECT plate_number, entry_time FROM entry_history ORDER BY entry_time DESC LIMIT 12"
    )

    regulars = _q(
        """SELECT plate_number, COUNT(*) AS visits, MAX(entry_time) AS last_visit
           FROM entry_history
           WHERE entry_time >= CURDATE() - INTERVAL 30 DAY
           GROUP BY plate_number ORDER BY visits DESC, last_visit DESC LIMIT 6"""
    )

    occupied = sum(1 for s in slots if s["is_occupied"])
    return {
        "server_time": now,
        "summary": {
            "total_slots": len(slots),
            "occupied": occupied,
            "free": len(slots) - occupied,
            "inside": len(inside),
            "entries_today": int(today),
            "entries_yesterday_same_time": int(yesterday_same_time),
        },
        "slots": slots,
        "inside": inside,
        "hourly": hourly,
        "daily": daily,
        "recent": recent,
        "regulars": regulars,
    }


# ---------- รันเฉพาะ dashboard ----------
app = FastAPI(title="Smart Parking Dashboard")
app.include_router(router)


@app.get("/", include_in_schema=False)
def _root():
    return RedirectResponse("/dashboard")
