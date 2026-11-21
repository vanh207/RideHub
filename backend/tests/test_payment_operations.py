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
from app.core.dependencies import get_current_user
from app.db.session import Base, get_db
from app.middleware.audit_log import AuditLogMiddleware
from app.models.booking import Booking
from app.models.payment import PaymentTransaction, PaymentWebhookLog, Refund
from app.models.user import User
from app.models.vehicle import Vehicle
from app.routers import payment as payment_router
from app.routers.payment import router


@pytest.fixture()
def operations_client():
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
                User(id=101, full_name="Nguyễn An", status="active"),
                Vehicle(
                    id=201,
                    store_id=301,
                    vehicle_type="MOTORBIKE",
                    plate_number="59A-12345",
                    brand="Honda",
                    model="Vision",
                    price_per_day=Decimal("300000"),
                ),
                Booking(
                    id=401,
                    customer_id=101,
                    vehicle_id=201,
                    start_time=now + timedelta(days=1),
                    end_time=now + timedelta(days=2),
                    status="CANCELLED",
                    rental_amount=Decimal("300000"),
                    delivery_fee=Decimal("0"),
                    deposit_amount=Decimal("200000"),
                    total_amount=Decimal("300000"),
                ),
                Booking(
                    id=402,
                    customer_id=101,
                    vehicle_id=201,
                    start_time=now + timedelta(days=3),
                    end_time=now + timedelta(days=4),
                    status="PENDING_PAYMENT",
                    rental_amount=Decimal("300000"),
                    delivery_fee=Decimal("0"),
                    deposit_amount=Decimal("200000"),
                    total_amount=Decimal("300000"),
                ),
                PaymentTransaction(
                    id=501,
                    booking_id=401,
                    transaction_code="RH-PAY-LATE",
                    provider="MOCK_PAY",
                    amount=Decimal("200000"),
                    status="LATE_PAYMENT",
                    provider_txn_id="BANK-LATE-1",
                ),
                PaymentTransaction(
                    id=502,
                    booking_id=402,
                    transaction_code="RH-PAY-MISMATCH",
                    provider="MOCK_PAY",
                    amount=Decimal("200000"),
                    status="PENDING",
                    provider_txn_id="BANK-MISMATCH-1",
                ),
                Refund(
                    id=601,
                    booking_id=401,
                    payment_transaction_id=501,
                    amount=Decimal("200000"),
                    reason="Thanh toán sau khi đơn đã hủy",
                    status="PENDING",
                ),
                PaymentWebhookLog(
                    id=701,
                    transaction_code="RH-PAY-LATE",
                    process_result="LATE_PAYMENT",
                    queue_reason="Thanh toán đến sau khi đơn đã đóng.",
                    processed_at=now,
                ),
                PaymentWebhookLog(
                    id=702,
                    transaction_code="RH-PAY-MISMATCH",
                    process_result="AMOUNT_MISMATCH",
                    queue_reason="Số tiền thanh toán không khớp.",
                    payload={"accountNumber": "must-not-be-returned"},
                    processed_at=now,
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
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=900,
        role="admin",
    )
    with TestClient(app) as client:
        yield client, app, testing_session
    engine.dispose()


def test_operations_queue_returns_anomalies_without_webhook_payload(operations_client):
    client, _, _ = operations_client

    response = client.get("/api/payments/operations/anomalies")

    assert response.status_code == 200
    rows = response.json()
    by_code = {row["transaction_code"]: row for row in rows}
    assert set(by_code) == {"RH-PAY-LATE", "RH-PAY-MISMATCH"}
    assert by_code["RH-PAY-LATE"]["can_refund"] is True
    assert by_code["RH-PAY-LATE"]["refund_status"] == "PENDING"
    assert by_code["RH-PAY-LATE"]["booking_status"] == "CANCELLED"
    assert by_code["RH-PAY-LATE"]["customer_name"] == "Nguyễn An"
    assert by_code["RH-PAY-LATE"]["vehicle_name"] == "Honda Vision"
    assert by_code["RH-PAY-LATE"]["vehicle_plate"] == "59A-12345"
    assert by_code["RH-PAY-MISMATCH"]["can_refund"] is False
    assert "accountNumber" not in response.text


def test_operations_queue_filters_search_and_paginates(operations_client):
    client, _, _ = operations_client

    filtered = client.get(
        "/api/payments/operations/anomalies",
        params={
            "refund_status": "PENDING",
            "transaction_status": "LATE_PAYMENT",
            "anomaly_type": "LATE_PAYMENT",
            "q": "RH-PAY-LATE",
        },
    )
    assert filtered.status_code == 200
    assert [row["transaction_code"] for row in filtered.json()] == ["RH-PAY-LATE"]
    assert filtered.headers["X-Total-Count"] == "1"
    assert filtered.headers["X-Page"] == "1"
    assert filtered.headers["X-Page-Size"] == "200"
    assert filtered.headers["X-Total-Pages"] == "1"

    second_page = client.get(
        "/api/payments/operations/anomalies",
        params={
            "page": 2,
            "page_size": 1,
            "sort_by": "transaction_code",
            "sort_order": "asc",
        },
    )
    assert second_page.status_code == 200
    assert [row["transaction_code"] for row in second_page.json()] == [
        "RH-PAY-MISMATCH"
    ]
    assert second_page.headers["X-Total-Count"] == "2"
    assert second_page.headers["X-Page"] == "2"
    assert second_page.headers["X-Page-Size"] == "1"
    assert second_page.headers["X-Total-Pages"] == "2"


