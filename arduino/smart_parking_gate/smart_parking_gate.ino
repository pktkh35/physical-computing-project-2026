/*
 * =====================================================
 *  Smart Parking - GATE board (Arduino UNO R4 WiFi)
 * =====================================================
 *  Ultrasonic + Servo + LCD 16x2 (I2C)
 *  Pins: TRIG D2, ECHO D3, Servo D9, LCD SDA A4 / SCL A5
 *
 *  Library: PubSubClient, ArduinoJson v7, Servo (built-in), LiquidCrystal I2C
 *  Board: "Arduino UNO R4 WiFi"
 *  LCD text (free slots, plate) comes from server via parking/lcd/set
 */

#include <WiFiS3.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Servo.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// ================== ตั้งค่า ==================
const char* WIFI_SSID   = "pxnd";
const char* WIFI_PASS   = "12345678";
const char* MQTT_HOST   = "mqtt-dashboard.com";   // IP เครื่องที่รัน Mosquitto
const int   MQTT_PORT   = 1883;
const char* MQTT_USER   = "";               // เว้นว่างถ้าไม่ใช้
const char* MQTT_PASS   = "";
const char* CLIENT_ID   = "parking-gate";   // ต้องไม่ซ้ำกับบอร์ดอื่น

const char* T_GATE_DETECT = "parking/gate/detect";
const char* T_GATE_OPEN   = "parking/gate/open";
const char* T_LCD_SET     = "parking/lcd/set";

const int GATE_TRIG = 2;
const int GATE_ECHO = 3;
const int SERVO_PIN = 9;
const int GATE_DETECT_CM = 15;    // ใกล้กว่านี้ = มีรถ
const int SERVO_CLOSED   = 0;
const int SERVO_OPEN     = 90;

const unsigned long CLOSE_DELAY_MS = 5000;  // ไม่มีรถนานเท่านี้ถึงปิดไม้กั้น
const unsigned long DEBOUNCE_MS = 1000;  // ค่าต้องนิ่งนานเท่านี้ถึงจะนับว่าเปลี่ยน

// =============================================
WiFiClient netClient;
PubSubClient mqtt(netClient);
Servo gateServo;
LiquidCrystal_I2C lcd(0x27, 16, 2);   // ถ้าจอไม่ขึ้นลอง 0x3F

bool gateCarPresent = false;
bool gateRawLast = false;
unsigned long gateRawSince = 0;
bool gateIsOpen = false;
unsigned long gateOpenUntil = 0;
unsigned long gateClearSince = 0;  // 0 = ยังมีรถ/ยังไม่เริ่มนับ

long readDistanceCm(int trig, int echo) {
  digitalWrite(trig, LOW);
  delayMicroseconds(2);
  digitalWrite(trig, HIGH);
  delayMicroseconds(10);
  digitalWrite(trig, LOW);
  long dur = pulseIn(echo, HIGH, 25000);   // timeout ~4 m
  if (dur == 0) return 999;
  return dur * 0.0343 / 2;
}

void lcdShow(const char* l1, const char* l2) {
  lcd.clear();
  lcd.setCursor(0, 0); lcd.print(l1);
  lcd.setCursor(0, 1); lcd.print(l2);
}

void openGate(unsigned long durationMs) {
  gateServo.write(SERVO_OPEN);
  gateIsOpen = true;
  gateOpenUntil = millis() + durationMs;
  Serial.println("[GATE] open");
}

void closeGateIfDone() {
  if (!gateIsOpen || millis() < gateOpenUntil) return;
  // ปิดเมื่อไม่มีรถหน้าประตูต่อเนื่อง CLOSE_DELAY_MS
  if (readDistanceCm(GATE_TRIG, GATE_ECHO) < GATE_DETECT_CM) {
    gateClearSince = 0;
    return;
  }
  if (gateClearSince == 0) gateClearSince = millis();
  if (millis() - gateClearSince < CLOSE_DELAY_MS) return;
  gateServo.write(SERVO_CLOSED);
  gateIsOpen = false;
  gateClearSince = 0;
  Serial.println("[GATE] closed");
}

void publishGateDetect(long cm) {
  JsonDocument doc;
  doc["car"] = true;
  doc["distance"] = cm;
  char buf[64];
  serializeJson(doc, buf);
  mqtt.publish(T_GATE_DETECT, buf);
  Serial.print("[MQTT] -> "); Serial.print(T_GATE_DETECT); Serial.print(" "); Serial.println(buf);
}

void onMessage(char* topic, byte* payload, unsigned int len) {
  JsonDocument doc;
  if (deserializeJson(doc, payload, len)) {
    Serial.println("[MQTT] JSON ผิดรูปแบบ");
    return;
  }
  Serial.print("[MQTT] <- "); Serial.println(topic);

  if (strcmp(topic, T_GATE_OPEN) == 0) {
    openGate(doc["duration"] | 5000);
  } else if (strcmp(topic, T_LCD_SET) == 0) {
    lcdShow(doc["line1"] | "", doc["line2"] | "");
  }
}

void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  lcdShow("Connecting WiFi", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.print("\n[WiFi] IP: "); Serial.println(WiFi.localIP());
}

void connectMQTT() {
  while (!mqtt.connected()) {
    lcdShow("Connecting MQTT", MQTT_HOST);
    bool ok = strlen(MQTT_USER)
                ? mqtt.connect(CLIENT_ID, MQTT_USER, MQTT_PASS)
                : mqtt.connect(CLIENT_ID);
    if (ok) {
      mqtt.subscribe(T_GATE_OPEN, 1);
      mqtt.subscribe(T_LCD_SET, 1);
      Serial.println("[MQTT] connected");
      lcdShow("Smart Parking", "Ready");
    } else {
      Serial.print("[MQTT] fail rc="); Serial.println(mqtt.state());
      delay(2000);
    }
  }
}

void checkGate() {
  long cm = readDistanceCm(GATE_TRIG, GATE_ECHO);
  bool raw = cm < GATE_DETECT_CM;
  if (raw != gateRawLast) { gateRawLast = raw; gateRawSince = millis(); }
  if (millis() - gateRawSince < DEBOUNCE_MS) return;

  if (raw && !gateCarPresent && !gateIsOpen) {
    gateCarPresent = true;
    publishGateDetect(cm);       // แจ้ง server ครั้งเดียวต่อรถหนึ่งคัน
  } else if (!raw && gateCarPresent) {
    gateCarPresent = false;       // รถไปแล้ว พร้อมรับคันถัดไป
  }
}

void setup() {
  Serial.begin(115200);

  Wire.begin();
  lcd.init();
  lcd.backlight();

  pinMode(GATE_TRIG, OUTPUT);
  pinMode(GATE_ECHO, INPUT);
  gateServo.attach(SERVO_PIN);
  gateServo.write(SERVO_CLOSED);

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

  checkGate();
  closeGateIfDone();
}
