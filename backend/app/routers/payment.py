"""Router API Xử lý Thanh toán, Webhook & Hoàn tiền (Sandbox/Mock Payment Gateway).

Mã task: TF19E3D
Dự án: RideHub (Hệ thống đặt xe và cho thuê xe trực tuyến)
Các tính năng cốt lõi:
1. POST /api/payments/create: Khởi tạo giao dịch đặt cọc & sinh mã QR / URL thanh toán.
2. POST /api/payments/webhook: Nhận Webhook từ cổng thanh toán, xác thực HMAC-SHA256, kiểm tra Idempotency & khóa lịch xe.
3. POST /api/payments/refund: Xử lý hoàn tiền cho giao dịch thành công & giải phóng lịch xe.
4. GET  /api/payments/{transaction_code}: Tra cứu chi tiết trạng thái giao dịch.
5. GET  /api/payments/booking/{booking_id}: Tra cứu lịch sử thanh toán theo đơn đặt xe.
6. POST /api/payments/simulate: Giả lập cổng thanh toán bắn Webhook trực tiếp từ Swagger UI.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.booking import Booking
from app.models.payment import PaymentTransaction, PaymentWebhookLog, Refund
from app.schemas.payment import (
    PaymentCreateRequest,
    PaymentCreateResponse,
    PaymentRefundRequest,
    PaymentSimulateRequest,
    PaymentTransactionResponse,
    PaymentWebhookPayload,
    RefundResponse,
)
from app.services.payment_gateway import payment_gateway_service

router = APIRouter(
    prefix="/payments",
    tags=["Payments - Thanh toán & Cổng Sandbox (TF19E3D)"],
)


# ==============================================================================
# 1. API KHỞI TẠO GIAO DỊCH THANH TOÁN / ĐẶT CỌC (DEPOSIT)
# ==============================================================================
@router.post(
    "/create",
    response_model=PaymentCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Khởi tạo giao dịch đặt cọc & sinh mã QR/URL thanh toán",
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
        # Nếu client không truyền amount -> lấy deposit_amount hoặc total_amount từ Booking
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
        # Sinh mã transaction_code độc lập, payment_url và qr_code_url
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
# 2. API TIẾP NHẬN WEBHOOK TỪ CỔNG THANH TOÁN (WEBHOOK PROCESSING)
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
        # Nếu giao dịch đã hoàn tất (SUCCESS) hoặc đã hoàn tiền (REFUNDED)
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
# 3. API HOÀN TIỀN (REFUND FLOW)
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
# 4. API TRA CỨU THÔNG TIN GIAO DỊCH (QUERY APIs)
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
# 5. API MÔ PHỎNG TEST NHANH TRÊN SWAGGER UI (SANDBOX SIMULATOR)
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

