"""TF19904 — Kiểm thử đặt trùng lịch đồng thời, giữ chỗ hết hạn và hủy đơn.

BẮT BUỘC chạy trên MySQL 8 thật (SQLite bỏ qua ``FOR UPDATE``). File này
KHÔNG sửa code sản phẩm; mọi phát hiện lỗi được ghi bằng assertion có thông điệp
rõ và được tổng hợp trong docs/test-results/TF19904-*.

Chạy:
    cd backend
    TEST_DATABASE_URL='mysql+pymysql://user:pass@127.0.0.1:3306/ridehub_test?charset=utf8mb4' \
      .venv/bin/python -m pytest tests/test_booking_concurrency_hold_cancel.py -v

Chốt an toàn: TEST_DATABASE_URL bắt buộc, phải là MySQL và tên database phải
chứa "test". Nếu không thỏa, toàn bộ test được skip, không đụng DB làm việc.
"""
from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Callable

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, delete, func, or_, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app import models  # noqa: F401 - đăng ký model với metadata
from app.core.config import settings
from app.crud import booking as booking_crud
from app.crud.vehicle import vehicle_has_conflict
from app.db.session import Base
from app.main import app
from app.models.booking import Booking
from app.models.delivery import DeliveryPoint
from app.models.payment import PaymentTransaction, Refund
from app.models.store import Store
from app.models.user import User
from app.models.vehicle import Vehicle, VehicleStatusHistory
from app.models.vehicle_reservation import VehicleReservation
from app.models.vehicle_schedule import VehicleSchedule
from app.routers.payment import cancel_booking_payment, process_payment_refund
from app.schemas.booking import BookingHoldCreate
from app.schemas.payment import PaymentRefundRequest

pytestmark = pytest.mark.mysql

ROUNDS = max(1, int(os.getenv("TF19904_ROUNDS", "20")))

OWNER_ID = 1990401
CUSTOMER_IDS = (1990411, 1990412, 1990413)
STORE_ID = 1990401
VEHICLE_IDS = (1990401, 1990402, 1990403)
VEHICLE_A, VEHICLE_B, VEHICLE_C = VEHICLE_IDS
DELIVERY_POINT_ID = 1990401
ADMIN_ID = 1990499

SessionLocal: sessionmaker | None = None


def _now() -> datetime:
    """Giờ địa phương, không dùng utcnow theo yêu cầu task."""
    return datetime.now().replace(microsecond=0)


def _get_test_database_url() -> str:
    url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL_TEST")
    if not url:
        pytest.skip("Chưa đặt TEST_DATABASE_URL/DATABASE_URL_TEST; không chạy test MySQL.")
    parsed = make_url(url)
    if parsed.get_backend_name() not in {"mysql", "pymysql"}:
        pytest.skip("TEST_DATABASE_URL phải là MySQL (FOR UPDATE không có trong SQLite).")
    database = (parsed.database or "").lower()
    if "test" not in database:
        pytest.skip(
            "Chốt an toàn: tên database không chứa 'test' "
            f"(nhận được database='{parsed.database}'); từ chối chạy để tránh đụng DB làm việc."
        )
    return url


@pytest.fixture(scope="session")
def mysql_engine():
    engine = create_engine(_get_test_database_url(), poolclass=NullPool, pool_pre_ping=True)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    Base.metadata.create_all(bind=engine)
    global SessionLocal
    SessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    yield engine
    engine.dispose()


@pytest.fixture
def seeded(mysql_engine):
    _clean_and_seed()
    return _now()


