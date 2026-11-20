# TF199BD — Sơ đồ minh họa

## Luồng truy vấn trước và sau

```mermaid
flowchart TD
    A[Client gọi tìm xe] --> B[search_public_vehicles]
    B --> C{Điều kiện thời gian}
    C --> D[Subquery booking NOT EXISTS]
    D --> E0[Trước: Materialize + Table scan bookings ~500k dòng]
    D --> E1[Sau: FORCE INDEX end_time -> Covering index range scan]
    E0 --> F[Sort price_per_day, id]
    E1 --> F
    F --> G[COUNT + SELECT cùng filter]
    G --> H[Client nhận kết quả]
```

## Vị trí index trên các bảng liên quan

```mermaid
erDiagram
    BOOKINGS {
        bigint id PK
        bigint vehicle_id FK
        datetime start_time
        datetime end_time
        varchar status
        datetime hold_expires_at
    }
    VEHICLES {
        bigint id PK
        bigint store_id FK
        decimal price_per_day
        boolean is_active
    }
    STORES {
        bigint id PK
        varchar status
    }
    DELIVERY_POINTS {
        bigint id PK
        bigint store_id FK
        varchar area
        boolean is_active
    }
    VEHICLE_RESERVATIONS {
        bigint id PK
        bigint vehicle_id FK
        bigint booking_id FK
        varchar status
        datetime expires_at
        datetime start_time
        datetime end_time
    }
    VEHICLE_SCHEDULES {
        bigint id PK
        bigint vehicle_id FK
        bigint booking_id FK
        varchar status
        datetime start_time
        datetime end_time
    }

    STORES ||--o{ VEHICLES : "store_id"
    STORES ||--o{ DELIVERY_POINTS : "store_id"
    VEHICLES ||--o{ BOOKINGS : "vehicle_id"
    VEHICLES ||--o{ VEHICLE_RESERVATIONS : "vehicle_id"
    VEHICLES ||--o{ VEHICLE_SCHEDULES : "vehicle_id"
    BOOKINGS ||--o| VEHICLE_RESERVATIONS : "booking_id"
    BOOKINGS ||--o| VEHICLE_SCHEDULES : "booking_id"
```

Index mới:

- `BOOKINGS`: `(end_time, start_time, status, vehicle_id, hold_expires_at)` — dùng cho subquery xung đột trực tiếp.
- `DELIVERY_POINTS`: `(store_id, is_active, area)` — dùng cho filter khu vực ở S3.

## Trình tự triển khai an toàn

```mermaid
sequenceDiagram
    participant Dev
    participant PerfDB as ridehub_perf
    participant TestDB as DB test
    participant Repo

    Dev->>PerfDB: seed deterministic + đo baseline
    Dev->>PerfDB: thử index invisible/visible + EXPLAIN
    Dev->>Repo: sửa model, hint, migration, docs
    Dev->>PerfDB: chạy migration + đo sau + verify equivalence
    Dev->>TestDB: fixture tự tạo index nếu bảng cũ
    Dev->>Repo: commit/push/PR develop
```
