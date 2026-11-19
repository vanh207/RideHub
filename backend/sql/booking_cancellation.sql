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
