from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.dependencies import get_current_customer_id, get_current_user
from app.db.session import Base, get_db
from app.main import app
from app.models.booking import Booking
from app.models.payment import PaymentTransaction, Refund
from app.models.role import Role, UserRole
from app.models.store import Store
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.vehicle_reservation import VehicleReservation
from app.models.vehicle_schedule import VehicleSchedule
from app.crud.booking_cancellation import (
    BookingActor,
    BookingNotFoundError,
    BookingPermissionError,
    BookingStateError,
    cancel_booking,
)

NOW = datetime.now().replace(minute=0, second=0, microsecond=0)
CUSTOMER_ID = 1
OWNER_ID = 2
ADMIN_ID = 3
OTHER_CUSTOMER_ID = 4


def _seed_user(db, user_id: int, role_code: str = "customer"):
    role = db.scalar(select(Role).where(Role.code == role_code))
    if role is None:
        role = Role(code=role_code, name=role_code)
        db.add(role)
        db.flush()
    user = User(id=user_id, email=f"user{user_id}@test.local", full_name=f"User {user_id}")
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user_id, role_id=role.id))
    db.flush()
    db.refresh(user)
    return user


def _seed_booking(db, *, status="DEPOSIT_PAID", hours_before=72, paid=Decimal("1500000")):
    customer = _seed_user(db, CUSTOMER_ID, "customer")
    owner = _seed_user(db, OWNER_ID, "store_owner")
    _seed_user(db, ADMIN_ID, "admin")
    _seed_user(db, OTHER_CUSTOMER_ID, "customer")

    store = Store(
        id=1,
        owner_user_id=owner.id,
        name="Store test",
        address="HCM",
        city="HCM",
        status="APPROVED",
        email="store@test.local",
        business_license="LIC-1",
    )
    db.add(store)
    db.flush()

    vehicle = Vehicle(
        id=1,
        store_id=store.id,
        vehicle_type="CAR",
        plate_number="51A-001",
        brand="Toyota",
        model="Vios",
        price_per_day=Decimal("1000000"),
        price_per_hour=Decimal("100000"),
    )
    db.add(vehicle)
    db.flush()

    start_time = NOW + timedelta(hours=hours_before)
    end_time = start_time + timedelta(hours=4)
    booking = Booking(
        id=1,
        customer_id=customer.id,
        vehicle_id=vehicle.id,
        store_id=store.id,
        start_time=start_time,
        end_time=end_time,
        hold_expires_at=NOW + timedelta(minutes=30),
        status=status,
        rental_amount=Decimal("1000000"),
        delivery_fee=Decimal("0"),
        deposit_amount=Decimal("1500000"),
        total_amount=Decimal("1500000"),
    )
    db.add(booking)
    db.flush()

    reservation = VehicleReservation(
        vehicle_id=vehicle.id,
        customer_id=customer.id,
        booking_id=booking.id,
        start_time=start_time,
        end_time=end_time,
        expires_at=NOW + timedelta(minutes=30),
        status="ACTIVE",
    )
    db.add(reservation)
    db.flush()

    schedule = VehicleSchedule(
        vehicle_id=vehicle.id,
        booking_id=booking.id,
        reservation_id=reservation.id,
        schedule_type="RENTAL",
        start_time=start_time,
        end_time=end_time,
        status="ACTIVE",
    )
    db.add(schedule)

    if paid > 0:
        db.add(
            PaymentTransaction(
                booking_id=booking.id,
                transaction_code="TXN-001",
                provider="MOCK",
                amount=paid,
                status="SUCCESS",
                paid_at=NOW,
            )
        )
    db.commit()
    return booking, customer, owner


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = session_local()
    yield db, session_local, engine
    db.close()
    engine.dispose()


