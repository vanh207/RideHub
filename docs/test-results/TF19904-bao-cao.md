# TF19904 — Báo cáo kết quả kiểm thử sau khi sửa lỗi

- Ngày chạy lại: `2026-11-20`
- Nhánh: `feature/TF19814-api-huy-don-hoan-tien` (rebase lên `origin/develop` @ `4badaca`)
- DB: `ridehub_test` trên MySQL 8.0.35; fixture chỉ dùng ID `19904xx`; chốt tên DB phải chứa `test`.
- Lệnh chạy TF19904: `cd backend && TEST_DATABASE_URL=<mysql-test-url> ../.venv/bin/python -m pytest tests/test_booking_concurrency_hold_cancel.py -v --disable-warnings --tb=line`
- Log thật: `docs/test-results/TF19904-pytest.log`
- Kết quả TF19904: **21 Passed / 0 Failed / 2 Skipped (Blocked)** — 23 test items, 20 vòng/kịch bản.
- Full suite backend: **105 Passed / 2 Skipped**.

## 1. Kết luận theo nhóm

### Nhóm A — đặt trùng lịch đồng thời: **8 Pass / 1 Blocked**
A1–A7 pass 20/20 vòng; luôn đúng 1 người thắng ở 2/10/20 luồng, không có bản ghi mồ côi. A8 vẫn Blocked do không inject lỗi giữa chừng.

### Nhóm C — hủy đơn và nhả lịch: **8 Pass / 0 Fail / 0 Blocked**
- C1: hủy đơn chưa cọc nhả reservation/schedule, khách khác đặt lại được.
- C2: BR-04 đúng 48h → 200.000đ, 12h → 100.000đ, 5h → 0đ; refund được ghi trong cùng transaction, txn chuyển `REFUNDED`.
- C3: có `booking_status_history` với 2 dòng `PENDING_PAYMENT → CANCELLED`, `changed_by=CUSTOMER`, `changed_by_user_id` đúng.
- C4/C5/C6: phân quyền, terminal, idempotent và cancel đua rebook đều pass.

### Nhóm B — giữ chỗ hết hạn: **4 Pass / 1 Blocked**
- B1: `hold_expires_at == reservation.expires_at == now + 30p`.
- B2: 29:59 còn chặn; đúng 30:00 không còn chặn dù job chưa chạy.
- B3: khách khác đặt lại thành công ngay sau hết hạn.
- B4: job chuyển `EXPIRED`, nhả reservation/schedule, chạy lại idempotent và 2 job song song chỉ expire 1 đơn.
- B5 vẫn Blocked do chưa inject clock/gateway để mô phỏng đúng thời điểm thanh toán đua hết hạn.

## 2. Các lỗi đã sửa

| ID | Lỗi | Cách sửa | Bằng chứng |
|---|---|---|---|
| BUG-01 | Hết hạn giữ chỗ nhưng xe vẫn bị chặn | `crud/vehicle.py` loại khỏi conflict query các booking/reservation/schedule thuộc hold đã quá `hold_expires_at`; `expire_hold_bookings` cũng quét cả legacy `PENDING` | B2, B3 pass |
| BUG-02 | Hủy đơn đã cọc không hoàn BR-04 | Đổi ngưỡng 24h/6h; endpoint legacy `/api/payments/booking/{id}/cancel` gọi chung `cancel_booking`; tạo `Refund`, đổi txn sang `REFUNDED`, chặn refund trùng | C2 pass 3/3 |
| BUG-03 | Chưa có job hết hạn trên develop | Giữ job `app/jobs/booking_expiry_job.py` + lifespan; bổ sung test expire, idempotent, 2 job song song | B4 pass |
| BUG-04 | Không có lịch sử trạng thái booking | Thêm `BookingStatusHistory`, DDL, helper ghi trong tạo đơn/hủy/hết hạn/payment/reconciliation | C3, B4 pass |

## 3. Blocked còn lại

- `TC-A8`: cần hook lỗi/DB kill để mô phỏng rollback giữa chừng; không inject vào code sản phẩm.
- `TC-B5`: cần inject clock/gateway để mô phỏng thanh toán đúng thời điểm hết hạn; ưu tiên thấp.

## 4. Lưu ý khi deploy

- Chạy `backend/sql/booking_cancellation.sql` hoặc restart server để `create_all()` tạo bảng `booking_status_history` và bổ sung 3 cột hủy đơn cho DB đã có.
- Cấu hình mới: `BOOKING_CANCEL_FREE_HOURS=24`, `BOOKING_CANCEL_PARTIAL_HOURS=6`, `BOOKING_CANCEL_PARTIAL_RATE=0.5`.

## 5. Phần đã làm / chưa làm

**Đã làm:** sửa cả 4 lỗi; cập nhật test TF19904 để kiểm chứng job/history; chạy lại trên MySQL test; cập nhật xlsx/log/báo cáo; full suite backend pass.

**Chưa làm:** A8, B5 vẫn Blocked; không chụp ảnh màn hình thay người nộp; không đụng DB làm việc hay frontend WIP.
