"""Test tự động cho API công khai xem chi tiết phương tiện.

Chạy từ thư mục backend/:

    pip install pytest httpx
    pytest tests/test_public_vehicle_detail.py -q

Test dùng SQLite in-memory và override dependency get_db, không cần MySQL.
"""
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import app
from app.models.booking import Booking
from app.models.delivery import DeliveryPoint
from app.models.store import Store
from app.models.user import User
from app.models.vehicle import Vehicle, VehicleImage
from app.models.vehicle_reservation import VehicleReservation
from app.models.vehicle_schedule import VehicleSchedule

URL = "/api/vehicles/{vehicle_id}"


@pytest.fixture()
def client():
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
    db.add_all(
        [
            User(id=9001, phone="0900000901", full_name="Chủ cửa hàng test"),
            User(id=9002, phone="0900000902", full_name="Khách hàng test"),
            Store(
                id=9001,
                owner_user_id=9001,
                name="RideHub Test APPROVED",
                address="122 Hoàng Quốc Việt",
                city="Hà Nội",
                business_license="GP-TEST-9001",
                bank_account_info="BANK-SECRET-9001",
                status="APPROVED",
            ),
            Store(
                id=9002,
                owner_user_id=9001,
                name="RideHub Test PENDING",
                address="1 Đại Cồ Việt",
                city="Hà Nội",
                business_license="GP-TEST-9002",
                bank_account_info="BANK-SECRET-9002",
                status="PENDING",
            ),
            Vehicle(
                id=9001,
                store_id=9001,
                vehicle_type="MOTORBIKE",
                plate_number="29A-9001",
                brand="Honda",
                model="Vision",
                year_of_manufacture=2023,
                engine_capacity=110,
                transmission_type="AUTOMATIC",
                seats=2,
                fuel_type="GASOLINE",
                price_per_day=150000,
                price_per_hour=25000,
                current_status="AVAILABLE",
                description="Xe mới, bảo dưỡng định kỳ",
                is_active=True,
            ),
            Vehicle(
                id=9002,
                store_id=9001,
                vehicle_type="MOTORBIKE",
                plate_number="29A-9002",
                brand="Honda",
                model="Wave",
                price_per_day=120000,
                price_per_hour=20000,
                current_status="AVAILABLE",
                is_active=True,
            ),
            Vehicle(
                id=9003,
                store_id=9001,
                vehicle_type="MOTORBIKE",
                plate_number="29A-9003",
                brand="Yamaha",
                model="Exciter",
                price_per_day=180000,
                current_status="AVAILABLE",
                is_active=True,
            ),
            Vehicle(
                id=9004,
                store_id=9001,
                vehicle_type="MOTORBIKE",
                plate_number="29A-9004",
                brand="Yamaha",
                model="Janus",
                price_per_day=140000,
                current_status="AVAILABLE",
                is_active=True,
            ),
            Vehicle(
                id=9005,
                store_id=9001,
                vehicle_type="CAR",
                plate_number="30A-9005",
                brand="Toyota",
                model="Vios",
                price_per_day=800000,
                current_status="MAINTENANCE",
                is_active=True,
            ),
            Vehicle(
                id=9006,
                store_id=9001,
                vehicle_type="MOTORBIKE",
                plate_number="29A-9006",
                brand="Honda",
                model="Future",
                price_per_day=110000,
                current_status="AVAILABLE",
                is_active=False,
            ),
            Vehicle(
                id=9007,
                store_id=9002,
                vehicle_type="MOTORBIKE",
                plate_number="29A-9007",
                brand="Honda",
                model="Air Blade",
                price_per_day=160000,
                current_status="AVAILABLE",
                is_active=True,
            ),
            VehicleImage(
                id=9101,
                vehicle_id=9001,
                image_url="https://example.com/vision-2.jpg",
                is_primary=False,
                sort_order=2,
            ),
            VehicleImage(
                id=9102,
                vehicle_id=9001,
                image_url="https://example.com/vision-1.jpg",
                is_primary=True,
                sort_order=1,
            ),
            VehicleImage(
                id=9103,
                vehicle_id=9001,
                image_url="https://example.com/vision-null.jpg",
                is_primary=False,
                sort_order=None,
            ),
            DeliveryPoint(
                id=9101,
                store_id=9001,
                name="Điểm giao Cầu Giấy",
                address="Bến xe Mỹ Đình",
                area="Quận Cầu Giấy",
                delivery_fee=50000,
                is_active=True,
            ),
            DeliveryPoint(
                id=9102,
                store_id=9001,
                name="Điểm giao Đống Đa",
                address="Ga Hà Nội",
                area="Quận Đống Đa",
                delivery_fee=40000,
                is_active=True,
            ),
            DeliveryPoint(
                id=9103,
                store_id=9001,
                name="Điểm giao ẩn",
                address="Không dùng",
                area="Quận X",
                delivery_fee=0,
                is_active=False,
            ),
            Booking(
                id=9001,
                customer_id=9002,
                vehicle_id=9002,
                store_id=9001,
                start_time=datetime(2026, 12, 1, 9, 0),
                end_time=datetime(2026, 12, 3, 9, 0),
                status="CONFIRMED",
                rental_amount=300000,
                delivery_fee=0,
                deposit_amount=100000,
                total_amount=400000,
            ),
            VehicleReservation(
                id=9001,
                vehicle_id=9003,
                customer_id=9002,
                start_time=datetime(2026, 12, 5, 9, 0),
                end_time=datetime(2026, 12, 6, 9, 0),
                expires_at=datetime(2030, 1, 1, 0, 0),
                status="ACTIVE",
            ),
            VehicleReservation(
                id=9002,
                vehicle_id=9004,
                customer_id=9002,
                start_time=datetime(2026, 12, 7, 9, 0),
                end_time=datetime(2026, 12, 8, 9, 0),
                expires_at=datetime(2020, 1, 1, 0, 0),
                status="ACTIVE",
            ),
            VehicleSchedule(
                id=9001,
                vehicle_id=9005,
                schedule_type="MAINTENANCE",
                start_time=datetime(2026, 12, 10, 9, 0),
                end_time=datetime(2026, 12, 11, 9, 0),
                status="ACTIVE",
                note="Bảo dưỡng định kỳ",
            ),
        ]
    )
    db.commit()
    db.close()

    def override_get_db():
        session = testing_session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def get(client, vehicle_id, **params):
    return client.get(URL.format(vehicle_id=vehicle_id), params=params)


