"""Sinh dữ liệu lớn cho TF199BD trên DB riêng (tên chứa perf/test)."""
from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import text

from db_guard import assert_safe_database, db_name_from_url, get_perf_url, make_perf_engine
from scenarios import ANCHOR, BUSY_END, BUSY_START
from app.models.booking import Booking
from app.models.delivery import DeliveryPoint
from app.models.role import Role, UserRole
from app.models.store import Store
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.vehicle_reservation import VehicleReservation
from app.models.vehicle_schedule import VehicleSchedule

BLOCKING_STATUSES = (
    "BOOKED",
    "CONFIRMED",
    "DEPOSIT_PAID",
    "IN_PROGRESS",
    "PENDING",
    "PENDING_PAYMENT",
    "PENDING_SETTLEMENT",
    "PENDING_STORE_CONFIRM",
)
EXPIRABLE = ("PENDING_PAYMENT", "PENDING")
CITIES = ("Ha Noi", "Ho Chi Minh", "Da Nang", "Can Tho", "Hai Phong")
AREAS = ("Hoan Kiem", "District 1", "Hai Chau", "Ninh Kieu", "Ngo Quyen")
RESET_TABLES = (
    "booking_status_history",
    "vehicle_schedules",
    "vehicle_reservations",
    "bookings",
    "vehicle_images",
    "vehicle_status_history",
    "vehicles",
    "delivery_points",
    "stores",
    "user_roles",
    "users",
    "roles",
)
BATCH_SIZE = 5000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scale", type=float, default=1.0, help="Hệ số quy mô, mặc định 1.0")
    parser.add_argument("--seed", type=int, default=20261120, help="Hạt giống cố định")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Xóa dữ liệu cũ trong DB perf/test trước khi sinh (bắt buộc để chạy lại)",
    )
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    return parser.parse_args()


def bulk_insert(engine, table, rows, batch_size: int) -> None:
    """Chèn theo lô, mỗi lô một transaction ngắn để không giữ undo log quá lớn."""
    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        with engine.begin() as conn:
            conn.execute(table.insert(), batch)


def reset_data(engine) -> None:
    """Chỉ chạy sau khi đã chốt DB; tắt FK tạm thời để truncate nhanh."""
    with engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        try:
            for table in RESET_TABLES:
                conn.execute(text(f"TRUNCATE TABLE `{table}`"))
        finally:
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))


def random_start(rng: random.Random, busy_probability: float) -> datetime:
    """Phân bổ thời gian: một phần dồn vào cao điểm, phần còn lại rải 12 tháng."""
    if rng.random() < busy_probability:
        return BUSY_START - timedelta(hours=rng.randint(0, 23)) + timedelta(
            minutes=rng.randint(0, 72 * 60)
        )
    return ANCHOR - timedelta(days=365) + timedelta(days=rng.randint(0, 455))


def make_bookings(rng: random.Random, count: int, vehicle_count: int, vehicle_store):
    """Trả về rows booking và các pool booking_id theo trạng thái hold."""
    hot_count = min(20, vehicle_count)
    statuses = BLOCKING_STATUSES + ("COMPLETED", "CANCELLED")
    weights = [2.25] * len(BLOCKING_STATUSES) + [55.0, 27.0]

    rows = []
    expired_hold_pool = []
    future_hold_pool = []
    other_pool = []

    for booking_id in range(1, count + 1):
        if rng.random() < 0.35:
            vehicle_id = rng.randint(1, hot_count)
        else:
            vehicle_id = rng.randint(1, vehicle_count)
        status = rng.choices(statuses, weights=weights, k=1)[0]

        hold_expires_at = None
        if status in EXPIRABLE:
            if rng.random() < 0.75:
                hold_expires_at = ANCHOR - timedelta(minutes=rng.randint(1, 60 * 48))
                expired_hold_pool.append((booking_id, vehicle_id))
            else:
                hold_expires_at = ANCHOR + timedelta(minutes=rng.randint(1, 60 * 48))
                future_hold_pool.append((booking_id, vehicle_id))
        elif status in BLOCKING_STATUSES:
            other_pool.append((booking_id, vehicle_id))
        else:
            other_pool.append((booking_id, vehicle_id))

        busy_probability = 0.55 if status in BLOCKING_STATUSES else 0.18
        start = random_start(rng, busy_probability)
        end = start + timedelta(hours=rng.randint(4, 30))
        amount = Decimal(rng.randint(180, 1200))
        rows.append(
            {
                "id": booking_id,
                "customer_id": rng.randint(51, 250),
                "vehicle_id": vehicle_id,
                "store_id": vehicle_store[vehicle_id],
                "delivery_point_id": None,
                "start_time": start,
                "end_time": end,
                "hold_expires_at": hold_expires_at,
                "status": status,
                "rental_amount": amount,
                "delivery_fee": Decimal("0"),
                "deposit_amount": (amount * Decimal("0.3")).quantize(Decimal("0.01")),
                "total_amount": amount,
            }
        )
    return rows, expired_hold_pool, future_hold_pool, other_pool


