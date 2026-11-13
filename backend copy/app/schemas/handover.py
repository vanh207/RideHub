from pydantic import BaseModel, Field
from typing import Optional, Any, List
from datetime import datetime

class HandoverProtocolBase(BaseModel):
    protocol_code: str = Field(..., max_length=50, description="Mã biên bản: BB-202611-xxxx")
    booking_id: int = Field(..., description="Mã đặt chỗ liên kết")
    protocol_type: str = Field("CHECK_OUT", description="CHECK_OUT hoặc CHECK_IN")
    store_agent_name: str = Field(..., max_length=100)
    store_agent_phone: Optional[str] = None
    customer_name: str = Field(..., max_length=100)
    customer_cccd: str = Field(..., max_length=20)
    customer_phone: str = Field(..., max_length=20)
    customer_license: str = Field(..., max_length=50)
    handover_location: str = Field(..., max_length=255)
    vehicle_name: str = Field(..., max_length=150)
    license_plate: str = Field(..., max_length=20)
    vehicle_category: str = Field("CAR", max_length=20)
    odo_checkout: int = 0
    odo_checkin: Optional[int] = None
    fuel_checkout: str = "FULL"
    fuel_checkin: Optional[str] = None
    damage_points: Optional[Any] = None
    checklist_data: Optional[Any] = None
    deposit_original: float = 0
    fee_overtime: float = 0
    fee_excess_km: float = 0
    fee_fuel: float = 0
    fee_cleaning: float = 0
    fee_damage: float = 0
    hold_fine_deposit: float = 0
    refund_immediate: float = 0
    customer_signature: Optional[str] = Field(None, description="Base64 hoặc URL chữ ký khách")
    staff_signature: Optional[str] = Field(None, description="Base64 hoặc URL chữ ký nhân viên")
    status: str = "COMPLETED"
    notes: Optional[str] = None

class HandoverProtocolCreate(HandoverProtocolBase):
    pass

class HandoverReturnUpdate(BaseModel):
    odo_checkin: int
    fuel_checkin: str
    damage_points: Optional[Any] = None
    fee_overtime: float = 0
    fee_excess_km: float = 0
    fee_fuel: float = 0
    fee_cleaning: float = 0
    fee_damage: float = 0
    hold_fine_deposit: float = 2000000
    refund_immediate: float
    customer_signature: Optional[str] = None
    staff_signature: Optional[str] = None
    notes: Optional[str] = None

class HandoverProtocolResponse(HandoverProtocolBase):
    id: int
    signed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

