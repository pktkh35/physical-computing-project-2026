"""MQTT client ฝั่ง Server: Send (Set LCD / Open Gate / Set LED) และ Receive (Gate / Park)"""
import json
import logging

import paho.mqtt.client as mqtt

import config as C

log = logging.getLogger("mqtt")


class ParkingMQTT:
    def __init__(self, on_gate, on_park, on_cmd):
        self.on_gate = on_gate   # callback(payload: dict)
        self.on_park = on_park   # callback(payload: dict)
        self.on_cmd = on_cmd     # callback(cmd: str, payload: dict)  เช่น "gate/open"
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                  client_id="parking-server")
        if C.MQTT_USER:
            self.client.username_pw_set(C.MQTT_USER, C.MQTT_PASS)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def start(self):
        self.client.connect(C.MQTT_HOST, C.MQTT_PORT, keepalive=60)
        self.client.loop_start()

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()

    # ---------- Receive ----------
    def _on_connect(self, client, userdata, flags, reason_code, properties):
        log.info("เชื่อมต่อ MQTT broker แล้ว (%s)", reason_code)
        client.subscribe([(C.TOPIC_GATE_DETECT, 1), (C.TOPIC_SLOT_STATUS, 1),
                          (C.TOPIC_CMD, 1)])

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode() or "{}")
        except json.JSONDecodeError:
            log.warning("payload ไม่ใช่ JSON: %s", msg.payload)
            return
        log.info("<- %s %s", msg.topic, payload)
        try:
            if msg.topic == C.TOPIC_GATE_DETECT:
                self.on_gate(payload)
            elif msg.topic == C.TOPIC_SLOT_STATUS:
                self.on_park(payload)
            elif msg.topic.startswith("parking/cmd/"):
                self.on_cmd(msg.topic[len("parking/cmd/"):], payload)
        except Exception:
            log.exception("จัดการข้อความ %s ไม่สำเร็จ", msg.topic)

    # ---------- Send ----------
    def _pub(self, topic, data):
        log.info("-> %s %s", topic, data)
        self.client.publish(topic, json.dumps(data, ensure_ascii=False), qos=1)

    def set_lcd(self, line1: str, line2: str = ""):
        # LCD 16x2 แสดงภาษาไทยไม่ได้ จึงส่งเป็นอังกฤษ/ตัวเลข
        self._pub(C.TOPIC_LCD_SET, {"line1": line1[:16], "line2": line2[:16]})

    def open_gate(self, duration_ms: int = 5000):
        self._pub(C.TOPIC_GATE_OPEN, {"action": "open", "duration": duration_ms})

    def set_led(self, slot: int, color: str):
        """color: green | red | off"""
        self._pub(C.TOPIC_LED_SET, {"slot": slot, "color": color})
