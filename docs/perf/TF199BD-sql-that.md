# TF199BD - SQL thật do ORM sinh ra

SQL dưới đây được biên dịch từ chính các statement trong `app.crud.vehicle` 
bằng `literal_binds=True` và dialect MySQL. Đây là câu lệnh dùng để đo, 
không phải SQL viết tay để tối ưu.

## S1 - 2 ngày ở tương lai xa, đa số xe trống

- Thời gian: `2027-03-10 08:00:00` -> `2027-03-12 08:00:00`
- Khu vực: `None`; loại xe: `None`; giá: `None` -> `None`
- Sắp xếp: `price_asc`; trang: `1`; kích thước trang: `12`

### COUNT

```sql
SELECT count(vehicles.id) AS count_1 
FROM vehicles INNER JOIN stores ON stores.id = vehicles.store_id 
WHERE vehicles.is_active IS true AND vehicles.price_per_day IS NOT NULL AND upper(trim(stores.status)) = 'APPROVED' AND NOT (EXISTS (SELECT bookings.id 
FROM bookings FORCE INDEX (ix_bookings_end_start_status_vehicle_hold) 
WHERE bookings.vehicle_id = vehicles.id AND bookings.status IN ('BOOKED', 'CONFIRMED', 'DEPOSIT_PAID', 'IN_PROGRESS', 'PENDING', 'PENDING_PAYMENT', 'PENDING_SETTLEMENT', 'PENDING_STORE_CONFIRM') AND bookings.start_time < '2027-03-12 09:00:00' AND bookings.end_time > '2027-03-10 07:00:00' AND ((bookings.status NOT IN ('PENDING_PAYMENT', 'PENDING')) OR bookings.hold_expires_at IS NULL OR bookings.hold_expires_at > '2026-11-20 08:00:00'))) AND NOT (EXISTS (SELECT vehicle_reservations.id 
FROM vehicle_reservations 
WHERE vehicle_reservations.vehicle_id = vehicles.id AND vehicle_reservations.status = 'ACTIVE' AND vehicle_reservations.expires_at > '2026-11-20 08:00:00' AND vehicle_reservations.start_time < '2027-03-12 09:00:00' AND vehicle_reservations.end_time > '2027-03-10 07:00:00' AND NOT (EXISTS (SELECT bookings.id 
FROM bookings 
WHERE bookings.id = vehicle_reservations.booking_id AND bookings.status IN ('PENDING_PAYMENT', 'PENDING') AND bookings.hold_expires_at IS NOT NULL AND bookings.hold_expires_at <= '2026-11-20 08:00:00')))) AND NOT (EXISTS (SELECT vehicle_schedules.id 
FROM vehicle_schedules 
WHERE vehicle_schedules.vehicle_id = vehicles.id AND vehicle_schedules.status = 'ACTIVE' AND vehicle_schedules.start_time < '2027-03-12 09:00:00' AND vehicle_schedules.end_time > '2027-03-10 07:00:00' AND NOT (EXISTS (SELECT bookings.id 
FROM bookings 
WHERE bookings.id = vehicle_schedules.booking_id AND bookings.status IN ('PENDING_PAYMENT', 'PENDING') AND bookings.hold_expires_at IS NOT NULL AND bookings.hold_expires_at <= '2026-11-20 08:00:00'))));
```

### SELECT

