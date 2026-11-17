"""Router quản lý Phương tiện (Xe máy & Ô tô) thuộc cửa hàng
Hỗ trợ: Thêm mới, xem danh sách, xem chi tiết, cập nhật thông tin xe.
Validate: Định dạng biển số xe VN, trùng biển số, giá sàn theo loại xe.
"""
import re
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.vehicle import Vehicle, VehicleStatusHistory
from app.schemas.vehicle import VehicleCreate, VehicleResponse, VehicleUpdate, VehicleStatusChangeRequest, VehicleStatusHistoryResponse
from app.services.vehicle_state_machine import validate_and_transition_status, TRANSITION_RULES

router = APIRouter(prefix="/vehicles", tags=["Vehicles Management"])

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

# chuyển đổi trạng thái xe kèm ghi Audit Log
@router.post("/{vehicle_id}/status", response_model=VehicleResponse)
def change_vehicle_status(
    vehicle_id: int,
    payload: VehicleStatusChangeRequest,
    db: Session = Depends(get_db)
):
    """Đổi trạng thái xe qua máy trạng thái (State Machine) và lưu Audit Log."""
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy phương tiện với ID={vehicle_id}!"
        )

    validate_and_transition_status(
        vehicle=vehicle,
        new_status=payload.new_status,
        changed_by=payload.changed_by,
        reason=payload.reason,
        note=payload.note,
        db=db
    )

    db.commit()
    db.refresh(vehicle)
    return vehicle


# xem lịch sử đổi trạng thái và audit log của một chiếc xe
@router.get("/{vehicle_id}/history", response_model=List[VehicleStatusHistoryResponse])
def get_vehicle_status_history(vehicle_id: int, db: Session = Depends(get_db)):
    """Lấy toàn bộ lịch sử thay đổi trạng thái (Audit Log) của một phương tiện."""
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy phương tiện với ID={vehicle_id}!"
        )

    logs = (
        db.query(VehicleStatusHistory)
        .filter(VehicleStatusHistory.vehicle_id == vehicle_id)
        .order_by(VehicleStatusHistory.created_at.desc(), VehicleStatusHistory.id.desc())
        .all()
    )
    return logs


# lấy danh sách quy tắc chuyển trạng thái (để Frontend hiển thị nút)
@router.get("/state-machine/transitions")
def get_state_machine_rules():
    """Trả về ma trận trạng thái hợp lệ của hệ thống."""
    return {
        "status_rules": TRANSITION_RULES,
        "description": "Danh sách các trạng thái và các bước chuyển tiếp hợp lệ"
    }