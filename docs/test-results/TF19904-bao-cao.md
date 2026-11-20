# TF19904 — Báo cáo kết quả kiểm thử đặt trùng lịch, giữ chỗ và hủy đơn

- Ngày chạy: `2026-11-20 07:31:57 +0700`
- Nhánh: `feature/tf19904-kiem-thu-dat-trung-lich`
- Commit lúc chạy: `4badaca3a1a97af7aab1bade857d24a0e160bf4e` (`origin/develop`)
- DB: `ridehub_test` trên MySQL 8.0.35; fixture chỉ dùng ID `19904xx`; có chốt chặn tên DB phải chứa `test`.
- Lệnh chạy: `cd backend && TEST_DATABASE_URL=<mysql-test-url> ../.venv/bin/python -m pytest tests/test_booking_concurrency_hold_cancel.py -v --disable-warnings --tb=line`
- Log thật: `docs/test-results/TF19904-pytest.log`
- Kết quả: **15 Passed / 4 Failed / 4 Skipped (Blocked)** — 23 test items, 20 vòng/kịch bản.

## 1. Hiện trạng (Bước 0)

| Hạng mục | Kết quả khảo sát trên develop |
|---|---|
| `POST /api/bookings` | Có, đã đăng ký tại `main.py:98`; route list thực tế gồm `/api/bookings` và `/api/bookings/check-eligibility`. Không phải lỗi hồi quy "chỉ còn check-eligibility". |
| Hủy đơn | Không có endpoint hủy trong `bookings.py`. Chỉ có `POST /api/payments/booking/{booking_id}/cancel` (JWT chủ đơn, 404 nếu không phải chủ, 409 nếu `BOOKED/COMPLETED`, idempotent) và `POST /api/payments/refund` (admin, chỉ txn `SUCCESS`). API hủy đầy đủ của TF19814 chưa merge vào develop. |
| Job hết hạn | Chưa có source `app/jobs/booking_expiry_job.py`; `lifespan` của `main.py` không đăng ký scheduler. Chỉ có check hết hạn theo request. |
| Auth/dữ liệu | `customer_id` lấy từ JWT, body bị bỏ qua. `ensure_customer_verified()` là TODO no-op; create không kiểm tuổi/GPLX. Fixture test tạo 3 khách hợp lệ. |
| Status/khóa | Booking hold `PENDING_PAYMENT`; reservation/schedule `ACTIVE`. `BLOCKING_BOOKING_STATUSES` gồm `PENDING_PAYMENT`, `DEPOSIT_PAID`, `PENDING_STORE_CONFIRM`, `CONFIRMED`, `IN_PROGRESS`, `PENDING_SETTLEMENT`, `PENDING`. Conflict chạy sau `SELECT vehicles ... FOR UPDATE`. |
| Cấu hình | `BOOKING_HOLD_MINUTES=30`, `BOOKING_BUFFER_MINUTES=60`, `MIN=4h`, `MAX=30 ngày`, deposit `30%`/min 200k/max 1 triệu, retry lock 3 lần. |

**Điều chỉnh kế hoạch:** A chạy direct CRUD trên session MySQL riêng (vẫn có smoke route); C gọi trực tiếp endpoint hủy/refund của payment router với object user thay vì JWT; B1-B3 test được, B4/B5 bị Blocked do chưa có job/clock injection. Không sửa `app/`, `sql/`, model/router/crud.

## 2. Kết luận theo nhóm

### Nhóm A — đặt trùng lịch đồng thời: **Pass**
A1 (2 luồng), A2 (10 và 20 luồng), A3 (giao nhau 1h), A4 (đệm 60/59 phút), A5 (2 xe), A6 (double-click), A7 (không mồ côi) đều pass 20/20 vòng. Luôn đúng **1 người thắng**; kẻ thua nhận `BookingConflictError` (router ánh xạ 409); DB luôn có đúng 1 booking + 1 reservation + 1 schedule cho slot đó; payment/refund = 0. A8 **Blocked** vì không mô phỏng lỗi giữa chừng mà không inject vào code sản phẩm.

