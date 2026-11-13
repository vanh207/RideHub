"""Router quản lý Biên bản Giao/Nhận xe điện tử & Chữ ký số (Module Handover Protocol)
Dành cho ticket: [BE] Thiết kế API biên bản giao nhận và chữ ký
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.handover import HandoverProtocol
from app.schemas.handover import (
    HandoverProtocolCreate,
    HandoverProtocolResponse,
    HandoverReturnUpdate,
)

router = APIRouter(prefix="/handover", tags=["Handover Protocol & Signatures"])


@router.post("", response_model=HandoverProtocolResponse, status_code=status.HTTP_201_CREATED)
def create_handover_protocol(
    payload: HandoverProtocolCreate,
    db: Session = Depends(get_db),
):
    """Tạo biên bản giao xe (Check-out) mới kèm chữ ký số điện tử của hai bên."""
    # Kiểm tra xem mã biên bản đã tồn tại chưa
    existing = db.query(HandoverProtocol).filter(HandoverProtocol.protocol_code == payload.protocol_code).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Mã biên bản {payload.protocol_code} đã tồn tại trên hệ thống."
        )

    protocol = HandoverProtocol(**payload.model_dump())
    db.add(protocol)
    db.commit()
    db.refresh(protocol)
    return protocol


@router.get("", response_model=List[HandoverProtocolResponse])
def list_handover_protocols(
    booking_id: Optional[int] = Query(None, description="Lọc theo mã đặt chỗ"),
    protocol_type: Optional[str] = Query(None, description="CHECK_OUT hoặc CHECK_IN"),
    db: Session = Depends(get_db),
):
    """Lấy danh sách các biên bản giao nhận xe."""
    query = db.query(HandoverProtocol)
    if booking_id is not None:
        query = query.filter(HandoverProtocol.booking_id == booking_id)
    if protocol_type is not None:
        query = query.filter(HandoverProtocol.protocol_type == protocol_type)
    return query.order_by(HandoverProtocol.id.desc()).all()


@router.get("/{protocol_id}", response_model=HandoverProtocolResponse)
def get_handover_protocol(
    protocol_id: int,
    db: Session = Depends(get_db),
):
    """Xem chi tiết một biên bản giao nhận xe kèm chữ ký số và sơ đồ tổn hại."""
    protocol = db.query(HandoverProtocol).filter(HandoverProtocol.id == protocol_id).first()
    if not protocol:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy biên bản giao nhận xe."
        )
    return protocol


@router.put("/{protocol_id}/return", response_model=HandoverProtocolResponse)
def return_vehicle_settlement(
    protocol_id: int,
    payload: HandoverReturnUpdate,
    db: Session = Depends(get_db),
):
    """Cập nhật biên bản hoàn trả xe (Check-in), tính toán chênh lệch ODO, nhiên liệu, phụ phí và tất toán cọc."""
    protocol = db.query(HandoverProtocol).filter(HandoverProtocol.id == protocol_id).first()
    if not protocol:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy biên bản để hoàn tất trả xe."
        )

    protocol.protocol_type = "CHECK_IN"
    protocol.odo_checkin = payload.odo_checkin
    protocol.fuel_checkin = payload.fuel_checkin
    if payload.damage_points is not None:
        protocol.damage_points = payload.damage_points

    protocol.fee_overtime = payload.fee_overtime
    protocol.fee_excess_km = payload.fee_excess_km
    protocol.fee_fuel = payload.fee_fuel
    protocol.fee_cleaning = payload.fee_cleaning
    protocol.fee_damage = payload.fee_damage
    protocol.hold_fine_deposit = payload.hold_fine_deposit
    protocol.refund_immediate = payload.refund_immediate

    if payload.customer_signature:
        protocol.customer_signature = payload.customer_signature
    if payload.staff_signature:
        protocol.staff_signature = payload.staff_signature
    if payload.notes:
        protocol.notes = payload.notes

    protocol.status = "COMPLETED"
    db.commit()
    db.refresh(protocol)
    return protocol

