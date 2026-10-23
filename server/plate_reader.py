"""จับภาพจาก IP Camera -> YOLO หาป้าย -> OCR อ่านทะเบียน"""
import logging
import os
import re
import time

import cv2

from config import CAMERA_URL, OCR_LANGS, OCR_MIN_CONF, YOLO_CONF, YOLO_MODEL

log = logging.getLogger("plate")

# ตัวอักษรที่ยอมรับในป้ายทะเบียนไทย
_PLATE_CHARS = re.compile(r"[^0-9ก-ฮ]")


class PlateReader:
    def __init__(self):
        self.yolo = None
        if os.path.exists(YOLO_MODEL):
            from ultralytics import YOLO
            self.yolo = YOLO(YOLO_MODEL)
            log.info("โหลดโมเดล YOLO: %s", YOLO_MODEL)
        else:
            log.warning("ไม่พบโมเดล %s -> จะ OCR ทั้งภาพแทน", YOLO_MODEL)

        import easyocr
        log.info("กำลังโหลด EasyOCR %s (ครั้งแรกจะดาวน์โหลดโมเดล)...", OCR_LANGS)
        self.ocr = easyocr.Reader(OCR_LANGS, gpu=False)

    # ---------- กล้อง ----------
    @staticmethod
    def capture(retries: int = 3):
        for i in range(retries):
            cap = cv2.VideoCapture(CAMERA_URL)
            # อ่านทิ้งสัก 2-3 เฟรมเพื่อให้ได้ภาพล่าสุด (RTSP buffer)
            frame = None
            for _ in range(3):
                ok, f = cap.read()
                if ok:
                    frame = f
            cap.release()
            if frame is not None:
                return frame
            log.warning("อ่านภาพจากกล้องไม่ได้ (ครั้งที่ %d)", i + 1)
            time.sleep(0.5)
        return None

    # ---------- YOLO ----------
    def detect_plates(self, frame):
        """คืนรายการภาพป้ายที่ crop แล้ว เรียงตามความมั่นใจ"""
        if self.yolo is None:
            return [(frame, 1.0)]
        res = self.yolo(frame, conf=YOLO_CONF, verbose=False)[0]
        crops = []
        for box in res.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            crop = frame[max(0, y1):y2, max(0, x1):x2]
            if crop.size:
                crops.append((crop, float(box.conf[0])))
        crops.sort(key=lambda c: c[1], reverse=True)
        return crops

    # ---------- OCR ----------
    @staticmethod
    def _preprocess(img):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h = gray.shape[0]
        if h < 120:  # ขยายภาพป้ายเล็ก ๆ ให้อ่านง่ายขึ้น
            scale = 120 / max(h, 1)
            gray = cv2.resize(gray, None, fx=scale, fy=scale,
                              interpolation=cv2.INTER_CUBIC)
        gray = cv2.bilateralFilter(gray, 11, 17, 17)
        return gray

    def ocr_plate(self, img):
        results = self.ocr.readtext(self._preprocess(img))
        # เรียงจากบนลงล่าง ซ้ายไปขวา
        results.sort(key=lambda r: (r[0][0][1] // 20, r[0][0][0]))
        texts, confs = [], []
        for _, text, conf in results:
            if conf < OCR_MIN_CONF:
                continue
            clean = _PLATE_CHARS.sub("", text)
            # บรรทัดชื่อจังหวัดมักเป็นตัวอักษรไทยล้วนยาว ๆ -> ข้าม
            if len(clean) > 4 and not any(c.isdigit() for c in clean):
                continue
            if clean:
                texts.append(clean)
                confs.append(conf)
        if not texts:
            return "", 0.0
        return "".join(texts), sum(confs) / len(confs)

    # ---------- รวมทุกขั้นตอน ----------
    def read(self):
        """คืน (plate, confidence) หรือ ("", 0) ถ้าอ่านไม่ได้"""
        frame = self.capture()
        if frame is None:
            return "", 0.0

        best = ("", 0.0)
        for crop, det_conf in self.detect_plates(frame)[:3]:
            plate, ocr_conf = self.ocr_plate(crop)
            score = ocr_conf * det_conf
            if plate and score > best[1]:
                best = (plate, score)
        log.info("อ่านทะเบียนได้: %r (conf=%.2f)", best[0], best[1])
        return best
