from datetime import date, datetime
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
from app.models.booking import Booking
from app.models.handover import HandoverProtocol
from app.models.payment import PaymentTransaction, PaymentWebhookLog, Refund
from app.models.user import User
from app.models.vehicle import Vehicle
from app.routers import payment, reports


@pytest.fixture()
def platform_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)

    report_time = datetime(2026, 1, 15, 12, 0)
    with testing_session() as db:
        db.add_all(
            [
                User(
                    id=1,
                    full_name="Platform Customer",
                    status="active",
                    created_at=datetime(2026, 1, 5),
                ),
                User(
                    id=2,
                    full_name="Inactive Customer",
                    status="disabled",
                    created_at=datetime(2025, 12, 1),
                ),
                Vehicle(
                    id=20,
                    store_id=10,
                    vehicle_type="MOTORBIKE",
                    plate_number="59A-10001",
                    brand="Honda",
                    model="Vision",
                    price_per_day=Decimal("300000"),
                    current_status="AVAILABLE",
                    is_active=True,
                    created_at=report_time,
                ),
                Booking(
                    id=30,
                    customer_id=1,
                    vehicle_id=20,
                    start_time=datetime(2026, 1, 14),
                    end_time=datetime(2026, 1, 16),
                    status="COMPLETED",
                    rental_amount=Decimal("300000"),
                    delivery_fee=Decimal("0"),
                    deposit_amount=Decimal("100000"),
                    total_amount=Decimal("300000"),
                    created_at=report_time,
                ),
                Booking(
                    id=31,
                    customer_id=1,
                    vehicle_id=20,
                    start_time=datetime(2026, 1, 17),
                    end_time=datetime(2026, 1, 18),
                    status="CANCELLED",
                    rental_amount=Decimal("100000"),
                    delivery_fee=Decimal("0"),
                    deposit_amount=Decimal("0"),
                    total_amount=Decimal("100000"),
                    created_at=report_time,
                ),
                PaymentTransaction(
                    id=101,
                    booking_id=30,
                    transaction_code="PAYOS_1001",
                    provider="PAYOS",
                    provider_txn_id="GW-1",
                    amount=Decimal("100.00"),
                    status="SUCCESS",
                    created_at=report_time,
                    paid_at=report_time,
                ),
                PaymentTransaction(
                    id=102,
                    booking_id=30,
                    transaction_code="PAYOS_1002",
                    provider="PAYOS",
                    provider_txn_id="GW-2",
                    amount=Decimal("200.00"),
                    status="PENDING",
                    created_at=report_time,
                ),
                PaymentTransaction(
                    id=103,
                    booking_id=30,
                    transaction_code="PAYOS_1003",
                    provider="PAYOS",
                    amount=Decimal("300.00"),
                    status="FAILED",
                    created_at=report_time,
                ),
                PaymentTransaction(
                    id=104,
                    booking_id=31,
                    transaction_code="PAYOS_1004",
                    provider="PAYOS",
                    amount=Decimal("400.00"),
                    status="LATE_PAYMENT",
                    created_at=report_time,
                    paid_at=report_time,
                ),
                PaymentTransaction(
                    id=105,
                    booking_id=31,
                    transaction_code="PAYOS_1005",
                    provider="PAYOS",
                    amount=Decimal("50.00"),
                    status="AMOUNT_MISMATCH",
                    created_at=report_time,
                ),
                PaymentTransaction(
                    id=106,
                    booking_id=31,
                    transaction_code="PAYOS_1006",
                    provider="PAYOS",
                    amount=Decimal("75.00"),
                    status="REFUNDED",
                    created_at=report_time,
                    paid_at=report_time,
                ),
                Refund(
                    id=201,
                    booking_id=30,
                    payment_transaction_id=102,
                    amount=Decimal("40.00"),
                    status="PENDING",
                    created_at=report_time,
                ),
                Refund(
                    id=202,
                    booking_id=31,
                    payment_transaction_id=106,
                    amount=Decimal("25.00"),
                    status="SUCCESS",
                    created_at=report_time,
                ),
                HandoverProtocol(
                    id=301,
                    protocol_code="REPORT-CHECKIN-30",
                    booking_id=30,
                    protocol_type="CHECK_IN",
                    store_agent_name="Store Operator",
                    customer_name="Platform Customer",
                    customer_cccd="123456789",
                    customer_phone="0900000000",
                    customer_license="A1",
                    handover_location="Store",
                    vehicle_name="Honda Vision",
                    license_plate="59A-10001",
                    fee_overtime=Decimal("10.00"),
                    fee_excess_km=Decimal("5.00"),
                    fee_fuel=Decimal("5.00"),
                    fee_cleaning=Decimal("5.00"),
                    fee_damage=Decimal("5.00"),
                    created_at=report_time,
                ),
                PaymentWebhookLog(
                    id=401,
                    transaction_code="PAYOS_1004",
                    signature_valid="INVALID",
                    process_result="REJECTED_INVALID_SIGNATURE",
                    processed_at=report_time,
                    created_at=report_time,
                ),
                PaymentWebhookLog(
                    id=402,
                    transaction_code="PAYOS_1005",
                    signature_valid="VALID",
                    process_result="AMOUNT_MISMATCH",
                    processed_at=report_time,
                    created_at=report_time,
                ),
            ]
        )
        db.commit()

    app = FastAPI()
    app.include_router(payment.router, prefix="/api")
    app.include_router(reports.router, prefix="/api")

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
        yield client, app
    engine.dispose()