```sql
SELECT vehicles.id AS id, stores.id AS store_id, stores.name AS store_name, stores.city AS store_city, vehicles.vehicle_type, vehicles.brand, vehicles.model, vehicles.seats, vehicles.transmission_type, vehicles.fuel_type, vehicles.price_per_day, vehicles.price_per_hour 
FROM vehicles INNER JOIN stores ON stores.id = vehicles.store_id 
WHERE vehicles.is_active IS true AND vehicles.price_per_day IS NOT NULL AND upper(trim(stores.status)) = 'APPROVED' AND NOT (EXISTS (SELECT bookings.id 
FROM bookings FORCE INDEX (ix_bookings_end_start_status_vehicle_hold) 
WHERE bookings.vehicle_id = vehicles.id AND bookings.status IN ('BOOKED', 'CONFIRMED', 'DEPOSIT_PAID', 'IN_PROGRESS', 'PENDING', 'PENDING_PAYMENT', 'PENDING_SETTLEMENT', 'PENDING_STORE_CONFIRM') AND bookings.start_time < '2027-03-12 09:00:00' AND bookings.end_time > '2027-03-10 07:00:00' AND ((bookings.status NOT IN ('PENDING_PAYMENT', 'PENDING')) OR bookings.hold_expires_at IS NULL OR bookings.hold_expires_at > '2026-11-20 08:00:00'))) AND NOT (EXISTS (SELECT vehicle_reservations.id 
FROM vehicle_reservations 
WHERE vehicle_reservations.vehicle_id = vehicles.id AND vehicle_reservations.status = 'ACTIVE' AND vehicle_reservations.expires_at > '2026-11-20 08:00:00' AND vehicle_reservations.start_time < '2027-03-12 09:00:00' AND vehicle_reservations.end_time > '2027-03-10 07:00:00' AND NOT (EXISTS (SELECT bookings.id 
FROM bookings 
WHERE bookings.id = vehicle_reservations.booking_id AND bookings.status IN ('PENDING_PAYMENT', 'PENDING') AND bookings.hold_expires_at IS NOT NULL AND bookings.hold_expires_at <= '2026-11-20 08:00:00')))) AND NOT (EXISTS (SELECT vehicle_schedules.id 
FROM vehicle_schedules 
WHERE vehicle_schedules.vehicle_id = vehicles.id AND vehicle_schedules.status = 'ACTIVE' AND vehicle_schedules.start_time < '2027-03-12 09:00:00' AND vehicle_schedules.end_time > '2027-03-10 07:00:00' AND NOT (EXISTS (SELECT bookings.id 
FROM bookings 
WHERE bookings.id = vehicle_schedules.booking_id AND bookings.status IN ('PENDING_PAYMENT', 'PENDING') AND bookings.hold_expires_at IS NOT NULL AND bookings.hold_expires_at <= '2026-11-20 08:00:00')))) ORDER BY vehicles.price_per_day ASC, vehicles.id ASC 
 LIMIT 0, 12;
```

## S2 - 2 ngày trùng cao điểm many bookings, đa số xe bận

- Thời gian: `2026-12-20 08:00:00` -> `2026-12-22 08:00:00`
- Khu vực: `None`; loại xe: `None`; giá: `None` -> `None`
- Sắp xếp: `price_asc`; trang: `1`; kích thước trang: `12`

### COUNT

```sql
SELECT count(vehicles.id) AS count_1 
FROM vehicles INNER JOIN stores ON stores.id = vehicles.store_id 
WHERE vehicles.is_active IS true AND vehicles.price_per_day IS NOT NULL AND upper(trim(stores.status)) = 'APPROVED' AND NOT (EXISTS (SELECT bookings.id 
FROM bookings FORCE INDEX (ix_bookings_end_start_status_vehicle_hold) 
WHERE bookings.vehicle_id = vehicles.id AND bookings.status IN ('BOOKED', 'CONFIRMED', 'DEPOSIT_PAID', 'IN_PROGRESS', 'PENDING', 'PENDING_PAYMENT', 'PENDING_SETTLEMENT', 'PENDING_STORE_CONFIRM') AND bookings.start_time < '2026-12-22 09:00:00' AND bookings.end_time > '2026-12-20 07:00:00' AND ((bookings.status NOT IN ('PENDING_PAYMENT', 'PENDING')) OR bookings.hold_expires_at IS NULL OR bookings.hold_expires_at > '2026-11-20 08:00:00'))) AND NOT (EXISTS (SELECT vehicle_reservations.id 
FROM vehicle_reservations 
WHERE vehicle_reservations.vehicle_id = vehicles.id AND vehicle_reservations.status = 'ACTIVE' AND vehicle_reservations.expires_at > '2026-11-20 08:00:00' AND vehicle_reservations.start_time < '2026-12-22 09:00:00' AND vehicle_reservations.end_time > '2026-12-20 07:00:00' AND NOT (EXISTS (SELECT bookings.id 
FROM bookings 
WHERE bookings.id = vehicle_reservations.booking_id AND bookings.status IN ('PENDING_PAYMENT', 'PENDING') AND bookings.hold_expires_at IS NOT NULL AND bookings.hold_expires_at <= '2026-11-20 08:00:00')))) AND NOT (EXISTS (SELECT vehicle_schedules.id 
FROM vehicle_schedules 
WHERE vehicle_schedules.vehicle_id = vehicles.id AND vehicle_schedules.status = 'ACTIVE' AND vehicle_schedules.start_time < '2026-12-22 09:00:00' AND vehicle_schedules.end_time > '2026-12-20 07:00:00' AND NOT (EXISTS (SELECT bookings.id 
FROM bookings 
WHERE bookings.id = vehicle_schedules.booking_id AND bookings.status IN ('PENDING_PAYMENT', 'PENDING') AND bookings.hold_expires_at IS NOT NULL AND bookings.hold_expires_at <= '2026-11-20 08:00:00'))));
```

