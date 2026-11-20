-- ==============================================================================
-- RIDEHUB — AUDIT LOG TABLE MIGRATION
-- Thao tác: Duyệt hồ sơ, Đổi trạng thái (xe/đơn), Hoàn tiền
-- ==============================================================================

CREATE TABLE IF NOT EXISTS `audit_logs` (
  `id` INT NOT NULL AUTO_INCREMENT,
  
  -- 1. AI (WHO)
  `user_id` INT NULL COMMENT 'ID người thực hiện (khóa ngoại sang users.id, SET NULL khi user bị xóa)',
  `user_email` VARCHAR(150) NULL COMMENT 'Email người thực hiện tại thời điểm thao tác',
  `user_role` VARCHAR(50) NULL COMMENT 'Vai trò người thực hiện: admin, store_owner, store_staff, customer, anonymous',
  `ip_address` VARCHAR(45) NULL COMMENT 'Địa chỉ IP nguồn của client (IPv4/IPv6)',
  `user_agent` VARCHAR(500) NULL COMMENT 'Trình duyệt/thiết bị của client',

  -- 2. LÀM GÌ (WHAT)
  `action` VARCHAR(100) NOT NULL COMMENT 'Mã hành động: REVIEW_APPROVE, REVIEW_REJECT, VEHICLE_STATUS_CHANGE, PAYMENT_REFUND,...',
  `resource_type` VARCHAR(100) NOT NULL COMMENT 'Đối tượng bị tác động: store, identity_document, driver_license, vehicle, booking, payment',
  `resource_id` VARCHAR(100) NULL COMMENT 'Khóa chính / ID đối tượng bị tác động',
  `http_method` VARCHAR(10) NOT NULL COMMENT 'Phương thức HTTP: POST, PATCH, PUT, DELETE',
  `endpoint` VARCHAR(255) NOT NULL COMMENT 'Đường dẫn API được gọi',
  `description` TEXT NULL COMMENT 'Mô tả tóm tắt hành động bằng ngôn ngữ tự nhiên',
  `request_payload` JSON NULL COMMENT 'Dữ liệu request gửi lên (đã che các trường nhạy cảm)',
  `response_summary` TEXT NULL COMMENT 'Tóm tắt dữ liệu phản hồi',

  -- 3. KẾT QUẢ & HIỆU NĂNG
  `status_code` INT NOT NULL COMMENT 'Mã trạng thái phản hồi HTTP (200, 400, 404, 500,...)',
  `status` VARCHAR(20) NOT NULL DEFAULT 'SUCCESS' COMMENT 'Kết quả: SUCCESS hoặc FAILED',
  `error_message` TEXT NULL COMMENT 'Thông báo lỗi chi tiết nếu thất bại',
  `execution_time_ms` FLOAT NULL COMMENT 'Thời gian thực thi của thao tác (mili-giây)',

  -- 4. LÚC NÀO (WHEN)
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Thời điểm ghi nhận thao tác',

  PRIMARY KEY (`id`),
  INDEX `idx_audit_logs_user_id` (`user_id`),
  INDEX `idx_audit_logs_user_email` (`user_email`),
  INDEX `idx_audit_logs_action` (`action`),
  INDEX `idx_audit_logs_resource` (`resource_type`, `resource_id`),
  INDEX `idx_audit_logs_created_at` (`created_at`),
  CONSTRAINT `fk_audit_logs_user_id`
    FOREIGN KEY (`user_id`)
    REFERENCES `users` (`id`)
    ON DELETE SET NULL
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Nhật ký kiểm toán hệ thống RideHub';
