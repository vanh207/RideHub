-- TF199BD: rollback 2 index tìm xe theo thời gian trống.
-- Chỉ chạy khi cần gỡ migration TF199BD_index_tim_xe_trong.sql.

ALTER TABLE bookings
    DROP INDEX ix_bookings_end_start_status_vehicle_hold,
    ALGORITHM=INPLACE,
    LOCK=NONE;

ALTER TABLE delivery_points
    DROP INDEX ix_delivery_points_store_active_area,
    ALGORITHM=INPLACE,
    LOCK=NONE;

ANALYZE TABLE bookings;
ANALYZE TABLE delivery_points;

-- Kiểm chứng sau khi chạy:
-- SELECT COUNT(*) AS remaining_indexes
-- FROM information_schema.statistics
-- WHERE TABLE_SCHEMA = DATABASE()
--   AND INDEX_NAME IN (
--     'ix_bookings_end_start_status_vehicle_hold',
--     'ix_delivery_points_store_active_area'
--   );
