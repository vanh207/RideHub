
from pydantic import BaseModel
from typing import Optional


class DeliveryFeeZoneBase(BaseModel):
    store_id: int
    area: str
    delivery_fee: float
    is_active: bool = True


class DeliveryFeeZoneCreate(DeliveryFeeZoneBase):
    pass


class DeliveryFeeZoneUpdate(BaseModel):
    store_id: Optional[int] = None
    area: Optional[str] = None
    delivery_fee: Optional[float] = None
    is_active: Optional[bool] = None


class DeliveryFeeZoneResponse(DeliveryFeeZoneBase):
    id: int

    class Config:
        from_attributes = True


class DeliveryPointBase(BaseModel):
    store_id: int
    delivery_fee_zone_id: Optional[int] = None
    name: str
    address: str
    area: Optional[str] = None
    delivery_fee: float = 0
    is_active: bool = True


class DeliveryPointCreate(DeliveryPointBase):
    pass

class DeliveryPointUpdate(BaseModel):
    store_id: Optional[int] = None
    delivery_fee_zone_id: Optional[int] = None
    name: Optional[str] = None
    address: Optional[str] = None
    area: Optional[str] = None
    delivery_fee: Optional[float] = None
    is_active: Optional[bool] = None


class DeliveryPointResponse(DeliveryPointBase):
    id: int

    class Config:
        from_attributes = True
