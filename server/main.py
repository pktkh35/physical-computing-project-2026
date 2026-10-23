"""
Smart Parking Server
  - รับข้อมูลจาก Arduino ผ่าน MQTT (Gate / Park)
  - อ่านทะเบียนด้วย YOLO + OCR
  - บันทึก MySQL
  - สั่ง Arduino (Set LCD / Open Gate / Set LED)
  - REST API ดูสถานะช่องจอด/ประวัติรถเข้า-ออก (http://localhost:8000/docs)
  - สั่งงานด้วยมือผ่าน MQTT topic parking/cmd/#

รัน:  uvicorn main:app --host 0.0.0.0 --port 8000
"""
import logging
import re
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI

import config as C
import db
from mqtt_client import ParkingMQTT
from plate_reader import PlateReader

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("server")

reader: PlateReader | None = None
mqttc: ParkingMQTT | None = None
_gate_lock = threading.Lock()
_last_open = 0.0


def plate_to_ascii(plate: str) -> str:
    """LCD แสดงตัวอักษรไทยไม่ได้ -> แสดงเฉพาะตัวเลข เช่น 1กข1234 -> 1-1234"""
    nums = re.findall(r"\d+", plate)
    return "-".join(nums) if nums else "UNKNOWN"


# ==================== Receive: Gate ====================
def handle_gate(payload: dict):
    """Arduino ตรวจเจอรถที่ประตู -> ประมวลผลใน thread แยก ไม่ให้ MQTT ค้าง"""
    if not payload.get("car", True):
        return
    if not _gate_lock.acquire(blocking=False):
        log.info("กำลังประมวลผลคันก่อนอยู่ ข้าม")
        return
    threading.Thread(target=_process_gate, daemon=True).start()


def _process_gate():
    global _last_open
    try:
        if time.time() - _last_open < C.GATE_COOLDOWN:
            log.info("อยู่ในช่วง cooldown หลังเปิดประตู ข้าม")
            return

        mqttc.set_lcd("Reading plate...", "Please wait")
        plate, _ = reader.read()

        if not plate:
            mqttc.set_lcd("Plate not found", "Please retry")
            return

        # รถคันนี้อยู่ในลานแล้ว -> ถือว่าขาออก
        open_log = db.find_open_log(plate)
        if open_log:
            db.mark_exit(open_log["id"])
            mqttc.set_lcd("Goodbye!", plate_to_ascii(plate))
            mqttc.open_gate()
            _last_open = time.time()
            return

        free = db.count_free_slots()
        if free <= 0:
            mqttc.set_lcd("Parking FULL", "Sorry")
            return

        db.insert_entry(plate)
        mqttc.set_lcd(f"Welcome {plate_to_ascii(plate)}", f"Free slot: {free}")
        mqttc.open_gate()
        _last_open = time.time()
    except Exception:
        log.exception("ประมวลผลรถที่ประตูไม่สำเร็จ")
        mqttc.set_lcd("System error", "Call staff")
    finally:
        _gate_lock.release()


# ==================== Receive: Park ====================
def handle_park(payload: dict):
    slot = int(payload["slot"])
    occupied = bool(payload["occupied"])
    db.update_slot(slot, occupied)
    mqttc.set_led(slot, "red" if occupied else "green")
    free = db.count_free_slots()
    mqttc.set_lcd("Smart Parking", f"Free slot: {free}")


# ==================== Receive: Command (แทน REST เดิม) ====================
def handle_cmd(cmd: str, payload: dict):
    """parking/cmd/<cmd> : gate/open, gate/scan, lcd, led"""
    if cmd == "gate/open":
        mqttc.open_gate(int(payload.get("duration", 5000)))
    elif cmd == "gate/scan":
        handle_gate({"car": True})   # ทดสอบกล้อง + OCR
    elif cmd == "lcd":
        mqttc.set_lcd(str(payload.get("line1", "")), str(payload.get("line2", "")))
    elif cmd == "led":
        color = payload.get("color")
        if color not in ("green", "red", "off"):
            log.warning("led color ต้องเป็น green, red หรือ off: %s", color)
            return
        mqttc.set_led(int(payload["slot"]), color)
    else:
        log.warning("ไม่รู้จักคำสั่ง: %s", cmd)


# ==================== FastAPI ====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    global reader, mqttc
    reader = PlateReader()
    mqttc = ParkingMQTT(on_gate=handle_gate, on_park=handle_park, on_cmd=handle_cmd)
    mqttc.start()
    # sync สถานะ LED ตามฐานข้อมูลตอนเริ่มระบบ
    time.sleep(1)
    for s in db.list_slots():
        mqttc.set_led(s["slot_id"], "red" if s["is_occupied"] else "green")
    mqttc.set_lcd("Smart Parking", f"Free slot: {db.count_free_slots()}")
    yield
    mqttc.stop()


app = FastAPI(title="Smart Parking API", lifespan=lifespan)


@app.get("/")
def root():
    return {"status": "ok", "free_slots": db.count_free_slots()}


@app.get("/slots")
def get_slots():
    return db.list_slots()


@app.get("/logs")
def get_logs(limit: int = 50):
    return db.list_logs(limit)
