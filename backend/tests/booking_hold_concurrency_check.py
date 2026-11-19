"""Kiểm thử tuần tự + đồng thời cho POST /api/bookings (TF197DE).

BẮT BUỘC chạy với MySQL thật vì SQLite bỏ qua ``SELECT ... FOR UPDATE``.
Khuyến nghị dùng một database test riêng, không dùng app_db thật:

    cd backend
    TEST_DATABASE_URL='mysql+pymysql://root:password@127.0.0.1:3306/ridehub_booking_test?charset=utf8mb4' \
      python tests/booking_hold_concurrency_check.py

Script tự tạo bảng còn thiếu, seed dữ liệu test, chạy các kịch bản rồi in
PASS/FAIL. Không in mật khẩu database.
"""
from __future__ import annotations

import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app import models  # noqa: F401 - đăng ký toàn bộ model với metadata
from app.crud import booking as booking_crud
from app.db.session import Base
from app.models.booking import Booking
from app.models.delivery import DeliveryPoint
from app.models.store import Store
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.vehicle_reservation import VehicleReservation
from app.models.vehicle_schedule import VehicleSchedule
from app.schemas.booking import BookingHoldCreate

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL") or os.getenv(
    "DATABASE_URL_TEST"
)
if not TEST_DATABASE_URL:
    print(
        "SKIP: chưa đặt TEST_DATABASE_URL. Cần MySQL thật để test FOR UPDATE.\n"
        "Ví dụ:\n"
        "  TEST_DATABASE_URL='mysql+pymysql://root:password@127.0.0.1:3306/"
        "ridehub_booking_test?charset=utf8mb4' \\\n"
        "    python tests/booking_hold_concurrency_check.py"
    )
    sys.exit(2)

if not TEST_DATABASE_URL.startswith("mysql"):
    print("FAIL: TEST_DATABASE_URL phải là MySQL, không dùng SQLite.")
    sys.exit(2)

engine = create_engine(
    TEST_DATABASE_URL,
    poolclass=NullPool,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)
Base.metadata.create_all(bind=engine)

USER_IDS = (8201, 8202, 8203)
STORE_IDS = (8201, 8202, 8203)
VEHICLE_IDS = (8301, 8302, 8303, 8304, 8305)
DELIVERY_POINT_IDS = (8401, 8402, 8403)


def _now() -> datetime:
    return datetime.now().replace(microsecond=0)


