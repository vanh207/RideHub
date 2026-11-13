"""Lớp Dịch vụ Cổng thanh toán giả lập (Sandbox/Mock Payment Gateway Service).

Mã task: TF19E3D
Dự án: RideHub (FastAPI, SQLAlchemy, Python)

Chức năng:
1. Sinh mã giao dịch độc lập, duy nhất (transaction_code) - TF1B039-TC002.
2. Khởi tạo phiên thanh toán sandbox, tạo payment_url và qr_code_url động - TF1B039-TC001.
3. Sinh chữ ký điện tử và xác thực chữ ký Webhook bằng thuật toán HMAC-SHA256 - TF1B039-TC005, TF1B039-TC006.
4. Xử lý yêu cầu hoàn tiền (Refund mock) gọi sang cổng thanh toán - TF1B039-TC009, TF1B039-TC010.
5. Hỗ trợ tạo Webhook Payload giả lập đầy đủ chữ ký phục vụ kiểm thử tự động.
"""
import hashlib
import hmac
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from urllib.parse import quote_plus, urlencode

from app.core.config import settings


class MockPaymentGatewayService:
    """Lớp xử lý tích hợp Cổng thanh toán Sandbox (Mock Payment Gateway)."""

    def __init__(
        self,
        secret_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        """Khởi tạo cấu hình cho Cổng thanh toán Sandbox.

        Args:
            secret_key: Khóa bí mật dùng để tạo/xác thực chữ ký HMAC-SHA256.
            base_url: Đường dẫn gốc giả lập cổng thanh toán.
        """
        self.secret_key = secret_key or getattr(
            settings, "PAYMENT_GATEWAY_SECRET", "ridehub_mock_secret_key_2026_tf19e3d"
        )
        self.base_url = base_url or getattr(
            settings, "PAYMENT_MOCK_BASE_URL", "https://sandbox.ridehub.vn"
        )

    def generate_transaction_code(self, prefix: str = "RH") -> str:
        """Sinh mã giao dịch duy nhất cho hệ thống RideHub.

        Đảm bảo ràng buộc unique khóa giao dịch (TF1B039-TC002).
        Định dạng: RH_<YYYYMMDDHHMMSS>_<RANDOM_8_HEX>
        Ví dụ: RH_20261112093000_A1B2C3D4
        """
        timestamp_str = datetime.now().strftime("%Y%m%d%H%M%S")
        random_suffix = uuid.uuid4().hex[:8].upper()
        return f"{prefix}_{timestamp_str}_{random_suffix}"

    def generate_provider_txn_id(self, provider: str = "MOCK") -> str:
        """Sinh mã giao dịch giả lập phía cổng thanh toán đối tác."""
        today_str = datetime.now().strftime("%Y%m%d")
        unique_token = uuid.uuid4().hex[:12].upper()
        return f"{provider.upper()}_{today_str}_{unique_token}"

    def generate_signature(
        self, data: Dict[str, Any], secret_key: Optional[str] = None
    ) -> str:
        """Tạo chữ ký bảo mật HMAC-SHA256 chuẩn hóa cho bản tin giao dịch.

        Thuật toán ký chuẩn:
        1. Loại bỏ các trường không tham gia ký (signature, secure_hash, None, rỗng).
        2. Sắp xếp các tham số theo thứ tự alphabet của key (A -> Z).
        3. Ghép nối thành chuỗi query format `key1=value1&key2=value2...`.
        4. Băm HMAC với thuật toán SHA-256 và secret_key bí mật.
        5. Xuất chuỗi Hex Digest dạng chữ thường.
        """
        key_to_use = (secret_key or self.secret_key).encode("utf-8")

        # 1. Lọc và chuẩn hóa dữ liệu
        filtered_items = []
        for key, value in data.items():
            if key in ("signature", "secure_hash"):
                continue
            if value is None:
                continue
            # Chuyển boolean, float, int sang chuỗi chuẩn
            if isinstance(value, float):
                # Giữ nguyên định dạng số (tránh sai lệch dấu phẩy động)
                val_str = f"{value:.2f}" if value % 1 != 0 else f"{value:.1f}"
            else:
                val_str = str(value)
            filtered_items.append((key, val_str))

        # 2. Sắp xếp khóa theo bảng chữ cái A-Z
        sorted_items = sorted(filtered_items, key=lambda item: item[0])

        # 3. Tạo chuỗi ký
        sign_string = "&".join(f"{k}={v}" for k, v in sorted_items)

        # 4. Ký HMAC-SHA256
        signature = hmac.new(
            key_to_use,
            sign_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return signature

    def verify_webhook_signature(
        self,
        payload: Dict[str, Any],
        received_signature: str,
        secret_key: Optional[str] = None,
    ) -> bool:
        """Xác thực tính toàn vẹn và nguồn gốc của bản tin Webhook.

        Sử dụng hmac.compare_digest để ngăn chặn triệt để tấn công Timing Attack.

        Args:
            payload: Dữ liệu nhận từ Webhook (dạng dict).
            received_signature: Chữ ký gửi kèm trong bản tin hoặc Header.
            secret_key: Khóa bí mật (nếu muốn override).

        Returns:
            True nếu chữ ký hợp lệ, False nếu sai chữ ký hoặc dữ liệu bị sửa đổi.
        """
        if not received_signature:
            return False

        try:
            expected_signature = self.generate_signature(
                payload, secret_key=secret_key
            )
            # So sánh an toàn không phụ thuộc thời gian
            return hmac.compare_digest(
                expected_signature.lower(), received_signature.strip().lower()
            )
        except Exception:
            return False

    def create_payment_session(
        self,
        booking_id: int,
        amount: float,
        provider: str = "MOCK_PAY",
        payment_method: str = "QR_CODE",
        order_info: Optional[str] = None,
        return_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Tạo phiên giao dịch thanh toán Sandbox (Mock Payment Session).

        Sinh ra:
        - transaction_code: Mã giao dịch nội bộ RideHub
        - payment_url: Đường link trang thanh toán giả lập sandbox
        - qr_code_url: Đường dẫn ảnh mã QR động để người dùng quét app ngân hàng
        - expires_at: Thời gian hết hạn phiên thanh toán (15 phút - TF1B039-TC004)
        """
        transaction_code = self.generate_transaction_code(prefix="RH")
        provider_txn_id = self.generate_provider_txn_id(provider=provider)
        expires_at = datetime.now() + timedelta(minutes=15)

        # Mô tả đơn hàng
        info = (
            order_info
            or f"Thanh toan tien coc don dat xe #{booking_id} tren RideHub"
        )

        # 1. Tạo dữ liệu mã QR động
        qr_content = (
            f"RIDEHUB_PAY|BOOKING:{booking_id}|TXN:{transaction_code}"
            f"|AMOUNT:{int(amount)}|EXP:{int(expires_at.timestamp())}"
        )
        encoded_qr_content = quote_plus(qr_content)
        # Sử dụng API sinh QR chuẩn SVG/PNG động tương thích mọi ứng dụng
        qr_code_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={encoded_qr_content}"

        # 2. Tạo đường link thanh toán chuyển hướng (Payment URL)
        query_params = {
            "txn": transaction_code,
            "booking_id": booking_id,
            "amount": f"{amount:.2f}",
            "provider": provider,
            "method": payment_method,
            "order_info": info,
            "expires_at": expires_at.isoformat(),
        }
        if return_url:
            query_params["return_url"] = return_url

        payment_url = f"{self.base_url}/checkout?{urlencode(query_params)}"

        return {
            "transaction_code": transaction_code,
            "provider_txn_id": provider_txn_id,
            "booking_id": booking_id,
            "amount": amount,
            "provider": provider,
            "payment_method": payment_method,
            "status": "PENDING",
            "payment_url": payment_url,
            "qr_code_url": qr_code_url,
            "expires_at": expires_at,
            "order_info": info,
        }

    def create_mock_webhook_payload(
        self,
        transaction_code: str,
        amount: float,
        provider_txn_id: Optional[str] = None,
        status: str = "SUCCESS",
        response_code: str = "00",
        message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Tạo bản tin Webhook mẫu có kèm chữ ký HMAC-SHA256 hợp lệ.

        Dùng để test sandbox, tự động hóa kiểm thử (Mock Test) hoặc
        Swagger UI simulate callback.
        """
        p_txn_id = provider_txn_id or self.generate_provider_txn_id()
        msg = message or (
            "Giao dich thanh toan thanh cong qua cong sandbox"
            if status == "SUCCESS"
            else "Giao dich thanh toan that bai hoac bi huy"
        )
        payload = {
            "transaction_code": transaction_code,
            "provider_txn_id": p_txn_id,
            "amount": float(amount),
            "status": status,
            "response_code": response_code,
            "message": msg,
            "timestamp": datetime.now().isoformat(),
        }

        # Ký chữ ký số bảo mật
        signature = self.generate_signature(payload)
        payload["signature"] = signature
        return payload

    def process_refund(
        self,
        transaction_code: str,
        amount: float,
        reason: str = "",
    ) -> Dict[str, Any]:
        """Giả lập gọi API hoàn tiền (Refund API) sang Cổng thanh toán.

        Đáp ứng TF1B039-TC009 & TF1B039-TC010.
        """
        refund_txn_id = f"REFUND_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6].upper()}"
        return {
            "status": "SUCCESS",
            "refund_txn_id": refund_txn_id,
            "transaction_code": transaction_code,
            "amount": float(amount),
            "reason": reason or "Khach hang yeu cau hoan coc",
            "processed_at": datetime.now().isoformat(),
            "message": "Hoan tien thanh cong qua cong thanh toan sandbox",
        }


# Khởi tạo instance mặc định (Singleton pattern) dùng chung trong dự án
payment_gateway_service = MockPaymentGatewayService()

