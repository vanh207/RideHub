"""Router Phương tiện (Xe máy & Ô tô).

- Nhóm quản lý cửa hàng: thêm mới, xem danh sách, xem chi tiết đầy đủ,
  cập nhật thông tin xe. Validate biển số VN, trùng biển số, giá sàn.
- Nhóm công khai: khách chưa đăng nhập xem chi tiết xe, giá thuê, ảnh,
  điểm giao nhận và kiểm tra xe có trống theo khoảng thời gian.
"""
import re
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.crud import vehicle as vehicle_crud
from app.db.session import get_db
from app.models.vehicle import Vehicle
from app.schemas.vehicle import (
    DeliveryPointSummary,
    PublicVehicleDetailResponse,
    StoreSummary,
    VehicleCreate,
    VehicleImageResponse,
    VehicleResponse,
    VehicleUpdate,
)

router = APIRouter(prefix="/vehicles", tags=["Vehicles Management"])
public_router = APIRouter(prefix="/vehicles", tags=["Vehicles (Public)"])


def _to_local_naive(value: datetime) -> datetime:
    """Chuyển datetime có timezone về giờ địa phương dạng naive.

    MySQL TIMESTAMP đang lưu giờ địa phương (Asia/Ho_Chi_Minh), nên cần bỏ
    timezone trước khi so sánh.
    """
    if value.tzinfo is not None:
        return value.astimezone().replace(tzinfo=None)
    return value

# thêm 
@router.post("", response_model=VehicleResponse, status_code=status.HTTP_201_CREATED)
def create_vehicle(payload: VehicleCreate, db: Session = Depends(get_db)):
    """Thêm phương tiện mới vào cửa hàng, validate biển số và giá thuê."""
    
    plate = re.sub(r"\s+", " ", payload.plate_number.strip().upper())
    payload.plate_number = plate

    pattern = r"^[0-9]{2}[A-Z0-9]{1,2}[- ]?[0-9]{4,5}(\.[0-9]{2})?$"
    if not re.match(pattern, plate):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Biển số xe không đúng định dạng chuẩn Việt Nam (VD: 30A-123.45 hoặc 29B1-123.45)!"
        )

    existing = db.query(Vehicle).filter(Vehicle.plate_number == plate).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Biển số xe '{plate}' đã được đăng ký trên hệ thống!"
        )

    v_type = payload.vehicle_type.upper()
    if v_type not in ["MOTORBIKE", "CAR"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Loại phương tiện (vehicle_type) chỉ được là 'MOTORBIKE' hoặc 'CAR'!"
        )

    if payload.price_per_day <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Giá thuê ngày phải lớn hơn 0!"
        )

    if v_type == "CAR" and payload.price_per_day < 300000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Giá thuê ô tô theo ngày tối thiểu từ 300.000 VNĐ!"
        )
    if v_type == "MOTORBIKE" and payload.price_per_day < 50000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Giá thuê xe máy theo ngày tối thiểu từ 50.000 VNĐ!"
        )

    vehicle = Vehicle(**payload.model_dump())
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle

# xem danh sách xe
@router.get("", response_model=List[VehicleResponse])
def list_vehicles(
    store_id: Optional[int] = Query(None, description="Lọc theo mã cửa hàng"),
    vehicle_type: Optional[str] = Query(None, description="Lọc loại: MOTORBIKE hoặc CAR"),
    status: Optional[str] = Query(None, description="Lọc trạng thái: AVAILABLE, RENTED, MAINTENANCE"),
    db: Session = Depends(get_db)
):
    """Lấy danh sách xe, hỗ trợ lọc theo cửa hàng, loại xe và trạng thái hoạt động."""
    query = db.query(Vehicle)
    if store_id is not None:
        query = query.filter(Vehicle.store_id == store_id)
    if vehicle_type is not None:
        query = query.filter(Vehicle.vehicle_type == vehicle_type.upper())
    if status is not None:
        query = query.filter(Vehicle.current_status == status.upper())
    
    return query.order_by(Vehicle.id.desc()).all()