### SELECT

```sql
SELECT vehicles.id AS id, stores.id AS store_id, stores.name AS store_name, stores.city AS store_city, vehicles.vehicle_type, vehicles.brand, vehicles.model, vehicles.seats, vehicles.transmission_type, vehicles.fuel_type, vehicles.price_per_day, vehicles.price_per_hour 
FROM vehicles INNER JOIN stores ON stores.id = vehicles.store_id 
WHERE vehicles.is_active IS true AND vehicles.price_per_day IS NOT NULL AND upper(trim(stores.status)) = 'APPROVED' AND NOT (EXISTS (SELECT bookings.id 
FROM bookings FORCE INDEX (ix_bookings_end_start_status_vehicle_hold) 
WHERE bookings.vehicle_id = vehicles.id AND bookings.status IN ('BOOKED', 'CONFIRMED', 'DEPOSIT_PAID', 'IN_PROGRESS', 'PENDING', 'PENDING_PAYMENT', 'PENDING_SETTLEMENT', 'PENDING_STORE_CONFIRM') AND bookings.start_time < '2026-12-22 09:00:00' AND bookings.end_time > '2026-12-20 07:00:00' AND ((bookings.status NOT IN ('PENDING_PAYMENT', 'PENDING')) OR bookings.hold_expires_at IS NULL OR bookings.hold_expires_at > '2026-11-20 08:00:00'))) AND NOT (EXISTS (SELECT vehicle_reservations.id 
FROM vehicle_reservations 
WHERE vehicle_reservations.vehicle_id = vehicles.id AND vehicle_reservations.status = 'ACTIVE' AND vehicle_reservations.expires_at > '2026-11-20 08:00:00' AND vehicle_reservations.start_time < '2026-12-22 09:00:00' AND vehicle_reservations.end_time > '2026-12-20 07:00:00' AND NOT (EXISTS (SELECT bookings.id 
FROM bookings 
WHERE bookings.id = vehicle_reservations.booking_id AND bookings.status IN ('PENDING_PAYMENT', 'PENDING') AND bookings.hold_expires_at IS NOT NULL AND bookings.hold_expires_at <= '2026-11-20 08:00:00')))) AND NOT (EXISTS (SELECT vehicle_schedules.id 
FROM vehicle_schedules 
WHERE vehicle_schedules.vehicle_id = vehicles.id AND vehicle_schedules.status = 'ACTIVE' AND vehicle_schedules.start_time < '2026-12-22 09:00:00' AND vehicle_schedules.end_time > '2026-12-20 07:00:00' AND NOT (EXISTS (SELECT bookings.id 
FROM bookings 
WHERE bookings.id = vehicle_schedules.booking_id AND bookings.status IN ('PENDING_PAYMENT', 'PENDING') AND bookings.hold_expires_at IS NOT NULL AND bookings.hold_expires_at <= '2026-11-20 08:00:00')))) ORDER BY vehicles.price_per_day ASC, vehicles.id ASC 
 LIMIT 0, 12;
```

## S3 - S1 + khu vực + loại xe + khoảng giá

- Thời gian: `2027-03-10 08:00:00` -> `2027-03-12 08:00:00`
- Khu vực: `Hoan Kiem`; loại xe: `MOTORBIKE`; giá: `200000` -> `600000`
- Sắp xếp: `price_asc`; trang: `1`; kích thước trang: `12`

### COUNT

