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
Các test `Fail` là lỗi sản phẩm đã được ghi trong sheet "Lỗi phát hiện";
các test `Blocked/skip` là tính năng chưa tồn tại trên `develop`.