def pick_booking(rng, expired_pool, future_pool, other_pool, prefer_future: bool):
    """Chọn booking hợp lệ để làm khóa ngoại, thiên về hold còn/hết hạn."""
    if prefer_future and future_pool and rng.random() < 0.60:
        return rng.choice(future_pool)
    if expired_pool and rng.random() < 0.65:
        return rng.choice(expired_pool)
    if other_pool and rng.random() < 0.60:
        return rng.choice(other_pool)
    for pool in (future_pool, expired_pool, other_pool):
        if pool:
            return rng.choice(pool)
    return None


def make_reservations(rng, count, vehicle_count, expired_pool, future_pool, other_pool):
    rows = []
    for reservation_id in range(1, count + 1):
        roll = rng.random()
        if roll < 0.06:
            status = "ACTIVE"
            expires_at = ANCHOR + timedelta(minutes=rng.randint(1, 60 * 24))
            busy = 0.90
        elif roll < 0.26:
            status = "ACTIVE"
            expires_at = ANCHOR - timedelta(minutes=rng.randint(1, 60 * 24))
            busy = 0.45
        else:
            status = rng.choice(("EXPIRED", "CONVERTED", "CANCELLED"))
            expires_at = ANCHOR - timedelta(minutes=rng.randint(1, 60 * 24 * 30))
            busy = 0.18

        picked = pick_booking(rng, expired_pool, future_pool, other_pool, status == "ACTIVE")
        if picked:
            booking_id, vehicle_id = picked
        else:
            booking_id = None
            vehicle_id = rng.randint(1, vehicle_count)

        start = random_start(rng, busy)
        rows.append(
            {
                "id": reservation_id,
                "vehicle_id": vehicle_id,
                "customer_id": rng.randint(51, 250),
                "booking_id": booking_id,
                "start_time": start,
                "end_time": start + timedelta(hours=rng.randint(4, 30)),
                "expires_at": expires_at,
                "status": status,
            }
        )
    return rows


def make_schedules(rng, count, vehicle_count, expired_pool, future_pool, other_pool):
    rows = []
    for schedule_id in range(1, count + 1):
        status = "ACTIVE" if rng.random() < 0.08 else "RELEASED"
        schedule_type = "MAINTENANCE" if rng.random() < 0.30 else "RENTAL"
        picked = pick_booking(rng, expired_pool, future_pool, other_pool, status == "ACTIVE")
        if picked:
            booking_id, vehicle_id = picked
        else:
            booking_id = None
            vehicle_id = rng.randint(1, vehicle_count)

        start = random_start(rng, 0.85 if status == "ACTIVE" else 0.20)
        rows.append(
            {
                "id": schedule_id,
                "vehicle_id": vehicle_id,
                "booking_id": booking_id,
                "reservation_id": None,
                "schedule_type": schedule_type,
                "start_time": start,
                "end_time": start + timedelta(hours=rng.randint(4, 48)),
                "status": status,
                "note": None,
            }
        )
    return rows


