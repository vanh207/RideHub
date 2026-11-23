"""Bộ kiểm thử toàn diện cho module Biên bản Giao/Nhận xe & Xác nhận ảnh chuyển trạng thái tự động.

Các Test Cases:
TC-HP-01: Tạo biên bản CHECK_OUT thành công bởi nhân viên/chủ cửa hàng.
TC-HP-02: Tạo biên bản thiếu trường bắt buộc -> Pydantic ValidationError (422).
TC-HP-03: Trùng protocol_code -> bắt IntegrityError trả về 409 Conflict.
TC-HP-04: Khách thuê không có quyền tạo biên bản giao xe -> 403 Forbidden.
TC-HP-05: Check-in tạo BẢN GHI RIÊNG, không ghi đè CHECK_OUT; cả 2 cùng tồn tại và tính đúng excess_km.
TC-HP-06: Check-in chỉ COMPLETED khi gửi đủ chữ ký cả 2 bên (customer & staff).
TC-HP-07: Chặn ký lại khi biên bản đã COMPLETED.
TC-HP-08: Phân quyền theo cửa hàng (Store Operator RBAC) — Nhân viên cửa hàng A không được can thiệp đơn của cửa hàng B.
TC-HP-09: Upload ảnh xe an toàn — đuôi file chuẩn suy ra từ Content-Type (MIME), không tin đuôi client.
TC-HP-10: Upload file sai định dạng (415); Xoá ảnh thành công (lấy file_url trước khi xoá); xoá lại -> 404.
TC-HP-11: Xác nhận ảnh Giao xe (CHECK_OUT): Khi cả khách và cửa hàng xác nhận -> Tự động chuyển Booking sang IN_PROGRESS, xe sang RENTED.
TC-HP-12: Xác nhận ảnh Trả xe (CHECK_IN): Khi cả hai xác nhận -> Tự động chuyển Booking sang COMPLETED, xe về AVAILABLE (hoặc MAINTENANCE nếu có hỏng).
TC-HP-13: Người ngoài cố xác nhận ảnh -> 403 Forbidden.
"""
from __future__ import annotations

import asyncio
import io
import os
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException, UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.datastructures import Headers

# Nạp TOÀN BỘ models trước để SQLAlchemy mapper biết tất cả class
import app.models  # noqa: F401

from app.db.session import Base
from app.models.booking import Booking, BookingStatusHistory
from app.models.handover import (
    HandoverMedia,
    HandoverProtocol,
    HandoverStatus,
    MediaType,
    ProtocolType,
    SignerRole,
)
from app.models.role import Role, UserRole
from app.models.store import Store, StoreStaff
from app.models.user import User
from app.models.vehicle import Vehicle, VehicleStatusHistory
from app.crud.handover_protocol import (
    compute_summary,
    confirm_handover_photos,
    create_checkin_protocol,
    create_handover_protocol,
    delete_handover_media,
    get_protocol_detail,
    list_protocols_by_booking,
    sign_protocol,
    upload_handover_media,
)
from app.schemas.handover import (
    ChecklistItem,
    DamagePoint,
    HandoverCheckinCreate,
    HandoverProtocolCreate,
    HandoverSignRequest,
    PhotoConfirmationRequest,
)

# ---------------------------------------------------------------------------
# SQLite in-memory DB cho test
# ---------------------------------------------------------------------------

SQLITE_URL = "sqlite://"

engine = create_engine(
    SQLITE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="module", autouse=True)
def create_tables():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


NOW = datetime.now().replace(second=0, microsecond=0)
OWNER_A_ID = 1
STAFF_A_ID = 2
CUSTOMER_ID = 3
ADMIN_ID = 4
OWNER_B_ID = 5
STRANGER_ID = 6


