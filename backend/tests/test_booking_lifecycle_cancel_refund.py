"""TF19B54 — Kiểm thử vòng đời đơn thuê, hủy đơn và hoàn tiền.

Chạy bắt buộc trên MySQL 8 thật, database có tên chứa "test":

    cd backend
    TEST_DATABASE_URL='mysql+pymysql://<user>:<pass>@127.0.0.1:3306/ridehub_test?charset=utf8mb4' \
      ../.venv/bin/python -m pytest tests/test_booking_lifecycle_cancel_refund.py -v

File này KHÔNG sửa code sản phẩm. Các kỳ vọng BR-04/FR-35/FR-76 được trích từ
workbook SRS `TestCaseTimKiemDatXeGiuChoHuyDon-1794876312912.xlsx` tìm thấy trên
máy; `SRS_MotoGo.docx` không có trong repo/máy nên cần xác nhận lại khi có file gốc.
Chốt an toàn: nếu thiếu TEST_DATABASE_URL, không phải MySQL, hoặc tên database
không chứa "test" thì toàn bộ test bị skip, không đụng DB làm việc/dev.
"""
from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime as _datetime
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, delete, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app import models  # noqa: F401
from app.core.booking_status import (
    CANONICAL_STATUSES,
    CANCELLED,
    COMPLETED,
    CONFIRMED,
    DEPOSIT_PAID,
    EXPIRED,
    IN_PROGRESS,
    PENDING_PAYMENT,
    PENDING_SETTLEMENT,
)
from app.crud import booking_cancellation as cancellation
from app.crud.vehicle import BOOKING_AVAILABILITY_INDEX, vehicle_has_conflict
from app.db.session import Base
from app.main import app
from app.models.booking import Booking, BookingStatusHistory
from app.models.delivery import DeliveryPoint
from app.models.payment import PaymentTransaction, Refund
from app.models.store import Store
from app.models.user import User
from app.models.vehicle import Vehicle, VehicleStatusHistory
from app.models.vehicle_reservation import VehicleReservation
from app.models.vehicle_schedule import VehicleSchedule
from app.routers.bookings import cancel_booking_endpoint
from app.schemas.booking import BookingCancelRequest
from app.services.cancellation_policy import calculate_refund_quote

pytestmark = pytest.mark.mysql

OWNER_ID = 1954001
CUSTOMER_ID = 1954011
OTHER_CUSTOMER_ID = 1954012
ADMIN_ID = 1954013
STORE_ID = 1954001
VEHICLE_ID = 1954001
DELIVERY_POINT_ID = 1954001
BOOKING_IDS = tuple(range(19540001, 19540080))

SessionLocal: sessionmaker | None = None


def _get_test_database_url() -> str:
    url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL_TEST")
    if not url:
        pytest.skip("Chưa đặt TEST_DATABASE_URL/DATABASE_URL_TEST; không chạy test MySQL.")
    parsed = make_url(url)
    if parsed.get_backend_name() not in {"mysql", "pymysql"}:
        pytest.skip("TEST_DATABASE_URL phải là MySQL để kiểm tra FOR UPDATE/rollback.")
    database = (parsed.database or "").lower()
    if "test" not in database:
        pytest.skip(
            "Chốt an toàn: tên database không chứa 'test' "
            f"(nhận được database='{parsed.database}'); từ chối chạy."
        )
    return url


def _ensure_booking_availability_index(engine) -> None:
    with engine.begin() as conn:
        exists = conn.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.statistics "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'bookings' "
                "AND INDEX_NAME = :index_name"
            ),
            {"index_name": BOOKING_AVAILABILITY_INDEX},
        ).scalar()
        if not exists:
            conn.execute(
                text(
                    f"ALTER TABLE bookings ADD INDEX `{BOOKING_AVAILABILITY_INDEX}` "
                    "(end_time, start_time, status, vehicle_id, hold_expires_at)"
                )
            )


@pytest.fixture(scope="session")
def mysql_engine():
    global SessionLocal
    engine = create_engine(
        _get_test_database_url(), poolclass=NullPool, pool_pre_ping=True
    )
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    Base.metadata.create_all(bind=engine)
    _ensure_booking_availability_index(engine)
    SessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    yield engine
    engine.dispose()


