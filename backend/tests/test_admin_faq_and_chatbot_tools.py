"""Bộ kiểm thử toàn diện cho:
1. [BE] Chatbot: API kho FAQ do admin quản lý (Thêm, Sửa, Xóa, Tra cứu, Kiểm soát quyền Admin).
2. [BE] Chatbot: Tìm xe và tra cứu đơn của chính người dùng qua API có kiểm soát (Chỉ trả đơn chính chủ).
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db.session import Base
from app.models.faq import FAQ
from app.models.vehicle import Vehicle
from app.models.booking import Booking
from app.models.user import User
from app.schemas.faq import FAQCreate, FAQUpdate
from app.schemas.chat import (
    ChatMessageRequest,
    KnowledgeEntryCreate,
    KnowledgeEntryUpdate,
)
from app.routers.faq import create_faq, update_faq, delete_faq, get_faqs, get_faq_detail
from app.routers.chat import (
    api_search_vehicles_tool,
    api_my_bookings_tool,
    api_update_knowledge_entry,
    require_admin,
)
from app.crud.chat import (
    search_vehicles_for_chat,
    lookup_user_bookings_for_chat,
    process_ai_chat_message,
    update_knowledge_entry,
)

# SQLite In-memory cho test
SQLITE_URL = "sqlite://"
engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSession(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def admin_mock():
    user = MagicMock()
    user.id = 1
    user.role = "admin"
    user.email = "admin@ridehub.vn"
    return user


@pytest.fixture
def customer_user_1(db):
    user = User(
        id=201,
        email="customer1@ridehub.vn",
        phone="0900000201",
        full_name="Khách Hàng Một",
        status="active",
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def customer_user_2(db):
    user = User(
        id=202,
        email="customer2@ridehub.vn",
        phone="0900000202",
        full_name="Khách Hàng Hai",
        status="active",
    )
    db.add(user)
    db.commit()
    return user


# ===========================================================================
# 1. TEST SUITE: API KHO FAQ DO ADMIN QUẢN LÝ
# ===========================================================================

def test_admin_create_faq_success(db, admin_mock):
    """Admin tạo mới câu hỏi FAQ / chính sách thành công."""
    payload = FAQCreate(
        category="price",
        category_name="Chính sách giá",
        question="Giá thuê xe ngày lễ tết có tăng không?",
        answer="RideHub áp dụng phụ thu 15% vào các ngày lễ Tết theo quy định.",
        display_order=1,
        is_active=True,
    )

    created = create_faq(payload=payload, db=db, _admin=admin_mock)
    assert created.id is not None
    assert created.category == "price"
    assert created.question == payload.question


def test_admin_update_faq_success(db, admin_mock):
    """Admin sửa nội dung FAQ thành công."""
    faq = FAQ(
        category="deposit",
        category_name="Tiền cọc",
        question="Cọc xe máy bao nhiêu?",
        answer="Cọc 2 triệu.",
        display_order=2,
        is_active=True,
    )
    db.add(faq)
    db.commit()

    update_payload = FAQUpdate(
        answer="Cọc 1 triệu đối với xe máy số, 2 triệu đối với xe tay ga cao cấp.",
        display_order=5,
    )
    updated = update_faq(faq_id=faq.id, payload=update_payload, db=db, _admin=admin_mock)
    assert updated.id == faq.id
    assert "1 triệu" in updated.answer
    assert updated.display_order == 5


def test_admin_delete_faq_success(db, admin_mock):
    """Admin xóa FAQ thành công, truy vấn lại trả về 404."""
    faq = FAQ(
        category="cancel",
        category_name="Hủy đơn",
        question="FAQ sẽ bị xóa",
        answer="Nội dung tạm",
        is_active=True,
    )
    db.add(faq)
    db.commit()

    res = delete_faq(faq_id=faq.id, db=db, _admin=admin_mock)
    assert "thành công" in res["message"]

    # Kiểm tra đã biến mất
    with pytest.raises(HTTPException) as exc_info:
        get_faq_detail(faq_id=faq.id, db=db)
    assert exc_info.value.status_code == 404


def test_public_get_faqs_and_detail(db):
    """Khách công khai tra cứu danh sách FAQ theo category và từ khóa."""
    faq1 = FAQ(category="ekyc", category_name="Xác thực", question="Cần CCCD gắn chip không?", answer="Có bắt buộc.", is_active=True)
    faq2 = FAQ(category="ekyc", category_name="Xác thực", question="Bằng lái xe nước ngoài được không?", answer="Cần đổi sang bằng quốc tế IAA.", is_active=True)
    faq_inactive = FAQ(category="ekyc", category_name="Xác thực", question="FAQ đã ẩn", answer="Ẩn rồi.", is_active=False)
    db.add_all([faq1, faq2, faq_inactive])
    db.commit()

    # Tra cứu công khai -> không thấy faq_inactive
    results = get_faqs(category="ekyc", q=None, include_inactive=False, db=db)
    assert len(results) == 2

    # Tìm kiếm theo từ khóa 'quốc tế'
    search_res = get_faqs(category="ekyc", q="quốc tế", include_inactive=False, db=db)
    assert len(search_res) == 1
    assert "nước ngoài" in search_res[0].question


def test_non_admin_blocked_from_faq_crud():
    """Người dùng không phải admin bị chặn quyền thêm/sửa/xóa (HTTP 403)."""
    user_mock = MagicMock()
    user_mock.role = "customer"

    with pytest.raises(HTTPException) as exc_info:
        require_admin(actor=user_mock)
    assert exc_info.value.status_code == 403
    assert "Chỉ admin" in exc_info.value.detail


# ===========================================================================
# 2. TEST SUITE: CHATBOT TÌM XE & TRA CỨU ĐƠN CỦA CHÍNH NGƯỜI DÙNG (CÓ KIỂM SOÁT)
# ===========================================================================

def test_chatbot_search_vehicles(db):
    """Chatbot gọi công cụ tìm kiếm xe khả dụng theo tiêu chí loại xe, giá, chỗ ngồi."""
    v1 = Vehicle(store_id=1, vehicle_type="CAR", plate_number="30A-111.11", brand="Toyota", model="Vios", seats=4, price_per_day=800000, current_status="AVAILABLE", is_active=True)
    v2 = Vehicle(store_id=1, vehicle_type="CAR", plate_number="30A-222.22", brand="Mitsubishi", model="Xpander", seats=7, price_per_day=1100000, current_status="AVAILABLE", is_active=True)
    v3 = Vehicle(store_id=1, vehicle_type="MOTORBIKE", plate_number="29B1-333.33", brand="Honda", model="Vision", seats=2, price_per_day=150000, current_status="AVAILABLE", is_active=True)
    v4 = Vehicle(store_id=1, vehicle_type="CAR", plate_number="30A-444.44", brand="Hyundai", model="Accent", seats=4, price_per_day=750000, current_status="RENTED", is_active=True)
    db.add_all([v1, v2, v3, v4])
    db.commit()

    # 1. Tìm ô tô 7 chỗ
    cars_7 = search_vehicles_for_chat(vehicle_type="CAR", seats=7, db=db)
    assert len(cars_7) == 1
    assert cars_7[0].model == "Xpander"

    # 2. Tìm xe máy
    bikes = search_vehicles_for_chat(vehicle_type="MOTORBIKE", db=db)
    assert len(bikes) == 1
    assert bikes[0].model == "Vision"

    # 3. Xe đang RENTED (Hyundai Accent) không bao giờ xuất hiện trong kết quả tìm xe khả dụng
    all_available = search_vehicles_for_chat(db=db)
    plate_list = [v.plate_number for v in all_available]
    assert "30A-444.44" not in plate_list


def test_chatbot_lookup_user_bookings_strict_isolation(db, customer_user_1, customer_user_2):
    """KIỂM SOÁT BẢO MẬT: Tra cứu đơn chỉ trả về đúng đơn của chính người dùng đang chat."""
    # Tạo xe
    v = Vehicle(store_id=1, vehicle_type="CAR", plate_number="30A-999.99", brand="Mazda", model="CX-5", seats=5, price_per_day=1200000, current_status="AVAILABLE", is_active=True)
    db.add(v)
    db.commit()

    # Đơn của User 1
    b1 = Booking(
        id=101,
        customer_id=customer_user_1.id,
        vehicle_id=v.id,
        start_time=datetime.now(),
        end_time=datetime.now() + timedelta(days=2),
        status="CONFIRMED",
        rental_amount=Decimal("2400000"),
        total_amount=Decimal("2400000"),
        deposit_amount=Decimal("5000000"),
    )
    # Đơn của User 2
    b2 = Booking(
        id=102,
        customer_id=customer_user_2.id,
        vehicle_id=v.id,
        start_time=datetime.now(),
        end_time=datetime.now() + timedelta(days=1),
        status="IN_PROGRESS",
        rental_amount=Decimal("1200000"),
        total_amount=Decimal("1200000"),
        deposit_amount=Decimal("5000000"),
    )
    db.add_all([b1, b2])
    db.commit()

    # User 1 tra cứu đơn của mình -> CHỈ thấy đơn 101, TUYỆT ĐỐI KHÔNG THẤY đơn 102
    user1_bookings = lookup_user_bookings_for_chat(current_user_id=customer_user_1.id, db=db)
    assert len(user1_bookings) == 1
    assert user1_bookings[0].booking_id == 101
    assert user1_bookings[0].plate_number == "30A-999.99"

    # User 1 cố tình tra cứu trực tiếp ID đơn 102 (đơn của User 2) -> Kết quả rỗng, không được xem!
    stolen_lookup = lookup_user_bookings_for_chat(current_user_id=customer_user_1.id, booking_id=102, db=db)
    assert len(stolen_lookup) == 0

    # User 2 tra cứu đơn của mình -> Thấy đúng đơn 102
    user2_bookings = lookup_user_bookings_for_chat(current_user_id=customer_user_2.id, booking_id=102, db=db)
    assert len(user2_bookings) == 1
    assert user2_bookings[0].booking_id == 102


def test_chatbot_message_flow_with_booking_and_vehicle_intent(db, customer_user_1):
    """Quy trình Chatbot xử lý tin nhắn tự động nhận diện ý định tra cứu đơn và tìm xe."""
    session_id = "b1c2d3e4-f5a6-4b7c-8d9e-0f1a2b3c4d5e"

    # Tạo trước 1 đơn thuê cho customer_user_1 và 1 xe ô tô 7 chỗ
    v_car = Vehicle(store_id=1, vehicle_type="CAR", plate_number="30A-777.77", brand="Mitsubishi", model="Xpander", seats=7, price_per_day=1100000, current_status="AVAILABLE", is_active=True)
    db.add(v_car)
    db.commit()

    b = Booking(
        id=201,
        customer_id=customer_user_1.id,
        vehicle_id=v_car.id,
        start_time=datetime.now(),
        end_time=datetime.now() + timedelta(days=2),
        status="CONFIRMED",
        rental_amount=Decimal("2200000"),
        total_amount=Decimal("2200000"),
        deposit_amount=Decimal("5000000"),
    )
    db.add(b)
    db.commit()

    # 1. Khách hỏi đơn mà CHƯA đăng nhập (current_user=None) -> Chatbot yêu cầu đăng nhập
    req_unauth = ChatMessageRequest(
        session_id=session_id,
        message="Kiểm tra đơn thuê xe của tôi với",
    )
    res_unauth = process_ai_chat_message(
        payload=req_unauth,
        client_identifier=session_id,
        db=db,
        current_user=None,
    )
    assert "đăng nhập" in res_unauth.message.lower()
    assert res_unauth.detected_intent == "lookup_booking_unauthorized"

    # 2. Khách ĐÃ đăng nhập hỏi đơn -> Chatbot trả về danh sách đơn của chính khách
    res_auth = process_ai_chat_message(
        payload=req_unauth,
        client_identifier=session_id,
        db=db,
        current_user=customer_user_1,
    )
    assert res_auth.detected_intent == "lookup_user_booking"
    assert "Đơn #" in res_auth.message
    assert "Xpander" in res_auth.message

    # 3. Khách hỏi tìm xe
    req_car = ChatMessageRequest(
        session_id=session_id,
        message="Cho mình tìm xe ô tô 7 chỗ với",
    )
    res_car = process_ai_chat_message(
        payload=req_car,
        client_identifier=session_id,
        db=db,
        current_user=customer_user_1,
    )
    assert res_car.detected_intent == "search_vehicles"
    assert "Xpander" in res_car.message
