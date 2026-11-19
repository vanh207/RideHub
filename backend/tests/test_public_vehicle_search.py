"""Test tự động cho API công khai tìm xe.

Chạy từ thư mục backend/:

    pip install pytest httpx
    pytest tests/test_public_vehicle_search.py -q

Test dùng SQLite in-memory và override dependency get_db, không cần MySQL.
"""
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401 - đăng ký toàn bộ model với metadata
from app.db.session import Base, get_db
from app.models.booking import Booking
from app.models.delivery import DeliveryPoint
from app.models.store import Store
from app.models.user import User
from app.models.vehicle import Vehicle, VehicleImage
from app.models.vehicle_reservation import VehicleReservation
from app.models.vehicle_schedule import VehicleSchedule
from app.routers.vehicles import router as vehicles_router

URL = "/api/vehicles/search"


def _vehicle(
    vehicle_id,
    store_id,
    vehicle_type,
    brand,
    model,
    price_per_day,
    created_at,
    *,
    price_per_hour=None,
    seats=2,
    transmission_type="MANUAL",
    fuel_type="GASOLINE",
    is_active=True,
):
    return Vehicle(
        id=vehicle_id,
        store_id=store_id,
        vehicle_type=vehicle_type,
        plate_number=f"TEST-{vehicle_id}",
        brand=brand,
        model=model,
        seats=seats,
        transmission_type=transmission_type,
        fuel_type=fuel_type,
        price_per_day=price_per_day,
        price_per_hour=price_per_hour,
        current_status="MAINTENANCE",
        is_active=is_active,
        created_at=created_at,
    )


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
            User(id=9201, phone="0900009201", full_name="Chủ cửa hàng"),
            User(id=9202, phone="0900009202", full_name="Khách hàng"),
            Store(
                id=9201,
                owner_user_id=9201,
                name="RideHub Hà Nội",
                address="122 Hoàng Quốc Việt",
                city="Hà Nội",
                business_license="GP-9201",
                bank_account_info="BANK-SECRET-9201",
                status="APPROVED",
            ),
            Store(
                id=9202,
                owner_user_id=9201,
                name="RideHub Đà Nẵng",
                address="1 Bạch Đằng",
                city="Đà Nẵng",
                business_license="GP-9202",
                bank_account_info="BANK-SECRET-9202",
                status="APPROVED",
            ),
            Store(
                id=9203,
                owner_user_id=9201,
                name="RideHub PENDING",
                address="1 Nguyễn Huệ",
                city="TP.HCM",
                business_license="GP-9203",
                bank_account_info="BANK-SECRET-9203",
                status="PENDING",
            ),
            _vehicle(
                9201, 9201, "MOTORBIKE", "Honda", "Vision", 150000,
                datetime(2026, 11, 1, 10, 0), price_per_hour=25000,
            ),
            _vehicle(
                9202, 9201, "MOTORBIKE", "Honda", "Wave", 120000,
                datetime(2026, 11, 2, 10, 0), price_per_hour=20000,
            ),
            _vehicle(
                9203, 9202, "CAR", "Toyota", "Vios", 800000,
                datetime(2026, 11, 3, 10, 0), price_per_hour=120000,
                seats=5, transmission_type="AUTOMATIC",
            ),
            _vehicle(
                9204, 9202, "MOTORBIKE", "Yamaha", "Exciter", 180000,
                datetime(2026, 11, 4, 10, 0), price_per_hour=30000,
            ),
            _vehicle(
                9205, 9201, "CAR", "Honda", "City", 900000,
                datetime(2026, 11, 5, 10, 0), price_per_hour=140000,
                seats=5, transmission_type="AUTOMATIC",
            ),
            _vehicle(
                9206, 9201, "MOTORBIKE", "Honda", "Future", 110000,
                datetime(2026, 11, 6, 10, 0), is_active=False,
            ),
            _vehicle(
                9207, 9203, "MOTORBIKE", "Honda", "Air Blade", 160000,
                datetime(2026, 11, 7, 10, 0),
            ),
            _vehicle(
                9208, 9201, "CAR", "Mazda", "CX-5", 850000,
                datetime(2026, 11, 8, 10, 0), price_per_hour=130000,
                seats=5, transmission_type="AUTOMATIC",
            ),
            _vehicle(
                9209, 9201, "MOTORBIKE", "Honda", "Dream", 100000,
                datetime(2026, 11, 9, 10, 0),
            ),
            VehicleImage(
                id=9401,
                vehicle_id=9201,
                image_url="https://example.com/9201-primary.jpg",
                is_primary=True,
                sort_order=1,
            ),
            VehicleImage(
                id=9402,
                vehicle_id=9201,
                image_url="https://example.com/9201-secondary.jpg",
                is_primary=False,
                sort_order=2,
            ),
            VehicleImage(
                id=9403,
                vehicle_id=9209,
                image_url="https://example.com/9209-first.jpg",
                is_primary=False,
                sort_order=None,
            ),
            DeliveryPoint(
                id=9301,
                store_id=9201,
                name="Điểm giao Cầu Giấy",
                address="Bến xe Mỹ Đình",
                area="Quận Cầu Giấy",
                delivery_fee=50000,
                is_active=True,
            ),
            DeliveryPoint(
                id=9302,
                store_id=9201,
                name="Điểm giao Đống Đa",
                address="Ga Hà Nội",
                area="Quận Đống Đa",
                delivery_fee=40000,
                is_active=True,
            ),
            DeliveryPoint(
                id=9303,
                store_id=9202,
                name="Điểm giao Hải Châu",
                address="Bạch Đằng",
                area="Quận Hải Châu",
                delivery_fee=30000,
                is_active=True,
            ),
            DeliveryPoint(
                id=9304,
                store_id=9201,
                name="Điểm giao ẩn",
                address="Không dùng",
                area="Quận X",
                delivery_fee=0,
                is_active=False,
            ),
            DeliveryPoint(
                id=9305,
                store_id=9203,
                name="Điểm giao PENDING",
                address="Không trả",
                area="Quận 1",
                delivery_fee=0,
                is_active=True,
            ),
            Booking(
                id=9501,
                customer_id=9202,
                vehicle_id=9202,
                store_id=9201,
                start_time=datetime(2026, 12, 1, 9, 0),
                end_time=datetime(2026, 12, 3, 9, 0),
                status="CONFIRMED",
                rental_amount=300000,
                delivery_fee=0,
                deposit_amount=100000,
                total_amount=400000,
            ),
            VehicleReservation(
                id=9601,
                vehicle_id=9204,
                customer_id=9202,
                start_time=datetime(2026, 12, 5, 9, 0),
                end_time=datetime(2026, 12, 6, 9, 0),
                expires_at=datetime(2030, 1, 1, 0, 0),
                status="ACTIVE",
            ),
            VehicleReservation(
                id=9602,
                vehicle_id=9205,
                customer_id=9202,
                start_time=datetime(2026, 12, 7, 9, 0),
                end_time=datetime(2026, 12, 8, 9, 0),
                expires_at=datetime(2020, 1, 1, 0, 0),
                status="ACTIVE",
            ),
            VehicleSchedule(
                id=9701,
                vehicle_id=9208,
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

    test_app = FastAPI()
    test_app.include_router(vehicles_router, prefix="/api")
    test_app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(test_app)
    finally:
        test_app.dependency_overrides.clear()


def get(client, **params):
    return client.get(URL, params=params)


def item_ids(response):
    return [item["id"] for item in response.json()["items"]]


def test_search_route_not_captured_by_vehicle_id(client):
    response = get(client)
    assert response.status_code == 200
    assert response.json()["total"] == 7


def test_search_without_params(client):
    response = get(client)
    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 1
    assert body["page_size"] == 12
    assert body["total"] == 7
    assert item_ids(response) == [
        9209,
        9202,
        9201,
        9204,
        9203,
        9208,
        9205,
    ]
    assert all(item["is_available"] is None for item in body["items"])
    assert set(body["items"][0]["store"]) == {"id", "name", "city"}
    assert 9206 not in item_ids(response)
    assert 9207 not in item_ids(response)


def test_primary_image_url(client):
    body = get(client).json()
    by_id = {item["id"]: item for item in body["items"]}
    assert (
        by_id[9201]["primary_image_url"]
        == "https://example.com/9201-primary.jpg"
    )
    assert by_id[9202]["primary_image_url"] is None
    assert by_id[9209]["primary_image_url"] == "https://example.com/9209-first.jpg"


def test_area_matches_city_case_insensitive(client):
    response = get(client, area="Hà Nội")
    assert response.status_code == 200
    assert response.json()["total"] == 5
    assert item_ids(response) == [9209, 9202, 9201, 9208, 9205]


def test_area_matches_delivery_point_area(client):
    response = get(client, area="quận cầu giấy")
    assert response.status_code == 200
    assert response.json()["total"] == 5
    assert item_ids(response) == [9209, 9202, 9201, 9208, 9205]

    response = get(client, area="Quận Hải Châu")
    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert item_ids(response) == [9204, 9203]


def test_area_ignores_inactive_point_and_pending_store(client):
    response = get(client, area="Quận X")
    assert response.status_code == 200
    assert response.json()["total"] == 0

    response = get(client, area="Quận 1")
    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_area_escapes_like_wildcards(client):
    response = get(client, area="%")
    assert response.status_code == 200
    assert response.json()["total"] == 0

    response = get(client, area="_")
    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_filter_by_vehicle_type(client):
    response = get(client, vehicle_type="motorbike")
    assert response.status_code == 200
    assert response.json()["total"] == 4
    assert item_ids(response) == [9209, 9202, 9201, 9204]

    response = get(client, vehicle_type="CAR")
    assert response.status_code == 200
    assert response.json()["total"] == 3
    assert item_ids(response) == [9203, 9208, 9205]

    response = get(client, vehicle_type="TRUCK")
    assert response.status_code == 422


def test_filter_by_price_and_invalid_range(client):
    response = get(client, min_price=150000, max_price=850000)
    assert response.status_code == 200
    assert response.json()["total"] == 4
    assert item_ids(response) == [9201, 9204, 9203, 9208]

    response = get(client, min_price=900000, max_price=100000)
    assert response.status_code == 422


def test_combined_filters(client):
    response = get(
        client,
        area="Hà Nội",
        vehicle_type="CAR",
        min_price=800000,
        max_price=900000,
        sort="price_desc",
    )
    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert item_ids(response) == [9205, 9208]


def test_pagination_and_sorting(client):
    response = get(client, page=2, page_size=3)
    assert response.status_code == 200
    assert response.json()["total"] == 7
    assert item_ids(response) == [9204, 9203, 9208]

    response = get(client, page=3, page_size=3)
    assert response.status_code == 200
    assert item_ids(response) == [9205]

    response = get(client, sort="price_desc")
    assert item_ids(response) == [9205, 9208, 9203, 9204, 9201, 9202, 9209]

    response = get(client, sort="newest")
    assert item_ids(response) == [9209, 9208, 9205, 9204, 9203, 9202, 9201]

    assert get(client, page_size=51).status_code == 422
    assert get(client, page=0).status_code == 422
    assert get(client, sort="unknown").status_code == 422


def test_time_validation(client):
    response = get(client, start_time="2026-12-20T09:00:00")
    assert response.status_code == 422
    assert response.json()["detail"] == "Phải truyền đủ cả start_time và end_time."

    response = get(
        client,
        start_time="2026-12-20T09:00:00",
        end_time="2026-12-20T09:00:00",
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "end_time phải lớn hơn start_time."

    response = get(
        client,
        start_time="2026-12-20T09:00:00",
        end_time="2026-12-20T12:59:59",
    )
    assert response.status_code == 422
    assert "4 giờ" in response.json()["detail"]

    response = get(
        client,
        start_time="2026-12-01T00:00:00",
        end_time="2026-12-31T01:00:00",
    )
    assert response.status_code == 422
    assert "30 ngày" in response.json()["detail"]


def test_free_time_range_returns_available_vehicles(client):
    response = get(
        client,
        start_time="2026-12-20T09:00:00",
        end_time="2026-12-20T13:00:00",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 7
    assert all(item["is_available"] is True for item in body["items"])


def test_booking_conflict_and_buffer_boundary(client):
    response = get(
        client,
        start_time="2026-12-02T09:00:00",
        end_time="2026-12-02T13:00:00",
    )
    assert response.status_code == 200
    assert response.json()["total"] == 6
    assert 9202 not in item_ids(response)

    response = get(
        client,
        start_time="2026-12-03T09:30:00",
        end_time="2026-12-03T13:30:00",
    )
    assert response.status_code == 200
    assert 9202 not in item_ids(response)

    response = get(
        client,
        start_time="2026-12-03T10:00:00",
        end_time="2026-12-03T14:00:00",
    )
    assert response.status_code == 200
    assert 9202 in item_ids(response)


def test_reservation_active_and_expired(client):
    response = get(
        client,
        start_time="2026-12-05T12:00:00",
        end_time="2026-12-05T16:00:00",
    )
    assert response.status_code == 200
    assert 9204 not in item_ids(response)

    response = get(
        client,
        start_time="2026-12-07T12:00:00",
        end_time="2026-12-07T16:00:00",
    )
    assert response.status_code == 200
    assert 9205 in item_ids(response)


def test_maintenance_schedule_excludes_vehicle(client):
    response = get(
        client,
        start_time="2026-12-10T12:00:00",
        end_time="2026-12-10T16:00:00",
    )
    assert response.status_code == 200
    assert 9208 not in item_ids(response)


def test_response_has_no_sensitive_fields(client):
    response = get(client)
    assert response.status_code == 200
    body = response.text
    for field in (
        "plate_number",
        "owner_user_id",
        "business_license",
        "bank_account_info",
        "reject_reason",
        "approved_by",
    ):
        assert field not in body