def _clean_test_data() -> None:
    assert SessionLocal is not None
    with SessionLocal() as db:
        booking_ids = BOOKING_IDS
        db.execute(delete(Refund).where(Refund.booking_id.in_(booking_ids)))
        db.execute(
            delete(PaymentTransaction).where(PaymentTransaction.booking_id.in_(booking_ids))
        )
        db.execute(
            delete(BookingStatusHistory).where(
                BookingStatusHistory.booking_id.in_(booking_ids)
            )
        )
        db.execute(
            delete(VehicleStatusHistory).where(VehicleStatusHistory.vehicle_id == VEHICLE_ID)
        )
        db.execute(
            delete(VehicleSchedule).where(VehicleSchedule.vehicle_id == VEHICLE_ID)
        )
        db.execute(
            delete(VehicleReservation).where(VehicleReservation.vehicle_id == VEHICLE_ID)
        )
        db.execute(delete(Booking).where(Booking.id.in_(booking_ids)))
        db.execute(delete(DeliveryPoint).where(DeliveryPoint.id == DELIVERY_POINT_ID))
        db.execute(delete(Vehicle).where(Vehicle.id == VEHICLE_ID))
        db.execute(delete(Store).where(Store.id == STORE_ID))
        db.execute(
            delete(User).where(
                User.id.in_((OWNER_ID, CUSTOMER_ID, OTHER_CUSTOMER_ID, ADMIN_ID))
            )
        )
        db.commit()


@pytest.fixture
def db_session(mysql_engine):
    _clean_test_data()
    with SessionLocal() as db:
        yield db
    _clean_test_data()


