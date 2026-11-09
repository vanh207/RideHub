from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

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