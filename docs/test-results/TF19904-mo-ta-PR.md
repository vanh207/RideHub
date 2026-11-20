## Mục tiêu

TF19904 — kiểm thử đồng thời luồng đặt xe/giữ chỗ/hủy đơn trên MySQL 8 thật; ghi kết quả và lỗi phát hiện mà **không sửa code sản phẩm**.

## Phạm vi

- Nhánh: `feature/tf19904-kiem-thu-dat-trung-lich` (từ `develop` @ `4badaca`).
- File thêm:
  - `backend/tests/test_booking_concurrency_hold_cancel.py`
  - `backend/pytest.ini` (đăng ký marker `mysql`)
  - `backend/tests/README_TF19904.md`
  - `docs/test-results/TF19904-pytest.log`
  - `docs/test-results/TF19904-ket-qua-kiem-thu.xlsx`
  - `docs/test-results/TF19904-bao-cao.md`
  - `docs/test-results/TF19904-so-do.md`
  - `docs/test-results/TF19904-anh-chup.md`
- Không đụng `app/`, `sql/`, model/router/crud; không commit `.env`, `serviceAccountKey.json`, `.venv`, `__pycache__`.

## Cách chạy

```bash
# Tạo DB riêng (không dùng DB làm việc)
mysql -e "CREATE DATABASE IF NOT EXISTS ridehub_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

export TEST_DATABASE_URL='mysql+pymysql://<user>:<password>@127.0.0.1:3306/ridehub_test?charset=utf8mb4'
cd backend
../.venv/bin/python -m pytest tests/test_booking_concurrency_hold_cancel.py -v --disable-warnings --tb=line
```

Chốt an toàn: thiếu env / không phải MySQL / tên DB không chứa `test` → skip toàn bộ. Mặc định 20 vòng/kịch bản; `TF19904_ROUNDS=3` để smoke nhanh.

## Bảng tóm tắt kết quả (chạy thật 2026-11-20 07:31 +0700)

| Nhóm | Pass | Fail | Blocked | Ghi chú |
|---|---:|---:|---:|---|
| Bước 0 | 1 | 0 | 0 | `POST /api/bookings` có trên develop |
| A — đặt trùng đồng thời | 8 | 0 | 1 | 2/10/20 luồng, 20 vòng: luôn đúng 1 thắng; A8 blocked |
| C — hủy đơn | 5 | 2 | 1 | C1/C4/C5/C6 pass; C2-48h/12h fail; C3 blocked |
| B — giữ chỗ hết hạn | 1 | 2 | 2 | B1 pass; B2/B3 fail; B4/B5 blocked |
| **Tổng** | **15** | **4** | **4** | Log: `docs/test-results/TF19904-pytest.log` |

## Lỗi phát hiện

| ID | Mô tả | Mức độ |
|---|---|---|
| BUG-01 | Hết hạn giữ chỗ nhưng booking `PENDING_PAYMENT` + schedule `ACTIVE` vẫn chặn xe; khách khác không đặt lại được | Cao |
| BUG-02 | Hủy đơn đã cọc không tạo `Refund` theo BR-04 (48h mong 200k, 12h mong 100k, thực tế 0đ) | Cao |
| BUG-03 | develop chưa có job tự hết hạn giữ chỗ | Trung bình |
| BUG-04 | Không có bảng lịch sử đổi trạng thái booking/`changed_by` | Trung bình |

Chi tiết bước tái hiện và gợi ý sửa: sheet **Lỗi phát hiện** trong xlsx.

## Blocked

- A8: không mô phỏng rollback giữa chừng nếu không inject lỗi vào code sản phẩm.
- C3: chưa có bảng booking history.
- B4: chưa có `app/jobs/booking_expiry_job.py` trong develop (chờ TF19814).
- B5: chưa mô phỏng được thanh toán đua hết hạn; ưu tiên thấp.

## Minh chứng

- Log pytest: `docs/test-results/TF19904-pytest.log`
- Bảng kết quả: `docs/test-results/TF19904-ket-qua-kiem-thu.xlsx`
- Báo cáo: `docs/test-results/TF19904-bao-cao.md`
- Sơ đồ: `docs/test-results/TF19904-so-do.md`
- Checklist ảnh cần tự chụp: `docs/test-results/TF19904-anh-chup.md`
