-- Du lieu demo cho man hinh kiem duyet ho so.
-- Chay file nay tren database da co schema trong erd_migration.sql
-- va stores_registration_migration.sql.
-- Cac email, so dien thoai va ma giay phep deu la du lieu gia.

SET NAMES utf8mb4;

INSERT IGNORE INTO roles (code, name, description) VALUES
    ('CUSTOMER', 'Khách hàng', 'Người dùng có nhu cầu thuê xe'),
    ('STORE_OWNER', 'Chủ cửa hàng', 'Chủ sở hữu cửa hàng cho thuê xe');

INSERT INTO users (firebase_uid, phone, email, full_name, date_of_birth, address, status)
SELECT 'demo_review_customer_pending', '0909000101', 'demo.customer.pending@ridehub.example',
       'Khách Demo Chờ duyệt', '1995-04-12', 'Quận Cầu Giấy, Hà Nội', 'ACTIVE'
FROM DUAL
WHERE NOT EXISTS (
    SELECT 1 FROM users WHERE email = 'demo.customer.pending@ridehub.example'
);

INSERT INTO users (firebase_uid, phone, email, full_name, date_of_birth, address, status)
SELECT 'demo_review_customer_approved', '0909000102', 'demo.customer.approved@ridehub.example',
       'Khách Demo Đã duyệt', '1992-08-20', 'Quận Ba Đình, Hà Nội', 'ACTIVE'
FROM DUAL
WHERE NOT EXISTS (
    SELECT 1 FROM users WHERE email = 'demo.customer.approved@ridehub.example'
);

INSERT INTO users (firebase_uid, phone, email, full_name, date_of_birth, address, status)
SELECT 'demo_review_customer_rejected', '0909000103', 'demo.customer.rejected@ridehub.example',
       'Khách Demo Bị từ chối', '1998-01-05', 'Quận Đống Đa, Hà Nội', 'ACTIVE'
FROM DUAL
WHERE NOT EXISTS (
    SELECT 1 FROM users WHERE email = 'demo.customer.rejected@ridehub.example'
);

INSERT INTO users (firebase_uid, phone, email, full_name, date_of_birth, address, status)
SELECT 'demo_review_store_pending', '0909000201', 'demo.store.pending@ridehub.example',
       'Chủ cửa hàng Demo Chờ duyệt', '1988-03-15', 'Quận Cầu Giấy, Hà Nội', 'ACTIVE'
FROM DUAL
WHERE NOT EXISTS (
    SELECT 1 FROM users WHERE email = 'demo.store.pending@ridehub.example'
);

INSERT INTO users (firebase_uid, phone, email, full_name, date_of_birth, address, status)
SELECT 'demo_review_store_approved', '0909000202', 'demo.store.approved@ridehub.example',
       'Chủ cửa hàng Demo Đã duyệt', '1985-11-02', 'Quận Hai Bà Trưng, Hà Nội', 'ACTIVE'
FROM DUAL
WHERE NOT EXISTS (
    SELECT 1 FROM users WHERE email = 'demo.store.approved@ridehub.example'
);

INSERT INTO users (firebase_uid, phone, email, full_name, date_of_birth, address, status)
SELECT 'demo_review_store_rejected', '0909000203', 'demo.store.rejected@ridehub.example',
       'Chủ cửa hàng Demo Bị từ chối', '1990-06-27', 'Quận Thanh Xuân, Hà Nội', 'ACTIVE'
FROM DUAL
WHERE NOT EXISTS (
    SELECT 1 FROM users WHERE email = 'demo.store.rejected@ridehub.example'
);

INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id
FROM users u
JOIN roles r ON r.code = 'CUSTOMER'
WHERE u.email IN (
    'demo.customer.pending@ridehub.example',
    'demo.customer.approved@ridehub.example',
    'demo.customer.rejected@ridehub.example'
)
AND NOT EXISTS (
    SELECT 1 FROM user_roles ur WHERE ur.user_id = u.id AND ur.role_id = r.id
);

INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id
FROM users u
JOIN roles r ON r.code = 'STORE_OWNER'
WHERE u.email IN (
    'demo.store.pending@ridehub.example',
    'demo.store.approved@ridehub.example',
    'demo.store.rejected@ridehub.example'
)
AND NOT EXISTS (
    SELECT 1 FROM user_roles ur WHERE ur.user_id = u.id AND ur.role_id = r.id
);

INSERT INTO identity_documents (
    user_id, document_type, document_number, issued_date, expiry_date,
    status, reject_reason, verified_at
)
SELECT u.id, 'CCCD', 'DEMO-CCCD-0001', '2020-04-12', '2035-04-12',
       'pending', NULL, NULL
FROM users u
WHERE u.email = 'demo.customer.pending@ridehub.example'
  AND NOT EXISTS (SELECT 1 FROM identity_documents WHERE document_number = 'DEMO-CCCD-0001');

INSERT INTO identity_documents (
    user_id, document_type, document_number, issued_date, expiry_date,
    status, reject_reason, verified_at
)
SELECT u.id, 'CCCD', 'DEMO-CCCD-0002', '2020-08-20', '2035-08-20',
       'approved', NULL, NOW()
