## TF199BD — Index tìm xe theo thời gian trống

### Mục tiêu
Tối ưu câu tìm xe theo khung giờ bằng 2 index có bằng chứng `EXPLAIN` và một hint MySQL nhắm đúng subquery booking. Không đổi điều kiện nghiệp vụ, buffer 60 phút, trạng thái bị chặn, sort hay phân trang.

### Thay đổi chính
- Thêm `ix_bookings_end_start_status_vehicle_hold (end_time, start_time, status, vehicle_id, hold_expires_at)` cho `bookings`.
- Thêm `ix_delivery_points_store_active_area (store_id, is_active, area)` cho `delivery_points`.
- `app/crud/vehicle.py`: dùng `with_hint(..., dialect_name="mysql")` để `FORCE INDEX` chỉ trên subquery booking đầu tiên. SQLite bỏ qua hint.
- Cập nhật model, `sql/erd_migration.sql`, migration/rollback SQL riêng cho TF199BD.
- Fixture test MySQL tự tạo index nếu bảng test cũ chưa có.
- Thêm bộ script đo/kiểm chứng trong `backend/scripts/perf/` và minh chứng trong `docs/perf/`.

### Bằng chứng đo
- Môi trường: `ridehub_perf`, MySQL `8.0.35`, 500000 bookings, 100000 reservations, 100000 schedules, 5000 vehicles, 50 stores, 250 delivery points.
- Cùng tham số `30 repeats / 3 warmup`.

| Kịch bản | API trước (ms) | API sau (ms) |
|---|---:|---:|
| S1 | 1689.801 | 258.179 |
| S2 | 1755.175 | 899.200 |
| S3 | 893.276 | 134.360 |
| S4 | 2564.113 | 273.345 |

- `EXPLAIN ANALYZE`: subquery booking chuyển từ `Table scan on bookings` (~500000 dòng) sang `Covering index range scan ... end_time`.
- Kiểm chứng tương đương: `10/10` kịch bản COUNT/SELECT/CONFLICT giống hệt.
- Test: `105 passed, 2 skipped`.

### Chốt an toàn
- Không đụng DB làm việc/dev; script chốt tên DB chứa `perf`/`test`.
- Không commit secret, `.env`, service account, file dữ liệu lớn.

### Kiểm tra trước khi merge
- [x] Đo baseline trước khi sửa.
- [x] `EXPLAIN` chứng minh từng index được giữ.
- [x] Kết quả trả về y hệt SQL gốc.
- [x] Migration và rollback có sẵn.
- [x] Full test pass.
- [x] Docs md/xlsx/sơ đồ có sẵn.

Chi tiết: `docs/perf/TF199BD-bao-cao.md`.