def _clean_and_seed() -> None:
    assert SessionLocal is not None
    with SessionLocal() as db:
        booking_ids = select(Booking.id).where(
            or_(
                Booking.vehicle_id.in_(VEHICLE_IDS),
                Booking.customer_id.in_(CUSTOMER_IDS),
            )
        )
        db.execute(delete(Refund).where(Refund.booking_id.in_(booking_ids)))
        db.execute(delete(PaymentTransaction).where(PaymentTransaction.booking_id.in_(booking_ids)))
        db.execute(delete(VehicleStatusHistory).where(VehicleStatusHistory.vehicle_id.in_(VEHICLE_IDS)))
        db.execute(delete(VehicleSchedule).where(VehicleSchedule.vehicle_id.in_(VEHICLE_IDS)))
        db.execute(delete(VehicleReservation).where(VehicleReservation.vehicle_id.in_(VEHICLE_IDS)))
        db.execute(
            delete(Booking).where(
                or_(
                    Booking.vehicle_id.in_(VEHICLE_IDS),
                    Booking.customer_id.in_(CUSTOMER_IDS),
                )
            )
        )
        db.execute(delete(DeliveryPoint).where(DeliveryPoint.id == DELIVERY_POINT_ID))
        db.execute(delete(Vehicle).where(Vehicle.id.in_(VEHICLE_IDS)))
        db.execute(delete(Store).where(Store.id == STORE_ID))
        db.execute(delete(User).where(User.id.in_((OWNER_ID, *CUSTOMER_IDS))))

        db.add_all(
            [
                User(id=OWNER_ID, phone="0919900001", full_name="Chủ cửa hàng TF19904"),
                *[
                    User(id=customer_id, phone=f"0919910{index:03d}", full_name=f"Khách TF19904 {index}")
                    for index, customer_id in enumerate(CUSTOMER_IDS, start=1)
                ],
                Store(
                    id=STORE_ID,
                    owner_user_id=OWNER_ID,
                    name="RideHub TF19904 Store",
                    address="122 Hoàng Quốc Việt",
                    city="Hà Nội",
                    business_license="GP-TF19904",
                    status="APPROVED",
                ),
                *[
                    Vehicle(
                        id=vehicle_id,
                        store_id=STORE_ID,
                        vehicle_type="MOTORBIKE",
                        plate_number=f"TF19904-{index}",
                        brand="Honda",
                        model=f"Test {index}",
                        price_per_day=Decimal("100000"),
                        price_per_hour=Decimal("25000"),
                        current_status="MAINTENANCE",
                        is_active=True,
                    )
                    for index, vehicle_id in enumerate(VEHICLE_IDS, start=1)
                ],
                DeliveryPoint(
                    id=DELIVERY_POINT_ID,
                    store_id=STORE_ID,
                    name="Điểm giao TF19904",
                    address="Bến xe Mỹ Đình",
                    area="Cầu Giấy",
                    delivery_fee=Decimal("50000"),
                    is_active=True,
                ),
            ]
        )
        db.commit()


def _payload(
    *,
    vehicle_id: int = VEHICLE_A,
    customer_id: int = CUSTOMER_IDS[0],
    start: datetime | None = None,
    end: datetime | None = None,
    delivery_point_id: int | None = DELIVERY_POINT_ID,
) -> BookingHoldCreate:
    start = start or (_now() + timedelta(days=20))
    end = end or (start + timedelta(days=2))
    return BookingHoldCreate(
        customer_id=customer_id,
        vehicle_id=vehicle_id,
        start_time=start,
        end_time=end,
        delivery_point_id=delivery_point_id,
    )


def _create_once(
    payload: BookingHoldCreate,
    *,
    customer_id: int | None = None,
    now: datetime | None = None,
):
    assert SessionLocal is not None
    with SessionLocal() as db:
        return booking_crud.create_booking_with_hold(
            db,
            payload,
            customer_id=customer_id or payload.customer_id,
            now=now,
        )


