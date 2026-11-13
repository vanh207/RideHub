CREATE DATABASE RideHub;

CREATE TABLE IF NOT EXISTS roles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(30) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    firebase_uid VARCHAR(128) UNIQUE,
    phone VARCHAR(15) UNIQUE NOT NULL,
    email VARCHAR(150) UNIQUE,
    full_name VARCHAR(150),
    date_of_birth DATE,
    address TEXT,
    avatar_url VARCHAR(500),
    status VARCHAR(30) DEFAULT 'ACTIVE',
    last_login_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_roles (
    user_id INT NOT NULL,
    role_id INT NOT NULL,
    PRIMARY KEY (user_id, role_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
);


-- ==========================================
-- 2. HỒ SƠ & QUY ĐỊNH (DOCUMENTS & RULES)
-- ==========================================
CREATE TABLE IF NOT EXISTS identity_documents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    document_type VARCHAR(30),
    document_number VARCHAR(50),
    front_image_url VARCHAR(500),
    back_image_url VARCHAR(500),
    issued_date DATE,
    expiry_date DATE,
    status VARCHAR(30) DEFAULT 'PENDING',
    reject_reason TEXT,
    verified_by INT,
    verified_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (verified_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS driver_licenses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    license_class VARCHAR(10),
    license_number VARCHAR(50),
    image_url VARCHAR(500),
    issued_date DATE,
    expiry_date DATE,
    status VARCHAR(30) DEFAULT 'PENDING',
    reject_reason TEXT,
    verified_by INT,
    verified_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (verified_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS license_rules (
    id INT AUTO_INCREMENT PRIMARY KEY,
    vehicle_group VARCHAR(50),
    required_license VARCHAR(10),
    min_age INT,
    is_active BOOLEAN DEFAULT TRUE,
    note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);


-- ==========================================
-- 3. CỬA HÀNG & PHƯƠNG TIỆN (STORES & VEHICLES)
-- ==========================================
CREATE TABLE IF NOT EXISTS stores (
    id INT AUTO_INCREMENT PRIMARY KEY,
    owner_user_id INT NOT NULL,
    name VARCHAR(200) NOT NULL,
    address TEXT,
    city VARCHAR(100),
    business_license VARCHAR(100),
    bank_account_info TEXT,
    status VARCHAR(30) DEFAULT 'PENDING',
    reject_reason TEXT,
    approved_by INT,
    approved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_user_id) REFERENCES users(id),
    FOREIGN KEY (approved_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS store_staff (
    id INT AUTO_INCREMENT PRIMARY KEY,
    store_id INT NOT NULL,
    user_id INT NOT NULL,
    staff_role VARCHAR(30),
    status VARCHAR(30) DEFAULT 'ACTIVE',
    created_by INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (store_id) REFERENCES stores(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (created_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS delivery_points (
    id INT AUTO_INCREMENT PRIMARY KEY,
    store_id INT NOT NULL,
    name VARCHAR(150),
    address TEXT,
    area VARCHAR(100),
    delivery_fee DECIMAL(12,2) DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (store_id) REFERENCES stores(id)
);

CREATE TABLE IF NOT EXISTS vehicles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    store_id INT NOT NULL,
    vehicle_type VARCHAR(30),
    plate_number VARCHAR(20) UNIQUE NOT NULL,
    brand VARCHAR(100),
    model VARCHAR(100),
    year_of_manufacture INT,
    engine_capacity INT,
    transmission_type VARCHAR(30),
    seats INT,
    body_type VARCHAR(50),
    fuel_type VARCHAR(30),
    price_per_day DECIMAL(12,2),
    price_per_hour DECIMAL(12,2),
    current_status VARCHAR(30) DEFAULT 'AVAILABLE',
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (store_id) REFERENCES stores(id)
);

CREATE TABLE IF NOT EXISTS vehicle_images (
    id INT AUTO_INCREMENT PRIMARY KEY,
    vehicle_id INT NOT NULL,
    image_url VARCHAR(500),
    is_primary BOOLEAN DEFAULT FALSE,
    sort_order INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
);

CREATE TABLE IF NOT EXISTS vehicle_status_histories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    vehicle_id INT NOT NULL,
    from_status VARCHAR(30),
    to_status VARCHAR(30) NOT NULL,
    changed_by INT,
    reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(id),
    FOREIGN KEY (changed_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS vehicle_favorites (
    user_id INT NOT NULL,
    vehicle_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, vehicle_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE
);


-- ==========================================
-- 4. ĐẶT XE & VẬN HÀNH (BOOKINGS & OPERATIONS)
-- ==========================================
CREATE TABLE IF NOT EXISTS bookings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    vehicle_id INT NOT NULL,
    store_id INT NOT NULL,
    delivery_point_id INT,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    hold_expires_at TIMESTAMP,
    status VARCHAR(40) DEFAULT 'PENDING',
    rental_amount DECIMAL(12,2) NOT NULL,
    delivery_fee DECIMAL(12,2) DEFAULT 0,
    deposit_amount DECIMAL(12,2) NOT NULL,
    total_amount DECIMAL(12,2) NOT NULL,
    customer_note TEXT,
    cancel_reason TEXT,
    cancelled_by INT,
    cancelled_at TIMESTAMP,
    store_confirmed_at TIMESTAMP,
    store_rejected_at TIMESTAMP,
    store_reject_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT ck_booking_time_range CHECK (start_time < end_time),
    CONSTRAINT ck_booking_rental_amount CHECK (rental_amount >= 0),
    CONSTRAINT ck_booking_delivery_fee CHECK (delivery_fee >= 0),
    CONSTRAINT ck_booking_deposit_amount CHECK (deposit_amount >= 0),
    CONSTRAINT ck_booking_total_amount CHECK (total_amount >= 0),
    FOREIGN KEY (customer_id) REFERENCES users(id),
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(id),
    FOREIGN KEY (store_id) REFERENCES stores(id),
    FOREIGN KEY (delivery_point_id) REFERENCES delivery_points(id),
    FOREIGN KEY (cancelled_by) REFERENCES users(id),
    INDEX ix_bookings_vehicle_time (vehicle_id, start_time, end_time),
    INDEX ix_bookings_vehicle_status_time (vehicle_id, status, start_time, end_time),
    INDEX ix_bookings_status_hold_expires (status, hold_expires_at)
);

-- Giữ chỗ tạm thời cho xe. Một giữ chỗ mới có hiệu lực tối đa 30 phút.
CREATE TABLE IF NOT EXISTS vehicle_reservations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    vehicle_id INT NOT NULL,
    customer_id INT NOT NULL,
    booking_id INT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    expires_at TIMESTAMP NOT NULL DEFAULT (CURRENT_TIMESTAMP + INTERVAL 30 MINUTE),
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT ck_reservation_time_range CHECK (start_time < end_time),
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE,
    FOREIGN KEY (customer_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE SET NULL,
    INDEX ix_reservations_vehicle_time (vehicle_id, start_time, end_time),
    INDEX ix_reservations_vehicle_status_expiry (vehicle_id, status, expires_at),
    INDEX ix_reservations_status_expiry (status, expires_at)
);

-- Lịch chiếm dụng xe: đơn thuê, giữ chỗ, bảo trì hoặc khóa xe.
CREATE TABLE IF NOT EXISTS vehicle_schedules (
    id INT AUTO_INCREMENT PRIMARY KEY,
    vehicle_id INT NOT NULL,
    booking_id INT NULL,
    reservation_id INT NULL,
    schedule_type VARCHAR(20) NOT NULL DEFAULT 'RENTAL',
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    note VARCHAR(500) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT ck_schedule_time_range CHECK (start_time < end_time),
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE,
    FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE SET NULL,
    FOREIGN KEY (reservation_id) REFERENCES vehicle_reservations(id) ON DELETE SET NULL,
    INDEX ix_schedules_vehicle_time (vehicle_id, start_time, end_time),
    INDEX ix_schedules_vehicle_status_time (vehicle_id, status, start_time, end_time)
);

CREATE TABLE IF NOT EXISTS booking_status_histories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    booking_id INT NOT NULL,
    from_status VARCHAR(40),
    to_status VARCHAR(40) NOT NULL,
    changed_by INT,
    reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (booking_id) REFERENCES bookings(id),
    FOREIGN KEY (changed_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS handover_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    booking_id INT NOT NULL,
    type VARCHAR(20) NOT NULL, -- GIAO / NHAN
    odometer INT,
    fuel_level VARCHAR(30),
    checklist JSON,
    notes TEXT,
    images JSON,
    customer_signature VARCHAR(500),
    staff_id INT,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (booking_id) REFERENCES bookings(id),
    FOREIGN KEY (staff_id) REFERENCES users(id)
);


-- ==========================================
-- 5. THANH TOÁN & ĐỐI SOÁT (PAYMENTS & FINANCE)
-- ==========================================
CREATE TABLE IF NOT EXISTS payment_transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    booking_id INT,
    transaction_code VARCHAR(100) UNIQUE NOT NULL,
    provider VARCHAR(50),
    provider_txn_id VARCHAR(150),
    amount DECIMAL(12,2) NOT NULL,
    status VARCHAR(30) DEFAULT 'PENDING',
    payment_method VARCHAR(50),
    qr_code_url VARCHAR(500),
    paid_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (booking_id) REFERENCES bookings(id)
);

CREATE TABLE IF NOT EXISTS payment_webhook_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    provider_txn_id VARCHAR(150),
    transaction_code VARCHAR(100),
    payload JSON,
    signature_valid BOOLEAN,
    process_result VARCHAR(50),
    queue_reason TEXT,
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS refunds (
    id INT AUTO_INCREMENT PRIMARY KEY,
    booking_id INT NOT NULL,
    payment_transaction_id INT,
    amount DECIMAL(12,2) NOT NULL,
    reason TEXT,
    status VARCHAR(30) DEFAULT 'PENDING',
    processed_by INT,
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (booking_id) REFERENCES bookings(id),
    FOREIGN KEY (payment_transaction_id) REFERENCES payment_transactions(id),
    FOREIGN KEY (processed_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS rental_settlements (
    id INT AUTO_INCREMENT PRIMARY KEY,
    booking_id INT UNIQUE NOT NULL,
    rental_amount DECIMAL(12,2),
    delivery_fee DECIMAL(12,2),
    deposit_deducted DECIMAL(12,2),
    extra_fees DECIMAL(12,2) DEFAULT 0,
    extra_fee_details JSON,
    amount_collected DECIMAL(12,2),
    payment_method VARCHAR(50),
    recorded_by INT,
    notes TEXT,
    status VARCHAR(30),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (booking_id) REFERENCES bookings(id),
    FOREIGN KEY (recorded_by) REFERENCES users(id)
);