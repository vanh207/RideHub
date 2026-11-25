from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.booking_status import normalize_status
from app.models.booking import Booking
from app.models.handover import HandoverProtocol, ProtocolType
from app.models.payment import PaymentTransaction, PaymentWebhookLog, Refund
from app.models.user import User
from app.models.vehicle import Vehicle

MONEY_QUANT = Decimal("0.01")
CAPTURED_PAYMENT_STATUSES = {"SUCCESS", "REFUNDED", "LATE_PAYMENT"}
COMPLETED_REFUND_STATUSES = {"SUCCESS", "REFUNDED"}
WEBHOOK_FAILURE_RESULTS = {
    "FAILED",
    "NOT_FOUND",
    "REJECTED_INVALID_SIGNATURE",
    "REJECTED_NO_ORDER_CODE",
}


def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(MONEY_QUANT)


def _period(from_date: date, to_date: date) -> tuple[datetime, datetime]:
    return (
        datetime.combine(from_date, time.min),
        datetime.combine(to_date + timedelta(days=1), time.min),
    )


def _grouped_status_counts(
    db: Session,
    model,
    status_column,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    timestamp_column=None,
) -> dict[str, int]:
    query = db.query(status_column, func.count(model.id))
    if start is not None and end is not None and timestamp_column is not None:
        query = query.filter(timestamp_column >= start, timestamp_column < end)
    rows = query.group_by(status_column).all()
    counts: dict[str, int] = {}
    for value, count in rows:
        normalized = str(value or "UNKNOWN")
        if model is Booking:
            normalized = normalize_status(normalized) or "UNKNOWN"
        counts[normalized] = counts.get(normalized, 0) + int(count)
    return counts


