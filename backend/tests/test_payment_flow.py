from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
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
from app.models.payment import PaymentTransaction, PaymentWebhookLog, Refund
from app.models.user import User
from app.models.vehicle import Vehicle
from app.routers import payment as payment_router
from app.routers.payment import router
from app.services.payos_service import (
    PayOSService,
    _url_for_booking,
    settings as payos_settings,
)


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


def test_payos_redirect_urls_keep_booking_id():
    assert _url_for_booking(
        "https://ridehub.example/payment?source=payos",
        9401,
    ) == "https://ridehub.example/payment?source=payos&booking_id=9401"


def test_payos_beneficiary_details_normalize_aliases_and_config_fallback(monkeypatch):
    service = PayOSService()
    details = service.normalize_beneficiary_details(
        {
            "bankName": "Test Bank",
            "accountNumber": "123456789",
            "accountName": "RIDEHUB TEST",
        }
    )
    assert details["bank_name"] == "Test Bank"
    assert details["account_number"] == "123456789"
    assert details["account_name"] == "RIDEHUB TEST"
    assert details["beneficiary_source"] == "PayOS"

    monkeypatch.setattr(payos_settings, "PAYOS_BANK_NAME", "Local Bank")
    monkeypatch.setattr(payos_settings, "PAYOS_ACCOUNT_NUMBER", "987654321")
    monkeypatch.setattr(payos_settings, "PAYOS_ACCOUNT_NAME", "LOCAL HOLDER")
    fallback = service.normalize_beneficiary_details({})
    assert fallback["bank_name"] == "Local Bank"
    assert fallback["account_number"] == "987654321"
    assert fallback["account_name"] == "LOCAL HOLDER"
    assert fallback["beneficiary_source"] == "Cấu hình PAYOS_* trong .env"


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
    assert first.json()["bank_name"] == "MB Bank"
    assert first.json()["account_number"] == "123456"
    assert first.json()["account_name"] == "RideHub"
    assert calls[0]["amount"] == 200000

    second = client.post(
        "/api/payments/deposit/payos",
        json={"booking_id": 9401},
    )
    assert second.status_code == 201, second.text
    assert second.json()["transaction_id"] == first.json()["transaction_id"]
    assert len(calls) == 1
    with session_factory() as db:
        transaction = db.query(payment_router.PaymentTransaction).one()
        assert transaction.bank_name == "MB Bank"
        assert transaction.bank_bin == "970422"
        assert transaction.account_number == "123456"
        assert transaction.account_name == "RideHub"


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


def test_failed_legacy_refund_gateway_does_not_update_payment(
    payment_client, monkeypatch
):
    client, app, session_factory = payment_client
    with session_factory() as db:
        db.add(
            PaymentTransaction(
                booking_id=9401,
                transaction_code="PAYOS_REFUND_FAILED",
                provider="PAYOS",
                amount=Decimal("200000"),
                status="SUCCESS",
            )
        )
        db.commit()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=900,
        role="admin",
    )
    monkeypatch.setattr(
        payment_router.payment_gateway_service,
        "process_refund",
        lambda **_kwargs: {"status": "FAILED"},
    )

    response = client.post(
        "/api/payments/refund",
        json={"transaction_code": "PAYOS_REFUND_FAILED"},
    )

    assert response.status_code == 502
    with session_factory() as db:
        transaction = (
            db.query(PaymentTransaction)
            .filter_by(transaction_code="PAYOS_REFUND_FAILED")
            .one()
        )
        assert transaction.status == "SUCCESS"
        assert db.get(Booking, 9401).status == "PENDING_PAYMENT"
        assert db.query(Refund).count() == 0


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


