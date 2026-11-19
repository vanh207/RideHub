from pydantic import BaseModel, Field
from typing import Any, Literal, Optional
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
    bank_name: Optional[str] = None
    bank_bin: Optional[str] = None
    account_number: Optional[str] = None
    account_name: Optional[str] = None
    beneficiary_source: Optional[str] = None
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


# --- 4. Schema mở rộng cho Flow Tích hợp Cổng thanh toán Sandbox (TF19E3D) ---
class PaymentCreateRequest(BaseModel):
    """Schema Client gửi lên để khởi tạo giao dịch đặt cọc / thanh toán."""
    booking_id: int = Field(..., gt=0, description="ID đơn đặt xe cần thanh toán cọc")
    provider: str = Field(default="MOCK_PAY", max_length=50, description="Cổng thanh toán (MOCK_PAY, VNPAY, MOMO...)")
    payment_method: Optional[str] = Field(default="QR_CODE", max_length=50, description="Phương thức: QR_CODE, ATM, CREDIT_CARD...")


class PaymentCreateResponse(BaseModel):
    """Schema trả về cho Frontend hiển thị mã QR và đường link thanh toán."""
    transaction_id: int = Field(..., description="ID bản ghi giao dịch trong CSDL")
    transaction_code: str = Field(..., description="Mã giao dịch duy nhất của hệ thống")
    booking_id: int = Field(..., description="ID đơn đặt xe")
    amount: float = Field(..., description="Số tiền cần thanh toán")
    provider: str = Field(..., description="Cổng thanh toán xử lý")
    payment_method: Optional[str] = Field(None, description="Phương thức thanh toán")
    status: str = Field(..., description="Trạng thái giao dịch khởi tạo (PENDING)")
    payment_url: str = Field(..., description="Đường dẫn chuyển hướng đến trang thanh toán giả lập")
    qr_code_url: Optional[str] = Field(None, description="Mã QR động để quét thanh toán")
    expires_at: Optional[datetime] = Field(None, description="Thời gian hết hạn giao dịch (mặc định 15 phút)")
    hold_expires_at: Optional[datetime] = Field(None, description="Thời hạn giữ chỗ của booking từ backend")
    message: str = Field(default="Khởi tạo giao dịch thanh toán thành công")


class PaymentWebhookPayload(BaseModel):
    """Bản tin Webhook do Cổng thanh toán gửi về API Server."""
    transaction_code: str = Field(..., description="Mã giao dịch hệ thống RideHub đã cấp khi tạo đơn")
    provider_txn_id: str = Field(..., description="Mã giao dịch phát sinh từ Cổng thanh toán")
    amount: float = Field(..., gt=0, description="Số tiền thanh toán thực tế")
    status: str = Field(..., description="Trạng thái thanh toán từ cổng: SUCCESS hoặc FAILED")
    response_code: Optional[str] = Field("00", description="Mã kết quả (00: thành công, khác: lỗi)")
    message: Optional[str] = Field(None, description="Thông điệp phản hồi từ cổng thanh toán")
    timestamp: Optional[str] = Field(None, description="Thời gian giao dịch dạng chuỗi ISO hoặc định dạng cổng")
    signature: str = Field(..., description="Chữ ký bảo mật HMAC-SHA256 để xác thực dữ liệu")


class PaymentRefundRequest(BaseModel):
    """Yêu cầu hoàn tiền cho đơn đặt xe / giao dịch."""
    booking_id: Optional[int] = Field(None, gt=0, description="ID đơn đặt xe cần hoàn tiền")
    transaction_code: Optional[str] = Field(None, description="Mã giao dịch cần hoàn tiền (nếu biết)")
    amount: Optional[float] = Field(None, gt=0, description="Số tiền muốn hoàn (bỏ trống để hoàn toàn bộ giao dịch)")
    reason: Optional[str] = Field("Khách hàng hủy đặt xe hợp lệ", description="Lý do hoàn tiền")


class PaymentSimulateRequest(BaseModel):
    """Yêu cầu giả lập thanh toán nhanh qua Swagger (Simulator tool)."""
    transaction_code: str = Field(..., description="Mã giao dịch cần mô phỏng")
    status: Literal["SUCCESS", "FAILED"] = Field(default="SUCCESS", description="Trạng thái mong muốn mô phỏng: SUCCESS hoặc FAILED")
    message: Optional[str] = Field("Mô phỏng thanh toán sandbox thành công", description="Ghi chú giả lập")


