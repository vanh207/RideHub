from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.crud.booking import (
    BookingConflictError,
    BookingNotFoundError,
    BookingUnavailableError,
    BookingValidationError,
    create_booking_with_hold,
)
from app.db.session import get_db
from app.models.user import User
from app.models.vehicle import Vehicle
from app.services.booking_eligibility import check_customer_can_rent
from app.schemas.booking import BookingHoldCreate, BookingHoldResponse


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
    except BookingValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


class BookingEligibilityRequest(BaseModel):
    vehicle_id: int
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
    vehicle = db.query(Vehicle).filter(Vehicle.id == payload.vehicle_id).first()
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy phương tiện.",
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
