"""Truy vấn phương tiện cho API công khai tìm xe.

Các quy tắc lịch được dùng chung với luồng xem chi tiết/đặt xe:
- BR-02: thời lượng thuê tối thiểu 4 giờ, tối đa 30 ngày.
- BR-07: đệm 60 phút trước và sau mỗi lượt thuê.
- BR-17: khả dụng dựa trên lịch đơn/giữ chỗ/lịch chặn, không dựa vào
  ``vehicles.current_status``.
"""
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.booking import Booking
from app.models.delivery import DeliveryPoint
from app.models.store import Store
from app.models.vehicle import Vehicle, VehicleImage
from app.models.vehicle_reservation import VehicleReservation
from app.models.vehicle_schedule import VehicleSchedule

# Các trạng thái booking còn chiếm lịch xe.
# "PENDING" được giữ lại để tương thích dữ liệu cũ.
BLOCKING_BOOKING_STATUSES = (
    "PENDING_PAYMENT",
    "DEPOSIT_PAID",
    "PENDING_STORE_CONFIRM",
    "CONFIRMED",
    "IN_PROGRESS",
    "PENDING_SETTLEMENT",
    "PENDING",
)

# BR-07: đệm 60 phút trước và sau mỗi lượt thuê.
AVAILABILITY_BUFFER = timedelta(minutes=settings.BOOKING_BUFFER_MINUTES)

# BR-02: thời gian thuê tối thiểu 4 giờ và tối đa 30 ngày cho một đơn.
MIN_RENTAL_DURATION = timedelta(hours=settings.BOOKING_MIN_DURATION_HOURS)
MAX_RENTAL_DURATION = timedelta(days=settings.BOOKING_MAX_DURATION_DAYS)

# Giá trị vehicle_type đang dùng trong model, router quản lý và SQL mẫu.
ALLOWED_VEHICLE_TYPES = ("MOTORBIKE", "CAR")

# Sắp xếp hợp lệ cho API tìm xe.
ALLOWED_SORT_VALUES = ("price_asc", "price_desc", "newest")


