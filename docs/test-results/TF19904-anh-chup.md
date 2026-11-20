# TF19904 — Danh sách ảnh chụp minh chứng cần nộp

Người nộp chỉ cần chạy các lệnh dưới đây trên terminal có `TEST_DATABASE_URL` trỏ tới `ridehub_test`, rồi chụp màn hình theo mô tả. **Không chụp màn hình có chứa mật khẩu DB.**

## Ảnh 1 — Tổng kết pytest

```bash
cd backend
TEST_DATABASE_URL='<mysql-test-url>' ../.venv/bin/python -m pytest tests/test_booking_concurrency_hold_cancel.py -v --disable-warnings --tb=line
```

Chụp: dòng tổng kết `4 failed, 15 passed, 4 skipped, 315 warnings in 22.68s` và danh sách 4 test FAILED ngay phía trên.
File log tương ứng: `docs/test-results/TF19904-pytest.log`.

## Ảnh 2 — SQL đếm bản ghi sau A1

Chạy riêng A1 để giữ trạng thái DB đúng sau kịch bản:

```bash
TEST_DATABASE_URL='<mysql-test-url>' ../.venv/bin/python -m pytest tests/test_booking_concurrency_hold_cancel.py::test_TC_A1_two_customers_same_vehicle_same_slot -v
```

SQL:

```sql
SELECT b.id, b.customer_id, b.status, b.start_time, b.end_time,
       (SELECT COUNT(*) FROM vehicle_reservations r WHERE r.booking_id = b.id) AS reservations,
       (SELECT COUNT(*) FROM vehicle_schedules s WHERE s.booking_id = b.id) AS schedules
FROM bookings b
WHERE b.vehicle_id = 1990401
  AND b.customer_id IN (1990411, 1990412)
ORDER BY b.id;

SELECT
  (SELECT COUNT(*) FROM payment_transactions) AS payments,
  (SELECT COUNT(*) FROM refunds) AS refunds;
```

Chụp: terminal hiển thị **1 dòng booking** và `reservations=1, schedules=1`, `payments=0, refunds=0`.

## Ảnh 3 — Bảng dữ liệu sau C1 (đã hủy, xe rảnh)

```bash
TEST_DATABASE_URL='<mysql-test-url>' ../.venv/bin/python -m pytest tests/test_booking_concurrency_hold_cancel.py::test_TC_C1_cancel_unpaid_booking_releases_slot -v
```

SQL:

```sql
SELECT id, customer_id, status, start_time, end_time, hold_expires_at
FROM bookings
WHERE vehicle_id = 1990401 AND customer_id IN (1990411, 1990412)
ORDER BY id;

SELECT id, booking_id, status, expires_at
FROM vehicle_reservations
WHERE vehicle_id = 1990401;

SELECT id, booking_id, reservation_id, schedule_type, status
FROM vehicle_schedules
WHERE vehicle_id = 1990401;
```

Chụp: booking đầu `CANCELLED`, reservation/schedule tương ứng `CANCELLED`, booking thứ hai (khách đặt lại) `PENDING_PAYMENT`.

## Ảnh 4 — Bảng dữ liệu sau B3 (lỗi hết hạn)

```bash
TEST_DATABASE_URL='<mysql-test-url>' ../.venv/bin/python -m pytest tests/test_booking_concurrency_hold_cancel.py::test_TC_B3_rebook_after_hold_expiry -v
```

SQL:

```sql
SELECT id, status, hold_expires_at, start_time, end_time
FROM bookings
WHERE vehicle_id = 1990401;

SELECT id, booking_id, status, expires_at
FROM vehicle_reservations
WHERE vehicle_id = 1990401;

SELECT id, booking_id, status, start_time, end_time
FROM vehicle_schedules
WHERE vehicle_id = 1990401;
```

Chụp: `hold_expires_at` đã ở quá khứ nhưng booking vẫn `PENDING_PAYMENT`, reservation vẫn `ACTIVE`, schedule vẫn `ACTIVE`; pytest báo `BookingConflictError`.

## Ảnh 5 — Cấu hình đệm/giữ chỗ

```bash
cd backend
../.venv/bin/python -c "from app.core.config import settings; print(settings.BOOKING_HOLD_MINUTES, settings.BOOKING_BUFFER_MINUTES, settings.BOOKING_DEPOSIT_RATE)"
```

Chụp: dòng `30 60 0.30` để đối chiếu A4/B1/B2.

## Gợi ý nộp

- Nộp link PR/link nhánh TF19904 **hoặc** đính kèm `TF19904-ket-qua-kiem-thu.xlsx`.
- Nếu nộp ảnh, đính kèm 5 ảnh trên theo đúng thứ tự để dễ đối chiếu với sheet "Test case".
