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

class ScheduleEventItem(BaseModel):
    """Một ca hoạt động của xe (Đơn thuê, Bảo dưỡng, Vệ sinh)."""
    id: str  # Ví dụ "booking-1" hoặc "schedule-5"
    event_type: str  # "RENTAL", "MAINTENANCE", "CLEANING"
    vehicle_id: int
    vehicle_name: str
    plate_number: str
    title: str
    start_time: datetime
    end_time: datetime
    status: str
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    note: Optional[str] = None
    has_conflict: bool = False
    conflict_reason: Optional[str] = None
    class Config:
        from_attributes = True
class ConflictAlert(BaseModel):
    """Cảnh báo 2 ca bị trùng giờ trên cùng một phương tiện."""
    vehicle_id: int
    vehicle_name: str
    plate_number: str
    conflict_type: str  # "DOUBLE_BOOKING", "MAINTENANCE_OVERLAP"
    event_id_1: str
    event_id_2: str
    description: str
class MaintenanceAlert(BaseModel):
    """Cảnh báo xe tới hạn hoặc đang trong ca bảo trì (FR-60)."""
    vehicle_id: int
    vehicle_name: str
    plate_number: str
    title: str
    description: str
    maintenance_date: datetime
    status: str
class ScheduleSummary(BaseModel):
    """Chỉ số KPIs tổng quan trong khoảng thời gian xem."""
    total_events: int
    total_conflicts: int
    total_maintenance_due: int
    total_active_rentals: int
class StoreVehicleScheduleOverview(BaseModel):
    """Dữ liệu trả về đầy đủ cho giao diện Lịch xe & Cảnh báo cửa hàng."""
    store_id: int
    start_date: datetime
    end_date: datetime
    view_mode: str  # "day", "week", "month"
    summary: ScheduleSummary
    conflicts: list[ConflictAlert]
    maintenance_alerts: list[MaintenanceAlert]
    events: list[ScheduleEventItem]