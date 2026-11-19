from pydantic import BaseModel, ConfigDict, Field, model_validator
from datetime import datetime
from typing import Optional


class BookingHoldCreate(BaseModel):
    """Body tạo đơn thuê. Client không được gửi số tiền; nếu gửi sẽ bị bỏ qua."""

    model_config = ConfigDict(extra="ignore")

    customer_id: int = Field(..., gt=0)
    vehicle_id: int = Field(..., gt=0)
    start_time: datetime
    end_time: datetime
    delivery_point_id: Optional[int] = Field(None, gt=0)
    customer_note: Optional[str] = None

    @model_validator(mode="after")
    def normalize_and_validate_times(self):
        if self.start_time.tzinfo is not None:
            self.start_time = self.start_time.astimezone().replace(tzinfo=None)
        if self.end_time.tzinfo is not None:
            self.end_time = self.end_time.astimezone().replace(tzinfo=None)
        if self.end_time <= self.start_time:
            raise ValueError("end_time phải lớn hơn start_time.")
        return self


class BookingHoldResponse(BaseModel):
    id: int
    booking_code: Optional[str] = None
    status: str
    vehicle_id: int
    store_id: int
    start_time: datetime
    end_time: datetime
    hold_expires_at: datetime
    rental_amount: float
    delivery_fee: float
    deposit_amount: float
    total_amount: float
    reservation_id: int


class BookingBase(BaseModel):
    customer_id: int
    vehicle_id: int
    store_id: Optional[int] = None
    delivery_point_id: Optional[int] = None
    start_time: datetime
    end_time: datetime
    rental_amount: float
    delivery_fee: float = 0 
    deposit_amount: float = 0
    total_amount: float

class BookingCreate(BookingBase):
    pass

class BookingResponse(BookingBase):
    id: int
    status: str
    hold_expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
