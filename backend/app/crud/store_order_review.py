"""Module xử lý nghiệp vụ Cửa hàng duyệt / từ chối đơn đặt xe (TF1A595).

Đáp ứng trọn vẹn yêu cầu nghiệp vụ:
1. Phân quyền chặt chẽ (RBAC):
   - Admin: toàn quyền duyệt/từ chối mọi đơn trên hệ thống.
   - Store Owner: chỉ duyệt/từ chối các đơn thuộc cửa hàng của mình sở hữu.
   - Store Staff (ACTIVE): chỉ duyệt/từ chối các đơn thuộc cửa hàng mình làm việc.
   - Customer hoặc người ngoài: 403 Forbidden.
2. Xác nhận đơn (Store Confirm / Approve):
   - Trạng thái chuyển sang CONFIRMED.
   - VehicleReservation & VehicleSchedule chuyển sang trạng thái đã chốt.
   - Ghi nhật ký trạng thái BookingStatusHistory.
   - Gửi email thông báo cho khách hàng chuẩn bị nhận xe.
3. Từ chối đơn kèm lý do (Store Reject with Reason):
   - Bắt buộc phải có lý do từ chối (min length >= 3).
   - Vì cửa hàng từ chối, khách hàng được hoàn 100% tiền cọc (Zero-fee cancellation policy).
   - Tự động tạo bản ghi Refund và kích hoạt hoàn qua VietQR/PayOS.
   - Giải phóng lịch xe (VehicleReservation, VehicleSchedule -> CANCELLED).
   - Trạng thái đơn chuyển sang CANCELLED, lưu cancelled_at, cancelled_by='STORE', cancel_reason.
   - Ghi BookingStatusHistory.
   - Gửi email giải thích lý do từ chối và thông báo hoàn cọc tới khách.
4. Quản lý danh sách đơn & KPI cho cửa hàng:
   - Truy vấn danh sách đơn hàng thực tế từ DB, hỗ trợ lọc trạng thái, tìm kiếm, phân trang và tính KPI tài chính.
"""
from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.booking_status import (
    CANCEL_ACTOR_STORE,
    CANCELLED,
    CONFIRMED,
    DEPOSIT_PAID,
    EXPIRED,
    IN_PROGRESS,
    PENDING_PAYMENT,
    PENDING_SETTLEMENT,
    COMPLETED,
    normalize_status,
)
from app.crud.booking_cancellation import (
    BookingCancellationError,
    BookingNotFoundError,
    BookingPermissionError,
    BookingStateError,
    _latest_success_transaction,
    _money,
    _release_schedule,
    get_paid_amount,
)
from app.crud.booking_status_history import record_booking_status_change
from app.models.booking import Booking
from app.models.payment import PaymentTransaction, Refund
from app.models.store import Store, StoreStaff
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.vehicle_reservation import VehicleReservation
from app.models.vehicle_schedule import VehicleSchedule
from app.schemas.booking import (
    StoreOrderConfirmResponse,
    StoreOrderCustomerInfo,
    StoreOrderItem,
    StoreOrderKPIMetrics,
    StoreOrderListResponse,
    StoreOrderPricingInfo,
    StoreOrderRejectResponse,
    StoreOrderScheduleInfo,
    StoreOrderVehicleInfo,
)
from app.services.email_service import email_service

logger = logging.getLogger("ridehub.store_order_review")


class BookingValidationError(BookingCancellationError):
    """Lỗi dữ liệu đầu vào không hợp lệ (lý do từ chối trống)."""
    pass


def _select_for_update(stmt, db: Session):
    if db.bind is not None and db.bind.dialect.name == "mysql":
        return stmt.with_for_update()
    return stmt


def get_user_store_ids(db: Session, user: User) -> list[int]:
    """Lấy danh sách các store_id mà user có quyền quản lý (chủ hoặc nhân viên)."""
    user_role = (user.role or "").lower()
    if user_role == "admin":
        return []  # Admin có quyền trên tất cả cửa hàng

    store_ids: set[int] = set()

    # Chủ cửa hàng
    owned_stores = db.scalars(
        select(Store.id).where(Store.owner_user_id == user.id)
    ).all()
    store_ids.update(owned_stores)

    # Nhân viên cửa hàng đang hoạt động
    staff_stores = db.scalars(
        select(StoreStaff.store_id).where(
            StoreStaff.user_id == user.id,
            StoreStaff.status == "ACTIVE",
        )
    ).all()
    store_ids.update(staff_stores)

    return list(store_ids)


