from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.dependencies import get_current_user
from app.db.session import Base, get_db
from app.middleware.audit_log import AuditLogMiddleware
from app.models.booking import Booking, BookingStatusHistory
from app.models.handover import HandoverProtocol
from app.models.payment import PaymentTransaction, Refund
from app.models.store import Store
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.vehicle_reservation import VehicleReservation
from app.models.vehicle_schedule import VehicleSchedule
from app.routers import payment as payment_router
from app.routers.bookings import router
from app.schemas.handover import HandoverCheckinCreate


@pytest.fixture()
def settlement_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)

    now = datetime.now().replace(microsecond=0)
    with testing_session() as db:
        db.add_all(
            [
                User(id=1, full_name="Customer", status="active"),
                User(id=2, full_name="Store owner", status="active"),
                User(id=3, full_name="Outsider", status="active"),
                Store(
                    id=10,
                    owner_user_id=2,
                    name="Settlement store",
                    address="Test",
                    city="HCM",
                    status="APPROVED",
                ),
                Vehicle(
                    id=20,
                    store_id=10,
                    vehicle_type="MOTORBIKE",
                    plate_number="59A-12345",
                    brand="Honda",
                    model="Vision",
                    price_per_day=Decimal("300000"),
                    current_status="AVAILABLE",
                ),
                Booking(
                    id=30,
                    customer_id=1,
                    vehicle_id=20,
                    store_id=10,
                    start_time=now - timedelta(days=2),
                    end_time=now - timedelta(days=1),
                    status="PENDING_SETTLEMENT",
                    rental_amount=Decimal("300000"),
                    delivery_fee=Decimal("0"),
                    deposit_amount=Decimal("200000"),
                    total_amount=Decimal("300000"),
                ),
                HandoverProtocol(
                    protocol_code="SETTLE-CHECKIN-30",
                    booking_id=30,
                    protocol_type="CHECK_IN",
                    store_agent_name="Store owner",
                    customer_name="Customer",
                    customer_cccd="123456789",
                    customer_phone="0900000001",
                    customer_license="A1",
                    handover_location="Store",
                    vehicle_name="Honda Vision",
                    license_plate="59A-12345",
                    status="COMPLETED",
                    both_confirmed=True,
                    fee_overtime=Decimal("10000"),
                    fee_excess_km=Decimal("5000"),
                    fee_fuel=Decimal("3000"),
                    fee_cleaning=Decimal("7000"),
                    fee_damage=Decimal("10000"),
                ),
                PaymentTransaction(
                    booking_id=30,
                    transaction_code="DEPOSIT-30",
                    provider="MOCK_PAY",
                    amount=Decimal("200000"),
                    status="SUCCESS",
                    payment_method="QR_CODE",
                ),
                Refund(
                    booking_id=30,
                    amount=Decimal("25000"),
                    status="SUCCESS",
                ),
                VehicleReservation(
                    vehicle_id=20,
                    customer_id=1,
                    booking_id=30,
                    start_time=now - timedelta(days=2),
                    end_time=now - timedelta(days=1),
                    expires_at=now,
                    status="ACTIVE",
                ),
                VehicleSchedule(
                    vehicle_id=20,
                    booking_id=30,
                    start_time=now - timedelta(days=2),
                    end_time=now - timedelta(days=1),
                    schedule_type="RENTAL",
                    status="ACTIVE",
                ),
            ]
        )
        db.commit()

    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.include_router(payment_router.router, prefix="/api")

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=2,
        role="store_owner",
    )
    with TestClient(app) as client:
        yield client, app, testing_session
    engine.dispose()


def test_settlement_calculates_balance_fees_and_completes_booking(settlement_client):
    client, app, session_factory = settlement_client

    response = client.post(
        "/api/bookings/30/settle",
        json={"payment_method": "BANK_TRANSFER"},
    )

    assert response.status_code == 200, response.text
    result = response.json()
    assert Decimal(result["total_amount"]) == Decimal("300000")
    assert Decimal(result["previously_paid"]) == Decimal("200000")
    assert Decimal(result["refunded_amount"]) == Decimal("25000")
    assert Decimal(result["net_paid"]) == Decimal("175000")
    assert Decimal(result["remaining_amount"]) == Decimal("125000")
    assert result["fee_breakdown"] == {
        "fee_overtime": "10000.00",
        "fee_excess_km": "5000.00",
        "fee_fuel": "3000.00",
        "fee_cleaning": "7000.00",
        "fee_damage": "10000.00",
    }
    assert Decimal(result["extra_fees"]) == Decimal("35000")
    assert Decimal(result["amount_due"]) == Decimal("160000")
    assert result["transaction_status"] == "SUCCESS"
    assert result["payment_method"] == "BANK_TRANSFER"

    with session_factory() as db:
        booking = db.query(Booking).filter_by(id=30).one()
        transaction = (
            db.query(PaymentTransaction)
            .filter(PaymentTransaction.transaction_code == result["transaction_code"])
            .one()
        )
        assert booking.status == "COMPLETED"
        assert transaction.amount == Decimal("160000.00")
        assert transaction.provider == "INTERNAL"
        assert transaction.status == "SUCCESS"
        assert db.query(BookingStatusHistory).filter_by(
            booking_id=30, to_status="COMPLETED"
        ).count() == 1
        assert db.query(VehicleReservation).filter_by(
            booking_id=30
        ).one().status == "COMPLETED"
        assert db.query(VehicleSchedule).filter_by(
            booking_id=30
        ).one().status == "COMPLETED"

    repeated = client.post("/api/bookings/30/settle", json={})
    assert repeated.status_code == 409


