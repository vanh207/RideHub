-- ==============================================================================
-- DỮ LIỆU MẪU KIỂM THỬ TRUY VẤN DOANH THU (SEED REVENUE TEST DATA)
-- ==============================================================================
USE app_db;

-- 1. Thêm 2 cửa hàng kiểm thử (nếu chưa có)
INSERT INTO stores (id, owner_user_id, name, city, district, address, status)
VALUES 
  (1, 1, 'GreenRide - Trụ sở Quận 1', 'TP. Hồ Chí Minh', 'Quận 1', '45 Lê Duẩn', 'APPROVED'),
  (2, 1, 'FastRide - Chi nhánh Tân Bình', 'TP. Hồ Chí Minh', 'Quận Tân Bình', '120 Trường Sơn', 'APPROVED')
ON DUPLICATE KEY UPDATE name=VALUES(name);

-- 2. Thêm phương tiện mẫu
INSERT INTO vehicles (id, store_id, vehicle_type, plate_number, brand, model, price_per_day)
VALUES 
  (101, 1, 'MOTORBIKE', '59A-11111', 'Honda', 'Vision', 150000),
  (102, 1, 'CAR', '51G-22222', 'VinFast', 'VF 5 Plus', 600000),
  (103, 2, 'MOTORBIKE', '59B-33333', 'Yamaha', 'Grande', 180000)
ON DUPLICATE KEY UPDATE brand=VALUES(brand);

-- 3. Thêm các đơn hàng giả lập đa dạng ngày, tháng và trạng thái
INSERT INTO bookings (customer_id, vehicle_id, store_id, start_time, end_time, status, rental_amount, delivery_fee, deposit_amount, total_amount, created_at)
VALUES 
  -- Đơn 1: Cửa hàng 1, hoàn thành ngày 10/11/2026 (Doanh thu: 300k + 30k = 330k)
  (1, 101, 1, '2026-11-10 08:00:00', '2026-11-12 08:00:00', 'COMPLETED', 300000, 30000, 500000, 830000, '2026-11-10 07:30:00'),

  -- Đơn 2: Cửa hàng 1, hoàn thành ngày 10/11/2026 (Doanh thu: 1.200k + 0đ = 1.200k)
  (1, 102, 1, '2026-11-10 09:00:00', '2026-11-12 09:00:00', 'COMPLETED', 1200000, 0, 2000000, 3200000, '2026-11-10 08:15:00'),

  -- Đơn 3: Cửa hàng 1, đơn BỊ HỦY ngày 10/11/2026 (KHÔNG được tính vào doanh thu)
  (1, 101, 1, '2026-11-10 14:00:00', '2026-11-11 14:00:00', 'CANCELLED', 150000, 20000, 500000, 670000, '2026-11-10 10:00:00'),

  -- Đơn 4: Cửa hàng 1, hoàn thành ngày 14/11/2026 (Doanh thu: 600k + 35k = 635k)
  (1, 102, 1, '2026-11-14 08:00:00', '2026-11-15 08:00:00', 'COMPLETED', 600000, 35000, 2000000, 2635000, '2026-11-14 07:00:00'),

  -- Đơn 5: Cửa hàng 1, hoàn thành vào tháng 10/2026 (Doanh thu: 900k + 0đ = 900k)
  (1, 101, 1, '2026-10-20 08:00:00', '2026-10-23 08:00:00', 'COMPLETED', 900000, 0, 500000, 1400000, '2026-10-20 07:45:00'),

  -- Đơn 6: Cửa hàng 2, hoàn thành ngày 14/11/2026 (Doanh thu: 360k + 20k = 380k)
  (1, 103, 2, '2026-11-14 09:00:00', '2026-11-16 09:00:00', 'COMPLETED', 360000, 20000, 500000, 880000, '2026-11-14 08:30:00');