# xem chi tiết xe (dành cho quản lý cửa hàng)
@router.get("/{vehicle_id}/management", response_model=VehicleResponse)
def get_vehicle_management(vehicle_id: int, db: Session = Depends(get_db)):
    """Xem chi tiết đầy đủ của xe, bao gồm biển số (dành cho quản lý)."""
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy phương tiện với ID={vehicle_id}!"
        )
    return vehicle


@public_router.get(
    "/{vehicle_id}",
    response_model=PublicVehicleDetailResponse,
    summary="Xem chi tiết phương tiện công khai",
)
def get_public_vehicle_detail(
    vehicle_id: int,
    start_time: Optional[datetime] = Query(
        None,
        description="Thời gian bắt đầu thuê (ISO 8601, VD: 2026-12-01T09:00:00)",
    ),
    end_time: Optional[datetime] = Query(
        None,
        description="Thời gian kết thúc thuê (ISO 8601, VD: 2026-12-03T09:00:00)",
    ),
    db: Session = Depends(get_db),
):
    """Xem chi tiết phương tiện công khai, không yêu cầu đăng nhập.

    Nếu truyền đủ ``start_time`` và ``end_time``, API kiểm tra xe có trống
    trong khoảng thời gian đó hay không (có đệm 60 phút theo BR-07).
    Endpoint chỉ đọc, không tạo giữ chỗ và không ghi dữ liệu.
    """
    if (start_time is None) != (end_time is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Phải truyền đủ cả start_time và end_time.",
        )

    if start_time is not None and end_time is not None:
        start_time = _to_local_naive(start_time)
        end_time = _to_local_naive(end_time)
        if end_time <= start_time:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="end_time phải lớn hơn start_time.",
            )

    data = vehicle_crud.get_public_vehicle_detail(db, vehicle_id)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy phương tiện hoặc phương tiện không còn công khai.",
        )

    vehicle, store, images, delivery_points = data

    is_available = None
    unavailable_reason = None
    if start_time is not None and end_time is not None:
        is_available, unavailable_reason = vehicle_crud.check_vehicle_availability(
            db, vehicle.id, start_time, end_time
        )

    return PublicVehicleDetailResponse(
        id=vehicle.id,
        store_id=vehicle.store_id,
        store=StoreSummary.model_validate(store),
        vehicle_type=vehicle.vehicle_type,
        brand=vehicle.brand,
        model=vehicle.model,
        year_of_manufacture=vehicle.year_of_manufacture,
        engine_capacity=vehicle.engine_capacity,
        transmission_type=vehicle.transmission_type,
        seats=vehicle.seats,
        body_type=vehicle.body_type,
        fuel_type=vehicle.fuel_type,
        price_per_day=vehicle.price_per_day,
        price_per_hour=vehicle.price_per_hour,
        current_status=vehicle.current_status or "UNKNOWN",
        is_available=is_available,
        unavailable_reason=unavailable_reason,
        description=vehicle.description,
        images=[VehicleImageResponse.model_validate(image) for image in images],
        delivery_points=[
            DeliveryPointSummary(
                id=point.id,
                name=point.name,
                address=point.address,
                area=point.area,
                delivery_fee=point.delivery_fee or 0,
            )
            for point in delivery_points
        ],
    )


# cập nhật thông tin xe
@router.put("/{vehicle_id}", response_model=VehicleResponse)
def update_vehicle(vehicle_id: int, payload: VehicleUpdate, db: Session = Depends(get_db)):
    """Sửa thông tin xe (giá thuê, trạng thái, mô tả...)."""
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy phương tiện với ID={vehicle_id}!"
        )

    if payload.price_per_day is not None and payload.price_per_day <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Giá thuê ngày phải lớn hơn 0!"
        )

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(vehicle, field, value)

    db.commit()
    db.refresh(vehicle)
    return vehicle