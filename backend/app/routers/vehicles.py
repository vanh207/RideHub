"""Router quản lý Phương tiện (Xe máy & Ô tô) thuộc cửa hàng
Hỗ trợ: Thêm mới, xem danh sách, xem chi tiết, cập nhật thông tin xe.
Validate: Định dạng biển số xe VN, trùng biển số, giá sàn theo loại xe.
"""
import re
from datetime import datetime
from typing import List, Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.crud import vehicle as vehicle_crud
from app.crud.vehicle import (
    ALLOWED_VEHICLE_TYPES,
    MAX_RENTAL_DURATION,
    MIN_RENTAL_DURATION,
)
from app.db.session import get_db
from app.models.vehicle import Vehicle
from app.schemas.vehicle import (
    VehicleCreate,
    VehicleResponse,
    VehicleSearchResponse,
    VehicleUpdate,
)

router = APIRouter(prefix="/vehicles", tags=["Vehicles Management"])


def _to_local_naive(value: datetime) -> datetime:
    """Chuyển datetime có timezone về giờ địa phương dạng naive.

    MySQL TIMESTAMP đang lưu giờ Việt Nam, nên bỏ timezone trước khi so sánh.
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

@router.get(
    "/search",
    response_model=VehicleSearchResponse,
    summary="Tìm xe công khai theo khu vực, loại, giá và thời gian trống",
    tags=["Vehicles (Public)"],
)
def search_public_vehicles(
    area: Optional[str] = Query(
        None,
        description=(
            "Khu vực cần tìm. Khớp không phân biệt hoa thường với "
            "stores.city hoặc delivery_points.area đang hoạt động. "
            "Ví dụ: Hà Nội, Quận Cầu Giấy."
        ),
    ),
    vehicle_type: Optional[str] = Query(
        None,
        description="Loại xe: MOTORBIKE hoặc CAR. Giá trị khác trả 422.",
    ),
    min_price: Optional[float] = Query(
        None,
        ge=0,
        description="Giá thuê ngày tối thiểu (VNĐ/ngày). Ví dụ: 100000.",
    ),
    max_price: Optional[float] = Query(
        None,
        ge=0,
        description="Giá thuê ngày tối đa (VNĐ/ngày). Ví dụ: 800000.",
    ),
    start_time: Optional[datetime] = Query(
        None,
        description=(
            "Thời gian bắt đầu thuê dạng ISO 8601. "
            "Ví dụ: 2026-12-20T09:00:00."
        ),
    ),
    end_time: Optional[datetime] = Query(
        None,
        description=(
            "Thời gian kết thúc thuê dạng ISO 8601. "
            "Ví dụ: 2026-12-20T13:00:00."
        ),
    ),
    sort: Literal["price_asc", "price_desc", "newest"] = Query(
        "price_asc",
        description="Sắp xếp: price_asc (mặc định), price_desc, newest.",
    ),
    page: int = Query(1, ge=1, description="Trang hiện tại, bắt đầu từ 1."),
    page_size: int = Query(
        12, ge=1, le=50, description="Số xe mỗi trang, từ 1 đến 50."
    ),
    db: Session = Depends(get_db),
):
    """Tìm xe công khai theo khu vực, loại, giá và khoảng thời gian trống.

    API không yêu cầu đăng nhập và chỉ đọc dữ liệu.

    Ví dụ tham số:
    - Không lọc thời gian: ``/api/vehicles/search?area=Hà Nội``
    - Lọc theo giá: ``/api/vehicles/search?min_price=100000&max_price=800000``
    - Lọc theo thời gian: ``/api/vehicles/search?start_time=2026-12-20T09:00:00&end_time=2026-12-20T13:00:00``

    Khi có thời gian, hệ thống áp dụng BR-02 (tối thiểu 4 giờ, tối đa 30 ngày)
    và BR-07 (đệm 60 phút ở cả hai đầu). Kết quả chỉ gồm xe còn trống theo
    booking, giữ chỗ còn hiệu lực và lịch chặn đang hoạt động.
    """
    if (
        min_price is not None
        and max_price is not None
        and min_price > max_price
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="min_price không được lớn hơn max_price.",
        )

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

        duration = end_time - start_time
        if duration < MIN_RENTAL_DURATION:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Thời gian thuê tối thiểu là 4 giờ theo BR-02.",
            )
        if duration > MAX_RENTAL_DURATION:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Thời gian thuê tối đa là 30 ngày theo BR-02.",
            )

    normalized_vehicle_type = None
    if vehicle_type is not None:
        normalized_vehicle_type = vehicle_type.strip().upper()
        if normalized_vehicle_type not in ALLOWED_VEHICLE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="vehicle_type chỉ hỗ trợ MOTORBIKE hoặc CAR.",
            )

    normalized_area = area.strip() if area is not None else None
    if normalized_area == "":
        normalized_area = None

    items, total = vehicle_crud.search_public_vehicles(
        db,
        area=normalized_area,
        vehicle_type=normalized_vehicle_type,
        min_price=min_price,
        max_price=max_price,
        start_time=start_time,
        end_time=end_time,
        sort=sort,
        page=page,
        page_size=page_size,
    )

    return VehicleSearchResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
    )


# xem chi tiết xe
@router.get("/{vehicle_id}", response_model=VehicleResponse)
def get_vehicle(vehicle_id: int, db: Session = Depends(get_db)):
    """Xem chi tiết thông số một chiếc xe theo ID."""
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy phương tiện với ID={vehicle_id}!"
        )
    return vehicle

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