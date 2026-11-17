from typing import List, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.vehicle import Vehicle, VehicleStatusHistory


# 1. Danh sách các trạng thái xe được phép
class VehicleState:
    AVAILABLE = "AVAILABLE"          # Sẵn sàng
    RESERVED = "RESERVED"            # Đã giữ chỗ
    RENTED = "RENTED"                # Đang thuê
    CLEANING = "CLEANING"            # Đang vệ sinh
    MAINTENANCE = "MAINTENANCE"      # Bảo trì / bảo dưỡng
    OUT_OF_SERVICE = "OUT_OF_SERVICE"# Tạm ngừng hoạt động


# 2. Ma trận chuyển đổi trạng thái hợp lệ (Valid Transitions)
TRANSITION_RULES = {
    VehicleState.AVAILABLE: [
        VehicleState.RESERVED,
        VehicleState.RENTED,
        VehicleState.MAINTENANCE,
        VehicleState.OUT_OF_SERVICE,
    ],
    VehicleState.RESERVED: [
        VehicleState.RENTED,
        VehicleState.AVAILABLE,
        VehicleState.MAINTENANCE,
    ],
    VehicleState.RENTED: [
        VehicleState.CLEANING,
        VehicleState.AVAILABLE,
        VehicleState.MAINTENANCE,
    ],
    VehicleState.CLEANING: [
        VehicleState.AVAILABLE,
        VehicleState.MAINTENANCE,
    ],
    VehicleState.MAINTENANCE: [
        VehicleState.AVAILABLE,
        VehicleState.CLEANING,
        VehicleState.OUT_OF_SERVICE,
    ],
    VehicleState.OUT_OF_SERVICE: [
        VehicleState.MAINTENANCE,
        VehicleState.AVAILABLE,
    ],
}


def validate_and_transition_status(
    vehicle: Vehicle,
    new_status: str,
    changed_by: str,
    reason: str = None,
    note: str = None,
    db: Session = None
) -> Tuple[Vehicle, VehicleStatusHistory]:
    """Kiểm tra máy trạng thái và ghi log nếu hợp lệ."""
    
    current = (vehicle.current_status or VehicleState.AVAILABLE).upper()
    target = new_status.strip().upper()

    # Kiểm tra trạng thái đích có tồn tại trong hệ thống không
    all_states = [getattr(VehicleState, attr) for attr in dir(VehicleState) if not attr.startswith("__")]
    if target not in all_states:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Trạng thái '{new_status}' không tồn tại trong hệ thống! Danh sách hợp lệ: {all_states}"
        )

    # Nếu trùng trạng thái hiện tại
    if current == target:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Phương tiện hiện đã ở trạng thái '{current}' rồi, không cần đổi lại!"
        )

    # Kiểm tra ma trận chuyển đổi hợp lệ
    allowed_next_states = TRANSITION_RULES.get(current, [])
    if target not in allowed_next_states:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Vi phạm quy tắc máy trạng thái: Không thể chuyển từ '{current}' sang '{target}'! "
                f"Các trạng thái hợp lệ có thể chuyển tiếp từ '{current}' là: {allowed_next_states}"
            )
        )

    # Ghi nhận trạng thái mới vào xe
    vehicle.current_status = target

    # Tạo bản ghi Audit Log
    history_log = VehicleStatusHistory(
        vehicle_id=vehicle.id,
        from_status=current,
        to_status=target,
        changed_by=changed_by.strip(),
        reason=reason.strip() if reason else None,
        note=note.strip() if note else None,
    )
    db.add(history_log)

    return vehicle, history_log