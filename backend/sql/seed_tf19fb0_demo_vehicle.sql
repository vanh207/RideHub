-- Local/development only. Run after the backend startup seed has created
-- customer@ridehub.vn and the sample GreenRide store.
-- Safe to rerun: only the TF19FB0 test vehicles and test driver's license
-- are inserted/updated, and existing bookings and schedules are never deleted.
SET NAMES utf8mb4;
START TRANSACTION;

UPDATE users
SET date_of_birth = COALESCE(date_of_birth, '1990-01-01'),
    status = 'active'
WHERE email = 'customer@ridehub.vn';

UPDATE stores AS sample_store
JOIN users AS sample_owner ON sample_owner.id = sample_store.owner_user_id
SET sample_store.status = 'APPROVED',
    sample_store.approved_at = COALESCE(
        sample_store.approved_at,
        CURRENT_TIMESTAMP
    )
WHERE sample_owner.email = 'owner@ridehub.vn'
  AND sample_store.name = 'GreenRide - Chi nhánh Quận 1';

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
    CONCAT('TF19FB0-TEST-A1-', user_row.id),
    CURDATE(),
    DATE_ADD(CURDATE(), INTERVAL 3 YEAR),
    'approved'
FROM users AS user_row
WHERE user_row.email = 'customer@ridehub.vn'
  AND NOT EXISTS (
      SELECT 1
      FROM driver_licenses AS license_row
      WHERE license_row.user_id = user_row.id
        AND UPPER(license_row.license_class) = 'A1'
        AND LOWER(license_row.status) IN ('approved', 'verified', 'active')
        AND license_row.expiry_date >= CURDATE()
  );

SET @approved_store_id := (
    SELECT store_row.id
    FROM stores AS store_row
    LEFT JOIN users AS sample_owner
        ON sample_owner.id = store_row.owner_user_id
    WHERE UPPER(TRIM(store_row.status)) = 'APPROVED'
    ORDER BY
        CASE
            WHEN sample_owner.email = 'owner@ridehub.vn'
             AND store_row.name = 'GreenRide - Chi nhánh Quận 1'
            THEN 0 ELSE 1
        END,
        store_row.id
    LIMIT 1
);

-- Avoid reusing IDs that an old booking, reservation, or schedule references.
SET @vehicle_id_floor := GREATEST(
    COALESCE((SELECT MAX(id) FROM vehicles), 0),
    COALESCE((SELECT MAX(vehicle_id) FROM bookings), 0),
    COALESCE((SELECT MAX(vehicle_id) FROM vehicle_reservations), 0),
    COALESCE((SELECT MAX(vehicle_id) FROM vehicle_schedules), 0)
);

SET @vehicle_id_1 := COALESCE(
    (SELECT id FROM vehicles
     WHERE store_id = @approved_store_id AND plate_number = '59TF-19019'),
    @vehicle_id_floor + 1
);
SET @vehicle_id_2 := COALESCE(
    (SELECT id FROM vehicles
     WHERE store_id = @approved_store_id AND plate_number = '59TF-19020'),
    @vehicle_id_floor + 2
);
SET @vehicle_id_3 := COALESCE(
    (SELECT id FROM vehicles
     WHERE store_id = @approved_store_id AND plate_number = '59TF-19021'),
    @vehicle_id_floor + 3
);

INSERT INTO vehicles (
    id,
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
VALUES
    (
        @vehicle_id_1,
        @approved_store_id,
        'MOTORBIKE',
        '59TF-19019',
        'Honda',
        'Vision TF19FB0 Demo 1',
        2024,
        110,
        'AUTOMATIC',
        2,
        'SCOOTER',
        'GASOLINE',
        150000,
        25000,
        'AVAILABLE',
        'TF19FB0 local test vehicle for booking and PayOS QR flow.',
        TRUE
    ),
    (
        @vehicle_id_2,
        @approved_store_id,
        'MOTORBIKE',
        '59TF-19020',
        'Yamaha',
        'Grande TF19FB0 Demo 2',
        2024,
        125,
        'AUTOMATIC',
        2,
        'SCOOTER',
        'GASOLINE',
        180000,
        30000,
        'AVAILABLE',
        'TF19FB0 local test vehicle for booking and PayOS QR flow.',
        TRUE
    ),
    (
        @vehicle_id_3,
        @approved_store_id,
        'MOTORBIKE',
        '59TF-19021',
        'Honda',
        'Air Blade TF19FB0 Demo 3',
        2024,
        160,
        'AUTOMATIC',
        2,
        'SCOOTER',
        'GASOLINE',
        220000,
        35000,
        'AVAILABLE',
        'TF19FB0 local test vehicle for booking and PayOS QR flow.',
        TRUE
    )
ON DUPLICATE KEY UPDATE
    store_id = VALUES(store_id),
    vehicle_type = VALUES(vehicle_type),
    brand = VALUES(brand),
    model = VALUES(model),
    year_of_manufacture = VALUES(year_of_manufacture),
    engine_capacity = VALUES(engine_capacity),
    transmission_type = VALUES(transmission_type),
    seats = VALUES(seats),
    body_type = VALUES(body_type),
    fuel_type = VALUES(fuel_type),
    price_per_day = VALUES(price_per_day),
    price_per_hour = VALUES(price_per_hour),
    current_status = VALUES(current_status),
    description = VALUES(description),
    is_active = VALUES(is_active);

COMMIT;

SELECT
    vehicle_row.id,
    vehicle_row.store_id,
    store_row.status AS store_status,
    vehicle_row.brand,
    vehicle_row.model,
    vehicle_row.plate_number,
    vehicle_row.price_per_day,
    vehicle_row.current_status,
    vehicle_row.is_active
FROM vehicles AS vehicle_row
JOIN stores AS store_row ON store_row.id = vehicle_row.store_id
WHERE vehicle_row.plate_number IN (
    '59TF-19019',
    '59TF-19020',
    '59TF-19021'
)
ORDER BY vehicle_row.plate_number;
