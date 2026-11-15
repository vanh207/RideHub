"""Dịch vụ tích hợp Cổng thanh toán PayOS (Thanh toán cọc & Sinh mã QR động).

Mã task: TF19EFA
Dự án: RideHub (FastAPI, SQLAlchemy, Python)

Chức năng:
1. Đọc thông tin xác thực Client ID, API Key, Checksum Key từ file .env / settings.
2. Sinh mã đơn hàng (orderCode) số nguyên hợp lệ và nội dung thanh toán chuẩn VietQR (<= 25 ký tự).
3. Sử dụng SDK bất đồng bộ AsyncPayOS để tạo Payment Link và chuỗi mã QR động.
4. Hỗ trợ tra cứu thông tin giao dịch và xác thực chữ ký Webhook từ PayOS.
"""
import re
import unicodedata
from datetime import datetime
from typing import Any, Dict, Optional
from urllib.parse import quote_plus

from fastapi import HTTPException, status
from payos import AsyncPayOS
from payos.types import CreatePaymentLinkRequest

from app.core.config import settings


def remove_vietnamese_accents(text: str) -> str:
    """Chuyển đổi chuỗi tiếng Việt có dấu thành không dấu."""
    nfkd = unicodedata.normalize("NFKD", text)
    no_accent = "".join([c for c in nfkd if not unicodedata.combining(c)])
    return no_accent.replace("đ", "d").replace("Đ", "D")


