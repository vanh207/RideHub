from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class VehicleScheduleBase(BaseModel):
    vehicle_id: int
    booking_id: Optional[int] = None
    reservation_id: Optional[int] = None
    schedule_type: str = Field(default="RENTAL", max_length=20)
    start_time: datetime
    end_time: datetime
    status: str = Field(default="ACTIVE", max_length=20)
    note: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.start_time >= self.end_time:
            raise ValueError("start_time phải trước end_time")
        if self.booking_id is None and self.reservation_id is None and self.schedule_type == "RENTAL":
            raise ValueError("Lịch RENTAL phải gắn với booking_id hoặc reservation_id")
        return self


class VehicleScheduleCreate(VehicleScheduleBase):
    pass


class VehicleScheduleResponse(VehicleScheduleBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