def test_detail_without_time(client):
    response = get(client, 9001)
    assert response.status_code == 200
    body = response.json()
    assert body["is_available"] is None
    assert body["unavailable_reason"] is None
    assert body["current_status"] == "AVAILABLE"
    assert body["price_per_day"] == 150000.0
    assert body["price_per_hour"] == 25000.0
    assert body["store"] == {
        "id": 9001,
        "name": "RideHub Test APPROVED",
        "address": "122 Hoàng Quốc Việt",
        "city": "Hà Nội",
    }
    assert [image["id"] for image in body["images"]] == [9102, 9101, 9103]
    assert [point["id"] for point in body["delivery_points"]] == [9101, 9102]


def test_vehicle_without_images(client):
    response = get(client, 9002)
    assert response.status_code == 200
    assert response.json()["images"] == []


def test_not_public_returns_404(client):
    expected = "Không tìm thấy phương tiện hoặc phương tiện không còn công khai."
    for vehicle_id in (9006, 9007, 999999):
        response = get(client, vehicle_id)
        assert response.status_code == 404
        assert response.json()["detail"] == expected


def test_vehicle_id_not_integer_returns_422(client):
    response = client.get("/api/vehicles/abc")
    assert response.status_code == 422


def test_time_validation(client):
    response = get(client, 9001, start_time="2026-12-20T09:00:00")
    assert response.status_code == 422
    assert response.json()["detail"] == "Phải truyền đủ cả start_time và end_time."

    response = get(
        client,
        9001,
        start_time="2026-12-20T09:00:00",
        end_time="2026-12-20T09:00:00",
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "end_time phải lớn hơn start_time."


def test_available_time_range(client):
    response = get(
        client,
        9001,
        start_time="2026-12-20T09:00:00",
        end_time="2026-12-21T09:00:00",
    )
    assert response.status_code == 200
    assert response.json()["is_available"] is True
    assert response.json()["unavailable_reason"] is None


def test_booking_conflict_and_buffer(client):
    response = get(
        client,
        9002,
        start_time="2026-12-02T09:00:00",
        end_time="2026-12-02T10:00:00",
    )
    assert response.status_code == 200
    assert response.json()["is_available"] is False
    assert response.json()["unavailable_reason"] == "BOOKED"

    response = get(
        client,
        9002,
        start_time="2026-12-03T09:30:00",
        end_time="2026-12-03T10:30:00",
    )
    assert response.json()["is_available"] is False
    assert response.json()["unavailable_reason"] == "BOOKED"

    response = get(
        client,
        9002,
        start_time="2026-12-03T10:01:00",
        end_time="2026-12-03T11:00:00",
    )
    assert response.json()["is_available"] is True


def test_reservation_conflict_and_expiry(client):
    response = get(
        client,
        9003,
        start_time="2026-12-05T12:00:00",
        end_time="2026-12-05T13:00:00",
    )
    assert response.json()["is_available"] is False
    assert response.json()["unavailable_reason"] == "HELD"

    response = get(
        client,
        9004,
        start_time="2026-12-07T12:00:00",
        end_time="2026-12-07T13:00:00",
    )
    assert response.json()["is_available"] is True


def test_schedule_conflict(client):
    response = get(
        client,
        9005,
        start_time="2026-12-10T12:00:00",
        end_time="2026-12-10T13:00:00",
    )
    assert response.json()["is_available"] is False
    assert response.json()["unavailable_reason"] == "MAINTENANCE_OR_BLOCKED"


def test_no_sensitive_data(client):
    body = get(client, 9001).text
    for field in (
        "plate_number",
        "owner_user_id",
        "business_license",
        "bank_account_info",
        "reject_reason",
        "approved_by",
    ):
        assert field not in body
