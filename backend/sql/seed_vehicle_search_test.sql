-- Dữ liệu mẫu cho API GET /api/vehicles/search.
-- Chạy trên MySQL 8 sau khi đã chạy sql/init.sql hoặc sql/erd_migration.sql.
-- Dùng bộ ID 92xx/93xx/94xx/95xx/96xx/97xx để không đụng dữ liệu thật.

SET NAMES utf8mb4;
START TRANSACTION;

DELETE FROM vehicle_schedules WHERE id IN (9701);
DELETE FROM vehicle_reservations WHERE id IN (9601, 9602);
DELETE FROM bookings WHERE id IN (9501);
DELETE FROM vehicle_images WHERE id IN (9401, 9402, 9403);
DELETE FROM delivery_points WHERE id IN (9301, 9302, 9303, 9304, 9305);
DELETE FROM vehicles WHERE id IN (9201, 9202, 9203, 9204, 9205, 9206, 9207, 9208, 9209);
DELETE FROM stores WHERE id IN (9201, 9202, 9203);
DELETE FROM users WHERE id IN (9201, 9202);

INSERT INTO users (id, phone, full_name, status) VALUES
(9201, '0900009201', 'Chủ cửa hàng test', 'ACTIVE'),
(9202, '0900009202', 'Khách hàng test', 'ACTIVE');

INSERT INTO stores
(id, owner_user_id, name, address, city, business_license, bank_account_info, status)
VALUES
(9201, 9201, 'RideHub Hà Nội', '122 Hoàng Quốc Việt', 'Hà Nội', 'GP-9201', 'BANK-SECRET-9201', 'APPROVED'),
(9202, 9201, 'RideHub Đà Nẵng', '1 Bạch Đằng', 'Đà Nẵng', 'GP-9202', 'BANK-SECRET-9202', 'APPROVED'),
(9203, 9201, 'RideHub PENDING', '1 Nguyễn Huệ', 'TP.HCM', 'GP-9203', 'BANK-SECRET-9203', 'PENDING');

INSERT INTO vehicles
(id, store_id, vehicle_type, plate_number, brand, model, seats,
 transmission_type, fuel_type, price_per_day, price_per_hour,
 current_status, is_active, created_at)
VALUES
(9201, 9201, 'MOTORBIKE', 'TEST-9201', 'Honda', 'Vision', 2,
 'MANUAL', 'GASOLINE', 150000, 25000, 'MAINTENANCE', TRUE, '2026-11-01 10:00:00'),
(9202, 9201, 'MOTORBIKE', 'TEST-9202', 'Honda', 'Wave', 2,
 'MANUAL', 'GASOLINE', 120000, 20000, 'MAINTENANCE', TRUE, '2026-11-02 10:00:00'),
(9203, 9202, 'CAR', 'TEST-9203', 'Toyota', 'Vios', 5,
 'AUTOMATIC', 'GASOLINE', 800000, 120000, 'MAINTENANCE', TRUE, '2026-11-03 10:00:00'),
(9204, 9202, 'MOTORBIKE', 'TEST-9204', 'Yamaha', 'Exciter', 2,
 'MANUAL', 'GASOLINE', 180000, 30000, 'MAINTENANCE', TRUE, '2026-11-04 10:00:00'),
(9205, 9201, 'CAR', 'TEST-9205', 'Honda', 'City', 5,
 'AUTOMATIC', 'GASOLINE', 900000, 140000, 'MAINTENANCE', TRUE, '2026-11-05 10:00:00'),
(9206, 9201, 'MOTORBIKE', 'TEST-9206', 'Honda', 'Future', 2,
 'MANUAL', 'GASOLINE', 110000, NULL, 'MAINTENANCE', FALSE, '2026-11-06 10:00:00'),
(9207, 9203, 'MOTORBIKE', 'TEST-9207', 'Honda', 'Air Blade', 2,
 'MANUAL', 'GASOLINE', 160000, NULL, 'MAINTENANCE', TRUE, '2026-11-07 10:00:00'),
(9208, 9201, 'CAR', 'TEST-9208', 'Mazda', 'CX-5', 5,
 'AUTOMATIC', 'GASOLINE', 850000, 130000, 'MAINTENANCE', TRUE, '2026-11-08 10:00:00'),
(9209, 9201, 'MOTORBIKE', 'TEST-9209', 'Honda', 'Dream', 2,
 'MANUAL', 'GASOLINE', 100000, NULL, 'MAINTENANCE', TRUE, '2026-11-09 10:00:00');

INSERT INTO vehicle_images (id, vehicle_id, image_url, is_primary, sort_order) VALUES
(9401, 9201, 'https://example.com/9201-primary.jpg', TRUE, 1),
(9402, 9201, 'https://example.com/9201-secondary.jpg', FALSE, 2),
(9403, 9209, 'https://example.com/9209-first.jpg', FALSE, NULL);

INSERT INTO delivery_points (id, store_id, name, address, area, delivery_fee, is_active) VALUES
(9301, 9201, 'Điểm giao Cầu Giấy', 'Bến xe Mỹ Đình', 'Quận Cầu Giấy', 50000, TRUE),
(9302, 9201, 'Điểm giao Đống Đa', 'Ga Hà Nội', 'Quận Đống Đa', 40000, TRUE),
(9303, 9202, 'Điểm giao Hải Châu', 'Bạch Đằng', 'Quận Hải Châu', 30000, TRUE),
(9304, 9201, 'Điểm giao ẩn', 'Không dùng', 'Quận X', 0, FALSE),
(9305, 9203, 'Điểm giao PENDING', 'Không trả', 'Quận 1', 0, TRUE);

INSERT INTO bookings
(id, customer_id, vehicle_id, store_id, start_time, end_time, status,
 rental_amount, delivery_fee, deposit_amount, total_amount)
VALUES
(9501, 9202, 9202, 9201, '2026-12-01 09:00:00', '2026-12-03 09:00:00',
 'CONFIRMED', 300000, 0, 100000, 400000);

INSERT INTO vehicle_reservations
(id, vehicle_id, customer_id, start_time, end_time, expires_at, status)
VALUES
(9601, 9204, 9202, '2026-12-05 09:00:00', '2026-12-06 09:00:00',
 '2030-01-01 00:00:00', 'ACTIVE'),
(9602, 9205, 9202, '2026-12-07 09:00:00', '2026-12-08 09:00:00',
 '2020-01-01 00:00:00', 'ACTIVE');

INSERT INTO vehicle_schedules
(id, vehicle_id, schedule_type, start_time, end_time, status, note)
VALUES
(9701, 9208, 'MAINTENANCE', '2026-12-10 09:00:00', '2026-12-11 09:00:00',
 'ACTIVE', 'Bảo dưỡng định kỳ');

COMMIT;
