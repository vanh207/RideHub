"""Tạo đơn thuê và giữ chỗ xe 30 phút (TF197DE).

Luồng giao dịch:
1. Validate input không cần DB.
2. Khóa dòng ``vehicles`` bằng ``SELECT ... FOR UPDATE``.
3. Kiểm tra khách, cửa hàng, điểm giao và lịch chiếm dụng.
4. Tính tiền thuê/cọc, tạo Booking + VehicleReservation + VehicleSchedule.
5. Commit trong cùng transaction; retry khi MySQL báo deadlock/lock timeout.

Giả định đã ghi rõ trong báo cáo:
- Cọc theo BR-03: 30% tiền thuê, tối thiểu 200.000đ, tối đa 1.000.000đ.
- SRS không quy định cách làm tròn giá; dùng giá giờ cho lượt dưới 24 giờ
  nếu xe có ``price_per_hour``, còn lại làm tròn lên theo ngày.
- SRS không quy định khoảng tối thiểu trước giờ nhận; cấu hình mặc định 0 phút.
- Model Booking chưa có cột ``customer_note`` nên field này được nhận nhưng
  bỏ qua, không sửa model.
- Chưa triển khai idempotency vì cần bảng/lưu vết riêng ngoài phạm vi task.
"""
from __future__ import annotations

import math
import time
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.booking_status import CANCEL_ACTOR_CUSTOMER
from app.core.config import settings
from app.core.kyc_errors import KycBusinessError, KycErrorCode
from app.core.kyc_status import APPROVED, normalize_status
from app.crud.booking_status_history import record_booking_status_change
from app.crud.vehicle import (
    MAX_RENTAL_DURATION,
    MIN_RENTAL_DURATION,
    vehicle_has_conflict,
)
from app.models.booking import Booking
from app.models.delivery import DeliveryPoint
from app.models.store import Store
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.vehicle_reservation import VehicleReservation
from app.models.vehicle_schedule import VehicleSchedule
from app.schemas.booking import BookingHoldCreate, BookingHoldResponse
from app.services.kyc_service import resolve_current_status

MONEY_QUANT = Decimal("0.01")
HOLD_BOOKING_STATUS = "PENDING_PAYMENT"
ACTIVE_RESERVATION_STATUS = "ACTIVE"
ACTIVE_SCHEDULE_STATUS = "ACTIVE"
RENTAL_SCHEDULE_TYPE = "RENTAL"

VEHICLE_NOT_FOUND_MESSAGE = (
    "Không tìm thấy phương tiện hoặc phương tiện không khả dụng."
)
CONFLICT_MESSAGE = (
    "Xe đã có lịch trong khoảng thời gian này. "
    "Vui lòng chọn xe hoặc khung giờ khác."
)
BUSY_MESSAGE = "Hệ thống đang bận, vui lòng thử lại sau ít giây."


class BookingError(Exception):
    """Lỗi nghiệp vụ cơ bản của luồng đặt xe."""


class BookingValidationError(BookingError):
    """Input không hợp lệ (router ánh xạ 422)."""


class BookingNotFoundError(BookingError):
    """Không thấy xe/cửa hàng (router ánh xạ 404)."""


class BookingConflictError(BookingError):
    """Khung giờ đã bị chiếm (router ánh xạ 409)."""


class BookingUnavailableError(BookingError):
    """Không lấy được khóa sau nhiều lần retry (router ánh xạ 503)."""