```sql
SELECT count(vehicles.id) AS count_1 
FROM vehicles INNER JOIN stores ON stores.id = vehicles.store_id 
WHERE vehicles.is_active IS true AND vehicles.price_per_day IS NOT NULL AND upper(trim(stores.status)) = 'APPROVED' AND (lower(stores.city) LIKE '%hoan kiem%' ESCAPE '\\' OR (EXISTS (SELECT delivery_points.id 
FROM delivery_points 
WHERE delivery_points.store_id = stores.id AND delivery_points.is_active IS true AND lower(delivery_points.area) LIKE '%hoan kiem%' ESCAPE '\\'))) AND upper(trim(vehicles.vehicle_type)) = 'MOTORBIKE' AND vehicles.price_per_day >= 200000 AND vehicles.price_per_day <= 600000 AND NOT (EXISTS (SELECT bookings.id 
FROM bookings FORCE INDEX (ix_bookings_end_start_status_vehicle_hold) 
WHERE bookings.vehicle_id = vehicles.id AND bookings.status IN ('BOOKED', 'CONFIRMED', 'DEPOSIT_PAID', 'IN_PROGRESS', 'PENDING', 'PENDING_PAYMENT', 'PENDING_SETTLEMENT', 'PENDING_STORE_CONFIRM') AND bookings.start_time < '2027-03-12 09:00:00' AND bookings.end_time > '2027-03-10 07:00:00' AND ((bookings.status NOT IN ('PENDING_PAYMENT', 'PENDING')) OR bookings.hold_expires_at IS NULL OR bookings.hold_expires_at > '2026-11-20 08:00:00'))) AND NOT (EXISTS (SELECT vehicle_reservations.id 
FROM vehicle_reservations 
WHERE vehicle_reservations.vehicle_id = vehicles.id AND vehicle_reservations.status = 'ACTIVE' AND vehicle_reservations.expires_at > '2026-11-20 08:00:00' AND vehicle_reservations.start_time < '2027-03-12 09:00:00' AND vehicle_reservations.end_time > '2027-03-10 07:00:00' AND NOT (EXISTS (SELECT bookings.id 
FROM bookings 
WHERE bookings.id = vehicle_reservations.booking_id AND bookings.status IN ('PENDING_PAYMENT', 'PENDING') AND bookings.hold_expires_at IS NOT NULL AND bookings.hold_expires_at <= '2026-11-20 08:00:00')))) AND NOT (EXISTS (SELECT vehicle_schedules.id 
FROM vehicle_schedules 
WHERE vehicle_schedules.vehicle_id = vehicles.id AND vehicle_schedules.status = 'ACTIVE' AND vehicle_schedules.start_time < '2027-03-12 09:00:00' AND vehicle_schedules.end_time > '2027-03-10 07:00:00' AND NOT (EXISTS (SELECT bookings.id 
FROM bookings 
WHERE bookings.id = vehicle_schedules.booking_id AND bookings.status IN ('PENDING_PAYMENT', 'PENDING') AND bookings.hold_expires_at IS NOT NULL AND bookings.hold_expires_at <= '2026-11-20 08:00:00'))));
```

### SELECT

