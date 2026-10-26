# Smart Parking — Arduino + MQTT + Python + MySQL

ระบบที่จอดรถอัจฉริยะ อ่านป้ายทะเบียนด้วย YOLO + OCR, เปิดไม้กั้นอัตโนมัติ และแสดงสถานะช่องจอดด้วย LED

```
┌──────────── Arduino UNO R4 WiFi ───────┐        ┌───────────── Server (Python) ─────────────┐
│ Front gate : Ultrasonic, Servo, LCD     │  MQTT  │ main.py      FastAPI + logic              │
│ Parking    : Ultrasonic, LED x N        │◄──────►│ plate_reader IP Camera → YOLO → OCR       │
└─────────────────────────────────────────┘Mosquitto│ db.py        MySQL                        │
                IP Camera ──── RTSP ───────────────►└───────────────────────────────────────────┘
```

## โครงสร้างไฟล์

```
smart-parking/
├── arduino/
│   ├── smart_parking_gate/           R4 WiFi บอร์ดประตู (Ultrasonic, Servo, LCD)
│   ├── smart_parking_slot/           R4 WiFi บอร์ดช่องจอด 1 บอร์ด/ช่อง (แก้ SLOT_ID)
│   └── smart_parking_uno_serial/     UNO/Mega ส่งผ่าน USB Serial
├── server/
│   ├── main.py                       จุดเริ่มต้น server + REST API
│   ├── mqtt_client.py                Send / Receive MQTT
│   ├── plate_reader.py               กล้อง + YOLO + OCR
│   ├── db.py                         ฟังก์ชัน MySQL
│   ├── dashboard.py                  หน้า Dashboard (/dashboard) + API (/api/dashboard)
│   ├── static/dashboard.html         หน้าเว็บ Dashboard
│   ├── config.py                     อ่านค่าจาก .env
│   ├── .env.example
│   └── requirements.txt
├── database/schema.sql               สร้างตาราง MySQL
├── database/mock_data.sql            ข้อมูลจำลองสำหรับทดสอบ Dashboard
├── mosquitto/config/mosquitto.conf
├── tools/
│   ├── simulator.py                  จำลอง Arduino (ทดสอบไม่ต้องมีบอร์ด)
│   ├── serial_bridge.py              ตัวแปลง Serial ↔ MQTT สำหรับ UNO
│   └── generate_mock_data.py         สร้าง database/mock_data.sql ชุดใหม่
└── docker-compose.yml                MySQL + Mosquitto
```

## MQTT Topics

| ทิศทาง | Topic | Payload ตัวอย่าง | ความหมาย |
|---|---|---|---|
| Receive (Arduino → Server) | `parking/gate/detect` | `{"car":true,"distance":10}` | **Gate** มีรถมาที่ประตู |
| Receive (Arduino → Server) | `parking/slot/status` | `{"slot":1,"occupied":true}` | **Park** สถานะช่องจอด |
| Send (Server → Arduino) | `parking/lcd/set` | `{"line1":"Welcome","line2":"Free slot: 3"}` | **Set LCD** |
| Send (Server → Arduino) | `parking/gate/open` | `{"action":"open","duration":5000}` | **Open Gate** |
| Send (Server → Arduino) | `parking/led/set` | `{"slot":1,"color":"red"}` | **Set LED** (`green`/`red`/`off`) |

## ขั้นตอนการทำงาน

1. Ultrasonic ที่ประตูเจอรถ (ใกล้กว่า 15 ซม.) นิ่งเกิน 1 วินาที → Arduino ส่ง `parking/gate/detect` (ครั้งเดียวต่อรถ 1 คัน)
2. Server ประมวลผลใน thread แยก (มี lock กันซ้อน และ cooldown `GATE_COOLDOWN` วินาทีหลังเปิดประตู)
   ดึงภาพจาก IP Camera → YOLO หาป้าย (crop สูงสุด 3 อันที่มั่นใจสุด) → OCR อ่านทะเบียน
   ถ้าอ่านทะเบียนไม่ได้ จะไม่ทำอะไรต่อ
3. Server ตรวจใน MySQL (ทุกคันเข้าได้ ไม่ต้องลงทะเบียน)
   - รถคันนี้ **อยู่ในลานแล้ว** → ถือเป็นขาออก ลบจาก `parking_logs` (ไม่เก็บเวลาออก; `entry_history` ยังอยู่) → Set LCD (ช่องว่าง) → Open Gate
   - **ลานเต็ม** → ไม่เปิดประตู
   - ผ่าน → บันทึกเวลาเข้า (ลง `parking_logs` และ `entry_history`) → Set LCD (ช่องว่าง) → Open Gate
4. Servo ยกไม้กั้น 90° แล้วปิดเองเมื่อครบเวลาและเซนเซอร์ไม่เจอรถขวางต่อเนื่อง 5 วินาที
5. Ultrasonic ที่ช่องจอดเปลี่ยนสถานะ → `parking/slot/status` → Server อัปเดต MySQL แล้วส่ง Set LED และ LCD (จำนวนช่องว่าง)

---

## วิธีติดตั้ง

