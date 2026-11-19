from datetime import datetime, timedelta
from decimal import Decimal

from app.services.cancellation_policy import calculate_refund_quote

NOW = datetime(2026, 1, 1, 12, 0, 0)


def quote(hours_before: float, **overrides):
    defaults = dict(
        booking_status="DEPOSIT_PAID",
        start_time=NOW + timedelta(hours=hours_before),
        deposit_amount=Decimal("1500000"),
        paid_amount=Decimal("1500000"),
        cancelled_at=NOW,
        now=NOW,
        cancelled_by="CUSTOMER",
    )
    defaults.update(overrides)
    return calculate_refund_quote(**defaults)


def test_free_cancel_full_refund():
    result = quote(48)
    assert result.policy_code == "FREE_CANCEL"
    assert result.amount == Decimal("1500000.00")


def test_partial_cancel_half_refund():
    result = quote(30)
    assert result.policy_code == "PARTIAL_CANCEL"
    assert result.amount == Decimal("750000.00")


def test_late_cancel_no_refund():
    result = quote(10)
    assert result.policy_code == "LATE_CANCEL"
    assert result.amount == Decimal("0.00")


def test_store_cancel_full_refund_even_when_late():
    result = quote(2, cancelled_by="STORE")
    assert result.policy_code == "STORE_CANCEL"
    assert result.amount == Decimal("1500000.00")


def test_system_expiry_no_refund():
    result = quote(72, cancelled_by="SYSTEM")
    assert result.policy_code == "HOLD_EXPIRED"
    assert result.amount == Decimal("0.00")


def test_refund_never_exceeds_paid_amount():
    result = quote(72, paid_amount=Decimal("900000"))
    assert result.amount == Decimal("900000.00")


def test_refund_subtracts_previous_refunds():
    result = quote(72, already_refunded=Decimal("500000"))
    assert result.amount == Decimal("1000000.00")


def test_terminal_booking_invalid_state():
    result = quote(72, booking_status="CANCELLED")
    assert result.policy_code == "INVALID_STATE"
    assert result.amount == Decimal("0.00")
