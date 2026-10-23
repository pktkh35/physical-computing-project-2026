/*
 * =====================================================
 *  Smart Parking - Arduino UNO / Mega (ไม่มี WiFi)
 * =====================================================
 *  ใช้เมื่อบอร์ดต่อเน็ตเองไม่ได้: ส่งข้อมูลทาง USB Serial
 *  แล้วให้ tools/serial_bridge.py แปลงเป็น MQTT ต่อ
 *
 *  โปรโตคอล Serial (9600 baud, 1 บรรทัด = 1 คำสั่ง)
 *   Arduino -> PC : GATE,<cm>            มีรถที่ประตู
 *                   SLOT,<n>,<0|1>       สถานะช่องจอด
 *   PC -> Arduino : OPEN,<ms>            เปิดไม้กั้น
 *                   LCD,<line1>|<line2>  แสดงข้อความ
 *                   LED,<n>,<green|red|off>
 *
 *  Library: Servo (มากับ IDE), LiquidCrystal I2C (Frank de Brabander)
 *  UNO มีขาจำกัด -> ตั้งไว้ 2 ช่องจอด (ใช้ Mega ได้มากกว่า)
 *  LCD I2C ใช้ขา A4 (SDA), A5 (SCL)
 */

#include <Servo.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// ---------- Front gate ----------
const int GATE_TRIG = 2;
const int GATE_ECHO = 3;
const int SERVO_PIN = 9;
const int GATE_DETECT_CM = 15;
const int SERVO_CLOSED = 0;
const int SERVO_OPEN = 90;

// ---------- Slots ----------
const int NUM_SLOTS = 2;
const int SLOT_TRIG[NUM_SLOTS]  = {4, 7};
const int SLOT_ECHO[NUM_SLOTS]  = {5, 8};
const int SLOT_GREEN[NUM_SLOTS] = {6, 10};
const int SLOT_RED[NUM_SLOTS]   = {11, 12};
const int SLOT_DETECT_CM = 10;

const unsigned long DEBOUNCE_MS = 1000;

Servo gateServo;
LiquidCrystal_I2C lcd(0x27, 16, 2);

bool gateCarPresent = false, gateRawLast = false, gateIsOpen = false;
unsigned long gateRawSince = 0, gateOpenUntil = 0;
bool slotOccupied[NUM_SLOTS], slotRawLast[NUM_SLOTS];
unsigned long slotRawSince[NUM_SLOTS];
String rxLine;

long readDistanceCm(int trig, int echo) {
  digitalWrite(trig, LOW);  delayMicroseconds(2);
  digitalWrite(trig, HIGH); delayMicroseconds(10);
  digitalWrite(trig, LOW);
  long dur = pulseIn(echo, HIGH, 25000);
  return dur == 0 ? 999 : dur * 0.0343 / 2;
}

void lcdShow(const String& l1, const String& l2) {
  lcd.clear();
  lcd.setCursor(0, 0); lcd.print(l1.substring(0, 16));
  lcd.setCursor(0, 1); lcd.print(l2.substring(0, 16));
}

void setLed(int idx, const String& color) {
  if (idx < 0 || idx >= NUM_SLOTS) return;
  digitalWrite(SLOT_GREEN[idx], color == "green");
  digitalWrite(SLOT_RED[idx],   color == "red");
}

void openGate(unsigned long ms) {
  gateServo.write(SERVO_OPEN);
  gateIsOpen = true;
  gateOpenUntil = millis() + ms;
}

void closeGateIfDone() {
  if (!gateIsOpen || millis() < gateOpenUntil) return;
  if (readDistanceCm(GATE_TRIG, GATE_ECHO) < GATE_DETECT_CM) {
    gateOpenUntil = millis() + 1000;
    return;
  }
  gateServo.write(SERVO_CLOSED);
  gateIsOpen = false;
}

void sendSlot(int i) {
  Serial.print("SLOT,"); Serial.print(i + 1); Serial.print(",");
  Serial.println(slotOccupied[i] ? 1 : 0);
}

// ---------- รับคำสั่งจาก PC ----------
void handleCommand(String line) {
  line.trim();
  int c1 = line.indexOf(',');
  if (c1 < 0) return;
  String cmd = line.substring(0, c1);
  String arg = line.substring(c1 + 1);

  if (cmd == "OPEN") {
    openGate(arg.toInt() > 0 ? arg.toInt() : 5000);
  } else if (cmd == "LCD") {
    int bar = arg.indexOf('|');
    if (bar < 0) lcdShow(arg, "");
    else lcdShow(arg.substring(0, bar), arg.substring(bar + 1));
  } else if (cmd == "LED") {
    int c2 = arg.indexOf(',');
    if (c2 > 0) setLed(arg.substring(0, c2).toInt() - 1, arg.substring(c2 + 1));
  } else if (cmd == "SYNC") {
    for (int i = 0; i < NUM_SLOTS; i++) sendSlot(i);
  }
}

void readSerial() {
  while (Serial.available()) {
    char ch = Serial.read();
    if (ch == '\n') { handleCommand(rxLine); rxLine = ""; }
    else if (ch != '\r' && rxLine.length() < 80) rxLine += ch;
  }
}

void checkGate() {
  long cm = readDistanceCm(GATE_TRIG, GATE_ECHO);
  bool raw = cm < GATE_DETECT_CM;
  if (raw != gateRawLast) { gateRawLast = raw; gateRawSince = millis(); }
  if (millis() - gateRawSince < DEBOUNCE_MS) return;
  if (raw && !gateCarPresent && !gateIsOpen) {
    gateCarPresent = true;
    Serial.print("GATE,"); Serial.println(cm);
  } else if (!raw && gateCarPresent) {
    gateCarPresent = false;
  }
}

void checkSlots() {
  for (int i = 0; i < NUM_SLOTS; i++) {
    bool raw = readDistanceCm(SLOT_TRIG[i], SLOT_ECHO[i]) < SLOT_DETECT_CM;
    if (raw != slotRawLast[i]) { slotRawLast[i] = raw; slotRawSince[i] = millis(); }
    if (millis() - slotRawSince[i] >= DEBOUNCE_MS && raw != slotOccupied[i]) {
      slotOccupied[i] = raw;
      setLed(i, raw ? "red" : "green");
      sendSlot(i);
    }
    delay(30);
  }
}

void setup() {
  Serial.begin(9600);
  lcd.init(); lcd.backlight();
  pinMode(GATE_TRIG, OUTPUT); pinMode(GATE_ECHO, INPUT);
  gateServo.attach(SERVO_PIN); gateServo.write(SERVO_CLOSED);
  for (int i = 0; i < NUM_SLOTS; i++) {
    pinMode(SLOT_TRIG[i], OUTPUT); pinMode(SLOT_ECHO[i], INPUT);
    pinMode(SLOT_GREEN[i], OUTPUT); pinMode(SLOT_RED[i], OUTPUT);
    slotOccupied[i] = slotRawLast[i] = false;
    slotRawSince[i] = 0;
    setLed(i, "green");
  }
  lcdShow("Smart Parking", "Waiting PC...");
}

void loop() {
  readSerial();
  checkGate();
  checkSlots();
  closeGateIfDone();
}
