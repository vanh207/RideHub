-- TF199BD: index phục vụ tìm xe theo thời gian trống.
-- Chạy trên DB đã tồn tại; DB mới đã có 2 index này trong erd_migration.sql.
-- Cú pháp ALTER TABLE dùng ALGORITHM/LOCK để tránh khóa bảng trong MySQL 8.

ALTER TABLE bookings
    ADD INDEX ix_bookings_end_start_status_vehicle_hold (
        end_time,
        start_time,
        status,
        vehicle_id,
        hold_expires_at
    ),
    ALGORITHM=INPLACE,
    LOCK=NONE;

ALTER TABLE delivery_points
    ADD INDEX ix_delivery_points_store_active_area (store_id, is_active, area),
    ALGORITHM=INPLACE,
    LOCK=NONE;

ANALYZE TABLE bookings;
ANALYZE TABLE delivery_points;

-- Kiểm chứng sau khi chạy:
-- SELECT INDEX_NAME, IS_VISIBLE FROM information_schema.statistics
-- WHERE TABLE_SCHEMA = DATABASE()
--   AND INDEX_NAME IN (
--     'ix_bookings_end_start_status_vehicle_hold',
--     'ix_delivery_points_store_active_area'
--   )
-- GROUP BY INDEX_NAME, IS_VISIBLE;
