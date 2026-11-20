-- Local/development only. Run after seed_tf19fb0_demo_vehicle.sql.
-- Creates one refundable late-payment anomaly for testing the operations UI.
-- Each execution creates a new booking, transaction, refund, and webhook log.
SET NAMES utf8mb4;
START TRANSACTION;

SET @customer_id := (
    SELECT id FROM users WHERE email = 'customer@ridehub.vn' LIMIT 1
);
SET @vehicle_id := (
    SELECT id
    FROM vehicles
    WHERE plate_number = '59TF-19019'
    ORDER BY id
    LIMIT 1
);
SET @store_id := (
    SELECT store_id FROM vehicles WHERE id = @vehicle_id LIMIT 1
);

INSERT INTO bookings (
    customer_id,
    vehicle_id,
    store_id,
    start_time,
    end_time,
    status,
    rental_amount,
    delivery_fee,
    deposit_amount,
    total_amount,
    cancelled_at,
    cancelled_by,
    cancel_reason
)
VALUES (
    @customer_id,
    @vehicle_id,
    @store_id,
    DATE_ADD(NOW(), INTERVAL 1 DAY),
    DATE_ADD(NOW(), INTERVAL 2 DAY),
    'CANCELLED',
    300000,
    0,
    100000,
    300000,
    NOW(),
    'SYSTEM',
    'TF1A12F demo: đơn hủy trước khi cổng báo thanh toán.'
);
SET @booking_id := LAST_INSERT_ID();
SET @transaction_code := CONCAT('TF1A12F_DEMO_', @booking_id);

INSERT INTO payment_transactions (
    booking_id,
    transaction_code,
    provider,
    provider_txn_id,
    amount,
    status,
    payment_method,
    paid_at
)
VALUES (
    @booking_id,
    @transaction_code,
    'MOCK_PAY',
    CONCAT('BANK_TF1A12F_', @booking_id),
    100000,
    'LATE_PAYMENT',
    'QR_CODE',
    NOW()
);
SET @transaction_id := LAST_INSERT_ID();

INSERT INTO refunds (
    booking_id,
    payment_transaction_id,
    amount,
    reason,
    status
)
VALUES (
    @booking_id,
    @transaction_id,
    100000,
    'TF1A12F demo: thanh toán đến sau khi đơn đã hủy.',
    'PENDING'
);
SET @refund_id := LAST_INSERT_ID();

INSERT INTO payment_webhook_logs (
    provider_txn_id,
    transaction_code,
    signature_valid,
    process_result,
    queue_reason,
    processed_at
)
VALUES (
    CONCAT('BANK_TF1A12F_', @booking_id),
    @transaction_code,
    'VALID',
    'LATE_PAYMENT',
    'TF1A12F demo: thanh toán đến sau khi đơn đã đóng, cần hoàn tiền.',
    NOW()
);

COMMIT;

SELECT
    @booking_id AS booking_id,
    @transaction_id AS transaction_id,
    @refund_id AS refund_id,
    @transaction_code AS transaction_code,
    'LATE_PAYMENT / PENDING' AS queue_status;
