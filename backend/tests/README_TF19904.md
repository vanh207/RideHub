# TF19904 — hướng dẫn chạy test trên DB test riêng

## 1. Tạo database test (không đụng DB làm việc)

Kết nối bằng chính user/password trong `backend/.env` nhưng tạo DB mới:

```sql
CREATE DATABASE IF NOT EXISTS ridehub_test
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Không dùng `DB_NAME` hiện tại. Script/pytest sẽ `CREATE TABLE` nếu thiếu và
chỉ xóa dữ liệu có ID test `19904xx`.

## 2. Export biến môi trường

```bash
export TEST_DATABASE_URL='mysql+pymysql://<user>:<password>@127.0.0.1:3306/ridehub_test?charset=utf8mb4'
```

Chốt an toàn trong test: nếu thiếu biến, không phải MySQL, hoặc tên DB không
chứa `test` thì toàn bộ test được skip.

## 3. Chạy

```bash
cd backend
../.venv/bin/python -m pytest tests/test_booking_concurrency_hold_cancel.py -v
```

Mặc định mỗi kịch bản chạy 20 vòng. Giảm số vòng khi cần smoke:

```bash
TF19904_ROUNDS=3 ../.venv/bin/python -m pytest tests/test_booking_concurrency_hold_cancel.py -v
```

## 4. Ghi kết quả

Log chạy thật được lưu tại `docs/test-results/TF19904-pytest.log`.

Sau khi sửa 4 lỗi TF19904: **21 passed / 0 failed / 2 blocked**. Các test bị skip là
`TC-A8` và `TC-B5`, cần inject lỗi/clock để mô phỏng; không phải lỗi sản phẩm.

Nếu DB test đã tồn tại từ trước, chạy `backend/sql/booking_cancellation.sql` hoặc
restart server để có `booking_status_history` và 3 cột `cancelled_at`, `cancelled_by`,
`cancel_reason` trên bảng `bookings`.
