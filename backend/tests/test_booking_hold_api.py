"""Test tuần tự cho API POST /api/bookings (TF197DE).

Các test này dùng SQLite in-memory để kiểm tra validation, tính tiền, transaction
và các nhánh lỗi. SQLite bỏ qua ``SELECT ... FOR UPDATE`` nên test đồng thời
thật nằm ở ``tests/booking_hold_concurrency_check.py`` và phải chạy với MySQL.

Chạy:
    cd backend
    pytest tests/test_booking_hold_api.py -q
"""
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401 - đăng ký toàn bộ model với metadata
from app.db.session import Base, get_db
from app.models.booking import Booking
from app.models.delivery import DeliveryPoint
from app.models.store import Store
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.vehicle_reservation import VehicleReservation
from app.models.vehicle_schedule import VehicleSchedule
from app.routers.bookings import router as bookings_router

URL = "/api/bookings"


def _now() -> datetime:
    return datetime.now().replace(microsecond=0)


def _seed_base(db):
    now = _now()
    db.add_all(
        [
            User(id=8201, phone="0900008201", full_name="Chủ cửa hàng"),
            User(id=8202, phone="0900008202", full_name="Khách hàng"),
            User(id=8203, phone="0900008203", full_name="Khách hàng khác"),
            Store(
                id=8201,
                owner_user_id=8201,
                name="Test Store Approved",
                address="122 Hoàng Quốc Việt",
                city="Hà Nội",
                business_license="GP-8201",
                status="APPROVED",
            ),
            Store(
                id=8202,
                owner_user_id=8201,
                name="Test Store Pending",
                address="1 Nguyễn Huệ",
                city="TP.HCM",
                business_license="GP-8202",
                status="PENDING",
            ),
            Store(
                id=8203,
                owner_user_id=8201,
                name="Test Store Other",
                address="1 Bạch Đằng",
                city="Đà Nẵng",
                business_license="GP-8203",
                status="APPROVED",
            ),
            Vehicle(
                id=8301,
                store_id=8201,
                vehicle_type="MOTORBIKE",
                plate_number="TEST-8301",
                brand="Honda",
                model="Vision",
                price_per_day=Decimal("150000"),
                price_per_hour=Decimal("25000"),
                current_status="MAINTENANCE",
                is_active=True,
            ),
            Vehicle(
                id=8302,
                store_id=8202,
                vehicle_type="MOTORBIKE",
                plate_number="TEST-8302",
                brand="Honda",
                model="Wave",
                price_per_day=Decimal("150000"),
                price_per_hour=Decimal("25000"),
                current_status="MAINTENANCE",
                is_active=True,
            ),
            Vehicle(
                id=8303,
                store_id=8201,
                vehicle_type="MOTORBIKE",
                plate_number="TEST-8303",
                brand="Honda",
                model="Future",
                price_per_day=Decimal("100000"),
                price_per_hour=None,
                current_status="MAINTENANCE",
                is_active=False,
            ),
            Vehicle(
                id=8304,
                store_id=8203,
                vehicle_type="MOTORBIKE",
                plate_number="TEST-8304",
                brand="Yamaha",
                model="Exciter",
                price_per_day=Decimal("200000"),
                price_per_hour=Decimal("30000"),
                current_status="MAINTENANCE",
                is_active=True,
            ),
            Vehicle(
                id=8305,
                store_id=8201,
                vehicle_type="MOTORBIKE",
                plate_number="TEST-8305",
                brand="Honda",
                model="Air Blade",
                price_per_day=Decimal("120000"),
                price_per_hour=Decimal("20000"),
                current_status="MAINTENANCE",
                is_active=True,
            ),
            DeliveryPoint(
                id=8401,
                store_id=8201,
                name="Điểm giao hợp lệ",
                address="Bến xe Mỹ Đình",
                area="Quận Cầu Giấy",
                delivery_fee=Decimal("50000"),
                is_active=True,
            ),
            DeliveryPoint(
                id=8402,
                store_id=8201,
                name="Điểm giao ẩn",
                address="Không dùng",
                area="Quận X",
                delivery_fee=Decimal("30000"),
                is_active=False,
            ),
            DeliveryPoint(
                id=8403,
                store_id=8203,
                name="Điểm giao cửa hàng khác",
                address="Bạch Đằng",
                area="Quận Hải Châu",
                delivery_fee=Decimal("40000"),
                is_active=True,
            ),
            Booking(
                id=8501,
                customer_id=8203,
                vehicle_id=8301,
                store_id=8201,
                start_time=now + timedelta(days=1),
                end_time=now + timedelta(days=2),
                status="CONFIRMED",
                rental_amount=Decimal("300000"),
                delivery_fee=Decimal("0"),
                deposit_amount=Decimal("200000"),
                total_amount=Decimal("300000"),
            ),
            Booking(
                id=8502,
                customer_id=8203,
                vehicle_id=8301,
                store_id=8201,
                start_time=now + timedelta(days=11),
                end_time=now + timedelta(days=12),
                status="CANCELLED",
                rental_amount=Decimal("300000"),
                delivery_fee=Decimal("0"),
                deposit_amount=Decimal("200000"),
                total_amount=Decimal("300000"),
            ),
            VehicleReservation(
                id=8601,
                vehicle_id=8301,
                customer_id=8203,
                start_time=now + timedelta(days=3),
                end_time=now + timedelta(days=4),
                expires_at=now + timedelta(minutes=30),
                status="ACTIVE",
            ),
            VehicleReservation(
                id=8602,
                vehicle_id=8301,
                customer_id=8203,
                start_time=now + timedelta(days=5),
                end_time=now + timedelta(days=6),
                expires_at=now - timedelta(minutes=1),
                status="ACTIVE",
            ),
            VehicleSchedule(
                id=8701,
                vehicle_id=8305,
                schedule_type="MAINTENANCE",
                start_time=now + timedelta(days=7),
                end_time=now + timedelta(days=8),
                status="ACTIVE",
                note="Bảo dưỡng định kỳ",
            ),
            VehicleSchedule(
                id=8702,
                vehicle_id=8301,
                schedule_type="RENTAL",
                start_time=now + timedelta(days=9),
                end_time=now + timedelta(days=10),
                status="ACTIVE",
                note="Lịch chặn",
            ),
        ]
    )
    db.commit()


