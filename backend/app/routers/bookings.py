from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.vehicle import Vehicle
from app.services.booking_eligibility import check_customer_can_rent


router = APIRouter(prefix="/bookings", tags=["Bookings"])


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