def _make_user(db, uid: int, email: str, role_code: str, status: str = "active") -> User:
    user = db.query(User).filter(User.id == uid).first()
    if not user:
        user = User(
            id=uid,
            email=email,
            full_name=f"User {role_code}",
            hashed_password="hash",
            phone=f"090000000{uid}",
            status=status,
        )
        db.add(user)
        db.flush()

    role = db.query(Role).filter(Role.code == role_code.upper()).first()
    if not role:
        role = Role(id=uid * 10, code=role_code.upper(), name=role_code)
        db.add(role)
        db.flush()

    ur = db.query(UserRole).filter(UserRole.user_id == uid, UserRole.role_id == role.id).first()
    if not ur:
        ur = UserRole(user_id=uid, role_id=role.id)
        db.add(ur)
        db.flush()
    return user


def _make_store_and_staff(db, store_id: int, owner: User, staff: User, store_name: str) -> Store:
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        store = Store(
            id=store_id,
            owner_user_id=owner.id,
            name=store_name,
            email=f"store{store_id}@test.com",
            phone="0901111111",
            address="123 Test St",
            city="HCM",
            status="APPROVED",
        )
        db.add(store)
        db.flush()

    if staff:
        st = db.query(StoreStaff).filter(StoreStaff.store_id == store_id, StoreStaff.user_id == staff.id).first()
        if not st:
            st = StoreStaff(store_id=store_id, user_id=staff.id, staff_role="STAFF", status="ACTIVE")
            db.add(st)
            db.flush()
    return store


def _make_booking(db, booking_id: int, cust_id: int, store_id: int) -> Booking:
    b = db.query(Booking).filter(Booking.id == booking_id).first()
    if not b:
        v = db.query(Vehicle).filter(Vehicle.id == store_id).first()
        if not v:
            v = Vehicle(
                id=store_id,
                store_id=store_id,
                vehicle_type="CAR",
                plate_number=f"51A-{store_id}99.99",
                brand="Toyota",
                model="Vios",
                price_per_day=Decimal("800000"),
                current_status="AVAILABLE",
            )
            db.add(v)
            db.flush()

        b = Booking(
            id=booking_id,
            customer_id=cust_id,
            vehicle_id=v.id,
            store_id=store_id,
            start_time=NOW,
            end_time=NOW + timedelta(days=2),
            status="CONFIRMED",
            rental_amount=Decimal("1600000"),
            deposit_amount=Decimal("2000000"),
            total_amount=Decimal("1600000"),
        )
        db.add(b)
        db.flush()
    return b


def _setup_test_db(db):
    owner_a = _make_user(db, OWNER_A_ID, "owner_a@test.com", "STORE_OWNER")
    staff_a = _make_user(db, STAFF_A_ID, "staff_a@test.com", "STORE_STAFF")
    customer = _make_user(db, CUSTOMER_ID, "customer@test.com", "CUSTOMER")
    _make_user(db, ADMIN_ID, "admin@test.com", "ADMIN")
    owner_b = _make_user(db, OWNER_B_ID, "owner_b@test.com", "STORE_OWNER")
    _make_user(db, STRANGER_ID, "stranger@test.com", "CUSTOMER")

    # Cửa hàng A (ID 1)
    _make_store_and_staff(db, 1, owner_a, staff_a, "GreenRide Q1")
    # Cửa hàng B (ID 2)
    _make_store_and_staff(db, 2, owner_b, None, "GreenRide Q7")

    # Booking 1 thuộc Store A, Booking 2 thuộc Store B
    _make_booking(db, 1, customer.id, 1)
    _make_booking(db, 2, customer.id, 2)
    db.commit()


@pytest.fixture()
def db():
    session = TestSession()
    try:
        _setup_test_db(session)
        yield session
    finally:
        session.close()


# ---------------------------------------------------------------------------
# TC-HP-01: Tạo biên bản CHECK_OUT thành công
# ---------------------------------------------------------------------------

