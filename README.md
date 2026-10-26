# Physical Computing Project 2026 - IT KMITL

## Smart Parking — ระบบลานจอดรถอัจฉริยะ

โครงงานรายวิชา **Physical Computing** ปีการศึกษา 2569 คณะเทคโนโลยีสารสนเทศ สถาบันเทคโนโลยีพระจอมเกล้าเจ้าคุณทหารลาดกระบัง (IT KMITL)

ระบบลานจอดรถที่อ่านป้ายทะเบียนด้วย YOLO + OCR แล้วเปิดไม้กั้นให้เอง พร้อมบอกสถานะช่องจอดด้วยไฟ LED และหน้า Dashboard แบบเรียลไทม์

| | ลิงก์ |
|---|---|
| 🌐 เว็บไซต์โครงงาน | https://pktkh35.github.io/physical-computing-project-2026/ |
| 💻 Source Code | https://github.com/pktkh35/physical-computing-project-2026 |
## ผู้จัดทำ

| ชื่อ-นามสกุล | รหัสนักศึกษา |
|---|---|
| ธีรวัจน์ รัศมีวิกัย | 68070072 |
| นภนธ์ นาคพันธุ์ | 68070077 |
| นิติภูมิ ฉิมนิล | 68070087 |
| วงศธร แซ่เฮ่า | 68070162 |

---

## บทคัดย่อ

โครงงานนี้พัฒนาระบบลานจอดรถอัจฉริยะที่เปิดไม้กั้นได้อัตโนมัติจากการอ่านป้ายทะเบียน และแสดงสถานะช่องจอดแบบเรียลไทม์ ที่ประตูทางเข้าใช้บอร์ด Arduino UNO R4 WiFi ร่วมกับเซนเซอร์อัลตราโซนิกตรวจจับรถ เซอร์โวมอเตอร์ควบคุมไม้กั้น และจอ LCD 16x2 แสดงจำนวนช่องว่าง ส่วนแต่ละช่องจอดมีเซนเซอร์อัลตราโซนิกตรวจสถานะและ LED สีเขียว/แดงบอกว่าช่องว่างหรือไม่ บอร์ดทั้งหมดสื่อสารกับเซิร์ฟเวอร์ Python (FastAPI) ผ่านโปรโตคอล MQTT เมื่อมีรถมาที่ประตู เซิร์ฟเวอร์จะดึงภาพจากกล้อง IP ใช้โมเดล YOLO หาตำแหน่งป้ายทะเบียน แล้วอ่านตัวอักษรด้วย EasyOCR จากนั้นตรวจสอบกับฐานข้อมูล MySQL เพื่อแยกรถขาเข้าและขาออกโดยใช้ประตูเดียว บันทึกเวลาเข้า และสั่งเปิดไม้กั้นเมื่อลานยังไม่เต็ม ผู้ดูแลติดตามสถานะช่องจอด สถิติรถเข้ารายชั่วโมงและรายวัน และประวัติการเข้าได้จากหน้า Dashboard ที่อัปเดตอัตโนมัติ

**คำสำคัญ:** Arduino, MQTT, YOLO, OCR, การรู้จำป้ายทะเบียน, Internet of Things

## วัตถุประสงค์

1. เพื่อพัฒนาระบบที่อ่านป้ายทะเบียนรถจากกล้อง และเปิดไม้กั้นได้อัตโนมัติโดยไม่ต้องมีคนเฝ้าประตู
2. เพื่อตรวจสถานะของแต่ละช่องจอด และแจ้งให้ผู้ขับขี่รู้ด้วยไฟ LED ที่ช่องจอดและจอ LCD ที่ประตูทางเข้า
3. เพื่อแยกรถขาเข้าและขาออกด้วยประตูเดียว โดยใช้ข้อมูลรถที่อยู่ในลานจากฐานข้อมูล และไม่เปิดไม้กั้นเมื่อลานเต็ม
4. เพื่อบันทึกประวัติรถเข้าลง MySQL และแสดงสถานะลานพร้อมสถิติรายชั่วโมงและรายวันบนหน้า Dashboard
5. เพื่อฝึกเชื่อมต่ออุปกรณ์ Physical Computing (เซนเซอร์, มอเตอร์, จอแสดงผล) เข้ากับซอฟต์แวร์ฝั่ง Server ผ่านโปรโตคอล IoT (MQTT)

