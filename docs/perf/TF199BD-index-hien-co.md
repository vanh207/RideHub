# TF199BD - Index hiện có trên DB perf

- Thời điểm lấy: `2026-11-20T16:46:13`
- Database: `ridehub_perf`

- MySQL `VERSION()`: `8.0.35`
- `@@session.time_zone`: `SYSTEM`

> `EXPLAIN ANALYZE` yêu cầu MySQL 8.0.18+. Phiên bản này đáp ứng.

## `bookings`

### SHOW INDEX

| Key_name | Seq_in_index | Column_name | Non_unique | Index_type |
|---|---:|---|---:|---|
| `PRIMARY` | 1 | `id` | 0 | BTREE |
| `customer_id` | 1 | `customer_id` | 1 | BTREE |
| `store_id` | 1 | `store_id` | 1 | BTREE |
| `delivery_point_id` | 1 | `delivery_point_id` | 1 | BTREE |
| `ix_bookings_id` | 1 | `id` | 1 | BTREE |
| `ix_bookings_vehicle_status_time` | 1 | `vehicle_id` | 1 | BTREE |
| `ix_bookings_vehicle_status_time` | 2 | `status` | 1 | BTREE |
| `ix_bookings_vehicle_status_time` | 3 | `start_time` | 1 | BTREE |
| `ix_bookings_vehicle_status_time` | 4 | `end_time` | 1 | BTREE |
| `ix_bookings_vehicle_time` | 1 | `vehicle_id` | 1 | BTREE |
| `ix_bookings_vehicle_time` | 2 | `start_time` | 1 | BTREE |
| `ix_bookings_vehicle_time` | 3 | `end_time` | 1 | BTREE |
| `ix_bookings_status_hold_expires` | 1 | `status` | 1 | BTREE |
| `ix_bookings_status_hold_expires` | 2 | `hold_expires_at` | 1 | BTREE |
| `ix_bookings_end_start_status_vehicle_hold` | 1 | `end_time` | 1 | BTREE |
| `ix_bookings_end_start_status_vehicle_hold` | 2 | `start_time` | 1 | BTREE |
| `ix_bookings_end_start_status_vehicle_hold` | 3 | `status` | 1 | BTREE |
| `ix_bookings_end_start_status_vehicle_hold` | 4 | `vehicle_id` | 1 | BTREE |
| `ix_bookings_end_start_status_vehicle_hold` | 5 | `hold_expires_at` | 1 | BTREE |

### SHOW CREATE TABLE

```sql
bookings
```

## `vehicle_reservations`

### SHOW INDEX

| Key_name | Seq_in_index | Column_name | Non_unique | Index_type |
|---|---:|---|---:|---|
| `PRIMARY` | 1 | `id` | 0 | BTREE |
| `customer_id` | 1 | `customer_id` | 1 | BTREE |
| `booking_id` | 1 | `booking_id` | 1 | BTREE |
| `ix_reservations_status_expiry` | 1 | `status` | 1 | BTREE |
| `ix_reservations_status_expiry` | 2 | `expires_at` | 1 | BTREE |
| `ix_reservations_vehicle_status_expiry` | 1 | `vehicle_id` | 1 | BTREE |
| `ix_reservations_vehicle_status_expiry` | 2 | `status` | 1 | BTREE |
| `ix_reservations_vehicle_status_expiry` | 3 | `expires_at` | 1 | BTREE |
| `ix_reservations_vehicle_time` | 1 | `vehicle_id` | 1 | BTREE |
| `ix_reservations_vehicle_time` | 2 | `start_time` | 1 | BTREE |
| `ix_reservations_vehicle_time` | 3 | `end_time` | 1 | BTREE |
| `ix_vehicle_reservations_id` | 1 | `id` | 1 | BTREE |

### SHOW CREATE TABLE

```sql
vehicle_reservations
```

## `vehicle_schedules`

### SHOW INDEX

| Key_name | Seq_in_index | Column_name | Non_unique | Index_type |
|---|---:|---|---:|---|
| `PRIMARY` | 1 | `id` | 0 | BTREE |
| `booking_id` | 1 | `booking_id` | 1 | BTREE |
| `reservation_id` | 1 | `reservation_id` | 1 | BTREE |
| `ix_vehicle_schedules_id` | 1 | `id` | 1 | BTREE |
| `ix_schedules_vehicle_status_time` | 1 | `vehicle_id` | 1 | BTREE |
| `ix_schedules_vehicle_status_time` | 2 | `status` | 1 | BTREE |
| `ix_schedules_vehicle_status_time` | 3 | `start_time` | 1 | BTREE |
| `ix_schedules_vehicle_status_time` | 4 | `end_time` | 1 | BTREE |
| `ix_schedules_vehicle_time` | 1 | `vehicle_id` | 1 | BTREE |
| `ix_schedules_vehicle_time` | 2 | `start_time` | 1 | BTREE |
| `ix_schedules_vehicle_time` | 3 | `end_time` | 1 | BTREE |

### SHOW CREATE TABLE

```sql
vehicle_schedules
```

## `vehicles`

### SHOW INDEX

| Key_name | Seq_in_index | Column_name | Non_unique | Index_type |
|---|---:|---|---:|---|
| `PRIMARY` | 1 | `id` | 0 | BTREE |
| `uq_vehicle_store_plate` | 1 | `store_id` | 0 | BTREE |
| `uq_vehicle_store_plate` | 2 | `plate_number` | 0 | BTREE |
| `ix_vehicles_id` | 1 | `id` | 1 | BTREE |

### SHOW CREATE TABLE

```sql
vehicles
```

## `stores`

### SHOW INDEX

| Key_name | Seq_in_index | Column_name | Non_unique | Index_type |
|---|---:|---|---:|---|
| `PRIMARY` | 1 | `id` | 0 | BTREE |
| `uq_stores_business_license_number` | 1 | `business_license` | 0 | BTREE |
| `uq_stores_name` | 1 | `name` | 0 | BTREE |
| `uq_stores_email` | 1 | `email` | 0 | BTREE |
| `ix_stores_owner_id_status` | 1 | `owner_user_id` | 1 | BTREE |
| `ix_stores_owner_id_status` | 2 | `status` | 1 | BTREE |
| `ix_stores_id` | 1 | `id` | 1 | BTREE |
| `ix_stores_status` | 1 | `status` | 1 | BTREE |

### SHOW CREATE TABLE

```sql
stores
```

## `delivery_points`

### SHOW INDEX

| Key_name | Seq_in_index | Column_name | Non_unique | Index_type |
|---|---:|---|---:|---|
| `PRIMARY` | 1 | `id` | 0 | BTREE |
| `delivery_fee_zone_id` | 1 | `delivery_fee_zone_id` | 1 | BTREE |
| `ix_delivery_points_id` | 1 | `id` | 1 | BTREE |
| `ix_delivery_points_store_active_area` | 1 | `store_id` | 1 | BTREE |
| `ix_delivery_points_store_active_area` | 2 | `is_active` | 1 | BTREE |
| `ix_delivery_points_store_active_area` | 3 | `area` | 1 | BTREE |

### SHOW CREATE TABLE

```sql
delivery_points
```

