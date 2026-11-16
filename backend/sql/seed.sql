INSERT INTO roles (code, name, description) VALUES
('ADMIN', 'Quản trị viên', 'Quản trị viên toàn quyền hệ thống'),
('STORE_OWNER', 'Chủ cửa hàng', 'Chủ sở hữu, quản lý cửa hàng cho thuê xe'),
('STORE_STAFF', 'Nhân viên cửa hàng', 'Nhân viên thực hiện giao nhận xe, kiểm tra tại cửa hàng'),
('CUSTOMER', 'Khách hàng', 'Người dùng có nhu cầu thuê xe'),
('SUPPORT', 'Nhân viên CSKH', 'Chăm sóc khách hàng và kiểm duyệt hồ sơ')
ON CONFLICT (code) DO NOTHING;

INSERT INTO users (id, firebase_uid, phone, email, full_name, status) 
VALUES (1, 'demo_firebase_uid_1', '0901234567', 'owner@ridehub.vn', 'Đỗ Việt Anh', 'ACTIVE')
ON CONFLICT DO NOTHING;

INSERT INTO user_roles (user_id, role_id) 
SELECT 1, id FROM roles WHERE code = 'STORE_OWNER'
ON CONFLICT DO NOTHING;

INSERT INTO stores (id, owner_user_id, name, address, city, status) 
VALUES (1, 1, 'RideHub Premium Store HN', '122 Hoàng Quốc Việt, Cầu Giấy', 'Hà Nội', 'APPROVED')
ON CONFLICT DO NOTHING;

-- Insert dữ liệu khu vực (delivery_points) thuộc cửa hàng trên
INSERT INTO delivery_points (store_id, name, address, area, delivery_fee, is_active) VALUES
(1, 'Điểm giao Cầu Giấy', 'Bến xe Mỹ Đình', 'Quận Cầu Giấy', 50000, true),
(1, 'Điểm giao Đống Đa', 'Ga Hà Nội', 'Quận Đống Đa', 40000, true),
(1, 'Điểm giao Hoàn Kiếm', 'Nhà Hát Lớn', 'Quận Hoàn Kiếm', 60000, true),
(1, 'Điểm giao Sân bay', 'Sân bay Nội Bài', 'Huyện Sóc Sơn', 150000, true)
ON CONFLICT DO NOTHING;