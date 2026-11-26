"""Router API Quản trị Cấu hình Chính sách Hệ thống (/api/admin/policies)."""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_admin
from app.db.session import get_db
from app.models.system_policy import SystemPolicy
from app.models.user import User

router = APIRouter(
    prefix="/admin/policies",
    tags=["Admin - Cấu hình Chính sách (Policies)"],
)

DEFAULT_POLICIES = [
    # 1. CHÍNH SÁCH GIỮ CHỖ (HOLD)
    {
        "policy_key": "booking_hold_minutes",
        "category": "HOLD",
        "label": "Thời gian giữ chỗ chờ thanh toán cọc",
        "value": str(settings.BOOKING_HOLD_MINUTES),
        "value_type": "number",
        "unit": "phút",
        "description": "Thời gian tạm giữ lịch xe khi khách tạo đơn chưa thanh toán cọc.",
    },
    {
        "policy_key": "booking_buffer_minutes",
        "category": "HOLD",
        "label": "Thời gian đệm giữa 2 chuyến xe",
        "value": str(settings.BOOKING_BUFFER_MINUTES),
        "value_type": "number",
        "unit": "phút",
        "description": "Khoảng thời gian nghỉ tối thiểu giữa lần trả xe trước và nhận xe sau.",
    },
    {
        "policy_key": "booking_max_duration_days",
        "category": "HOLD",
        "label": "Thời gian thuê tối đa mỗi đơn",
        "value": str(settings.BOOKING_MAX_DURATION_DAYS),
        "value_type": "number",
        "unit": "ngày",
        "description": "Giới hạn số ngày thuê tối đa cho một đơn đặt xe.",
    },
    # 2. CHÍNH SÁCH ĐẶT CỌC & HOÀN TIỀN (DEPOSIT / CANCELLATION)
    {
        "policy_key": "booking_deposit_rate_percent",
        "category": "DEPOSIT",
        "label": "Tỷ lệ tiền cọc đặt xe",
        "value": str(int(float(settings.BOOKING_DEPOSIT_RATE) * 100)),
        "value_type": "percent",
        "unit": "%",
        "description": "Phần trăm tiền cọc yêu cầu trên tổng giá trị đơn thuê (BR-03).",
    },
    {
        "policy_key": "booking_deposit_min_vnd",
        "category": "DEPOSIT",
        "label": "Tiền cọc tối thiểu",
        "value": str(int(settings.BOOKING_DEPOSIT_MIN)),
        "value_type": "number",
        "unit": "VNĐ",
        "description": "Mức tiền cọc tối thiểu cho mỗi đơn đặt xe.",
    },
    {
        "policy_key": "booking_deposit_max_vnd",
        "category": "DEPOSIT",
        "label": "Tiền cọc tối đa",
        "value": str(int(settings.BOOKING_DEPOSIT_MAX)),
        "value_type": "number",
        "unit": "VNĐ",
        "description": "Mức tiền cọc trần tối đa cho mỗi đơn đặt xe.",
    },
    {
        "policy_key": "cancel_free_hours",
        "category": "CANCELLATION",
        "label": "Thời hạn hủy miễn phí (hoàn 100%)",
        "value": str(settings.BOOKING_CANCEL_FREE_HOURS),
        "value_type": "number",
        "unit": "giờ",
        "description": "Số giờ tối thiểu trước giờ nhận xe để khách được hoàn 100% tiền cọc.",
    },
    {
        "policy_key": "cancel_partial_hours",
        "category": "CANCELLATION",
        "label": "Thời hạn hủy hoàn một phần",
        "value": str(settings.BOOKING_CANCEL_PARTIAL_HOURS),
        "value_type": "number",
        "unit": "giờ",
        "description": "Số giờ tối thiểu trước giờ nhận xe để khách được hoàn theo tỷ lệ một phần.",
    },
    {
        "policy_key": "cancel_partial_refund_percent",
        "category": "CANCELLATION",
        "label": "Tỷ lệ hoàn tiền khi hủy sát giờ",
        "value": str(int(float(settings.BOOKING_CANCEL_PARTIAL_RATE) * 100)),
        "value_type": "percent",
        "unit": "%",
        "description": "Phần trăm hoàn tiền trong khung thời gian hủy một phần.",
    },
    # 3. CHÍNH SÁCH PHÍ & PHỤ THU (FEES)
    {
        "policy_key": "late_return_fee_per_hour_vnd",
        "category": "FEES",
        "label": "Phí trả xe trễ mỗi giờ",
        "value": "50000",
        "value_type": "number",
        "unit": "VNĐ/giờ",
        "description": "Mức phụ thu áp dụng khi khách trả xe trễ hơn thời gian cam kết.",
    },
    {
        "policy_key": "over_mileage_fee_per_km_vnd",
        "category": "FEES",
        "label": "Phí vượt giới hạn quãng đường (250km/ngày)",
        "value": "3000",
        "value_type": "number",
        "unit": "VNĐ/km",
        "description": "Đơn giá phụ thu trên mỗi km vượt định mức ngày.",
    },
    {
        "policy_key": "cleaning_fee_vnd",
        "category": "FEES",
        "label": "Phí vệ sinh / khử mùi",
        "value": "50000",
        "value_type": "number",
        "unit": "VNĐ",
        "description": "Phí vệ sinh áp dụng khi xe trả lại có bùn đất hoặc mùi nặng.",
    },
    {
        "policy_key": "platform_service_fee_percent",
        "category": "FEES",
        "label": "Phí dịch vụ nền tảng",
        "value": "5",
        "value_type": "percent",
        "unit": "%",
        "description": "Tỷ lệ phí dịch vụ nền tảng tính trên giá trị đơn thuê.",
    },
    # 4. BẢO MẬT (SECURITY)
    {
        "policy_key": "login_rate_limit_max_attempts",
        "category": "SECURITY",
        "label": "Số lần thử đăng nhập tối đa",
        "value": str(getattr(settings, "LOGIN_RATE_LIMIT_MAX_ATTEMPTS", 5)),
        "value_type": "number",
        "unit": "lần",
        "description": "Số lần đăng nhập tối đa trong một cửa sổ thời gian trước khi bị chặn 429.",
    },
    {
        "policy_key": "login_rate_limit_window_seconds",
        "category": "SECURITY",
        "label": "Cửa sổ giới hạn đăng nhập",
        "value": str(getattr(settings, "LOGIN_RATE_LIMIT_WINDOW_SECONDS", 60)),
        "value_type": "number",
        "unit": "giây",
        "description": "Khoảng thời gian áp dụng bộ đếm giới hạn tần suất đăng nhập.",
    },
]


