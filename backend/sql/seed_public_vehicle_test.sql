-- Dữ liệu mẫu để test API công khai xem chi tiết phương tiện.
-- Chạy bằng MySQL Workbench sau khi đã chạy sql/erd_migration.sql.
-- Script dùng ID 9001+ để không ảnh hưởng dữ liệu hiện có và có thể chạy lại.

SET FOREIGN_KEY_CHECKS = 0;

DELETE FROM vehicle_schedules
WHERE id = 9001 OR vehicle_id BETWEEN 9001 AND 9007;
DELETE FROM vehicle_reservations
WHERE id IN (9001, 9002) OR vehicle_id BETWEEN 9001 AND 9007;
DELETE FROM bookings
WHERE id = 9001 OR vehicle_id BETWEEN 9001 AND 9007;
DELETE FROM vehicle_images
WHERE id BETWEEN 9101 AND 9103 OR vehicle_id BETWEEN 9001 AND 9007;
DELETE FROM delivery_points
WHERE id BETWEEN 9101 AND 9104 OR store_id IN (9001, 9002);
DELETE FROM vehicles WHERE id BETWEEN 9001 AND 9007;
DELETE FROM stores WHERE id IN (9001, 9002);
DELETE FROM users WHERE id IN (9001, 9002);

SET FOREIGN_KEY_CHECKS = 1;

-- 1 chủ cửa hàng và 1 khách hàng.
INSERT INTO users (id, firebase_uid, phone, email, full_name, status) VALUES
(9001, 'test_owner_9001', '0900000901', 'owner9001@example.com', 'Chủ cửa hàng test', 'ACTIVE'),
(9002, 'test_customer_9002', '0900000902', 'customer9002@example.com', 'Khách hàng test', 'ACTIVE');

-- 1 cửa hàng APPROVED và 1 cửa hàng PENDING.
INSERT INTO stores (
    id, owner_user_id, name, address, city,
    business_license, bank_account_info, status
) VALUES
(9001, 9001, 'RideHub Test APPROVED', '122 Hoàng Quốc Việt', 'Hà Nội',
 'GP-TEST-9001', 'BANK-SECRET-9001', 'APPROVED'),
(9002, 9001, 'RideHub Test PENDING', '1 Đại Cồ Việt', 'Hà Nội',
 'GP-TEST-9002', 'BANK-SECRET-9002', 'PENDING');

-- Xe 9001: có ảnh, không vướng lịch.
-- Xe 9002: không có ảnh, có booking CONFIRMED.
-- Xe 9003: có reservation ACTIVE còn hạn.
-- Xe 9004: có reservation ACTIVE đã hết hạn.
-- Xe 9005: có lịch bảo dưỡng.
-- Xe 9006: is_active = 0.
-- Xe 9007: thuộc cửa hàng PENDING.
INSERT INTO vehicles (
    id, store_id, vehicle_type, plate_number, brand, model,
    year_of_manufacture, engine_capacity, transmission_type, seats,
    body_type, fuel_type, price_per_day, price_per_hour,
    current_status, description, is_active
) VALUES
(9001, 9001, 'MOTORBIKE', '29A-9001', 'Honda', 'Vision',
 2023, 110, 'AUTOMATIC', 2, NULL, 'GASOLINE', 150000, 25000,
 'AVAILABLE', 'Xe mới, bảo dưỡng định kỳ', TRUE),
(9002, 9001, 'MOTORBIKE', '29A-9002', 'Honda', 'Wave',
 2022, 110, 'MANUAL', 2, NULL, 'GASOLINE', 120000, 20000,
 'AVAILABLE', 'Xe không có ảnh', TRUE),
(9003, 9001, 'MOTORBIKE', '29A-9003', 'Yamaha', 'Exciter',
 2023, 150, 'MANUAL', 2, NULL, 'GASOLINE', 180000, 30000,
 'AVAILABLE', 'Xe có giữ chỗ còn hiệu lực', TRUE),