```sql
SELECT vehicles.id AS id, stores.id AS store_id, stores.name AS store_name, stores.city AS store_city, vehicles.vehicle_type, vehicles.brand, vehicles.model, vehicles.seats, vehicles.transmission_type, vehicles.fuel_type, vehicles.price_per_day, vehicles.price_per_hour 
FROM vehicles INNER JOIN stores ON stores.id = vehicles.store_id 
WHERE vehicles.is_active IS true AND vehicles.price_per_day IS NOT NULL AND upper(trim(stores.status)) = 'APPROVED' AND (lower(stores.city) LIKE '%hoan kiem%' ESCAPE '\\' OR (EXISTS (SELECT delivery_points.id 
FROM delivery_points 
WHERE delivery_points.store_id = stores.id AND delivery_points.is_active IS true AND lower(delivery_points.area) LIKE '%hoan kiem%' ESCAPE '\\'))) AND upper(trim(vehicles.vehicle_type)) = 'MOTORBIKE' AND vehicles.price_per_day >= 200000 AND vehicles.price_per_day <= 600000 AND NOT (EXISTS (SELECT bookings.id 
FROM bookings FORCE INDEX (ix_bookings_end_start_status_vehicle_hold) 
WHERE bookings.vehicle_id = vehicles.id AND bookings.status IN ('BOOKED', 'CONFIRMED', 'DEPOSIT_PAID', 'IN_PROGRESS', 'PENDING', 'PENDING_PAYMENT', 'PENDING_SETTLEMENT', 'PENDING_STORE_CONFIRM') AND bookings.start_time < '2027-03-12 09:00:00' AND bookings.end_time > '2027-03-10 07:00:00' AND ((bookings.status NOT IN ('PENDING_PAYMENT', 'PENDING')) OR bookings.hold_expires_at IS NULL OR bookings.hold_expires_at > '2026-11-20 08:00:00'))) AND NOT (EXISTS (SELECT vehicle_reservations.id 
FROM vehicle_reservations 
WHERE vehicle_reservations.vehicle_id = vehicles.id AND vehicle_reservations.status = 'ACTIVE' AND vehicle_reservations.expires_at > '2026-11-20 08:00:00' AND vehicle_reservations.start_time < '2027-03-12 09:00:00' AND vehicle_reservations.end_time > '2027-03-10 07:00:00' AND NOT (EXISTS (SELECT bookings.id 
FROM bookings 
WHERE bookings.id = vehicle_reservations.booking_id AND bookings.status IN ('PENDING_PAYMENT', 'PENDING') AND bookings.hold_expires_at IS NOT NULL AND bookings.hold_expires_at <= '2026-11-20 08:00:00')))) AND NOT (EXISTS (SELECT vehicle_schedules.id 
FROM vehicle_schedules 
WHERE vehicle_schedules.vehicle_id = vehicles.id AND vehicle_schedules.status = 'ACTIVE' AND vehicle_schedules.start_time < '2027-03-12 09:00:00' AND vehicle_schedules.end_time > '2027-03-10 07:00:00' AND NOT (EXISTS (SELECT bookings.id 
FROM bookings 
WHERE bookings.id = vehicle_schedules.booking_id AND bookings.status IN ('PENDING_PAYMENT', 'PENDING') AND bookings.hold_expires_at IS NOT NULL AND bookings.hold_expires_at <= '2026-11-20 08:00:00')))) ORDER BY vehicles.price_per_day ASC, vehicles.id ASC 
 LIMIT 0, 12;
```

## S4 - Trang cuối offset lớn + COUNT

- Thời gian: `2027-03-10 08:00:00` -> `2027-03-12 08:00:00`
- Khu vực: `None`; loại xe: `None`; giá: `None` -> `None`
- Sắp xếp: `price_asc`; trang: `300`; kích thước trang: `12`

### COUNT

```sql
SELECT count(vehicles.id) AS count_1 
FROM vehicles INNER JOIN stores ON stores.id = vehicles.store_id 
WHERE vehicles.is_active IS true AND vehicles.price_per_day IS NOT NULL AND upper(trim(stores.status)) = 'APPROVED' AND NOT (EXISTS (SELECT bookings.id 
FROM bookings FORCE INDEX (ix_bookings_end_start_status_vehicle_hold) 
WHERE bookings.vehicle_id = vehicles.id AND bookings.status IN ('BOOKED', 'CONFIRMED', 'DEPOSIT_PAID', 'IN_PROGRESS', 'PENDING', 'PENDING_PAYMENT', 'PENDING_SETTLEMENT', 'PENDING_STORE_CONFIRM') AND bookings.start_time < '2027-03-12 09:00:00' AND bookings.end_time > '2027-03-10 07:00:00' AND ((bookings.status NOT IN ('PENDING_PAYMENT', 'PENDING')) OR bookings.hold_expires_at IS NULL OR bookings.hold_expires_at > '2026-11-20 08:00:00'))) AND NOT (EXISTS (SELECT vehicle_reservations.id 
FROM vehicle_reservations 
WHERE vehicle_reservations.vehicle_id = vehicles.id AND vehicle_reservations.status = 'ACTIVE' AND vehicle_reservations.expires_at > '2026-11-20 08:00:00' AND vehicle_reservations.start_time < '2027-03-12 09:00:00' AND vehicle_reservations.end_time > '2027-03-10 07:00:00' AND NOT (EXISTS (SELECT bookings.id 
FROM bookings 
WHERE bookings.id = vehicle_reservations.booking_id AND bookings.status IN ('PENDING_PAYMENT', 'PENDING') AND bookings.hold_expires_at IS NOT NULL AND bookings.hold_expires_at <= '2026-11-20 08:00:00')))) AND NOT (EXISTS (SELECT vehicle_schedules.id 
FROM vehicle_schedules 
WHERE vehicle_schedules.vehicle_id = vehicles.id AND vehicle_schedules.status = 'ACTIVE' AND vehicle_schedules.start_time < '2027-03-12 09:00:00' AND vehicle_schedules.end_time > '2027-03-10 07:00:00' AND NOT (EXISTS (SELECT bookings.id 
FROM bookings 
WHERE bookings.id = vehicle_schedules.booking_id AND bookings.status IN ('PENDING_PAYMENT', 'PENDING') AND bookings.hold_expires_at IS NOT NULL AND bookings.hold_expires_at <= '2026-11-20 08:00:00'))));
```

