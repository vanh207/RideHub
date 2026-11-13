"""Truy vấn và kiểm tra khả dụng phương tiện cho trang công khai."""
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

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
AVAILABILITY_BUFFER = timedelta(minutes=60)


def get_public_vehicle_detail(db: Session, vehicle_id: int):
    """Lấy dữ liệu công khai của xe.

    Trả về tuple ``(vehicle, store, images, delivery_points)`` hoặc ``None``
    nếu xe không tồn tại, đã bị tắt, hoặc cửa hàng chưa được duyệt.
    """
    vehicle = db.get(Vehicle, vehicle_id)
    if vehicle is None or not vehicle.is_active:
        return None

    # Chỉ chọn các cột cần trả ra, không nạp các trường nội bộ/nhạy cảm.
    store = db.execute(
        select(
            Store.id,
            Store.name,
            Store.address,
            Store.city,
            Store.status,
        ).where(Store.id == vehicle.store_id)
    ).first()
    if store is None or (store.status or "").strip().upper() != "APPROVED":
        return None

    # Ảnh: ảnh chính trước, sort_order tăng dần (NULL xuống cuối), rồi id.
    images = db.execute(
        select(
            VehicleImage.id,
            VehicleImage.image_url,
            VehicleImage.is_primary,
            VehicleImage.sort_order,
        )
        .where(VehicleImage.vehicle_id == vehicle.id)
        .order_by(
            VehicleImage.is_primary.desc(),
            VehicleImage.sort_order.is_(None).asc(),
            VehicleImage.sort_order.asc(),
            VehicleImage.id.asc(),
        )
    ).all()

    # Điểm giao nhận: chỉ chọn cột cần dùng vì model có cột không tồn tại
    # trong bảng thật (delivery_fee_zone_id).
    delivery_points = db.execute(
        select(
            DeliveryPoint.id,
            DeliveryPoint.name,
            DeliveryPoint.address,
            DeliveryPoint.area,
            DeliveryPoint.delivery_fee,
        )
        .where(
            DeliveryPoint.store_id == store.id,
            DeliveryPoint.is_active.is_(True),
        )
        .order_by(DeliveryPoint.id.asc())
    ).all()

    return vehicle, store, images, delivery_points


def check_vehicle_availability(
    db: Session,
    vehicle_id: int,
    start_time: datetime,
    end_time: datetime,
):
    """Kiểm tra xe có trống trong khoảng thời gian yêu cầu hay không.

    Có tính đệm 60 phút ở cả hai đầu theo BR-07. Trả về
    ``(is_available, unavailable_reason)``. Hàm chỉ đọc dữ liệu.
    """
    # existing.start < new_end + 60 phút
    latest_start = end_time + AVAILABILITY_BUFFER
    # existing.end + 60 phút > new_start
    earliest_end = start_time - AVAILABILITY_BUFFER

    booking_id = db.scalar(
        select(Booking.id)
        .where(
            Booking.vehicle_id == vehicle_id,
            Booking.status.in_(BLOCKING_BOOKING_STATUSES),
            Booking.start_time < latest_start,
            Booking.end_time > earliest_end,
        )
        .limit(1)
    )
    if booking_id is not None:
        return False, "BOOKED"

    # Giữ chỗ chỉ còn hiệu lực khi chưa hết hạn.
    now = datetime.now()
    reservation_id = db.scalar(
        select(VehicleReservation.id)
        .where(
            VehicleReservation.vehicle_id == vehicle_id,
            VehicleReservation.status == "ACTIVE",
            VehicleReservation.expires_at > now,
            VehicleReservation.start_time < latest_start,
            VehicleReservation.end_time > earliest_end,
        )
        .limit(1)
    )
    if reservation_id is not None:
        return False, "HELD"

    # Lịch bảo dưỡng hoặc khóa xe.
    schedule_id = db.scalar(
        select(VehicleSchedule.id)
        .where(
            VehicleSchedule.vehicle_id == vehicle_id,
            VehicleSchedule.status == "ACTIVE",
            VehicleSchedule.start_time < latest_start,
            VehicleSchedule.end_time > earliest_end,
        )
        .limit(1)
    )
    if schedule_id is not None:
        return False, "MAINTENANCE_OR_BLOCKED"

    return True, None
