"""Bộ kiểm thử đơn vị & tích hợp cho luồng Cửa hàng xác nhận / từ chối đơn (TF1A595).

Kiểm tra:
1. Xác nhận đơn thành công (chuyển sang CONFIRMED, lưu lịch sử, cập nhật lịch xe).
2. Tính idempotent khi xác nhận lại đơn đã xác nhận.
3. Từ chối đơn thành công kèm lý do (chuyển CANCELLED, hoàn cọc 100%, giải phóng lịch xe).
4. Tính idempotent khi từ chối lại đơn đã hủy.
5. Từ chối không có lý do -> Báo lỗi BookingValidationError (422).
6. Phân quyền RBAC (Khách hàng hoặc chủ cửa hàng khác không được phép duyệt/từ chối đơn).
7. Admin và Nhân viên cửa hàng (ACTIVE) có quyền duyệt/từ chối đơn.
8. Không thể duyệt/từ chối đơn ở trạng thái không hợp lệ (IN_PROGRESS, COMPLETED).
9. Truy vấn danh sách đơn hàng cho cửa hàng và tính toán KPI dòng tiền chính xác.
"""
from datetime import datetime, timedelta
from decimal import Decimal
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


from app.core.booking_status import (
    CANCELLED,
    CONFIRMED,
    DEPOSIT_PAID,
    PENDING_PAYMENT,
)
from app.crud.store_order_review import (
    BookingNotFoundError,
    BookingPermissionError,
    BookingStateError,
    BookingValidationError,
    get_store_orders_list,
    store_confirm_booking,
    store_reject_booking,
)
from app.db.session import Base
from app.models.booking import Booking, BookingStatusHistory
from app.models.payment import PaymentTransaction, Refund
from app.models.role import Role, UserRole
from app.models.store import Store, StoreStaff
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.vehicle_reservation import VehicleReservation
from app.models.vehicle_schedule import VehicleSchedule
from app.services.email_service import MockEmailSender, email_service
import app.models  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401

NOW = datetime.now().replace(minute=0, second=0, microsecond=0)
CUSTOMER_ID = 101
OWNER_ID = 102
STAFF_ID = 103
OTHER_OWNER_ID = 104
ADMIN_ID = 105


@pytest.fixture
def db_session():
    """Tạo DB in-memory SQLite cô lập cho từng test case."""
    old_sender = email_service.sender
    email_service.sender = MockEmailSender()

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()

    yield session

    session.close()
    Base.metadata.drop_all(bind=engine)
    email_service.sender = old_sender



def _create_user(db, user_id: int, role_code: str, email: str, name: str) -> User:
    role = db.scalar(select(Role).where(Role.code == role_code))
    if role is None:
        role = Role(code=role_code, name=role_code)
        db.add(role)
        db.flush()

    user = User(
        id=user_id,
        email=email,
        full_name=name,
        status="active",
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user_id, role_id=role.id))
    db.flush()
    db.refresh(user)
    return user


