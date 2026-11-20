"""Kiểm thử đồng thời cho hủy đơn/expiry job. BẮT BUỘC dùng MySQL thật.

    cd backend
    TEST_DATABASE_URL='mysql+pymysql://root:password@127.0.0.1:3306/ridehub_cancel_test?charset=utf8mb4' \
      python3 tests/booking_cancellation_concurrency_check.py

Script tự seed dữ liệu test và xóa dữ liệu đó sau khi chạy. Không in mật khẩu DB.
"""
from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app import models  # noqa: F401
from app.crud.booking_cancellation import BookingActor, cancel_booking, expire_hold_bookings
from app.db.session import Base
from app.models.booking import Booking
from app.models.payment import PaymentTransaction, Refund
from app.models.store import Store
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.vehicle_reservation import VehicleReservation
from app.models.vehicle_schedule import VehicleSchedule
from app.services.payment_booking_reconciliation import apply_successful_payment_to_booking

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL_TEST")
if not TEST_DATABASE_URL:
    print(
        "SKIP: chưa đặt TEST_DATABASE_URL. Cần MySQL thật để test FOR UPDATE.\n"
        "Ví dụ:\n"
        "  TEST_DATABASE_URL='mysql+pymysql://root:password@127.0.0.1:3306/"
        "ridehub_cancel_test?charset=utf8mb4' \\\n"
        "    python3 tests/booking_cancellation_concurrency_check.py"
    )
    sys.exit(2)

if not TEST_DATABASE_URL.startswith("mysql"):
    print("FAIL: TEST_DATABASE_URL phải là MySQL, không dùng SQLite.")
    sys.exit(2)

NOW = datetime(2026, 3, 1, 9, 0, 0)
IDS = {
    "customer": 91001,
    "store": 91001,
    "vehicle": 91001,
    "booking_a": 91001,
    "booking_b": 91002,
    "booking_c": 91003,
}

engine = create_engine(TEST_DATABASE_URL, poolclass=NullPool, pool_pre_ping=True)
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)
Base.metadata.create_all(bind=engine)


def cleanup(db):
    booking_ids = [IDS["booking_a"], IDS["booking_b"], IDS["booking_c"]]
    db.execute(delete(Refund).where(Refund.booking_id.in_(booking_ids)))
    db.execute(delete(PaymentTransaction).where(PaymentTransaction.booking_id.in_(booking_ids)))
    db.execute(delete(VehicleSchedule).where(VehicleSchedule.booking_id.in_(booking_ids)))
    db.execute(delete(VehicleReservation).where(VehicleReservation.booking_id.in_(booking_ids)))
    db.execute(delete(Booking).where(Booking.id.in_(booking_ids)))
    db.execute(delete(Vehicle).where(Vehicle.id == IDS["vehicle"]))
    db.execute(delete(Store).where(Store.id == IDS["store"]))
    db.execute(delete(User).where(User.id == IDS["customer"]))
    db.commit()


def seed(db):
    cleanup(db)

    db.add(User(id=IDS["customer"], email="cancel-test@ridehub.local", full_name="Cancel Test"))
    db.flush()
    db.add(
        Store(
            id=IDS["store"],
            owner_user_id=IDS["customer"],
            name="Cancel Test Store",
            address="HCM",
            city="HCM",
            status="APPROVED",
            business_license="CANCEL-TEST-001",
        )
    )
    db.flush()
    db.add(
        Vehicle(
            id=IDS["vehicle"],
            store_id=IDS["store"],
            vehicle_type="CAR",
            plate_number="59A-CANCEL",
            brand="Toyota",
            model="Vios",
            price_per_day=Decimal("1000000"),
        )
    )
    db.flush()

    start = NOW + timedelta(hours=72)
    end = start + timedelta(hours=4)

    def add_booking(booking_id, status, hold_delta, txn_status):
        booking = Booking(
            id=booking_id,
            customer_id=IDS["customer"],
            vehicle_id=IDS["vehicle"],
            store_id=IDS["store"],
            start_time=start,
            end_time=end,
            hold_expires_at=NOW + hold_delta,
            status=status,
            rental_amount=Decimal("1000000"),
            deposit_amount=Decimal("1500000"),
            total_amount=Decimal("1500000"),
        )
        db.add(booking)
        db.flush()
        db.add(
            VehicleReservation(
                vehicle_id=IDS["vehicle"],
                customer_id=IDS["customer"],
                booking_id=booking_id,
                start_time=start,
                end_time=end,
                expires_at=NOW + hold_delta,
                status="ACTIVE",
            )
        )
        db.add(
            VehicleSchedule(
                vehicle_id=IDS["vehicle"],
                booking_id=booking_id,
                schedule_type="RENTAL",
                start_time=start,
                end_time=end,
                status="ACTIVE",
            )
        )
        db.add(
            PaymentTransaction(
                booking_id=booking_id,
                transaction_code=f"CANCEL-TEST-{booking_id}",
                provider="MOCK",
                amount=Decimal("1500000"),
                status=txn_status,
            )
        )

    add_booking(IDS["booking_a"], "DEPOSIT_PAID", timedelta(hours=1), "SUCCESS")
    add_booking(IDS["booking_b"], "PENDING_PAYMENT", timedelta(minutes=-1), "PENDING")
    add_booking(IDS["booking_c"], "PENDING_PAYMENT", timedelta(minutes=-1), "SUCCESS")
    db.commit()