@pytest.fixture()
def client_and_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(
        bind=engine, autoflush=False, autocommit=False
    )
    Base.metadata.create_all(bind=engine)

    db = testing_session()
    _seed_base(db)
    db.close()

    app = FastAPI()
    app.include_router(bookings_router, prefix="/api")

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client, testing_session


def _payload(
    *,
    start: datetime,
    end: datetime,
    vehicle_id: int = 8301,
    customer_id: int = 8202,
    delivery_point_id: int | None = None,
    **extra,
):
    data = {
        "customer_id": customer_id,
        "vehicle_id": vehicle_id,
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "delivery_point_id": delivery_point_id,
    }
    data.update(extra)
    return data


def _counts(session_factory, vehicle_id, start, end):
    with session_factory() as db:
        booking_count = db.scalar(
            select(func.count())
            .select_from(Booking)
            .where(
                Booking.vehicle_id == vehicle_id,
                Booking.status == "PENDING_PAYMENT",
                Booking.start_time == start,
                Booking.end_time == end,
            )
        )
        reservation_count = db.scalar(
            select(func.count())
            .select_from(VehicleReservation)
            .where(
                VehicleReservation.vehicle_id == vehicle_id,
                VehicleReservation.start_time == start,
                VehicleReservation.end_time == end,
            )
        )
        schedule_count = db.scalar(
            select(func.count())
            .select_from(VehicleSchedule)
            .where(
                VehicleSchedule.vehicle_id == vehicle_id,
                VehicleSchedule.start_time == start,
                VehicleSchedule.end_time == end,
            )
        )
    return booking_count or 0, reservation_count or 0, schedule_count or 0


