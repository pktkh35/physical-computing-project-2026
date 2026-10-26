"""
สร้างไฟล์ SQL ข้อมูลจำลอง (mock) สำหรับทดสอบ Dashboard

    python tools/generate_mock_data.py                    # เขียน database/mock_data.sql
    python tools/generate_mock_data.py --days 60 --seed 7 # ย้อนหลัง 60 วัน, สุ่มชุดใหม่

เวลาในไฟล์ SQL เขียนแบบสัมพัทธ์กับ CURDATE()/NOW() ดังนั้นรันไฟล์วันไหน
ข้อมูลก็จะดู "สด" ตามวันนั้นเสมอ ไม่ต้อง generate ใหม่

ข้อมูลที่ได้
  - parking_slots : ช่อง 1..N (บางช่องมีรถ)
  - parking_logs  : รถที่ยังอยู่ในลานตอนนี้ (จำนวนเท่ากับช่องที่มีรถ)
  - entry_history : ประวัติรถเข้าย้อนหลัง พร้อมช่วงเวลาเร่งด่วนเช้า/เที่ยง/เย็น
"""
import argparse
import random
from pathlib import Path

CONSONANTS = "กขคฆงจฉชซฌญฎฐฒณดตถทธนบปผพฟภมยรลวศษสหฬอฮ"

# น้ำหนักจำนวนรถเข้าในแต่ละชั่วโมง (0-23) วันทำงาน / วันหยุด
WEEKDAY_HOURS = [0, 0, 0, 0, 0, 1, 2, 9, 14, 8, 4, 4, 7, 8, 4, 3, 4, 6, 7, 4, 3, 2, 1, 0]
WEEKEND_HOURS = [0, 0, 0, 0, 0, 0, 1, 1, 2, 4, 6, 7, 6, 5, 5, 5, 4, 4, 3, 3, 2, 1, 1, 0]


def random_plate(rng: random.Random) -> str:
    """ทะเบียนรูปแบบเดียวกับที่ OCR อ่านได้ เช่น 1กข1234, กท5521"""
    letters = "".join(rng.choice(CONSONANTS) for _ in range(2))
    prefix = str(rng.randint(1, 9)) if rng.random() < 0.6 else ""
    return f"{prefix}{letters}{rng.randint(1, 9999)}"


def sql_time(day_offset: int, minute_of_day: int) -> str:
    """เวลาแบบสัมพัทธ์: วันที่ (วันนี้ - day_offset) + นาทีของวัน"""
    day = "CURDATE()" if day_offset == 0 else f"(CURDATE() - INTERVAL {day_offset} DAY)"
    return f"{day} + INTERVAL {minute_of_day} MINUTE"