## รายละเอียดโครงงาน

### ความสามารถของระบบ

- อ่านป้ายทะเบียนรถไทยจากกล้อง แล้วเปิดไม้กั้นอัตโนมัติ ไม่ต้องมีคนเฝ้า
- ใช้ประตูเดียวทั้งขาเข้าและขาออก โดยแยกจากข้อมูลในฐานข้อมูล
- ไม่เปิดไม้กั้นเมื่อลานเต็ม
- ไฟ LED เขียว/แดงที่แต่ละช่องจอด และจอ LCD บอกจำนวนช่องว่างที่ประตู
- หน้า Dashboard แสดงผังช่องจอด สถิติรายชั่วโมงและรายวัน และประวัติรถเข้า

### ภาพรวมระบบ

```
┌──────── Arduino UNO R4 WiFi ────────┐          ┌──────────── Server (Python) ────────────┐
│ บอร์ดประตู : Ultrasonic, Servo, LCD  │   MQTT   │ main.py       FastAPI + logic           │
│ บอร์ดช่องจอด: Ultrasonic, LED × N   │◄────────►│ plate_reader  IP Camera → YOLO → OCR    │
└─────────────────────────────────────┘Mosquitto │ db.py         MySQL                     │
                IP Camera ───── RTSP ───────────►│ dashboard.py  หน้าเว็บ Dashboard          │
                                                 └─────────────────────────────────────────┘
```

#### ขั้นตอนการทำงาน

1. Ultrasonic ที่ประตูเจอรถใกล้กว่า 15 ซม. นิ่งเกิน 1 วินาที บอร์ดประตูส่ง `parking/gate/detect` ครั้งเดียวต่อรถหนึ่งคัน
2. Server ดึงภาพจาก IP Camera ใช้ YOLO หาป้าย (เลือก 3 ภาพที่มั่นใจที่สุด) แล้ว OCR อ่านทะเบียน ถ้าอ่านไม่ได้จะไม่ทำอะไรต่อ
3. Server ตรวจกับ MySQL
   - ทะเบียนนี้**อยู่ในลานแล้ว** → ถือเป็นขาออก ลบจาก `parking_logs` แล้วเปิดไม้กั้น
   - **ลานเต็ม** → ไม่เปิดไม้กั้น
   - กรณีอื่น → บันทึกเวลาเข้าแล้วเปิดไม้กั้น
4. Servo ยกไม้กั้น 90° แล้วปิดเองเมื่อไม่มีรถขวางต่อเนื่อง 5 วินาที
5. Ultrasonic ในช่องจอดเปลี่ยนสถานะ ส่ง `parking/slot/status` Server อัปเดต MySQL สั่ง LED เปลี่ยนสี และอัปเดตจำนวนช่องว่างบน LCD

### อุปกรณ์

| อุปกรณ์ | จำนวน | หน้าที่ |
|---|---|---|
| Arduino UNO R4 WiFi | 1 + N | บอร์ดประตู 1 บอร์ด และบอร์ดช่องจอดช่องละ 1 บอร์ด |
| Ultrasonic HC-SR04 | 1 + N | ตรวจรถที่ประตูและในช่องจอด |
| Servo motor | 1 | ยกไม้กั้น |
| LCD 16x2 (I2C) | 1 | แสดงจำนวนช่องว่าง |
| LED เขียว / แดง + ตัวต้านทาน 220Ω | อย่างละ N | บอกสถานะช่องจอด |
| IP Camera หรือเว็บแคม | 1 | ถ่ายภาพป้ายทะเบียน |
| คอมพิวเตอร์ | 1 | รัน Server, MySQL, Mosquitto |

#### การต่อวงจร (Arduino UNO R4 WiFi)