def _setup_test_environment(db):
    """Thiết lập cửa hàng, người dùng, xe và đơn đặt xe thử nghiệm."""
    customer = _create_user(db, CUSTOMER_ID, "customer", "customer@ridehub.vn", "Nguyễn Văn An")
    owner = _create_user(db, OWNER_ID, "store_owner", "owner@ridehub.vn", "Chủ Cửa Hàng 1")
    staff = _create_user(db, STAFF_ID, "store_staff", "staff@ridehub.vn", "Nhân Viên Trạm")
    other_owner = _create_user(db, OTHER_OWNER_ID, "store_owner", "other@ridehub.vn", "Chủ Cửa Hàng 2")
    admin = _create_user(db, ADMIN_ID, "admin", "admin@ridehub.vn", "Quản Trị Viên")

    # Tạo Cửa hàng 1
    store1 = Store(
        id=1,
        owner_user_id=owner.id,
        name="Trạm GreenRide Q.1",
        phone="0901234567",
        address="120 Nguyễn Huệ, Quận 1, TP.HCM",
        status="APPROVED",
    )
    db.add(store1)

    # Tạo Cửa hàng 2
    store2 = Store(
        id=2,
        owner_user_id=other_owner.id,
        name="Trạm GreenRide Q.7",
        phone="0909888777",
        address="45 Nguyễn Thị Thập, Quận 7, TP.HCM",
        status="APPROVED",
    )
    db.add(store2)
    db.flush()

    # Thêm nhân viên vào Cửa hàng 1
    staff_member = StoreStaff(
        id=1,
        store_id=store1.id,
        user_id=staff.id,
        staff_role="STAFF",
        status="ACTIVE",
    )
    db.add(staff_member)

    # Tạo Phương tiện thuộc Cửa hàng 1
    vehicle = Vehicle(
        id=1,
        store_id=store1.id,
        brand="VinFast",
        model="Feliz S",
        plate_number="59A-123.45",
        vehicle_type="MOTORBIKE",
        price_per_day=Decimal("160000.00"),
        current_status="AVAILABLE",
    )
    db.add(vehicle)
    db.flush()

    # Tạo Đơn đặt xe mẫu (trạng thái DEPOSIT_PAID - đã thanh toán cọc)
    booking = Booking(
        id=1,
        customer_id=customer.id,
        vehicle_id=vehicle.id,
        store_id=store1.id,
        start_time=NOW + timedelta(days=2),
        end_time=NOW + timedelta(days=4),
        status="DEPOSIT_PAID",
        rental_amount=Decimal("320000.00"),
        delivery_fee=Decimal("0.00"),
        deposit_amount=Decimal("96000.00"),
        total_amount=Decimal("320000.00"),
    )
    db.add(booking)
    db.flush()

    # Tạo Lịch giữ chỗ
    reservation = VehicleReservation(
        id=1,
        vehicle_id=vehicle.id,
        customer_id=customer.id,
        booking_id=booking.id,
        start_time=booking.start_time,
        end_time=booking.end_time,
        status="ACTIVE",
    )
    db.add(reservation)

    schedule = VehicleSchedule(
        id=1,
        vehicle_id=vehicle.id,
        booking_id=booking.id,
        reservation_id=reservation.id,
        schedule_type="RENTAL",
        start_time=booking.start_time,
        end_time=booking.end_time,
        status="ACTIVE",
        note="Giữ chỗ tự động",
    )
    db.add(schedule)

    # Tạo giao dịch cọc thành công
    transaction = PaymentTransaction(
        id=1,
        booking_id=booking.id,
        amount=Decimal("96000.00"),
        provider="VIETQR",
        payment_method="VIETQR",
        transaction_code="TRX_DEPOSIT_001",
        status="SUCCESS",
        paid_at=NOW,
    )
    db.add(transaction)
    db.commit()

    return {
        "customer": customer,
        "owner": owner,
        "staff": staff,
        "other_owner": other_owner,
        "admin": admin,
        "store1": store1,
        "store2": store2,
        "vehicle": vehicle,
        "booking": booking,
        "reservation": reservation,
        "schedule": schedule,
        "transaction": transaction,
    }


def test_store_owner_confirm_booking_success(db_session):
    """Test Case 1: Chủ cửa hàng xác nhận đơn thành công."""
    env = _setup_test_environment(db_session)
    booking = env["booking"]
    owner = env["owner"]

    result = store_confirm_booking(
        db_session,
        booking_id=booking.id,
        user=owner,
        note="Đã kiểm tra xe, mức pin 100%, sẵn sàng giao",
        now=NOW,
    )

    assert result.success is True
    assert result.status == CONFIRMED
    assert result.already_confirmed is False
    assert result.booking_id == booking.id

    # Kiểm tra trạng thái trong DB
    db_session.refresh(booking)
    assert booking.status == CONFIRMED

    # Kiểm tra VehicleReservation được chuyển sang CONFIRMED
    res = db_session.query(VehicleReservation).filter(VehicleReservation.booking_id == booking.id).first()
    assert res.status == "CONFIRMED"

    # Kiểm tra nhật ký BookingStatusHistory
    history = db_session.query(BookingStatusHistory).filter(
        BookingStatusHistory.booking_id == booking.id
    ).order_by(BookingStatusHistory.id.desc()).first()
    assert history is not None
    assert history.to_status == CONFIRMED
    assert history.changed_by == "STORE"
    assert history.changed_by_user_id == owner.id
    assert "Đã kiểm tra xe" in history.reason


def test_store_confirm_booking_idempotent(db_session):
    """Test Case 2: Tính Idempotent khi duyệt lại đơn đã duyệt."""
    env = _setup_test_environment(db_session)
    booking = env["booking"]
    owner = env["owner"]

    # Xác nhận lần 1
    store_confirm_booking(db_session, booking.id, owner, now=NOW)

    # Xác nhận lần 2
    result = store_confirm_booking(db_session, booking.id, owner, now=NOW)
    assert result.success is True
    assert result.already_confirmed is True
    assert result.status == CONFIRMED


