from types import SimpleNamespace
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.crud.booking import (
    BookingConflictError,
    BookingNotFoundError,
    BookingUnavailableError,
    BookingValidationError as BookingHoldValidationError,
    create_booking_with_hold,
)
from app.crud.booking_cancellation import (
    BookingActor,
    BookingCancellationError,
    BookingNotFoundError as BookingCancelNotFoundError,
    BookingPermissionError,
    BookingStateError,
    cancel_booking,
)
from app.crud.booking_settlement import (
    BookingSettlementNotFoundError,
    BookingSettlementPaymentError,
    BookingSettlementPermissionError,
    BookingSettlementStateError,
    BookingSettlementValidationError,
    settle_booking,
)
from app.crud.store_order_review import (
    BookingValidationError as StoreOrderValidationError,
    get_store_orders_list,
    store_confirm_booking,
    store_reject_booking,
)
from app.crud.booking_feedback import (
    BookingFeedbackConflictError,
    BookingFeedbackNotFoundError,
    BookingFeedbackPermissionError,
    BookingFeedbackStateError,
    BookingFeedbackValidationError,
    create_booking_complaint,
    create_booking_review,
)
from app.db.session import get_db
from app.models.user import User
from app.models.vehicle import Vehicle
from app.schemas.booking import (
    BookingCancelRequest,
    BookingCancelResponse,
    BookingHoldCreate,
    BookingHoldResponse,
    BookingSettlementRequest,
    BookingSettlementResponse,
    StoreOrderConfirmRequest,
    StoreOrderConfirmResponse,
    StoreOrderListResponse,
    StoreOrderRejectRequest,
    StoreOrderRejectResponse,
    BookingReviewRequest,
    BookingReviewResponse,
    BookingComplaintRequest,
    BookingComplaintResponse,
)
from app.services.booking_eligibility import check_customer_can_rent

router = APIRouter(prefix="/bookings", tags=["Bookings"])



@router.post("", response_model=BookingHoldResponse, status_code=status.HTTP_201_CREATED)
def create_booking_hold(
    payload: BookingHoldCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return create_booking_with_hold(
            db,
            payload,
            customer_id=current_user.id,
        )
    except BookingConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except BookingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except BookingUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except BookingHoldValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


class BookingEligibilityRequest(BaseModel):
    vehicle_id: int | None = None
    vehicle_type: str | None = None
    rental_start: str | None = None


class BookingEligibilityResponse(BaseModel):
    eligible: bool
    reasons: tuple[str, ...]


@router.post("/check-eligibility", response_model=BookingEligibilityResponse)
def check_booking_eligibility(
    payload: BookingEligibilityRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.vehicle_id is not None:
        vehicle = db.query(Vehicle).filter(Vehicle.id == payload.vehicle_id).first()
        if not vehicle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy phương tiện.",
            )
    elif payload.vehicle_type:
        vehicle = SimpleNamespace(vehicle_type=payload.vehicle_type)
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cần cung cấp vehicle_id hoặc vehicle_type.",
        )

    rental_start = None
    if payload.rental_start:
        from datetime import datetime

        try:
            rental_start = datetime.fromisoformat(
                payload.rental_start.replace("Z", "+00:00")
            )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="rental_start không đúng định dạng ISO 8601.",
            )

    result = check_customer_can_rent(current_user, vehicle, rental_start)
    return BookingEligibilityResponse(
        eligible=result.eligible,
        reasons=result.reasons,
    )


