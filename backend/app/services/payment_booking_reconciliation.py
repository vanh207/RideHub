"""Đối chiếu thanh toán thành công với trạng thái booking.

Nếu đơn đã hủy/hết hạn/completed thì không được đổi status ngược lại; tạo
một Refund PENDING để vận hành xử lý thủ công thay vì mất tiền khách.
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.booking_status import DEPOSIT_PAID, TERMINAL_STATUSES, normalize_status
from app.models.booking import Booking
from app.models.payment import PaymentTransaction, Refund

logger = logging.getLogger("ridehub.payment_reconciliation")


def create_pending_refund_for_transaction(
    db: Session,
    booking: Booking,
    transaction: PaymentTransaction,
    reason: str,
) -> bool:
    existing_refund_id = db.scalar(
        select(Refund.id).where(
            Refund.booking_id == booking.id,
            Refund.payment_transaction_id == transaction.id,
        )
    )
    if existing_refund_id is not None:
        return False
    db.add(
        Refund(
            booking_id=booking.id,
            payment_transaction_id=transaction.id,
            amount=transaction.amount,
            reason=reason,
            status="PENDING",
        )
    )
    return True


def apply_successful_payment_to_booking(
    db: Session,
    booking: Booking,
    transaction: PaymentTransaction,
) -> str:
    current_status = normalize_status(booking.status)
    if current_status in TERMINAL_STATUSES:
        create_pending_refund_for_transaction(
            db,
            booking,
            transaction,
            f"PAID_AFTER_{current_status}: thanh toán thành công sau khi đơn đã kết thúc, cần hoàn tiền.",
        )
        logger.warning(
            "Booking %s thanh toán sau khi ở trạng thái %s -> tạo refund PENDING",
            booking.id,
            current_status,
        )
        return "REFUND_REQUIRED"

    booking.status = DEPOSIT_PAID
    return "DEPOSIT_PAID"