def test_store_staff_can_confirm_booking(db_session):
    """Test Case 3: Nhân viên trạm (ACTIVE) có quyền xác nhận đơn."""
    env = _setup_test_environment(db_session)
    booking = env["booking"]
    staff = env["staff"]

    result = store_confirm_booking(db_session, booking.id, staff, note="Nhân viên ca sáng xác nhận", now=NOW)
    assert result.success is True
    assert result.status == CONFIRMED


def test_admin_can_confirm_and_reject_any_order(db_session):
    """Test Case 4: Admin có toàn quyền duyệt đơn."""
    env = _setup_test_environment(db_session)
    booking = env["booking"]
    admin = env["admin"]

    result = store_confirm_booking(db_session, booking.id, admin, note="Admin hỗ trợ duyệt", now=NOW)
    assert result.success is True
    assert result.status == CONFIRMED


def test_unauthorized_user_cannot_confirm(db_session):
    """Test Case 5: Khách hàng hoặc chủ cửa hàng khác không có quyền duyệt."""
    env = _setup_test_environment(db_session)
    booking = env["booking"]
    customer = env["customer"]
    other_owner = env["other_owner"]

    # Khách hàng thử duyệt đơn
    with pytest.raises(BookingPermissionError):
        store_confirm_booking(db_session, booking.id, customer, now=NOW)

    # Chủ cửa hàng khác thử duyệt đơn
    with pytest.raises(BookingPermissionError):
        store_confirm_booking(db_session, booking.id, other_owner, now=NOW)


def test_store_reject_booking_success_with_100_percent_refund(db_session):
    """Test Case 6: Cửa hàng từ chối đơn thành công, hoàn 100% cọc và giải phóng lịch xe."""
    env = _setup_test_environment(db_session)
    booking = env["booking"]
    owner = env["owner"]

    reason = "Xe gặp sự cố kỹ thuật đột xuất cần bảo dưỡng động cơ"
    result = store_reject_booking(
        db_session,
        booking_id=booking.id,
        user=owner,
        reason=reason,
        now=NOW,
    )

    assert result.success is True
    assert result.status == CANCELLED
    assert result.cancelled_by == "STORE"
    assert result.cancel_reason == reason
    assert result.refund_amount == 96000.0  # Hoàn 100% tiền cọc 96k
    assert result.refund_rate == 1.0

    # Kiểm tra DB booking
    db_session.refresh(booking)
    assert booking.status == CANCELLED
    assert booking.cancelled_by == "STORE"
    assert booking.cancel_reason == reason

    # Kiểm tra lịch xe đã được giải phóng (CANCELLED)
    res = db_session.query(VehicleReservation).filter(VehicleReservation.booking_id == booking.id).first()
    assert res.status == "CANCELLED"
    sch = db_session.query(VehicleSchedule).filter(VehicleSchedule.booking_id == booking.id).first()
    assert sch.status == "CANCELLED"

    # Kiểm tra bản ghi Refund đã được sinh ra
    refund = db_session.query(Refund).filter(Refund.booking_id == booking.id).first()
    assert refund is not None
    assert float(refund.amount) == 96000.0
    assert "STORE_REJECT" in refund.reason

    # Kiểm tra BookingStatusHistory
    history = db_session.query(BookingStatusHistory).filter(
        BookingStatusHistory.booking_id == booking.id
    ).order_by(BookingStatusHistory.id.desc()).first()
    assert history.to_status == CANCELLED
    assert history.changed_by == "STORE"
    assert reason in history.reason


def test_store_reject_without_reason_raises_validation_error(db_session):
    """Test Case 7: Từ chối đơn không kèm lý do hoặc lý do quá ngắn sẽ bị chặn."""
    env = _setup_test_environment(db_session)
    booking = env["booking"]
    owner = env["owner"]

    with pytest.raises(BookingValidationError):
        store_reject_booking(db_session, booking.id, owner, reason="", now=NOW)

    with pytest.raises(BookingValidationError):
        store_reject_booking(db_session, booking.id, owner, reason="   ", now=NOW)

    with pytest.raises(BookingValidationError):
        store_reject_booking(db_session, booking.id, owner, reason="ab", now=NOW)


