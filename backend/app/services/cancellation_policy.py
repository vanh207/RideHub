"""Tính tiền hoàn khi hủy đơn thuê xe.

Module này thuần logic: không truy cập DB, không gọi cổng thanh toán.
Việc lấy số tiền đã trả / đã hoàn và ghi bản ghi Refund nằm ở CRUD.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from app.core.booking_status import (
    CANCEL_ACTOR_ADMIN,
    CANCEL_ACTOR_STORE,
    CANCEL_ACTOR_SYSTEM,
    CANCELLED,
    EXPIRED,
    TERMINAL_STATUSES,
)
from app.core.config import settings

MONEY_QUANT = Decimal("0.01")


@dataclass(frozen=True)
class RefundQuote:
    amount: Decimal
    rate: Decimal
    policy_code: str
    reason: str


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _to_naive(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone().replace(tzinfo=None)
    return value


def calculate_refund_quote(
    *,
    booking_status: str,
    start_time: datetime,
    deposit_amount: Decimal,
    paid_amount: Decimal,
    already_refunded: Decimal = Decimal("0"),
    cancelled_at: Optional[datetime] = None,
    cancelled_by: str = CANCEL_ACTOR_ADMIN,
    now: Optional[datetime] = None,
) -> RefundQuote:
    """Trả về số tiền hoàn theo chính sách.

    paid_amount là tổng các giao dịch SUCCESS, đã trừ các refund trước đó
    khi gọi từ CRUD. Hàm này vẫn trừ already_refunded để an toàn khi gọi lại.
    """
    reference_time = _to_naive(now) or datetime.now()
    cancel_time = _to_naive(cancelled_at) or reference_time
    rental_start = _to_naive(start_time)

    paid = Decimal(str(paid_amount or 0))
    refunded = Decimal(str(already_refunded or 0))
    deposit = Decimal(str(deposit_amount or 0))

    if (booking_status or "").upper() in TERMINAL_STATUSES | {CANCELLED, EXPIRED}:
        return RefundQuote(
            amount=Decimal("0.00"),
            rate=Decimal("0"),
            policy_code="INVALID_STATE",
            reason="Đơn đã ở trạng thái kết thúc, không tính hoàn lại.",
        )

    refundable_base = min(paid, deposit)
    remaining = max(refundable_base - refunded, Decimal("0"))
    if remaining <= 0 or paid <= 0:
        return RefundQuote(
            amount=Decimal("0.00"),
            rate=Decimal("0"),
            policy_code="NO_PAYMENT",
            reason="Chưa có tiền cọc được thanh toán hoặc đã hoàn hết.",
        )

    hours_before_start = Decimal(str((rental_start - cancel_time).total_seconds())) / Decimal(
        "3600"
    )

    if hours_before_start <= 0:
        return RefundQuote(
            amount=Decimal("0.00"),
            rate=Decimal("0"),
            policy_code="NO_REFUND",
            reason="Đơn đã đến giờ nhận xe hoặc đang thuê, không hoàn tiền.",
        )

    actor = (cancelled_by or "").strip().upper()
    if actor == CANCEL_ACTOR_SYSTEM:
        return RefundQuote(
            amount=Decimal("0.00"),
            rate=Decimal("0"),
            policy_code="HOLD_EXPIRED",
            reason="Hết hạn giữ chỗ, không phát sinh hoàn tiền.",
        )

    if actor in {CANCEL_ACTOR_STORE, CANCEL_ACTOR_ADMIN}:
        rate = Decimal(str(settings.BOOKING_CANCEL_STORE_FAULT_RATE))
        return RefundQuote(
            amount=_money(remaining * rate),
            rate=rate,
            policy_code="STORE_CANCEL",
            reason="Cửa hàng/admin hủy đơn, hoàn 100% tiền cọc đã trả.",
        )

    free_hours = Decimal(str(settings.BOOKING_CANCEL_FREE_HOURS))
    partial_hours = Decimal(str(settings.BOOKING_CANCEL_PARTIAL_HOURS))

    if hours_before_start >= free_hours:
        rate = Decimal("1")
        code = "FREE_CANCEL"
        reason = f"Hủy trước {settings.BOOKING_CANCEL_FREE_HOURS} giờ, hoàn 100% tiền cọc."
    elif hours_before_start >= partial_hours:
        rate = Decimal(str(settings.BOOKING_CANCEL_PARTIAL_RATE))
        code = "PARTIAL_CANCEL"
        reason = (
            f"Hủy trước {settings.BOOKING_CANCEL_PARTIAL_HOURS} đến "
            f"{settings.BOOKING_CANCEL_FREE_HOURS} giờ, hoàn "
            f"{rate * 100:.0f}% tiền cọc."
        )
    else:
        rate = Decimal("0")
        code = "LATE_CANCEL"
        reason = f"Hủy trong vòng {settings.BOOKING_CANCEL_PARTIAL_HOURS} giờ, không hoàn tiền."

    return RefundQuote(
        amount=_money(remaining * rate) if rate > 0 else Decimal("0.00"),
        rate=rate,
        policy_code=code,
        reason=reason,
    )
