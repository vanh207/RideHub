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
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional
from urllib.parse import parse_qsl, quote_plus, urlencode, urlsplit, urlunsplit

from fastapi import HTTPException, status
from payos import AsyncPayOS
from payos.types import CreatePaymentLinkRequest

from app.core.config import settings
from app.services.payment_booking_reconciliation import (
    apply_successful_payment_to_booking,
    create_pending_refund_for_transaction,
)


BANK_NAMES_BY_BIN = {
    "970422": "MB Bank",
}


def _read_field(source: Any, *names: str) -> Any:
    for name in names:
        if isinstance(source, dict):
            value = source.get(name)
        else:
            value = getattr(source, name, None)
        if value is not None and str(value).strip():
            return value
    return None


def remove_vietnamese_accents(text: str) -> str:
    """Chuyển đổi chuỗi tiếng Việt có dấu thành không dấu."""
    nfkd = unicodedata.normalize("NFKD", text)
    no_accent = "".join([c for c in nfkd if not unicodedata.combining(c)])
    return no_accent.replace("đ", "d").replace("Đ", "D")


def _url_for_booking(url: str, booking_id: int) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["booking_id"] = str(booking_id)
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )


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

    def normalize_beneficiary_details(
        self, source: Any
    ) -> Dict[str, Optional[str]]:
        """Normalize PayOS beneficiary fields, with optional local env fallbacks."""
        bank_bin_value = _read_field(source, "bin", "bank_bin", "bankBin")
        bank_bin = str(bank_bin_value).strip() if bank_bin_value is not None else None
        payos_bank_name = _read_field(source, "bank_name", "bankName")
        payos_account_number = _read_field(
            source, "account_number", "accountNumber", "account_no", "accountNo"
        )
        payos_account_name = _read_field(
            source, "account_name", "accountName"
        )

        config_fallback_used = False
        if payos_bank_name is not None:
            bank_name = str(payos_bank_name).strip()
        else:
            bank_name = BANK_NAMES_BY_BIN.get(bank_bin)
            if not bank_name:
                bank_name = settings.PAYOS_BANK_NAME.strip() or None
                config_fallback_used = bank_name is not None
        if not bank_name and bank_bin:
            bank_name = f"BIN {bank_bin}"

        account_number = (
            str(payos_account_number).strip()
            if payos_account_number is not None
            else settings.PAYOS_ACCOUNT_NUMBER.strip() or None
        )
        account_name = (
            str(payos_account_name).strip()
            if payos_account_name is not None
            else settings.PAYOS_ACCOUNT_NAME.strip() or None
        )
        if payos_account_number is None and account_number:
            config_fallback_used = True
        if payos_account_name is None and account_name:
            config_fallback_used = True

        payos_data_present = any(
            value is not None
            for value in (
                payos_bank_name,
                bank_bin_value,
                payos_account_number,
                payos_account_name,
            )
        )
        stored_source = _read_field(source, "beneficiary_source")
        if config_fallback_used and payos_data_present:
            beneficiary_source = "PayOS + cấu hình PAYOS_*"
        elif config_fallback_used:
            beneficiary_source = "Cấu hình PAYOS_* trong .env"
        elif stored_source:
            beneficiary_source = str(stored_source)
        elif payos_data_present:
            beneficiary_source = (
                "PayOS (tên ngân hàng suy ra từ BIN)"
                if not payos_bank_name and bank_bin
                else "PayOS"
            )
        else:
            beneficiary_source = "PayOS chưa trả về thông tin thụ hưởng"

        return {
            "bank_name": bank_name,
            "bin": bank_bin,
            "account_number": account_number,
            "account_name": account_name,
            "beneficiary_source": beneficiary_source,
        }

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
        ret_url = _url_for_booking(
            return_url or self.return_url,
            booking_id,
        )
        can_url = _url_for_booking(
            cancel_url or self.cancel_url,
            booking_id,
        )

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
            beneficiary_details = self.normalize_beneficiary_details(response)

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
                **beneficiary_details,
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

    async def cancel_payment_link(
        self,
        order_code: int,
        reason: str = "Booking hold cancelled",
    ) -> Any:
        """Hủy link PayOS đang chờ thanh toán."""
        client = self._get_client()
        try:
            return await client.cancelPaymentLink(order_code, reason)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Không thể hủy liên kết thanh toán PayOS.",
            ) from exc

    async def verify_payment_webhook_data(self, webhook_body: Dict[str, Any]) -> Any:
        """Xác thực chữ ký dữ liệu Webhook từ PayOS."""
        client = self._get_client()
        return await client.verifyPaymentWebhookData(webhook_body)

    async def process_payos_webhook(
        self,
        webhook_body: Dict[str, Any],
        db,
    ) -> Dict[str, Any]:
        """Xử lý toàn bộ luồng Webhook từ PayOS (TF1A032).

        Luồng:
        1. Xác thực chữ ký (Signature Verification) bằng PayOS SDK + PAYOS_CHECKSUM_KEY.
        2. Ghi log vào bảng payment_webhook_logs.
        3. Idempotency - bỏ qua nếu giao dịch đã được xử lý.
        4. Cập nhật PaymentTransaction: PENDING -> SUCCESS (hoặc FAILED/CANCELLED).
        5. Nếu SUCCESS: cập nhật Booking theo trạng thái chuẩn (DEPOSIT_PAID hoặc refund khi đơn đã đóng).

        Args:
            webhook_body: Dict raw payload do PayOS gửi về.
            db: SQLAlchemy Session.

        Returns:
            Dict chứa thông tin kết quả xử lý.

        Raises:
            HTTPException 401 nếu chữ ký không hợp lệ.
            HTTPException 404 nếu không tìm thấy giao dịch.
        """
        from datetime import datetime
        from app.models.payment import PaymentTransaction, PaymentWebhookLog
        from app.models.booking import Booking

        order_code = None
        transaction_code = None

        try:
            # B1. Xác thực chữ ký từ PayOS SDK (sử dụng PAYOS_CHECKSUM_KEY)
            try:
                verified_data = await self.verify_payment_webhook_data(webhook_body)
                is_valid = True
            except Exception:
                is_valid = False
                verified_data = None

            # Trích xuất thông tin cơ bản từ payload để ghi log
            data_block = webhook_body.get("data", {})
            order_code = data_block.get("orderCode")
            if order_code:
                transaction_code = f"PAYOS_{order_code}"

            # B2. Ghi log webhook vào CSDL (luôn ghi kể cả chữ ký sai)
            webhook_log = PaymentWebhookLog(
                provider_txn_id=data_block.get("reference") or data_block.get("paymentLinkId"),
                transaction_code=transaction_code,
                payload=webhook_body,
                signature_valid="VALID" if is_valid else "INVALID",
                process_result="PENDING",
                queue_reason=None,
                processed_at=datetime.now(),
            )
            db.add(webhook_log)
            db.flush()  # flush để có id nhưng chưa commit

            # B3. Từ chối nếu chữ ký sai
            if not is_valid:
                webhook_log.process_result = "REJECTED_INVALID_SIGNATURE"
                webhook_log.queue_reason = (
                    "Chữ ký PayOS không hợp lệ. "
                    "Kiểm tra PAYOS_CHECKSUM_KEY và dữ liệu payload (TF1A032)."
                )
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Xác thực chữ ký Webhook PayOS thất bại. Yêu cầu không hợp lệ.",
                )

            # B4. Tra cứu giao dịch trong CSDL
            if not transaction_code:
                webhook_log.process_result = "REJECTED_NO_ORDER_CODE"
                webhook_log.queue_reason = "Payload thiếu orderCode không thể tra cứu giao dịch."
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Payload Webhook không chứa orderCode hợp lệ.",
                )

            transaction = (
                db.query(PaymentTransaction)
                .filter(PaymentTransaction.transaction_code == transaction_code)
                .first()
            )

            if not transaction:
                webhook_log.process_result = "NOT_FOUND"
                webhook_log.queue_reason = f"Không tìm thấy giao dịch: {transaction_code}"
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Không tìm thấy giao dịch PayOS với mã {transaction_code}",
                )

            booking = (
                db.query(Booking)
                .filter(Booking.id == transaction.booking_id)
                .with_for_update()
                .first()
            )
            transaction = (
                db.query(PaymentTransaction)
                .filter(PaymentTransaction.id == transaction.id)
                .with_for_update()
                .first()
            )

            # B5. Idempotency - bỏ qua nếu đã xử lý xong
            if transaction.status in (
                "SUCCESS",
                "REFUNDED",
                "FAILED",
                "CANCELLED",
                "EXPIRED",
                "LATE_PAYMENT",
            ):
                webhook_log.process_result = "IDEMPOTENT_IGNORED"
                webhook_log.queue_reason = (
                    f"Giao dịch {transaction_code} đã ở trạng thái {transaction.status}. "
                    "Bỏ qua cập nhật trùng lặp (Idempotency - TF1A032)."
                )
                db.commit()
                return {
                    "status": "OK",
                    "message": "Giao dịch đã được xử lý thành công trước đó (Idempotent).",
                    "transaction_code": transaction_code,
                    "current_status": transaction.status,
                }

            # B6. Phân tích kết quả PayOS
            is_success = (
                webhook_body.get("success") is True
                and webhook_body.get("code") == "00"
            )

            if is_success:
                reported_amount = data_block.get("amount")
                try:
                    if isinstance(reported_amount, bool):
                        raise InvalidOperation
                    actual_amount = Decimal(str(reported_amount))
                    expected_amount = Decimal(str(transaction.amount))
                    if not actual_amount.is_finite():
                        raise InvalidOperation
                    amount_matches = actual_amount == expected_amount
                except (InvalidOperation, TypeError, ValueError):
                    actual_amount = None
                    expected_amount = Decimal(str(transaction.amount))
                    amount_matches = False

                if not amount_matches:
                    transaction.status = "AMOUNT_MISMATCH"
                    transaction.paid_at = datetime.now()
                    webhook_log.process_result = "AMOUNT_MISMATCH"
                    if actual_amount is None:
                        webhook_log.queue_reason = (
                            "Số tiền PayOS báo không hợp lệ; "
                            f"số tiền giao dịch yêu cầu là {expected_amount:f} VND."
                        )
                    else:
                        difference = abs(expected_amount - actual_amount)
                        direction = "thiếu" if actual_amount < expected_amount else "thừa"
                        webhook_log.queue_reason = (
                            f"Thanh toán {direction} {difference:f} VND: "
                            f"yêu cầu {expected_amount:f} VND, "
                            f"PayOS báo {actual_amount:f} VND."
                        )
                    db.commit()
                    return {
                        "status": "OK",
                        "message": "Số tiền thanh toán không khớp; cần xử lý thủ công.",
                        "transaction_code": transaction_code,
                        "booking_id": transaction.booking_id,
                    }

                # === Thanh toán THÀNH CÔNG ===
                transaction.provider_txn_id = (
                    data_block.get("reference")
                    or data_block.get("paymentLinkId")
                )

                # Cập nhật đơn đặt xe sang BOOKED (khóa xe)
                if (
                    booking
                    and (
                        booking.status not in {"PENDING_PAYMENT", "PENDING"}
                        or booking.hold_expires_at is None
                        or booking.hold_expires_at <= datetime.now()
                    )
                ):
                    transaction.status = "LATE_PAYMENT"
                    transaction.paid_at = datetime.now()
                    create_pending_refund_for_transaction(
                        db,
                        booking,
                        transaction,
                        "LATE_PAYMENT: thanh toán đến sau khi giữ chỗ hết hạn hoặc đơn đã đóng.",
                    )
                    webhook_log.process_result = "LATE_PAYMENT"
                    webhook_log.queue_reason = (
                        "PayOS báo đã thanh toán sau khi booking hết hạn hoặc bị hủy; đã tạo refund PENDING."
                    )
                    db.commit()
                    return {
                        "status": "OK",
                        "message": "Thanh toán đến sau khi giữ chỗ hết hạn; đã tạo refund PENDING.",
                        "transaction_code": transaction_code,
                        "booking_id": transaction.booking_id,
                        "booking_status": booking.status,
                    }

                transaction.status = "SUCCESS"
                transaction.paid_at = datetime.now()
                if booking:
                    apply_successful_payment_to_booking(db, booking, transaction)

                webhook_log.process_result = "SUCCESS"
                webhook_log.queue_reason = (
                    "Xác thực hợp lệ. Đã cập nhật giao dịch SUCCESS và "
                    "đối chiếu trạng thái đơn đặt xe (TF1A032)."
                )
                db.commit()

                return {
                    "status": "OK",
                    "message": "Webhook PayOS xử lý thành công: giao dịch PAID, trạng thái đơn đã được đối chiếu.",
                    "transaction_code": transaction_code,
                    "booking_id": transaction.booking_id,
                    "booking_status": booking.status if booking else None,
                    "order_code": order_code,
                }

            else:
                # === Thanh toán THẤT BẠI / HỦY ===
                transaction.status = "FAILED"
                transaction.provider_txn_id = (
                    data_block.get("reference")
                    or data_block.get("paymentLinkId")
                )

                webhook_log.process_result = "FAILED"
                webhook_log.queue_reason = (
                    webhook_body.get("desc")
                    or "Cổng thanh toán PayOS báo giao dịch thất bại hoặc bị hủy."
                )
                db.commit()

                return {
                    "status": "OK",
                    "message": "Đã ghi nhận giao dịch PayOS thất bại (FAILED).",
                    "transaction_code": transaction_code,
                    "order_code": order_code,
                    "reason": webhook_body.get("desc"),
                }

        except HTTPException:
            raise
        except Exception as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Lỗi hệ thống khi xử lý PayOS Webhook: {str(exc)}",
            )


# Khởi tạo singleton instance dùng chung trong toàn bộ dự án
payos_service = PayOSService()
