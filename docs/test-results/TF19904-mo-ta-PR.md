## Mục tiêu

TF19814 — hoàn thiện API hủy đơn/hoàn tiền và sửa 4 lỗi do TF19904 phát hiện, kèm bộ test kiểm chứng chạy thật trên MySQL 8 test.

## Phạm vi

- Nhánh: `feature/TF19814-api-huy-don-hoan-tien` (rebase lên `develop` @ `4badaca`).
- Sửa lỗi:
  - BUG-01: hold hết hạn vẫn chặn xe → lọc theo `hold_expires_at` trong conflict query.
  - BUG-02: BR-04 24h/6h, legacy cancel endpoint dùng chung luồng hủy, ghi `Refund`, txn `REFUNDED`.
  - BUG-03: job hết hạn/idempotent/2 job song song được kiểm chứng.
  - BUG-04: thêm `booking_status_history` và ghi `changed_by` cho các chuyển trạng thái.
- Test/minh chứng TF19904:
  - `backend/tests/test_booking_concurrency_hold_cancel.py`
  - `backend/pytest.ini`
  - `backend/tests/README_TF19904.md`
  - `docs/test-results/TF19904-pytest.log`
  - `docs/test-results/TF19904-ket-qua-kiem-thu.xlsx`
  - `docs/test-results/TF19904-bao-cao.md`
  - `docs/test-results/TF19904-so-do.md`
  - `docs/test-results/TF19904-anh-chup.md`
- Không commit `.env`, `serviceAccountKey.json`, `.venv`, `__pycache__`, frontend WIP.

## Cách chạy

```bash
mysql -e "CREATE DATABASE IF NOT EXISTS ridehub_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
export TEST_DATABASE_URL='mysql+pymysql://<user>:<password>@127.0.0.1:3306/ridehub_test?charset=utf8mb4'
cd backend
../.venv/bin/python -m pytest tests/test_booking_concurrency_hold_cancel.py -v
```

Với DB đã tồn tại, chạy `backend/sql/booking_cancellation.sql` hoặc restart server để tạo `booking_status_history` và các cột hủy đơn.

## Kết quả chạy thật

| Nhóm | Pass | Fail | Blocked | Ghi chú |
|---|---:|---:|---:|---|
| Bước 0 | 1 | 0 | 0 | route đăng ký đầy đủ |
| A — đặt trùng đồng thời | 8 | 0 | 1 | 2/10/20 luồng, 20 vòng; A8 blocked |
| C — hủy đơn | 8 | 0 | 0 | BR-04 + history pass |
| B — giữ chỗ hết hạn | 4 | 0 | 1 | job/idempotent/song song pass; B5 blocked |
| **Tổng TF19904** | **21** | **0** | **2** | Log: `docs/test-results/TF19904-pytest.log` |
| Full suite backend | **105** | **0** | **2** | `pytest -q` |

## Blocked còn lại

- A8: rollback giữa chừng cần inject lỗi; không sửa code sản phẩm để mô phỏng.
- B5: cần inject clock/gateway; ưu tiên thấp.

## Minh chứng

- Log pytest, xlsx, báo cáo, sơ đồ Mermaid và checklist ảnh nằm tại `docs/test-results/`.