def test_failed_transaction_reports_reason_and_expired_hold(payment_client):
    client, _, session_factory = payment_client
    with session_factory() as db:
        booking = db.get(Booking, 9401)
        booking.hold_expires_at = datetime.now() - timedelta(seconds=1)
        db.add(
            PaymentTransaction(
                booking_id=9401,
                transaction_code="PAYOS_123458",
                provider="PAYOS",
                amount=Decimal("200000"),
                status="FAILED",
            )
        )
        db.add(
            PaymentWebhookLog(
                transaction_code="PAYOS_123458",
                process_result="FAILED",
                queue_reason="Ngân hàng từ chối giao dịch.",
            )
        )
        db.commit()

    response = client.get("/api/payments/booking/9401/status")
    assert response.status_code == 200
    assert response.json()["payment_status"] == "EXPIRED"
    assert response.json()["failure_reason"] == "Ngân hàng từ chối giao dịch."
    assert response.json()["paid_at"] is None


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
                bank_name="MB Bank",
                bank_bin="970422",
                account_number="123456",
                account_name="RideHub",
                beneficiary_source="PayOS (tên ngân hàng suy ra từ BIN)",
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
    assert response.json()["paid_at"]
    assert response.json()["bank_name"] == "MB Bank"
    assert response.json()["bin"] == "970422"
    assert response.json()["account_number"] == "123456"
    assert response.json()["account_name"] == "RideHub"
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

    async def accept_signature(_payload):
        return True

    monkeypatch.setattr(
        payment_router.payos_service,
        "verify_payment_webhook_data",
        accept_signature,
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


def _seed_pending_payos_transaction(session_factory, order_code):
    with session_factory() as db:
        db.add(
            PaymentTransaction(
                booking_id=9401,
                transaction_code=f"PAYOS_{order_code}",
                provider="PAYOS",
                provider_txn_id=f"payos-link-{order_code}",
                amount=Decimal("200000"),
                status="PENDING",
                payment_method="QR_CODE",
            )
        )
        db.commit()


def _payos_webhook_body(order_code, amount):
    return {
        "code": "00",
        "desc": "success",
        "success": True,
        "data": {
            "orderCode": order_code,
            "amount": amount,
            "description": "Coc xe don 9401",
            "reference": f"bank-ref-{order_code}",
        },
        "signature": "test-signature",
    }


async def _accept_payos_signature(_payload):
    return True


def test_payos_duplicate_webhook_is_idempotent(payment_client, monkeypatch):
    client, _, session_factory = payment_client
    order_code = 123458
    _seed_pending_payos_transaction(session_factory, order_code)
    monkeypatch.setattr(
        payment_router.payos_service,
        "verify_payment_webhook_data",
        _accept_payos_signature,
    )
    body = _payos_webhook_body(order_code, 200000)

    first = client.post("/api/payments/webhook/payos", json=body)
    with session_factory() as db:
        paid_at = (
            db.query(PaymentTransaction)
            .filter_by(transaction_code=f"PAYOS_{order_code}")
            .one()
            .paid_at
        )
    duplicate = client.post("/api/payments/webhook/payos", json=body)

    assert first.status_code == duplicate.status_code == 200
    assert first.json()["status"] == duplicate.json()["status"] == "OK"
    assert "Idempotent" in duplicate.json()["message"]
    with session_factory() as db:
        transaction = (
            db.query(PaymentTransaction)
            .filter_by(transaction_code=f"PAYOS_{order_code}")
            .one()
        )
        assert transaction.status == "SUCCESS"
        assert transaction.paid_at == paid_at
        assert db.get(Booking, 9401).status == "DEPOSIT_PAID"
        assert db.query(Refund).count() == 0
        assert [
            log.process_result
            for log in db.query(PaymentWebhookLog)
            .filter_by(transaction_code=f"PAYOS_{order_code}")
            .order_by(PaymentWebhookLog.id)
            .all()
        ] == ["SUCCESS", "IDEMPOTENT_IGNORED"]


def test_payos_webhook_rejects_invalid_signature_without_state_change(
    payment_client, monkeypatch
):
    client, _, session_factory = payment_client
    order_code = 123459
    _seed_pending_payos_transaction(session_factory, order_code)

    monkeypatch.setattr(
        payment_router.payos_service,
        "verify_payment_webhook_data",
        PayOSService(
            client_id="test-client",
            api_key="test-api",
            checksum_key="test-checksum",
        ).verify_payment_webhook_data,
    )
    response = client.post(
        "/api/payments/webhook/payos",
        json=_payos_webhook_body(order_code, 200000),
    )

    assert response.status_code == 401
    with session_factory() as db:
        transaction = (
            db.query(PaymentTransaction)
            .filter_by(transaction_code=f"PAYOS_{order_code}")
            .one()
        )
        log = (
            db.query(PaymentWebhookLog)
            .filter_by(transaction_code=f"PAYOS_{order_code}")
            .one()
        )
        assert transaction.status == "PENDING"
        assert transaction.paid_at is None
        assert db.get(Booking, 9401).status == "PENDING_PAYMENT"
        assert db.query(Refund).count() == 0
        assert log.signature_valid == "INVALID"
        assert log.process_result == "REJECTED_INVALID_SIGNATURE"


@pytest.mark.parametrize(
    ("reported_amount", "direction", "difference"),
    [(199000, "thiếu", "1000"), (201000, "thừa", "1000")],
)
def test_payos_webhook_records_under_and_overpayment(
    payment_client, monkeypatch, reported_amount, direction, difference
):
    client, _, session_factory = payment_client
    order_code = 123460 + (reported_amount > 200000)
    _seed_pending_payos_transaction(session_factory, order_code)
    monkeypatch.setattr(
        payment_router.payos_service,
        "verify_payment_webhook_data",
        _accept_payos_signature,
    )

    response = client.post(
        "/api/payments/webhook/payos",
        json=_payos_webhook_body(order_code, reported_amount),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "OK"
    with session_factory() as db:
        transaction = (
            db.query(PaymentTransaction)
            .filter_by(transaction_code=f"PAYOS_{order_code}")
            .one()
        )
        log = (
            db.query(PaymentWebhookLog)
            .filter_by(transaction_code=f"PAYOS_{order_code}")
            .one()
        )
        assert transaction.status == "AMOUNT_MISMATCH"
        assert db.get(Booking, 9401).status == "PENDING_PAYMENT"
        assert db.query(Refund).count() == 0
        assert log.signature_valid == "VALID"
        assert log.process_result == "AMOUNT_MISMATCH"
        assert log.payload["data"]["amount"] == reported_amount
        assert direction in log.queue_reason
        assert difference in log.queue_reason