def test_01_create_checkout_success(db):
    """TC-HP-01: Nhân viên cửa hàng tạo biên bản giao xe (CHECK_OUT) đầy đủ thông tin."""
    staff_a = db.query(User).filter(User.id == STAFF_A_ID).first()
    payload = HandoverProtocolCreate(
        protocol_code="BB-OUT-001",
        booking_id=1,
        protocol_type="CHECK_OUT",
        handover_location="Cửa hàng GreenRide Q1",
        vehicle_name="Toyota Vios 2023",
        license_plate="51A-199.99",
        customer_name="Nguyễn Văn Khách",
        customer_cccd="012345678901",
        customer_phone="0912345678",
        customer_license="B2-999888",
        odo_checkout=10000,
        fuel_checkout="FULL",
        free_km_limit=50,
        deposit_original=Decimal("2000000"),
        damage_points=[DamagePoint(x=10.0, y=20.0, label="Xước cản trước", color="orange")],
        checklist_data=[ChecklistItem(item="Đèn pha", ok=True)],
    )

    p = create_handover_protocol(payload, staff_a, db)

    assert p.id is not None
    assert p.protocol_code == "BB-OUT-001"
    assert p.protocol_type == ProtocolType.CHECK_OUT.value
    assert p.status == HandoverStatus.DRAFT.value
    assert p.odo_checkout == 10000
    assert p.free_km_limit == 50
    assert p.store_agent_id == staff_a.id
    assert p.customer_id == CUSTOMER_ID
    assert p.customer_cccd == "012345678901"


# ---------------------------------------------------------------------------
# TC-HP-02: Tạo biên bản thiếu trường bắt buộc -> 422
# ---------------------------------------------------------------------------

def test_02_create_missing_required_fields():
    """TC-HP-02: Thiếu handover_location, license_plate -> ValidationError."""
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        HandoverProtocolCreate(
            protocol_code="BB-FAIL",
            booking_id=1,
            vehicle_name="Vios",
        )


# ---------------------------------------------------------------------------
# TC-HP-03: Trùng protocol_code -> bắt IntegrityError trả 409
# ---------------------------------------------------------------------------

def test_03_duplicate_protocol_code(db):
    """TC-HP-03: Trùng mã protocol_code -> 409 Conflict."""
    staff_a = db.query(User).filter(User.id == STAFF_A_ID).first()
    payload = HandoverProtocolCreate(
        protocol_code="BB-OUT-UNIQUE",
        booking_id=1,
        handover_location="Cửa hàng",
        vehicle_name="Toyota Vios",
        license_plate="51A-199.99",
        odo_checkout=10000,
    )
    create_handover_protocol(payload, staff_a, db)

    with pytest.raises(HTTPException) as exc:
        create_handover_protocol(payload, staff_a, db)

    assert exc.value.status_code == 409
    assert "đã tồn tại" in exc.value.detail


# ---------------------------------------------------------------------------
# TC-HP-04: Khách thuê không được tạo biên bản -> 403
# ---------------------------------------------------------------------------

def test_04_customer_cannot_create(db):
    """TC-HP-04: Khách thuê cố tạo biên bản giao xe -> 403 Forbidden."""
    customer = db.query(User).filter(User.id == CUSTOMER_ID).first()
    payload = HandoverProtocolCreate(
        protocol_code="BB-OUT-CUST-FAIL",
        booking_id=1,
        handover_location="Cửa hàng",
        vehicle_name="Toyota Vios",
        license_plate="51A-199.99",
        odo_checkout=10000,
    )
    with pytest.raises(HTTPException) as exc:
        create_handover_protocol(payload, customer, db)

    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# TC-HP-05: Check-in tạo BẢN GHI RIÊNG, không đè CHECK_OUT; tính excess_km
# ---------------------------------------------------------------------------

