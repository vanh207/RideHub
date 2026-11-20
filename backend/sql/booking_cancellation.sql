-- ==============================================================================
-- RIDEHUB — BOOKING CANCELLATION COLUMNS
-- Dùng cho MySQL 8. app/db/auto_migration.py sẽ tự bổ sung nếu chạy server.
-- Chạy tay nếu cần:
--   mysql -u root -p app_db < backend/sql/booking_cancellation.sql
-- ==============================================================================

ALTER TABLE `bookings`
  ADD COLUMN `cancelled_at` DATETIME NULL AFTER `total_amount`,
  ADD COLUMN `cancelled_by` VARCHAR(30) NULL AFTER `cancelled_at`,
  ADD COLUMN `cancel_reason` TEXT NULL AFTER `cancelled_by`;

-- Các trạng thái mới được lưu trong cột status VARCHAR(40) có sẵn:
-- DEPOSIT_PAID, CONFIRMED, IN_PROGRESS, PENDING_SETTLEMENT, COMPLETED,
-- CANCELLED, EXPIRED.
-- Giữ lại dữ liệu legacy: PENDING, PENDING_STORE_CONFIRM, BOOKED.

CREATE TABLE IF NOT EXISTS `booking_status_history` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `booking_id` INT NOT NULL,
  `from_status` VARCHAR(40) NULL,
  `to_status` VARCHAR(40) NOT NULL,
  `changed_by` VARCHAR(30) NOT NULL,
  `changed_by_user_id` INT NULL,
  `reason` TEXT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  INDEX `ix_booking_status_history_booking_created` (`booking_id`, `created_at`),
  CONSTRAINT `fk_booking_status_history_booking`
    FOREIGN KEY (`booking_id`) REFERENCES `bookings` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_booking_status_history_user`
    FOREIGN KEY (`changed_by_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