class PolicyUpdateItem(BaseModel):
    policy_key: str = Field(..., min_length=1, max_length=100)
    value: str = Field(..., min_length=1, max_length=255)


class PolicyBulkUpdateRequest(BaseModel):
    updates: List[PolicyUpdateItem]


def _ensure_default_policies(db: Session) -> List[SystemPolicy]:
    existing_keys = {p.policy_key for p in db.query(SystemPolicy).all()}
    created = False
    for item in DEFAULT_POLICIES:
        if item["policy_key"] not in existing_keys:
            db.add(SystemPolicy(**item))
            created = True
    if created:
        db.commit()
    return db.query(SystemPolicy).order_by(SystemPolicy.id.asc()).all()


def _serialize_policy(p: SystemPolicy) -> dict:
    return {
        "id": p.id,
        "policy_key": p.policy_key,
        "category": p.category,
        "label": p.label,
        "value": p.value,
        "value_type": p.value_type,
        "unit": p.unit,
        "description": p.description,
        "updated_by": p.updated_by,
        "updated_at": p.updated_at,
    }


@router.get("", summary="Lấy danh sách cấu hình chính sách hệ thống")
def list_policies(
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    policies = _ensure_default_policies(db)
    if category:
        cat_upper = category.strip().upper()
        policies = [p for p in policies if (p.category or "").upper() == cat_upper]
    return {
        "success": True,
        "data": [_serialize_policy(p) for p in policies],
    }


@router.put("", summary="Cập nhật cấu hình chính sách hệ thống")
def update_policies(
    payload: PolicyBulkUpdateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    _ensure_default_policies(db)
    if not payload.updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Danh sách cập nhật chính sách không được để trống.",
        )

    updated_items = []
    for item in payload.updates:
        policy = db.query(SystemPolicy).filter(SystemPolicy.policy_key == item.policy_key).first()
        if not policy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy chính sách '{item.policy_key}'.",
            )
        val_str = item.value.strip()
        if policy.value_type in ("number", "percent"):
            try:
                num = float(val_str)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Giá trị cho '{policy.label}' phải là số hợp lệ.",
                )
            if num < 0:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Giá trị cho '{policy.label}' không được âm.",
                )
            if policy.value_type == "percent" and num > 100:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Tỷ lệ phần trăm cho '{policy.label}' phải nằm trong khoảng 0 - 100%.",
                )

        policy.value = val_str
        policy.updated_by = admin.id
        policy.updated_at = datetime.now()
        updated_items.append(policy)

    db.commit()
    for p in updated_items:
        db.refresh(p)

    return {
        "success": True,
        "message": f"Đã cập nhật {len(updated_items)} cấu hình chính sách thành công.",
        "data": [_serialize_policy(p) for p in updated_items],
    }
