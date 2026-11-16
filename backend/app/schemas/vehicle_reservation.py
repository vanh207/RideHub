from datetime import datetime
from typing import Optional

from pydantic import BaseModel, model_validator


class VehicleReservationBase(BaseModel):
    vehicle_id: int
    customer_id: int
    start_time: datetime
    end_time: datetime

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.start_time >= self.end_time:
            raise ValueError("start_time phải trước end_time")
        return self


class VehicleReservationCreate(VehicleReservationBase):
    pass


class VehicleReservationResponse(VehicleReservationBase):
    id: int
    booking_id: Optional[int] = None
    expires_at: datetime
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