class PayOSService:
    """Lớp xử lý nghiệp vụ kết nối với Cổng thanh toán PayOS."""

    def __init__(
        self,
        client_id: Optional[str] = None,
        api_key: Optional[str] = None,
        checksum_key: Optional[str] = None,
        return_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
    ):
        """Khởi tạo cấu hình PayOS từ Settings môi trường."""
        self.client_id = client_id or settings.PAYOS_CLIENT_ID
        self.api_key = api_key or settings.PAYOS_API_KEY
        self.checksum_key = checksum_key or settings.PAYOS_CHECKSUM_KEY
        self.return_url = return_url or settings.PAYOS_RETURN_URL
        self.cancel_url = cancel_url or settings.PAYOS_CANCEL_URL

    def _get_client(self) -> AsyncPayOS:
        """Khởi tạo và trả về client AsyncPayOS.

        Kiểm tra tính hợp lệ của biến môi trường trước khi khởi tạo client.
        """
        if (
            not self.client_id
            or not self.api_key
            or not self.checksum_key
            or self.client_id == "your_client_id_here"
            or self.api_key == "your_api_key_here"
            or self.checksum_key == "your_checksum_key_here"
        ):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    "Cấu hình PayOS chưa đầy đủ! Vui lòng kiểm tra các biến môi trường "
                    "PAYOS_CLIENT_ID, PAYOS_API_KEY, PAYOS_CHECKSUM_KEY trong file .env."
                ),
            )

        return AsyncPayOS(
            client_id=self.client_id,
            api_key=self.api_key,
            checksum_key=self.checksum_key,
        )

    def generate_order_code(self, booking_id: int) -> int:
        """Sinh mã đơn hàng orderCode dạng số nguyên duy nhất cho PayOS.

        Quy định của PayOS:
        - orderCode BẮT BUỘC là số nguyên (int), tối đa 9007199254740991 (int53).
        - Phải là số duy nhất, không trùng lặp giữa các yêu cầu tạo link thanh toán.

        Công thức: YYMMDDHHMMSS + (booking_id % 100) -> 14 chữ số an toàn.
        Ví dụ: 26111322150001
        """
        timestamp_prefix = datetime.now().strftime("%y%m%d%H%M%S")
        suffix = f"{booking_id % 100:02d}"
        return int(f"{timestamp_prefix}{suffix}")

    def clean_description(self, text: str, max_length: int = 25) -> str:
        """Chuẩn hóa nội dung giao dịch cho chuyển khoản ngân hàng VietQR / PayOS.

        Quy định ngân hàng:
        - Tối đa 25 ký tự.
        - Không chứa dấu tiếng Việt hoặc ký tự đặc biệt.
        """
        clean_text = remove_vietnamese_accents(text)
        # Chỉ giữ lại chữ cái, số, khoảng trắng và dấu gạch ngang
        clean_text = re.sub(r"[^a-zA-Z0-9\s\-]", "", clean_text)
        clean_text = re.sub(r"\s+", " ", clean_text).strip()
        return clean_text[:max_length]

    async def create_deposit_payment_link(
        self,
        booking_id: int,
        amount: float,
        description: Optional[str] = None,
        return_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Tạo link thanh toán tiền cọc và mã QR động qua PayOS (Bất đồng bộ).

        Args:
            booking_id: ID đơn đặt xe trên RideHub.
            amount: Số tiền cọc cần thanh toán (VNĐ).
            description: Nội dung thanh toán (tùy chọn, tối đa 25 ký tự).
            return_url: URL redirect khi thanh toán thành công.
            cancel_url: URL redirect khi người dùng hủy.

        Returns:
            Dict chứa checkout_url, qr_code, qr_code_url, order_code, payment_link_id...
        """
        client = self._get_client()

        # 1. Chuẩn hóa dữ liệu đầu vào
        order_code = self.generate_order_code(booking_id=booking_id)
        amount_int = int(amount)
        if amount_int <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Số tiền cọc phải lớn hơn 0 VNĐ.",
            )

        # 2. Chuẩn hóa nội dung chuyển khoản
        default_desc = f"Coc xe don {booking_id}"
        desc_to_use = self.clean_description(description or default_desc, max_length=25)

        # 3. URL chuyển hướng
        ret_url = return_url or self.return_url or "http://localhost:3000/payment/success"
        can_url = cancel_url or self.cancel_url or "http://localhost:3000/payment/cancel"

        # 4. Đóng gói request cho PayOS SDK
        payment_data = CreatePaymentLinkRequest(
            order_code=order_code,
            amount=amount_int,
            description=desc_to_use,
            return_url=ret_url,
            cancel_url=can_url,
        )

        try:
            # 5. Gọi API PayOS bất đồng bộ bằng client.payment_requests.create
            response = await client.payment_requests.create(payment_data)

            # 6. Sinh URL ảnh QR động từ chuỗi VietQR để frontend hiển thị thẻ <img>
            encoded_qr = quote_plus(response.qr_code)
            qr_image_url = f"https://api.qrserver.com/v1/create-qr-code/?size=350x350&data={encoded_qr}"

            return {
                "order_code": response.order_code,
                "amount": response.amount,
                "description": response.description,
                "status": response.status,
                "checkout_url": response.checkout_url,
                "qr_code": response.qr_code,
                "qr_code_url": qr_image_url,
                "payment_link_id": response.payment_link_id,
                "bin": getattr(response, "bin", None),
                "account_number": getattr(response, "account_number", None),
                "account_name": getattr(response, "account_name", None),
            }

        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Lỗi khi kết nối cổng thanh toán PayOS: {str(exc)}",
            )

    async def get_payment_link_information(self, order_code: int) -> Any:
        """Tra cứu thông tin trạng thái link thanh toán trên PayOS."""
        client = self._get_client()
        try:
            return await client.payment_requests.get(order_code)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Lỗi khi tra cứu đơn hàng PayOS #{order_code}: {str(exc)}",
            )

    def verify_payment_webhook_data(self, webhook_body: Dict[str, Any]) -> Any:
        """Xác thực chữ ký dữ liệu Webhook từ PayOS."""
        client = self._get_client()
        return client.verifyPaymentWebhookData(webhook_body)


# Khởi tạo singleton instance dùng chung trong toàn bộ dự án
payos_service = PayOSService()