def _seed_base():
    now = _now()
    with SessionLocal() as db:
        db.add_all(
            [
                User(id=8201, phone="0900008201", full_name="Chủ cửa hàng"),
                User(id=8202, phone="0900008202", full_name="Khách hàng"),
                User(id=8203, phone="0900008203", full_name="Khách hàng khác"),
                Store(
                    id=8201,
                    owner_user_id=8201,
                    name="RideHub Booking Test Approved",
                    address="122 Hoàng Quốc Việt",
                    city="Hà Nội",
                    business_license="GP-8201",
                    status="APPROVED",
                ),
                Store(
                    id=8202,
                    owner_user_id=8201,
                    name="RideHub Booking Test Pending",
                    address="1 Nguyễn Huệ",
                    city="TP.HCM",
                    business_license="GP-8202",
                    status="PENDING",
                ),
                Store(
                    id=8203,
                    owner_user_id=8201,
                    name="RideHub Booking Test Other",
                    address="1 Bạch Đằng",
                    city="Đà Nẵng",
                    business_license="GP-8203",
                    status="APPROVED",
                ),
                Vehicle(
                    id=8301,
                    store_id=8201,
                    vehicle_type="MOTORBIKE",
                    plate_number="TEST-8301",
                    brand="Honda",
                    model="Vision",
                    price_per_day=Decimal("150000"),
                    price_per_hour=Decimal("25000"),
                    current_status="MAINTENANCE",
                    is_active=True,
                ),
                Vehicle(
                    id=8302,
                    store_id=8202,
                    vehicle_type="MOTORBIKE",
                    plate_number="TEST-8302",
                    brand="Honda",
                    model="Wave",
                    price_per_day=Decimal("150000"),
                    price_per_hour=Decimal("25000"),
                    current_status="MAINTENANCE",
                    is_active=True,
                ),
                Vehicle(
                    id=8303,
                    store_id=8201,
                    vehicle_type="MOTORBIKE",
                    plate_number="TEST-8303",
                    brand="Honda",
                    model="Future",
                    price_per_day=Decimal("100000"),
                    price_per_hour=None,
                    current_status="MAINTENANCE",
                    is_active=False,
                ),
                Vehicle(
                    id=8304,
                    store_id=8203,
                    vehicle_type="MOTORBIKE",
                    plate_number="TEST-8304",
                    brand="Yamaha",
                    model="Exciter",
                    price_per_day=Decimal("200000"),
                    price_per_hour=Decimal("30000"),
                    current_status="MAINTENANCE",
                    is_active=True,
                ),
                Vehicle(
                    id=8305,
                    store_id=8201,
                    vehicle_type="MOTORBIKE",
                    plate_number="TEST-8305",
                    brand="Honda",
                    model="Air Blade",
                    price_per_day=Decimal("120000"),
                    price_per_hour=Decimal("20000"),
                    current_status="MAINTENANCE",
                    is_active=True,
                ),
                DeliveryPoint(
                    id=8401,
                    store_id=8201,
                    name="Điểm giao hợp lệ",
                    address="Bến xe Mỹ Đình",
                    area="Quận Cầu Giấy",
                    delivery_fee=Decimal("50000"),
                    is_active=True,
                ),
                DeliveryPoint(
                    id=8402,
                    store_id=8201,
                    name="Điểm giao ẩn",
                    address="Không dùng",
                    area="Quận X",
                    delivery_fee=Decimal("30000"),
                    is_active=False,
                ),
                DeliveryPoint(
                    id=8403,
                    store_id=8203,
                    name="Điểm giao cửa hàng khác",
                    address="Bạch Đằng",
                    area="Quận Hải Châu",
                    delivery_fee=Decimal("40000"),
                    is_active=True,
                ),
                Booking(
                    id=8501,
                    customer_id=8203,
                    vehicle_id=8301,
                    store_id=8201,
                    start_time=now + timedelta(days=1),
                    end_time=now + timedelta(days=2),
                    status="CONFIRMED",
                    rental_amount=Decimal("300000"),
                    delivery_fee=Decimal("0"),
                    deposit_amount=Decimal("200000"),
                    total_amount=Decimal("300000"),
                ),
                Booking(
                    id=8502,
                    customer_id=8203,
                    vehicle_id=8301,
                    store_id=8201,
                    start_time=now + timedelta(days=11),
                    end_time=now + timedelta(days=12),
                    status="CANCELLED",
                    rental_amount=Decimal("300000"),
                    delivery_fee=Decimal("0"),
                    deposit_amount=Decimal("200000"),
                    total_amount=Decimal("300000"),
                ),
                VehicleReservation(
                    id=8601,
                    vehicle_id=8301,
                    customer_id=8203,
                    start_time=now + timedelta(days=3),
                    end_time=now + timedelta(days=4),
                    expires_at=now + timedelta(minutes=30),
                    status="ACTIVE",
                ),
                VehicleReservation(
                    id=8602,
                    vehicle_id=8301,
                    customer_id=8203,
                    start_time=now + timedelta(days=5),
                    end_time=now + timedelta(days=6),
                    expires_at=now - timedelta(minutes=1),
                    status="ACTIVE",
                ),
                VehicleSchedule(
                    id=8701,
                    vehicle_id=8305,
                    schedule_type="MAINTENANCE",
                    start_time=now + timedelta(days=7),
                    end_time=now + timedelta(days=8),
                    status="ACTIVE",
                    note="Bảo dưỡng định kỳ",
                ),
                VehicleSchedule(
                    id=8702,
                    vehicle_id=8301,
                    schedule_type="RENTAL",
                    start_time=now + timedelta(days=9),
                    end_time=now + timedelta(days=10),
                    status="ACTIVE",
                    note="Lịch chặn",
                ),
            ]
        )
        db.commit()