def check_double_cancel():
    def worker():
        with SessionLocal() as db:
            cancel_booking(
                db,
                IDS["booking_a"],
                actor=BookingActor(id=IDS["customer"], role="customer"),
                reason="Concurrency test",
                now=NOW,
            )
            return True

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(lambda _: worker(), range(2)))

    with SessionLocal() as db:
        status = db.scalar(select(Booking.status).where(Booking.id == IDS["booking_a"]))
        refund_count = db.scalar(
            select(func.count()).select_from(Refund).where(Refund.booking_id == IDS["booking_a"])
        )
    assert status == "CANCELLED", f"booking_a status={status}"
    assert refund_count == 1, f"expected 1 refund, got {refund_count}"
    print("PASS: double-cancel chỉ tạo đúng 1 refund.")


def check_double_expiry():
    def worker():
        with SessionLocal() as db:
            result = expire_hold_bookings(db, now=NOW)
            return result.expired

    with ThreadPoolExecutor(max_workers=2) as executor:
        expired_counts = list(executor.map(lambda _: worker(), range(2)))

    assert sum(expired_counts) == 1, f"expired_counts={expired_counts}"
    with SessionLocal() as db:
        status = db.scalar(select(Booking.status).where(Booking.id == IDS["booking_b"]))
    assert status == "EXPIRED", f"booking_b status={status}"
    print("PASS: expiry job chạy đồng thời chỉ hủy 1 lần.")


def check_paid_after_hold_expired():
    with SessionLocal() as db:
        result = expire_hold_bookings(db, now=NOW)
        assert result.paid_race == 1, f"paid_race={result.paid_race}"
        status = db.scalar(select(Booking.status).where(Booking.id == IDS["booking_c"]))
    assert status == "DEPOSIT_PAID", f"booking_c status={status}"
    print("PASS: đơn có thanh toán trước khi job chạy không bị hủy.")


def check_payment_after_cancel():
    with SessionLocal() as db:
        transaction = PaymentTransaction(
            booking_id=IDS["booking_a"],
            transaction_code="CANCEL-TEST-LATE",
            provider="MOCK",
            amount=Decimal("1500000"),
            status="SUCCESS",
        )
        db.add(transaction)
        db.flush()
        booking = db.get(Booking, IDS["booking_a"])
        outcome = apply_successful_payment_to_booking(db, booking, transaction)
        db.commit()

    assert outcome == "REFUND_REQUIRED"
    with SessionLocal() as db:
        status = db.scalar(select(Booking.status).where(Booking.id == IDS["booking_a"]))
        pending_refunds = db.scalar(
            select(func.count())
            .select_from(Refund)
            .where(
                Refund.booking_id == IDS["booking_a"],
                Refund.status == "PENDING",
            )
        )
    assert status == "CANCELLED", f"status={status}"
    assert pending_refunds >= 1, f"pending_refunds={pending_refunds}"
    print("PASS: thanh toán sau hủy tạo refund PENDING, không mở lại đơn.")


def main():
    seed(SessionLocal())
    try:
        check_double_cancel()
        check_double_expiry()
        check_paid_after_hold_expired()
        check_payment_after_cancel()
    finally:
        cleanup(SessionLocal())
        engine.dispose()
    print("ALL CANCELLATION CONCURRENCY CHECKS PASSED")


if __name__ == "__main__":
    main()
