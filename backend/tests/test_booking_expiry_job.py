from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.crud.booking_cancellation import expire_hold_bookings
from app.db.session import Base
from app.models.booking import Booking
from app.models.payment import PaymentTransaction, Refund
from app.models.store import Store
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.vehicle_reservation import VehicleReservation
from app.models.vehicle_schedule import VehicleSchedule
from app.services.payment_booking_reconciliation import apply_successful_payment_to_booking

NOW = datetime(2026, 2, 1, 10, 0, 0)


def _seed(db, *, status="PENDING_PAYMENT", paid=False):
    user = User(id=1, email="customer@test.local", full_name="Customer")
    db.add(user)
    db.flush()

    store = Store(
        id=1,
        owner_user_id=1,
        name="Store expiry",
        address="HCM",
        city="HCM",
        status="APPROVED",
        business_license="EXP-1",
    )
    db.add(store)
    db.flush()

    vehicle = Vehicle(
        id=1,
        store_id=1,
        vehicle_type="CAR",
        plate_number="51A-999",
        brand="Toyota",
        model="Vios",
        price_per_day=Decimal("1000000"),
    )
    db.add(vehicle)
    db.flush()

    start_time = NOW + timedelta(hours=5)
    end_time = start_time + timedelta(hours=4)
    booking = Booking(
        id=1,
        customer_id=1,
        vehicle_id=1,
        store_id=1,
        start_time=start_time,
        end_time=end_time,
        hold_expires_at=NOW - timedelta(minutes=1),
        status=status,
        rental_amount=Decimal("1000000"),
        deposit_amount=Decimal("1500000"),
        total_amount=Decimal("1500000"),
    )
    db.add(booking)
    db.flush()

    reservation = VehicleReservation(
        vehicle_id=1,
        customer_id=1,
        booking_id=1,
        start_time=start_time,
        end_time=end_time,
        expires_at=NOW - timedelta(minutes=1),
        status="ACTIVE",
    )
    db.add(reservation)
    db.flush()

    schedule = VehicleSchedule(
        vehicle_id=1,
        booking_id=1,
        reservation_id=reservation.id,
        schedule_type="RENTAL",
        start_time=start_time,
        end_time=end_time,
        status="ACTIVE",
    )
    db.add(schedule)

    transaction = PaymentTransaction(
        booking_id=1,
        transaction_code="EXP-TXN",
        provider="MOCK",
        amount=Decimal("1500000"),
        status="SUCCESS" if paid else "PENDING",
    )
    db.add(transaction)
    db.commit()
    return booking, transaction


def _make_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return engine, session_local, session_local()


def test_expire_hold_releases_inventory():
    engine, _, db = _make_db()
    try:
        booking, transaction = _seed(db)

        result = expire_hold_bookings(db, now=NOW)

        assert result.scanned == 1
        assert result.expired == 1
        assert result.paid_race == 0
        db.refresh(booking)
        assert booking.status == "EXPIRED"
        assert booking.cancelled_by == "SYSTEM"
        assert "HOLD_EXPIRED" in booking.cancel_reason
        db.refresh(transaction)
        assert transaction.status == "EXPIRED"

        assert db.scalar(select(VehicleReservation.status).where(VehicleReservation.booking_id == 1)) == "EXPIRED"
        assert db.scalar(select(VehicleSchedule.status).where(VehicleSchedule.booking_id == 1)) == "CANCELLED"
        assert db.scalar(select(Refund.id).where(Refund.booking_id == 1)) is None
    finally:
        db.close()
        engine.dispose()


def test_paid_hold_is_not_expired():
    engine, _, db = _make_db()
    try:
        booking, _ = _seed(db, paid=True)

        result = expire_hold_bookings(db, now=NOW)

        assert result.scanned == 1
        assert result.paid_race == 1
        assert result.expired == 0
        db.refresh(booking)
        assert booking.status == "DEPOSIT_PAID"
    finally:
        db.close()
        engine.dispose()


def test_payment_after_expiry_creates_pending_refund():
    engine, _, db = _make_db()
    try:
        booking, transaction = _seed(db, status="EXPIRED", paid=True)

        outcome = apply_successful_payment_to_booking(db, booking, transaction)
        db.commit()

        assert outcome == "REFUND_REQUIRED"
        db.refresh(booking)
        assert booking.status == "EXPIRED"
        refund = db.scalar(select(Refund).where(Refund.booking_id == booking.id))
        assert refund is not None
        assert refund.status == "PENDING"
        assert "PAID_AFTER_EXPIRED" in refund.reason
    finally:
        db.close()
        engine.dispose()