def statement_payload():
    return {
        "provider": "PAYOS",
        "gateway_transactions": [
            {
                "transaction_code": "PAYOS_1001",
                "provider_txn_id": "GW-1",
                "amount": "100.00",
                "status": "PAID",
                "occurred_at": "2026-01-15T12:00:00",
            },
            {
                "transaction_code": "PAYOS_1002",
                "provider_txn_id": "GW-2",
                "amount": "250.00",
                "status": "PAID",
                "occurred_at": "2026-01-15T12:30:00",
            },
            {
                "transaction_code": "PAYOS_9999",
                "provider_txn_id": "GW-9999",
                "amount": "50.00",
                "status": "PAID",
                "occurred_at": "2026-01-15T13:00:00",
            },
        ],
    }


def test_reconciliation_classifies_matched_mismatched_and_missing(platform_client):
    client, _ = platform_client

    response = client.post(
        "/api/payments/operations/reconciliation",
        params={"from_date": "2026-01-15", "to_date": "2026-01-15"},
        json=statement_payload(),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    summary = body["summary"]
    assert summary["total_count"] == 7
    assert summary["matched_count"] == 1
    assert summary["mismatched_count"] == 1
    assert summary["missing_gateway_count"] == 4
    assert summary["missing_local_count"] == 1
    assert Decimal(summary["local_amount_total"]) == Decimal("1125.00")
    assert Decimal(summary["gateway_amount_total"]) == Decimal("400.00")
    assert Decimal(summary["difference_amount_total"]) == Decimal("-725.00")
    assert summary["pending_refund_count"] == 1
    assert Decimal(summary["pending_refund_amount"]) == Decimal("40.00")
    assert Decimal(summary["completed_refund_amount"]) == Decimal("25.00")

    by_code = {item["transaction_code"]: item for item in body["transactions"]}
    assert by_code["PAYOS_1001"]["reconciliation_status"] == "MATCHED"
    assert by_code["PAYOS_1002"]["reconciliation_status"] == "MISMATCHED"
    assert by_code["PAYOS_1002"]["anomaly_types"] == ["PENDING_REFUND"]
    assert by_code["PAYOS_1003"]["reconciliation_status"] == "MISSING_GATEWAY"
    assert by_code["PAYOS_9999"]["reconciliation_status"] == "MISSING_LOCAL"


def test_reconciliation_filters_by_status_search_and_date(platform_client):
    client, _ = platform_client
    payload = statement_payload()
    payload["gateway_transactions"].append(
        {
            "transaction_code": "PAYOS-OUT-OF-RANGE",
            "amount": "70.00",
            "status": "PAID",
            "occurred_at": "2026-01-16T00:00:00",
        }
    )

    response = client.post(
        "/api/payments/operations/reconciliation",
        params={
            "from_date": "2026-01-15",
            "to_date": "2026-01-15",
            "status": "MISMATCHED",
            "q": "PAYOS_1002",
        },
        json=payload,
    )

    assert response.status_code == 200, response.text
    assert response.json()["summary"]["total_count"] == 1
    assert response.json()["transactions"][0]["transaction_code"] == "PAYOS_1002"

    booking_search = client.post(
        "/api/payments/operations/reconciliation",
        params={
            "from_date": "2026-01-15",
            "to_date": "2026-01-15",
            "q": "30",
        },
        json=payload,
    )
    assert booking_search.status_code == 200
    assert {
        row["transaction_code"] for row in booking_search.json()["transactions"]
    } == {"PAYOS_1001", "PAYOS_1002", "PAYOS_1003"}


def test_reconciliation_is_read_only_and_idempotent(platform_client):
    client, _ = platform_client
    before = client.get(
        "/api/reports/platform",
        params={"from_date": "2026-01-15", "to_date": "2026-01-15"},
    ).json()["payments"]
    request_params = {
        "from_date": "2026-01-15",
        "to_date": "2026-01-15",
    }

    first = client.post(
        "/api/payments/operations/reconciliation",
        params=request_params,
        json=statement_payload(),
    )
    second = client.post(
        "/api/payments/operations/reconciliation",
        params=request_params,
        json=statement_payload(),
    )
    after = client.get(
        "/api/reports/platform",
        params={"from_date": "2026-01-15", "to_date": "2026-01-15"},
    ).json()["payments"]

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert after == before


def test_reconciliation_returns_empty_result_without_local_or_gateway_rows(
    platform_client,
):
    client, _ = platform_client

    response = client.post(
        "/api/payments/operations/reconciliation",
        params={"from_date": "2024-01-01", "to_date": "2024-01-02"},
        json={"provider": "PAYOS", "gateway_transactions": []},
    )

    assert response.status_code == 200
    assert response.json()["transactions"] == []
    assert response.json()["summary"]["total_count"] == 0
    assert Decimal(response.json()["summary"]["local_amount_total"]) == 0
    assert Decimal(response.json()["summary"]["gateway_amount_total"]) == 0


def test_reconciliation_can_match_by_provider_transaction_id(platform_client):
    client, _ = platform_client

    response = client.post(
        "/api/payments/operations/reconciliation",
        params={"from_date": "2026-01-15", "to_date": "2026-01-15"},
        json={
            "provider": "PAYOS",
            "gateway_transactions": [
                {
                    "provider_txn_id": "GW-1",
                    "amount": "100.00",
                    "status": "PAID",
                    "occurred_at": "2026-01-15T12:00:00",
                }
            ],
        },
    )

    assert response.status_code == 200
    item = response.json()["transactions"][0]
    assert item["reconciliation_status"] == "MATCHED"
    assert item["transaction_code"] == "PAYOS_1001"
    assert item["gateway_transaction_code"] is None


@pytest.mark.parametrize(
    "params",
    [
        {"from_date": "2026-01-16", "to_date": "2026-01-15"},
        {"from_date": "not-a-date", "to_date": "2026-01-15"},
    ],
)
def test_reconciliation_rejects_invalid_date_filters(platform_client, params):
    client, _ = platform_client

    response = client.post(
        "/api/payments/operations/reconciliation",
        params=params,
        json=statement_payload(),
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "invalid_statement",
    [
        {"provider": "PAYOS", "gateway_transactions": [{"amount": -1}]},
        {
            "provider": "PAYOS",
            "gateway_transactions": [
                {
                    "transaction_code": "INVALID-STATUS",
                    "amount": 1,
                    "status": "UNKNOWN",
                    "occurred_at": "2026-01-15T12:00:00",
                }
            ],
        },
        {
            "provider": "PAYOS",
            "gateway_transactions": [
                {
                    "transaction_code": "DUP",
                    "amount": 1,
                    "status": "PAID",
                    "occurred_at": "2026-01-15T12:00:00",
                },
                {
                    "transaction_code": "DUP",
                    "amount": 1,
                    "status": "PAID",
                    "occurred_at": "2026-01-15T12:00:00",
                },
            ],
        },
    ],
)
def test_reconciliation_rejects_invalid_or_duplicate_statement_rows(
    platform_client, invalid_statement
):
    client, _ = platform_client

    response = client.post(
        "/api/payments/operations/reconciliation",
        params={"from_date": "2026-01-15", "to_date": "2026-01-15"},
        json=invalid_statement,
    )

    assert response.status_code == 422


def test_platform_report_aggregates_money_statuses_and_entities(platform_client):
    client, _ = platform_client

    response = client.get(
        "/api/reports/platform",
        params={"from_date": "2026-01-01", "to_date": "2026-01-31"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["currency"] == "VND"
    assert body["payments"]["transaction_count"] == 6
    assert body["payments"]["transactions_by_status"] == {
        "SUCCESS": 1,
        "PENDING": 1,
        "FAILED": 1,
        "LATE_PAYMENT": 1,
        "AMOUNT_MISMATCH": 1,
        "REFUNDED": 1,
    }
    assert body["payments"]["captured_count"] == 3
    assert Decimal(body["payments"]["captured_amount"]) == Decimal("575.00")
    assert Decimal(body["payments"]["completed_refund_amount"]) == Decimal("25.00")
    assert Decimal(body["payments"]["net_collected_amount"]) == Decimal("550.00")
    assert body["refunds"]["pending_count"] == 1
    assert Decimal(body["refunds"]["pending_amount"]) == Decimal("40.00")
    assert body["bookings"]["booking_count"] == 2
    assert body["bookings"]["bookings_by_status"] == {
        "COMPLETED": 1,
        "CANCELLED": 1,
    }
    assert body["extra_fee_count"] == 1
    assert Decimal(body["extra_fee_amount"]) == Decimal("30.00")
    assert body["platform"]["user_count"] == 2
    assert body["platform"]["active_user_count"] == 1
    assert body["platform"]["new_user_count"] == 1
    assert body["platform"]["vehicle_count"] == 1
    assert body["platform"]["active_vehicle_count"] == 1
    assert body["anomalies"] == {
        "amount_mismatch_count": 1,
        "late_payment_count": 1,
        "pending_refund_count": 1,
        "invalid_signature_webhook_count": 1,
        "failed_webhook_count": 1,
    }


def test_platform_report_returns_zero_totals_for_empty_period(platform_client):
    client, _ = platform_client

    response = client.get(
        "/api/reports/platform",
        params={"from_date": "2024-01-01", "to_date": "2024-01-31"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["payments"]["transaction_count"] == 0
    assert body["payments"]["captured_amount"] == "0.00"
    assert body["payments"]["net_collected_amount"] == "0.00"
    assert body["refunds"]["refund_count"] == 0
    assert body["bookings"]["booking_count"] == 0
    assert body["extra_fee_count"] == 0
    assert body["extra_fee_amount"] == "0.00"
    assert body["anomalies"]["pending_refund_count"] == 0


def test_platform_report_rejects_invalid_date_range(platform_client):
    client, _ = platform_client

    response = client.get(
        "/api/reports/platform",
        params={"from_date": "2026-01-16", "to_date": "2026-01-15"},
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "path,method",
    [
        ("/api/payments/operations/reconciliation", "post"),
        ("/api/reports/platform", "get"),
    ],
)
def test_admin_apis_require_authentication(platform_client, path, method):
    client, app = platform_client
    app.dependency_overrides.pop(get_current_user)

    if method == "post":
        response = client.post(
            path,
            params={"from_date": "2026-01-15", "to_date": "2026-01-15"},
            json={"provider": "PAYOS", "gateway_transactions": []},
        )
    else:
        response = client.get(path)

    assert response.status_code == 401


@pytest.mark.parametrize(
    "path,method",
    [
        ("/api/payments/operations/reconciliation", "post"),
        ("/api/reports/platform", "get"),
    ],
)
def test_admin_apis_reject_non_operations_roles(platform_client, path, method):
    client, app = platform_client
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=901,
        role="customer",
    )

    if method == "post":
        response = client.post(
            path,
            params={"from_date": "2026-01-15", "to_date": "2026-01-15"},
            json={"provider": "PAYOS", "gateway_transactions": []},
        )
    else:
        response = client.get(path)

    assert response.status_code == 403
