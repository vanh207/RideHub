-- TASK_BONUS_FACECHECK: thêm kết quả máy vào hồ sơ định danh hiện có.
-- Chỉ thêm cột nullable; không sửa cột/dữ liệu cũ (kể cả front_image_url và status).
-- Cần đối chiếu số lượng bản ghi identity_documents trước khi chạy trên production.
ALTER TABLE identity_documents
    ADD COLUMN selfie_path VARCHAR(500) NULL AFTER back_image_url,
    ADD COLUMN match_score FLOAT NULL AFTER selfie_path,
    ADD COLUMN liveness_result VARCHAR(30) NULL AFTER match_score,
    ADD COLUMN kyc_flags JSON NULL AFTER liveness_result,
    ADD COLUMN kyc_provider VARCHAR(30) NULL AFTER kyc_flags;
