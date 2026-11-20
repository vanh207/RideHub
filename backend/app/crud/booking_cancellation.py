"""Hủy đơn, giải phóng lịch và tính hoàn tiền.

Mọi thao tác được thực hiện trong một transaction và khóa dòng booking trước
khi kiểm tra trạng thái để tránh double-cancel/double-refund.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.booking_status import (
    CANCEL_ACTOR_ADMIN,
    CANCEL_ACTOR_CUSTOMER,
    CANCEL_ACTOR_STORE,
    CANCEL_ACTOR_SYSTEM,
    CANCELLED,
    DEPOSIT_PAID,
    EXPIRED,
    PENDING_PAYMENT,
    TERMINAL_STATUSES,
    can_transition,
    is_terminal,
    normalize_status,
)
from app.core.config import settings
from app.crud.booking_status_history import record_booking_status_change
from app.models.booking import Booking
from app.models.payment import PaymentTransaction, Refund
from app.models.store import Store, StoreStaff
from app.models.vehicle_reservation import VehicleReservation
from app.models.vehicle_schedule import VehicleSchedule
from app.services.cancellation_policy import RefundQuote, calculate_refund_quote

logger = logging.getLogger("ridehub.booking_cancellation")

ACTIVE = "ACTIVE"
CANCELLED_STATUS = "CANCELLED"
EXPIRED_STATUS = "EXPIRED"
PENDING_STATUS = "PENDING"
SUCCESS_STATUS = "SUCCESS"
REFUND_PENDING_STATUSES = ("PENDING", "SUCCESS", "REFUNDED")


class BookingCancellationError(Exception):
    """Lỗi nghiệp vụ khi hủy đơn."""


class BookingNotFoundError(BookingCancellationError):
    pass


class BookingPermissionError(BookingCancellationError):
    pass


class BookingStateError(BookingCancellationError):
    pass


@dataclass(frozen=True)
class BookingActor:
    id: int
    role: str
    store_id: Optional[int] = None

    def normalized_role(self) -> str:
        return (self.role or "").strip().upper()

    def cancellation_actor(self) -> str:
        role = self.normalized_role()
        if role == "ADMIN":
            return CANCEL_ACTOR_ADMIN
        if role in {"STORE_OWNER", "STORE_STAFF"}:
            return CANCEL_ACTOR_STORE
        return CANCEL_ACTOR_CUSTOMER


@dataclass(frozen=True)
class BookingCancelResult:
    booking_id: int
    status: str
    cancelled_at: Optional[datetime]
    cancelled_by: Optional[str]
    cancel_reason: Optional[str]
    refund: RefundQuote
    refund_id: Optional[int]
    refund_status: Optional[str]
    reservation_released: bool
    schedule_released: bool
    already_cancelled: bool = False


@dataclass(frozen=True)
class ExpiryResult:
    scanned: int = 0
    expired: int = 0
    paid_race: int = 0
    skipped: int = 0


def _select_for_update(stmt, db: Session):
    if db.bind is not None and db.bind.dialect.name == "mysql":
        return stmt.with_for_update(skip_locked=True)
    return stmt


def _money(value) -> Decimal:
    return Decimal(str(value or 0))


def get_paid_amount(db: Session, booking_id: int) -> Decimal:
    amounts = db.scalars(
        select(PaymentTransaction.amount).where(
            PaymentTransaction.booking_id == booking_id,
            PaymentTransaction.status == SUCCESS_STATUS,
        )
    ).all()
    return sum((_money(amount) for amount in amounts), Decimal("0"))


def get_already_refunded_amount(db: Session, booking_id: int) -> Decimal:
    amounts = db.scalars(
        select(Refund.amount).where(
            Refund.booking_id == booking_id,
            Refund.status.in_(REFUND_PENDING_STATUSES),
        )
    ).all()
    return sum((_money(amount) for amount in amounts), Decimal("0"))


def _latest_success_transaction(
    db: Session, booking_id: int
) -> Optional[PaymentTransaction]:
    return db.execute(
        select(PaymentTransaction)
        .where(
            PaymentTransaction.booking_id == booking_id,
            PaymentTransaction.status == SUCCESS_STATUS,
        )
        .order_by(PaymentTransaction.id.desc())
    ).scalar_one_or_none()


def _existing_refund(db: Session, booking_id: int) -> Optional[Refund]:
    return db.execute(
        select(Refund)
        .where(Refund.booking_id == booking_id)
        .order_by(Refund.id.desc())
    ).scalar_one_or_none()


def _actor_can_cancel(db: Session, booking: Booking, actor: BookingActor) -> bool:
    role = actor.normalized_role()
    if role == "ADMIN":
        return True
    if role == CANCEL_ACTOR_CUSTOMER or not role:
        return actor.id == booking.customer_id
    if role in {"STORE_OWNER", "STORE_STAFF"}:
        if booking.store_id is None:
            return False
        if role == "STORE_OWNER":
            owner_store_id = db.scalar(
                select(Store.id).where(
                    Store.id == booking.store_id,
                    Store.owner_user_id == actor.id,
                )
            )
            return owner_store_id is not None
        staff_store_id = db.scalar(
            select(StoreStaff.store_id).where(
                StoreStaff.user_id == actor.id,
                StoreStaff.store_id == booking.store_id,
                StoreStaff.status == ACTIVE,
            )
        )
        return staff_store_id is not None
    return False


def _release_schedule(
    db: Session,
    booking_id: int,
    *,
    reservation_status: str = EXPIRED_STATUS,
) -> bool:
    reservations = db.scalars(
        select(VehicleReservation).where(
            VehicleReservation.booking_id == booking_id,
            VehicleReservation.status == ACTIVE,
        )
    ).all()
    schedules = db.scalars(
        select(VehicleSchedule).where(
            VehicleSchedule.booking_id == booking_id,
            VehicleSchedule.status == ACTIVE,
        )
    ).all()

    released = bool(reservations or schedules)
    for reservation in reservations:
        reservation.status = reservation_status
    for schedule in schedules:
        schedule.status = CANCELLED_STATUS
    return released


def _idempotent_result(db: Session, booking: Booking) -> BookingCancelResult:
    refund = _existing_refund(db, booking.id)
    quote = RefundQuote(
        amount=_money(refund.amount) if refund else Decimal("0.00"),
        rate=Decimal("0"),
        policy_code="EXISTING_REFUND" if refund else "ALREADY_CANCELLED",
        reason=booking.cancel_reason or "Đơn đã được xử lý hủy trước đó.",
    )
    return BookingCancelResult(
        booking_id=booking.id,
        status=normalize_status(booking.status),
        cancelled_at=booking.cancelled_at,
        cancelled_by=booking.cancelled_by,
        cancel_reason=booking.cancel_reason,
        refund=quote,
        refund_id=refund.id if refund else None,
        refund_status=refund.status if refund else None,
        reservation_released=False,
        schedule_released=False,
        already_cancelled=True,
    )


def cancel_booking(
    db: Session,
    booking_id: int,
    *,
    actor: BookingActor,
    reason: str,
    now: Optional[datetime] = None,
) -> BookingCancelResult:
    """Hủy một booking đang hợp lệ. Trả về kết quả idempotent nếu đã hủy."""
    cancel_time = now or datetime.now()
    reason = (reason or "").strip()
    if not reason:
        raise BookingCancellationError("Lý do hủy không được để trống.")

    booking = db.execute(
        _select_for_update(select(Booking).where(Booking.id == booking_id), db)
    ).scalar_one_or_none()
    if booking is None:
        raise BookingNotFoundError("Không tìm thấy đơn đặt xe.")

    current_status = normalize_status(booking.status)
    if current_status in {CANCELLED, EXPIRED}:
        return _idempotent_result(db, booking)

    if not _actor_can_cancel(db, booking, actor):
        raise BookingPermissionError("Bạn không có quyền hủy đơn này.")

    if is_terminal(current_status):
        raise BookingStateError("Đơn đã kết thúc, không thể hủy.")

    if current_status in {"IN_PROGRESS", "PENDING_SETTLEMENT"} and actor.normalized_role() != "ADMIN":
        raise BookingStateError("Đơn đang trong quá trình thuê, không thể hủy.")

    if not can_transition(current_status, CANCELLED):
        raise BookingStateError(
            f"Không thể hủy đơn ở trạng thái {current_status or booking.status}."
        )

    paid_amount = get_paid_amount(db, booking.id)
    already_refunded = get_already_refunded_amount(db, booking.id)
    quote = calculate_refund_quote(
        booking_status=current_status,
        start_time=booking.start_time,
        deposit_amount=_money(booking.deposit_amount),
        paid_amount=paid_amount,
        already_refunded=already_refunded,
        cancelled_at=cancel_time,
        cancelled_by=actor.cancellation_actor(),
        now=cancel_time,
    )

    released = _release_schedule(
        db,
        booking.id,
        reservation_status=CANCELLED_STATUS,
    )

    refund_id = None
    refund_status = None
    if quote.amount > 0:
        transaction = _latest_success_transaction(db, booking.id)
        refund_status_value = REFUND_PENDING_STATUSES[0]
        if transaction is not None:
            try:
                from app.services.payment_gateway import payment_gateway_service

                gateway_result = payment_gateway_service.process_refund(
                    transaction_code=transaction.transaction_code,
                    amount=float(quote.amount),
                    reason=reason,
                )
                if str(gateway_result.get("status", "")).upper() == SUCCESS_STATUS:
                    refund_status_value = SUCCESS_STATUS
            except Exception as exc:
                logger.warning("Không gọi được cổng hoàn tiền, để refund PENDING: %s", exc)

        refund = Refund(
            booking_id=booking.id,
            payment_transaction_id=transaction.id if transaction else None,
            amount=quote.amount,
            reason=f"{quote.policy_code}: {reason}",
            status=refund_status_value,
            processed_by=actor.id if actor.normalized_role() != CANCEL_ACTOR_CUSTOMER else None,
            processed_at=cancel_time if refund_status_value == SUCCESS_STATUS else None,
        )
        db.add(refund)
        db.flush()
        refund_id = refund.id
        refund_status = refund.status
        if refund_status_value == SUCCESS_STATUS and transaction is not None:
            transaction.status = "REFUNDED"

    history_reason = f"{quote.policy_code}: {reason}" if reason else quote.policy_code
    record_booking_status_change(
        db,
        booking,
        booking.status,
        CANCELLED,
        changed_by=actor.cancellation_actor(),
        changed_by_user_id=actor.id,
        reason=history_reason,
        created_at=cancel_time,
    )
    booking.status = CANCELLED
    booking.cancelled_at = cancel_time
    booking.cancelled_by = actor.cancellation_actor()
    booking.cancel_reason = history_reason

    db.commit()

    return BookingCancelResult(
        booking_id=booking.id,
        status=CANCELLED,
        cancelled_at=booking.cancelled_at,
        cancelled_by=booking.cancelled_by,
        cancel_reason=booking.cancel_reason,
        refund=quote,
        refund_id=refund_id,
        refund_status=refund_status,
        reservation_released=released,
        schedule_released=released,
    )


def expire_hold_bookings(
    db: Session,
    *,
    now: Optional[datetime] = None,
    batch_size: Optional[int] = None,
) -> ExpiryResult:
    """Tự hủy các đơn PENDING_PAYMENT hết hạn giữ chỗ."""
    current_time = now or datetime.now()
    limit = batch_size or settings.BOOKING_EXPIRY_JOB_BATCH_SIZE

    ids = db.scalars(
        _select_for_update(
            select(Booking.id).where(
                Booking.status.in_((PENDING_PAYMENT, PENDING_STATUS)),
                Booking.hold_expires_at.is_not(None),
                Booking.hold_expires_at <= current_time,
            )
            .order_by(Booking.hold_expires_at)
            .limit(limit),
            db,
        )
    ).all()

    scanned = 0
    expired = 0
    paid_race = 0
    skipped = 0

    for booking_id in ids:
        scanned += 1
        booking = db.get(Booking, booking_id)
        if booking is None:
            skipped += 1
            continue
        if normalize_status(booking.status) != PENDING_PAYMENT:
            skipped += 1
            continue

        paid_amount = get_paid_amount(db, booking.id)
        if paid_amount > 0:
            record_booking_status_change(
                db,
                booking,
                booking.status,
                DEPOSIT_PAID,
                changed_by=CANCEL_ACTOR_SYSTEM,
                reason="PAYMENT_AFTER_HOLD_EXPIRY",
                created_at=current_time,
            )
            booking.status = DEPOSIT_PAID
            paid_race += 1
            logger.warning(
                "Booking %s có thanh toán sau khi hết hạn hold, chuyển DEPOSIT_PAID",
                booking.id,
            )
            continue

        expiry_reason = "HOLD_EXPIRED: Hết hạn giữ chỗ"
        record_booking_status_change(
            db,
            booking,
            booking.status,
            EXPIRED,
            changed_by=CANCEL_ACTOR_SYSTEM,
            reason=expiry_reason,
            created_at=current_time,
        )
        booking.status = EXPIRED
        booking.cancelled_at = current_time
        booking.cancelled_by = CANCEL_ACTOR_SYSTEM
        booking.cancel_reason = expiry_reason

        _release_schedule(db, booking.id)

        pending_transactions = db.scalars(
            select(PaymentTransaction).where(
                PaymentTransaction.booking_id == booking.id,
                PaymentTransaction.status == PENDING_STATUS,
            )
        ).all()
        for transaction in pending_transactions:
            transaction.status = EXPIRED_STATUS

        expired += 1

    if scanned:
        db.commit()

    return ExpiryResult(
        scanned=scanned,
        expired=expired,
        paid_race=paid_race,
        skipped=skipped,
    )