### 1) MySQL + Mosquitto

**ใช้ Docker (ง่ายสุด)**
```bash
docker compose up -d
```
ตารางจะถูกสร้างอัตโนมัติ (รหัส root คือ `root1234`)

**ไม่ใช้ Docker**
- ติดตั้ง MySQL แล้วรัน `mysql -u root -p < database/schema.sql`
- ติดตั้ง Mosquitto แล้วรันด้วย `mosquitto -c mosquitto/config/mosquitto.conf` (Windows: แก้ `persistence_location` เป็นโฟลเดอร์ในเครื่อง)

### 2) Python Server (Python 3.10+)
```bash
cd server
python -m venv venv
venv\Scripts\activate            # Windows
# source venv/bin/activate       # Mac/Linux
pip install -r requirements.txt
copy .env.example .env           # Mac/Linux: cp .env.example .env
# แก้ .env: CAMERA_URL, DB_PASS ฯลฯ
uvicorn main:app --host 0.0.0.0 --port 8000
```
เปิด http://localhost:8000/docs เพื่อดูและทดสอบ API

**โมเดล YOLO:** ต้องใช้โมเดลที่เทรนให้ตรวจจับป้ายทะเบียน (โมเดลทั่วไปอย่าง `yolov8n.pt` หาป้ายไม่ได้) วางไฟล์ไว้ที่ `server/models/license_plate.pt`
- เทรนเองด้วย Ultralytics จาก dataset ป้ายทะเบียนไทยบน Roboflow Universe
- ถ้ายังไม่มีโมเดล ระบบจะ OCR ทั้งภาพแทน ใช้ทดสอบได้แต่แม่นยำน้อยกว่า

### 3) Arduino

**Arduino UNO R4 WiFi (แนะนำ)** — ใช้ 1 บอร์ดสำหรับประตู (`arduino/smart_parking_gate/`) + 1 บอร์ดต่อช่องจอด (`arduino/smart_parking_slot/` แก้ `SLOT_ID` ก่อน Upload แต่ละบอร์ด) ดูวงจรในหัวข้อ "การต่อวงจร" ด้านล่าง
1. Boards Manager → ติดตั้ง **Arduino UNO R4 Boards** → เลือก *Arduino UNO R4 WiFi*
2. Library Manager → `PubSubClient`, `ArduinoJson`, `LiquidCrystal I2C` (Servo มากับบอร์ด)
3. แก้ `WIFI_SSID`, `WIFI_PASS`, `MQTT_HOST` แล้ว Upload
4. ต่อวงจรตามหัวข้อ "การต่อวงจร Arduino UNO R4 WiFi" ด้านล่าง
5. `DELETE FROM parking_slots WHERE slot_id>3;`

**Arduino UNO / Mega** — เปิด `arduino/smart_parking_uno_serial/...ino` (รองรับ 2 ช่องจอด) แล้วรันตัวแปลงบนคอม
```bash
pip install pyserial paho-mqtt
python tools/serial_bridge.py --port COM3
```
> ถ้าใช้ UNO 2 ช่อง ให้ลบช่อง 3, 4 ออกจาก MySQL: `DELETE FROM parking_slots WHERE slot_id>2;`

### 4) ทดสอบโดยไม่มีฮาร์ดแวร์
```bash
python tools/simulator.py
> g          # จำลองรถมาที่ประตู (server จะดึงภาพกล้อง/เว็บแคม)
> p 1 1      # ช่อง 1 มีรถ
> p 1 0      # ช่อง 1 ว่าง
```
ตั้ง `CAMERA_URL=0` ใน `.env` เพื่อใช้เว็บแคมแทน IP Camera ระหว่างทดสอบ

### 5) Dashboard + ข้อมูลจำลอง

ใส่ข้อมูลจำลอง (⚠ จะล้างข้อมูลเดิมใน `parking_slots`, `parking_logs`, `entry_history` ทั้งหมด)
```bash
# ใช้ Docker
docker exec -i parking-mysql mysql -uroot -proot1234 < database/mock_data.sql
# ไม่ใช้ Docker
mysql -u root -p < database/mock_data.sql
```
ข้อมูลที่ได้: ช่องจอด 4 ช่อง (มีรถ 3 ช่อง), รถที่อยู่ในลาน 3 คัน, ประวัติรถเข้าย้อนหลัง 30 วัน ~500 รายการ
เวลาในไฟล์อ้างอิงจาก `NOW()`/`CURDATE()` จึงรันวันไหนข้อมูลก็เป็นของ "วันนี้" เสมอ
อยากได้ชุดใหม่: `python tools/generate_mock_data.py --days 60 --seed 7`

เปิด Dashboard
```bash
cd server
uvicorn main:app --host 0.0.0.0 --port 8000        # server เต็ม (ต้องมี MQTT broker)
uvicorn dashboard:app --host 0.0.0.0 --port 8000   # เฉพาะ dashboard ใช้แค่ MySQL
```
แล้วเปิด http://localhost:8000/dashboard (รีเฟรชข้อมูลเองทุก 5 วินาที)

---

## การต่อวงจร Arduino UNO R4 WiFi