def test_create_booking_hold_success_and_amounts(client_and_session):
    client, session_factory = client_and_session
    start = _now() + timedelta(days=20)
    end = start + timedelta(days=2)

    response = client.post(
        URL,
        json=_payload(
            start=start,
            end=end,
            delivery_point_id=8401,
            customer_id=8202,
            # Client gửi tiền sai vẫn phải bị bỏ qua.
            rental_amount=1,
            total_amount=1,
        ),
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "PENDING_PAYMENT"
    assert body["booking_code"] is None
    assert body["store_id"] == 8201
    assert body["rental_amount"] == pytest.approx(300000.0)
    assert body["delivery_fee"] == pytest.approx(50000.0)
    assert body["deposit_amount"] == pytest.approx(200000.0)
    assert body["total_amount"] == pytest.approx(350000.0)
    assert body["reservation_id"] > 0

    hold_expires_at = datetime.fromisoformat(body["hold_expires_at"])
    assert _now() + timedelta(minutes=29) <= hold_expires_at
    assert hold_expires_at <= _now() + timedelta(minutes=31)

    with session_factory() as db:
        booking = db.get(Booking, body["id"])
        reservation = db.get(VehicleReservation, body["reservation_id"])
        schedule = db.scalar(
            select(VehicleSchedule).where(
                VehicleSchedule.booking_id == booking.id
            )
        )

    assert booking is not None
    assert booking.customer_id == 8202
    assert booking.vehicle_id == 8301
    assert booking.store_id == 8201
    assert booking.delivery_point_id == 8401
    assert booking.status == "PENDING_PAYMENT"
    assert reservation is not None
    assert reservation.booking_id == booking.id
    assert reservation.expires_at == booking.hold_expires_at
    assert reservation.status == "ACTIVE"
    assert schedule is not None
    assert schedule.reservation_id == reservation.id
    assert schedule.schedule_type == "RENTAL"
    assert schedule.status == "ACTIVE"


def test_rejects_duration_under_4_hours(client_and_session):
    client, _ = client_and_session
    start = _now() + timedelta(days=20)
    response = client.post(
        URL,
        json=_payload(start=start, end=start + timedelta(hours=3)),
    )
    assert response.status_code == 422
    assert "tối thiểu" in response.json()["detail"]


def test_rejects_duration_over_30_days(client_and_session):
    client, _ = client_and_session
    start = _now() + timedelta(days=20)
    response = client.post(
        URL,
        json=_payload(start=start, end=start + timedelta(days=31)),
    )
    assert response.status_code == 422
    assert "tối đa" in response.json()["detail"]


def test_pending_store_returns_404(client_and_session):
    client, _ = client_and_session
    start = _now() + timedelta(days=20)
    response = client.post(
        URL,
        json=_payload(
            start=start,
            end=start + timedelta(days=2),
            vehicle_id=8302,
        ),
    )
    assert response.status_code == 404
    assert "phương tiện" in response.json()["detail"]


def test_inactive_vehicle_returns_404(client_and_session):
    client, _ = client_and_session
    start = _now() + timedelta(days=20)
    response = client.post(
        URL,
        json=_payload(
            start=start,
            end=start + timedelta(days=2),
            vehicle_id=8303,
        ),
    )
    assert response.status_code == 404


def test_unknown_vehicle_returns_404(client_and_session):
    client, _ = client_and_session
    start = _now() + timedelta(days=20)
    response = client.post(
        URL,
        json=_payload(
            start=start,
            end=start + timedelta(days=2),
            vehicle_id=9999,
        ),
    )
    assert response.status_code == 404


def test_delivery_point_wrong_store_returns_422(client_and_session):
    client, _ = client_and_session
    start = _now() + timedelta(days=20)
    response = client.post(
        URL,
        json=_payload(
            start=start,
            end=start + timedelta(days=2),
            delivery_point_id=8403,
        ),
    )
    assert response.status_code == 422
    assert "Điểm giao" in response.json()["detail"]


def test_inactive_delivery_point_returns_422(client_and_session):
    client, _ = client_and_session
    start = _now() + timedelta(days=20)
    response = client.post(
        URL,
        json=_payload(
            start=start,
            end=start + timedelta(days=2),
            delivery_point_id=8402,
        ),
    )
    assert response.status_code == 422


def test_unknown_customer_returns_422(client_and_session):
    client, _ = client_and_session
    start = _now() + timedelta(days=20)
    response = client.post(
        URL,
        json=_payload(
            start=start,
            end=start + timedelta(days=2),
            customer_id=9999,
        ),
    )
    assert response.status_code == 422
    assert "customer_id" in response.json()["detail"]


def test_overlapping_confirmed_booking_returns_409(client_and_session):
    client, session_factory = client_and_session
    start = _now() + timedelta(days=1, hours=1)
    end = start + timedelta(hours=4)
    response = client.post(URL, json=_payload(start=start, end=end))
    assert response.status_code == 409
    assert "đã có lịch" in response.json()["detail"]
    assert _counts(session_factory, 8301, start, end) == (0, 0, 0)


def test_cancelled_booking_does_not_block(client_and_session):
    client, _ = client_and_session
    start = _now() + timedelta(days=11, hours=1)
    end = start + timedelta(hours=4)
    response = client.post(URL, json=_payload(start=start, end=end))
    assert response.status_code == 201, response.text


def test_active_reservation_blocks(client_and_session):
    client, _ = client_and_session
    start = _now() + timedelta(days=3, hours=1)
    end = start + timedelta(hours=4)
    response = client.post(URL, json=_payload(start=start, end=end))
    assert response.status_code == 409


def test_expired_reservation_does_not_block(client_and_session):
    client, _ = client_and_session
    start = _now() + timedelta(days=5, hours=1)
    end = start + timedelta(hours=4)
    response = client.post(URL, json=_payload(start=start, end=end))
    assert response.status_code == 201, response.text


def test_maintenance_schedule_blocks(client_and_session):
    client, _ = client_and_session
    start = _now() + timedelta(days=7, hours=1)
    end = start + timedelta(hours=4)
    response = client.post(
        URL,
        json=_payload(start=start, end=end, vehicle_id=8305),
    )
    assert response.status_code == 409


def test_rental_schedule_blocks(client_and_session):
    client, _ = client_and_session
    start = _now() + timedelta(days=9, hours=1)
    end = start + timedelta(hours=4)
    response = client.post(URL, json=_payload(start=start, end=end))
    assert response.status_code == 409


def test_60_minute_buffer_allows_next_booking(client_and_session):
    client, _ = client_and_session
    first_start = _now() + timedelta(days=20)
    first_end = first_start + timedelta(days=2)
    first = client.post(
        URL, json=_payload(start=first_start, end=first_end)
    )
    assert first.status_code == 201, first.text

    second_start = first_end + timedelta(minutes=60)
    second = client.post(
        URL,
        json=_payload(
            start=second_start,
            end=second_start + timedelta(hours=4),
        ),
    )
    assert second.status_code == 201, second.text


def test_59_minute_buffer_blocks_next_booking(client_and_session):
    client, _ = client_and_session
    first_start = _now() + timedelta(days=20)
    first_end = first_start + timedelta(days=2)
    first = client.post(
        URL, json=_payload(start=first_start, end=first_end)
    )
    assert first.status_code == 201, first.text

    second_start = first_end + timedelta(minutes=59)
    second = client.post(
        URL,
        json=_payload(
            start=second_start,
            end=second_start + timedelta(hours=4),
        ),
    )
    assert second.status_code == 409


def test_same_time_second_request_conflicts(client_and_session):
    client, session_factory = client_and_session
    start = _now() + timedelta(days=20)
    end = start + timedelta(days=2)

    first = client.post(URL, json=_payload(start=start, end=end))
    second = client.post(URL, json=_payload(start=start, end=end))

    assert first.status_code == 201, first.text
    assert second.status_code == 409
    assert _counts(session_factory, 8301, start, end) == (1, 1, 1)
