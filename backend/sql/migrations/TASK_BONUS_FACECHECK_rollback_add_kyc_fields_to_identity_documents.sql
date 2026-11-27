-- TASK_BONUS_FACECHECK: rollback kết quả máy trên identity_documents.
ALTER TABLE identity_documents
    DROP COLUMN kyc_provider,
    DROP COLUMN kyc_flags,
    DROP COLUMN liveness_result,
    DROP COLUMN match_score,
    DROP COLUMN selfie_path;
