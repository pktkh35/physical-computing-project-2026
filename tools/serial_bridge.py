"""
Serial <-> MQTT Bridge สำหรับ Arduino UNO/Mega ที่ไม่มี WiFi

    pip install pyserial paho-mqtt
    python serial_bridge.py --port COM3            (Windows)
    python serial_bridge.py --port /dev/ttyUSB0    (Linux/Mac)
"""
import argparse
import json
import threading
import time

import paho.mqtt.client as mqtt
import serial

T_GATE_DETECT = "parking/gate/detect"
T_SLOT_STATUS = "parking/slot/status"
T_GATE_OPEN = "parking/gate/open"
T_LCD_SET = "parking/lcd/set"
T_LED_SET = "parking/led/set"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True)
    ap.add_argument("--baud", type=int, default=9600)
    ap.add_argument("--mqtt", default="localhost")
    ap.add_argument("--mqtt-port", type=int, default=1883)
    args = ap.parse_args()

    ser = serial.Serial(args.port, args.baud, timeout=1)
    time.sleep(2)  # UNO reset ตัวเองตอนเปิดพอร์ต
    lock = threading.Lock()

    def ser_write(line: str):
        with lock:
            ser.write((line + "\n").encode())
        print(">> Arduino:", line)

    def on_connect(c, u, f, rc, p):
        print("MQTT connected")
        c.subscribe([(T_GATE_OPEN, 1), (T_LCD_SET, 1), (T_LED_SET, 1)])
        ser_write("SYNC,1")

    def on_message(c, u, msg):
        d = json.loads(msg.payload.decode() or "{}")
        if msg.topic == T_GATE_OPEN:
            ser_write(f"OPEN,{d.get('duration', 5000)}")
        elif msg.topic == T_LCD_SET:
            l1 = d.get("line1", "").replace("|", " ")
            l2 = d.get("line2", "").replace("|", " ")
            ser_write(f"LCD,{l1}|{l2}")
        elif msg.topic == T_LED_SET:
            ser_write(f"LED,{d.get('slot')},{d.get('color', 'off')}")

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="parking-bridge")
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(args.mqtt, args.mqtt_port)
    client.loop_start()

    print(f"Bridge {args.port} <-> mqtt://{args.mqtt}:{args.mqtt_port}")
    while True:
        line = ser.readline().decode(errors="ignore").strip()
        if not line:
            continue
        print("<< Arduino:", line)
        parts = line.split(",")
        if parts[0] == "GATE":
            client.publish(T_GATE_DETECT, json.dumps(
                {"car": True, "distance": int(parts[1]) if len(parts) > 1 else 0}), qos=1)
        elif parts[0] == "SLOT" and len(parts) == 3:
            client.publish(T_SLOT_STATUS, json.dumps(
                {"slot": int(parts[1]), "occupied": parts[2] == "1"}), qos=1)


if __name__ == "__main__":
    main()
