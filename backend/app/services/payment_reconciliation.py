from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import String, cast, func, or_
from sqlalchemy.orm import Session

from app.models.payment import PaymentTransaction, PaymentWebhookLog, Refund
from app.schemas.reconciliation import (
    GatewayReconciliationRequest,
    PaymentReconciliationResponse,
    ReconciliationItem,
    ReconciliationSummary,
)

MONEY_QUANT = Decimal("0.01")
COMPLETED_REFUND_STATUSES = {"SUCCESS", "REFUNDED"}
TRACKED_REFUND_STATUSES = COMPLETED_REFUND_STATUSES | {"PENDING"}
GATEWAY_STATUS_MAP = {
    "PAID": "SUCCESS",
    "SUCCESS": "SUCCESS",
    "PENDING": "PENDING",
    "PROCESSING": "PENDING",
    "FAILED": "FAILED",
    "CANCELLED": "CANCELLED",
    "CANCELED": "CANCELLED",
    "EXPIRED": "EXPIRED",
    "REFUNDED": "REFUNDED",
}
LOCAL_PAYMENT_STATUS_MAP = {
    "LATE_PAYMENT": "SUCCESS",
}
WEBHOOK_ANOMALIES = {
    "AMOUNT_MISMATCH",
    "LATE_PAYMENT",
    "REJECTED_INVALID_SIGNATURE",
    "REJECTED_NO_ORDER_CODE",
    "NOT_FOUND",
}


def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(MONEY_QUANT)


def _within_period(value: datetime, from_date: date, to_date: date) -> bool:
    return from_date <= value.date() <= to_date


def _refund_data(db: Session, transaction_ids: list[int]) -> dict[int, dict]:
    if not transaction_ids:
        return {}
    rows = (
        db.query(Refund)
        .filter(
            Refund.payment_transaction_id.in_(transaction_ids),
            Refund.status.in_(TRACKED_REFUND_STATUSES),
        )
        .order_by(Refund.id)
        .all()
    )
    result: dict[int, dict] = {}
    for refund in rows:
        entry = result.setdefault(
            refund.payment_transaction_id,
            {
                "status": None,
                "amount": Decimal("0.00"),
                "pending_amount": Decimal("0.00"),
                "completed_amount": Decimal("0.00"),
                "has_pending": False,
            },
        )
        amount = _money(refund.amount)
        entry["amount"] += amount
        if refund.status == "PENDING":
            entry["pending_amount"] += amount
            entry["has_pending"] = True
        else:
            entry["completed_amount"] += amount
            entry["status"] = refund.status
    for entry in result.values():
        if entry["has_pending"]:
            entry["status"] = "PENDING"
    return result


def _latest_anomalous_webhook_logs(
    db: Session, transaction_codes: list[str]
) -> dict[str, str]:
    if not transaction_codes:
        return {}
    rows = (
        db.query(PaymentWebhookLog)
        .filter(PaymentWebhookLog.transaction_code.in_(transaction_codes))
        .order_by(PaymentWebhookLog.id)
        .all()
    )
    latest = {row.transaction_code: row.process_result for row in rows}
    return {
        transaction_code: result
        for transaction_code, result in latest.items()
        if result in WEBHOOK_ANOMALIES
    }


def _local_anomalies(
    transaction: PaymentTransaction,
    refund: dict,
    webhook_result: str | None,
) -> list[str]:
    anomalies = []
    if transaction.status in {"AMOUNT_MISMATCH", "LATE_PAYMENT"}:
        anomalies.append(transaction.status)
    if refund.get("has_pending"):
        anomalies.append("PENDING_REFUND")
    elif refund.get("completed_amount", Decimal("0.00")) > 0:
        anomalies.append("REFUNDED")
    if webhook_result and webhook_result not in anomalies:
        anomalies.append(webhook_result)
    return anomalies


def _make_item(
    *,
    local: PaymentTransaction | None,
    gateway,
    reconciliation_status: str,
    refund: dict | None = None,
    webhook_result: str | None = None,
) -> ReconciliationItem:
    refund = refund or {}
    local_amount = _money(local.amount) if local else None
    gateway_amount = _money(gateway.amount) if gateway else None
    difference = _money((gateway_amount or 0) - (local_amount or 0))
    local_status = local.status if local else None
    gateway_status = gateway.status if gateway else None
    anomaly_types = (
        _local_anomalies(local, refund, webhook_result) if local else []
    )
    if (
        local
        and gateway
        and local.provider_txn_id
        and gateway.provider_txn_id
        and local.provider_txn_id != gateway.provider_txn_id
    ):
        anomaly_types.append("PROVIDER_TXN_ID_MISMATCH")

    return ReconciliationItem(
        reconciliation_status=reconciliation_status,
        transaction_code=(
            local.transaction_code
            if local
            else gateway.transaction_code
        ),
        gateway_transaction_code=(
            gateway.transaction_code if gateway else None
        ),
        provider_txn_id=(
            gateway.provider_txn_id
            if gateway and gateway.provider_txn_id
            else local.provider_txn_id if local else None
        ),
        booking_id=local.booking_id if local else None,
        local_amount=local_amount,
        gateway_amount=gateway_amount,
        difference_amount=difference,
        local_status=local_status,
        gateway_status=gateway_status,
        refund_status=refund.get("status"),
        refund_amount=_money(refund.get("amount")),
        pending_refund_amount=_money(refund.get("pending_amount")),
        completed_refund_amount=_money(refund.get("completed_amount")),
        anomaly_types=anomaly_types,
    )