def _escape_like(value: str) -> str:
    """Escape ký tự đại diện của LIKE để người dùng không lọc toàn bảng."""
    return (
        value.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def _no_conflict_conditions(
    vehicle_id_column,
    start_time: datetime,
    end_time: datetime,
    current_time: datetime,
):
    """Trả về các điều kiện SQL ``NOT EXISTS`` dùng chung cho tìm xe và đặt xe."""
    # existing.start_time < end_time + 60 phút
    latest_start = end_time + AVAILABILITY_BUFFER
    # existing.end_time + 60 phút > start_time
    earliest_end = start_time - AVAILABILITY_BUFFER

    booking_conflict = (
        select(Booking.id)
        .where(
            Booking.vehicle_id == vehicle_id_column,
            Booking.status.in_(BLOCKING_BOOKING_STATUSES),
            Booking.start_time < latest_start,
            Booking.end_time > earliest_end,
        )
        .exists()
    )
    reservation_conflict = (
        select(VehicleReservation.id)
        .where(
            VehicleReservation.vehicle_id == vehicle_id_column,
            VehicleReservation.status == "ACTIVE",
            VehicleReservation.expires_at > current_time,
            VehicleReservation.start_time < latest_start,
            VehicleReservation.end_time > earliest_end,
        )
        .exists()
    )
    schedule_conflict = (
        select(VehicleSchedule.id)
        .where(
            VehicleSchedule.vehicle_id == vehicle_id_column,
            VehicleSchedule.status == "ACTIVE",
            VehicleSchedule.start_time < latest_start,
            VehicleSchedule.end_time > earliest_end,
        )
        .exists()
    )
    return [
        ~booking_conflict,
        ~reservation_conflict,
        ~schedule_conflict,
    ]


def vehicle_has_conflict(
    db: Session,
    vehicle_id: int,
    start_time: datetime,
    end_time: datetime,
    *,
    now: Optional[datetime] = None,
) -> bool:
    """Kiểm tra một xe có bị chiếm lịch trong khoảng thời gian yêu cầu không."""
    current_time = now or datetime.now()
    no_conflict = _no_conflict_conditions(
        Vehicle.id, start_time, end_time, current_time
    )
    available_vehicle_id = db.scalar(
        select(Vehicle.id).where(Vehicle.id == vehicle_id, *no_conflict)
    )
    return available_vehicle_id is None


def search_public_vehicles(
    db: Session,
    *,
    area: Optional[str] = None,
    vehicle_type: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    sort: str = "price_asc",
    page: int = 1,
    page_size: int = 12,
    now: Optional[datetime] = None,
):
    """Tìm xe công khai theo khu vực, loại, giá và khoảng thời gian trống.

    Trả về ``(items, total)``. Mỗi item là dict đã đủ dữ liệu để router dựng
    ``VehicleSearchItem``; không chứa biển số hoặc trường nội bộ cửa hàng.

    Khi có ``start_time`` và ``end_time``, hàm dùng ba điều kiện ``NOT EXISTS``
    trên booking, giữ chỗ còn hạn và lịch chặn. Cách này giữ truy vấn danh sách
    trong một câu SQL, không kiểm tra từng xe (tránh N+1).
    """
    filters = [
        Vehicle.is_active.is_(True),
        Vehicle.price_per_day.is_not(None),
        func.upper(func.trim(Store.status)) == "APPROVED",
    ]

    if area:
        area_pattern = f"%{_escape_like(area.lower())}%"
        has_delivery_area = (
            select(DeliveryPoint.id)
            .where(
                DeliveryPoint.store_id == Store.id,
                DeliveryPoint.is_active.is_(True),
                func.lower(DeliveryPoint.area).like(
                    area_pattern, escape="\\"
                ),
            )
            .exists()
        )
        filters.append(
            or_(
                func.lower(Store.city).like(area_pattern, escape="\\"),
                has_delivery_area,
            )
        )

    if vehicle_type:
        filters.append(
            func.upper(func.trim(Vehicle.vehicle_type))
            == vehicle_type.strip().upper()
        )

    if min_price is not None:
        filters.append(Vehicle.price_per_day >= min_price)
    if max_price is not None:
        filters.append(Vehicle.price_per_day <= max_price)

    if start_time is not None and end_time is not None:
        current_time = now or datetime.now()
        filters.extend(
            _no_conflict_conditions(
                Vehicle.id, start_time, end_time, current_time
            )
        )

    total = db.scalar(
        select(func.count(Vehicle.id))
        .select_from(Vehicle)
        .join(Store, Store.id == Vehicle.store_id)
        .where(*filters)
    ) or 0

    if sort == "price_desc":
        order_by = (Vehicle.price_per_day.desc(), Vehicle.id.asc())
    elif sort == "newest":
        order_by = (Vehicle.created_at.desc(), Vehicle.id.desc())
    else:
        order_by = (Vehicle.price_per_day.asc(), Vehicle.id.asc())

    rows = db.execute(
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
        .where(*filters)
        .order_by(*order_by)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).mappings().all()

    vehicle_ids = [row["id"] for row in rows]
    primary_images = {}
    if vehicle_ids:
        image_rows = db.execute(
            select(VehicleImage.vehicle_id, VehicleImage.image_url)
            .where(VehicleImage.vehicle_id.in_(vehicle_ids))
            .order_by(
                VehicleImage.vehicle_id.asc(),
                VehicleImage.is_primary.desc(),
                VehicleImage.sort_order.is_(None).asc(),
                VehicleImage.sort_order.asc(),
                VehicleImage.id.asc(),
            )
        ).all()
        for vehicle_id, image_url in image_rows:
            primary_images.setdefault(vehicle_id, image_url)

    is_available = True if start_time is not None else None
    items = []
    for row in rows:
        items.append(
            {
                "id": row["id"],
                "store": {
                    "id": row["store_id"],
                    "name": row["store_name"],
                    "city": row["store_city"],
                },
                "vehicle_type": row["vehicle_type"],
                "brand": row["brand"],
                "model": row["model"],
                "seats": row["seats"],
                "transmission_type": row["transmission_type"],
                "fuel_type": row["fuel_type"],
                "price_per_day": (
                    float(row["price_per_day"])
                    if row["price_per_day"] is not None
                    else None
                ),
                "price_per_hour": (
                    float(row["price_per_hour"])
                    if row["price_per_hour"] is not None
                    else None
                ),
                "primary_image_url": primary_images.get(row["id"]),
                "is_available": is_available,
            }
        )

    return items, total
