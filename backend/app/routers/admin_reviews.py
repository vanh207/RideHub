from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_admin
from app.db.session import get_db
from app.models.driver_license import DriverLicense
from app.models.identity_document import IdentityDocument
from app.models.store import Store
from app.models.user import User

router = APIRouter(prefix="/admin/reviews", tags=["Admin Reviews"])


class ReviewDecision(BaseModel):
    status: Literal["approved", "rejected"]
    reason: str | None = Field(default=None, max_length=1000)


def _is_pending(status: str | None) -> bool:
    return (status or "").lower() == "pending"


def _store_data(store: Store) -> dict:
    owner = store.owner
    return {
        "id": store.id,
        "name": store.name,
        "description": store.description,
        "phone": store.phone,
        "email": store.email,
        "address": store.address,
        "city": store.city,
        "district": store.district,
        "ward": store.ward,
        "address_detail": store.address_detail,
        "business_license": store.business_license,
        "business_license_url": f"/api/stores/{store.id}/business-license",
        "status": store.status,
        "reject_reason": store.reject_reason,
        "created_at": store.created_at,
        "owner": {
            "id": owner.id,
            "full_name": owner.full_name,
            "email": owner.email,
            "phone": owner.phone,
        } if owner else None,
    }


def _customer_data(document: IdentityDocument | DriverLicense, resource_type: str) -> dict:
    user = document.user
    data = {
        "id": document.id,
        "resource_type": resource_type,
        "user_id": document.user_id,
        "full_name": user.full_name if user else None,
        "email": user.email if user else None,
        "phone": user.phone if user else None,
        "status": document.status,
        "reject_reason": document.reject_reason,
        "created_at": document.created_at,
    }
    if isinstance(document, IdentityDocument):
        data.update({
            "document_type": document.document_type,
            "document_number": document.document_number,
            "front_image_url": document.front_image_url,
            "back_image_url": document.back_image_url,
            "issued_date": document.issued_date,
            "expiry_date": document.expiry_date,
        })
    else:
        data.update({
            "license_class": document.license_class,
            "license_number": document.license_number,
            "image_url": document.image_url,
            "issued_date": document.issued_date,
            "expiry_date": document.expiry_date,
        })
    return data


@router.get("/queue")
def get_review_queue(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    stores = db.query(Store).filter(func.lower(Store.status) == "pending").order_by(
        Store.created_at.asc(), Store.id.asc()
    ).all()
    identity_documents = db.query(IdentityDocument).filter(
        func.lower(IdentityDocument.status) == "pending"
    ).order_by(IdentityDocument.created_at.asc(), IdentityDocument.id.asc()).all()
    driver_licenses = db.query(DriverLicense).filter(
        func.lower(DriverLicense.status) == "pending"
    ).order_by(DriverLicense.created_at.asc(), DriverLicense.id.asc()).all()

    return {
        "success": True,
        "data": {
            "stores": [_store_data(item) for item in stores if _is_pending(item.status)],
            "customers": [
                _customer_data(item, "identity_document")
                for item in identity_documents
                if _is_pending(item.status) and item.user and item.user.role == "customer"
            ] + [
                _customer_data(item, "driver_license")
                for item in driver_licenses
                if _is_pending(item.status) and item.user and item.user.role == "customer"
            ],
        },
    }


@router.patch("/{resource_type}/{item_id}")
def decide_review(
    resource_type: Literal["stores", "identity-documents", "driver-licenses"],
    item_id: int,
    decision: ReviewDecision,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    reason = decision.reason.strip() if decision.reason else None
    if decision.status == "rejected" and not reason:
        raise HTTPException(status_code=422, detail="Vui lòng nhập lý do từ chối.")

    model = {
        "stores": Store,
        "identity-documents": IdentityDocument,
        "driver-licenses": DriverLicense,
    }[resource_type]
    record = db.query(model).filter(model.id == item_id).with_for_update().first()
    if record is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ.")
    if resource_type != "stores" and (not record.user or record.user.role != "customer"):
        raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ khách hàng.")
    if not _is_pending(record.status):
        raise HTTPException(status_code=409, detail="Hồ sơ này đã được xử lý.")

    is_store = resource_type == "stores"
    record.status = decision.status.upper() if is_store else decision.status
    record.reject_reason = reason if decision.status == "rejected" else None
    if is_store:
        record.approved_by = admin.id
        record.approved_at = datetime.now()
    else:
        record.verified_by = admin.id
        record.verified_at = datetime.now()

    db.commit()
    db.refresh(record)
    return {
        "success": True,
        "message": "Đã cập nhật kết quả duyệt hồ sơ.",
        "data": {
            "id": record.id,
            "status": record.status,
            "reject_reason": record.reject_reason,
        },
    }
