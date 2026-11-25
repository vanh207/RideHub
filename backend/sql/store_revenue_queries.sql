USE app_db;
-- 1: tổng hợp doanh thu theo ngày
SELECT 
    s.id AS store_id,
    s.name AS store_name,
    DATE(b.created_at) AS report_date,
    COUNT(b.id) AS total_orders,
    SUM(CASE WHEN b.status IN ('COMPLETED', 'PAID', 'CONFIRMED') THEN 1 ELSE 0 END) AS valid_orders,
    SUM(CASE WHEN b.status = 'CANCELLED' THEN 1 ELSE 0 END) AS cancelled_orders,
    COALESCE(SUM(CASE WHEN b.status IN ('COMPLETED', 'PAID', 'CONFIRMED') THEN b.rental_amount ELSE 0 END), 0) AS rental_revenue,
    COALESCE(SUM(CASE WHEN b.status IN ('COMPLETED', 'PAID', 'CONFIRMED') THEN b.delivery_fee ELSE 0 END), 0) AS delivery_revenue,
    COALESCE(SUM(CASE WHEN b.status IN ('COMPLETED', 'PAID', 'CONFIRMED') THEN (b.rental_amount + b.delivery_fee) ELSE 0 END), 0) AS net_revenue,
    COALESCE(SUM(CASE WHEN b.status IN ('COMPLETED', 'PAID', 'CONFIRMED') THEN b.deposit_amount ELSE 0 END), 0) AS total_deposit_held
FROM stores s
INNER JOIN bookings b ON b.store_id = s.id
GROUP BY s.id, s.name, DATE(b.created_at)
ORDER BY report_date DESC, net_revenue DESC;

-- 2 tổng hợp doanh thu theo tháng
SELECT 
    s.id AS store_id,
    s.name AS store_name,
    DATE_FORMAT(b.created_at, '%Y-%m') AS report_month,
    COUNT(b.id) AS total_orders,
    SUM(CASE WHEN b.status IN ('COMPLETED', 'PAID', 'CONFIRMED') THEN 1 ELSE 0 END) AS valid_orders,
    SUM(CASE WHEN b.status = 'CANCELLED' THEN 1 ELSE 0 END) AS cancelled_orders,
    COALESCE(SUM(CASE WHEN b.status IN ('COMPLETED', 'PAID', 'CONFIRMED') THEN b.rental_amount ELSE 0 END), 0) AS total_rental_revenue,
    COALESCE(SUM(CASE WHEN b.status IN ('COMPLETED', 'PAID', 'CONFIRMED') THEN b.delivery_fee ELSE 0 END), 0) AS total_delivery_revenue,
    COALESCE(SUM(CASE WHEN b.status IN ('COMPLETED', 'PAID', 'CONFIRMED') THEN (b.rental_amount + b.delivery_fee) ELSE 0 END), 0) AS net_revenue,
    ROUND(
        COALESCE(SUM(CASE WHEN b.status IN ('COMPLETED', 'PAID', 'CONFIRMED') THEN (b.rental_amount + b.delivery_fee) ELSE 0 END), 0) 
        / NULLIF(SUM(CASE WHEN b.status IN ('COMPLETED', 'PAID', 'CONFIRMED') THEN 1 ELSE 0 END), 0),
        2
    ) AS avg_revenue_per_order
FROM stores s
INNER JOIN bookings b ON b.store_id = s.id
GROUP BY s.id, s.name, DATE_FORMAT(b.created_at, '%Y-%m')
ORDER BY report_month DESC, net_revenue DESC;

-- 3: xếp hạng doanh thu của 1 cửa hàng trong khoảng tg cụ thể
SELECT 
    s.id AS store_id,
    s.name AS store_name,
    DATE(b.created_at) AS order_date,
    COUNT(b.id) AS total_orders,
    SUM(b.rental_amount) AS rental_revenue,
    SUM(b.delivery_fee) AS delivery_revenue,
    SUM(b.rental_amount + b.delivery_fee) AS net_revenue
FROM stores s
INNER JOIN bookings b ON b.store_id = s.id
WHERE s.id = 1 
  AND b.status IN ('COMPLETED', 'PAID', 'CONFIRMED')
  AND b.created_at >= '2026-11-01 00:00:00' 
  AND b.created_at <= '2026-11-30 23:59:59'
GROUP BY s.id, s.name, DATE(b.created_at)
ORDER BY order_date ASC;


-- 4: cơ cấu doanh thu theo loại xe
SELECT 
    s.id AS store_id,
    s.name AS store_name,
    v.vehicle_type,
    COUNT(b.id) AS total_rentals,
    SUM(b.rental_amount) AS rental_revenue,
    SUM(b.delivery_fee) AS delivery_revenue,
    SUM(b.rental_amount + b.delivery_fee) AS total_revenue
FROM stores s
INNER JOIN bookings b ON b.store_id = s.id
INNER JOIN vehicles v ON b.vehicle_id = v.id
WHERE b.status IN ('COMPLETED', 'PAID', 'CONFIRMED')
GROUP BY s.id, s.name, v.vehicle_type;

-- 5 tối ưu hóa index để tăng tốc
CREATE INDEX ix_bookings_store_status_created 
ON bookings (store_id, status, created_at);