def test_settlement_without_remaining_balance_creates_zero_amount_record(
    settlement_client,
):
    client, app, session_factory = settlement_client
    with session_factory() as db:
        db.query(PaymentTransaction).filter_by(transaction_code="DEPOSIT-30").update(
            {PaymentTransaction.amount: Decimal("300000")}
        )
        db.query(Refund).delete()
        db.query(HandoverProtocol).filter_by(booking_id=30).update(
            {
                HandoverProtocol.fee_overtime: Decimal("0"),
                HandoverProtocol.fee_excess_km: Decimal("0"),
                HandoverProtocol.fee_fuel: Decimal("0"),
                HandoverProtocol.fee_cleaning: Decimal("0"),
                HandoverProtocol.fee_damage: Decimal("0"),
            }
        )
        db.commit()

    response = client.post("/api/bookings/30/settle", json={})

    assert response.status_code == 200, response.text
    assert Decimal(response.json()["amount_due"]) == Decimal("0")
    assert response.json()["payment_method"] == "NO_CHARGE"

    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=1,
        role="customer",
    )
    history = client.get("/api/payments/booking/30")
    assert history.status_code == 200, history.text
    assert any(row["amount"] == 0 for row in history.json())


def test_settlement_without_prior_deposit_charges_full_balance_and_fees(
    settlement_client,
):
    client, _, session_factory = settlement_client
    with session_factory() as db:
        db.query(PaymentTransaction).delete()
        db.query(Refund).delete()
        db.commit()

    response = client.post("/api/bookings/30/settle", json={})

    assert response.status_code == 200, response.text
    result = response.json()
    assert Decimal(result["previously_paid"]) == Decimal("0")
    assert Decimal(result["remaining_amount"]) == Decimal("300000")
    assert Decimal(result["amount_due"]) == Decimal("335000")


@pytest.mark.parametrize(
    ("booking_status", "expected_status"),
    [("IN_PROGRESS", 409), ("COMPLETED", 409)],
)
def test_settlement_rejects_invalid_or_completed_booking_state(
    settlement_client, booking_status, expected_status
):
    client, _, session_factory = settlement_client
    with session_factory() as db:
        db.query(Booking).filter_by(id=30).update({Booking.status: booking_status})
        db.commit()

    response = client.post("/api/bookings/30/settle", json={})

    assert response.status_code == expected_status


def test_settlement_returns_404_for_missing_booking(settlement_client):
    client, _, _ = settlement_client

    response = client.post("/api/bookings/999/settle", json={})

    assert response.status_code == 404


def test_settlement_requires_store_permission(settlement_client):
    client, app, _ = settlement_client
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=3,
        role="customer",
    )

    response = client.post("/api/bookings/30/settle", json={})

    assert response.status_code == 403


def test_settlement_requires_authentication(settlement_client):
    client, app, _ = settlement_client
    app.dependency_overrides.pop(get_current_user)

    response = client.post("/api/bookings/30/settle", json={})

    assert response.status_code == 401


def test_settlement_rejects_invalid_request_and_negative_stored_fee(
    settlement_client,
):
    client, _, session_factory = settlement_client

    invalid_method = client.post(
        "/api/bookings/30/settle",
        json={"payment_method": "CRYPTO"},
    )
    assert invalid_method.status_code == 422

    with session_factory() as db:
        db.query(HandoverProtocol).filter_by(booking_id=30).update(
            {HandoverProtocol.fee_damage: Decimal("-1")}
        )
        db.commit()

    invalid_fee = client.post("/api/bookings/30/settle", json={})
    assert invalid_fee.status_code == 422


@pytest.mark.parametrize("invalid_amount", [Decimal("-1"), Decimal("1.001")])
def test_checkin_fee_schema_rejects_negative_or_fractional_currency(
    invalid_amount,
):
    with pytest.raises(ValidationError):
        HandoverCheckinCreate(
            protocol_code="INVALID-FEE",
            booking_id=30,
            odo_checkin=100,
            fuel_checkin="FULL",
            fee_damage=invalid_amount,
        )


def test_settlement_endpoint_is_audited_as_booking_status_change():
    middleware = AuditLogMiddleware(FastAPI())

    rule, groups = middleware._match_audit_rule(
        "POST",
        "/api/bookings/30/settle",
    )

    assert rule["default_action"] == "BOOKING_SETTLEMENT"
    assert groups["resource_id"] == "30"