FROM users u
WHERE u.email = 'demo.customer.approved@ridehub.example'
  AND NOT EXISTS (SELECT 1 FROM identity_documents WHERE document_number = 'DEMO-CCCD-0002');

INSERT INTO identity_documents (
    user_id, document_type, document_number, issued_date, expiry_date,
    status, reject_reason, verified_at
)
SELECT u.id, 'CCCD', 'DEMO-CCCD-0003', '2020-01-05', '2035-01-05',
       'rejected', 'Ảnh CCCD bị mờ, vui lòng tải lại ảnh rõ nét.', NOW()
FROM users u
WHERE u.email = 'demo.customer.rejected@ridehub.example'
  AND NOT EXISTS (SELECT 1 FROM identity_documents WHERE document_number = 'DEMO-CCCD-0003');

INSERT INTO driver_licenses (
    user_id, license_class, license_number, issued_date, expiry_date,
    status, reject_reason, verified_at
)
SELECT u.id, 'A1', 'DEMO-GPLX-0001', '2021-04-12', '2031-04-12',
       'pending', NULL, NULL
FROM users u
WHERE u.email = 'demo.customer.pending@ridehub.example'
  AND NOT EXISTS (SELECT 1 FROM driver_licenses WHERE license_number = 'DEMO-GPLX-0001');

INSERT INTO driver_licenses (
    user_id, license_class, license_number, issued_date, expiry_date,
    status, reject_reason, verified_at
)
SELECT u.id, 'A1', 'DEMO-GPLX-0002', '2021-08-20', '2031-08-20',
       'approved', NULL, NOW()
FROM users u
WHERE u.email = 'demo.customer.approved@ridehub.example'
  AND NOT EXISTS (SELECT 1 FROM driver_licenses WHERE license_number = 'DEMO-GPLX-0002');

INSERT INTO driver_licenses (
    user_id, license_class, license_number, issued_date, expiry_date,
    status, reject_reason, verified_at
)
SELECT u.id, 'A1', 'DEMO-GPLX-0003', '2021-01-05', '2031-01-05',
       'rejected', 'Ảnh giấy phép lái xe không đọc được số giấy phép.', NOW()
FROM users u
WHERE u.email = 'demo.customer.rejected@ridehub.example'
  AND NOT EXISTS (SELECT 1 FROM driver_licenses WHERE license_number = 'DEMO-GPLX-0003');

INSERT INTO stores (
    owner_user_id, name, description, phone, email, address, city, district,
    business_license, status, reject_reason, approved_at
)
SELECT u.id, 'Cửa hàng Demo Chờ duyệt', 'Cửa hàng mẫu đang chờ kiểm duyệt.',
       '0909000201', 'demo.store.pending@ridehub.example',
       '123 Xuân Thủy', 'Hà Nội', 'Cầu Giấy', 'DEMO-GPKD-0001',
       'PENDING', NULL, NULL
FROM users u
WHERE u.email = 'demo.store.pending@ridehub.example'
  AND NOT EXISTS (
      SELECT 1 FROM stores
      WHERE name = 'Cửa hàng Demo Chờ duyệt'
         OR email = 'demo.store.pending@ridehub.example'
         OR business_license = 'DEMO-GPKD-0001'
  );

INSERT INTO stores (
    owner_user_id, name, description, phone, email, address, city, district,
    business_license, status, reject_reason, approved_at
)
SELECT u.id, 'Cửa hàng Demo Đã duyệt', 'Cửa hàng mẫu đã được kiểm duyệt.',
       '0909000202', 'demo.store.approved@ridehub.example',
       '45 Bạch Mai', 'Hà Nội', 'Hai Bà Trưng', 'DEMO-GPKD-0002',
       'APPROVED', NULL, NOW()
FROM users u
WHERE u.email = 'demo.store.approved@ridehub.example'
  AND NOT EXISTS (
      SELECT 1 FROM stores
      WHERE name = 'Cửa hàng Demo Đã duyệt'
         OR email = 'demo.store.approved@ridehub.example'
         OR business_license = 'DEMO-GPKD-0002'
  );

INSERT INTO stores (
    owner_user_id, name, description, phone, email, address, city, district,
    business_license, status, reject_reason, approved_at
)
SELECT u.id, 'Cửa hàng Demo Bị từ chối', 'Cửa hàng mẫu bị từ chối để demo.',
       '0909000203', 'demo.store.rejected@ridehub.example',
       '78 Nguyễn Trãi', 'Hà Nội', 'Thanh Xuân', 'DEMO-GPKD-0003',
       'REJECTED', 'Thông tin giấy phép kinh doanh chưa hợp lệ.', NULL
FROM users u
WHERE u.email = 'demo.store.rejected@ridehub.example'
  AND NOT EXISTS (
      SELECT 1 FROM stores
      WHERE name = 'Cửa hàng Demo Bị từ chối'
         OR email = 'demo.store.rejected@ridehub.example'
         OR business_license = 'DEMO-GPKD-0003'
  );
