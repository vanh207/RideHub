# TF199BD — Báo cáo index tìm xe theo thời gian trống

## 1. Mục tiêu và phạm vi

Tối ưu `search_public_vehicles` / `vehicle_has_conflict` trong `backend/app/crud/vehicle.py` khi kiểm tra xe trống theo khung giờ. Chỉ thêm index và một hint MySQL trên đúng subquery booking; không đổi điều kiện nghiệp vụ, buffer 60 phút, trạng thái bị chặn hay thứ tự trả kết quả.

Chốt an toàn: mọi thao tác đo nằm ở `ridehub_perf`. Không đụng DB làm việc/dev. Script `scripts/perf/db_guard.py` từ chối chạy nếu tên DB không chứa `perf` hoặc `test`.

## 2. Môi trường đo

- MySQL `8.0.35` (`EXPLAIN ANALYZE` yêu cầu >= 8.0.18).
- Database: `ridehub_perf`; `@@session.time_zone = SYSTEM`.
- Seed tái lập: `--scale 1.0 --seed 20261120 --reset --batch-size 10000`.
- Tập dữ liệu: `bookings=500000`, `vehicle_reservations=100000`, `vehicle_schedules=100000`, `vehicles=5000`, `stores=50`, `delivery_points=250`.
- Cấu hình đo: `30 repeats`, `3 warmup`, median/p95 từ `scripts/perf/measure.py`; dùng cùng tham số cho baseline và sau.

## 3. Baseline và nguyên nhân

Trước khi sửa, `EXPLAIN ANALYZE` cho thấy subquery booking bị materialize toàn bảng:

```text
-> Aggregate: count(vehicles.id)  (cost=492e+6 rows=1) (actual time=1221..1221 rows=1 loops=1)
            -> Materialize with deduplication  (cost=100147..100147 rows=497087) (actual time=822..822 rows=0 loops=1)
                        -> Table scan on bookings  (cost=50438 rows=497087) (actual time=0.0428..577 rows=500000 loops=1)
```

`COUNT` và `SELECT` đều lặp cùng điều kiện này; S4 ở trang cuối còn phải sort 3600 dòng sau khi materialize 500000 dòng booking.

## 4. Quyết định index

Giữ 2 index:

| Bảng | Index | Lý do |
|---|---|---|
| `bookings` | `ix_bookings_end_start_status_vehicle_hold (end_time, start_time, status, vehicle_id, hold_expires_at)` | Khi được dùng, subquery booking chuyển từ `Table scan on bookings` sang `Covering index range scan ... over ('...' < end_time)`. Các cột còn lại nằm trong index nên không cần đọc lại bảng. |
| `delivery_points` | `ix_delivery_points_store_active_area (store_id, is_active, area)` | S3 chuyển sang `Covering index lookup ... rows=5` thay vì quét `delivery_points`; phục vụ filter khu vực giao hàng. |

Chỉ dùng index `bookings` là chưa đủ: optimizer vẫn chọn `Table scan on bookings` dù index đã tồn tại. Vì vậy `app/crud/vehicle.py` thêm `FORCE INDEX (ix_bookings_end_start_status_vehicle_hold)` **chỉ cho subquery booking đầu tiên** qua `with_hint(..., dialect_name="mysql")`. SQLite bỏ qua hint nên test SQLite không đổi.

Các ứng viên bị loại sau khi đo:

- `ix_bookings_status_end_start_vehicle_hold`: sinh nhiều range scan theo từng status, S2/S4 chậm hơn ứng viên end-first.
- `ix_vehicles_active_price_id`: vẫn phải `Sort: vehicles.price_per_day, vehicles.id`, không giảm filesort.
- `ix_schedules_vehicle_status_time_booking`: plan xấu hơn khi bật visibility; không giữ.
- `materialization=off`: S1 count `1.973s`, S2 count `0.986s`, chậm hơn baseline; không dùng.

## 5. Kết quả đo sau khi áp

Đơn vị: ms, median của 30 lần chạy sau 3 lần warmup.

| Kịch bản | Trước COUNT | Sau COUNT | Giảm | Trước SELECT | Sau SELECT | Giảm | API trước | API sau |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| S1 | 946.546 | 129.420 | 86.3% | 743.255 | 128.759 | 82.7% | 1689.801 | 258.179 |
| S2 | 1078.358 | 456.739 | 57.6% | 676.817 | 442.461 | 34.6% | 1755.175 | 899.200 |
| S3 | 808.412 | 78.107 | 90.3% | 84.864 | 56.253 | 33.7% | 893.276 | 134.360 |
| S4 | 1195.924 | 132.264 | 88.9% | 1368.189 | 141.081 | 89.7% | 2564.113 | 273.345 |
| S5_NORMAL | 1.552 | 1.490 | ~ | — | — | — | — | — |
| S5_HOT | 2.061 | 2.297 | ~ | — | — | — | — | — |

Plan sau cho S1:

```text
-> Aggregate: count(vehicles.id)  (cost=3221 rows=1) (actual time=144..144 rows=1 loops=1)
            -> Materialize with deduplication  (cost=1.31..1.31 rows=1) (actual time=0.0269..0.0269 rows=0 loops=1)
                        -> Covering index range scan on bookings using ix_bookings_end_start_status_vehicle_hold over ('2027-03-10 07:00:00' < end_time)  (cost=1.21 rows=1) (actual time=0.0233..0.0233 rows=0 loops=1)
```

S5 là câu kiểm tra một xe, vốn đã dùng index sẵn; chênh lệch ~0.2ms nằm trong nhiễu đo.

## 6. Kiểm chứng đúng kết quả

`scripts/perf/verify_equivalence.py` so sánh SQL gốc (bỏ hint) và SQL sau (có hint) trên cùng dataset: `10/10` kịch bản giống hệt, gồm COUNT/SELECT của S1–S4 và CONFLICT của S5_NORMAL/S5_HOT. Chi tiết: `docs/perf/TF199BD-kiem-chung-tuong-duong.json`.

## 7. Migration và rollback

- Tạo: `backend/sql/migrations/TF199BD_index_tim_xe_trong.sql`
- Gỡ: `backend/sql/migrations/TF199BD_rollback_index_tim_xe_trong.sql`
- DB mới: index đã khai báo trong `backend/sql/erd_migration.sql`.
- Model: `backend/app/models/booking.py` và `backend/app/models/delivery.py`.
- Fixture test MySQL tự tạo index nếu bảng test cũ chưa có; `create_all` không tự sửa bảng đã tồn tại.

## 8. Kiểm thử

- Full suite: `105 passed, 2 skipped`.
- Không tìm thấy cấu hình lint/typecheck riêng trong repo; đã biên dịch cú pháp Python bằng `compileall` trước khi commit.

## 9. Phụ lục

- SQL thật: `docs/perf/TF199BD-sql-that.md`
- Index/DDL hiện có: `docs/perf/TF199BD-index-hien-co.md`
- Baseline: `docs/perf/TF199BD-baseline.json`
- Sau: `docs/perf/TF199BD-after.json`
- Bảng test case: `docs/perf/TF199BD-bang-test-case.xlsx`
- Sơ đồ: `docs/perf/TF199BD-so-do.md`