@router.post(
    "/{booking_id}/cancel",
    response_model=BookingCancelResponse,
    summary="Hủy đơn và tính tiền hoàn theo chính sách",
)
def cancel_booking_endpoint(
    booking_id: int,
    payload: BookingCancelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    actor = BookingActor(id=current_user.id, role=current_user.role)
    try:
        return cancel_booking(
            db,
            booking_id,
            actor=actor,
            reason=payload.reason,
        )
    except BookingCancelNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except BookingPermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except BookingStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except BookingCancellationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/{booking_id}/settle",
    response_model=BookingSettlementResponse,
    summary="Thu phần còn lại và phí phát sinh, hoàn tất đơn thuê",
    description=(
        "Chỉ admin/operator hoặc chủ/nhân viên cửa hàng phụ trách được gọi. "
        "Gọi sau khi đã thu tiền mặt/chuyển khoản thực tế và gửi amount_received "
        "khớp chính xác với số tiền cần thu; phí lấy từ biên bản CHECK_IN đã "
        "được hai bên xác nhận."
    ),
)
def settle_booking_endpoint(
    booking_id: int,
    payload: BookingSettlementRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return settle_booking(
            db,
            booking_id,
            actor=current_user,
            amount_received=payload.amount_received,
            payment_method=payload.payment_method,
        )
    except BookingSettlementNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy đơn đặt xe.",
        ) from exc
    except BookingSettlementPermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền tất toán đơn của cửa hàng này.",
        ) from exc
    except BookingSettlementPaymentError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except BookingSettlementStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except BookingSettlementValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


# ==============================================================================
# ENDPOINTS DÀNH RIÊNG CHO CỬA HÀNG DUYỆT / TỪ CHỐI ĐƠN ĐẶT XE (TF1A595)
# ==============================================================================