def validate_store_operator(db: Session, booking: Booking, user: User) -> bool:
    """Kiểm tra người dùng hiện tại có quyền thao tác trên đơn hàng này không."""
    user_role = (user.role or "").lower()
    if user_role == "admin":
        return True

    booking_store_id = booking.store_id
    if booking_store_id is None:
        # Nếu booking chưa có store_id, tra cứu từ xe
        vehicle = db.query(Vehicle).filter(Vehicle.id == booking.vehicle_id).first()
        if vehicle and vehicle.store_id:
            booking_store_id = vehicle.store_id

    if not booking_store_id:
        return False

    # Kiểm tra xem user có phải chủ cửa hàng không
    is_owner = db.scalar(
        select(Store.id).where(
            Store.id == booking_store_id,
            Store.owner_user_id == user.id,
        )
    )
    if is_owner:
        return True

    # Kiểm tra xem user có phải nhân viên ACTIVE của cửa hàng không
    is_staff = db.scalar(
        select(StoreStaff.id).where(
            StoreStaff.store_id == booking_store_id,
            StoreStaff.user_id == user.id,
            StoreStaff.status == "ACTIVE",
        )
    )
    return is_staff is not None


def store_confirm_booking(
    db: Session,
    booking_id: int,
    user: User,
    note: Optional[str] = None,
    now: Optional[datetime] = None,
) -> StoreOrderConfirmResponse:
    """Cửa hàng xác nhận duyệt đơn đặt xe (TF1A595)."""
    confirm_time = now or datetime.now()

    # Khóa đơn để tránh tranh chấp dữ liệu
    booking = db.execute(
        _select_for_update(select(Booking).where(Booking.id == booking_id), db)
    ).scalar_one_or_none()

    if booking is None:
        raise BookingNotFoundError("Không tìm thấy đơn đặt xe.")

    if not validate_store_operator(db, booking, user):
        raise BookingPermissionError(
            "Bạn không có quyền thao tác trên đơn hàng của cửa hàng này."
        )

    current_status = normalize_status(booking.status)

    # Tính Idempotent: Nếu đơn đã xác nhận trước đó thì trả về thành công an toàn
    if current_status == CONFIRMED:
        return StoreOrderConfirmResponse(
            success=True,
            message="Đơn đặt xe đã được xác nhận trước đó.",
            booking_id=booking.id,
            status=CONFIRMED,
            confirmed_at=booking.updated_at or confirm_time,
            confirmed_by_user_id=user.id,
            already_confirmed=True,
        )

    if current_status in {CANCELLED, EXPIRED}:
        raise BookingStateError(
            f"Đơn đặt xe đã bị hủy hoặc hết hạn ({booking.status}), không thể xác nhận."
        )

    if current_status in {IN_PROGRESS, PENDING_SETTLEMENT, COMPLETED}:
        raise BookingStateError(
            f"Đơn đặt xe đang hoặc đã hoàn tất thuê ({booking.status}), không thể xác nhận lại."
        )

    old_status = booking.status or ""
    history_reason = note or "Cửa hàng xác nhận duyệt đơn đặt xe"

    # Cập nhật trạng thái đơn sang CONFIRMED
    booking.status = CONFIRMED
    booking.updated_at = confirm_time

    # Cập nhật VehicleReservation sang trạng thái CONFIRMED
    reservations = db.scalars(
        select(VehicleReservation).where(
            VehicleReservation.booking_id == booking.id,
            VehicleReservation.status == "ACTIVE",
        )
    ).all()
    for res in reservations:
        res.status = "CONFIRMED"

    # Cập nhật ghi chú trên VehicleSchedule
    schedules = db.scalars(
        select(VehicleSchedule).where(
            VehicleSchedule.booking_id == booking.id,
            VehicleSchedule.status == "ACTIVE",
        )
    ).all()
    for sch in schedules:
        sch.note = f"Cửa hàng đã xác nhận đơn. {note or ''}".strip()

    # Ghi nhận vết lịch sử trạng thái
    record_booking_status_change(
        db,
        booking,
        old_status,
        CONFIRMED,
        changed_by=CANCEL_ACTOR_STORE,
        changed_by_user_id=user.id,
        reason=history_reason,
        created_at=confirm_time,
    )

    db.commit()

    # Gửi email thông báo cho khách hàng (Fail-safe, không ảnh hưởng transaction)
    try:
        customer = db.query(User).filter(User.id == booking.customer_id).first()
        vehicle = db.query(Vehicle).filter(Vehicle.id == booking.vehicle_id).first()
        store = (
            db.query(Store).filter(Store.id == booking.store_id).first()
            if booking.store_id
            else None
        )

        if customer and customer.email:
            v_name = f"{vehicle.brand} {vehicle.model}" if (vehicle and hasattr(vehicle, "brand") and hasattr(vehicle, "model")) else (getattr(vehicle, "name", "Phương tiện thuê") if vehicle else "Phương tiện thuê")
            v_plate = getattr(vehicle, "plate_number", getattr(vehicle, "license_plate", "Chưa xếp biển")) if vehicle else "Chưa xếp biển"
            email_service.send_store_order_confirmation(
                to_email=customer.email,
                customer_name=customer.full_name or "Quý khách",
                booking_id=booking.id,
                vehicle_name=v_name,
                license_plate=v_plate,
                start_time=booking.start_time.strftime("%H:%M - %d/%m/%Y")
                if booking.start_time
                else "",
                end_time=booking.end_time.strftime("%H:%M - %d/%m/%Y")
                if booking.end_time
                else "",
                store_name=store.name if store else "Trạm RideHub",
                store_phone=store.phone or "1900-7433" if store else "1900-7433",
                store_address=getattr(store, "address", "Trạm đối tác RideHub") if store else "Trạm đối tác RideHub",
            )
    except Exception as exc:
        logger.warning("Không thể gửi email xác nhận đơn cho khách: %s", exc)

    return StoreOrderConfirmResponse(
        success=True,
        message="Cửa hàng đã xác nhận duyệt đơn đặt xe thành công.",
        booking_id=booking.id,
        status=CONFIRMED,
        confirmed_at=confirm_time,
        confirmed_by_user_id=user.id,
        already_confirmed=False,
    )


