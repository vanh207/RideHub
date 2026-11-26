# Seed dữ liệu mẫu đơn thuê TF1AE49

Script này tạo dữ liệu mẫu trên **DB test/demo** để kiểm chứng các trạng thái đơn, luồng hủy/hoàn tiền, bàn giao xe và khả năng hiển thị trên các màn hình liên quan.

## Cảnh báo an toàn

- Chỉ chạy khi `DB_NAME` hoặc URL DB chứa `test`, `demo` hoặc `dev`.
- Script chặn mọi môi trường có `prod`, `production`, `live`.
- Mọi lần ghi đều cần `--yes`; mặc định script chỉ in kế hoạch.
- Script chỉ xóa dữ liệu có dấu `[DEMO] TF1AE49`, không đụng dữ liệu thật.
- Không sửa code sản phẩm; script chỉ đọc cấu hình/hàm tính của backend.

## Yêu cầu dữ liệu nền

Chạy từ thư mục `backend/` trước khi seed TF1AE49:

```bash
DB_NAME=ridehub_test ../.venv/bin/python -c "from app.db.seed_data import seed_default_accounts; seed_default_accounts()"
DB_NAME=ridehub_test ../.venv/bin/python -c "from app.db.seed_vehicles_delivery import seed_vehicles_and_delivery; seed_vehicles_and_delivery()"
```

Script tự tra cứu theo email, cửa hàng của xe nền và biển số; **không hard-code ID**.

## Cách chạy

Từ thư mục `backend/`:

```bash
# Xem trước, không ghi DB
DB_NAME=ridehub_test ../.venv/bin/python -m scripts.seed_demo_bookings --dry-run

# Xem trước danh sách sẽ bị xóa khi reset
DB_NAME=ridehub_test ../.venv/bin/python -m scripts.seed_demo_bookings --dry-run --reset

# Ghi dữ liệu mẫu
DB_NAME=ridehub_test ../.venv/bin/python -m scripts.seed_demo_bookings --yes

# Xóa dữ liệu TF1AE49 rồi tạo lại
DB_NAME=ridehub_test ../.venv/bin/python -m scripts.seed_demo_bookings --reseed --yes

# Chỉ xóa dữ liệu TF1AE49
DB_NAME=ridehub_test ../.venv/bin/python -m scripts.seed_demo_bookings --reset --yes
```

Chạy test:

```bash
DB_NAME=ridehub_test ../.venv/bin/python -m pytest tests/test_seed_demo_bookings.py -v
```

## Dữ liệu tạo ra

15 đơn mẫu, 124 dòng dữ liệu trên các bảng:

| Bảng | Số dòng |
|---|---:|
| `bookings` | 15 |
| `booking_status_history` | 44 |
| `vehicle_reservations` | 15 |
| `vehicle_schedules` | 15 |
| `payment_transactions` | 16 |
| `refunds` | 4 |
| `handover_protocols` | 5 |
| `complaints` | 1 |
| `complaint_status_histories` | 1 |
| `vehicle_status_history` | 8 |

| Trạng thái | Mã đơn mẫu | Ý nghĩa |
|---|---|---|
| `PENDING_PAYMENT` | `DEMO-TF1AE49-01-PP-FRESH`, `DEMO-TF1AE49-02-PP-SOON` | Chờ thanh toán, còn hạn / sắp hết hạn giữ chỗ |
| `DEPOSIT_PAID` | `DEMO-TF1AE49-03-DEPOSIT-PAID` | Đã cọc, chờ cửa hàng duyệt |
| `PENDING_STORE_CONFIRM` | `DEMO-TF1AE49-04-PENDING-STORE` | Legacy/SRS, tương đương `DEPOSIT_PAID` |
| `BOOKED` | `DEMO-TF1AE49-15-BOOKED-LEGACY` | Legacy webhook, tương đương `DEPOSIT_PAID` |
| `CONFIRMED` | `DEMO-TF1AE49-05-CONFIRMED` | Đã duyệt, bắt đầu trong tương lai gần |
| `IN_PROGRESS` | `DEMO-TF1AE49-06-IN-PROGRESS` | Đang thuê, đã giao xe |
| `PENDING_SETTLEMENT` | `DEMO-TF1AE49-07-PENDING-SETTLEMENT` | Đã trả xe, chờ tất toán |
| `COMPLETED` | `DEMO-TF1AE49-09-COMPLETED` | Hoàn tất đủ cọc, giao nhận, tất toán |
| `EXPIRED` | `DEMO-TF1AE49-10-EXPIRED` | Hết hạn giữ chỗ, lịch đã nhả |
| `CANCELLED` | `DEMO-TF1AE49-11-CANCEL-FULL`, `12-CANCEL-PARTIAL`, `13-CANCEL-LATE` | Hủy theo BR-04: 100% / 50% / 0% |
| `REJECTED` | `DEMO-TF1AE49-14-REJECTED` | SRS; backend hiện ghi `CANCELLED` |
| `DISPUTED` | `DEMO-TF1AE49-08-DISPUTED` | SRS; không có canonical trong backend |

## Dấu nhận diện và dọn dẹp

DB test hiện không có `booking_code` và `customer_note`, nên script dùng các dấu sau:

- `booking_status_history.reason`: `[DEMO] TF1AE49:<mã đơn>|NEW->...`
- `vehicle_schedules.note`: `[DEMO] TF1AE49:<mã đơn>|prev=...`
- `payment_transactions.transaction_code`: tiền tố `TF1AE49`
- `handover_protocols.protocol_code`: tiền tố `TF1AE49`
- `vehicle_status_history.note`: `[DEMO] TF1AE49:<mã đơn>|prev=<trạng thái cũ>`

`--reset` tìm booking qua các dấu trên, xóa theo thứ tự an toàn và khôi phục `vehicles.current_status` từ giá trị `prev=...`.

## Kiểm chứng

- 15/15 đơn được tạo; chạy lại lần 2 bỏ qua 15 đơn.
- `--reset` không còn dòng mang dấu TF1AE49; `users`, `stores`, `vehicles` giữ nguyên.
- Tổng tiền, cọc, giữ chỗ, schedule, refund, handover và lịch sử trạng thái nhất quán.
- API `GET /api/vehicles/search` ẩn xe đang có đơn `CONFIRMED`, hiện lại xe của đơn `CANCELLED`.
- Test tự động: 4/4 passed.