def test_05_create_checkin_as_separate_record(db):
    """TC-HP-05: Tạo Check-in thành bản ghi mới riêng biệt, CHECK_OUT vẫn còn nguyên vẹn."""
    staff_a = db.query(User).filter(User.id == STAFF_A_ID).first()

    co_payload = HandoverProtocolCreate(
        protocol_code="BB-OUT-TC05",
        booking_id=1,
        handover_location="Cửa hàng Q1",
        vehicle_name="Toyota Vios",
        license_plate="51A-199.99",
        odo_checkout=10000,
        free_km_limit=50,
        deposit_original=Decimal("2000000"),
    )
    co_proto = create_handover_protocol(co_payload, staff_a, db)

    ci_payload = HandoverCheckinCreate(
        protocol_code="BB-IN-TC05",
        booking_id=1,
        odo_checkin=10300,
        fuel_checkin="1/2",
        fee_excess_km=Decimal("250000"),
        hold_fine_deposit=Decimal("250000"),
        refund_immediate=Decimal("1750000"),
    )
    ci_proto = create_checkin_protocol(ci_payload, staff_a, db)

    assert co_proto.id != ci_proto.id
    assert co_proto.protocol_type == ProtocolType.CHECK_OUT.value
    assert ci_proto.protocol_type == ProtocolType.CHECK_IN.value

    protos = list_protocols_by_booking(1, staff_a, db)
    assert len(protos) >= 2
    types = [p.protocol_type for p in protos]
    assert ProtocolType.CHECK_OUT.value in types
    assert ProtocolType.CHECK_IN.value in types

    summary = compute_summary(ci_proto)
    assert summary["excess_km"] == 250
    assert float(summary["total_extra_fees"]) == 250000.0


# ---------------------------------------------------------------------------
# TC-HP-06: Check-in chỉ COMPLETED khi chữ ký gửi ở lần check-in đủ 2 bên
# ---------------------------------------------------------------------------

def test_06_checkin_completed_only_when_both_signatures_provided(db):
    """TC-HP-06: Check-in chỉ COMPLETED khi có đủ chữ ký khách và nhân viên gửi trong payload check-in."""
    staff_a = db.query(User).filter(User.id == STAFF_A_ID).first()

    ci_draft = create_checkin_protocol(
        HandoverCheckinCreate(
            protocol_code="BB-IN-TC06-DRAFT",
            booking_id=1,
            odo_checkin=10100,
            fuel_checkin="FULL",
        ),
        staff_a,
        db,
    )
    assert ci_draft.status == HandoverStatus.DRAFT.value

    ci_completed = create_checkin_protocol(
        HandoverCheckinCreate(
            protocol_code="BB-IN-TC06-DONE",
            booking_id=1,
            odo_checkin=10100,
            fuel_checkin="FULL",
            customer_signature="data:image/png;base64," + "A" * 30,
            staff_signature="data:image/png;base64," + "B" * 30,
        ),
        staff_a,
        db,
    )
    assert ci_completed.status == HandoverStatus.COMPLETED.value
    assert ci_completed.signed_at is not None


# ---------------------------------------------------------------------------
# TC-HP-07: Chặn ký lại khi biên bản đã COMPLETED
# ---------------------------------------------------------------------------

def test_07_prevent_resigning_when_completed(db):
    """TC-HP-07: Biên bản đã COMPLETED thì không được phép ký thêm -> 400 Bad Request."""
    staff_a = db.query(User).filter(User.id == STAFF_A_ID).first()
    ci = create_checkin_protocol(
        HandoverCheckinCreate(
            protocol_code="BB-IN-TC07",
            booking_id=1,
            odo_checkin=10100,
            fuel_checkin="FULL",
            customer_signature="data:image/png;base64," + "A" * 30,
            staff_signature="data:image/png;base64," + "B" * 30,
        ),
        staff_a,
        db,
    )
    assert ci.status == HandoverStatus.COMPLETED.value

    req = HandoverSignRequest(signer="STAFF", signature="data:image/png;base64," + "C" * 30)
    with pytest.raises(HTTPException) as exc:
        sign_protocol(ci.id, req, staff_a, db)

    assert exc.value.status_code == 400
    assert "không thể ký thêm" in exc.value.detail