def build_platform_report(
    db: Session,
    *,
    from_date: date,
    to_date: date,
) -> dict:
    start, end = _period(from_date, to_date)
    transaction_timestamp = func.coalesce(
        PaymentTransaction.paid_at,
        PaymentTransaction.created_at,
    )
    transaction_rows = (
        db.query(
            PaymentTransaction.status,
            func.count(PaymentTransaction.id),
            func.coalesce(func.sum(PaymentTransaction.amount), 0),
        )
        .filter(
            transaction_timestamp >= start,
            transaction_timestamp < end,
        )
        .group_by(PaymentTransaction.status)
        .all()
    )
    transactions_by_status = {
        str(transaction_status or "UNKNOWN"): int(count)
        for transaction_status, count, _ in transaction_rows
    }
    transaction_count = sum(transactions_by_status.values())
    captured_count = sum(
        count
        for transaction_status, count in transactions_by_status.items()
        if transaction_status in CAPTURED_PAYMENT_STATUSES
    )
    captured_amount = _money(
        sum(
            (
                _money(amount)
                for transaction_status, _, amount in transaction_rows
                if transaction_status in CAPTURED_PAYMENT_STATUSES
            ),
            Decimal("0.00"),
        )
    )

    refund_rows = (
        db.query(
            Refund.status,
            func.count(Refund.id),
            func.coalesce(func.sum(Refund.amount), 0),
        )
        .filter(Refund.created_at >= start, Refund.created_at < end)
        .group_by(Refund.status)
        .all()
    )
    refunds_by_status = {
        str(refund_status or "UNKNOWN"): int(count)
        for refund_status, count, _ in refund_rows
    }
    refund_count = sum(refunds_by_status.values())
    pending_count = refunds_by_status.get("PENDING", 0)
    pending_amount = _money(
        sum(
            (
                _money(amount)
                for refund_status, _, amount in refund_rows
                if refund_status == "PENDING"
            ),
            Decimal("0.00"),
        )
    )
    completed_refund_amount = _money(
        sum(
            (
                _money(amount)
                for refund_status, _, amount in refund_rows
                if refund_status in COMPLETED_REFUND_STATUSES
            ),
            Decimal("0.00"),
        )
    )
    completed_refund_count = sum(
        count
        for refund_status, count, _ in refund_rows
        if refund_status in COMPLETED_REFUND_STATUSES
    )

    booking_status_counts = _grouped_status_counts(
        db,
        Booking,
        Booking.status,
        start=start,
        end=end,
        timestamp_column=Booking.created_at,
    )
    user_status_counts = _grouped_status_counts(db, User, User.status)
    vehicle_status_counts = _grouped_status_counts(
        db, Vehicle, Vehicle.current_status
    )

    user_created_count = (
        db.query(func.count(User.id))
        .filter(User.created_at >= start, User.created_at < end)
        .scalar()
        or 0
    )
    active_vehicle_count = (
        db.query(func.count(Vehicle.id))
        .filter(Vehicle.is_active.is_(True))
        .scalar()
        or 0
    )

    extra_fee_expression = (
        HandoverProtocol.fee_overtime
        + HandoverProtocol.fee_excess_km
        + HandoverProtocol.fee_fuel
        + HandoverProtocol.fee_cleaning
        + HandoverProtocol.fee_damage
    )
    extra_fee_count, extra_fee_amount = (
        db.query(
            func.count(HandoverProtocol.id),
            func.coalesce(func.sum(extra_fee_expression), 0),
        )
        .filter(
            HandoverProtocol.protocol_type == ProtocolType.CHECK_IN.value,
            HandoverProtocol.created_at >= start,
            HandoverProtocol.created_at < end,
            extra_fee_expression > 0,
        )
        .one()
    )

    webhook_rows = (
        db.query(
            PaymentWebhookLog.process_result,
            PaymentWebhookLog.signature_valid,
            func.count(PaymentWebhookLog.id),
        )
        .filter(
            PaymentWebhookLog.processed_at >= start,
            PaymentWebhookLog.processed_at < end,
        )
        .group_by(
            PaymentWebhookLog.process_result,
            PaymentWebhookLog.signature_valid,
        )
        .all()
    )
    mismatch_transaction_codes = {
        code
        for (code,) in (
            db.query(PaymentTransaction.transaction_code)
            .filter(
                PaymentTransaction.status == "AMOUNT_MISMATCH",
                transaction_timestamp >= start,
                transaction_timestamp < end,
            )
            .all()
        )
    }
    late_transaction_codes = {
        code
        for (code,) in (
            db.query(PaymentTransaction.transaction_code)
            .filter(
                PaymentTransaction.status == "LATE_PAYMENT",
                transaction_timestamp >= start,
                transaction_timestamp < end,
            )
            .all()
        )
    }
    mismatch_transaction_codes.update(
        code
        for result, code in (
            db.query(
                PaymentWebhookLog.process_result,
                PaymentWebhookLog.transaction_code,
            )
            .filter(
                PaymentWebhookLog.process_result == "AMOUNT_MISMATCH",
                PaymentWebhookLog.processed_at >= start,
                PaymentWebhookLog.processed_at < end,
            )
            .all()
        )
        if code
    )
    late_transaction_codes.update(
        code
        for result, code in (
            db.query(
                PaymentWebhookLog.process_result,
                PaymentWebhookLog.transaction_code,
            )
            .filter(
                PaymentWebhookLog.process_result == "LATE_PAYMENT",
                PaymentWebhookLog.processed_at >= start,
                PaymentWebhookLog.processed_at < end,
            )
            .all()
        )
        if code
    )
    amount_mismatch_count = len(mismatch_transaction_codes)
    late_payment_count = len(late_transaction_codes)
    invalid_signature_webhook_count = sum(
        int(count)
        for _, signature_valid, count in webhook_rows
        if signature_valid == "INVALID"
    )
    failed_webhook_count = sum(
        int(count)
        for process_result, _, count in webhook_rows
        if process_result in WEBHOOK_FAILURE_RESULTS
    )

    return {
        "period": {"from_date": from_date, "to_date": to_date},
        "currency": "VND",
        "payments": {
            "transaction_count": transaction_count,
            "transactions_by_status": transactions_by_status,
            "captured_count": captured_count,
            "captured_amount": captured_amount,
            "completed_refund_amount": completed_refund_amount,
            "net_collected_amount": _money(
                captured_amount - completed_refund_amount
            ),
        },
        "refunds": {
            "refund_count": refund_count,
            "refunds_by_status": refunds_by_status,
            "pending_count": pending_count,
            "pending_amount": pending_amount,
            "completed_count": completed_refund_count,
            "completed_amount": completed_refund_amount,
        },
        "bookings": {
            "booking_count": sum(booking_status_counts.values()),
            "bookings_by_status": booking_status_counts,
        },
        "extra_fee_count": int(extra_fee_count or 0),
        "extra_fee_amount": _money(extra_fee_amount),
        "platform": {
            "user_count": sum(user_status_counts.values()),
            "active_user_count": sum(
                count
                for user_status, count in user_status_counts.items()
                if user_status.casefold() == "active"
            ),
            "new_user_count": int(user_created_count),
            "users_by_status": user_status_counts,
            "vehicle_count": sum(vehicle_status_counts.values()),
            "active_vehicle_count": int(active_vehicle_count),
            "vehicles_by_status": vehicle_status_counts,
        },
        "anomalies": {
            "amount_mismatch_count": amount_mismatch_count,
            "late_payment_count": late_payment_count,
            "pending_refund_count": pending_count,
            "invalid_signature_webhook_count": invalid_signature_webhook_count,
            "failed_webhook_count": failed_webhook_count,
        },
    }