def test_customer_cancel_full_refund_and_release(db_session):
    db, _, _ = db_session
    booking, customer, _ = _seed_booking(db)

    result = cancel_booking(
        db,
        booking.id,
        actor=BookingActor(id=customer.id, role="customer"),
        reason="Không còn nhu cầu",
        now=NOW,
    )

    assert result.status == "CANCELLED"
    assert result.refund.policy_code == "FREE_CANCEL"
    assert result.refund.amount == Decimal("1500000.00")
    assert result.reservation_released is True
    assert result.schedule_released is True

    db.refresh(booking)
    assert booking.status == "CANCELLED"
    assert booking.cancelled_by == "CUSTOMER"
    assert "FREE_CANCEL" in booking.cancel_reason

    refund = db.scalar(select(Refund).where(Refund.booking_id == booking.id))
    assert refund is not None
    assert refund.amount == Decimal("1500000.00")

    reservation = db.scalar(select(VehicleReservation).where(VehicleReservation.booking_id == booking.id))
    schedule = db.scalar(select(VehicleSchedule).where(VehicleSchedule.booking_id == booking.id))
    assert reservation.status == "EXPIRED"
    assert schedule.status == "CANCELLED"


def test_cancel_is_idempotent(db_session):
    db, _, _ = db_session
    booking, customer, _ = _seed_booking(db)
    actor = BookingActor(id=customer.id, role="customer")

    first = cancel_booking(db, booking.id, actor=actor, reason="Hủy", now=NOW)
    second = cancel_booking(db, booking.id, actor=actor, reason="Hủy lần 2", now=NOW)

    assert first.already_cancelled is False
    assert second.already_cancelled is True
    assert second.refund_id == first.refund_id
    assert db.scalars(select(Refund).where(Refund.booking_id == booking.id)).all().__len__() == 1


def test_other_customer_cannot_cancel(db_session):
    db, _, _ = db_session
    booking, _, _ = _seed_booking(db)

    with pytest.raises(BookingPermissionError):
        cancel_booking(
            db,
            booking.id,
            actor=BookingActor(id=OTHER_CUSTOMER_ID, role="customer"),
            reason="Hủy giúp",
            now=NOW,
        )


def test_store_owner_can_cancel_with_full_refund(db_session):
    db, _, _ = db_session
    booking, _, owner = _seed_booking(db, hours_before=1)

    result = cancel_booking(
        db,
        booking.id,
        actor=BookingActor(id=owner.id, role="store_owner"),
        reason="Xe hỏng",
        now=NOW,
    )

    assert result.refund.policy_code == "STORE_CANCEL"
    assert result.refund.amount == Decimal("1500000.00")


def test_admin_can_cancel_in_progress(db_session):
    db, _, _ = db_session
    booking, _, _ = _seed_booking(db, status="IN_PROGRESS", hours_before=-1)

    result = cancel_booking(
        db,
        booking.id,
        actor=BookingActor(id=ADMIN_ID, role="admin"),
        reason="Hủy bởi admin",
        now=NOW,
    )

    assert result.refund.policy_code == "NO_REFUND"
    assert result.refund.amount == Decimal("0.00")


def test_completed_booking_cannot_cancel(db_session):
    db, _, _ = db_session
    booking, _, _ = _seed_booking(db, status="COMPLETED", hours_before=-5)

    with pytest.raises(BookingStateError):
        cancel_booking(
            db,
            booking.id,
            actor=BookingActor(id=ADMIN_ID, role="admin"),
            reason="Hủy nhầm",
            now=NOW,
        )


def test_missing_booking_raises_not_found(db_session):
    db, _, _ = db_session
    _seed_booking(db)

    with pytest.raises(BookingNotFoundError):
        cancel_booking(
            db,
            999,
            actor=BookingActor(id=ADMIN_ID, role="admin"),
            reason="Hủy",
            now=NOW,
        )


def test_api_cancel_endpoint(db_session):
    db, session_local, _ = db_session
    booking, customer, _ = _seed_booking(db)
    user = db.get(User, customer.id)

    app.dependency_overrides[get_db] = lambda: session_local()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_customer_id] = lambda: customer.id
    client = TestClient(app)

    response = client.post(
        f"/api/bookings/{booking.id}/cancel",
        json={"reason": "Không đi được"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "CANCELLED"
    assert body["refund"]["policy_code"] == "FREE_CANCEL"
    assert float(body["refund"]["amount"]) == 1500000.0

    app.dependency_overrides.clear()
