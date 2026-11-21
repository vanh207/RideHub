-- Local/development only. Run after seed_tf19fb0_demo_vehicle.sql and backend startup.
-- Safe to rerun with the same suffix: it neither duplicates nor resets a processed refund.
-- Change @demo_suffix (for example to '02') to create another independent test case.
SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;
START TRANSACTION;

SET @demo_suffix := '01';
SET @transaction_code := CONCAT('TF1A0A9_DEMO_', @demo_suffix);
SET @booking_marker := CONCAT('TF1A0A9 demo anomaly seed ', @demo_suffix);
SET @existing_transaction_id := (
    SELECT id
    FROM payment_transactions
    WHERE transaction_code = @transaction_code
    ORDER BY id
    LIMIT 1
);
SET @existing_transaction_booking_id := (
    SELECT booking_id
    FROM payment_transactions
    WHERE id = @existing_transaction_id
);
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
SET @existing_booking_id := (
    SELECT id
    FROM bookings
    WHERE cancel_reason = @booking_marker
    ORDER BY id
    LIMIT 1
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
SELECT
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
    @booking_marker
FROM DUAL
WHERE @existing_booking_id IS NULL
  AND NOT EXISTS (
      SELECT 1
      FROM payment_transactions
      WHERE transaction_code = @transaction_code
  );
SET @booking_id := COALESCE(
    @existing_booking_id,
    @existing_transaction_booking_id,
    LAST_INSERT_ID()
);

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
    CONCAT('BANK_TF1A0A9_', @demo_suffix),
    100000,
    'LATE_PAYMENT',
    'QR_CODE',
    NOW()
)
ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id);
SET @transaction_id := LAST_INSERT_ID();

SET @existing_refund_id := (
    SELECT id
    FROM refunds
    WHERE payment_transaction_id = @transaction_id
    ORDER BY id
    LIMIT 1
);
INSERT INTO refunds (
    booking_id,
    payment_transaction_id,
    amount,
    reason,
    status
)
SELECT
    @booking_id,
    @transaction_id,
    100000,
    CONCAT('TF1A0A9 demo: thanh toán đến sau khi đơn đã hủy (', @demo_suffix, ').'),
    'PENDING'
FROM DUAL
WHERE @existing_refund_id IS NULL;
SET @refund_id := COALESCE(@existing_refund_id, LAST_INSERT_ID());

SET @existing_webhook_log_id := (
    SELECT id
    FROM payment_webhook_logs
    WHERE transaction_code = @transaction_code
      AND process_result = 'LATE_PAYMENT'
    ORDER BY id
    LIMIT 1
);
INSERT INTO payment_webhook_logs (
    provider_txn_id,
    transaction_code,
    signature_valid,
    process_result,
    queue_reason,
    processed_at
)
SELECT
    CONCAT('BANK_TF1A0A9_', @demo_suffix),
    @transaction_code,
    'VALID',
    'LATE_PAYMENT',
    CONCAT('TF1A0A9 demo: thanh toán đến sau khi đơn đã đóng (', @demo_suffix, ').'),
    NOW()
FROM DUAL
WHERE @existing_webhook_log_id IS NULL;

COMMIT;

SELECT
    booking.id AS booking_id,
    pt.id AS transaction_id,
    pt.transaction_code,
    pt.status AS transaction_status,
    refund.id AS refund_id,
    refund.status AS refund_status,
    CASE
        WHEN refund.status = 'PENDING'
         AND pt.status IN ('SUCCESS', 'LATE_PAYMENT')
         AND refund.amount > 0
         AND refund.amount <= pt.amount
        THEN TRUE
        ELSE FALSE
    END AS can_refund
FROM payment_transactions AS pt
JOIN bookings AS booking ON booking.id = pt.booking_id
LEFT JOIN refunds AS refund ON refund.payment_transaction_id = pt.id
WHERE pt.transaction_code = @transaction_code
ORDER BY refund.id
LIMIT 1;