def test_operations_queue_preserves_legacy_limit_parameter(operations_client):
    client, _, _ = operations_client

    response = client.get(
        "/api/payments/operations/anomalies",
        params={"limit": 1},
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.headers["X-Page-Size"] == "1"


def test_operations_queue_rejects_conflicting_pagination_parameters(
    operations_client,
):
    client, _, _ = operations_client

    response = client.get(
        "/api/payments/operations/anomalies",
        params={"limit": 10, "page_size": 20},
    )

    assert response.status_code == 422


def test_operations_queue_openapi_documents_filters_and_pagination_headers():
    app = FastAPI()
    app.include_router(router, prefix="/api")
    operation = app.openapi()["paths"]["/api/payments/operations/anomalies"]["get"]

    parameters = {parameter["name"] for parameter in operation["parameters"]}
    headers = set(operation["responses"]["200"]["headers"])

    assert {
        "page",
        "page_size",
        "refund_status",
        "transaction_status",
        "anomaly_type",
        "q",
        "sort_by",
        "sort_order",
    }.issubset(parameters)
    assert {
        "X-Total-Count",
        "X-Page",
        "X-Page-Size",
        "X-Total-Pages",
    }.issubset(headers)


def test_operations_queue_empty_response(operations_client):
    client, _, session_factory = operations_client
    with session_factory() as db:
        db.query(PaymentWebhookLog).delete()
        db.query(Refund).delete()
        db.query(PaymentTransaction).delete()
        db.commit()

    response = client.get("/api/payments/operations/anomalies")

    assert response.status_code == 200
    assert response.json() == []


def test_confirm_pending_refund_updates_refund_and_transaction(
    operations_client, monkeypatch
):
    client, _, session_factory = operations_client
    gateway_calls = []

    def process_refund(**kwargs):
        gateway_calls.append(kwargs)
        return {"status": "SUCCESS"}

    monkeypatch.setattr(payment_router.payment_gateway_service, "process_refund", process_refund)

    response = client.post(
        "/api/payments/operations/refunds/601/confirm",
        json={"reason": "Đã đối soát với ngân hàng"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "SUCCESS"
    assert response.json()["processed_by"] == 900
    assert response.json()["reason"] == "Đã đối soát với ngân hàng"
    assert gateway_calls[0]["transaction_code"] == "RH-PAY-LATE"
    with session_factory() as db:
        assert db.query(PaymentTransaction).filter_by(id=501).one().status == "REFUNDED"
        assert db.query(Refund).filter_by(id=601).one().status == "SUCCESS"

    duplicate = client.post(
        "/api/payments/operations/refunds/601/confirm",
        json={},
    )
    assert duplicate.status_code == 409


def test_operator_role_can_access_operations_queue(operations_client):
    client, app, _ = operations_client
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=902,
        role="operator",
    )

    response = client.get("/api/payments/operations/anomalies")

    assert response.status_code == 200


def test_failed_gateway_keeps_refund_pending(operations_client, monkeypatch):
    client, _, session_factory = operations_client
    monkeypatch.setattr(
        payment_router.payment_gateway_service,
        "process_refund",
        lambda **_kwargs: {"status": "FAILED"},
    )

    response = client.post(
        "/api/payments/operations/refunds/601/confirm",
        json={},
    )

    assert response.status_code == 502
    with session_factory() as db:
        assert db.query(Refund).filter_by(id=601).one().status == "PENDING"
        assert db.query(PaymentTransaction).filter_by(id=501).one().status == "LATE_PAYMENT"


@pytest.mark.parametrize(
    ("role", "expected_status"),
    [("customer", 403), ("store_owner", 403)],
)
def test_non_operations_roles_cannot_view_or_confirm(operations_client, role, expected_status):
    client, app, _ = operations_client
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=901,
        role=role,
    )

    queue_response = client.get("/api/payments/operations/anomalies")
    refund_response = client.post(
        "/api/payments/operations/refunds/601/confirm",
        json={},
    )

    assert queue_response.status_code == expected_status
    assert refund_response.status_code == expected_status


def test_operations_endpoints_require_login(operations_client):
    client, app, _ = operations_client
    app.dependency_overrides.pop(get_current_user)

    queue_response = client.get("/api/payments/operations/anomalies")
    refund_response = client.post(
        "/api/payments/operations/refunds/601/confirm",
        json={},
    )

    assert queue_response.status_code == 401
    assert refund_response.status_code == 401


def test_cannot_confirm_refund_for_unpaid_transaction(operations_client):
    client, _, session_factory = operations_client
    with session_factory() as db:
        db.add(
            Refund(
                id=602,
                booking_id=402,
                payment_transaction_id=502,
                amount=Decimal("100000"),
                status="PENDING",
            )
        )
        db.commit()

    response = client.post(
        "/api/payments/operations/refunds/602/confirm",
        json={},
    )

    assert response.status_code == 409


def test_confirm_unknown_refund_returns_404(operations_client):
    client, _, _ = operations_client

    response = client.post(
        "/api/payments/operations/refunds/9999/confirm",
        json={},
    )

    assert response.status_code == 404


def test_confirm_refund_rejects_amount_exceeding_paid_transaction(
    operations_client,
):
    client, _, session_factory = operations_client
    with session_factory() as db:
        db.query(Refund).filter_by(id=601).update(
            {Refund.amount: Decimal("250000")}
        )
        db.commit()

    response = client.post(
        "/api/payments/operations/refunds/601/confirm",
        json={},
    )

    assert response.status_code == 409


def test_operations_refund_confirmation_matches_audit_rule():
    middleware = AuditLogMiddleware(FastAPI())

    rule, groups = middleware._match_audit_rule(
        "POST",
        "/api/payments/operations/refunds/601/confirm",
    )

    assert rule["category"] == "REFUND"
    assert groups["resource_id"] == "601"