# ---------------------------------------------------------------------------
# TC-HP-08: Phân quyền theo cửa hàng (Store Operator RBAC)
# ---------------------------------------------------------------------------

def test_08_store_operator_isolation(db):
    """TC-HP-08: Nhân viên cửa hàng A không thể thao tác trên đơn của Cửa hàng B -> 403."""
    staff_a = db.query(User).filter(User.id == STAFF_A_ID).first()

    payload = HandoverProtocolCreate(
        protocol_code="BB-OUT-ILLEGAL-STORE",
        booking_id=2,  # Đơn của store B
        handover_location="Cửa hàng",
        vehicle_name="Toyota Vios",
        license_plate="51A-299.99",
        odo_checkout=5000,
    )
    with pytest.raises(HTTPException) as exc:
        create_handover_protocol(payload, staff_a, db)

    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# TC-HP-09: Upload ảnh xe — đuôi file suy ra từ MIME type (.jpg), an toàn
# ---------------------------------------------------------------------------

def test_09_upload_media_validation_and_mime_mapping(db, tmp_path, monkeypatch):
    """TC-HP-09: Upload ảnh với đuôi file gốc lung tung, hệ thống map chuẩn từ MIME type sang .jpg."""
    import app.crud.handover_protocol as crud_module
    monkeypatch.setattr(crud_module, "_UPLOAD_DIR", str(tmp_path))

    staff_a = db.query(User).filter(User.id == STAFF_A_ID).first()
    p = create_handover_protocol(
        HandoverProtocolCreate(
            protocol_code="BB-OUT-TC09",
            booking_id=1,
            handover_location="Cửa hàng",
            vehicle_name="Vios",
            license_plate="51A-199.99",
            odo_checkout=1000,
        ),
        staff_a,
        db,
    )

    fake_content = b"\xff\xd8\xff\xe0" + b"\x00" * 50
    upload = UploadFile(
        filename="attacker_trick.exe",
        file=io.BytesIO(fake_content),
        headers=Headers({"content-type": "image/jpeg"}),
    )

    saved = upload_handover_media(
        protocol_id=p.id,
        files=[upload],
        media_type="VEHICLE_PHOTO",
        actor=staff_a,
        db=db,
        captions=["Ảnh góc trái"],
    )

    assert len(saved) == 1
    media = saved[0]
    assert media.file_url.endswith(".jpg")
    assert media.mime_type == "image/jpeg"


# ---------------------------------------------------------------------------
# TC-HP-10: Upload file sai định dạng (415) & Xoá ảnh an toàn
# ---------------------------------------------------------------------------

def test_10_upload_invalid_mime_and_delete_media(db, tmp_path, monkeypatch):
    """TC-HP-10: File không thuộc whitelist bị từ chối 415; Xoá ảnh an toàn."""
    import app.crud.handover_protocol as crud_module
    monkeypatch.setattr(crud_module, "_UPLOAD_DIR", str(tmp_path))

    staff_a = db.query(User).filter(User.id == STAFF_A_ID).first()
    p = create_handover_protocol(
        HandoverProtocolCreate(
            protocol_code="BB-OUT-TC10",
            booking_id=1,
            handover_location="Cửa hàng",
            vehicle_name="Vios",
            license_plate="51A-199.99",
            odo_checkout=1000,
        ),
        staff_a,
        db,
    )

    bad_upload = UploadFile(
        filename="script.sh",
        file=io.BytesIO(b"echo hello"),
        headers=Headers({"content-type": "application/x-sh"}),
    )
    with pytest.raises(HTTPException) as exc:
        upload_handover_media(
            protocol_id=p.id,
            files=[bad_upload],
            media_type="VEHICLE_PHOTO",
            actor=staff_a,
            db=db,
        )
    assert exc.value.status_code == 415

    good_upload = UploadFile(
        filename="bien_ban.png",
        file=io.BytesIO(b"\x89PNG" + b"\x00" * 20),
        headers=Headers({"content-type": "image/png"}),
    )
    saved = upload_handover_media(
        protocol_id=p.id,
        files=[good_upload],
        media_type="SIGNED_DOCUMENT",
        actor=staff_a,
        db=db,
    )
    media_id = saved[0].id
    del_res = delete_handover_media(media_id, staff_a, db)
    assert del_res["deleted_media_id"] == media_id

    with pytest.raises(HTTPException) as exc_del:
        delete_handover_media(media_id, staff_a, db)
    assert exc_del.value.status_code == 404


