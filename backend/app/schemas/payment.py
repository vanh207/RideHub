from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime

# --- 1. Schema cho Giao dịch thanh toán (PaymentTransaction) ---
class PaymentTransactionBase(BaseModel):
    booking_id: int
    amount: float = Field(..., gt=0, description="Số tiền giao dịch phải lớn hơn 0")
    provider: str = Field(..., max_length=50, description="Cổng thanh toán (VNPAY, MOMO...)")
    payment_method: Optional[str] = Field(None, max_length=50)

class PaymentTransactionCreate(PaymentTransactionBase):
    transaction_code: str = Field(..., max_length=100)

class PaymentTransactionResponse(PaymentTransactionBase):
    id: int
    transaction_code: str
    provider_txn_id: Optional[str] = None
    status: str
    qr_code_url: Optional[str] = None
    paid_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # Cho phép chuyển đổi từ SQLAlchemy Model sang Pydantic schema


# --- 2. Schema cho Hoàn tiền (Refund) ---
class RefundBase(BaseModel):
    booking_id: int
    payment_transaction_id: Optional[int] = None
    amount: float = Field(..., gt=0)
    reason: Optional[str] = None

class RefundCreate(RefundBase):
    pass

class RefundResponse(RefundBase):
    id: int
    status: str
    processed_by: Optional[int] = None
    processed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


# --- 3. Schema cho Webhook Log ---
class PaymentWebhookLogCreate(BaseModel):
    provider_txn_id: Optional[str] = None
    transaction_code: Optional[str] = None
    payload: Optional[Any] = None
    signature_valid: Optional[str] = None
    process_result: Optional[str] = None
    queue_reason: Optional[str] = None