def _money(value) -> Decimal:
    if value is None:
        return Decimal("0.00")
    return Decimal(str(value)).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _to_local_naive(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone().replace(tzinfo=None)
    return value


def _is_retryable_lock_error(exc: OperationalError) -> bool:
    """Nhận diện MySQL deadlock (1213) hoặc lock wait timeout (1205)."""
    original = getattr(exc, "orig", None)
    if original is None:
        return False

    code = None
    args = getattr(original, "args", ())
    if args:
        code = args[0]
    if code is None:
        code = getattr(original, "errno", None)

    try:
        return int(code) in (1213, 1205)
    except (TypeError, ValueError):
        return False


def _validate_payload(
    payload: BookingHoldCreate,
    customer_id: int,
    now: datetime,
) -> tuple[datetime, datetime]:
    if customer_id <= 0:
        raise BookingValidationError("customer_id không hợp lệ.")
    if payload.vehicle_id <= 0:
        raise BookingValidationError("vehicle_id không hợp lệ.")

    start_time = _to_local_naive(payload.start_time)
    end_time = _to_local_naive(payload.end_time)

    if end_time <= start_time:
        raise BookingValidationError("end_time phải lớn hơn start_time.")

    duration = end_time - start_time
    if duration < MIN_RENTAL_DURATION:
        raise BookingValidationError(
            "Thời gian thuê tối thiểu là 4 giờ theo BR-02."
        )
    if duration > MAX_RENTAL_DURATION:
        raise BookingValidationError(
            "Thời gian thuê tối đa là 30 ngày theo BR-02."
        )

    # SRS không quy định khoảng tối thiểu trước giờ nhận. Chỉ áp dụng nếu
    # sau này cấu hình BOOKING_MIN_START_LEAD_MINUTES được đặt > 0.
    if settings.BOOKING_MIN_START_LEAD_MINUTES > 0:
        earliest_start = now + timedelta(
            minutes=settings.BOOKING_MIN_START_LEAD_MINUTES
        )
        if start_time < earliest_start:
            raise BookingValidationError(
                "start_time quá gần thời điểm hiện tại."
            )

    return start_time, end_time


def _ensure_customer_exists(db: Session, customer_id: int) -> None:
    # Chỉ select cột id: model User có hashed_password nhưng bảng SQL thật không có.
    existing_id = db.scalar(select(User.id).where(User.id == customer_id))
    if existing_id is None:
        raise BookingValidationError("customer_id không tồn tại.")


def ensure_customer_verified(db: Session, customer_id: int) -> None:
    """Chặn đặt xe khi eKYC được yêu cầu nhưng hồ sơ khách chưa được duyệt."""
    if not settings.KYC_ENABLED or not settings.KYC_REQUIRED_FOR_BOOKING:
        return
    user = db.scalar(select(User).where(User.id == customer_id))
    role = (getattr(user, "role", "customer") or "customer").lower()
    if role != "customer":
        return
    status, _, _ = resolve_current_status(db, customer_id)
    current_status = normalize_status(status)
    if current_status != APPROVED:
        raise KycBusinessError(
            KycErrorCode.KYC_NOT_APPROVED,
            details={"status": current_status or "NOT_STARTED"},
        )


def _lock_vehicle(db: Session, vehicle_id: int) -> Vehicle:
    vehicle = db.execute(
        select(Vehicle).where(Vehicle.id == vehicle_id).with_for_update()
    ).scalar_one_or_none()
    if vehicle is None or not vehicle.is_active:
        raise BookingNotFoundError(VEHICLE_NOT_FOUND_MESSAGE)
    return vehicle


def _get_approved_store_id(db: Session, store_id: Optional[int]) -> int:
    approved_store_id = db.scalar(
        select(Store.id).where(
            Store.id == store_id,
            func.upper(func.trim(Store.status)) == "APPROVED",
        )
    )
    if approved_store_id is None:
        raise BookingNotFoundError(VEHICLE_NOT_FOUND_MESSAGE)
    return approved_store_id


def _get_delivery_fee(
    db: Session,
    delivery_point_id: Optional[int],
    store_id: int,
) -> Decimal:
    if delivery_point_id is None:
        return Decimal("0.00")

    # Không select toàn bộ DeliveryPoint vì model có delivery_fee_zone_id
    # nhưng bảng SQL thật không có cột này.
    row = db.execute(
        select(
            DeliveryPoint.store_id,
            DeliveryPoint.delivery_fee,
            DeliveryPoint.is_active,
        ).where(DeliveryPoint.id == delivery_point_id)
    ).first()

    if row is None or not row.is_active or row.store_id != store_id:
        raise BookingValidationError(
            "Điểm giao không hợp lệ hoặc không thuộc cửa hàng của xe."
        )
    return _money(row.delivery_fee)


def calculate_rental_amount(
    vehicle: Vehicle,
    start_time: datetime,
    end_time: datetime,
) -> Decimal:
    duration_seconds = int((end_time - start_time).total_seconds())
    price_per_day = _money(vehicle.price_per_day)
    price_per_hour = (
        _money(vehicle.price_per_hour)
        if vehicle.price_per_hour is not None
        else None
    )

    if price_per_day <= 0:
        raise BookingValidationError("Xe chưa được cấu hình giá thuê hợp lệ.")
    if price_per_hour is not None and price_per_hour <= 0:
        price_per_hour = None

    hourly_limit_seconds = settings.BOOKING_HOURLY_MAX_HOURS * 3600
    if price_per_hour is not None and duration_seconds < hourly_limit_seconds:
        hours = math.ceil(duration_seconds / 3600)
        return _money(price_per_hour * Decimal(hours))

    days = math.ceil(duration_seconds / 86400)
    return _money(price_per_day * Decimal(days))


def calculate_deposit_amount(rental_amount: Decimal) -> Decimal:
    deposit = rental_amount * settings.BOOKING_DEPOSIT_RATE
    deposit = max(deposit, settings.BOOKING_DEPOSIT_MIN)
    deposit = min(deposit, settings.BOOKING_DEPOSIT_MAX)
    return _money(deposit)


def _create_booking_tx(
    db: Session,
    payload: BookingHoldCreate,
    customer_id: int,
    start_time: datetime,
    end_time: datetime,
    now: Optional[datetime],
) -> BookingHoldResponse:
    attempt_now = now or datetime.now()

    # Bước 2: khóa xe trước mọi truy vấn nghiệp vụ để tránh race condition.
    vehicle = _lock_vehicle(db, payload.vehicle_id)

    # Các truy vấn dưới đây chạy sau khi đã khóa xe. Không đọc DB trước khóa
    # để tránh snapshot REPEATABLE READ cũ che mất booking vừa commit.
    _ensure_customer_exists(db, customer_id)
    store_id = _get_approved_store_id(db, vehicle.store_id)
    delivery_fee = _get_delivery_fee(
        db, payload.delivery_point_id, store_id
    )

    if vehicle_has_conflict(
        db,
        vehicle.id,
        start_time,
        end_time,
        now=attempt_now,
    ):
        raise BookingConflictError(CONFLICT_MESSAGE)

    ensure_customer_verified(db, customer_id)

    rental_amount = calculate_rental_amount(vehicle, start_time, end_time)
    deposit_amount = calculate_deposit_amount(rental_amount)
    total_amount = _money(rental_amount + delivery_fee)
    hold_expires_at = attempt_now + timedelta(
        minutes=settings.BOOKING_HOLD_MINUTES
    )

    booking = Booking(
        customer_id=customer_id,
        vehicle_id=vehicle.id,
        store_id=store_id,
        delivery_point_id=payload.delivery_point_id,
        start_time=start_time,
        end_time=end_time,
        hold_expires_at=hold_expires_at,
        status=HOLD_BOOKING_STATUS,
        rental_amount=rental_amount,
        delivery_fee=delivery_fee,
        deposit_amount=deposit_amount,
        total_amount=total_amount,
        # Booking model chưa có customer_note; payload.customer_note bị bỏ qua.
    )
    db.add(booking)
    db.flush()
    record_booking_status_change(
        db,
        booking,
        "",
        HOLD_BOOKING_STATUS,
        changed_by=CANCEL_ACTOR_CUSTOMER,
        changed_by_user_id=customer_id,
        reason="BOOKING_CREATED",
        created_at=attempt_now,
    )

    reservation = VehicleReservation(
        vehicle_id=vehicle.id,
        customer_id=customer_id,
        booking_id=booking.id,
        start_time=start_time,
        end_time=end_time,
        expires_at=hold_expires_at,
        status=ACTIVE_RESERVATION_STATUS,
    )
    db.add(reservation)
    db.flush()

    schedule = VehicleSchedule(
        vehicle_id=vehicle.id,
        booking_id=booking.id,
        reservation_id=reservation.id,
        schedule_type=RENTAL_SCHEDULE_TYPE,
        start_time=start_time,
        end_time=end_time,
        status=ACTIVE_SCHEDULE_STATUS,
        note="Giữ chỗ tự động khi tạo đơn",
    )
    db.add(schedule)
    db.flush()

    # Dựng response trước khi commit để không phải đọc lại DB sau commit.
    response = BookingHoldResponse(
        id=booking.id,
        booking_code=None,
        status=booking.status,
        vehicle_id=booking.vehicle_id,
        store_id=booking.store_id,
        start_time=booking.start_time,
        end_time=booking.end_time,
        hold_expires_at=booking.hold_expires_at,
        rental_amount=float(booking.rental_amount),
        delivery_fee=float(booking.delivery_fee),
        deposit_amount=float(booking.deposit_amount),
        total_amount=float(booking.total_amount),
        reservation_id=reservation.id,
    )
    db.commit()
    return response


def create_booking_with_hold(
    db: Session,
    payload: BookingHoldCreate,
    *,
    customer_id: int,
    now: Optional[datetime] = None,
) -> BookingHoldResponse:
    """Tạo Booking + giữ chỗ + lịch thuê trong một transaction."""
    validation_now = now or datetime.now()
    start_time, end_time = _validate_payload(
        payload, customer_id, validation_now
    )

    attempts = max(1, settings.BOOKING_LOCK_RETRY_ATTEMPTS)
    for attempt in range(attempts):
        try:
            return _create_booking_tx(
                db,
                payload,
                customer_id,
                start_time,
                end_time,
                now,
            )
        except OperationalError as exc:
            db.rollback()
            if not _is_retryable_lock_error(exc):
                raise
            if attempt >= attempts - 1:
                raise BookingUnavailableError(BUSY_MESSAGE) from exc
            delay = settings.BOOKING_LOCK_RETRY_BASE_DELAY_SECONDS * (
                2 ** attempt
            )
            time.sleep(delay)
        except Exception:
            db.rollback()
            raise

    raise BookingUnavailableError(BUSY_MESSAGE)