# ---------------------------------------------------------------------------
# TC-HP-11: Xác nhận ảnh CHECK_OUT: tự động chuyển Booking sang IN_PROGRESS, xe sang RENTED
# ---------------------------------------------------------------------------

def test_11_confirm_photos_checkout_auto_transition_to_in_progress(db):
    """TC-HP-11: Cả hai bên xác nhận ảnh giao xe -> Tự động chuyển Booking sang IN_PROGRESS và xe sang RENTED."""
    staff_a = db.query(User).filter(User.id == STAFF_A_ID).first()
    customer = db.query(User).filter(User.id == CUSTOMER_ID).first()

    # 1. Tạo biên bản giao xe
    p = create_handover_protocol(
        HandoverProtocolCreate(
            protocol_code="BB-OUT-TC11",
            booking_id=1,
            handover_location="Cửa hàng",
            vehicle_name="Vios",
            license_plate="51A-199.99",
            odo_checkout=1000,
        ),
        staff_a,
        db,
    )

    booking = db.query(Booking).filter(Booking.id == 1).first()
    vehicle = db.query(Vehicle).filter(Vehicle.id == booking.vehicle_id).first()
    assert booking.status == "CONFIRMED"
    assert vehicle.current_status == "AVAILABLE"

    # 2. Khách xác nhận ảnh
    res_cust = confirm_handover_photos(
        protocol_id=p.id,
        payload=PhotoConfirmationRequest(confirmed=True, note="Khách đã kiểm tra 4 góc xe, đúng tình trạng."),
        actor=customer,
        db=db,
    )
    assert res_cust["customer_confirmed"] is True
    assert res_cust["staff_confirmed"] is False
    assert res_cust["both_confirmed"] is False
    # Chưa đủ 2 bên nên trạng thái booking vẫn giữ nguyên
    assert db.query(Booking).filter(Booking.id == 1).first().status == "CONFIRMED"

    # 3. Cửa hàng xác nhận ảnh -> ĐỦ HAI BÊN!
    res_staff = confirm_handover_photos(
        protocol_id=p.id,
        payload=PhotoConfirmationRequest(confirmed=True, note="Nhân viên đã bàn giao chìa khóa và kiểm tra ảnh."),
        actor=staff_a,
        db=db,
    )
    assert res_staff["customer_confirmed"] is True
    assert res_staff["staff_confirmed"] is True
    assert res_staff["both_confirmed"] is True
    assert res_staff["protocol_status"] == HandoverStatus.COMPLETED.value
    assert res_staff["booking_status"] == "IN_PROGRESS"
    assert res_staff["vehicle_status"] == "RENTED"

    # Kiểm tra DB thực tế
    b_updated = db.query(Booking).filter(Booking.id == 1).first()
    v_updated = db.query(Vehicle).filter(Vehicle.id == booking.vehicle_id).first()
    assert b_updated.status == "IN_PROGRESS"
    assert v_updated.current_status == "RENTED"

    # Kiểm tra lịch sử chuyển trạng thái BookingStatusHistory
    b_history = (
        db.query(BookingStatusHistory)
        .filter(BookingStatusHistory.booking_id == 1, BookingStatusHistory.to_status == "IN_PROGRESS")
        .first()
    )
    assert b_history is not None
    assert b_history.changed_by == "HANDOVER_CHECKOUT"