# --- 5. Schema Tích hợp Cổng thanh toán PayOS (TF19EFA) ---
class PayOSPaymentCreateRequest(BaseModel):
    """Yêu cầu tạo link thanh toán cọc và mã QR động qua PayOS."""
    booking_id: int = Field(..., gt=0, description="ID đơn đặt xe cần thanh toán cọc")


class BookingPaymentStatusResponse(BaseModel):
    booking_id: int
    booking_status: str
    payment_status: str
    transaction_code: Optional[str] = None
    amount: Optional[float] = None
    qr_code_url: Optional[str] = None
    bank_name: Optional[str] = None
    bin: Optional[str] = None
    account_number: Optional[str] = None
    account_name: Optional[str] = None
    beneficiary_source: Optional[str] = None
    description: Optional[str] = None
    hold_expires_at: Optional[datetime] = None
    remaining_seconds: int
    hold_duration_seconds: int


class PayOSPaymentResponse(BaseModel):
    """Thông tin trả về cho Frontend hiển thị mã QR động và link thanh toán PayOS."""
    transaction_id: int = Field(..., description="ID bản ghi giao dịch trong CSDL RideHub")
    transaction_code: str = Field(..., description="Mã giao dịch hệ thống RideHub (PAYOS_orderCode)")
    order_code: int = Field(..., description="Mã đơn hàng số nguyên của PayOS")
    booking_id: int = Field(..., description="ID đơn đặt xe")
    amount: int = Field(..., description="Số tiền thanh toán cọc (VNĐ)")
    status: str = Field(..., description="Trạng thái giao dịch (PENDING)")
    checkout_url: Optional[str] = Field(None, description="Link mở trang thanh toán chuẩn của PayOS")
    qr_code: Optional[str] = Field(None, description="Chuỗi dữ liệu VietQR để vẽ mã QR trên frontend hoặc app ngân hàng quét")
    qr_code_url: Optional[str] = Field(None, description="Link ảnh mã QR động sẵn sàng hiển thị thẻ <img>")
    payment_link_id: Optional[str] = Field(None, description="ID phiên thanh toán phía PayOS")
    bank_name: Optional[str] = Field(None, description="Tên ngân hàng thụ hưởng")
    account_number: Optional[str] = Field(None, description="Số tài khoản ngân hàng thụ hưởng")
    account_name: Optional[str] = Field(None, description="Tên chủ tài khoản ngân hàng thụ hưởng")
    bin: Optional[str] = Field(None, description="Mã định danh ngân hàng (BIN)")
    beneficiary_source: Optional[str] = Field(None, description="Nguồn thông tin tài khoản thụ hưởng")
    description: str
    hold_expires_at: datetime
    remaining_seconds: int
    message: str = Field(default="Tạo link thanh toán cọc và mã QR động PayOS thành công")


# --- 6. Schema Webhook từ PayOS (TF1A032) ---
class PayOSWebhookData(BaseModel):
    """Dữ liệu giao dịch bên trong payload webhook PayOS."""
    orderCode: int = Field(..., description="Mã đơn hàng PayOS (order_code)")
    amount: int = Field(..., description="Số tiền giao dịch (VNĐ)")
    description: Optional[str] = Field(None, description="Nội dung chuyển khoản")
    accountNumber: Optional[str] = Field(None, description="Số tài khoản thụ hưởng")
    reference: Optional[str] = Field(None, description="Mã tham chiếu giao dịch ngân hàng")
    transactionDateTime: Optional[str] = Field(None, description="Thời gian giao dịch")
    paymentLinkId: Optional[str] = Field(None, description="ID link thanh toán PayOS")
    code: Optional[str] = Field(None, description="Mã kết quả: 00 = thành công")
    desc: Optional[str] = Field(None, description="Mô tả kết quả từ PayOS")
    counterAccountBankId: Optional[str] = None
    counterAccountBankName: Optional[str] = None
    counterAccountName: Optional[str] = None
    counterAccountNumber: Optional[str] = None
    virtualAccountName: Optional[str] = None
    virtualAccountNumber: Optional[str] = None
    currency: Optional[str] = Field(None, description="Đơn vị tiền tệ, mặc định VND")


class PayOSWebhookPayload(BaseModel):
    """Payload đầy đủ PayOS gửi về webhook endpoint (TF1A032)."""
    code: str = Field(..., description="Mã kết quả: '00' = thành công")
    desc: str = Field(..., description="Mô tả kết quả: 'success' hoặc lý do lỗi")
    success: bool = Field(..., description="True nếu giao dịch thành công")
    data: PayOSWebhookData = Field(..., description="Chi tiết giao dịch")
    signature: str = Field(..., description="Chữ ký HMAC-SHA256 xác thực từ PayOS")
