from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.db.session import get_db
from app.models.delivery import DeliveryFeeZone, DeliveryPoint
from app.schemas.delivery import (
    DeliveryFeeZoneCreate, DeliveryFeeZoneResponse,
    DeliveryPointCreate, DeliveryPointResponse
)

router = APIRouter(prefix="/delivery", tags=["Vehicle Delivery"])

# 1. Thêm phí theo khu vực 
@router.post("/zones", response_model=DeliveryFeeZoneResponse)
def create_zone(payload: DeliveryFeeZoneCreate, db: Session = Depends(get_db)):
   
    if payload.delivery_fee < 0:
        raise HTTPException(status_code=400, detail="Phí giao nhận không được âm!")
    zone = DeliveryFeeZone(**payload.model_dump())
    db.add(zone)

# 2. Xem danh sách phí các khu vực
@router.get("/zones", response_model=List[DeliveryFeeZoneResponse])
def get_zones(store_id: int, db: Session = Depends(get_db)):
    return db.query(DeliveryFeeZone).filter(DeliveryFeeZone.store_id == store_id).all()

# 3. Thêm điểm giao nhận (ví dụ: Sân bay Ga T1, Bến xe)
@router.post("/points", response_model=DeliveryPointResponse)
def create_point(payload: DeliveryPointCreate, db: Session = Depends(get_db)):

    if payload.delivery_fee < 0:
        raise HTTPException(status_code=400, detail="Phí giao nhận không được âm!")
    point = DeliveryPoint(**payload.model_dump())
    db.add(point)

# 4. Xem danh sách điểm giao nhận của cửa hàng
@router.get("/points", response_model=List[DeliveryPointResponse])
def get_points(store_id: int, db: Session = Depends(get_db)):
    return db.query(DeliveryPoint).filter(DeliveryPoint.store_id == store_id).all()