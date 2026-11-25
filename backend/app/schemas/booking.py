from pydantic import BaseModel, ConfigDict, Field, model_validator
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional


class BookingHoldCreate(BaseModel):
    """Body tạo đơn thuê. Client không được gửi số tiền; nếu gửi sẽ bị bỏ qua."""

    model_config = ConfigDict(extra="ignore")

    customer_id: Optional[int] = Field(None, gt=0)
    vehicle_id: int = Field(..., gt=0)
    start_time: datetime
    end_time: datetime
    delivery_point_id: Optional[int] = Field(None, gt=0)
    customer_note: Optional[str] = None

    @model_validator(mode="after")
    def normalize_and_validate_times(self):
        if self.start_time.tzinfo is not None:
            self.start_time = self.start_time.astimezone().replace(tzinfo=None)
        if self.end_time.tzinfo is not None:
            self.end_time = self.end_time.astimezone().replace(tzinfo=None)
        if self.end_time <= self.start_time:
            raise ValueError("end_time phải lớn hơn start_time.")
        return self


class BookingHoldResponse(BaseModel):
    id: int
    booking_code: Optional[str] = None
    status: str
    vehicle_id: int
    store_id: int
    start_time: datetime
    end_time: datetime
    hold_expires_at: datetime
    rental_amount: float
    delivery_fee: float
    deposit_amount: float
    total_amount: float
    reservation_id: int


class BookingBase(BaseModel):
    customer_id: int
    vehicle_id: int
    store_id: Optional[int] = None
    delivery_point_id: Optional[int] = None
    start_time: datetime
    end_time: datetime
    rental_amount: float
    delivery_fee: float = 0 
    deposit_amount: float = 0
    total_amount: float

class BookingCreate(BookingBase):
    pass

class BookingResponse(BookingBase):
    id: int
    status: str
    hold_expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BookingCancelRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


class RefundQuoteResponse(BaseModel):
    amount: Decimal
    rate: Decimal
    policy_code: str
    reason: str


class BookingCancelResponse(BaseModel):
    booking_id: int
    status: str
    cancelled_at: Optional[datetime] = None
    cancelled_by: Optional[str] = None
    cancel_reason: Optional[str] = None
    refund: RefundQuoteResponse
    refund_id: Optional[int] = None
    refund_status: Optional[str] = None
    reservation_released: bool = False
    schedule_released: bool = False
    already_cancelled: bool = False


class BookingSettlementRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount_received: Decimal = Field(
        ...,
        ge=0,
        max_digits=12,
        decimal_places=2,
        description="Số tiền thực nhận khi tất toán (phải khớp số tiền cần thu)",
    )
    payment_method: Literal["CASH", "BANK_TRANSFER", "OTHER"] = Field(
        "CASH",
        description="Phương thức thu khoản tất toán cuối",
    )


class BookingSettlementFeeBreakdown(BaseModel):
    fee_overtime: Decimal
    fee_excess_km: Decimal
    fee_fuel: Decimal
    fee_cleaning: Decimal
    fee_damage: Decimal


class BookingSettlementResponse(BaseModel):
    booking_id: int
    status: str
    currency: str
    total_amount: Decimal
    previously_paid: Decimal
    refunded_amount: Decimal
    net_paid: Decimal
    remaining_amount: Decimal
    fee_breakdown: BookingSettlementFeeBreakdown
    extra_fees: Decimal
    amount_due: Decimal
    transaction_id: int
    transaction_code: str
    transaction_status: str
    payment_method: str
    settled_at: datetime


# ==============================================================================
# SCHEMAS DÀNH RIÊNG CHO CỬA HÀNG XÁC NHẬN / TỪ CHỐI ĐƠN (TF1A595)
# ==============================================================================

class StoreOrderConfirmRequest(BaseModel):
    """Payload khi cửa hàng duyệt xác nhận đơn đặt xe."""
    note: Optional[str] = Field(None, max_length=500, description="Ghi chú xác nhận của cửa hàng")


class StoreOrderConfirmResponse(BaseModel):
    """Kết quả phản hồi sau khi cửa hàng xác nhận đơn."""
    success: bool = True
    message: str = "Cửa hàng đã xác nhận duyệt đơn đặt xe thành công."
    booking_id: int
    status: str
    confirmed_at: datetime
    confirmed_by_user_id: Optional[int] = None
    already_confirmed: bool = False


class StoreOrderRejectRequest(BaseModel):
    """Payload khi cửa hàng từ chối đơn đặt xe (bắt buộc kèm lý do)."""
    reason: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Lý do từ chối nhận đơn (bắt buộc: xe hỏng, hết xe, không đủ điều kiện eKYC,...)",
        examples=["Xe gặp sự cố kỹ thuật đột xuất cần bảo dưỡng"]
    )
    note: Optional[str] = Field(None, max_length=500, description="Ghi chú nội bộ thêm")


class StoreOrderRejectResponse(BaseModel):
    """Kết quả phản hồi sau khi cửa hàng từ chối đơn."""
    success: bool = True
    message: str = "Đã từ chối đơn đặt xe và tự động kích hoạt hoàn 100% tiền cọc cho khách hàng."
    booking_id: int
    status: str
    cancelled_at: Optional[datetime] = None
    cancelled_by: Optional[str] = None
    cancel_reason: Optional[str] = None
    refund_amount: float = 0.0
    refund_rate: float = 1.0
    refund_status: Optional[str] = None
    refund_id: Optional[int] = None
    already_cancelled: bool = False


class StoreOrderCustomerInfo(BaseModel):
    id: int
    full_name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    cccd: Optional[str] = None
    ekyc_status: str = "pass"


class StoreOrderVehicleInfo(BaseModel):
    id: int
    name: str
    license_plate: str
    vehicle_type: Optional[str] = None
    category_label: Optional[str] = None
    image_url: Optional[str] = None


class StoreOrderScheduleInfo(BaseModel):
    start_time: datetime
    end_time: datetime
    duration_days: float
    schedule_display: str


class StoreOrderPricingInfo(BaseModel):
    rental_amount: float
    delivery_fee: float
    deposit_amount: float
    total_amount: float
    paid_deposit: float
    remaining_amount: float
    collateral_note: Optional[str] = None


class StoreOrderItem(BaseModel):
    id: int
    booking_code: str
    store_id: Optional[int] = None
    status: str
    status_label: str
    cancel_reason: Optional[str] = None
    cancelled_by: Optional[str] = None
    customer: StoreOrderCustomerInfo
    vehicle: StoreOrderVehicleInfo
    schedule: StoreOrderScheduleInfo
    pricing: StoreOrderPricingInfo
    created_at: datetime


class StoreOrderKPIMetrics(BaseModel):
    total_orders: int = 0
    pending_orders: int = 0
    approved_orders: int = 0
    cancelled_orders: int = 0
    total_deposit: float = 0.0
    total_revenue: float = 0.0
    remain_collection: float = 0.0


class StoreOrderListResponse(BaseModel):
    success: bool = True
    total: int
    page: int
    page_size: int
    metrics: StoreOrderKPIMetrics
    orders: list[StoreOrderItem]

