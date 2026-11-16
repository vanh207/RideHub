"""Kịch bản kiểm thử Tự động cho Tích hợp Cổng thanh toán PayOS (TF19EFA).

Dự án: RideHub
Chạy kiểm thử:
    cd RideHub/backend
    python tests/test_payos.py
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta

# Bổ sung đường dẫn gốc app vào sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.models.booking import Booking
from app.models.payment import PaymentTransaction
from app.schemas.payment import PayOSPaymentCreateRequest
from app.services.payos_service import payos_service
from app.routers.payment import create_payos_deposit_payment, get_payos_order_status


async def run_payos_tests():
    print("================================================================")
    print(" BẮT ĐẦU KIỂM THỬ TÍCH HỢP PAYOS - THANH TOÁN CỌC (TF19EFA)")
    print("================================================================")

    # 1. Test sinh mã đơn hàng orderCode số nguyên an toàn
    order_code = payos_service.generate_order_code(booking_id=15)
    assert isinstance(order_code, int), "orderCode phải là số nguyên int"
    assert order_code < 9007199254740991, "orderCode phải nằm trong giới hạn int53"
    print(f"[PASSED] 1. Sinh orderCode an toàn: {order_code}")

    # 2. Test chuẩn hóa nội dung VietQR (không dấu, <= 25 ký tự)
    clean_desc = payos_service.clean_description("Đặt cọc xe VinFast VF8 đơn #1234")
    assert len(clean_desc) <= 25, "Nội dung VietQR phải <= 25 ký tự"
    assert "đ" not in clean_desc and "Đ" not in clean_desc
    print(f"[PASSED] 2. Chuẩn hóa nội dung VietQR: '{clean_desc}' (độ dài={len(clean_desc)})")

    # 3. Khởi tạo SQLite in-memory để test lưu trữ DB
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSession = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSession()

    # Seed Booking mẫu
    booking = Booking(
        id=88,
        customer_id=1,
        vehicle_id=5,
        start_time=datetime.now(),
        end_time=datetime.now() + timedelta(days=2),
        status="PENDING",
        rental_amount=1200000.0,
        deposit_amount=50000.0,
        total_amount=1200000.0,
    )
    db.add(booking)
    db.commit()

    # 4. Test gọi router API tạo link cọc và mã QR động qua PayOS
    req = PayOSPaymentCreateRequest(
        booking_id=88,
        amount=50000.0,
        description="Coc xe #88",
        return_url="http://localhost:3000/payment/success",
        cancel_url="http://localhost:3000/payment/cancel",
    )
    print("Đang gửi yêu cầu tạo link cọc sang PayOS API...")
    res = await create_payos_deposit_payment(request=req, db=db)

    print("[PASSED] 3. Phản hồi thành công từ PayOS:")
    print(f"   - Mã đơn hàng PayOS (order_code): {res.order_code}")
    print(f"   - Mã giao dịch RideHub: {res.transaction_code}")
    print(f"   - Link thanh toán (checkout_url): {res.checkout_url}")
    print(f"   - Chuỗi VietQR (qr_code): {res.qr_code[:35]}...")
    print(f"   - Link ảnh QR động (qr_code_url): {res.qr_code_url[:45]}...")
    print(f"   - Trạng thái: {res.status}")

    # 5. Kiểm tra dữ liệu được lưu trong bảng payment_transactions
    txn = db.query(PaymentTransaction).filter(PaymentTransaction.transaction_code == res.transaction_code).first()
    assert txn is not None, "Giao dịch phải được lưu vào CSDL"
    assert txn.provider == "PAYOS"
    assert txn.status == "PENDING"
    assert float(txn.amount) == 50000.0
    print("[PASSED] 4. Đã lưu bản ghi PaymentTransaction vào CSDL với trạng thái PENDING!")

    # 6. Test tra cứu trạng thái đơn hàng từ PayOS
    order_status = await get_payos_order_status(order_code=res.order_code, db=db)
    assert order_status is not None
    print(f"[PASSED] 5. Tra cứu đơn hàng PayOS #{res.order_code} thành công: status={order_status.status}")

    print("\n================================================================")
    print(" >>> CHÚC MỪNG: TOÀN BỘ CÁC TEST CASES PAYOS ĐẠT 100%! <<<")
    print("================================================================")


if __name__ == "__main__":
    asyncio.run(run_payos_tests())