def store_reject_booking(
    db: Session,
    booking_id: int,
    user: User,
    reason: str,
    note: Optional[str] = None,
    now: Optional[datetime] = None,
) -> StoreOrderRejectResponse:
    """Cửa hàng từ chối nhận đơn đặt xe kèm lý do bắt buộc (TF1A595)."""
    reject_time = now or datetime.now()
    clean_reason = (reason or "").strip()

    if not clean_reason or len(clean_reason) < 3:
        raise BookingValidationError(
            "Lý do từ chối đơn là bắt buộc (tối thiểu 3 ký tự)."
        )

    # Khóa đơn để tránh tranh chấp dữ liệu
    booking = db.execute(
        _select_for_update(select(Booking).where(Booking.id == booking_id), db)
    ).scalar_one_or_none()

    if booking is None:
        raise BookingNotFoundError("Không tìm thấy đơn đặt xe.")

    if not validate_store_operator(db, booking, user):
        raise BookingPermissionError(
            "Bạn không có quyền thao tác trên đơn hàng của cửa hàng này."
        )

    current_status = normalize_status(booking.status)

    # Idempotent: Nếu đơn đã hủy từ trước
    if current_status in {CANCELLED, EXPIRED}:
        existing_refund = (
            db.query(Refund)
            .filter(Refund.booking_id == booking.id)
            .order_by(Refund.id.desc())
            .first()
        )
        return StoreOrderRejectResponse(
            success=True,
            message="Đơn đặt xe đã được xử lý hủy trước đó.",
            booking_id=booking.id,
            status=CANCELLED,
            cancelled_at=booking.cancelled_at or reject_time,
            cancelled_by=booking.cancelled_by or CANCEL_ACTOR_STORE,
            cancel_reason=booking.cancel_reason or clean_reason,
            refund_amount=float(existing_refund.amount) if existing_refund else 0.0,
            refund_rate=1.0,
            refund_status=existing_refund.status if existing_refund else None,
            refund_id=existing_refund.id if existing_refund else None,
            already_cancelled=True,
        )

    if current_status in {IN_PROGRESS, PENDING_SETTLEMENT, COMPLETED}:
        raise BookingStateError(
            f"Đơn đặt xe đang hoặc đã hoàn tất thuê ({booking.status}), không thể từ chối."
        )

    # QUY TRÌNH HOÀN TIỀN CỌC 100% (Vì lỗi từ chối xuất phát từ cửa hàng)
    paid_amount = get_paid_amount(db, booking.id)
    refund_amount = paid_amount if paid_amount > 0 else _money(booking.deposit_amount)

    # Giải phóng lịch giữ xe
    _release_schedule(db, booking.id, reservation_status="CANCELLED")

    # Tạo bản ghi Refund
    refund_id: Optional[int] = None
    refund_status: str = "PENDING"

    if refund_amount > 0:
        transaction = _latest_success_transaction(db, booking.id)
        if transaction is not None:
            try:
                from app.services.payment_gateway import payment_gateway_service

                gateway_res = payment_gateway_service.process_refund(
                    transaction_code=transaction.transaction_code,
                    amount=float(refund_amount),
                    reason=f"Cửa hàng từ chối: {clean_reason}",
                )
                if str(gateway_res.get("status", "")).upper() == "SUCCESS":
                    refund_status = "SUCCESS"
            except Exception as exc:
                logger.warning("Cổng thanh toán tự động hoàn tiền báo lỗi: %s", exc)

        refund = Refund(
            booking_id=booking.id,
            payment_transaction_id=transaction.id if transaction else None,
            amount=refund_amount,
            reason=f"STORE_REJECT_100_PERCENT: {clean_reason}",
            status=refund_status,
            processed_by=user.id,
            processed_at=reject_time if refund_status == "SUCCESS" else None,
        )
        db.add(refund)
        db.flush()
        refund_id = refund.id

        if refund_status == "SUCCESS" and transaction is not None:
            transaction.status = "REFUNDED"

    old_status = booking.status or ""
    history_reason = f"Cửa hàng từ chối đơn: {clean_reason}"

    # Cập nhật thông tin hủy trên Booking
    booking.status = CANCELLED
    booking.cancelled_at = reject_time
    booking.cancelled_by = CANCEL_ACTOR_STORE
    booking.cancel_reason = clean_reason
    booking.updated_at = reject_time

    # Ghi nhận vết lịch sử trạng thái
    record_booking_status_change(
        db,
        booking,
        old_status,
        CANCELLED,
        changed_by=CANCEL_ACTOR_STORE,
        changed_by_user_id=user.id,
        reason=history_reason,
        created_at=reject_time,
    )

    db.commit()

    # Gửi email giải thích lý do từ chối và thông tin hoàn 100% cọc
    try:
        customer = db.query(User).filter(User.id == booking.customer_id).first()
        vehicle = db.query(Vehicle).filter(Vehicle.id == booking.vehicle_id).first()

        if customer and customer.email:
            v_name = f"{vehicle.brand} {vehicle.model}" if (vehicle and hasattr(vehicle, "brand") and hasattr(vehicle, "model")) else (getattr(vehicle, "name", "Phương tiện đặt") if vehicle else "Phương tiện đặt")
            email_service.send_store_order_rejection(
                to_email=customer.email,
                customer_name=customer.full_name or "Quý khách",
                booking_id=booking.id,
                vehicle_name=v_name,
                reject_reason=clean_reason,
                refund_amount=float(refund_amount),
                bank_name="Tài khoản thanh toán ban đầu (VietQR / PayOS)",
            )
    except Exception as exc:
        logger.warning("Không thể gửi email từ chối đơn cho khách: %s", exc)

    return StoreOrderRejectResponse(
        success=True,
        message="Đã từ chối đơn đặt xe và tự động kích hoạt hoàn 100% tiền cọc cho khách hàng.",
        booking_id=booking.id,
        status=CANCELLED,
        cancelled_at=reject_time,
        cancelled_by=CANCEL_ACTOR_STORE,
        cancel_reason=clean_reason,
        refund_amount=float(refund_amount),
        refund_rate=1.0,
        refund_status=refund_status,
        refund_id=refund_id,
        already_cancelled=False,
    )