# ---------------------------------------------------------------------------
# TC-HP-12: Xác nhận ảnh CHECK_IN: tự động chuyển Booking sang COMPLETED, xe về AVAILABLE
# ---------------------------------------------------------------------------

def test_12_confirm_photos_checkin_auto_transition_to_completed(db):
    """TC-HP-12: Cả hai bên xác nhận ảnh trả xe -> Tự động chuyển Booking sang COMPLETED và xe về AVAILABLE."""
    staff_a = db.query(User).filter(User.id == STAFF_A_ID).first()
    customer = db.query(User).filter(User.id == CUSTOMER_ID).first()

    # Đặt booking sang IN_PROGRESS và xe sang RENTED trước khi trả xe
    booking = db.query(Booking).filter(Booking.id == 1).first()
    booking.status = "IN_PROGRESS"
    vehicle = db.query(Vehicle).filter(Vehicle.id == booking.vehicle_id).first()
    vehicle.current_status = "RENTED"
    db.commit()

    # Tạo biên bản nhận lại xe
    ci = create_checkin_protocol(
        HandoverCheckinCreate(
            protocol_code="BB-IN-TC12",
            booking_id=1,
            odo_checkin=10500,
            fuel_checkin="FULL",
            fee_damage=Decimal("0"),  # Không hư hại
            refund_immediate=Decimal("2000000"),
        ),
        staff_a,
        db,
    )

    # 1. Nhân viên xác nhận ảnh trả xe
    confirm_handover_photos(
        protocol_id=ci.id,
        payload=PhotoConfirmationRequest(confirmed=True, note="Xe nguyên vẹn, đủ xăng."),
        actor=staff_a,
        db=db,
    )

    # 2. Khách xác nhận ảnh trả xe -> ĐỦ HAI BÊN!
    res = confirm_handover_photos(
        protocol_id=ci.id,
        payload=PhotoConfirmationRequest(confirmed=True, note="Đồng ý kết quả kiểm tra nhận xe."),
        actor=customer,
        db=db,
    )

    assert res["both_confirmed"] is True
    assert res["booking_status"] == "COMPLETED"
    assert res["vehicle_status"] == "AVAILABLE"

    # Kiểm tra DB
    b_updated = db.query(Booking).filter(Booking.id == 1).first()
    v_updated = db.query(Vehicle).filter(Vehicle.id == booking.vehicle_id).first()
    assert b_updated.status == "COMPLETED"
    assert v_updated.current_status == "AVAILABLE"


# ---------------------------------------------------------------------------
# TC-HP-13: Người ngoài cố xác nhận ảnh -> 403 Forbidden
# ---------------------------------------------------------------------------

def test_13_unauthorized_user_cannot_confirm_photos(db):
    """TC-HP-13: User không liên quan cố gọi API xác nhận ảnh -> 403 Forbidden."""
    staff_a = db.query(User).filter(User.id == STAFF_A_ID).first()
    stranger = db.query(User).filter(User.id == STRANGER_ID).first()

    p = create_handover_protocol(
        HandoverProtocolCreate(
            protocol_code="BB-OUT-TC13",
            booking_id=1,
            handover_location="Cửa hàng",
            vehicle_name="Vios",
            license_plate="51A-199.99",
            odo_checkout=1000,
        ),
        staff_a,
        db,
    )

    with pytest.raises(HTTPException) as exc:
        confirm_handover_photos(
            protocol_id=p.id,
            payload=PhotoConfirmationRequest(confirmed=True, note="Xác nhận giả mạo"),
            actor=stranger,
            db=db,
        )

    assert exc.value.status_code == 403
