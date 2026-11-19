-- Dữ liệu mẫu cho API POST /api/bookings (TF197DE).
-- Chạy trên MySQL 8 sau khi đã chạy sql/init.sql hoặc sql/erd_migration.sql.
-- Dùng bộ ID 82xx/83xx/84xx/85xx/86xx/87xx để không đụng dữ liệu thật.
-- Thời gian tương đối với NOW() để test được nhiều lần.

SET NAMES utf8mb4;
START TRANSACTION;

-- Xóa dữ liệu test cũ theo thứ tự khóa ngoại.
DELETE FROM vehicle_schedules WHERE vehicle_id IN (8301, 8302, 8303, 8304, 8305);
DELETE FROM vehicle_reservations WHERE vehicle_id IN (8301, 8302, 8303, 8304, 8305);
DELETE FROM bookings WHERE vehicle_id IN (8301, 8302, 8303, 8304, 8305);
DELETE FROM delivery_points WHERE id IN (8401, 8402, 8403);
DELETE FROM vehicles WHERE id IN (8301, 8302, 8303, 8304, 8305);
DELETE FROM stores WHERE id IN (8201, 8202, 8203);
DELETE FROM users WHERE id IN (8201, 8202, 8203);

INSERT INTO users (id, phone, full_name, status) VALUES
(8201, '0900008201', 'Chủ cửa hàng test', 'ACTIVE'),
(8202, '0900008202', 'Khách hàng test', 'ACTIVE'),
(8203, '0900008203', 'Khách hàng khác', 'ACTIVE');

INSERT INTO stores
(id, owner_user_id, name, address, city, business_license, status)
VALUES
(8201, 8201, 'RideHub Booking Test Approved', '122 Hoàng Quốc Việt', 'Hà Nội', 'GP-8201', 'APPROVED'),
(8202, 8201, 'RideHub Booking Test Pending', '1 Nguyễn Huệ', 'TP.HCM', 'GP-8202', 'PENDING'),
(8203, 8201, 'RideHub Booking Test Other', '1 Bạch Đằng', 'Đà Nẵng', 'GP-8203', 'APPROVED');

INSERT INTO vehicles
(id, store_id, vehicle_type, plate_number, brand, model, seats,
 transmission_type, fuel_type, price_per_day, price_per_hour,
 current_status, is_active)
VALUES
(8301, 8201, 'MOTORBIKE', 'TEST-8301', 'Honda', 'Vision', 2,
 'MANUAL', 'GASOLINE', 150000, 25000, 'MAINTENANCE', TRUE),
(8302, 8202, 'MOTORBIKE', 'TEST-8302', 'Honda', 'Wave', 2,
 'MANUAL', 'GASOLINE', 150000, 25000, 'MAINTENANCE', TRUE),
(8303, 8201, 'MOTORBIKE', 'TEST-8303', 'Honda', 'Future', 2,
 'MANUAL', 'GASOLINE', 100000, NULL, 'MAINTENANCE', FALSE),
(8304, 8203, 'MOTORBIKE', 'TEST-8304', 'Yamaha', 'Exciter', 2,
 'MANUAL', 'GASOLINE', 200000, 30000, 'MAINTENANCE', TRUE),
(8305, 8201, 'MOTORBIKE', 'TEST-8305', 'Honda', 'Air Blade', 2,
 'MANUAL', 'GASOLINE', 120000, 20000, 'MAINTENANCE', TRUE);

INSERT INTO delivery_points
(id, store_id, name, address, area, delivery_fee, is_active)
VALUES
(8401, 8201, 'Điểm giao hợp lệ', 'Bến xe Mỹ Đình', 'Quận Cầu Giấy', 50000, TRUE),
(8402, 8201, 'Điểm giao ẩn', 'Không dùng', 'Quận X', 30000, FALSE),
(8403, 8203, 'Điểm giao cửa hàng khác', 'Bạch Đằng', 'Quận Hải Châu', 40000, TRUE);

-- Booking CONFIRMED chặn khung now+1d..now+2d.
INSERT INTO bookings
(id, customer_id, vehicle_id, store_id, start_time, end_time, status,
 rental_amount, delivery_fee, deposit_amount, total_amount)
VALUES
(8501, 8203, 8301, 8201,
 DATE_ADD(NOW(), INTERVAL 1 DAY), DATE_ADD(NOW(), INTERVAL 2 DAY),
 'CONFIRMED', 300000, 0, 200000, 300000);

-- Booking CANCELLED không chặn khung now+11d..now+12d.
INSERT INTO bookings
(id, customer_id, vehicle_id, store_id, start_time, end_time, status,
 rental_amount, delivery_fee, deposit_amount, total_amount)
VALUES
(8502, 8203, 8301, 8201,
 DATE_ADD(NOW(), INTERVAL 11 DAY), DATE_ADD(NOW(), INTERVAL 12 DAY),
 'CANCELLED', 300000, 0, 200000, 300000);

-- Giữ chỗ ACTIVE còn hạn chặn now+3d..now+4d.
INSERT INTO vehicle_reservations
(id, vehicle_id, customer_id, start_time, end_time, expires_at, status)
VALUES
(8601, 8301, 8203,
 DATE_ADD(NOW(), INTERVAL 3 DAY), DATE_ADD(NOW(), INTERVAL 4 DAY),
 DATE_ADD(NOW(), INTERVAL 30 MINUTE), 'ACTIVE');

-- Giữ chỗ ACTIVE đã hết hạn không chặn now+5d..now+6d.
INSERT INTO vehicle_reservations
(id, vehicle_id, customer_id, start_time, end_time, expires_at, status)
VALUES
(8602, 8301, 8203,
 DATE_ADD(NOW(), INTERVAL 5 DAY), DATE_ADD(NOW(), INTERVAL 6 DAY),
 DATE_SUB(NOW(), INTERVAL 1 MINUTE), 'ACTIVE');

-- Lịch bảo dưỡng chặn xe 8305 trong now+7d..now+8d.
INSERT INTO vehicle_schedules
(id, vehicle_id, schedule_type, start_time, end_time, status, note)
VALUES
(8701, 8305, 'MAINTENANCE',
 DATE_ADD(NOW(), INTERVAL 7 DAY), DATE_ADD(NOW(), INTERVAL 8 DAY),
 'ACTIVE', 'Bảo dưỡng định kỳ');

-- Lịch RENTAL chặn xe 8301 trong now+9d..now+10d.
INSERT INTO vehicle_schedules
(id, vehicle_id, schedule_type, start_time, end_time, status, note)
VALUES
(8702, 8301, 'RENTAL',
 DATE_ADD(NOW(), INTERVAL 9 DAY), DATE_ADD(NOW(), INTERVAL 10 DAY),
 'ACTIVE', 'Lịch chặn');

COMMIT;