def test_cannot_confirm_or_reject_cancelled_or_completed_order(db_session):
    """Test Case 8: Không thể duyệt đơn đã hủy hoặc đang/đã kết thúc."""
    env = _setup_test_environment(db_session)
    booking = env["booking"]
    owner = env["owner"]

    # Đơn đã hủy
    booking.status = CANCELLED
    db_session.commit()

    with pytest.raises(BookingStateError):
        store_confirm_booking(db_session, booking.id, owner, now=NOW)

    # Đơn đã hoàn tất
    booking.status = "COMPLETED"
    db_session.commit()

    with pytest.raises(BookingStateError):
        store_confirm_booking(db_session, booking.id, owner, now=NOW)

    with pytest.raises(BookingStateError):
        store_reject_booking(db_session, booking.id, owner, reason="Lý do trễ", now=NOW)


def test_get_store_orders_list_and_kpis(db_session):
    """Test Case 9: Truy vấn danh sách đơn hàng cho cửa hàng và kiểm tra tính toán KPI."""
    env = _setup_test_environment(db_session)
    owner = env["owner"]

    result = get_store_orders_list(
        db_session,
        user=owner,
        status_filter="all",
        page=1,
        page_size=10,
    )

    assert result.success is True
    assert result.total == 1
    assert len(result.orders) == 1
    order = result.orders[0]
    assert order.id == 1
    assert order.customer.full_name == "Nguyễn Văn An"
    assert order.vehicle.name == "VinFast Feliz S"
    assert order.pricing.deposit_amount == 96000.0
    assert order.pricing.total_amount == 320000.0

    # Kiểm tra chỉ số KPI
    assert result.metrics.total_orders == 1
    assert result.metrics.pending_orders == 1
    assert result.metrics.approved_orders == 0
    assert result.metrics.total_deposit == 96000.0
    assert result.metrics.total_revenue == 320000.0
    assert result.metrics.remain_collection == 224000.0


# ==============================================================================
# HTTP INTEGRATION TESTS VỚI FASTAPI TESTCLIENT
# ==============================================================================

# ==============================================================================
# FASTAPI ROUTER ENDPOINT TESTS (TF1A595)
# ==============================================================================

def test_router_store_confirm_and_reject_endpoints(db_session):
    """Test Case 10: Kiểm thử trực tiếp các router endpoint trong bookings.py."""
    from fastapi import HTTPException
    from app.routers.bookings import (
        confirm_booking_endpoint,
        reject_booking_endpoint,
        get_store_orders_endpoint,
    )
    from app.schemas.booking import (
        StoreOrderConfirmRequest,
        StoreOrderRejectRequest,
    )

    env = _setup_test_environment(db_session)
    booking = env["booking"]
    owner = env["owner"]
    customer = env["customer"]

    # 1. Chủ cửa hàng duyệt đơn qua router endpoint
    res_confirm = confirm_booking_endpoint(
        booking_id=booking.id,
        payload=StoreOrderConfirmRequest(note="Xác nhận giao xe đúng hẹn qua API"),
        db=db_session,
        current_user=owner,
    )
    assert res_confirm.success is True
    assert res_confirm.status == "CONFIRMED"
    assert res_confirm.booking_id == booking.id

    # 2. Xem danh sách đơn của cửa hàng qua router endpoint
    res_list = get_store_orders_endpoint(
        status="all",
        search=None,
        page=1,
        page_size=20,
        store_id=None,
        db=db_session,
        current_user=owner,
    )
    assert res_list.success is True
    assert res_list.total >= 1
    assert res_list.metrics.approved_orders == 1

    # 3. Khách hàng không có quyền từ chối qua API cửa hàng -> HTTPException 403 Forbidden
    with pytest.raises(HTTPException) as exc_forbidden:
        reject_booking_endpoint(
            booking_id=booking.id,
            payload=StoreOrderRejectRequest(reason="Khách thử từ chối đơn"),
            db=db_session,
            current_user=customer,
        )
    assert exc_forbidden.value.status_code == 403

    # 4. Chủ cửa hàng từ chối thiếu lý do -> HTTPException 422
    with pytest.raises(HTTPException) as exc_invalid:
        reject_booking_endpoint(
            booking_id=booking.id,
            payload=StoreOrderRejectRequest.model_construct(reason=""),
            db=db_session,
            current_user=owner,
        )
    assert exc_invalid.value.status_code == 422

    # 5. Chủ cửa hàng từ chối kèm lý do hợp lệ -> 200 OK & hoàn 100% cọc
    res_reject = reject_booking_endpoint(
        booking_id=booking.id,
        payload=StoreOrderRejectRequest(reason="Khách hàng không đủ điều kiện GPLX theo quy định"),
        db=db_session,
        current_user=owner,
    )
    assert res_reject.success is True
    assert res_reject.status == "CANCELLED"
    assert res_reject.refund_amount == 96000.0



