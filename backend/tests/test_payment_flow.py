from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.core.config import Settings
from app.core.dependencies import get_current_user
from app.db.session import Base, get_db
from app.models.booking import Booking
from app.models.payment import PaymentTransaction
from app.models.user import User
from app.models.vehicle import Vehicle
from app.routers import payment as payment_router
from app.routers.payment import router


def test_placeholder_secrets_are_replaced_with_random_values():
    first = Settings(
        JWT_SECRET_KEY="your_strong_random_jwt_secret_here",
        PAYMENT_GATEWAY_SECRET="your_mock_webhook_secret_here",
    )
    second = Settings(
        JWT_SECRET_KEY="your_strong_random_jwt_secret_here",
        PAYMENT_GATEWAY_SECRET="your_mock_webhook_secret_here",
    )

    assert first.JWT_SECRET_KEY != "your_strong_random_jwt_secret_here"
    assert first.PAYMENT_GATEWAY_SECRET != "your_mock_webhook_secret_here"
    assert first.JWT_SECRET_KEY != second.JWT_SECRET_KEY
    assert first.PAYMENT_GATEWAY_SECRET != second.PAYMENT_GATEWAY_SECRET


@pytest.fixture()
def payment_client():
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
                User(id=9101, full_name="Owner", status="active"),
                User(id=9102, full_name="Other", status="active"),
                Vehicle(
                    id=9201,
                    store_id=9301,
                    vehicle_type="MOTORBIKE",
                    plate_number="TEST-9201",
                    brand="Honda",
                    model="Vision",
                    price_per_day=Decimal("300000"),
                    is_active=True,
                ),
                Booking(
                    id=9401,
                    customer_id=9101,
                    vehicle_id=9201,
                    store_id=9301,
                    start_time=now + timedelta(days=2),
                    end_time=now + timedelta(days=3),
                    hold_expires_at=now + timedelta(minutes=30),
                    status="PENDING_PAYMENT",
                    rental_amount=Decimal("300000"),
                    delivery_fee=Decimal("0"),
                    deposit_amount=Decimal("200000"),
                    total_amount=Decimal("300000"),
                ),
            ]
        )
        db.commit()

    app = FastAPI()
    app.include_router(router, prefix="/api")

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: User(
        id=9101,
        status="active",
    )
    with TestClient(app) as client:
        yield client, app, testing_session
    engine.dispose()


def test_payment_status_requires_login_and_booking_ownership(payment_client):
    client, app, _ = payment_client
    app.dependency_overrides.pop(get_current_user)
    assert client.get("/api/payments/booking/9401/status").status_code == 401

    app.dependency_overrides[get_current_user] = lambda: User(
        id=9102,
        status="active",
    )
    response = client.get("/api/payments/booking/9401/status")
    assert response.status_code == 404


def test_payment_creation_uses_booking_and_reuses_pending_transaction(
    payment_client, monkeypatch
):
    client, _, session_factory = payment_client
    calls = []

    async def create_link(**kwargs):
        calls.append(kwargs)
        return {
            "order_code": 123456789,
            "payment_link_id": "payos-link-1",
            "checkout_url": "https://pay.payos.vn/web/123",
            "qr_code": "PAYOS-QR-DATA",
            "qr_code_url": "https://api.qrserver.com/v1/create-qr-code/?size=350x350",
            "account_number": "123456",
            "account_name": "RideHub",
            "bin": "970422",
            "description": kwargs["description"],
        }

    monkeypatch.setattr(
        payment_router.payos_service,
        "create_deposit_payment_link",
        create_link,
    )
    monkeypatch.setattr(
        payment_router,
        "check_customer_can_rent",
        lambda *_args, **_kwargs: type(
            "Eligibility", (), {"eligible": True, "first_reason": lambda self: None}
        )(),
    )

    first = client.post(
        "/api/payments/deposit/payos",
        json={"booking_id": 9401, "amount": 1},
    )
    assert first.status_code == 201, first.text
    assert first.json()["amount"] == 200000
    assert first.json()["hold_expires_at"]
    assert calls[0]["amount"] == 200000

    second = client.post(
        "/api/payments/deposit/payos",
        json={"booking_id": 9401},
    )
    assert second.status_code == 201, second.text
    assert second.json()["transaction_id"] == first.json()["transaction_id"]
    assert len(calls) == 1
    with session_factory() as db:
        assert db.query(payment_router.PaymentTransaction).count() == 1


def test_customer_cannot_simulate_or_refund_payments(payment_client):
    client, _, _ = payment_client
    simulated = client.post(
        "/api/payments/simulate",
        json={"transaction_code": "PAYOS_123"},
    )
    refunded = client.post(
        "/api/payments/refund",
        json={"transaction_code": "PAYOS_123"},
    )
    assert simulated.status_code == 403
    assert refunded.status_code == 403


def test_expired_hold_is_terminal_and_releases_booking(payment_client):
    client, _, session_factory = payment_client
    with session_factory() as db:
        booking = db.get(Booking, 9401)
        booking.hold_expires_at = datetime.now() - timedelta(seconds=1)
        db.commit()

    response = client.get("/api/payments/booking/9401/status")
    assert response.status_code == 200
    assert response.json()["payment_status"] == "EXPIRED"
    assert response.json()["remaining_seconds"] == 0
    with session_factory() as db:
        assert db.get(Booking, 9401).status == "CANCELLED"


def test_status_polling_syncs_paid_payos_link(payment_client, monkeypatch):
    client, _, session_factory = payment_client
    with session_factory() as db:
        db.add(
            PaymentTransaction(
                booking_id=9401,
                transaction_code="PAYOS_123456",
                provider="PAYOS",
                provider_txn_id="payos-link-1",
                amount=Decimal("200000"),
                status="PENDING",
                payment_method="QR_CODE",
                qr_code_url="https://api.qrserver.com/v1/create-qr-code/",
            )
        )
        db.commit()

    async def get_paid_link(_order_code):
        return SimpleNamespace(status="PAID", amountPaid=200000)

    monkeypatch.setattr(
        payment_router.payos_service,
        "get_payment_link_information",
        get_paid_link,
    )
    response = client.get("/api/payments/booking/9401/status")
    assert response.status_code == 200
    assert response.json()["payment_status"] == "SUCCESS"
    with session_factory() as db:
        assert db.get(Booking, 9401).status == "BOOKED"


def test_payos_webhook_rejects_amount_mismatch(payment_client, monkeypatch):
    client, _, session_factory = payment_client
    with session_factory() as db:
        db.add(
            PaymentTransaction(
                booking_id=9401,
                transaction_code="PAYOS_123457",
                provider="PAYOS",
                provider_txn_id="payos-link-2",
                amount=Decimal("200000"),
                status="PENDING",
                payment_method="QR_CODE",
            )
        )
        db.commit()

    monkeypatch.setattr(
        payment_router.payos_service,
        "verify_payment_webhook_data",
        lambda _payload: True,
    )
    response = client.post(
        "/api/payments/webhook/payos",
        json={
            "code": "00",
            "desc": "success",
            "success": True,
            "data": {
                "orderCode": 123457,
                "amount": 199999,
                "description": "Coc xe don 9401",
            },
            "signature": "valid",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "OK"
    with session_factory() as db:
        transaction = (
            db.query(PaymentTransaction)
            .filter(PaymentTransaction.transaction_code == "PAYOS_123457")
            .one()
        )
        assert transaction.status == "AMOUNT_MISMATCH"
        assert db.get(Booking, 9401).status == "PENDING_PAYMENT"
