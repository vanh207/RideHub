-- TASK_BONUS_FACECHECK: thêm dữ liệu đồng ý và thông tin CCCD vào phiên eKYC.
-- Chỉ thêm cột nullable; không đổi dữ liệu của cột cũ.
ALTER TABLE kyc_sessions
    ADD COLUMN document_number VARCHAR(50) NULL AFTER consent_ip,
    ADD COLUMN full_name VARCHAR(150) NULL AFTER document_number,
    ADD COLUMN date_of_birth DATE NULL AFTER full_name,
    ADD COLUMN issued_date DATE NULL AFTER date_of_birth,
    ADD COLUMN expiry_date DATE NULL AFTER issued_date,
    ADD COLUMN gender VARCHAR(20) NULL AFTER expiry_date,
    ADD COLUMN address VARCHAR(300) NULL AFTER gender;