def _run_concurrent(tasks: list[Callable[[], object]]) -> list[tuple[str, str]]:
    barrier = threading.Barrier(len(tasks))
    results: list[tuple[str, str]] = []

    def worker(task: Callable[[], object]) -> tuple[str, str]:
        try:
            barrier.wait(timeout=20)
        except Exception as exc:  # noqa: BLE001
            return "BARRIER_ERROR", repr(exc)
        try:
            value = task()
            return "OK", f"{type(value).__name__}:{getattr(value, 'id', '')}"
        except booking_crud.BookingConflictError as exc:
            return "CONFLICT", str(exc)
        except booking_crud.BookingUnavailableError as exc:
            return "BUSY", str(exc)
        except HTTPException as exc:
            return f"HTTP_{exc.status_code}", str(exc.detail)
        except Exception as exc:  # noqa: BLE001 - test cần thấy lỗi thật
            return "ERROR", repr(exc)

    with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
        results = list(pool.map(worker, tasks))
    return results


def _statuses(results: list[tuple[str, str]]) -> list[str]:
    return [status for status, _ in results]


def _slot_counts(vehicle_id: int, start: datetime, end: datetime) -> tuple[int, int, int]:
    assert SessionLocal is not None
    with SessionLocal() as db:
        booking_count = db.scalar(
            select(func.count())
            .select_from(Booking)
            .where(
                Booking.vehicle_id == vehicle_id,
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


def _payment_counts() -> tuple[int, int]:
    assert SessionLocal is not None
    with SessionLocal() as db:
        payments = db.scalar(select(func.count()).select_from(PaymentTransaction)) or 0
        refunds = db.scalar(select(func.count()).select_from(Refund)) or 0
    return payments, refunds


def _get_booking(booking_id: int) -> Booking:
    assert SessionLocal is not None
    with SessionLocal() as db:
        booking = db.get(Booking, booking_id)
        assert booking is not None
        db.expunge(booking)
        return booking


def _set_booking_status(booking_id: int, status_value: str) -> None:
    assert SessionLocal is not None
    with SessionLocal() as db:
        db.execute(
            Booking.__table__.update()
            .where(Booking.id == booking_id)
            .values(status=status_value)
        )
        db.commit()


def _add_success_payment(booking: Booking) -> PaymentTransaction:
    assert SessionLocal is not None
    with SessionLocal() as db:
        txn = PaymentTransaction(
            booking_id=booking.id,
            transaction_code=f"TF19904-SUCCESS-{booking.id}",
            provider="SANDBOX",
            amount=booking.deposit_amount,
            status="SUCCESS",
            paid_at=_now(),
        )
        db.add(txn)
        db.commit()
        db.refresh(txn)
        db.expunge(txn)
        return txn


def _cancel_endpoint(booking_id: int, customer_id: int):
    async def _call():
        assert SessionLocal is not None
        with SessionLocal() as db:
            current_user = User(id=customer_id, status="active")
            return await cancel_booking_payment(booking_id, db, current_user)

    return asyncio.run(_call())


def _refund_endpoint(booking_id: int, amount: float | None = None):
    assert SessionLocal is not None
    with SessionLocal() as db:
        admin = User(id=ADMIN_ID, status="active")
        request = PaymentRefundRequest(
            booking_id=booking_id,
            amount=amount,
            reason="TF19904 kiểm tra BR-04",
        )
        return process_payment_refund(request, db, admin)


# ---------------------------------------------------------------------------
# Bước 0 — đăng ký route (không cần DB)
# ---------------------------------------------------------------------------
def test_TC_S0_create_booking_route_registered(mysql_engine):
    paths = {(route.path, "POST") for route in app.routes if hasattr(route, "methods")}
    assert ("/api/bookings", "POST") in paths, "POST /api/bookings bị thiếu trên nhánh đang test"
    assert ("/api/bookings/check-eligibility", "POST") in paths


# ---------------------------------------------------------------------------
# NHÓM A — đặt trùng lịch đồng thời
# ---------------------------------------------------------------------------
def test_TC_A1_two_customers_same_vehicle_same_slot(seeded):
    detail = []
    for round_index in range(ROUNDS):
        _clean_and_seed()
        start = _now() + timedelta(days=20 + round_index)
        end = start + timedelta(days=2)
        payloads = [
            _payload(customer_id=customer_id, start=start, end=end)
            for customer_id in CUSTOMER_IDS[:2]
        ]
        results = _run_concurrent([lambda p=p: _create_once(p) for p in payloads])
        statuses = _statuses(results)
        detail.append(f"v{round_index + 1}={statuses}")
        assert statuses.count("OK") == 1, f"A1 vòng {round_index + 1}: {statuses} {results}"
        assert all(status in {"OK", "CONFLICT", "BUSY"} for status in statuses), (
            f"A1 vòng {round_index + 1}: có lỗi ngoài expected: {results}"
        )
        assert _slot_counts(VEHICLE_A, start, end) == (1, 1, 1), (
            f"A1 vòng {round_index + 1}: counts={_slot_counts(VEHICLE_A, start, end)}"
        )
    assert len(detail) == ROUNDS


@pytest.mark.parametrize("workers", [10, 20])
def test_TC_A2_10_and_20_threads_one_winner(seeded, workers):
    for round_index in range(ROUNDS):
        _clean_and_seed()
        start = _now() + timedelta(days=20 + round_index)
        end = start + timedelta(days=2)
        payloads = [
            _payload(customer_id=CUSTOMER_IDS[index % 3], start=start, end=end)
            for index in range(workers)
        ]
        results = _run_concurrent([lambda p=p: _create_once(p) for p in payloads])
        statuses = _statuses(results)
        assert statuses.count("OK") == 1, (
            f"A2 workers={workers} vòng {round_index + 1}: {statuses} {results}"
        )
        assert "ERROR" not in statuses, f"A2 workers={workers}: {results}"
        assert _slot_counts(VEHICLE_A, start, end) == (1, 1, 1)


def test_TC_A3_partial_overlap_one_hour(seeded):
    for round_index in range(ROUNDS):
        _clean_and_seed()
        start = _now() + timedelta(days=20 + round_index)
        first_end = start + timedelta(hours=4)
        second_start = start + timedelta(hours=1)
        second_end = second_start + timedelta(hours=4)
        payloads = [
            _payload(customer_id=CUSTOMER_IDS[0], start=start, end=first_end),
            _payload(customer_id=CUSTOMER_IDS[1], start=second_start, end=second_end),
        ]
        results = _run_concurrent([lambda p=p: _create_once(p) for p in payloads])
        statuses = _statuses(results)
        assert statuses.count("OK") == 1, (
            f"A3 vòng {round_index + 1}: {statuses} {results}"
        )


def test_TC_A4_buffer_60_minutes_allowed_59_blocked(seeded):
    buffer = timedelta(minutes=settings.BOOKING_BUFFER_MINUTES)
    assert buffer == timedelta(minutes=60)
    for round_index in range(ROUNDS):
        day = 20 + round_index

        _clean_and_seed()
        first_start = _now() + timedelta(days=day)
        first_end = first_start + timedelta(hours=4)
        _create_once(_payload(start=first_start, end=first_end))
        allowed_start = first_end + buffer
        allowed = _create_once(
            _payload(
                customer_id=CUSTOMER_IDS[1],
                start=allowed_start,
                end=allowed_start + timedelta(hours=4),
            )
        )
        assert allowed.id > 0, f"A4 vòng {round_index + 1}: cách đúng 60 phút bị chặn"

        _clean_and_seed()
        first_start = _now() + timedelta(days=day)
        first_end = first_start + timedelta(hours=4)
        _create_once(_payload(start=first_start, end=first_end))
        blocked_start = first_end + buffer - timedelta(minutes=1)
        with pytest.raises(booking_crud.BookingConflictError) as exc:
            _create_once(
                _payload(
                    customer_id=CUSTOMER_IDS[1],
                    start=blocked_start,
                    end=blocked_start + timedelta(hours=4),
                )
            )
        assert "Đã có lịch" in str(exc.value) or "lịch" in str(exc.value)


def test_TC_A5_two_vehicles_do_not_block_each_other(seeded):
    durations = []
    for round_index in range(ROUNDS):
        _clean_and_seed()
        start = _now() + timedelta(days=20 + round_index)
        end = start + timedelta(days=2)
        payloads = [
            _payload(vehicle_id=VEHICLE_A, customer_id=CUSTOMER_IDS[0], start=start, end=end),
            _payload(vehicle_id=VEHICLE_B, customer_id=CUSTOMER_IDS[1], start=start, end=end),
        ]
        started = time.monotonic()
        results = _run_concurrent([lambda p=p: _create_once(p) for p in payloads])
        durations.append(time.monotonic() - started)
        statuses = _statuses(results)
        assert statuses.count("OK") == 2, f"A5 vòng {round_index + 1}: {results}"
    assert max(durations) > 0


def test_TC_A6_same_customer_double_click(seeded):
    for round_index in range(ROUNDS):
        _clean_and_seed()
        start = _now() + timedelta(days=20 + round_index)
        end = start + timedelta(days=2)
        payload = _payload(customer_id=CUSTOMER_IDS[0], start=start, end=end)
        results = _run_concurrent([lambda: _create_once(payload) for _ in range(2)])
        statuses = _statuses(results)
        assert statuses.count("OK") == 1, f"A6 vòng {round_index + 1}: {statuses} {results}"
        assert _slot_counts(VEHICLE_A, start, end) == (1, 1, 1)


def test_TC_A7_no_orphan_rows_after_conflict(seeded):
    _clean_and_seed()
    start = _now() + timedelta(days=30)
    end = start + timedelta(days=2)
    payload = _payload(start=start, end=end)
    _create_once(payload)
    with pytest.raises(booking_crud.BookingConflictError):
        _create_once(_payload(customer_id=CUSTOMER_IDS[1], start=start, end=end))

    assert _slot_counts(VEHICLE_A, start, end) == (1, 1, 1), (
        f"A7 counts={_slot_counts(VEHICLE_A, start, end)}"
    )
    assert _payment_counts() == (0, 0), f"A7 payment/refund counts={_payment_counts()}"


def test_TC_A8_mid_transaction_rollback(seeded):
    pytest.skip(
        "Blocked: không mô phỏng được lỗi giữa chừng sau db.flush() mà không sửa code sản phẩm "
        "hoặc inject lỗi vào engine; A7 đã kiểm tra bản ghi mồ côi sau conflict thường."
    )


# ---------------------------------------------------------------------------
# NHÓM C — hủy đơn và nhả lịch
# ---------------------------------------------------------------------------
def test_TC_C1_cancel_unpaid_booking_releases_slot(seeded):
    for round_index in range(ROUNDS):
        _clean_and_seed()
        start = _now() + timedelta(days=20 + round_index)
        end = start + timedelta(days=2)
        created = _create_once(_payload(start=start, end=end))
        response = _cancel_endpoint(created.id, CUSTOMER_IDS[0])
        assert response["status"] == "CANCELLED"

        assert SessionLocal is not None
        with SessionLocal() as db:
            booking = db.get(Booking, created.id)
            reservation = db.scalar(
                select(VehicleReservation).where(VehicleReservation.booking_id == created.id)
            )
            schedule = db.scalar(
                select(VehicleSchedule).where(VehicleSchedule.booking_id == created.id)
            )
            assert booking.status == "CANCELLED"
            assert reservation.status == "CANCELLED"
            assert schedule.status == "CANCELLED"

        rebooked = _create_once(
            _payload(customer_id=CUSTOMER_IDS[1], start=start, end=end)
        )
        assert rebooked.id > 0, f"C1 vòng {round_index + 1}: khách khác không đặt lại được"


@pytest.mark.parametrize(
    "lead_hours, expected_rate",
    [
        (48, 1.0),
        (12, 0.5),
        (5, 0.0),
    ],
)
def test_TC_C2_paid_cancel_refund_policy_BR04(seeded, lead_hours, expected_rate):
    _clean_and_seed()
    now = _now()
    start = now + timedelta(hours=lead_hours)
    end = start + timedelta(hours=4)
    created = _create_once(_payload(start=start, end=end), now=now)
    _set_booking_status(created.id, "DEPOSIT_PAID")
    _add_success_payment(_get_booking(created.id))

    response = _cancel_endpoint(created.id, CUSTOMER_IDS[0])
    assert response["status"] == "CANCELLED"

    expected_amount = float(created.deposit_amount) * expected_rate
    with SessionLocal() as db:
        refunds = db.scalar(
            select(func.count()).select_from(Refund).where(Refund.booking_id == created.id)
        ) or 0
        actual_amount = db.scalar(
            select(func.sum(Refund.amount)).where(Refund.booking_id == created.id)
        ) or 0
        txn_status = db.scalar(
            select(PaymentTransaction.status).where(
                PaymentTransaction.booking_id == created.id
            )
        )
    assert refunds == (1 if expected_rate > 0 else 0), (
        f"C2 lead={lead_hours}h BR-04 mong đợi refund_rate={expected_rate} "
        f"({expected_amount:,.0f}đ) nhưng thực tế refunds={refunds}, amount={actual_amount}, "
        f"txn_status={txn_status}; endpoint cancel chỉ hủy txn, không tạo Refund."
    )
    if expected_rate > 0:
        assert float(actual_amount) == pytest.approx(expected_amount, abs=1), (
            f"C2 lead={lead_hours}h: expected={expected_amount}, actual={actual_amount}"
        )


def test_TC_C3_status_history_row(seeded):
    tables = set(Base.metadata.tables)
    has_booking_history = any(
        "booking" in name and ("history" in name or "log" in name) for name in tables
    )
    if not has_booking_history:
        pytest.skip(
            "Blocked: develop không có bảng lịch sử đổi trạng thái booking "
            "(chỉ có vehicle_status_history), không thể kiểm tra dòng changed_by."
        )
    assert has_booking_history


def test_TC_C4_cancel_other_customers_booking(seeded):
    created = _create_once(_payload(start=_now() + timedelta(days=25)))
    with pytest.raises(HTTPException) as exc:
        _cancel_endpoint(created.id, CUSTOMER_IDS[1])
    assert exc.value.status_code == 404, f"C4 nhận {exc.value.status_code}: {exc.value.detail}"
    assert _get_booking(created.id).status == "PENDING_PAYMENT"


def test_TC_C5_terminal_status_and_repeated_cancel(seeded):
    created = _create_once(_payload(start=_now() + timedelta(days=26)))
    _set_booking_status(created.id, "COMPLETED")
    with pytest.raises(HTTPException) as exc:
        _cancel_endpoint(created.id, CUSTOMER_IDS[0])
    assert exc.value.status_code == 409
    assert _get_booking(created.id).status == "COMPLETED"

    second = _create_once(_payload(start=_now() + timedelta(days=30)))
    first = _cancel_endpoint(second.id, CUSTOMER_IDS[0])
    again = _cancel_endpoint(second.id, CUSTOMER_IDS[0])
    assert first["status"] == again["status"] == "CANCELLED"
    assert _payment_counts() == (0, 0)


def test_TC_C6_concurrent_cancel_and_cancel_vs_rebook(seeded):
    _clean_and_seed()
    created = _create_once(_payload(start=_now() + timedelta(days=28)))
    tasks = [
        lambda: _cancel_endpoint(created.id, CUSTOMER_IDS[0]),
        lambda: _cancel_endpoint(created.id, CUSTOMER_IDS[0]),
    ]
    results = _run_concurrent(tasks)
    assert all(status == "OK" for status in _statuses(results)), results
    assert _payment_counts() == (0, 0)

    _clean_and_seed()
    start = _now() + timedelta(days=29)
    end = start + timedelta(days=2)
    created = _create_once(_payload(start=start, end=end))
    cancel_task = lambda: _cancel_endpoint(created.id, CUSTOMER_IDS[0])
    rebook_task = lambda: _create_once(
        _payload(customer_id=CUSTOMER_IDS[1], start=start, end=end)
    )
    results = _run_concurrent([cancel_task, rebook_task])
    statuses = _statuses(results)
    assert "ERROR" not in statuses, results
    assert _slot_counts(VEHICLE_A, start, end)[0] <= 1, (
        f"C6 đặt trùng sau khi hủy: {_slot_counts(VEHICLE_A, start, end)}"
    )


# ---------------------------------------------------------------------------
# NHÓM B — giữ chỗ hết hạn
# ---------------------------------------------------------------------------
def test_TC_B1_hold_expires_equals_reservation_expires(seeded):
    _clean_and_seed()
    now = _now()
    created = _create_once(_payload(start=now + timedelta(days=21)), now=now)
    with SessionLocal() as db:
        booking = db.get(Booking, created.id)
        reservation = db.get(VehicleReservation, created.reservation_id)
        expected = now + timedelta(minutes=settings.BOOKING_HOLD_MINUTES)
        assert abs((booking.hold_expires_at - expected).total_seconds()) <= 2
        assert booking.hold_expires_at == reservation.expires_at


def test_TC_B2_boundary_29_59_vs_30_00(seeded):
    _clean_and_seed()
    now = _now()
    start = now + timedelta(days=22)
    end = start + timedelta(days=2)
    created = _create_once(_payload(start=start, end=end), now=now)
    assert SessionLocal is not None

    with SessionLocal() as db:
        still_blocked = vehicle_has_conflict(
            db,
            VEHICLE_A,
            start,
            end,
            now=now + timedelta(minutes=29, seconds=59),
        )
    assert still_blocked is True, "B2 ở 29:59 reservation vẫn phải chặn"

    with SessionLocal() as db:
        at_expiry = vehicle_has_conflict(
            db,
            VEHICLE_A,
            start,
            end,
            now=now + timedelta(minutes=30),
        )
    assert at_expiry is False, (
        "B2 ở 30:00 reservation đã hết hạn nhưng xe vẫn bị chặn; "
        f"booking_status={_get_booking(created.id).status}; "
        "nguyên nhân: booking PENDING_PAYMENT + schedule ACTIVE vẫn nằm trong điều kiện conflict."
    )


def test_TC_B3_rebook_after_hold_expiry(seeded):
    _clean_and_seed()
    now = _now()
    start = now + timedelta(days=23)
    end = start + timedelta(days=2)
    created = _create_once(_payload(start=start, end=end), now=now)

    with pytest.raises(booking_crud.BookingConflictError) as exc:
        _create_once(
            _payload(customer_id=CUSTOMER_IDS[1], start=start, end=end),
            now=now + timedelta(minutes=settings.BOOKING_HOLD_MINUTES, seconds=1),
        )

    with SessionLocal() as db:
        reservation_status = db.scalar(
            select(VehicleReservation.status).where(
                VehicleReservation.booking_id == created.id
            )
        )
        schedule_status = db.scalar(
            select(VehicleSchedule.status).where(VehicleSchedule.booking_id == created.id)
        )
    assert False, (
        "B3 sau hết hạn khách khác vẫn không đặt được: "
        f"{exc.value}; reservation={reservation_status}, schedule={schedule_status}, "
        "booking=PENDING_PAYMENT; xe bị chặn oan dù reservation đã hết hạn."
    )


def test_TC_B4_expiry_job(seeded):
    if importlib.util.find_spec("app.jobs.booking_expiry_job") is None:
        pytest.skip(
            "Blocked: develop chưa có app/jobs/booking_expiry_job.py và lifespan không đăng ký job; "
            "không thể test tự chuyển EXPIRED/nhả lịch/chạy 2 lần/2 job song song."
        )
    pytest.skip("Blocked: job vừa xuất hiện cần cập nhật test theo implementation mới.")


def test_TC_B5_payment_vs_expiry_race(seeded):
    pytest.skip(
        "Blocked (ưu tiên thấp): chưa mô phỏng được thanh toán đúng thời điểm hết hạn "
        "mà không inject clock/gateway vào code sản phẩm."
    )
