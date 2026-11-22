"""Định nghĩa bộ kịch bản đo cố định và biên dịch SQL thật của ORM."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.dialects import mysql

from app.crud.vehicle import _escape_like, _no_conflict_conditions
from app.models.delivery import DeliveryPoint
from app.models.store import Store
from app.models.vehicle import Vehicle
from app.models.vehicle_reservation import VehicleReservation
from app.models.vehicle_schedule import VehicleSchedule
from app.models.booking import Booking

# Mốc cố định để seed và đo có thể tái lập; không phụ thuộc ngày hệ thống.
ANCHOR = datetime(2026, 11, 20, 8, 0, 0)
BUSY_START = datetime(2026, 12, 20, 8, 0, 0)
BUSY_END = BUSY_START + timedelta(days=2)


@dataclass(frozen=True)
class SearchScenario:
    """Một kịch bản tìm xe công khai."""

    code: str
    description: str
    area: Optional[str]
    vehicle_type: Optional[str]
    min_price: Optional[float]
    max_price: Optional[float]
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    sort: str
    page: int
    page_size: int
    now: datetime = ANCHOR


@dataclass(frozen=True)
class ConflictScenario:
    """Một kịch bản kiểm tra trùng lịch cho đúng một xe."""

    code: str
    description: str
    vehicle_id: int
    start_time: datetime
    end_time: datetime
    now: datetime = ANCHOR


SEARCH_SCENARIOS = {
    s.code: s
    for s in [
        SearchScenario(
            code="S1",
            description="2 ngày ở tương lai xa, đa số xe trống",
            area=None,
            vehicle_type=None,
            min_price=None,
            max_price=None,
            start_time=datetime(2027, 3, 10, 8, 0),
            end_time=datetime(2027, 3, 12, 8, 0),
            sort="price_asc",
            page=1,
            page_size=12,
        ),
        SearchScenario(
            code="S2",
            description="2 ngày trùng cao điểm many bookings, đa số xe bận",
            area=None,
            vehicle_type=None,
            min_price=None,
            max_price=None,
            start_time=BUSY_START,
            end_time=BUSY_END,
            sort="price_asc",
            page=1,
            page_size=12,
        ),
        SearchScenario(
            code="S3",
            description="S1 + khu vực + loại xe + khoảng giá",
            area="Hoan Kiem",
            vehicle_type="MOTORBIKE",
            min_price=200000,
            max_price=600000,
            start_time=datetime(2027, 3, 10, 8, 0),
            end_time=datetime(2027, 3, 12, 8, 0),
            sort="price_asc",
            page=1,
            page_size=12,
        ),
        SearchScenario(
            code="S4",
            description="Trang cuối offset lớn + COUNT",
            area=None,
            vehicle_type=None,
            min_price=None,
            max_price=None,
            start_time=datetime(2027, 3, 10, 8, 0),
            end_time=datetime(2027, 3, 12, 8, 0),
            sort="price_asc",
            page=300,
            page_size=12,
        ),
    ]
}

CONFLICT_SCENARIOS = {
    s.code: s
    for s in [
        ConflictScenario(
            code="S5_NORMAL",
            description="Kiểm tra trùng lịch cho xe thường",
            vehicle_id=3456,
            start_time=BUSY_START,
            end_time=BUSY_END,
        ),
        ConflictScenario(
            code="S5_HOT",
            description="Kiểm tra trùng lịch cho xe nóng",
            vehicle_id=17,
            start_time=BUSY_START,
            end_time=BUSY_END,
        ),
    ]
}


def build_filters(scenario: SearchScenario):
    """Dựng lại đúng bộ filter của search_public_vehicles (không đổi ngữ nghĩa)."""
    filters = [
        Vehicle.is_active.is_(True),
        Vehicle.price_per_day.is_not(None),
        func.upper(func.trim(Store.status)) == "APPROVED",
    ]

    if scenario.area:
        area_pattern = f"%{_escape_like(scenario.area.lower())}%"
        has_delivery_area = (
            select(DeliveryPoint.id)
            .where(
                DeliveryPoint.store_id == Store.id,
                DeliveryPoint.is_active.is_(True),
                func.lower(DeliveryPoint.area).like(area_pattern, escape="\\"),
            )
            .exists()
        )
        filters.append(
            or_(
                func.lower(Store.city).like(area_pattern, escape="\\"),
                has_delivery_area,
            )
        )

    if scenario.vehicle_type:
        filters.append(
            func.upper(func.trim(Vehicle.vehicle_type))
            == scenario.vehicle_type.strip().upper()
        )

    if scenario.min_price is not None:
        filters.append(Vehicle.price_per_day >= scenario.min_price)
    if scenario.max_price is not None:
        filters.append(Vehicle.price_per_day <= scenario.max_price)

    if scenario.start_time is not None and scenario.end_time is not None:
        filters.extend(
            _no_conflict_conditions(
                Vehicle.id, scenario.start_time, scenario.end_time, scenario.now
            )
        )
    return filters


def build_count_stmt(scenario: SearchScenario):
    """Câu COUNT y hệt hàm search_public_vehicles."""
    return (
        select(func.count(Vehicle.id))
        .select_from(Vehicle)
        .join(Store, Store.id == Vehicle.store_id)
        .where(*build_filters(scenario))
    )


def build_select_stmt(scenario: SearchScenario):
    """Câu SELECT y hệt hàm search_public_vehicles, kể cả sort/pagination."""
    if scenario.sort == "price_desc":
        order_by = (Vehicle.price_per_day.desc(), Vehicle.id.asc())
    elif scenario.sort == "newest":
        order_by = (Vehicle.created_at.desc(), Vehicle.id.desc())
    else:
        order_by = (Vehicle.price_per_day.asc(), Vehicle.id.asc())

    return (
        select(
            Vehicle.id.label("id"),
            Store.id.label("store_id"),
            Store.name.label("store_name"),
            Store.city.label("store_city"),
            Vehicle.vehicle_type,
            Vehicle.brand,
            Vehicle.model,
            Vehicle.seats,
            Vehicle.transmission_type,
            Vehicle.fuel_type,
            Vehicle.price_per_day,
            Vehicle.price_per_hour,
        )
        .join(Store, Store.id == Vehicle.store_id)
        .where(*build_filters(scenario))
        .order_by(*order_by)
        .offset((scenario.page - 1) * scenario.page_size)
        .limit(scenario.page_size)
    )


def build_conflict_stmt(scenario: ConflictScenario):
    """Câu kiểm tra trùng lịch y hệt vehicle_has_conflict."""
    no_conflict = _no_conflict_conditions(
        Vehicle.id, scenario.start_time, scenario.end_time, scenario.now
    )
    return select(Vehicle.id).where(Vehicle.id == scenario.vehicle_id, *no_conflict)


def compile_mysql(stmt) -> str:
    """Biên dịch SQL với literal binds theo dialect MySQL để lưu vào tài liệu."""
    sql = str(
        stmt.compile(
            dialect=mysql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    # MySQL dialect escape '%' thành '%%' cho paramstyle; khi chạy literal không có args
    # thì phải trả lại '%' để LIKE '%area%' giữ đúng ngữ nghĩa.
    return sql.replace("%%", "%")
