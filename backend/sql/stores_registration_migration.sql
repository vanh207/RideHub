-- Run once against the existing RideHub database before deploying store registration.
-- Resolve existing duplicate names/business_license/email values before creating the unique indexes.
ALTER TABLE stores
    ADD COLUMN description TEXT NULL,
    ADD COLUMN phone VARCHAR(20) NULL,
    ADD COLUMN email VARCHAR(255) NULL,
    ADD COLUMN district VARCHAR(100) NULL,
    ADD COLUMN ward VARCHAR(100) NULL,
    ADD COLUMN address_detail TEXT NULL,
    ADD COLUMN business_license_file VARCHAR(255) NULL,
    ADD COLUMN logo_file VARCHAR(255) NULL;

CREATE INDEX ix_stores_owner_id_status ON stores (owner_user_id, status);
CREATE INDEX ix_stores_status ON stores (status);
CREATE UNIQUE INDEX uq_stores_business_license_number ON stores (business_license);
CREATE UNIQUE INDEX uq_stores_email ON stores (email);
CREATE UNIQUE INDEX uq_stores_name ON stores (name);