| บอร์ด | อุปกรณ์ | ขา |
|---|---|---|
| ประตู | Ultrasonic TRIG / ECHO | D2 / D3 |
| ประตู | Servo | D9 |
| ประตู | LCD I2C SDA / SCL | A4 / A5 |
| ช่องจอด | Ultrasonic TRIG / ECHO | D4 / D5 |
| ช่องจอด | LED เขียว / แดง | D6 / D7 |

### เทคโนโลยีที่ใช้

Arduino (C++) · MQTT (Eclipse Mosquitto) · Python 3.10+ · FastAPI · Ultralytics YOLO · EasyOCR · OpenCV · MySQL 8 · Docker Compose

### โครงสร้างไฟล์

```
physical-computing-project-2026/
├── arduino/
│   ├── smart_parking_gate/          บอร์ดประตู (Ultrasonic, Servo, LCD)
│   ├── smart_parking_slot/          บอร์ดช่องจอด 1 บอร์ดต่อ 1 ช่อง (แก้ SLOT_ID)
│   └── smart_parking_uno_serial/    สำหรับ UNO/Mega ที่ไม่มี WiFi
├── server/
│   ├── main.py                      จุดเริ่มต้น server + REST API
│   ├── plate_reader.py              กล้อง → YOLO → OCR
│   ├── mqtt_client.py               รับ/ส่ง MQTT
│   ├── db.py                        ฟังก์ชัน MySQL
│   ├── dashboard.py                 API ของหน้า Dashboard
│   ├── static/dashboard.html        หน้าเว็บ Dashboard
│   ├── config.py, .env.example      ค่าตั้งค่า
│   ├── models/license_plate.pt      โมเดล YOLO ตรวจจับป้ายทะเบียน
│   └── requirements.txt
├── database/
│   ├── schema.sql                   สร้างตาราง
│   └── mock_data.sql                ข้อมูลจำลองสำหรับทดสอบ
├── tools/
│   ├── simulator.py                 จำลอง Arduino
│   ├── serial_bridge.py             แปลง Serial ↔ MQTT สำหรับ UNO
│   └── generate_mock_data.py        สร้างข้อมูลจำลองชุดใหม่
├── docs/                            เว็บไซต์โครงงาน (GitHub Pages)
├── mosquitto/config/mosquitto.conf
└── docker-compose.yml               MySQL + Mosquitto
```

## วิธีติดตั้งและรัน (Windows PowerShell)

**ต้องมี:** Docker Desktop, Python 3.10+, Arduino IDE

### 1. เปิด MySQL + Mosquitto
```powershell
cd physical-computing-project-2026
docker compose up -d
```
ตารางจะถูกสร้างให้อัตโนมัติ (user `root` / รหัส `root1234`)

### 2. ติดตั้งและรัน Server
```powershell
cd server
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env        # แก้ CAMERA_URL ให้ตรงกล้อง (ใช้เว็บแคมให้ตั้งเป็น 0)
uvicorn main:app --host 0.0.0.0 --port 8000
```
ถ้า `activate` ขึ้นว่า *running scripts is disabled* ให้รัน `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` ก่อน

### 3. อัปโหลดโค้ด Arduino
1. Boards Manager → ติดตั้ง **Arduino UNO R4 Boards**
2. Library Manager → ติดตั้ง `PubSubClient`, `ArduinoJson`, `LiquidCrystal I2C`
3. แก้ `WIFI_SSID`, `WIFI_PASS`, `MQTT_HOST` (IP เครื่องที่รัน Mosquitto) ในไฟล์ `.ino`
4. บอร์ดช่องจอดแต่ละบอร์ด แก้ `SLOT_ID` ให้ไม่ซ้ำกัน (1, 2, 3, …) แล้วอัปโหลด

### 4. เปิด Dashboard
เปิด http://localhost:8000/dashboard หน้าเว็บอัปเดตเองทุก 5 วินาที
เครื่องอื่นในวง WiFi เดียวกันเปิดได้ที่ `http://<IP เครื่อง server>:8000/dashboard`

### ทดสอบโดยไม่มีฮาร์ดแวร์