def reset_seed_data():
    with SessionLocal() as db:
        db.execute(
            delete(VehicleSchedule).where(
                VehicleSchedule.vehicle_id.in_(VEHICLE_IDS)
            )
        )
        db.execute(
            delete(VehicleReservation).where(
                VehicleReservation.vehicle_id.in_(VEHICLE_IDS)
            )
        )
        db.execute(
            delete(Booking).where(Booking.vehicle_id.in_(VEHICLE_IDS))
        )
        db.execute(
            delete(DeliveryPoint).where(
                DeliveryPoint.id.in_(DELIVERY_POINT_IDS)
            )
        )
        db.execute(delete(Vehicle).where(Vehicle.id.in_(VEHICLE_IDS)))
        db.execute(delete(Store).where(Store.id.in_(STORE_IDS)))
        db.execute(delete(User).where(User.id.in_(USER_IDS)))
        db.commit()
    _seed_base()


def make_payload(
    *,
    vehicle_id: int = 8301,
    start: datetime | None = None,
    end: datetime | None = None,
    delivery_point_id: int | None = None,
    customer_id: int = 8202,
) -> BookingHoldCreate:
    now = _now()
    start = start or (now + timedelta(days=20))
    end = end or (start + timedelta(days=2))
    return BookingHoldCreate(
        customer_id=customer_id,
        vehicle_id=vehicle_id,
        start_time=start,
        end_time=end,
        delivery_point_id=delivery_point_id,
    )


def create_once(payload: BookingHoldCreate):
    with SessionLocal() as db:
        return booking_crud.create_booking_with_hold(
            db, payload, customer_id=payload.customer_id
        )


def _counts(vehicle_id, start, end):
    with SessionLocal() as db:
        booking_count = db.scalar(
            select(func.count())
            .select_from(Booking)
            .where(
                Booking.vehicle_id == vehicle_id,
                Booking.status == "PENDING_PAYMENT",
                Booking.start_time == start,
                Booking.end_time == end,
            )
        )
        reservation_count = db.scalar(
            select(func.count())
            .select_from(VehicleReservation)
            .where(
                VehicleReservation.vehicle_id == vehicle_id,
                VehicleReservation.start_time == start,
                VehicleReservation.end_time == end,
            )
        )
        schedule_count = db.scalar(
            select(func.count())
            .select_from(VehicleSchedule)
            .where(
                VehicleSchedule.vehicle_id == vehicle_id,
                VehicleSchedule.start_time == start,
                VehicleSchedule.end_time == end,
            )
        )
    return booking_count or 0, reservation_count or 0, schedule_count or 0


def _run_concurrent(payloads):
    barrier = threading.Barrier(len(payloads))

    def worker(payload):
        try:
            barrier.wait(timeout=15)
        except Exception as exc:  # noqa: BLE001 - báo lỗi barrier rõ ràng
            return "ERROR", f"barrier: {exc!r}"

        try:
            return "OK", create_once(payload)
        except booking_crud.BookingConflictError as exc:
            return "CONFLICT", str(exc)
        except booking_crud.BookingUnavailableError as exc:
            return "BUSY", str(exc)
        except booking_crud.BookingError as exc:
            return type(exc).__name__, str(exc)
        except Exception as exc:  # noqa: BLE001 - test cần thấy lỗi thật
            return "ERROR", repr(exc)

    with ThreadPoolExecutor(max_workers=len(payloads)) as pool:
        return list(pool.map(worker, payloads))


def _check(name, condition, detail=""):
    if condition:
        print(f"PASS {name}")
        return True
    print(f"FAIL {name} {detail}")
    return False


def _expect_error(name, payload, error_type):
    try:
        create_once(payload)
    except error_type:
        return _check(name, True)
    except Exception as exc:  # noqa: BLE001
        return _check(name, False, f"nhận {type(exc).__name__}: {exc}")
    return _check(name, False, "không raise lỗi")