def main() -> None:
    args = parse_args()
    if args.scale <= 0:
        raise SystemExit("--scale phải > 0")

    url = get_perf_url()
    engine = make_perf_engine(url)
    database = assert_safe_database(engine)
    print(f"DB an toàn: {database} ({db_name_from_url(url)})")

    if args.reset:
        reset_data(engine)
        print("Đã reset dữ liệu cũ")
    else:
        print("Không reset; script sẽ chèn thêm và có thể vi phạm khóa duy nhất.")

    rng = random.Random(args.seed)
    store_count = max(1, int(50 * args.scale))
    vehicle_count = max(store_count, int(5000 * args.scale))
    booking_count = max(1, int(500000 * args.scale))
    reservation_count = max(1, int(100000 * args.scale))
    schedule_count = max(1, int(100000 * args.scale))

    with engine.begin() as conn:
        conn.execute(
            Role.__table__.insert(),
            [
                {"id": 1, "code": "CUSTOMER", "name": "Khách hàng"},
                {"id": 2, "code": "STORE_OWNER", "name": "Chủ cửa hàng"},
            ],
        )
        users = []
        for user_id in range(1, 251):
            users.append(
                {
                    "id": user_id,
                    "firebase_uid": f"perf-uid-{user_id}",
                    "phone": f"09{user_id:09d}"[:15],
                    "email": f"perf-user-{user_id}@example.test",
                    "full_name": f"Perf User {user_id}",
                    "status": "active",
                }
            )
        conn.execute(User.__table__.insert(), users)
        conn.execute(
            UserRole.__table__.insert(),
            [
                {"user_id": user_id, "role_id": 1 if user_id > store_count else 2}
                for user_id in range(1, 251)
            ],
        )

        stores = []
        for store_id in range(1, store_count + 1):
            city = "Ha Noi" if store_id <= 10 else CITIES[store_id % len(CITIES)]
            stores.append(
                {
                    "id": store_id,
                    "owner_user_id": store_id,
                    "name": f"Perf Store {store_id}",
                    "email": f"perf-store-{store_id}@example.test",
                    "address": f"{store_id} Perf Street",
                    "city": city,
                    "business_license": f"PERF-LIC-{store_id:05d}",
                    "status": "APPROVED",
                }
            )
        conn.execute(Store.__table__.insert(), stores)

        points = []
        point_id = 1
        for store_id in range(1, store_count + 1):
            for area in AREAS:
                points.append(
                    {
                        "id": point_id,
                        "store_id": store_id,
                        "name": f"Diem giao {point_id}",
                        "address": f"{point_id} Perf Alley",
                        "area": area,
                        "delivery_fee": Decimal("15000"),
                        "is_active": True,
                    }
                )
                point_id += 1
        conn.execute(DeliveryPoint.__table__.insert(), points)

        vehicle_store = [0] * (vehicle_count + 1)
        vehicles = []
        for vehicle_id in range(1, vehicle_count + 1):
            store_id = (vehicle_id - 1) % store_count + 1
            vehicle_store[vehicle_id] = store_id
            vehicles.append(
                {
                    "id": vehicle_id,
                    "store_id": store_id,
                    "vehicle_type": "MOTORBIKE" if vehicle_id % 3 else "CAR",
                    "plate_number": f"{store_id}-{vehicle_id:06d}"[-20:],
                    "brand": "Honda" if vehicle_id % 3 else "Toyota",
                    "model": f"Model {vehicle_id % 20}",
                    "transmission_type": "AUTO" if vehicle_id % 2 else "MANUAL",
                    "seats": 2 if vehicle_id % 3 else 4,
                    "fuel_type": "XANG",
                    "price_per_day": Decimal(rng.randint(150, 900) * 1000),
                    "price_per_hour": Decimal(rng.randint(20, 90) * 1000),
                    "current_status": "AVAILABLE",
                    "is_active": rng.random() < 0.97,
                    "created_at": ANCHOR - timedelta(days=rng.randint(1, 720)),
                }
            )
        conn.execute(Vehicle.__table__.insert(), vehicles)

    print(
        f"Đã seed users=250 stores={store_count} delivery_points={len(points)} "
        f"vehicles={vehicle_count}"
    )

    bookings, expired_pool, future_pool, other_pool = make_bookings(
        rng, booking_count, vehicle_count, vehicle_store
    )
    bulk_insert(engine, Booking.__table__, bookings, args.batch_size)
    print(
        f"Đã seed bookings={booking_count} "
        f"(expired_hold={len(expired_pool)}, future_hold={len(future_pool)})"
    )

    reservations = make_reservations(
        rng, reservation_count, vehicle_count, expired_pool, future_pool, other_pool
    )
    bulk_insert(engine, VehicleReservation.__table__, reservations, args.batch_size)
    print(f"Đã seed vehicle_reservations={reservation_count}")

    schedules = make_schedules(
        rng, schedule_count, vehicle_count, expired_pool, future_pool, other_pool
    )
    bulk_insert(engine, VehicleSchedule.__table__, schedules, args.batch_size)
    print(f"Đã seed vehicle_schedules={schedule_count}")

    analyze_tables = [
        "bookings",
        "vehicle_reservations",
        "vehicle_schedules",
        "vehicles",
        "stores",
        "delivery_points",
    ]
    with engine.begin() as conn:
        for table in analyze_tables:
            conn.execute(text(f"ANALYZE TABLE `{table}`"))
    print("Đã ANALYZE TABLE các bảng liên quan")


if __name__ == "__main__":
    main()