**จำลองบอร์ด Arduino**
```powershell
python tools/simulator.py
> g          # รถมาที่ประตู
> p 1 1      # ช่อง 1 มีรถ
> p 1 0      # ช่อง 1 ว่าง
```

**ใส่ข้อมูลจำลองเพื่อดู Dashboard** (⚠️ จะล้างข้อมูลเดิมในฐานข้อมูลทั้งหมด)
```powershell
docker cp database/mock_data.sql parking-mysql:/tmp/mock.sql
docker exec parking-mysql sh -c "mysql -uroot -proot1234 < /tmp/mock.sql"
cd server
uvicorn dashboard:app --port 8000       # เปิดเฉพาะ Dashboard ไม่ต้องมีกล้องและ MQTT
```

## MQTT Topics

| ทิศทาง | Topic | Payload ตัวอย่าง |
|---|---|---|
| Arduino → Server | `parking/gate/detect` | `{"car":true,"distance":10}` |
| Arduino → Server | `parking/slot/status` | `{"slot":1,"occupied":true}` |
| Server → Arduino | `parking/gate/open` | `{"action":"open","duration":5000}` |
| Server → Arduino | `parking/lcd/set` | `{"line1":"Free slot","line2":"3"}` |
| Server → Arduino | `parking/led/set` | `{"slot":1,"color":"red"}` |

## ฐานข้อมูล

| ตาราง | เก็บอะไร |
|---|---|
| `parking_slots` | สถานะแต่ละช่อง (ว่าง/มีรถ) และเวลาที่เปลี่ยนล่าสุด |
| `parking_logs` | รถที่อยู่ในลานตอนนี้ ลบออกเมื่อรถออก |
| `entry_history` | ประวัติรถเข้าทั้งหมด ไม่ลบ ใช้ทำสถิติ |

## REST API

| Method | Path | หน้าที่ |
|---|---|---|
| GET | `/` | สถานะระบบและจำนวนช่องว่าง |
| GET | `/slots` | สถานะทุกช่องจอด |
| GET | `/logs?limit=50` | ประวัติรถเข้า |
| GET | `/dashboard` | หน้าเว็บ Dashboard |
| GET | `/api/dashboard` | ข้อมูลที่หน้า Dashboard ใช้ |
| GET | `/docs` | ทดสอบ API (Swagger) |

## ข้อจำกัด

- LCD 16x2 แสดงภาษาไทยไม่ได้ จึงแสดงเฉพาะตัวเลขของทะเบียน เช่น `1กข1234` เป็น `1-1234`
- ความแม่นยำของ OCR ขึ้นกับมุมกล้องและแสง ควรติดกล้องให้เห็นป้ายตรง ๆ ระยะ 1–3 เมตร
- มีประตูเดียวใช้ทั้งเข้าและออก
- ลานเต็มหรืออ่านทะเบียนไม่ได้ ระบบไม่เปิดไม้กั้น แต่ยังไม่มีข้อความแจ้งบน LCD
- Mosquitto ตั้งค่าแบบไม่มีรหัสผ่าน เหมาะกับเครือข่ายภายในเท่านั้น

## แนวทางพัฒนาต่อ

- แสดงข้อความ "ลานเต็ม" หรือ "อ่านป้ายไม่ได้" บน LCD
- เก็บเวลาออกเพื่อคำนวณระยะเวลาจอดและค่าจอด
- เพิ่มรหัสผ่านและ TLS ให้ MQTT
- เทรนโมเดลให้อ่านป้ายทะเบียนไทยและชื่อจังหวัดได้แม่นยำขึ้น
- แยกประตูเข้าและประตูออก

## อ้างอิง

- Ultralytics YOLO — https://docs.ultralytics.com/
- EasyOCR — https://github.com/JaidedAI/EasyOCR
- Eclipse Mosquitto — https://mosquitto.org/
- FastAPI — https://fastapi.tiangolo.com/
- Arduino UNO R4 WiFi — https://docs.arduino.cc/hardware/uno-r4-wifi/
- Roboflow Universe (ชุดข้อมูลป้ายทะเบียน) — https://universe.roboflow.com/