def scenario_success():
    reset_seed_data()
    start = _now() + timedelta(days=20)
    end = start + timedelta(days=2)
    result = create_once(
        make_payload(start=start, end=end, delivery_point_id=8401)
    )

    ok = _check(
        "tuần tự: tạo thành công + tính tiền/cọc",
        result.status == "PENDING_PAYMENT"
        and result.booking_code is None
        and result.store_id == 8201
        and result.rental_amount == 300000.0
        and result.delivery_fee == 50000.0
        and result.deposit_amount == 200000.0
        and result.total_amount == 350000.0
        and result.reservation_id > 0,
        repr(result),
    )
    ok &= _check(
        "tuần tự: đủ 1 booking + 1 reservation + 1 schedule",
        _counts(8301, start, end) == (1, 1, 1),
        str(_counts(8301, start, end)),
    )

    with SessionLocal() as db:
        booking = db.get(Booking, result.id)
        reservation = db.get(VehicleReservation, result.reservation_id)
        schedule = db.scalar(
            select(VehicleSchedule).where(
                VehicleSchedule.booking_id == booking.id
            )
        )

    ok &= _check(
        "tuần tự: reservation/schedule liên kết đúng booking",
        booking is not None
        and reservation is not None
        and reservation.booking_id == booking.id
        and reservation.expires_at == booking.hold_expires_at
        and schedule is not None
        and schedule.reservation_id == reservation.id
        and schedule.schedule_type == "RENTAL"
        and schedule.status == "ACTIVE",
    )
    return ok


def scenario_validation_errors():
    reset_seed_data()
    start = _now() + timedelta(days=20)
    ok = True
    ok &= _expect_error(
        "validate: dưới 4 giờ",
        make_payload(start=start, end=start + timedelta(hours=3)),
        booking_crud.BookingValidationError,
    )
    ok &= _expect_error(
        "validate: quá 30 ngày",
        make_payload(start=start, end=start + timedelta(days=31)),
        booking_crud.BookingValidationError,
    )
    ok &= _expect_error(
        "validate: cửa hàng PENDING -> 404",
        make_payload(
            start=start,
            end=start + timedelta(days=2),
            vehicle_id=8302,
        ),
        booking_crud.BookingNotFoundError,
    )
    ok &= _expect_error(
        "validate: xe is_active=false -> 404",
        make_payload(
            start=start,
            end=start + timedelta(days=2),
            vehicle_id=8303,
        ),
        booking_crud.BookingNotFoundError,
    )
    ok &= _expect_error(
        "validate: điểm giao khác cửa hàng",
        make_payload(
            start=start,
            end=start + timedelta(days=2),
            delivery_point_id=8403,
        ),
        booking_crud.BookingValidationError,
    )
    ok &= _expect_error(
        "validate: khách không tồn tại",
        make_payload(
            start=start,
            end=start + timedelta(days=2),
            customer_id=9999,
        ),
        booking_crud.BookingValidationError,
    )
    return ok


def scenario_conflicts_and_buffer():
    reset_seed_data()
    ok = True

    ok &= _expect_error(
        "lịch: booking CONFIRMED chặn",
        make_payload(
            start=_now() + timedelta(days=1, hours=1),
            end=_now() + timedelta(days=1, hours=5),
        ),
        booking_crud.BookingConflictError,
    )
    ok &= _expect_error(
        "lịch: reservation ACTIVE còn hạn chặn",
        make_payload(
            start=_now() + timedelta(days=3, hours=1),
            end=_now() + timedelta(days=3, hours=5),
        ),
        booking_crud.BookingConflictError,
    )
    ok &= _expect_error(
        "lịch: schedule MAINTENANCE chặn",
        make_payload(
            start=_now() + timedelta(days=7, hours=1),
            end=_now() + timedelta(days=7, hours=5),
            vehicle_id=8305,
        ),
        booking_crud.BookingConflictError,
    )
    ok &= _expect_error(
        "lịch: schedule RENTAL chặn",
        make_payload(
            start=_now() + timedelta(days=9, hours=1),
            end=_now() + timedelta(days=9, hours=5),
        ),
        booking_crud.BookingConflictError,
    )

    # Booking CANCELLED không chặn.
    cancelled_start = _now() + timedelta(days=11, hours=1)
    try:
        create_once(
            make_payload(
                start=cancelled_start,
                end=cancelled_start + timedelta(hours=4),
            )
        )
        ok &= _check("lịch: booking CANCELLED không chặn", True)
    except Exception as exc:  # noqa: BLE001
        ok &= _check(
            "lịch: booking CANCELLED không chặn",
            False,
            f"{type(exc).__name__}: {exc}",
        )

    # Reservation ACTIVE đã hết hạn không chặn.
    expired_start = _now() + timedelta(days=5, hours=1)
    try:
        create_once(
            make_payload(
                start=expired_start,
                end=expired_start + timedelta(hours=4),
            )
        )
        ok &= _check("lịch: reservation hết hạn không chặn", True)
    except Exception as exc:  # noqa: BLE001
        ok &= _check(
            "lịch: reservation hết hạn không chặn",
            False,
            f"{type(exc).__name__}: {exc}",
        )

    # Đệm 60 phút: cách đúng 60 phút được phép.
    reset_seed_data()
    first_start = _now() + timedelta(days=20)
    first_end = first_start + timedelta(days=2)
    create_once(make_payload(start=first_start, end=first_end))
    second_start = first_end + timedelta(minutes=60)
    try:
        create_once(
            make_payload(
                start=second_start,
                end=second_start + timedelta(hours=4),
            )
        )
        ok &= _check("đệm: cách đúng 60 phút được phép", True)
    except Exception as exc:  # noqa: BLE001
        ok &= _check(
            "đệm: cách đúng 60 phút được phép",
            False,
            f"{type(exc).__name__}: {exc}",
        )

    # Đệm 59 phút: bị chặn.
    reset_seed_data()
    first_start = _now() + timedelta(days=20)
    first_end = first_start + timedelta(days=2)
    create_once(make_payload(start=first_start, end=first_end))
    second_start = first_end + timedelta(minutes=59)
    ok &= _expect_error(
        "đệm: cách 59 phút bị chặn",
        make_payload(
            start=second_start,
            end=second_start + timedelta(hours=4),
        ),
        booking_crud.BookingConflictError,
    )
    return ok