def reconcile_gateway_statement(
    db: Session,
    request: GatewayReconciliationRequest,
    *,
    from_date: date,
    to_date: date,
    status_filter: str | None = None,
    search: str | None = None,
) -> PaymentReconciliationResponse:
    start = datetime.combine(from_date, time.min)
    end = datetime.combine(to_date + timedelta(days=1), time.min)
    local_timestamp = func.coalesce(
        PaymentTransaction.paid_at,
        PaymentTransaction.created_at,
    )
    local_query = db.query(PaymentTransaction).filter(
        PaymentTransaction.provider == request.provider,
        local_timestamp >= start,
        local_timestamp < end,
    )
    search_text = search.strip() if search else ""
    if search_text:
        pattern = f"%{search_text}%"
        local_query = local_query.filter(
            or_(
                PaymentTransaction.transaction_code.ilike(pattern),
                PaymentTransaction.provider_txn_id.ilike(pattern),
                cast(PaymentTransaction.booking_id, String).ilike(pattern),
            )
        )
    local_transactions = local_query.order_by(PaymentTransaction.id).all()

    local_codes = {
        transaction.transaction_code for transaction in local_transactions
    }
    local_provider_ids = {
        transaction.provider_txn_id
        for transaction in local_transactions
        if transaction.provider_txn_id
    }
    gateway_transactions = [
        transaction
        for transaction in request.gateway_transactions
        if _within_period(transaction.occurred_at, from_date, to_date)
        and (
            not search_text
            or search_text.casefold() in (transaction.transaction_code or "").casefold()
            or search_text.casefold() in (transaction.provider_txn_id or "").casefold()
            or transaction.transaction_code in local_codes
            or transaction.provider_txn_id in local_provider_ids
        )
    ]

    local_by_code = {
        transaction.transaction_code: transaction
        for transaction in local_transactions
    }
    local_by_provider_id: dict[str, list[PaymentTransaction]] = {}
    for transaction in local_transactions:
        if transaction.provider_txn_id:
            local_by_provider_id.setdefault(
                transaction.provider_txn_id, []
            ).append(transaction)

    refunds = _refund_data(
        db, [transaction.id for transaction in local_transactions]
    )
    webhook_logs = _latest_anomalous_webhook_logs(
        db, [transaction.transaction_code for transaction in local_transactions]
    )

    items = []
    matched_local_ids = set()
    for gateway in gateway_transactions:
        local = (
            local_by_code.get(gateway.transaction_code)
            if gateway.transaction_code
            else None
        )
        if local is None and gateway.provider_txn_id:
            provider_matches = local_by_provider_id.get(
                gateway.provider_txn_id, []
            )
            if len(provider_matches) == 1:
                local = provider_matches[0]

        if local is None or local.id in matched_local_ids:
            item = _make_item(
                local=None,
                gateway=gateway,
                reconciliation_status="MISSING_LOCAL",
            )
        else:
            matched_local_ids.add(local.id)
            local_status = LOCAL_PAYMENT_STATUS_MAP.get(
                local.status, local.status
            )
            gateway_status = GATEWAY_STATUS_MAP[gateway.status]
            identity_mismatch = bool(
                local.provider_txn_id
                and gateway.provider_txn_id
                and local.provider_txn_id != gateway.provider_txn_id
            )
            is_matched = (
                _money(local.amount) == _money(gateway.amount)
                and local_status == gateway_status
                and not identity_mismatch
            )
            item = _make_item(
                local=local,
                gateway=gateway,
                reconciliation_status="MATCHED" if is_matched else "MISMATCHED",
                refund=refunds.get(local.id),
                webhook_result=webhook_logs.get(local.transaction_code),
            )
        items.append(item)

    for local in local_transactions:
        if local.id in matched_local_ids:
            continue
        items.append(
            _make_item(
                local=local,
                gateway=None,
                reconciliation_status="MISSING_GATEWAY",
                refund=refunds.get(local.id),
                webhook_result=webhook_logs.get(local.transaction_code),
            )
        )

    if status_filter:
        items = [
            item
            for item in items
            if item.reconciliation_status == status_filter
        ]

    matched_count = sum(
        item.reconciliation_status == "MATCHED" for item in items
    )
    mismatched_count = sum(
        item.reconciliation_status == "MISMATCHED" for item in items
    )
    missing_gateway_count = sum(
        item.reconciliation_status == "MISSING_GATEWAY" for item in items
    )
    missing_local_count = sum(
        item.reconciliation_status == "MISSING_LOCAL" for item in items
    )
    return PaymentReconciliationResponse(
        provider=request.provider,
        from_date=from_date,
        to_date=to_date,
        summary=ReconciliationSummary(
            total_count=len(items),
            matched_count=matched_count,
            mismatched_count=mismatched_count,
            missing_gateway_count=missing_gateway_count,
            missing_local_count=missing_local_count,
            local_amount_total=_money(
                sum(
                    (item.local_amount or Decimal("0.00") for item in items),
                    Decimal("0.00"),
                )
            ),
            gateway_amount_total=_money(
                sum(
                    (item.gateway_amount or Decimal("0.00") for item in items),
                    Decimal("0.00"),
                )
            ),
            difference_amount_total=_money(
                sum(
                    (item.difference_amount for item in items),
                    Decimal("0.00"),
                )
            ),
            anomaly_count=sum(bool(item.anomaly_types) for item in items),
            pending_refund_count=sum(
                item.refund_status == "PENDING" for item in items
            ),
            pending_refund_amount=_money(
                sum(
                    (item.pending_refund_amount for item in items),
                    Decimal("0.00"),
                )
            ),
            completed_refund_amount=_money(
                sum(
                    (item.completed_refund_amount for item in items),
                    Decimal("0.00"),
                )
            ),
        ),
        transactions=items,
    )
