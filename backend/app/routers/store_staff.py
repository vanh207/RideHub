from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
import uuid

from app.db.session import get_db
from app.models.user import User
from app.models.store import StoreStaff

router = APIRouter(prefix="/store-staff", tags=["Store Staff"])

class StaffCreate(BaseModel):
    store_id: int
    full_name: str
    phone: str
    staff_role: str = "STAFF"  # 'STAFF' hoặc 'MANAGER'

# 1. Tạo nhân viên mới cho cửa hàng
@router.post("")
def add_staff(payload: StaffCreate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.phone == payload.phone).first()
    if not user:
        user = User(
            firebase_uid=f"staff_{uuid.uuid4().hex[:8]}",
            full_name=payload.full_name,
            phone=payload.phone,
            status="active"
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    staff = StoreStaff(
        store_id=payload.store_id,
        user_id=user.id,
        staff_role=payload.staff_role,
        status="ACTIVE"
    )
    db.add(staff)
    db.commit()
    db.refresh(staff)

    return {
        "message": "Tạo nhân viên thành công!",
        "staff_id": staff.id,
        "name": user.full_name,
        "phone": user.phone,
        "role": staff.staff_role
    }

# 2. Xem danh sách nhân viên của cửa hàng
@router.get("")
def list_staff(store_id: int, db: Session = Depends(get_db)):
    staffs = db.query(StoreStaff).filter(StoreStaff.store_id == store_id).all()
    
    return [
        {
            "id": staff.id,
            "store_id": staff.store_id,
            "user_id": staff.user_id,
            "staff_role": staff.staff_role,
            "status": staff.status
        }
        for staff in staffs
    ]