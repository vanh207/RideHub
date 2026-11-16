"""Router API Xử lý Thanh toán, Webhook & Hoàn tiền (Sandbox & PayOS).

Mã task:
- TF19E3D: Lớp tích hợp cổng thanh toán Sandbox/Mock
- TF19EFA: Thanh toán tiền cọc: tạo giao dịch và mã QR động qua PayOS
- TF1A032: Webhook thanh toán PayOS: xác nhận, cập nhật đơn

Các tính năng cốt lõi:
1. POST /api/payments/deposit/payos: Tạo link cọc xe & mã QR động qua PayOS (TF19EFA).
2. GET  /api/payments/payos/order/{order_code}: Tra cứu trạng thái đơn hàng PayOS.
3. POST /api/payments/webhook/payos: Tiếp nhận Webhook từ PayOS, xác thực chữ ký SDK + Idempotency (TF1A032).
4. POST /api/payments/create: Khởi tạo giao dịch cọc & sinh mã QR / URL sandbox (TF19E3D).
5. POST /api/payments/webhook: Nhận Webhook từ cổng thanh toán, xác thực HMAC-SHA256 & Idempotency.
6. POST /api/payments/refund: Xử lý hoàn tiền cho giao dịch thành công & giải phóng lịch xe.
7. GET  /api/payments/{transaction_code}: Tra cứu chi tiết trạng thái giao dịch.
8. GET  /api/payments/booking/{booking_id}: Tra cứu lịch sử thanh toán theo đơn đặt xe.
9. POST /api/payments/simulate: Giả lập cổng thanh toán bắn Webhook trực tiếp từ Swagger UI.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.booking import Booking
from app.models.payment import PaymentTransaction, PaymentWebhookLog, Refund
from app.schemas.payment import (
    PayOSPaymentCreateRequest,
    PayOSPaymentResponse,
    PayOSWebhookPayload,
    PaymentCreateRequest,
    PaymentCreateResponse,
    PaymentRefundRequest,
    PaymentSimulateRequest,
    PaymentTransactionResponse,
    PaymentWebhookPayload,
    RefundResponse,
)
from app.services.payment_gateway import payment_gateway_service
from app.services.payos_service import payos_service

router = APIRouter(
    prefix="/payments",
    tags=["Payments - Thanh toán & Cổng PayOS / Sandbox"],
)


# ==============================================================================
# 1. API THANH TOÁN TIỀN CỌC QUA CỔNG PAYOS (MÃ TASK: TF19EFA)
# ==============================================================================
@router.post(
    "/deposit/payos",
    response_model=PayOSPaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo giao dịch thanh toán tiền cọc & sinh mã QR động qua PayOS (TF19EFA)",
    description="""
    Khởi tạo giao dịch thanh toán cọc đơn đặt xe thông qua cổng thanh toán PayOS:
    - Đọc thông tin xác thực an toàn từ `.env` (`PAYOS_CLIENT_ID`, `PAYOS_API_KEY`, `PAYOS_CHECKSUM_KEY`).
    - Tự động sinh `orderCode` số nguyên duy nhất và chuẩn hóa nội dung VietQR (tối đa 25 ký tự).
    - Gọi bất đồng bộ (`async/await`) sang SDK **AsyncPayOS**.
    - Nhận đường dẫn thanh toán (`checkoutUrl`) và chuỗi mã QR động (`qrCode`).
    - Lưu bản ghi `PaymentTransaction` vào MySQL ở trạng thái **PENDING**.
    """,
)
async def create_payos_deposit_payment(
    request: PayOSPaymentCreateRequest,
    db: Session = Depends(get_db),
):
    try:
        # B1. Kiểm tra đơn đặt xe (Booking)
        booking = db.query(Booking).filter(Booking.id == request.booking_id).first()
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy đơn đặt xe với ID {request.booking_id}",
            )

        if booking.status in ("BOOKED", "COMPLETED"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Đơn đặt xe này đã được xác nhận thanh toán thành công trước đó.",
            )
        elif booking.status == "CANCELLED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Đơn đặt xe đã bị hủy, không thể tạo thanh toán cọc.",
            )

        # B2. Xác định số tiền cọc (VNĐ)
        deposit_amount = request.amount
        if deposit_amount is None:
            deposit_amount = (
                float(booking.deposit_amount)
                if float(booking.deposit_amount) > 0
                else float(booking.total_amount)
            )

        if deposit_amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Số tiền cọc thanh toán phải lớn hơn 0 VNĐ.",
            )

        # B3. Gọi PayOS Service tạo payment link & mã QR động (bất đồng bộ)
        payos_data = await payos_service.create_deposit_payment_link(
            booking_id=booking.id,
            amount=deposit_amount,
            description=request.description,
            return_url=request.return_url,
            cancel_url=request.cancel_url,
        )

        # B4. Lưu bản ghi PaymentTransaction vào MySQL qua SQLAlchemy ở trạng thái PENDING
        order_code = payos_data["order_code"]
        transaction_code = f"PAYOS_{order_code}"

        new_transaction = PaymentTransaction(
            booking_id=booking.id,
            transaction_code=transaction_code,
            provider="PAYOS",
            provider_txn_id=str(payos_data["payment_link_id"]),
            amount=deposit_amount,
            status="PENDING",
            payment_method="QR_CODE",
            qr_code_url=payos_data["qr_code_url"],
        )
        db.add(new_transaction)
        db.commit()
        db.refresh(new_transaction)

        # B5. Trả về thông tin đầy đủ cho Frontend hiển thị QR và chuyển hướng
        return PayOSPaymentResponse(
            transaction_id=new_transaction.id,
            transaction_code=new_transaction.transaction_code,
            order_code=order_code,
            booking_id=booking.id,
            amount=int(deposit_amount),
            status=new_transaction.status,
            checkout_url=payos_data["checkout_url"],
            qr_code=payos_data["qr_code"],
            qr_code_url=payos_data["qr_code_url"],
            payment_link_id=payos_data["payment_link_id"],
            account_number=payos_data.get("account_number"),
            account_name=payos_data.get("account_name"),
            bin=payos_data.get("bin"),
            message="Khởi tạo giao dịch thanh toán cọc và sinh mã QR PayOS thành công.",
        )

    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi hệ thống khi tạo giao dịch PayOS: {str(exc)}",
        )


@router.get(
    "/payos/order/{order_code}",
    summary="Tra cứu thông tin trạng thái đơn hàng từ PayOS (TF19EFA)",
    description="Tra cứu trực tiếp trạng thái link thanh toán từ PayOS và tự động đồng bộ vào CSDL nếu đơn đã thanh toán.",
)
async def get_payos_order_status(
    order_code: int,
    db: Session = Depends(get_db),
):
    try:
        # Gọi SDK tra cứu đơn hàng từ PayOS
        order_info = await payos_service.get_payment_link_information(order_code=order_code)

        # Kiểm tra và đồng bộ trạng thái giao dịch trong CSDL
        transaction_code = f"PAYOS_{order_code}"
        txn = (
            db.query(PaymentTransaction)
            .filter(PaymentTransaction.transaction_code == transaction_code)
            .first()
        )

        status_str = getattr(order_info, "status", None)
        if txn and status_str == "PAID" and txn.status != "SUCCESS":
            txn.status = "SUCCESS"
            txn.paid_at = datetime.now()

            # Khóa lịch xe khi thanh toán thành công
            booking = db.query(Booking).filter(Booking.id == txn.booking_id).first()
            if booking:
                booking.status = "BOOKED"

            db.commit()

        return order_info

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi tra cứu đơn hàng PayOS #{order_code}: {str(exc)}",
        )


# ==============================================================================
# 2. WEBHOOK THANH TOÁN TỪ PAYOS (MÃ TASK: TF1A032)
# ==============================================================================
@router.post(
    "/webhook/payos",
    status_code=status.HTTP_200_OK,
    summary="Tiếp nhận Webhook kết quả thanh toán từ PayOS (TF1A032)",
    description="""
    Endpoint nhận thông báo kết quả thanh toán tự động từ PayOS sau khi người dùng hoàn tất giao dịch.

    **Luồng xử lý (TF1A032):**
    1. **Xác thực chữ ký (Signature Verification):** Dùng PayOS SDK + `PAYOS_CHECKSUM_KEY` để kiểm tra
       tính toàn vẹn và tính xác thực của payload. Từ chối ngay nếu chữ ký sai (HTTP 401).
    2. **Ghi log Webhook:** Mọi request vào endpoint này đều được ghi vào bảng `payment_webhook_logs`
       để kiểm tra/debug sau, dù hợp lệ hay không.
    3. **Idempotency (chống gọi lặp):** Nếu giao dịch đã ở trạng thái `SUCCESS` hoặc `REFUNDED`,
       bỏ qua mà vẫn trả về `200 OK` cho PayOS (tránh PayOS retry vô hạn).
    4. **Cập nhật trạng thái:** Nếu `success=true` và `code='00'`:
       - `PaymentTransaction.status` → **SUCCESS** + ghi `paid_at`.
       - `Booking.status` → **BOOKED** (khóa xe, không cho đặt trùng lịch).
    5. **Trả về HTTP 200** cho PayOS biết đã nhận webhook thành công.

    > **Lưu ý bảo mật:** `PAYOS_CHECKSUM_KEY` chỉ được đọc từ biến môi trường `.env`,
    > không bao giờ hard-code trong code Python.
    """,
    response_description="PayOS yêu cầu trả về HTTP 200 để không retry webhook.",
)
async def process_payos_webhook(
    payload: PayOSWebhookPayload,
    db: Session = Depends(get_db),
):
    """Nhận và xử lý Webhook kết quả thanh toán từ PayOS (TF1A032).

    PayOS gửi POST JSON với cấu trúc:
    ```json
    {
        "code": "00",
        "desc": "success",
        "success": true,
        "data": {
            "orderCode": 26111322150001,
            "amount": 500000,
            "description": "Coc xe don 1",
            "reference": "TXN_REF_ABC123",
            "paymentLinkId": "abc123",
            ...
        },
        "signature": "hmac_sha256_signature_here"
    }
    ```
    """
    # Chuyển Pydantic model -> Dict để truyền vào service (PayOS SDK cần raw dict)
    webhook_body = payload.model_dump()
    return await payos_service.process_payos_webhook(
        webhook_body=webhook_body,
        db=db,
    )



# ==============================================================================
@router.post(
    "/create",
    response_model=PaymentCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Khởi tạo giao dịch đặt cọc & sinh mã QR/URL thanh toán Sandbox (TF19E3D)",
    description="""
    Khởi tạo giao dịch thanh toán ở trạng thái **PENDING** và gọi sang cổng Sandbox
    để sinh `transaction_code` độc lập, `payment_url` và `qr_code_url` động.
    - Đáp ứng: **TF1B039-TC001**, **TF1B039-TC002**, **TF1B039-TC003**.
    """,
)
def create_payment_transaction(
    request: PaymentCreateRequest,
    db: Session = Depends(get_db),
):
    try:
        # B1. Kiểm tra đơn đặt xe (Booking)
        booking = db.query(Booking).filter(Booking.id == request.booking_id).first()
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy đơn đặt xe với ID {request.booking_id}",
            )

        # Kiểm tra xem đơn đặt xe đã hoàn tất thanh toán trước đó chưa
        if booking.status in ("BOOKED", "COMPLETED"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Đơn đặt xe này đã được xác nhận thanh toán thành công trước đó.",
            )

        # B2. Xác định số tiền thanh toán (amount)
        payment_amount = request.amount
        if payment_amount is None:
            payment_amount = float(booking.deposit_amount) if float(booking.deposit_amount) > 0 else float(booking.total_amount)

        # Kiểm tra số tiền hợp lệ > 0 (TF1B039-TC003)
        if payment_amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Số tiền giao dịch phải lớn hơn 0 (TF1B039-TC003).",
            )

        # B3. Gọi Lớp tích hợp cổng thanh toán Sandbox (MockPaymentGatewayService)
        session_data = payment_gateway_service.create_payment_session(
            booking_id=booking.id,
            amount=payment_amount,
            provider=request.provider,
            payment_method=request.payment_method or "QR_CODE",
            order_info=f"Dat coc thue xe don #{booking.id}",
        )

        # B4. Lưu bản ghi PaymentTransaction vào MySQL ở trạng thái PENDING
        new_transaction = PaymentTransaction(
            booking_id=booking.id,
            transaction_code=session_data["transaction_code"],
            provider=request.provider,
            amount=payment_amount,
            status="PENDING",
            payment_method=request.payment_method or "QR_CODE",
            qr_code_url=session_data["qr_code_url"],
        )
        db.add(new_transaction)
        db.commit()
        db.refresh(new_transaction)

        # B5. Trả về thông tin đầy đủ cho Frontend hiển thị QR / Chuyển hướng
        return PaymentCreateResponse(
            transaction_id=new_transaction.id,
            transaction_code=new_transaction.transaction_code,
            booking_id=new_transaction.booking_id,
            amount=float(new_transaction.amount),
            provider=new_transaction.provider,
            payment_method=new_transaction.payment_method,
            status=new_transaction.status,
            payment_url=session_data["payment_url"],
            qr_code_url=new_transaction.qr_code_url,
            expires_at=session_data["expires_at"],
            message="Khởi tạo giao dịch thanh toán cọc thành công.",
        )

    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi hệ thống khi khởi tạo giao dịch thanh toán: {str(exc)}",
        )


# ==============================================================================
# 3. API TIẾP NHẬN WEBHOOK TỪ CỔNG THANH TOÁN (WEBHOOK PROCESSING)
# ==============================================================================
@router.post(
    "/webhook",
    status_code=status.HTTP_200_OK,
    summary="Tiếp nhận Webhook từ Cổng thanh toán (HMAC-SHA256 & Idempotency)",
    description="""
    Tiếp nhận thông báo kết quả giao dịch tự động từ Cổng thanh toán:
    1. Ghi log bản tin vào `payment_webhook_logs`.
    2. Xác thực chữ ký số **HMAC-SHA256** (TF1B039-TC006).
    3. Kiểm tra tính toàn vẹn **Idempotency** chống trùng lặp (TF1B039-TC007).
    4. Cập nhật giao dịch thành **SUCCESS**, đồng thời chuyển trạng thái đơn đặt xe sang **BOOKED** (khóa xe) (TF1B039-TC005).
    5. Xử lý trường hợp **FAILED** (TF1B039-TC008).
    """,
)
def process_payment_webhook(
    payload: PaymentWebhookPayload,
    x_signature: Optional[str] = Header(None, alias="X-Signature"),
    db: Session = Depends(get_db),
):
    # Lấy signature từ payload hoặc Header
    signature_to_verify = payload.signature or x_signature
    raw_payload_dict = payload.model_dump()

    # B1. Xác thực chữ ký bảo mật HMAC-SHA256
    is_signature_valid = payment_gateway_service.verify_webhook_signature(
        payload=raw_payload_dict,
        received_signature=signature_to_verify,
    )

    # Nếu chữ ký KHÔNG hợp lệ -> Từ chối và ghi log bảo mật (TF1B039-TC006)
    if not is_signature_valid:
        error_log = PaymentWebhookLog(
            provider_txn_id=payload.provider_txn_id,
            transaction_code=payload.transaction_code,
            payload=raw_payload_dict,
            signature_valid="INVALID",
            process_result="FAILED",
            queue_reason="Chữ ký bảo mật HMAC-SHA256 không hợp lệ (TF1B039-TC006)",
            processed_at=datetime.now(),
        )
        db.add(error_log)
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Xác thực chữ ký số thất bại! Yêu cầu Webhook không hợp lệ.",
        )

    try:
        # B2. Tra cứu bản ghi Giao dịch trong CSDL theo transaction_code
        transaction = (
            db.query(PaymentTransaction)
            .filter(PaymentTransaction.transaction_code == payload.transaction_code)
            .first()
        )

        if not transaction:
            log_entry = PaymentWebhookLog(
                provider_txn_id=payload.provider_txn_id,
                transaction_code=payload.transaction_code,
                payload=raw_payload_dict,
                signature_valid="VALID",
                process_result="NOT_FOUND",
                queue_reason=f"Không tìm thấy transaction_code: {payload.transaction_code}",
                processed_at=datetime.now(),
            )
            db.add(log_entry)
            db.commit()

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy mã giao dịch {payload.transaction_code}",
            )

        # B3. Cơ chế chống lặp Webhook - Idempotency (TF1B039-TC007)
        if transaction.status in ("SUCCESS", "REFUNDED"):
            idempotent_log = PaymentWebhookLog(
                provider_txn_id=payload.provider_txn_id,
                transaction_code=payload.transaction_code,
                payload=raw_payload_dict,
                signature_valid="VALID",
                process_result="IDEMPOTENT_IGNORED",
                queue_reason="Giao dịch đã được xử lý trước đó. Bỏ qua cập nhật lặp lại (TF1B039-TC007).",
                processed_at=datetime.now(),
            )
            db.add(idempotent_log)
            db.commit()

            return {
                "status": "OK",
                "message": "Giao dịch đã được ghi nhận thành công trước đó (Idempotent success).",
                "transaction_code": transaction.transaction_code,
                "current_status": transaction.status,
            }

        # B4. Kiểm tra tính toàn vẹn số tiền thanh toán
        if abs(float(transaction.amount) - float(payload.amount)) > 0.01:
            mismatch_log = PaymentWebhookLog(
                provider_txn_id=payload.provider_txn_id,
                transaction_code=payload.transaction_code,
                payload=raw_payload_dict,
                signature_valid="VALID",
                process_result="AMOUNT_MISMATCH",
                queue_reason=f"Số tiền không khớp: Hệ thống={transaction.amount}, Webhook={payload.amount}",
                processed_at=datetime.now(),
            )
            db.add(mismatch_log)
            db.commit()

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Số tiền trong Webhook không khớp với số tiền của giao dịch gốc.",
            )

        # B5. Phân nhánh xử lý trạng thái Webhook
        if payload.status == "SUCCESS" and payload.response_code == "00":
            # === Giao dịch thành công (TF1B039-TC005) ===
            transaction.status = "SUCCESS"
            transaction.paid_at = datetime.now()
            transaction.provider_txn_id = payload.provider_txn_id

            # Cập nhật đơn đặt xe sang BOOKED (khóa lịch xe)
            booking = db.query(Booking).filter(Booking.id == transaction.booking_id).first()
            if booking:
                booking.status = "BOOKED"

            # Ghi log thành công
            success_log = PaymentWebhookLog(
                provider_txn_id=payload.provider_txn_id,
                transaction_code=payload.transaction_code,
                payload=raw_payload_dict,
                signature_valid="VALID",
                process_result="SUCCESS",
                queue_reason="Xác thực hợp lệ. Đã cập nhật giao dịch SUCCESS và khóa lịch xe.",
                processed_at=datetime.now(),
            )
            db.add(success_log)
            db.commit()

            return {
                "status": "OK",
                "message": "Xử lý Webhook thành công: Giao dịch SUCCESS, đơn đặt xe đã chuyển sang BOOKED.",
                "transaction_code": transaction.transaction_code,
                "booking_id": transaction.booking_id,
                "booking_status": booking.status if booking else None,
            }

        else:
            # === Giao dịch thất bại / Bị hủy (TF1B039-TC008) ===
            transaction.status = "FAILED"
            transaction.provider_txn_id = payload.provider_txn_id

            fail_log = PaymentWebhookLog(
                provider_txn_id=payload.provider_txn_id,
                transaction_code=payload.transaction_code,
                payload=raw_payload_dict,
                signature_valid="VALID",
                process_result="FAILED",
                queue_reason=payload.message or "Cổng thanh toán báo giao dịch thất bại.",
                processed_at=datetime.now(),
            )
            db.add(fail_log)
            db.commit()

            return {
                "status": "OK",
                "message": "Đã ghi nhận giao dịch thanh toán thất bại (FAILED).",
                "transaction_code": transaction.transaction_code,
                "reason": payload.message,
            }

    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi xử lý dữ liệu Webhook: {str(exc)}",
        )


# ==============================================================================
# 4. API HOÀN TIỀN (REFUND FLOW)
# ==============================================================================
@router.post(
    "/refund",
    response_model=RefundResponse,
    status_code=status.HTTP_200_OK,
    summary="Yêu cầu hoàn tiền giao dịch cọc (Refund)",
    description="""
    Xử lý hoàn tiền cho giao dịch đã thanh toán thành công:
    - Kiểm tra điều kiện: giao dịch phải ở trạng thái **SUCCESS** (TF1B039-TC011).
    - Gọi API hoàn tiền giả lập sang Cổng thanh toán (TF1B039-TC009).
    - Cập nhật giao dịch sang **REFUNDED**, giải phóng xe sang **CANCELLED** và lưu log bảng `refunds` (TF1B039-TC010).
    """,
)
def process_payment_refund(
    request: PaymentRefundRequest,
    db: Session = Depends(get_db),
):
    try:
        # B1. Tìm kiếm giao dịch cần hoàn tiền
        query = db.query(PaymentTransaction)
        if request.transaction_code:
            transaction = query.filter(PaymentTransaction.transaction_code == request.transaction_code).first()
        elif request.booking_id:
            transaction = (
                query.filter(PaymentTransaction.booking_id == request.booking_id)
                .order_by(PaymentTransaction.id.desc())
                .first()
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cần cung cấp ít nhất transaction_code hoặc booking_id để hoàn tiền.",
            )

        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy thông tin giao dịch thanh toán.",
            )

        # B2. Kiểm tra điều kiện hoàn tiền (TF1B039-TC011)
        if transaction.status != "SUCCESS":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Giao dịch không hợp lệ để hoàn tiền (Trạng thái hiện tại: {transaction.status}). "
                       f"Chỉ có thể hoàn tiền cho giao dịch đã SUCCESS (TF1B039-TC011).",
            )

        # Kiểm tra xem giao dịch đã được hoàn trước đó chưa
        existing_refund = (
            db.query(Refund)
            .filter(Refund.payment_transaction_id == transaction.id, Refund.status == "SUCCESS")
            .first()
        )
        if existing_refund:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Giao dịch này đã được hoàn tiền thành công trước đó.",
            )

        # B3. Xác định số tiền hoàn
        refund_amount = request.amount if request.amount is not None else float(transaction.amount)
        if refund_amount <= 0 or refund_amount > float(transaction.amount):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Số tiền hoàn ({refund_amount}) không hợp lệ (Số tiền gốc: {transaction.amount}).",
            )

        # B4. Gọi dịch vụ Mock Gateway để thực hiện hoàn tiền sandbox
        gateway_refund_res = payment_gateway_service.process_refund(
            transaction_code=transaction.transaction_code,
            amount=refund_amount,
            reason=request.reason or "Khách hàng hủy chuyến hợp lệ",
        )

        # B5. Tạo bản ghi Refund trong CSDL
        refund_record = Refund(
            booking_id=transaction.booking_id,
            payment_transaction_id=transaction.id,
            amount=refund_amount,
            reason=request.reason or "Khách hàng hủy lịch hợp lệ",
            status="SUCCESS",
            processed_by=None,
            processed_at=datetime.now(),
        )
        db.add(refund_record)

        # B6. Cập nhật trạng thái giao dịch sang REFUNDED và giải phóng xe
        transaction.status = "REFUNDED"

        booking = db.query(Booking).filter(Booking.id == transaction.booking_id).first()
        if booking:
            booking.status = "CANCELLED"  # Giải phóng xe khi hủy/hoàn tiền

        db.commit()
        db.refresh(refund_record)

        return RefundResponse(
            id=refund_record.id,
            booking_id=refund_record.booking_id,
            payment_transaction_id=refund_record.payment_transaction_id,
            amount=float(refund_record.amount),
            reason=refund_record.reason,
            status=refund_record.status,
            processed_by=refund_record.processed_by,
            processed_at=refund_record.processed_at,
            created_at=refund_record.created_at,
        )

    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi hệ thống khi xử lý hoàn tiền: {str(exc)}",
        )


# ==============================================================================
# 5. API TRA CỨU THÔNG TIN GIAO DỊCH (QUERY APIs)
# ==============================================================================
@router.get(
    "/{transaction_code}",
    response_model=PaymentTransactionResponse,
    summary="Tra cứu chi tiết giao dịch theo mã giao dịch",
)
def get_payment_by_code(
    transaction_code: str,
    db: Session = Depends(get_db),
):
    """Lấy thông tin chi tiết một giao dịch thanh toán để Frontend kiểm tra trạng thái."""
    transaction = (
        db.query(PaymentTransaction)
        .filter(PaymentTransaction.transaction_code == transaction_code)
        .first()
    )
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy giao dịch với mã {transaction_code}",
        )
    return transaction


@router.get(
    "/booking/{booking_id}",
    response_model=List[PaymentTransactionResponse],
    summary="Lấy danh sách các giao dịch của một đơn đặt xe",
)
def get_payments_by_booking(
    booking_id: int,
    db: Session = Depends(get_db),
):
    """Liệt kê toàn bộ lịch sử các giao dịch thanh toán phát sinh từ một đơn đặt xe."""
    transactions = (
        db.query(PaymentTransaction)
        .filter(PaymentTransaction.booking_id == booking_id)
        .order_by(PaymentTransaction.id.desc())
        .all()
    )
    return transactions


# ==============================================================================
# 6. API MÔ PHỎNG TEST NHANH TRÊN SWAGGER UI (SANDBOX SIMULATOR)
# ==============================================================================
@router.post(
    "/simulate",
    summary="[Sandbox Tool] Mô phỏng cổng thanh toán gửi Webhook nhanh",
    description="""
    Công cụ tiện ích cho Developer & QA:
    Tự động sinh chữ ký bảo mật HMAC-SHA256 hợp lệ và kích hoạt luồng Webhook
    ngay lập tức mà không cần phần mềm bên thứ 3 (như Postman hay Ngrok).
    """,
)
def simulate_payment_webhook(
    request: PaymentSimulateRequest,
    db: Session = Depends(get_db),
):
    # 1. Tìm giao dịch
    transaction = (
        db.query(PaymentTransaction)
        .filter(PaymentTransaction.transaction_code == request.transaction_code)
        .first()
    )
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy transaction_code: {request.transaction_code}",
        )

    # 2. Tạo Webhook Payload giả lập có chữ ký HMAC-SHA256 hợp lệ
    mock_payload_dict = payment_gateway_service.create_mock_webhook_payload(
        transaction_code=transaction.transaction_code,
        amount=float(transaction.amount),
        status=request.status.upper(),
        response_code="00" if request.status.upper() == "SUCCESS" else "99",
        message=request.message,
    )

    # 3. Tạo Pydantic model và gọi trực tiếp vào hàm xử lý Webhook
    payload_obj = PaymentWebhookPayload(**mock_payload_dict)
    webhook_result = process_payment_webhook(payload=payload_obj, db=db)

    return {
        "simulator_note": "Mô phỏng Webhook thành công qua Mock Payment Gateway Service.",
        "simulated_payload": mock_payload_dict,
        "webhook_result": webhook_result,
    }