### SELECT

```sql
SELECT vehicles.id AS id, stores.id AS store_id, stores.name AS store_name, stores.city AS store_city, vehicles.vehicle_type, vehicles.brand, vehicles.model, vehicles.seats, vehicles.transmission_type, vehicles.fuel_type, vehicles.price_per_day, vehicles.price_per_hour 
FROM vehicles INNER JOIN stores ON stores.id = vehicles.store_id 
WHERE vehicles.is_active IS true AND vehicles.price_per_day IS NOT NULL AND upper(trim(stores.status)) = 'APPROVED' AND NOT (EXISTS (SELECT bookings.id 
FROM bookings FORCE INDEX (ix_bookings_end_start_status_vehicle_hold) 
WHERE bookings.vehicle_id = vehicles.id AND bookings.status IN ('BOOKED', 'CONFIRMED', 'DEPOSIT_PAID', 'IN_PROGRESS', 'PENDING', 'PENDING_PAYMENT', 'PENDING_SETTLEMENT', 'PENDING_STORE_CONFIRM') AND bookings.start_time < '2027-03-12 09:00:00' AND bookings.end_time > '2027-03-10 07:00:00' AND ((bookings.status NOT IN ('PENDING_PAYMENT', 'PENDING')) OR bookings.hold_expires_at IS NULL OR bookings.hold_expires_at > '2026-11-20 08:00:00'))) AND NOT (EXISTS (SELECT vehicle_reservations.id 
FROM vehicle_reservations 
WHERE vehicle_reservations.vehicle_id = vehicles.id AND vehicle_reservations.status = 'ACTIVE' AND vehicle_reservations.expires_at > '2026-11-20 08:00:00' AND vehicle_reservations.start_time < '2027-03-12 09:00:00' AND vehicle_reservations.end_time > '2027-03-10 07:00:00' AND NOT (EXISTS (SELECT bookings.id 
FROM bookings 
WHERE bookings.id = vehicle_reservations.booking_id AND bookings.status IN ('PENDING_PAYMENT', 'PENDING') AND bookings.hold_expires_at IS NOT NULL AND bookings.hold_expires_at <= '2026-11-20 08:00:00')))) AND NOT (EXISTS (SELECT vehicle_schedules.id 
FROM vehicle_schedules 
WHERE vehicle_schedules.vehicle_id = vehicles.id AND vehicle_schedules.status = 'ACTIVE' AND vehicle_schedules.start_time < '2027-03-12 09:00:00' AND vehicle_schedules.end_time > '2027-03-10 07:00:00' AND NOT (EXISTS (SELECT bookings.id 
FROM bookings 
WHERE bookings.id = vehicle_schedules.booking_id AND bookings.status IN ('PENDING_PAYMENT', 'PENDING') AND bookings.hold_expires_at IS NOT NULL AND bookings.hold_expires_at <= '2026-11-20 08:00:00')))) ORDER BY vehicles.price_per_day ASC, vehicles.id ASC 
 LIMIT 3588, 12;
```

## S5_NORMAL - Kiểm tra trùng lịch cho xe thường

- Xe: `3456`; thời gian: `2026-12-20 08:00:00` -> `2026-12-22 08:00:00`

### SELECT

