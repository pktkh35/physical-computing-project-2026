"""โหลดค่าตั้งค่าจากไฟล์ .env"""
import os
from dotenv import load_dotenv

load_dotenv()


def _bool(v: str) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "on")


MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER") or None
MQTT_PASS = os.getenv("MQTT_PASS") or None

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASS", ""),
    "database": os.getenv("DB_NAME", "smart_parking"),
}

_cam = os.getenv("CAMERA_URL", "0")
CAMERA_URL = int(_cam) if _cam.isdigit() else _cam

YOLO_MODEL = os.getenv("YOLO_MODEL", "models/license_plate.pt")
YOLO_CONF = float(os.getenv("YOLO_CONF", "0.5"))
OCR_LANGS = [s.strip() for s in os.getenv("OCR_LANGS", "th,en").split(",")]
OCR_MIN_CONF = float(os.getenv("OCR_MIN_CONF", "0.3"))

TOTAL_SLOTS = int(os.getenv("TOTAL_SLOTS", "4"))
GATE_COOLDOWN = float(os.getenv("GATE_COOLDOWN", "8"))

# ---------- MQTT Topics ----------
# Receive (Arduino -> Server)
TOPIC_GATE_DETECT = "parking/gate/detect"
TOPIC_SLOT_STATUS = "parking/slot/status"
# Send (Server -> Arduino)
TOPIC_GATE_OPEN = "parking/gate/open"
TOPIC_LCD_SET = "parking/lcd/set"
TOPIC_LED_SET = "parking/led/set"
# คำสั่งมือ: parking/cmd/gate/open, gate/scan, lcd, led (แทน REST เดิม)
TOPIC_CMD = "parking/cmd/#"
