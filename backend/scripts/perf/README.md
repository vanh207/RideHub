# scripts/perf — đo hiệu năng TF199BD

Các script này chỉ chạy trên DB có tên chứa `perf` hoặc `test`. `db_guard.py` sẽ từ chối nếu URL trỏ tới DB khác. Không dùng DB làm việc/dev.

## Chuẩn bị

```bash
cd backend
python -m venv .venv  # nếu chưa có
.venv/bin/python -m pip install -r requirements.txt
export PERF_DATABASE_URL='mysql+pymysql://user:pass@127.0.0.1:3306/ridehub_perf?charset=utf8mb4'
```

## Chạy tuần tự

```bash
# 1. Xuất SQL thật do ORM sinh ra
PYTHONPATH=.:scripts/perf .venv/bin/python scripts/perf/compile_queries.py

# 2. Lấy index/DDL hiện có từ DB perf
PYTHONPATH=.:scripts/perf .venv/bin/python scripts/perf/inspect_schema.py

# 3. Seed dữ liệu tái lập (chỉ trên ridehub_perf)
PYTHONPATH=.:scripts/perf .venv/bin/python scripts/perf/seed_perf_data.py \
  --scale 1.0 --seed 20261120 --reset --batch-size 10000

# 4. Đo baseline (trước khi đổi code/index) hoặc sau
PYTHONPATH=.:scripts/perf .venv/bin/python scripts/perf/measure.py \
  --phase baseline --repeats 30 --warmup 3
PYTHONPATH=.:scripts/perf .venv/bin/python scripts/perf/measure.py \
  --phase after --repeats 30 --warmup 3

# 5. So sánh kết quả SQL gốc và SQL sau hint
PYTHONPATH=.:scripts/perf .venv/bin/python scripts/perf/verify_equivalence.py
```

## Ý nghĩa từng file

- `db_guard.py`: đọc URL từ môi trường, chốt tên DB, tạo engine.
- `scenarios.py`: S1–S5, biên dịch statement thật của `app.crud.vehicle`.
- `compile_queries.py`: ghi `docs/perf/TF199BD-sql-that.md`.
- `inspect_schema.py`: ghi `docs/perf/TF199BD-index-hien-co.md`.
- `seed_perf_data.py`: tạo dữ liệu deterministic, có `--reset`.
- `measure.py`: ghi `docs/perf/TF199BD-<phase>.json`, gồm `EXPLAIN`, `EXPLAIN ANALYZE`, Handler_read và latency.
- `verify_equivalence.py`: ghi `docs/perf/TF199BD-kiem-chung-tuong-duong.json`.

## Lưu ý

- `EXPLAIN ANALYZE` yêu cầu MySQL 8.0.18+.
- Không chạy lệnh này khi chưa `source` đúng `PERF_DATABASE_URL`.
- Không commit file chứa URL/token hay dữ liệu seed.
