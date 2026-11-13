
from pydantic import BaseModel
from typing import Optional


class VehicleBase(BaseModel):
    store_id: int
    vehicle_type: str
    plate_number: str
    brand: str
    model: str
    year_of_manufacture: Optional[int] = None
    engine_capacity: Optional[int] = None
    transmission_type: Optional[str] = None
    seats: Optional[int] = None
    body_type: Optional[str] = None
    fuel_type: Optional[str] = None
    price_per_day: float
    price_per_hour: Optional[float] = None
    current_status: str = "AVAILABLE"
    description: Optional[str] = None
    is_active: bool = True


class VehicleCreate(VehicleBase):
    pass


class VehicleUpdate(BaseModel):
    store_id: Optional[int] = None
    vehicle_type: Optional[str] = None
    plate_number: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    year_of_manufacture: Optional[int] = None
    engine_capacity: Optional[int] = None
    transmission_type: Optional[str] = None
    seats: Optional[int] = None
    body_type: Optional[str] = None
    fuel_type: Optional[str] = None
    price_per_day: Optional[float] = None
    price_per_hour: Optional[float] = None
    current_status: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class VehicleResponse(VehicleBase):
    id: int

    class Config:
        from_attributes = True


class VehicleImageResponse(BaseModel):
    id: int
    image_url: str
    is_primary: bool = False
    sort_order: Optional[int] = None

    class Config:
        from_attributes = True


class StoreSummary(BaseModel):
    id: int
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None

    class Config:
        from_attributes = True


class DeliveryPointSummary(BaseModel):
    id: int
    name: Optional[str] = None
    address: Optional[str] = None
    area: Optional[str] = None
    delivery_fee: float = 0

    class Config:
        from_attributes = True


class PublicVehicleDetailResponse(BaseModel):
    """Chi tiết phương tiện dành cho khách chưa đăng nhập.

    Không trả về biển số xe và các trường nội bộ của cửa hàng.
    """

    id: int
    store_id: int
    store: StoreSummary

    vehicle_type: str
    brand: str
    model: str
    year_of_manufacture: Optional[int] = None
    engine_capacity: Optional[int] = None
    transmission_type: Optional[str] = None
    seats: Optional[int] = None
    body_type: Optional[str] = None
    fuel_type: Optional[str] = None

    price_per_day: float
    price_per_hour: Optional[float] = None

    current_status: str
    is_available: Optional[bool] = None
    unavailable_reason: Optional[str] = None
    description: Optional[str] = None

    images: list[VehicleImageResponse] = []
    delivery_points: list[DeliveryPointSummary] = []
