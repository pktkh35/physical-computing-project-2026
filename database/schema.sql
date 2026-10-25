-- =====================================================
--  Smart Parking - MySQL Schema
-- =====================================================

CREATE DATABASE IF NOT EXISTS smart_parking
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE smart_parking;

CREATE TABLE IF NOT EXISTS parking_slots (
  slot_id     INT PRIMARY KEY,
  is_occupied TINYINT(1) NOT NULL DEFAULT 0,
  updated_at  DATETIME   NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS parking_logs (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  plate_number VARCHAR(20) NOT NULL,
  entry_time   DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_plate (plate_number),
  INDEX idx_entry (entry_time)
);

INSERT IGNORE INTO parking_slots (slot_id, is_occupied) VALUES (1,0);