### Nhóm C — hủy đơn và nhả lịch: **5 Pass / 2 Fail / 1 Blocked**
- Pass: C1 (hủy đơn chưa cọc → khách khác đặt lại được cả 20 vòng), C2-5h (không hoàn là đúng BR-04), C4 (404 khi hủy đơn người khác), C5 (COMPLETED → 409; hủy lặp 2 lần vẫn nhất quán, không 2 refund), C6 (2 cancel đồng thời + cancel đua rebook không tạo trùng).
- Fail: C2-48h và C2-12h — endpoint cancel chỉ hủy txn `PENDING`, không tạo `Refund` dù txn `SUCCESS`; mong đợi 200.000đ/100.000đ, thực tế 0đ. Xem BUG-02.
- Blocked: C3 — develop không có bảng lịch sử trạng thái booking. Xem BUG-04.

### Nhóm B — giữ chỗ hết hạn: **1 Pass / 2 Fail / 2 Blocked**
- Pass: B1 — `booking.hold_expires_at == reservation.expires_at == now + 30p` (sai số ≤2s).
- Fail: B2 — ở `now+30:00`, reservation đã hết hạn nhưng `vehicle_has_conflict()` vẫn `True`; booking `PENDING_PAYMENT` + schedule `ACTIVE` vẫn chặn. B3 — khách khác đặt lại nhận `BookingConflictError`; reservation vẫn `ACTIVE`, schedule vẫn `ACTIVE`. Xem BUG-01.
- Blocked: B4 (chưa có job tự hết hạn), B5 (chưa mô phỏng được thanh toán đua hết hạn).

## 3. Lỗi phát hiện

| ID | Mô tả | Mức độ | Liên quan |
|---|---|---|---|
| BUG-01 | Hết hạn giữ chỗ nhưng xe vẫn bị chặn oan | Cao | TF197DE / TF19814 |
| BUG-02 | Hủy đơn đã cọc không hoàn theo BR-04 (48h → 100%, 12h → 50%) | Cao | TF19814 / BR-04 |
| BUG-03 | Chưa có job tự hết hạn trên develop | Trung bình | TF19814 |
| BUG-04 | Không có lịch sử đổi trạng thái booking/`changed_by` | Trung bình | TF19814 |

Chi tiết bước tái hiện, mong đợi/thực tế và gợi ý sửa nằm trong sheet **Lỗi phát hiện** của `TF19904-ket-qua-kiem-thu.xlsx`.

## 4. Phần Blocked và lý do

- `TC-A8`: rollback giữa chừng cần hook lỗi/DB kill; không được sửa code sản phẩm.
- `TC-C3`: chưa có bảng `booking_status_history` trên develop.
- `TC-B4`: chưa có `app/jobs/booking_expiry_job.py` và không có scheduler trong `lifespan`.
- `TC-B5`: cần inject clock/gateway để mô phỏng đúng thời điểm hết hạn; ưu tiên thấp.

## 5. Đề xuất

1. Ưu tiên merge TF19814 sau khi xử lý BUG-01/BUG-02; bổ sung job hết hạn và policy BR-04 vào cùng transaction hủy.
2. Khi sửa BUG-01, cần xử lý đồng thời 3 nguồn chặn: booking `PENDING_PAYMENT`, reservation `ACTIVE`, schedule `ACTIVE`; đừng chỉ dựa vào `expires_at`.
3. Thêm bảng history booking để truy vết `changed_by` rỗng/SYSTEM phục vụ audit.
4. Sau khi merge, chạy lại toàn bộ test TF19904 trên `ridehub_test` và cập nhật xlsx.

## 6. Phần đã làm / chưa làm

**Đã làm:** Bước 0; bộ test pytest 23 items cho A/B/C + route smoke; chốt an toàn DB test; chạy thật 20 vòng/MySQL 8; log, xlsx, báo cáo, sơ đồ, checklist ảnh, mô tả PR; branch + commit/push theo quy ước.

**Chưa làm:** A8, C3, B4, B5 (Blocked như trên); không tự sửa lỗi sản phẩm; không chụp ảnh màn hình thay người nộp (đã chuẩn bị danh sách cần chụp); không tạo PR nếu người dùng chỉ yêu cầu nộp link nhánh/file (đã soạn sẵn mô tả).