(9004, 9001, 'MOTORBIKE', '29A-9004', 'Yamaha', 'Janus',
 2023, 125, 'AUTOMATIC', 2, NULL, 'GASOLINE', 140000, 22000,
 'AVAILABLE', 'Xe có giữ chỗ đã hết hạn', TRUE),
(9005, 9001, 'CAR', '30A-9005', 'Toyota', 'Vios',
 2022, 1500, 'AUTOMATIC', 5, 'SEDAN', 'GASOLINE', 800000, 120000,
 'MAINTENANCE', 'Xe đang bảo dưỡng', TRUE),
(9006, 9001, 'MOTORBIKE', '29A-9006', 'Honda', 'Future',
 2021, 125, 'MANUAL', 2, NULL, 'GASOLINE', 110000, 18000,
 'AVAILABLE', 'Xe đã tắt hoạt động', FALSE),
(9007, 9002, 'MOTORBIKE', '29A-9007', 'Honda', 'Air Blade',
 2023, 125, 'AUTOMATIC', 2, NULL, 'GASOLINE', 160000, 26000,
 'AVAILABLE', 'Xe thuộc cửa hàng chưa duyệt', TRUE);

-- Ảnh của xe 9001: ảnh chính trước, sort_order NULL xuống cuối.
INSERT INTO vehicle_images (id, vehicle_id, image_url, is_primary, sort_order) VALUES
(9101, 9001, 'https://example.com/vision-2.jpg', FALSE, 2),
(9102, 9001, 'https://example.com/vision-1.jpg', TRUE, 1),
(9103, 9001, 'https://example.com/vision-null.jpg', FALSE, NULL);

-- Điểm giao nhận: 9103 không hoạt động nên không được trả ra.
INSERT INTO delivery_points (id, store_id, name, address, area, delivery_fee, is_active) VALUES
(9101, 9001, 'Điểm giao Cầu Giấy', 'Bến xe Mỹ Đình', 'Quận Cầu Giấy', 50000, TRUE),
(9102, 9001, 'Điểm giao Đống Đa', 'Ga Hà Nội', 'Quận Đống Đa', 40000, TRUE),
(9103, 9001, 'Điểm giao ẩn', 'Không dùng', 'Quận X', 0, FALSE),
(9104, 9002, 'Điểm giao PENDING', 'Không trả', 'Quận Y', 0, TRUE);

-- Booking CONFIRMED của xe 9002: 2026-12-01 09:00 -> 2026-12-03 09:00.
INSERT INTO bookings (
    id, customer_id, vehicle_id, store_id, delivery_point_id,
    start_time, end_time, status,
    rental_amount, delivery_fee, deposit_amount, total_amount
) VALUES (
    9001, 9002, 9002, 9001, NULL,
    '2026-12-01 09:00:00', '2026-12-03 09:00:00', 'CONFIRMED',
    300000, 0, 100000, 400000
);

-- Giữ chỗ còn hiệu lực của xe 9003.
INSERT INTO vehicle_reservations (
    id, vehicle_id, customer_id, booking_id,
    start_time, end_time, expires_at, status
) VALUES (
    9001, 9003, 9002, NULL,
    '2026-12-05 09:00:00', '2026-12-06 09:00:00',
    '2030-01-01 00:00:00', 'ACTIVE'
);

-- Giữ chỗ đã hết hạn của xe 9004.
INSERT INTO vehicle_reservations (
    id, vehicle_id, customer_id, booking_id,
    start_time, end_time, expires_at, status
) VALUES (
    9002, 9004, 9002, NULL,
    '2026-12-07 09:00:00', '2026-12-08 09:00:00',
    '2020-01-01 00:00:00', 'ACTIVE'
);

-- Lịch bảo dưỡng của xe 9005.
INSERT INTO vehicle_schedules (
    id, vehicle_id, booking_id, reservation_id,
    schedule_type, start_time, end_time, status, note
) VALUES (
    9001, 9005, NULL, NULL,
    'MAINTENANCE', '2026-12-10 09:00:00', '2026-12-11 09:00:00',
    'ACTIVE', 'Bảo dưỡng định kỳ'
);
