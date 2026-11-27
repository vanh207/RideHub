-- TASK_BONUS_FACECHECK: rollback các cột đồng ý/CCCD của phiên eKYC.
ALTER TABLE kyc_sessions
    DROP COLUMN address,
    DROP COLUMN gender,
    DROP COLUMN expiry_date,
    DROP COLUMN issued_date,
    DROP COLUMN date_of_birth,
    DROP COLUMN full_name,
    DROP COLUMN document_number;
