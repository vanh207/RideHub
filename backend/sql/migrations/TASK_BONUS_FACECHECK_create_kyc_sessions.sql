-- TASK_BONUS_FACECHECK: tạo bảng phiên eKYC.
-- Chỉ tạo bảng mới; KHÔNG sửa dữ liệu/ ràng buộc của identity_documents.
CREATE TABLE IF NOT EXISTS kyc_sessions (
    id INT NOT NULL AUTO_INCREMENT,
    user_id INT NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'CREATED',
    challenge VARCHAR(64) NULL,
    challenge_expires_at DATETIME NULL,
    attempt_count INT NOT NULL DEFAULT 0,
    consent_version VARCHAR(30) NULL,
    consented_at DATETIME NULL,
    consent_ip VARCHAR(45) NULL,
    front_path VARCHAR(500) NULL,
    back_path VARCHAR(500) NULL,
    selfie_path VARCHAR(500) NULL,
    qr_payload_hash VARCHAR(64) NULL,
    qr_consistent TINYINT(1) NULL,
    match_score FLOAT NULL,
    liveness_result VARCHAR(30) NULL,
    provider VARCHAR(30) NULL,
    flags JSON NULL,
    identity_document_id INT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    expires_at DATETIME NULL,
    PRIMARY KEY (id),
    INDEX idx_kyc_sessions_user_status (user_id, status),
    INDEX idx_kyc_sessions_expires_at (expires_at),
    CONSTRAINT fk_kyc_sessions_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_kyc_sessions_identity_document FOREIGN KEY (identity_document_id)
        REFERENCES identity_documents(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
