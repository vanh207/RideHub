"""Kịch bản kiểm thử Tự động cho Lớp tích hợp cổng thanh toán Sandbox (TF19E3D).

Dự án: RideHub
Chạy kiểm thử:
    cd RideHub/backend
    python tests/test_payment_gateway.py
"""
import sys
import os
from datetime import datetime, timedelta

# Bổ sung đường dẫn gốc app vào sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.models.booking import Booking
from app.models.payment import PaymentTransaction, Refund, PaymentWebhookLog
from app.schemas.payment import (
    PaymentCreateRequest,
    PaymentWebhookPayload,
    PaymentRefundRequest,
    PaymentSimulateRequest,
)
from app.services.payment_gateway import payment_gateway_service
from app.routers.payment import (
    create_payment_transaction,
    process_payment_webhook,
    process_payment_refund,
    get_payment_by_code,
    get_payments_by_booking,
    simulate_payment_webhook,
)


def run_all_tests():
    print("================================================================")
    print(" BẮT ĐẦU CHẠY KIỂM THỬ TOÀN DIỆN TASK [TF19E3D] - RIDEHUB PAYMENT")
    print("================================================================")

    # Khởi tạo SQLite In-memory để test độc lập không phụ thuộc DB ngoài
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSession()

    # 1. Tạo đơn đặt xe mẫu (Booking Seed)
    booking = Booking(
        id=1,
        customer_id=10,
        vehicle_id=20,
        start_time=datetime.now(),
        end_time=datetime.now() + timedelta(days=2),
        status="PENDING",
        rental_amount=500000.0,
        delivery_fee=0.0,
        deposit_amount=200000.0,
        total_amount=500000.0,
    )
    db.add(booking)
    db.commit()

    # TEST CASE 1: Khởi tạo giao dịch cọc (TF1B039-TC001, TC002)
    req1 = PaymentCreateRequest(
        booking_id=1,
        amount=200000.0,
        provider="MOCK_PAY",
        payment_method="QR_CODE",
    )
    resp1 = create_payment_transaction(request=req1, db=db)
    assert resp1.status == "PENDING"
    assert resp1.payment_url.startswith("https://sandbox.ridehub.vn")
    assert "qrserver.com" in resp1.qr_code_url
    txn_code = resp1.transaction_code
    print(f"[PASSED] TC001 & TC002: Khởi tạo giao dịch thành công. Mã: {txn_code}")

    # TEST CASE 2: Kiểm tra số tiền <= 0 bị từ chối (TF1B039-TC003)
    from pydantic import ValidationError
    try:
        invalid_req = PaymentCreateRequest(booking_id=1, amount=-50000.0)
        create_payment_transaction(request=invalid_req, db=db)
        assert False, "Cần chặn số tiền <= 0"
    except (HTTPException, ValidationError) as exc:
        print("[PASSED] TC003: Chặn số tiền cọc không hợp lệ thành công (Validation Error).")

    # TEST CASE 3: Từ chối Webhook khi Signature sai (TF1B039-TC006)
    invalid_payload = PaymentWebhookPayload(
        transaction_code=txn_code,
        provider_txn_id="PROVIDER_TXN_001",
        amount=200000.0,
        status="SUCCESS",
        response_code="00",
        signature="sai_chu_ky_bao_mat_fake_hash",
    )
    try:
        process_payment_webhook(payload=invalid_payload, db=db)
        assert False, "Cần trả về 401 khi chữ ký sai"
    except HTTPException as exc:
        assert exc.status_code == 401
        print("[PASSED] TC006: Từ chối Webhook khi chữ ký HMAC sai (HTTP 401).")

    # TEST CASE 4: Xử lý Webhook thành công hợp lệ (TF1B039-TC005)
    valid_dict = payment_gateway_service.create_mock_webhook_payload(
        transaction_code=txn_code,
        amount=200000.0,
        status="SUCCESS",
        response_code="00",
    )
    valid_payload = PaymentWebhookPayload(**valid_dict)
    res_webhook = process_payment_webhook(payload=valid_payload, db=db)
    assert res_webhook["status"] == "OK"

    db.expire_all()
    txn_db = db.query(PaymentTransaction).filter(PaymentTransaction.transaction_code == txn_code).first()
    booking_db = db.query(Booking).filter(Booking.id == 1).first()
    assert txn_db.status == "SUCCESS"
    assert booking_db.status == "BOOKED"
    print("[PASSED] TC005: Xử lý Webhook thành công -> Giao dịch SUCCESS, Booking BOOKED (khóa xe).")

    # TEST CASE 5: Kiểm tra chống lặp Idempotency (TF1B039-TC007)
    res_repeat = process_payment_webhook(payload=valid_payload, db=db)
    assert res_repeat["status"] == "OK"
    assert "Idempotent" in res_repeat["message"]
    print("[PASSED] TC007: Cơ chế Idempotency hoạt động chuẩn (bỏ qua xử lý lặp lại).")

    # TEST CASE 6: Xử lý Hoàn tiền khi đã SUCCESS (TF1B039-TC009, TC010)
    ref_req = PaymentRefundRequest(transaction_code=txn_code, reason="Khách hủy chuyến hợp lệ")
    ref_resp = process_payment_refund(request=ref_req, db=db)
    assert ref_resp.status == "SUCCESS"

    db.expire_all()
    assert txn_db.status == "REFUNDED"
    assert booking_db.status == "CANCELLED"
    print("[PASSED] TC009 & TC010: Hoàn tiền thành công -> Giao dịch REFUNDED, Booking CANCELLED (giải phóng xe).")

    # TEST CASE 7: Từ chối hoàn tiền khi giao dịch không hợp lệ (TF1B039-TC011)
    try:
        process_payment_refund(request=ref_req, db=db)
        assert False, "Cần chặn hoàn tiền lần 2"
    except HTTPException as exc:
        assert exc.status_code == 400
        print("[PASSED] TC011: Chặn hoàn tiền lặp lại hoặc giao dịch không hợp lệ (HTTP 400).")

    # TEST CASE 8: Công cụ giả lập trên Swagger UI (Simulate API)
    booking2 = Booking(
        id=2, customer_id=15, vehicle_id=25,
        start_time=datetime.now(), end_time=datetime.now() + timedelta(days=1),
        status="PENDING", rental_amount=300000.0, deposit_amount=100000.0, total_amount=300000.0
    )
    db.add(booking2)
    db.commit()

    txn2 = create_payment_transaction(request=PaymentCreateRequest(booking_id=2, amount=100000.0), db=db)
    sim_res = simulate_payment_webhook(
        request=PaymentSimulateRequest(transaction_code=txn2.transaction_code, status="SUCCESS"),
        db=db,
    )
    assert sim_res["webhook_result"]["status"] == "OK"
    print("[PASSED] Simulator Tool: Giả lập Webhook trên Swagger UI hoạt động hoàn hảo.")

    print("\n================================================================")
    print(" >>> CHÚC MỪNG: TOÀN BỘ CÁC TEST CASES ĐỀU ĐẠT CHUẨN 100%! <<<")
    print("================================================================")


if __name__ == "__main__":
    run_all_tests()
