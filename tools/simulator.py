"""
จำลอง Arduino ผ่าน MQTT (ทดสอบ server ได้โดยไม่ต้องมีฮาร์ดแวร์)

    pip install paho-mqtt
    python simulator.py

คำสั่ง:
    g        = มีรถมาที่ประตู
    p 1 1    = ช่อง 1 มีรถจอด
    p 1 0    = ช่อง 1 ว่าง
    q        = ออก
"""
import json
import sys

import paho.mqtt.client as mqtt

HOST = sys.argv[1] if len(sys.argv) > 1 else "localhost"


def on_connect(c, u, f, rc, p):
    print(f"[SIM] connected to {HOST}")
    c.subscribe([("parking/gate/open", 1), ("parking/lcd/set", 1), ("parking/led/set", 1)])


def on_message(c, u, msg):
    d = json.loads(msg.payload.decode() or "{}")
    if msg.topic == "parking/lcd/set":
        print(f"\n  ┌────────────────┐\n  │{d.get('line1',''):<16}│\n"
              f"  │{d.get('line2',''):<16}│\n  └────────────────┘")
    elif msg.topic == "parking/gate/open":
        print(f"\n  [SERVO] ไม้กั้นเปิด {d.get('duration')} ms")
    elif msg.topic == "parking/led/set":
        icon = {"green": "🟢", "red": "🔴"}.get(d.get("color"), "⚫")
        print(f"\n  [LED] ช่อง {d.get('slot')} {icon}")
    print("> ", end="", flush=True)


c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="parking-sim")
c.on_connect = on_connect
c.on_message = on_message
c.connect(HOST, 1883)
c.loop_start()

print(__doc__)
while True:
    cmd = input("> ").strip().split()
    if not cmd:
        continue
    if cmd[0] == "q":
        break
    if cmd[0] == "g":
        c.publish("parking/gate/detect", json.dumps({"car": True, "distance": 10}), qos=1)
    elif cmd[0] == "p" and len(cmd) == 3:
        c.publish("parking/slot/status",
                  json.dumps({"slot": int(cmd[1]), "occupied": cmd[2] == "1"}), qos=1)
    else:
        print("คำสั่งไม่ถูกต้อง")
c.loop_stop()
