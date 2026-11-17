
from pydantic import BaseModel, ConfigDict
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


class VehicleSearchStore(BaseModel):
    """Tóm tắt cửa hàng được phép trả ra ở API công khai."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: Optional[str] = None
    city: Optional[str] = None


class VehicleSearchItem(BaseModel):
    """Một phương tiện trong kết quả tìm kiếm công khai.

    Không chứa biển số xe hoặc các trường nội bộ của cửa hàng.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    store: VehicleSearchStore
    vehicle_type: str
    brand: str
    model: str
    seats: Optional[int] = None
    transmission_type: Optional[str] = None
    fuel_type: Optional[str] = None
    price_per_day: float
    price_per_hour: Optional[float] = None
    primary_image_url: Optional[str] = None
    is_available: Optional[bool] = None


class VehicleSearchResponse(BaseModel):
    """Kết quả tìm kiếm xe có phân trang."""

    items: list[VehicleSearchItem]
    page: int
    page_size: int
    total: int