```sql
SELECT vehicles.id 
FROM vehicles 
WHERE vehicles.id = 3456 AND NOT (EXISTS (SELECT bookings.id 
FROM bookings FORCE INDEX (ix_bookings_end_start_status_vehicle_hold) 
WHERE bookings.vehicle_id = vehicles.id AND bookings.status IN ('BOOKED', 'CONFIRMED', 'DEPOSIT_PAID', 'IN_PROGRESS', 'PENDING', 'PENDING_PAYMENT', 'PENDING_SETTLEMENT', 'PENDING_STORE_CONFIRM') AND bookings.start_time < '2026-12-22 09:00:00' AND bookings.end_time > '2026-12-20 07:00:00' AND ((bookings.status NOT IN ('PENDING_PAYMENT', 'PENDING')) OR bookings.hold_expires_at IS NULL OR bookings.hold_expires_at > '2026-11-20 08:00:00'))) AND NOT (EXISTS (SELECT vehicle_reservations.id 
FROM vehicle_reservations 
WHERE vehicle_reservations.vehicle_id = vehicles.id AND vehicle_reservations.status = 'ACTIVE' AND vehicle_reservations.expires_at > '2026-11-20 08:00:00' AND vehicle_reservations.start_time < '2026-12-22 09:00:00' AND vehicle_reservations.end_time > '2026-12-20 07:00:00' AND NOT (EXISTS (SELECT bookings.id 
FROM bookings 
WHERE bookings.id = vehicle_reservations.booking_id AND bookings.status IN ('PENDING_PAYMENT', 'PENDING') AND bookings.hold_expires_at IS NOT NULL AND bookings.hold_expires_at <= '2026-11-20 08:00:00')))) AND NOT (EXISTS (SELECT vehicle_schedules.id 
FROM vehicle_schedules 
WHERE vehicle_schedules.vehicle_id = vehicles.id AND vehicle_schedules.status = 'ACTIVE' AND vehicle_schedules.start_time < '2026-12-22 09:00:00' AND vehicle_schedules.end_time > '2026-12-20 07:00:00' AND NOT (EXISTS (SELECT bookings.id 
FROM bookings 
WHERE bookings.id = vehicle_schedules.booking_id AND bookings.status IN ('PENDING_PAYMENT', 'PENDING') AND bookings.hold_expires_at IS NOT NULL AND bookings.hold_expires_at <= '2026-11-20 08:00:00'))));
```

## S5_HOT - Kiểm tra trùng lịch cho xe nóng

- Xe: `17`; thời gian: `2026-12-20 08:00:00` -> `2026-12-22 08:00:00`

### SELECT

```sql
SELECT vehicles.id 
FROM vehicles 
WHERE vehicles.id = 17 AND NOT (EXISTS (SELECT bookings.id 
FROM bookings FORCE INDEX (ix_bookings_end_start_status_vehicle_hold) 
WHERE bookings.vehicle_id = vehicles.id AND bookings.status IN ('BOOKED', 'CONFIRMED', 'DEPOSIT_PAID', 'IN_PROGRESS', 'PENDING', 'PENDING_PAYMENT', 'PENDING_SETTLEMENT', 'PENDING_STORE_CONFIRM') AND bookings.start_time < '2026-12-22 09:00:00' AND bookings.end_time > '2026-12-20 07:00:00' AND ((bookings.status NOT IN ('PENDING_PAYMENT', 'PENDING')) OR bookings.hold_expires_at IS NULL OR bookings.hold_expires_at > '2026-11-20 08:00:00'))) AND NOT (EXISTS (SELECT vehicle_reservations.id 
FROM vehicle_reservations 
WHERE vehicle_reservations.vehicle_id = vehicles.id AND vehicle_reservations.status = 'ACTIVE' AND vehicle_reservations.expires_at > '2026-11-20 08:00:00' AND vehicle_reservations.start_time < '2026-12-22 09:00:00' AND vehicle_reservations.end_time > '2026-12-20 07:00:00' AND NOT (EXISTS (SELECT bookings.id 
FROM bookings 
WHERE bookings.id = vehicle_reservations.booking_id AND bookings.status IN ('PENDING_PAYMENT', 'PENDING') AND bookings.hold_expires_at IS NOT NULL AND bookings.hold_expires_at <= '2026-11-20 08:00:00')))) AND NOT (EXISTS (SELECT vehicle_schedules.id 
FROM vehicle_schedules 
WHERE vehicle_schedules.vehicle_id = vehicles.id AND vehicle_schedules.status = 'ACTIVE' AND vehicle_schedules.start_time < '2026-12-22 09:00:00' AND vehicle_schedules.end_time > '2026-12-20 07:00:00' AND NOT (EXISTS (SELECT bookings.id 
FROM bookings 
WHERE bookings.id = vehicle_schedules.booking_id AND bookings.status IN ('PENDING_PAYMENT', 'PENDING') AND bookings.hold_expires_at IS NOT NULL AND bookings.hold_expires_at <= '2026-11-20 08:00:00'))));
```

