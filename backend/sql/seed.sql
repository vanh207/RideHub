-- ==============================================================================
-- RIDEHUB — DỮ LIỆU MẪU MẶC ĐỊNH (SEED DATA)
-- Khởi tạo 3 tài khoản đại diện: Khách thuê, Chủ cửa hàng, Quản trị viên
-- ==============================================================================

-- 1. Khởi tạo danh mục Vai trò (Roles)
INSERT INTO roles (code, name, description) VALUES
('admin', 'Quản trị viên', 'Quản trị viên toàn quyền hệ thống'),
('store_owner', 'Chủ cửa hàng', 'Chủ sở hữu, quản lý cửa hàng cho thuê xe'),
('store_staff', 'Nhân viên cửa hàng', 'Nhân viên thực hiện giao nhận xe, kiểm tra tại cửa hàng'),
('customer', 'Khách thuê', 'Người dùng có nhu cầu thuê xe'),
('operator', 'Điều hành', 'Vận hành viên điều phối và chăm sóc khách hàng')
ON DUPLICATE KEY UPDATE name=VALUES(name);

-- 2. Khởi tạo 3 tài khoản mẫu (Mật khẩu mặc định: password123)
-- Hash bcrypt tương ứng của password123: $2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewfYp01U2McfM1O2
INSERT INTO users (id, firebase_uid, phone, email, full_name, hashed_password, status) VALUES
(1, 'seed_customer_uid_01', '0901234567', 'customer@ridehub.vn', 'Nguyễn Văn An (Khách thuê)', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewfYp01U2McfM1O2', 'active'),
(2, 'seed_store_owner_uid_02', '0902222222', 'owner@ridehub.vn', 'Lê Hoàng Nam (Chủ cửa hàng)', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewfYp01U2McfM1O2', 'active'),
(3, 'seed_admin_uid_03', '0909999999', 'admin@ridehub.vn', 'Quản Trị Viên Hệ Thống', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewfYp01U2McfM1O2', 'active')
ON DUPLICATE KEY UPDATE 
    hashed_password=VALUES(hashed_password),
    status=VALUES(status);

-- 3. Gán vai trò cho từng tài khoản
INSERT INTO user_roles (user_id, role_id)
SELECT 1, id FROM roles WHERE code = 'customer'
ON DUPLICATE KEY UPDATE role_id=VALUES(role_id);

INSERT INTO user_roles (user_id, role_id)
SELECT 2, id FROM roles WHERE code = 'store_owner'
ON DUPLICATE KEY UPDATE role_id=VALUES(role_id);

INSERT INTO user_roles (user_id, role_id)
SELECT 3, id FROM roles WHERE code = 'admin'
ON DUPLICATE KEY UPDATE role_id=VALUES(role_id);

-- 4. Khởi tạo Cửa hàng mẫu đã được duyệt cho Chủ cửa hàng (User ID: 2)
INSERT INTO stores (id, owner_user_id, name, description, phone, email, address, city, district, ward, status, approved_at) VALUES
(1, 2, 'GreenRide - Chi nhánh Quận 1', 'Cửa hàng cho thuê xe điện & xe máy uy tín tại trung tâm TP.HCM', '0902222222', 'greenride@ridehub.vn', '120 Lê Lợi, Phường Bến Thành', 'TP. Hồ Chí Minh', 'Quận 1', 'Phường Bến Thành', 'APPROVED', NOW())
ON DUPLICATE KEY UPDATE 
    name=VALUES(name),
    status=VALUES(status);

-- 5. Khởi tạo các điểm giao nhận thuộc cửa hàng
INSERT INTO delivery_points (store_id, name, address, area, delivery_fee, is_active) VALUES
(1, 'Điểm giao Quận 1', '120 Lê Lợi, Bến Thành', 'Quận 1', 0, true),
(1, 'Điểm giao Bến xe Miền Tây', '395 Kinh Dương Vương, An Lạc', 'Quận Bình Tân', 50000, true),
(1, 'Điểm giao Sân bay Tân Sơn Nhất', 'Cột số 5, Ga Quốc nội TSN', 'Quận Tân Bình', 80000, true)
ON DUPLICATE KEY UPDATE 
    delivery_fee=VALUES(delivery_fee),
    is_active=VALUES(is_active);