@router.post(
    "/{booking_id}/confirm",
    response_model=StoreOrderConfirmResponse,
    summary="Cửa hàng duyệt xác nhận đơn đặt xe (TF1A595)",
    description="Chuyển trạng thái đơn sang CONFIRMED, khóa lịch phương tiện và gửi email thông báo cho khách.",
)
def confirm_booking_endpoint(
    booking_id: int,
    payload: StoreOrderConfirmRequest = StoreOrderConfirmRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return store_confirm_booking(
            db,
            booking_id=booking_id,
            user=current_user,
            note=payload.note,
        )
    except BookingCancelNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except BookingPermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except BookingStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except StoreOrderValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except BookingCancellationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/{booking_id}/reject",
    response_model=StoreOrderRejectResponse,
    summary="Cửa hàng từ chối nhận đơn đặt xe kèm lý do (TF1A595)",
    description="Hủy đơn kèm lý do bắt buộc, giải phóng phương tiện và tự động kích hoạt hoàn 100% tiền cọc cho khách.",
)
def reject_booking_endpoint(
    booking_id: int,
    payload: StoreOrderRejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return store_reject_booking(
            db,
            booking_id=booking_id,
            user=current_user,
            reason=payload.reason,
            note=payload.note,
        )
    except BookingCancelNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except BookingPermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except BookingStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except StoreOrderValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except BookingCancellationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/{booking_id}/review",
    response_model=BookingReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Gửi đánh giá cho đơn thuê đã hoàn tất",
)
def create_booking_review_endpoint(
    booking_id: int,
    payload: BookingReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        review = create_booking_review(
            db,
            booking_id=booking_id,
            customer=current_user,
            rating=payload.rating,
            comment=payload.comment,
        )
        return BookingReviewResponse(
            id=review.id,
            booking_id=review.booking_id,
            reviewer_id=review.reviewer_id,
            rating=review.rating,
            comment=review.comment,
            created_at=review.created_at,
        )
    except BookingFeedbackNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BookingFeedbackPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except BookingFeedbackStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except BookingFeedbackConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except BookingFeedbackValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/{booking_id}/complaint",
    response_model=BookingComplaintResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Gửi khiếu nại cho đơn thuê đã hoàn tất",
)
def create_booking_complaint_endpoint(
    booking_id: int,
    payload: BookingComplaintRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        complaint = create_booking_complaint(
            db,
            booking_id=booking_id,
            customer=current_user,
            category=payload.category,
            subject=payload.subject,
            description=payload.description,
            against_user_id=payload.against_user_id,
            evidence_urls=payload.evidence_urls,
        )
        return BookingComplaintResponse(
            id=complaint.id,
            booking_id=complaint.booking_id,
            reporter_id=complaint.reporter_id,
            category=complaint.category,
            subject=complaint.subject,
            description=complaint.description,
            status=complaint.status,
            priority=complaint.priority,
            created_at=complaint.created_at,
        )
    except BookingFeedbackNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BookingFeedbackPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except BookingFeedbackStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except BookingFeedbackConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except BookingFeedbackValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(
    "/me",
    summary="Danh sách đơn đặt xe của người dùng hiện tại (đã thanh toán, chờ duyệt, chờ thanh toán)",
)
def get_my_bookings(
    group: str = Query("all", description="all | paid | pending_approval | pending_payment"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.booking import Booking
    from app.models.vehicle import Vehicle

    rows = (
        db.query(Booking, Vehicle)
        .outerjoin(Vehicle, Booking.vehicle_id == Vehicle.id)
        .filter(Booking.customer_id == current_user.id)
        .order_by(Booking.id.desc())
        .all()
    )

    def _classify(st: str) -> str:
        s = (st or "").upper()
        if s in ("PAID", "CONFIRMED", "DEPOSIT_PAID", "IN_PROGRESS", "ACTIVE", "COMPLETED", "HANDED_OVER"):
            return "paid"
        if s in ("AWAITING_PAYMENT", "HOLD", "PENDING_PAYMENT", "APPROVED"):
            return "pending_payment"
        if s in ("PENDING", "PENDING_APPROVAL", "PENDING_STORE_APPROVAL", "BOOKED"):
            return "pending_approval"
        return "other"

    items = []
    for b, v in rows:
        grp = _classify(b.status)
        if group != "all" and grp != group:
            continue
        items.append({
            "id": b.id,
            "order_code": f"RH-{b.id}",
            "vehicle_id": b.vehicle_id,
            "vehicle_name": v.name if v else f"Xe #{b.vehicle_id}",
            "license_plate": v.license_plate if v else "",
            "start_time": b.start_time.isoformat() if b.start_time else None,
            "end_time": b.end_time.isoformat() if b.end_time else None,
            "hold_expires_at": b.hold_expires_at.isoformat() if b.hold_expires_at else None,
            "status": b.status,
            "group": grp,
            "rental_amount": float(b.rental_amount or 0),
            "delivery_fee": float(b.delivery_fee or 0),
            "deposit_amount": float(b.deposit_amount or 0),
            "deposit_type": getattr(b, "deposit_type", None) or "CASH",
            "collateral_info": getattr(b, "collateral_info", None),
            "total_amount": float(b.total_amount or 0),
        })

    return {"success": True, "total": len(items), "items": items}


@router.get(
    "/store/orders",
    response_model=StoreOrderListResponse,
    summary="Danh sách đơn đặt xe và chỉ số KPI cho Cửa hàng (TF1A595)",
    description="Lấy danh sách các đơn đặt xe thuộc cửa hàng của tài khoản đang đăng nhập, hỗ trợ lọc, tìm kiếm và phân trang.",
)
def get_store_orders_endpoint(
    status_filter: str = Query("all", description="Bộ lọc trạng thái: all, pending, approved, cancelled, in_progress"),
    search: Optional[str] = Query(None, description="Từ khóa tìm kiếm (mã đơn, tên, sđt)"),
    page: int = Query(1, ge=1, description="Số trang"),
    page_size: int = Query(20, ge=1, le=100, description="Số bản ghi mỗi trang"),
    store_id: Optional[int] = Query(None, description="ID cửa hàng (chỉ Admin mới được chọn tuỳ ý)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return get_store_orders_list(
            db,
            user=current_user,
            store_id=store_id,
            status_filter=status_filter,
            search=search,
            page=page,
            page_size=page_size,
        )
    except BookingPermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