def scenario_concurrent_2():
    reset_seed_data()
    start = _now() + timedelta(days=20)
    end = start + timedelta(days=2)
    payloads = [
        make_payload(start=start, end=end),
        make_payload(start=start, end=end),
    ]
    results = _run_concurrent(payloads)
    statuses = [status for status, _ in results]
    ok = _check(
        "đồng thời 2 request cùng xe/giờ: đúng 1 thành công",
        statuses.count("OK") == 1 and statuses.count("CONFLICT") == 1,
        str(statuses),
    )
    ok &= _check(
        "đồng thời 2 request: DB chỉ có 1 bộ bản ghi",
        _counts(8301, start, end) == (1, 1, 1),
        str(_counts(8301, start, end)),
    )
    return ok


def scenario_concurrent_20():
    reset_seed_data()
    start = _now() + timedelta(days=20)
    end = start + timedelta(days=2)
    payloads = [
        make_payload(start=start, end=end) for _ in range(20)
    ]
    results = _run_concurrent(payloads)
    statuses = [status for status, _ in results]
    ok = _check(
        "đồng thời 20 request cùng xe/giờ: đúng 1 thành công",
        statuses.count("OK") == 1 and statuses.count("CONFLICT") == 19,
        str(statuses),
    )
    ok &= _check(
        "đồng thời 20 request: DB chỉ có 1 bộ bản ghi",
        _counts(8301, start, end) == (1, 1, 1),
        str(_counts(8301, start, end)),
    )
    return ok


def scenario_loop_20():
    ok = True
    for index in range(20):
        reset_seed_data()
        start = _now() + timedelta(days=20)
        end = start + timedelta(days=2)
        payloads = [
            make_payload(start=start, end=end) for _ in range(5)
        ]
        results = _run_concurrent(payloads)
        statuses = [status for status, _ in results]
        counts = _counts(8301, start, end)
        if statuses.count("OK") != 1 or statuses.count("CONFLICT") != 4:
            ok = _check(
                f"lặp 20 lần: vòng {index + 1}",
                False,
                str(statuses),
            )
            break
        if counts != (1, 1, 1):
            ok = _check(
                f"lặp 20 lần: vòng {index + 1} DB",
                False,
                str(counts),
            )
            break
    if ok:
        ok = _check("lặp 20 lần x 5 request: luôn đúng 1 thành công", True)
    return ok


def main():
    print("Chạy test booking hold trên MySQL thật.")
    results = [
        scenario_success(),
        scenario_validation_errors(),
        scenario_conflicts_and_buffer(),
        scenario_concurrent_2(),
        scenario_concurrent_20(),
        scenario_loop_20(),
    ]
    if all(results):
        print("\nTẤT CẢ KỊCH BẢN PASS")
        return 0
    print("\nCÓ KỊCH BẢN FAIL")
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {type(exc).__name__}: {exc}")
        raise
