-- Add one development vehicle for exercising the real booking/payment flow.
-- Safe to run repeatedly; does not delete or update existing business data.
-- Run only against a local/development database.
SET NAMES utf8mb4;
START TRANSACTION;

UPDATE users
SET date_of_birth = COALESCE(date_of_birth, '1990-01-01')
WHERE email = 'customer@ridehub.vn';

INSERT INTO driver_licenses (
    user_id,
    license_class,
    license_number,
    issued_date,
    expiry_date,
    status
)
SELECT
    user_row.id,
    'A1',
    'TF19FB0-TEST-A1',
    CURDATE(),
    DATE_ADD(CURDATE(), INTERVAL 3 YEAR),
    'approved'
FROM users AS user_row
WHERE user_row.email = 'customer@ridehub.vn'
  AND NOT EXISTS (
      SELECT 1
      FROM driver_licenses AS license_row
      WHERE license_row.user_id = user_row.id
        AND license_row.license_class = 'A1'
        AND license_row.status IN ('approved', 'verified', 'active')
        AND license_row.expiry_date >= CURDATE()
  );

SET @approved_store_id := (
    SELECT id
    FROM stores
    WHERE UPPER(status) = 'APPROVED'
    ORDER BY id
    LIMIT 1
);

INSERT INTO vehicles (
    store_id,
    vehicle_type,
    plate_number,
    brand,
    model,
    year_of_manufacture,
    engine_capacity,
    transmission_type,
    seats,
    body_type,
    fuel_type,
    price_per_day,
    price_per_hour,
    current_status,
    description,
    is_active
)
SELECT
    @approved_store_id,
    'MOTORBIKE',
    '59TF-19019',
    'Honda',
    'Vision TF19FB0 Demo',
    2024,
    110,
    'AUTOMATIC',
    2,
    'SCOOTER',
    'GASOLINE',
    150000,
    25000,
    'AVAILABLE',
    'Xe mẫu dành riêng cho kiểm thử luồng booking và thanh toán TF19FB0.',
    TRUE
FROM DUAL
WHERE @approved_store_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM vehicles WHERE plate_number = '59TF-19019'
  );

COMMIT;

SELECT id, brand, model, plate_number, current_status
FROM vehicles
WHERE plate_number = '59TF-19019';