def get_store_orders_list(
    db: Session,
    user: User,
    store_id: Optional[int] = None,
    status_filter: str = "all",
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> StoreOrderListResponse:
    """Truy vấn danh sách đơn hàng cho Cửa hàng kèm theo chỉ số KPI thực tế."""
    user_role = (user.role or "").lower()

    # Xử lý trường hợp được gọi trực tiếp bằng Python function mà tham số mặc định là FastAPI Query object
    if store_id is not None and not isinstance(store_id, int):
        store_id = None
    if search is not None and not isinstance(search, str):
        search = None
    if not isinstance(page, int):
        page = 1
    if not isinstance(page_size, int):
        page_size = 20

    target_store_ids = []

    if user_role == "admin":
        if store_id:
            target_store_ids = [store_id]
        else:
            # Admin xem tất cả các đơn
            target_store_ids = []
    else:
        user_stores = get_user_store_ids(db, user)
        if not user_stores:
            raise BookingPermissionError("Bạn chưa được liên kết với bất kỳ cửa hàng nào.")
        if store_id and store_id in user_stores:
            target_store_ids = [store_id]
        else:
            target_store_ids = user_stores

    base_query = db.query(Booking)
    if target_store_ids:
        base_query = base_query.filter(Booking.store_id.in_(target_store_ids))

    all_orders = base_query.all()

    # Tính KPI
    total_orders = len(all_orders)
    pending_orders = sum(
        1
        for o in all_orders
        if normalize_status(o.status) in {PENDING_PAYMENT, DEPOSIT_PAID, "PENDING", "BOOKED", "PENDING_STORE_CONFIRM"}
    )
    approved_orders = sum(
        1 for o in all_orders if normalize_status(o.status) == CONFIRMED
    )
    cancelled_orders = sum(
        1 for o in all_orders if normalize_status(o.status) in {CANCELLED, EXPIRED}
    )

    active_orders = [
        o for o in all_orders if normalize_status(o.status) not in {CANCELLED, EXPIRED}
    ]
    total_deposit = sum(float(o.deposit_amount or 0) for o in active_orders)
    total_revenue = sum(float(o.total_amount or 0) for o in active_orders)
    remain_collection = max(0.0, total_revenue - total_deposit)

    metrics = StoreOrderKPIMetrics(
        total_orders=total_orders,
        pending_orders=pending_orders,
        approved_orders=approved_orders,
        cancelled_orders=cancelled_orders,
        total_deposit=total_deposit,
        total_revenue=total_revenue,
        remain_collection=remain_collection,
    )

    # Áp dụng bộ lọc
    filtered_orders = all_orders
    norm_status = (status_filter or "all").lower()

    if norm_status == "pending":
        filtered_orders = [
            o
            for o in filtered_orders
            if normalize_status(o.status)
            in {PENDING_PAYMENT, DEPOSIT_PAID, "PENDING", "BOOKED", "PENDING_STORE_CONFIRM"}
        ]
    elif norm_status in {"approved", "confirmed"}:
        filtered_orders = [
            o for o in filtered_orders if normalize_status(o.status) == CONFIRMED
        ]
    elif norm_status == "cancelled":
        filtered_orders = [
            o
            for o in filtered_orders
            if normalize_status(o.status) in {CANCELLED, EXPIRED}
        ]
    elif norm_status == "in_progress":
        filtered_orders = [
            o
            for o in filtered_orders
            if normalize_status(o.status) == IN_PROGRESS
        ]

    elif norm_status == "completed":
        filtered_orders = [
            o
            for o in filtered_orders
            if normalize_status(o.status) == COMPLETED
        ]

    # Tìm kiếm
    if search:
        s = search.lower().strip()
        filtered_orders = [
            o
            for o in filtered_orders
            if s in f"#{o.id} rh-{o.id}".lower()
        ]

    # Sắp xếp theo ID giảm dần (mới nhất lên trước)
    filtered_orders.sort(key=lambda o: o.id, reverse=True)

    # Phân trang
    total_filtered = len(filtered_orders)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paged_orders = filtered_orders[start_idx:end_idx]

    items: list[StoreOrderItem] = []
    for b in paged_orders:
        customer = db.query(User).filter(User.id == b.customer_id).first()
        vehicle = db.query(Vehicle).filter(Vehicle.id == b.vehicle_id).first()

        # Tính duration
        duration_days = 1.0
        if b.start_time and b.end_time:
            delta = b.end_time - b.start_time
            duration_days = round(max(0.5, delta.total_seconds() / 86400), 1)

        schedule_display = ""
        if b.start_time and b.end_time:
            schedule_display = f"{b.start_time.strftime('%d/%m/%Y %H:%M')} → {b.end_time.strftime('%d/%m/%Y %H:%M')}"

        st = normalize_status(b.status)
        if st in {PENDING_PAYMENT, DEPOSIT_PAID, "PENDING", "BOOKED", "PENDING_STORE_CONFIRM"}:
            status_label = "Chờ duyệt đơn"
        elif st == CONFIRMED:
            status_label = "Đã duyệt"
        elif st in {CANCELLED, EXPIRED}:
            status_label = "Đã từ chối / Hủy"
        elif st == IN_PROGRESS:
            status_label = "Đang thuê"
        elif st == COMPLETED:
            status_label = "Đã hoàn thành"
        else:
            status_label = b.status or "Không xác định"

        rental_amt = float(b.rental_amount or 0)
        delivery_amt = float(b.delivery_fee or 0)
        deposit_amt = float(b.deposit_amount or 0)
        total_amt = float(b.total_amount or 0)
        remain_amt = max(0.0, total_amt - deposit_amt)

        item = StoreOrderItem(
            id=b.id,
            booking_code=f"RH-{b.id:04d}",
            store_id=b.store_id,
            status=st.lower(),
            status_label=status_label,
            cancel_reason=b.cancel_reason,
            cancelled_by=b.cancelled_by,
            customer=StoreOrderCustomerInfo(
                id=customer.id if customer else 0,
                full_name=customer.full_name if customer else "Khách vãng lai",
                phone=customer.phone if customer else None,
                email=customer.email if customer else None,
                cccd=customer.cccd_number if hasattr(customer, "cccd_number") else None,
                ekyc_status="pass",
            ),
            vehicle=StoreOrderVehicleInfo(
                id=vehicle.id if vehicle else 0,
                name=f"{vehicle.brand} {vehicle.model}" if (vehicle and hasattr(vehicle, "brand") and hasattr(vehicle, "model")) else (getattr(vehicle, "name", "Phương tiện") if vehicle else "Phương tiện"),
                license_plate=getattr(vehicle, "plate_number", getattr(vehicle, "license_plate", "Chưa có")) if vehicle else "Chưa có",
                vehicle_type=vehicle.vehicle_type if vehicle else None,
                category_label=getattr(vehicle, "body_type", None) or getattr(vehicle, "vehicle_type", "Xe điện RideHub"),
                image_url=getattr(vehicle, "image_url", None),
            ),
            schedule=StoreOrderScheduleInfo(
                start_time=b.start_time,
                end_time=b.end_time,
                duration_days=duration_days,
                schedule_display=schedule_display,
            ),
            pricing=StoreOrderPricingInfo(
                rental_amount=rental_amt,
                delivery_fee=delivery_amt,
                deposit_amount=deposit_amt,
                total_amount=total_amt,
                paid_deposit=deposit_amt,
                remaining_amount=remain_amt,
                collateral_note="Miễn tiền cọc thế chấp (eKYC Hợp lệ)",
            ),
            created_at=b.created_at or datetime.now(),
        )
        items.append(item)

    return StoreOrderListResponse(
        success=True,
        total=total_filtered,
        page=page,
        page_size=page_size,
        metrics=metrics,
        orders=items,
    )
