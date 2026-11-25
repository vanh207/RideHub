"""Settlement of returned rental bookings."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.booking_status import COMPLETED, PENDING_SETTLEMENT, normalize_status
from app.crud.booking_status_history import record_booking_status_change
from app.models.booking import Booking
from app.models.handover import HandoverProtocol, ProtocolType
from app.models.payment import PaymentTransaction, Refund
from app.models.store import Store, StoreStaff
from app.models.user import User
from app.models.vehicle_reservation import VehicleReservation
from app.models.vehicle_schedule import VehicleSchedule

MONEY_QUANT = Decimal("0.01")
SUCCESS_REFUND_STATUSES = {"SUCCESS", "REFUNDED"}


class BookingSettlementError(Exception):
    """Base class for settlement errors mapped by the API router."""


class BookingSettlementNotFoundError(BookingSettlementError):
    pass


class BookingSettlementPermissionError(BookingSettlementError):
    pass


class BookingSettlementStateError(BookingSettlementError):
    pass


class BookingSettlementValidationError(BookingSettlementError):
    pass


class BookingSettlementPaymentError(BookingSettlementError):
    pass


def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _can_settle(db: Session, booking: Booking, actor: User) -> bool:
    role = (actor.role or "").lower()
    if role in {"admin", "operator"}:
        return True
    if booking.store_id is None:
        return False
    owns_store = db.scalar(
        select(Store.id).where(
            Store.id == booking.store_id,
            Store.owner_user_id == actor.id,
        )
    )
    if owns_store is not None:
        return True
    is_active_staff = db.scalar(
        select(StoreStaff.id).where(
            StoreStaff.store_id == booking.store_id,
            StoreStaff.user_id == actor.id,
            StoreStaff.status == "ACTIVE",
        )
    )
    return is_active_staff is not None


def settle_booking(
    db: Session,
    booking_id: int,
    *,
    actor: User,
    amount_received: Decimal,
    payment_method: str,
) -> dict:
    """Collect the outstanding booking balance and recorded check-in fees."""
    try:
        booking = (
            db.query(Booking)
            .filter(Booking.id == booking_id)
            .with_for_update()
            .first()
        )
        if booking is None:
            raise BookingSettlementNotFoundError
        if not _can_settle(db, booking, actor):
            raise BookingSettlementPermissionError

        current_status = normalize_status(booking.status)
        if current_status == COMPLETED:
            raise BookingSettlementStateError("Đơn thuê đã được tất toán.")
        if current_status != PENDING_SETTLEMENT:
            raise BookingSettlementStateError(
                "Chỉ có thể tất toán đơn đang ở trạng thái PENDING_SETTLEMENT."
            )

        checkin = (
            db.query(HandoverProtocol)
            .filter(
                HandoverProtocol.booking_id == booking.id,
                HandoverProtocol.protocol_type == ProtocolType.CHECK_IN.value,
            )
            .order_by(HandoverProtocol.id.desc())
            .with_for_update()
            .first()
        )
        if (
            checkin is None
            or checkin.status != "COMPLETED"
            or not checkin.both_confirmed
        ):
            raise BookingSettlementStateError(
                "Cần hoàn tất biên bản CHECK_IN và xác nhận của cả hai bên trước khi tất toán."
            )

        fee_fields = (
            "fee_overtime",
            "fee_excess_km",
            "fee_fuel",
            "fee_cleaning",
            "fee_damage",
        )
        fee_breakdown = {field: _money(getattr(checkin, field)) for field in fee_fields}
        immediate_refund = _money(checkin.refund_immediate)
        if immediate_refund < 0 or any(
            amount < 0 for amount in fee_breakdown.values()
        ):
            raise BookingSettlementValidationError(
                "Biên bản có khoản phí hoặc hoàn cọc không hợp lệ."
            )
        extra_fees = sum(fee_breakdown.values(), Decimal("0.00"))

        successful_payments = db.scalars(
            select(PaymentTransaction.amount).where(
                PaymentTransaction.booking_id == booking.id,
                PaymentTransaction.status == "SUCCESS",
            )
        ).all()
        previously_paid = sum(
            (_money(amount) for amount in successful_payments), Decimal("0.00")
        )

        successful_refunds = db.scalars(
            select(Refund.amount).where(
                Refund.booking_id == booking.id,
                Refund.status.in_(SUCCESS_REFUND_STATUSES),
            )
        ).all()
        refund_amounts = [_money(amount) for amount in successful_refunds]
        if any(amount < 0 for amount in refund_amounts):
            raise BookingSettlementValidationError(
                "Lịch sử hoàn tiền của đơn có dữ liệu không hợp lệ."
            )
        refunded = sum(refund_amounts, Decimal("0.00"))
        # A check-in refund is recorded on the protocol; it may not have a
        # corresponding Refund row when it was returned directly by the store.
        refunded += immediate_refund
        net_paid = max(Decimal("0.00"), previously_paid - refunded)
        remaining_amount = max(
            Decimal("0.00"), _money(booking.total_amount) - net_paid
        )
        amount_due = remaining_amount + extra_fees
        if amount_due > Decimal("9999999999.99"):
            raise BookingSettlementValidationError(
                "Tổng số tiền tất toán vượt giới hạn cho phép."
            )
        amount_received = _money(amount_received)
        if amount_received != amount_due:
            raise BookingSettlementPaymentError(
                f"Số tiền thực nhận ({amount_received}) phải khớp số tiền cần thu ({amount_due})."
            )

        now = datetime.now()
        final_payment_method = payment_method if amount_due > 0 else "NO_CHARGE"
        transaction = PaymentTransaction(
            booking_id=booking.id,
            transaction_code=f"RH-SET-{booking.id}-{uuid4().hex[:12].upper()}",
            provider="INTERNAL",
            amount=amount_due,
            status="SUCCESS",
            payment_method=final_payment_method,
            paid_at=now,
        )
        db.add(transaction)
        db.flush()

        record_booking_status_change(
            db,
            booking,
            booking.status,
            COMPLETED,
            changed_by="SETTLEMENT",
            changed_by_user_id=actor.id,
            reason=f"FINAL_PAYMENT:{transaction.transaction_code}",
            created_at=now,
        )
        booking.status = COMPLETED

        db.query(VehicleReservation).filter(
            VehicleReservation.booking_id == booking.id,
            VehicleReservation.status == "ACTIVE",
        ).update(
            {VehicleReservation.status: "COMPLETED"},
            synchronize_session=False,
        )
        db.query(VehicleSchedule).filter(
            VehicleSchedule.booking_id == booking.id,
            VehicleSchedule.status == "ACTIVE",
        ).update(
            {VehicleSchedule.status: "COMPLETED"},
            synchronize_session=False,
        )

        db.commit()
        db.refresh(transaction)
        return {
            "booking_id": booking.id,
            "status": booking.status,
            "currency": "VND",
            "total_amount": _money(booking.total_amount),
            "previously_paid": previously_paid,
            "refunded_amount": refunded,
            "net_paid": net_paid,
            "remaining_amount": remaining_amount,
            "fee_breakdown": fee_breakdown,
            "extra_fees": extra_fees,
            "amount_due": amount_due,
            "transaction_id": transaction.id,
            "transaction_code": transaction.transaction_code,
            "transaction_status": transaction.status,
            "payment_method": transaction.payment_method,
            "settled_at": transaction.paid_at,
        }
    except Exception:
        db.rollback()
        raise
