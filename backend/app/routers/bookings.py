"""API tạo đơn thuê và giữ chỗ xe 30 phút (TF197DE)."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_customer_id
from app.crud import booking as booking_crud
from app.db.session import get_db
from app.schemas.booking import BookingHoldCreate, BookingHoldResponse

router = APIRouter(prefix="/bookings", tags=["Bookings"])


@router.post(
    "",
    response_model=BookingHoldResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo đơn thuê và giữ chỗ xe 30 phút",
)
def create_booking_hold(
    payload: BookingHoldCreate,
    current_customer_id: Optional[int] = Depends(get_current_customer_id),
    db: Session = Depends(get_db),
):
    """Tạo Booking + giữ chỗ 30 phút + lịch thuê trong cùng transaction.

    - 404: xe không tồn tại/không hoạt động hoặc cửa hàng chưa duyệt.
    - 409: khung giờ đã bị booking/giữ chỗ/lịch chặn chiếm.
    - 422: thời lượng/điểm giao/khách hàng không hợp lệ.
    - 503: không lấy được khóa sau nhiều lần retry.
    """
    customer_id = current_customer_id or payload.customer_id
    try:
        return booking_crud.create_booking_with_hold(
            db,
            payload,
            customer_id=customer_id,
        )
    except booking_crud.BookingValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except booking_crud.BookingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except booking_crud.BookingConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except booking_crud.BookingUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