def build(days: int, slots: int, seed: int) -> str:
    rng = random.Random(seed)
    regulars = [random_plate(rng) for _ in range(35)]  # ขาประจำ (พนักงาน/นักศึกษา)

    def pick_plate() -> str:
        return rng.choice(regulars) if rng.random() < 0.7 else random_plate(rng)

    history = []  # (sql_time_expr, plate)
    # อ้างอิงวันในสัปดาห์จากวันที่ generate ใช้แค่กำหนดสัดส่วน ไม่ต้องตรงเป๊ะ
    for d in range(days, -1, -1):
        weekend = (d % 7) in (1, 2)  # ให้มีช่วงเสาร์-อาทิตย์ราว 2 วันทุกสัปดาห์
        weights = WEEKEND_HOURS if weekend else WEEKDAY_HOURS
        n = rng.randint(6, 11) if weekend else rng.randint(15, 24)
        for _ in range(n):
            hour = rng.choices(range(24), weights=weights)[0]
            history.append((sql_time(d, hour * 60 + rng.randint(0, 59)), pick_plate()))

    # รถที่ยังอยู่ในลานตอนนี้ = ช่องที่มีรถ (เว้นว่างไว้ 1 ช่อง)
    occupied = sorted(rng.sample(range(1, slots + 1), k=max(slots - 1, 0)))
    inside_minutes = sorted(rng.sample(range(8, 300), k=len(occupied)))
    inside_plates = rng.sample(regulars, k=len(occupied))

    out = [
        "-- =====================================================",
        "--  Smart Parking - Mock data (สร้างโดย tools/generate_mock_data.py)",
        f"--  seed={seed}, days={days}, slots={slots}",
        "--  ⚠ ล้างข้อมูลเดิมในทั้ง 3 ตารางก่อนใส่ข้อมูลจำลอง",
        "-- =====================================================",
        "",
        "SET NAMES utf8mb4;  -- กันภาษาไทยเพี้ยนเวลารันผ่าน client ที่ค่าเริ่มต้นไม่ใช่ utf8mb4",
        "USE smart_parking;",
        "",
        "DELETE FROM parking_logs;",
        "DELETE FROM entry_history;",
        "DELETE FROM parking_slots;",
        "ALTER TABLE parking_logs AUTO_INCREMENT = 1;",
        "ALTER TABLE entry_history AUTO_INCREMENT = 1;",
        "",
        "-- ---------- ช่องจอด ----------",
        "INSERT INTO parking_slots (slot_id, is_occupied, updated_at) VALUES",
    ]
    rows = []
    for s in range(1, slots + 1):
        if s in occupied:
            mins = inside_minutes[occupied.index(s)] - rng.randint(1, 4)
            rows.append(f"  ({s}, 1, NOW() - INTERVAL {max(mins, 1)} MINUTE)")
        else:
            rows.append(f"  ({s}, 0, NOW() - INTERVAL {rng.randint(3, 40)} MINUTE)")
    out.append(",\n".join(rows) + ";")

    out += ["", "-- ---------- ประวัติรถเข้า (ไม่ลบ) ----------"]
    for i in range(0, len(history), 200):
        chunk = history[i:i + 200]
        out.append("INSERT INTO entry_history (plate_number, entry_time) VALUES")
        out.append(",\n".join(f"  ('{p}', {t})" for t, p in chunk) + ";")
    out += [
        "",
        "-- ตัดรายการของวันนี้ที่เลยเวลาปัจจุบันออก (ข้อมูลอนาคตไม่ควรมี)",
        "DELETE FROM entry_history WHERE entry_time > NOW();",
        "",
        "-- ---------- รถที่อยู่ในลานตอนนี้ ----------",
        "-- ใส่ทั้ง parking_logs และ entry_history เหมือนที่ server ทำจริงใน db.insert_entry()",
    ]
    for plate, mins in zip(inside_plates, reversed(inside_minutes)):
        out.append(f"INSERT INTO parking_logs (plate_number, entry_time) "
                   f"VALUES ('{plate}', NOW() - INTERVAL {mins} MINUTE);")
    out += [
        "-- รถที่ยังอยู่ในลานต้องไม่มีประวัติ 'เข้า' หลังจากเวลาที่มันเข้ามาจอด",
        "DELETE eh FROM entry_history eh",
        "  JOIN parking_logs pl ON pl.plate_number = eh.plate_number",
        "  WHERE eh.entry_time >= pl.entry_time;",
        "INSERT INTO entry_history (plate_number, entry_time)",
        "  SELECT plate_number, entry_time FROM parking_logs;",
    ]
    out.append("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=30, help="จำนวนวันย้อนหลัง (ค่าเริ่มต้น 30)")
    ap.add_argument("--slots", type=int, default=4, help="จำนวนช่องจอด (ให้ตรง TOTAL_SLOTS)")
    ap.add_argument("--seed", type=int, default=2026, help="seed สุ่ม (เปลี่ยนเพื่อได้ชุดใหม่)")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent
                                         / "database" / "mock_data.sql"))
    a = ap.parse_args()

    Path(a.out).write_text(build(a.days, a.slots, a.seed), encoding="utf-8")
    print(f"เขียนไฟล์แล้ว: {a.out}")


if __name__ == "__main__":
    main()
