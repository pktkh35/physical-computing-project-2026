/*
 * =====================================================
 *  Smart Parking - SLOT board (Arduino UNO R4 WiFi)
 * =====================================================
 *  One board per parking slot. Ultrasonic + LED green/red.
 *  Pins: TRIG D4, ECHO D5, LED green D6, LED red D7 (220 ohm each)
 *
 *  ก่อน Upload ให้แก้ SLOT_ID (1, 2, 3 ...) ให้ตรงกับ slot_id ใน MySQL
 *  CLIENT_ID ถูกสร้างจาก SLOT_ID อัตโนมัติ ไม่ซ้ำกันระหว่างบอร์ด
 *
 *  Library: PubSubClient, ArduinoJson v7
 *  Board: "Arduino UNO R4 WiFi"
 */

#include <WiFiS3.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// ================== ตั้งค่า ==================
const int   SLOT_ID     = 1;                // <-- แก้ต่อบอร์ด
const char* WIFI_SSID   = "pxnd";
const char* WIFI_PASS   = "12345678";
const char* MQTT_HOST   = "mqtt-dashboard.com";   // IP เครื่องที่รัน Mosquitto
const int   MQTT_PORT   = 1883;
const char* MQTT_USER   = "";               // เว้นว่างถ้าไม่ใช้
const char* MQTT_PASS   = "";

const char* T_SLOT_STATUS = "parking/slot/status";
const char* T_LED_SET     = "parking/led/set";

const int TRIG      = 4;
const int ECHO      = 5;
const int PIN_LED_GREEN = 6;
const int PIN_LED_RED   = 7;
const int SLOT_DETECT_CM = 10;

const unsigned long DEBOUNCE_MS = 1000;  // ค่าต้องนิ่งนานเท่านี้ถึงจะนับว่าเปลี่ยน

// =============================================
WiFiClient netClient;
PubSubClient mqtt(netClient);
char clientId[16];

bool occupied = false;
bool rawLast = false;
unsigned long rawSince = 0;

long readDistanceCm() {
  digitalWrite(TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG, LOW);
  long dur = pulseIn(ECHO, HIGH, 25000);   // timeout ~4 m
  if (dur == 0) return 999;
  return dur * 0.0343 / 2;
}

void setLed(const char* color) {
  digitalWrite(PIN_LED_GREEN, strcmp(color, "green") == 0);
  digitalWrite(PIN_LED_RED,   strcmp(color, "red")   == 0);
}

void publishSlot() {
  JsonDocument doc;
  doc["slot"] = SLOT_ID;
  doc["occupied"] = occupied;
  char buf[64];
  serializeJson(doc, buf);
  mqtt.publish(T_SLOT_STATUS, buf);
  Serial.print("[MQTT] -> "); Serial.print(T_SLOT_STATUS); Serial.print(" "); Serial.println(buf);
}

void onMessage(char* topic, byte* payload, unsigned int len) {
  JsonDocument doc;
  if (deserializeJson(doc, payload, len)) {
    Serial.println("[MQTT] JSON ผิดรูปแบบ");
    return;
  }
  // topic เดียวกันถูกส่งถึงทุกบอร์ด ทำเฉพาะของช่องตัวเอง
  if (strcmp(topic, T_LED_SET) == 0 && (doc["slot"] | 0) == SLOT_ID) {
    setLed(doc["color"] | "off");
  }
}

void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.print("\n[WiFi] IP: "); Serial.println(WiFi.localIP());
}

void connectMQTT() {
  while (!mqtt.connected()) {
    bool ok = strlen(MQTT_USER)
                ? mqtt.connect(clientId, MQTT_USER, MQTT_PASS)
                : mqtt.connect(clientId);
    if (ok) {
      mqtt.subscribe(T_LED_SET, 1);
      Serial.println("[MQTT] connected");
      publishSlot();   // ให้ server sync สถานะ
    } else {
      Serial.print("[MQTT] fail rc="); Serial.println(mqtt.state());
      delay(2000);
    }
  }
}

void checkSlot() {
  bool raw = readDistanceCm() < SLOT_DETECT_CM;
  if (raw != rawLast) { rawLast = raw; rawSince = millis(); }
  if (millis() - rawSince >= DEBOUNCE_MS && raw != occupied) {
    occupied = raw;
    setLed(raw ? "red" : "green");   // ตอบสนองทันที server จะยืนยันซ้ำ
    publishSlot();
  }
}

void setup() {
  Serial.begin(115200);
  snprintf(clientId, sizeof(clientId), "parking-slot%d", SLOT_ID);

  pinMode(TRIG, OUTPUT);
  pinMode(ECHO, INPUT);
  pinMode(PIN_LED_GREEN, OUTPUT);
  pinMode(PIN_LED_RED, OUTPUT);
  setLed("green");

  connectWiFi();
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(onMessage);
  mqtt.setBufferSize(512);
  connectMQTT();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) connectWiFi();
  if (!mqtt.connected()) connectMQTT();
  mqtt.loop();

  checkSlot();
  delay(30);
}
