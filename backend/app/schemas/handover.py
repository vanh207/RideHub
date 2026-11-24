"""Pydantic schemas cho module Biên bản Giao/Nhận xe (Handover Protocol)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.handover import HandoverStatus, MediaType, ProtocolType, SignerRole


# ---------------------------------------------------------------------------
# Media (ảnh xe, ảnh biên bản đã ký)
# ---------------------------------------------------------------------------

class HandoverMediaItem(BaseModel):
    """Thông tin một ảnh đính kèm biên bản."""

    id: int
    protocol_id: int
    media_type: str = Field(description="VEHICLE_PHOTO | SIGNED_DOCUMENT | DAMAGE_PHOTO")
    file_url: str
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    caption: Optional[str] = None
    sort_order: int = 0
    is_primary: bool = False
    uploaded_by_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Checklist & Damage
# ---------------------------------------------------------------------------

class ChecklistItem(BaseModel):
    item: str = Field(..., description="Tên hạng mục kiểm tra, vd: Đèn pha trước")
    ok: bool = Field(True, description="Trạng thái OK/Not OK")
    note: Optional[str] = Field(None, description="Ghi chú thêm nếu có vấn đề")


class DamagePoint(BaseModel):
    x: float = Field(..., ge=0.0, le=100.0, description="Toạ độ X trên sơ đồ thân xe (0–100%)")
    y: float = Field(..., ge=0.0, le=100.0, description="Toạ độ Y trên sơ đồ thân xe (0–100%)")
    label: str = Field(..., min_length=1, max_length=150, description="Mô tả vị trí tổn hại")
    color: str = Field("orange", description="Màu điểm đánh dấu: orange=cũ, red=mới")


# ---------------------------------------------------------------------------
# Tạo biên bản GIAO XE (CHECK_OUT)
# ---------------------------------------------------------------------------

class HandoverProtocolCreate(BaseModel):
    """Payload tạo biên bản Giao xe (Check-out)."""

    protocol_code: str = Field(..., min_length=3, max_length=50, description="Mã biên bản: BB-xxxx")
    booking_id: int = Field(..., description="Mã đặt chỗ liên kết")
    protocol_type: str = Field(ProtocolType.CHECK_OUT.value, description="CHECK_OUT hoặc CHECK_IN")

    # Thông tin xe & vị trí
    handover_location: str = Field(..., min_length=2, max_length=255)
    vehicle_name: str = Field(..., min_length=1, max_length=150)
    license_plate: str = Field(..., min_length=1, max_length=20)
    vehicle_category: str = Field("CAR", max_length=20)

    # Thông tin khách hàng (tuỳ chọn gửi kèm, nếu không hệ thống tự lấy từ booking/user)
    customer_name: Optional[str] = None
    customer_cccd: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_license: Optional[str] = None

    # Vận hành lúc giao
    odo_checkout: int = Field(0, ge=0, description="Số km lúc giao xe (ODO)")
    fuel_checkout: str = Field("FULL", description="Mức nhiên liệu: FULL|3/4|1/2|1/4|EMPTY")
    free_km_limit: int = Field(0, ge=0, description="Số km miễn phí")

    # Sơ đồ & Checklist
    damage_points: Optional[List[DamagePoint]] = None
    checklist_data: Optional[List[ChecklistItem]] = None

    # Tài chính
    deposit_original: Decimal = Field(Decimal("0"), ge=0, description="Tiền cọc ban đầu (VNĐ)")

    # Chữ ký (nếu ký ngay)
    customer_signature: Optional[str] = None
    staff_signature: Optional[str] = None

    notes: Optional[str] = None

    @field_validator("fuel_checkout")
    @classmethod
    def validate_fuel(cls, v: str) -> str:
        allowed = {"FULL", "3/4", "1/2", "1/4", "EMPTY"}
        if v not in allowed:
            raise ValueError(f"fuel_checkout phải là một trong: {', '.join(sorted(allowed))}")
        return v

    @field_validator("protocol_type")
    @classmethod
    def validate_protocol_type(cls, v: str) -> str:
        allowed = {ProtocolType.CHECK_OUT.value, ProtocolType.CHECK_IN.value}
        if v not in allowed:
            raise ValueError(f"protocol_type phải là: {', '.join(sorted(allowed))}")
        return v


# ---------------------------------------------------------------------------
# Tạo biên bản NHẬN XE (CHECK_IN) — TÁCH THÀNH BẢN GHI MỚI ĐỘC LẬP
# ---------------------------------------------------------------------------

class HandoverCheckinCreate(BaseModel):
    """Payload tạo biên bản Nhận xe (Check-in) riêng biệt khi trả xe.
    
    Tạo ra một bản ghi HandoverProtocol mới hoàn toàn (protocol_type='CHECK_IN')
    để không làm mất bản ghi CHECK_OUT lúc ban đầu.
    """

    protocol_code: str = Field(..., min_length=3, max_length=50, description="Mã biên bản nhận xe: BB-IN-xxxx")
    booking_id: int = Field(..., description="Mã đặt chỗ liên kết")

    odo_checkin: int = Field(..., ge=0, description="Số km lúc trả xe")
    fuel_checkin: str = Field(..., description="Mức nhiên liệu khi trả: FULL|3/4|1/2|1/4|EMPTY")

    handover_location: Optional[str] = Field(None, max_length=255)
    damage_points: Optional[List[DamagePoint]] = None
    checklist_data: Optional[List[ChecklistItem]] = None

    # Phụ phí quyết toán (VNĐ) — tất cả đều phải >= 0
    fee_overtime: Decimal = Field(Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    fee_excess_km: Decimal = Field(Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    fee_fuel: Decimal = Field(Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    fee_cleaning: Decimal = Field(Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    fee_damage: Decimal = Field(Decimal("0"), ge=0, max_digits=12, decimal_places=2)

    # Quyết toán cọc
    deposit_original: Optional[Decimal] = Field(
        None, ge=0, max_digits=12, decimal_places=2
    )
    hold_fine_deposit: Decimal = Field(
        Decimal("0"),
        ge=0,
        max_digits=12,
        decimal_places=2,
        description="Giữ lại từ cọc (khấu trừ vi phạm/phụ phí)",
    )
    refund_immediate: Decimal = Field(
        Decimal("0"),
        ge=0,
        max_digits=12,
        decimal_places=2,
        description="Hoàn lại ngay cho khách",
    )

    # Chữ ký tại thời điểm trả xe
    customer_signature: Optional[str] = None
    staff_signature: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("fuel_checkin")
    @classmethod
    def validate_fuel_checkin(cls, v: str) -> str:
        allowed = {"FULL", "3/4", "1/2", "1/4", "EMPTY"}
        if v not in allowed:
            raise ValueError(f"fuel_checkin phải là một trong: {', '.join(sorted(allowed))}")
        return v

    @model_validator(mode="after")
    def validate_deposit_settlement(self):
        """Kiểm tra logic cọc: tổng tiền giữ lại và hoàn ngay không vượt quá tiền cọc gốc (nếu có)."""
        if self.deposit_original is not None and self.deposit_original > 0:
            total_settled = (self.hold_fine_deposit or Decimal(0)) + (self.refund_immediate or Decimal(0))
            if total_settled > self.deposit_original:
                raise ValueError(
                    f"Tổng tiền giữ lại ({self.hold_fine_deposit}) và hoàn trả ({self.refund_immediate}) "
                    f"không được vượt quá tiền cọc gốc ({self.deposit_original})."
                )
        return self


# Backward-compatible alias
HandoverCheckinUpdate = HandoverCheckinCreate
HandoverReturnUpdate = HandoverCheckinCreate


# ---------------------------------------------------------------------------
# Ký biên bản điện tử
# ---------------------------------------------------------------------------

class HandoverSignRequest(BaseModel):
    """Yêu cầu ký biên bản bởi một bên."""

    signer: str = Field(..., description="CUSTOMER hoặc STAFF")
    signature: str = Field(..., min_length=10, description="Base64 PNG hoặc URL đã lưu trữ")

    @field_validator("signer")
    @classmethod
    def validate_signer(cls, v: str) -> str:
        allowed = {SignerRole.CUSTOMER.value, SignerRole.STAFF.value}
        if v not in allowed:
            raise ValueError(f"signer phải là một trong: {', '.join(sorted(allowed))}")
        return v


# ---------------------------------------------------------------------------
# Xác nhận ảnh giao/nhận xe (Photo Confirmation)
# ---------------------------------------------------------------------------

class PhotoConfirmationRequest(BaseModel):
    """Yêu cầu xác nhận ảnh và tình trạng xe."""

    confirmed: bool = Field(True, description="Xác nhận ảnh và tình trạng xe")
    note: Optional[str] = Field(None, max_length=255, description="Ghi chú xác nhận (nếu có)")


class PhotoConfirmationResponse(BaseModel):
    """Kết quả xác nhận ảnh và trạng thái chuyển đổi tự động."""

    protocol_id: int
    protocol_code: str
    protocol_type: str

    # Trạng thái xác nhận của từng bên
    customer_confirmed: bool
    customer_confirmed_at: Optional[datetime] = None
    customer_confirm_note: Optional[str] = None

    staff_confirmed: bool
    staff_confirmed_at: Optional[datetime] = None
    staff_confirm_note: Optional[str] = None

    both_confirmed: bool
    both_confirmed_at: Optional[datetime] = None

    # Tự động chuyển trạng thái đơn & xe
    booking_id: int
    booking_status: str
    vehicle_id: Optional[int] = None
    vehicle_status: Optional[str] = None
    protocol_status: str

    message: str


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------

class HandoverProtocolResponse(BaseModel):
    """Response đầy đủ trả về cho client."""

    id: int
    protocol_code: str
    booking_id: int
    protocol_type: str

    store_agent_id: Optional[int] = None
    store_agent_name: str
    store_agent_phone: Optional[str] = None
    customer_id: Optional[int] = None
    customer_name: str
    customer_cccd: str
    customer_phone: str
    customer_license: str
    handover_location: str

    vehicle_id: Optional[int] = None
    vehicle_name: str
    license_plate: str
    vehicle_category: str

    odo_checkout: int
    odo_checkin: Optional[int] = None
    fuel_checkout: str
    fuel_checkin: Optional[str] = None
    free_km_limit: int = 0

    damage_points: Optional[Any] = None
    checklist_data: Optional[Any] = None

    deposit_original: Decimal
    fee_overtime: Decimal
    fee_excess_km: Decimal
    fee_fuel: Decimal
    fee_cleaning: Decimal
    fee_damage: Decimal
    hold_fine_deposit: Decimal
    refund_immediate: Decimal

    customer_signature: Optional[str] = None
    staff_signature: Optional[str] = None
    signed_at: Optional[datetime] = None

    # Xác nhận ảnh
    customer_confirmed: bool = False
    customer_confirmed_at: Optional[datetime] = None
    customer_confirm_note: Optional[str] = None
    staff_confirmed: bool = False
    staff_confirmed_at: Optional[datetime] = None
    staff_confirm_note: Optional[str] = None
    both_confirmed: bool = False
    both_confirmed_at: Optional[datetime] = None

    status: str
    notes: Optional[str] = None

    media: List[HandoverMediaItem] = []

    created_at: datetime
    updated_at: datetime

    # Trường tính toán nhanh
    total_extra_fees: Optional[Decimal] = None
    excess_km: Optional[int] = None
    is_fully_signed: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedHandoverResponse(BaseModel):
    """Response phân trang cho danh sách biên bản."""

    total: int
    skip: int
    limit: int
    items: List[HandoverProtocolResponse]