@pytest.fixture
def frozen_now(monkeypatch):
    fixed = _datetime.now().replace(microsecond=0)

    class FrozenDatetime(_datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed if tz is None else fixed.replace(tzinfo=tz)

    monkeypatch.setattr(cancellation, "datetime", FrozenDatetime)
    return fixed


@pytest.fixture
def booking_id():
    iterator = iter(BOOKING_IDS)
    return lambda: next(iterator)


def _seed_context(db, *, now: _datetime):
    db.add_all(
        [
            User(id=OWNER_ID, phone="1954000001", full_name="CH TF19B54", status="active"),
            User(id=CUSTOMER_ID, phone="1954000011", full_name="KH TF19B54", status="active"),
            User(id=OTHER_CUSTOMER_ID, phone="1954000012", full_name="KH khác TF19B54", status="active"),
            User(id=ADMIN_ID, phone="1954000013", full_name="Admin TF19B54", status="active"),
            Store(
                id=STORE_ID,
                owner_user_id=OWNER_ID,
                name="Store TF19B54",
                address="122 Hoàng Quốc Việt",
                city="Hà Nội",
                business_license="GP-TF19B54",
                status="APPROVED",
            ),
            Vehicle(
                id=VEHICLE_ID,
                store_id=STORE_ID,
                vehicle_type="MOTORBIKE",
                plate_number="TF19B54-01",
                brand="Honda",
                model="Vision",
                price_per_day=Decimal("150000"),
                price_per_hour=Decimal("30000"),
                current_status="BOOKED",
                is_active=True,
            ),
            DeliveryPoint(
                id=DELIVERY_POINT_ID,
                store_id=STORE_ID,
                name="Điểm giao TF19B54",
                address="Bến xe Mỹ Đình",
                area="Cầu Giấy",
                delivery_fee=Decimal("30000"),
                is_active=True,
            ),
        ]
    )
    db.commit()
    return db.get(Vehicle, VEHICLE_ID)


def _seed_booking(
    db,
    *,
    now: _datetime,
    booking_id: int,
    status: str = DEPOSIT_PAID,
    lead: timedelta = timedelta(hours=25),
    deposit: Decimal = Decimal("540000"),
    paid_amount: Decimal = Decimal("540000"),
    hold_minutes: int = 30,
):
    _seed_context(db, now=now)
    start = now + lead
    end = start + timedelta(hours=4)
    hold_expires = now + timedelta(minutes=hold_minutes)

    booking = Booking(
        id=booking_id,
        customer_id=CUSTOMER_ID,
        vehicle_id=VEHICLE_ID,
        store_id=STORE_ID,
        delivery_point_id=DELIVERY_POINT_ID,
        start_time=start,
        end_time=end,
        hold_expires_at=hold_expires,
        status=status,
        rental_amount=deposit,
        delivery_fee=Decimal("0"),
        deposit_amount=deposit,
        total_amount=deposit,
    )
    db.add(booking)
    db.flush()

    reservation = VehicleReservation(
        vehicle_id=VEHICLE_ID,
        customer_id=CUSTOMER_ID,
        booking_id=booking.id,
        start_time=start,
        end_time=end,
        expires_at=hold_expires,
        status="ACTIVE",
    )
    db.add(reservation)
    db.flush()

    db.add(
        VehicleSchedule(
            vehicle_id=VEHICLE_ID,
            booking_id=booking.id,
            reservation_id=reservation.id,
            schedule_type="RENTAL",
            start_time=start,
            end_time=end,
            status="ACTIVE",
        )
    )

    if paid_amount > 0:
        db.add(
            PaymentTransaction(
                booking_id=booking.id,
                transaction_code=f"TF19B54-{booking_id}",
                provider="MOCK",
                amount=paid_amount,
                status="SUCCESS",
                paid_at=now,
            )
        )
    db.commit()
    db.refresh(booking)
    return booking


def _cancel(db, booking_id: int, *, actor_id: int, role: str, reason: str = "Khách hủy chuyến"):
    return cancel_booking_endpoint(
        booking_id=booking_id,
        payload=BookingCancelRequest(reason=reason),
        db=db,
        current_user=SimpleNamespace(id=actor_id, role=role),
    )


def _refund_of(db, booking_id: int):
    return db.scalar(select(Refund).where(Refund.booking_id == booking_id))


def _active_children(db, booking_id: int):
    reservation = db.scalar(
        select(VehicleReservation).where(
            VehicleReservation.booking_id == booking_id,
            VehicleReservation.status == "ACTIVE",
        )
    )
    schedule = db.scalar(
        select(VehicleSchedule).where(
            VehicleSchedule.booking_id == booking_id,
            VehicleSchedule.status == "ACTIVE",
        )
    )
    return reservation, schedule


# ---------------------------------------------------------------------------
# Nhóm B — hủy đơn và hoàn tiền theo BR-04
# ---------------------------------------------------------------------------


def test_B1_cancel_25h_before_creates_full_refund_with_pending_status(
    db_session, frozen_now, booking_id
):
    db = db_session
    booking = _seed_booking(db, now=frozen_now, booking_id=booking_id())

    result = _cancel(db, booking.id, actor_id=CUSTOMER_ID, role="customer")

    assert result.refund.amount == Decimal("540000.00")
    assert result.refund.policy_code == "FREE_CANCEL"
    assert result.refund_status == "PENDING", (
        "BR-04/TC-HUY-01: refund phải ở PENDING để vận hành viên xác nhận; "
        "hiện luồng hủy gọi gateway và ghi SUCCESS ngay."
    )


@pytest.mark.parametrize(
    "lead, expected_amount",
    [
        (timedelta(hours=24, minutes=1), Decimal("540000.00")),
        (timedelta(hours=24), Decimal("540000.00")),
        (timedelta(hours=23, minutes=59), Decimal("270000.00")),
    ],
)
def test_B2_24h_boundary_refund(
    db_session, frozen_now, booking_id, lead, expected_amount
):
    db = db_session
    booking = _seed_booking(db, now=frozen_now, booking_id=booking_id(), lead=lead)

    result = _cancel(db, booking.id, actor_id=CUSTOMER_ID, role="customer")

    assert result.refund.amount == expected_amount, (
        f"BR-04 boundary lead={lead}: kỳ vọng {expected_amount}, thực tế {result.refund.amount}"
    )


@pytest.mark.parametrize(
    "lead, expected_amount",
    [
        (timedelta(hours=6, minutes=1), Decimal("270000.00")),
        (timedelta(hours=6), Decimal("270000.00")),
        (timedelta(hours=5, minutes=59), Decimal("0.00")),
    ],
)
def test_B3_6h_boundary_refund(
    db_session, frozen_now, booking_id, lead, expected_amount
):
    db = db_session
    booking = _seed_booking(db, now=frozen_now, booking_id=booking_id(), lead=lead)

    result = _cancel(db, booking.id, actor_id=CUSTOMER_ID, role="customer")

    assert result.refund.amount == expected_amount, (
        f"BR-04 boundary lead={lead}: kỳ vọng {expected_amount}, thực tế {result.refund.amount}"
    )


@pytest.mark.parametrize("lead", [timedelta(minutes=30), timedelta(hours=-1)])
def test_B4_late_and_after_start_no_refund(db_session, frozen_now, booking_id, lead):
    db = db_session
    booking = _seed_booking(db, now=frozen_now, booking_id=booking_id(), lead=lead)

    result = _cancel(db, booking.id, actor_id=CUSTOMER_ID, role="customer")

    assert result.refund.amount == Decimal("0.00")
    assert result.refund_id is None


def test_B5_unpaid_pending_payment_cancels_without_refund(
    db_session, frozen_now, booking_id
):
    db = db_session
    booking = _seed_booking(
        db,
        now=frozen_now,
        booking_id=booking_id(),
        status=PENDING_PAYMENT,
        paid_amount=Decimal("0"),
    )

    result = _cancel(db, booking.id, actor_id=CUSTOMER_ID, role="customer")

    assert result.status == CANCELLED
    assert result.refund.amount == Decimal("0.00")
    assert result.refund_id is None
    assert result.reservation_released and result.schedule_released


def test_B6_rounding_half_up(db_session, frozen_now):
    quote = calculate_refund_quote(
        booking_status=DEPOSIT_PAID,
        start_time=frozen_now + timedelta(hours=23, minutes=59),
        deposit_amount=Decimal("100.05"),
        paid_amount=Decimal("100.05"),
        cancelled_at=frozen_now,
        cancelled_by="CUSTOMER",
        now=frozen_now,
    )

    assert quote.amount == Decimal("50.03"), (
        "Giả định làm tròn ROUND_HALF_UP theo code; SRS gốc chưa xác nhận cách làm tròn."
    )


def test_B7_only_paid_booking_can_refund(db_session, frozen_now, booking_id):
    db = db_session
    booking = _seed_booking(
        db, now=frozen_now, booking_id=booking_id(), paid_amount=Decimal("0")
    )

    result = _cancel(db, booking.id, actor_id=CUSTOMER_ID, role="customer")

    assert result.refund.policy_code == "NO_PAYMENT"
    assert _refund_of(db, booking.id) is None


def test_B8_duplicate_cancel_is_idempotent(db_session, frozen_now, booking_id):
    db = db_session
    booking = _seed_booking(db, now=frozen_now, booking_id=booking_id())

    first = _cancel(db, booking.id, actor_id=CUSTOMER_ID, role="customer")
    second = _cancel(db, booking.id, actor_id=CUSTOMER_ID, role="customer", reason="Hủy lại")

    assert first.already_cancelled is False
    assert second.already_cancelled is True
    assert second.refund_id == first.refund_id
    assert len(db.scalars(select(Refund).where(Refund.booking_id == booking.id)).all()) == 1


def test_B9_refund_preview_capability_available():
    paths = {getattr(route, "path", "") for route in app.routes}
    assert any("refund-preview" in path for path in paths), (
        "FR-35: không có endpoint xem trước số tiền hoàn trước khi xác nhận hủy."
    )


@pytest.mark.parametrize(
    "actor_id, role, expected_amount",
    [
        (CUSTOMER_ID, "customer", Decimal("0.00")),
        (OWNER_ID, "store_owner", Decimal("540000.00")),
        (ADMIN_ID, "admin", Decimal("540000.00")),
    ],
)
def test_B10_actor_dependent_refund(
    db_session, frozen_now, booking_id, actor_id, role, expected_amount
):
    db = db_session
    booking = _seed_booking(
        db, now=frozen_now, booking_id=booking_id(), lead=timedelta(hours=1)
    )

    result = _cancel(db, booking.id, actor_id=actor_id, role=role)

    expected_actor = {
        "customer": "CUSTOMER",
        "store_owner": "STORE",
        "admin": "ADMIN",
    }[role]
    assert result.refund.amount == expected_amount
    assert result.cancelled_by == expected_actor


# ---------------------------------------------------------------------------
# Nhóm A — vòng đời và ma trận chuyển trạng thái
# ---------------------------------------------------------------------------

EXPECTED_TRANSITIONS = {
    PENDING_PAYMENT: {DEPOSIT_PAID, EXPIRED, CANCELLED},
    DEPOSIT_PAID: {CONFIRMED, CANCELLED},
    CONFIRMED: {IN_PROGRESS, CANCELLED},
    IN_PROGRESS: {PENDING_SETTLEMENT},
    PENDING_SETTLEMENT: {COMPLETED},
    COMPLETED: set(),
    CANCELLED: set(),
    EXPIRED: set(),
}


@pytest.mark.parametrize("current", sorted(CANONICAL_STATUSES))
@pytest.mark.parametrize("target", sorted(CANONICAL_STATUSES))
def test_A1_state_transition_matrix(current, target):
    from app.core.booking_status import can_transition

    expected = target in EXPECTED_TRANSITIONS.get(current, set())
    assert can_transition(current, target) is expected, (
        "Ma trận chuyển trạng thái kỳ vọng (suy từ FR-30/33/35 + luồng tất toán; "
        "cần đối chiếu SRS gốc): "
        f"{current} -> {target} expected={expected}"
    )


def test_A2_happy_path_deposit_paid_to_cancelled(db_session, frozen_now, booking_id):
    db = db_session
    booking = _seed_booking(db, now=frozen_now, booking_id=booking_id())

    result = _cancel(db, booking.id, actor_id=CUSTOMER_ID, role="customer")

    assert result.status == CANCELLED
    db.refresh(booking)
    assert booking.status == CANCELLED
    assert booking.cancelled_at == frozen_now


@pytest.mark.parametrize(
    "status", [IN_PROGRESS, PENDING_SETTLEMENT, COMPLETED, EXPIRED]
)
def test_A3_invalid_cancel_transitions_rejected_without_changes(
    db_session, frozen_now, booking_id, status
):
    db = db_session
    booking = _seed_booking(
        db, now=frozen_now, booking_id=booking_id(), status=status
    )

    with pytest.raises(HTTPException) as exc_info:
        _cancel(db, booking.id, actor_id=CUSTOMER_ID, role="customer")
    assert exc_info.value.status_code == 409

    db.refresh(booking)
    assert booking.status == status


@pytest.mark.parametrize("status", [COMPLETED, EXPIRED])
def test_A4_terminal_states_cannot_be_reopened(db_session, frozen_now, booking_id, status):
    db = db_session
    booking = _seed_booking(
        db, now=frozen_now, booking_id=booking_id(), status=status
    )
    before = len(db.scalars(select(BookingStatusHistory).where(
        BookingStatusHistory.booking_id == booking.id
    )).all())

    with pytest.raises(HTTPException) as exc_info:
        _cancel(db, booking.id, actor_id=CUSTOMER_ID, role="customer")
    assert exc_info.value.status_code == 409

    after = len(db.scalars(select(BookingStatusHistory).where(
        BookingStatusHistory.booking_id == booking.id
    )).all())
    db.refresh(booking)
    assert booking.status == status
    assert after == before


def test_A5_cancel_writes_status_history(db_session, frozen_now, booking_id):
    db = db_session
    booking = _seed_booking(db, now=frozen_now, booking_id=booking_id())

    _cancel(db, booking.id, actor_id=CUSTOMER_ID, role="customer")

    history = db.scalar(
        select(BookingStatusHistory).where(
            BookingStatusHistory.booking_id == booking.id
        )
    )
    assert history is not None
    assert history.from_status == DEPOSIT_PAID
    assert history.to_status == CANCELLED
    assert history.changed_by == "CUSTOMER"
    assert history.created_at == frozen_now


@pytest.mark.parametrize("legacy_status", ["PENDING", "BOOKED"])
def test_A6_legacy_status_aliases_normalized(
    db_session, frozen_now, booking_id, legacy_status
):
    db = db_session
    booking = _seed_booking(
        db, now=frozen_now, booking_id=booking_id(), status=legacy_status
    )

    result = _cancel(db, booking.id, actor_id=CUSTOMER_ID, role="customer")

    assert result.status == CANCELLED
    history = db.scalar(
        select(BookingStatusHistory).where(
            BookingStatusHistory.booking_id == booking.id
        )
    )
    expected_from = (
        PENDING_PAYMENT if legacy_status == "PENDING" else DEPOSIT_PAID
    )
    assert history.from_status == expected_from


def test_A7_hold_expiry_boundary_29m59_and_30m00(
    db_session, frozen_now, booking_id
):
    db = db_session
    booking = _seed_booking(
        db,
        now=frozen_now,
        booking_id=booking_id(),
        status=PENDING_PAYMENT,
        paid_amount=Decimal("0"),
    )

    before = cancellation.expire_hold_bookings(
        db, now=frozen_now + timedelta(minutes=29, seconds=59)
    )
    assert before.expired == 0
    db.refresh(booking)
    assert booking.status == PENDING_PAYMENT

    at_boundary = cancellation.expire_hold_bookings(
        db, now=frozen_now + timedelta(minutes=30)
    )
    assert at_boundary.expired == 1
    db.refresh(booking)
    assert booking.status == EXPIRED
    assert booking.cancelled_by == "SYSTEM"
    assert _active_children(db, booking.id) == (None, None)


# ---------------------------------------------------------------------------
# Nhóm C — nhất quán dữ liệu, rollback, phân quyền và đồng thời
# ---------------------------------------------------------------------------


def test_C1_cancel_releases_slot_for_rebooking(db_session, frozen_now, booking_id):
    db = db_session
    booking = _seed_booking(db, now=frozen_now, booking_id=booking_id())
    start, end = booking.start_time, booking.end_time

    assert vehicle_has_conflict(db, VEHICLE_ID, start, end, now=frozen_now) is True

    _cancel(db, booking.id, actor_id=CUSTOMER_ID, role="customer")

    assert vehicle_has_conflict(db, VEHICLE_ID, start, end, now=frozen_now) is False
    assert _active_children(db, booking.id) == (None, None)


def test_C2_cancel_does_not_change_vehicle_current_status(
    db_session, frozen_now, booking_id
):
    db = db_session
    booking = _seed_booking(db, now=frozen_now, booking_id=booking_id())
    vehicle = db.get(Vehicle, VEHICLE_ID)
    assert vehicle.current_status == "BOOKED"

    _cancel(db, booking.id, actor_id=CUSTOMER_ID, role="customer")

    db.refresh(vehicle)
    assert vehicle.current_status == "BOOKED"


def test_C3_refund_columns_are_consistent(db_session, frozen_now, booking_id):
    db = db_session
    booking = _seed_booking(db, now=frozen_now, booking_id=booking_id())

    result = _cancel(db, booking.id, actor_id=CUSTOMER_ID, role="customer")
    refund = _refund_of(db, booking.id)

    assert refund is not None
    assert refund.booking_id == booking.id
    assert refund.amount == Decimal("540000.00")
    assert refund.amount == Decimal(str(result.refund.amount))
    assert "FREE_CANCEL" in (refund.reason or "")
    assert refund.processed_by is None


def test_C4_failed_status_history_rolls_back_cancel(
    db_session, frozen_now, booking_id, monkeypatch
):
    db = db_session
    booking = _seed_booking(db, now=frozen_now, booking_id=booking_id())

    def _boom(*args, **kwargs):
        raise RuntimeError("Lỗi giả lập khi ghi lịch sử trạng thái")

    monkeypatch.setattr(cancellation, "record_booking_status_change", _boom)

    with pytest.raises(RuntimeError):
        _cancel(db, booking.id, actor_id=CUSTOMER_ID, role="customer")
    db.rollback()

    db.refresh(booking)
    assert booking.status == DEPOSIT_PAID
    assert booking.cancelled_at is None
    assert _refund_of(db, booking.id) is None
    assert _active_children(db, booking.id) != (None, None)


@pytest.mark.parametrize(
    "actor_id, role",
    [
        (OTHER_CUSTOMER_ID, "customer"),
        (CUSTOMER_ID, "store_staff"),
    ],
)
def test_C5_unrelated_actors_cannot_cancel(
    db_session, frozen_now, booking_id, actor_id, role
):
    db = db_session
    booking = _seed_booking(db, now=frozen_now, booking_id=booking_id())

    with pytest.raises(HTTPException) as exc_info:
        _cancel(db, booking.id, actor_id=actor_id, role=role)
    assert exc_info.value.status_code == 403

    db.refresh(booking)
    assert booking.status == DEPOSIT_PAID
    assert _refund_of(db, booking.id) is None


def test_C6_concurrent_cancel_under_lock_has_no_error(
    mysql_engine, frozen_now, booking_id
):
    booking_id_value = booking_id()

    with SessionLocal() as seed_db:
        _seed_booking(seed_db, now=frozen_now, booking_id=booking_id_value)

    errors: list[str] = []

    def _worker() -> None:
        try:
            with SessionLocal() as db:
                _cancel(db, booking_id_value, actor_id=CUSTOMER_ID, role="customer")
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}")

    with SessionLocal() as locker:
        locked = locker.execute(
            select(Booking).where(Booking.id == booking_id_value).with_for_update()
        ).scalar_one()
        assert locked.id == booking_id_value
        with ThreadPoolExecutor(max_workers=1) as executor:
            list(executor.map(lambda _: _worker(), range(1)))

    assert not errors, (
        "Hủy đơn khi dòng booking đang bị khóa phải chờ hoặc trả kết quả idempotent; "
        f"thực tế lỗi: {errors}"
    )

    with SessionLocal() as verify_db:
        refunds = verify_db.scalars(
            select(Refund).where(Refund.booking_id == booking_id_value)
        ).all()
        assert len(refunds) <= 1