| อุปกรณ์ | ขา R4 |
|---|---|
| Gate Ultrasonic TRIG / ECHO | 2 / 3 |
| Servo (สายสัญญาณ) | 9 |
| LCD I2C SDA / SCL | A4 / A5 |
| **บอร์ดช่องจอด (ทุกบอร์ดต่อเหมือนกัน)** TRIG / ECHO / LED เขียว / LED แดง | 4 / 5 / 6 / 7 |

- HC-SR04 และ Servo ใช้ไฟ **5V** ส่วน GND ต้องต่อร่วมกันภายในแต่ละบอร์ด (R4 เป็น 5V ต่อขา ECHO ตรงได้)
- LED ทุกดวงต่อตัวต้านทาน 220Ω
- Servo กินกระแสมาก ถ้าบอร์ดรีเซ็ตตอนเปิดไม้กั้น ให้ใช้ไฟเลี้ยงแยก
- ถ้า LCD ไม่ขึ้น ลองเปลี่ยน address `0x27` เป็น `0x3F`

## การต่อวงจร Arduino UNO

| อุปกรณ์ | ขา UNO |
|---|---|
| Gate Ultrasonic TRIG / ECHO | 2 / 3 |
| Servo | 9 |
| LCD I2C SDA / SCL | A4 / A5 |
| ช่อง 1 TRIG / ECHO / เขียว / แดง | 4 / 5 / 6 / 11 |
| ช่อง 2 | 7 / 8 / 10 / 12 |

---

## REST API (ดูข้อมูล)

| Method | Path | หน้าที่ |
|---|---|---|
| GET | `/` | สถานะระบบ + จำนวนช่องว่าง |
| GET | `/slots` | สถานะทุกช่องจอด |
| GET | `/logs?limit=50` | ประวัติรถที่เข้าลาน (เก็บเฉพาะทะเบียน + เวลาเข้า ไม่ลบ) |
| GET | `/dashboard` | หน้าเว็บ Dashboard |
| GET | `/api/dashboard?days=14` | ข้อมูลทั้งหมดที่ Dashboard ใช้ (สรุป, ช่องจอด, รถในลาน, กราฟรายชั่วโมง/รายวัน, ขาประจำ) |

## คำสั่งมือผ่าน MQTT (แทน REST เดิม)

Server subscribe `parking/cmd/#` — publish ได้จากเครื่องไหนก็ได้ที่ต่อ broker

| Topic | Payload | หน้าที่ |
|---|---|---|
| `parking/cmd/gate/open` | `{"duration":5000}` (ไม่ใส่ก็ได้) | สั่งเปิดไม้กั้น |
| `parking/cmd/gate/scan` | `{}` | สั่งอ่านทะเบียนทันที (ทดสอบกล้อง) |
| `parking/cmd/lcd` | `{"line1":"...","line2":"..."}` | Set LCD |
| `parking/cmd/led` | `{"slot":1,"color":"red"}` | Set LED |

```bash
mosquitto_pub -t parking/cmd/gate/open -m '{}'
```

## ข้อจำกัดที่ควรรู้

- LCD 16x2 แสดงภาษาไทยไม่ได้ จึงแสดงเฉพาะตัวเลขของทะเบียน เช่น `1กข1234` จะเป็น `1-1234`
- ความแม่นยำของ OCR ขึ้นกับมุมกล้องและแสง ควรติดกล้องให้เห็นป้ายตรง ๆ ระยะ 1–3 เมตร
- ระบบมีประตูเดียว ใช้ทั้งเข้าและออก (แยกจากการเทียบว่าทะเบียนนี้อยู่ในลานหรือไม่)
- Mosquitto ตั้งค่าแบบไม่มีรหัสผ่าน เหมาะกับเครือข่ายภายในเท่านั้น
- `MQTT_HOST` ในไฟล์ `.ino` ต้องแก้ให้ตรงกับ broker ของคุณ (ค่าในโค้ดตอนนี้เป็น broker สาธารณะ `mqtt-dashboard.com` ซึ่งใครก็อ่าน topic ได้)
- ลานเต็มหรืออ่านทะเบียนไม่ได้ ระบบแค่ไม่เปิดประตู ยังไม่มีข้อความแจ้งบน LCD


## Contributors

| ID       | Name                                       | Img                                                                             |
|----------|--------------------------------------------|---------------------------------------------------------------------------------|
| 68070072 | นายธีรวัจน์ รัศมีวิกัย (ธีร์)          | <img alt="Thee" height="150" src="assets/img/Thee.jpg" width="150"/> |
| 68070077 | นายนภนธ์ นาคพันธุ์ (ตอง) | <img alt="Tong" height="150" src="assets/img/Tong.jpg" width="150"/>     |
| 68070087 | นายนิติภูมิ ฉิมนิล (ปอนด์)          | <img alt="Pond" height="150" src="assets/img/Pond.jpg" width="150"/>    |
| 68070162 | นายวงศธร แซ่เฮ่า (อ้น)        | <img alt="Aon" height="150" src="assets/img/Aon.jpg" width="150"/>     |