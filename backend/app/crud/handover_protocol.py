"""Module xử lý nghiệp vụ Biên bản Giao/Nhận xe (Handover Protocol).

Đáp ứng các nguyên tắc bảo mật và nghiệp vụ chuẩn thực tế:
1. Tách riêng CHECK_OUT (giao xe) và CHECK_IN (nhận lại xe) thành 2 bản ghi riêng biệt.
   Không ghi đè để lưu vết đối chiếu và bằng chứng giao/nhận xe độc lập.
2. Check-in chỉ COMPLETED khi chữ ký gửi ở lần check-in đủ cả hai bên (customer & staff).
3. Phân quyền chặt chẽ theo cửa hàng (Store Operator RBAC), mặc định từ chối (default deny).
4. Không tin cậy ID từ payload: customer_id, store_agent_id lấy từ booking và JWT token.
5. Upload an toàn: map extension từ MIME type, kiểm tra toàn bộ file trước khi lưu đĩa,
   dùng UUID đầy đủ, chống tấn công file traversal & DoS dung lượng.
6. Toàn vẹn dữ liệu: bắt lỗi trùng mã biên bản (409 Conflict), chặn ký lại khi đã COMPLETED.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Tuple

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.booking import Booking
from app.models.handover import (
    HandoverMedia,
    HandoverProtocol,
    HandoverStatus,
    MediaType,
    ProtocolType,
    SignerRole,
)
from app.models.store import Store, StoreStaff
from app.models.user import User
from app.models.vehicle import Vehicle, VehicleStatusHistory
from app.crud.booking_status_history import record_booking_status_change
from app.schemas.handover import (
    HandoverCheckinCreate,
    HandoverProtocolCreate,
    HandoverSignRequest,
    PhotoConfirmationRequest,
    PhotoConfirmationResponse,
)

logger = logging.getLogger("ridehub.handover")

# Thư mục lưu trữ media
_UPLOAD_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "frontend", "uploads", "handover")
)

# MIME type được phép và ánh xạ sang đuôi file chuẩn (không tin đuôi từ client)
_MIME_TO_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "application/pdf": ".pdf",
}

# Giới hạn kích thước một file: 10 MB
_MAX_FILE_SIZE = 10 * 1024 * 1024


# ---------------------------------------------------------------------------
# RBAC Helpers
# ---------------------------------------------------------------------------

def _is_store_operator(user: User, booking: Optional[Booking], db: Session) -> bool:
    """Kiểm tra quyền quản lý cửa hàng (admin, store_owner, store_staff ACTIVE).
    
    NGUYÊN TẮC BẢO MẬT: Mặc định từ chối (Default Deny), không có fallback True.
    """
    if not user:
        return False

    role = (user.role or "").lower()
    if role == "admin":
        return True

    # Nếu có booking cụ thể -> kiểm tra xem user có thuộc store sở hữu booking đó không
    if booking and booking.store_id:
        store = db.query(Store).filter(Store.id == booking.store_id).first()
        if store and store.owner_user_id == user.id:
            return True

        staff = (
            db.query(StoreStaff)
            .filter(
                StoreStaff.store_id == booking.store_id,
                StoreStaff.user_id == user.id,
                StoreStaff.status == "ACTIVE",
            )
            .first()
        )
        if staff:
            return True

    # Mặc định từ chối
    return False


def _require_operator(user: User, booking: Optional[Booking], db: Session) -> None:
    """Bắt buộc người dùng phải là nhân viên / chủ của cửa hàng quản lý đơn, hoặc admin."""
    if not _is_store_operator(user, booking, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ nhân viên / chủ cửa hàng được phân công hoặc admin mới có quyền thực hiện.",
        )


def _get_booking_or_404(booking_id: int, db: Session) -> Booking:
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy đơn đặt xe #{booking_id}.",
        )
    return booking


def _get_protocol_or_404(protocol_id: int, db: Session) -> HandoverProtocol:
    p = db.query(HandoverProtocol).filter(HandoverProtocol.id == protocol_id).first()
    if not p:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy biên bản #{protocol_id}.",
        )
    return p


# ---------------------------------------------------------------------------
# 1. Tạo biên bản CHECK_OUT (Giao xe)
# ---------------------------------------------------------------------------

def create_handover_protocol(
    payload: HandoverProtocolCreate,
    actor: User,
    db: Session,
) -> HandoverProtocol:
    """Tạo biên bản giao xe mới (Check-out).

    - Lấy thông tin khách, nhân viên từ booking và token đăng nhập, không tin payload.
    - Bắt IntegrityError khi trùng mã biên bản.
    """
    booking = _get_booking_or_404(payload.booking_id, db)
    _require_operator(actor, booking, db)

    # Chuyển Pydantic models sang JSON-compatible dicts
    damage_json = (
        [d.model_dump() for d in payload.damage_points] if payload.damage_points else None
    )
    checklist_json = (
        [c.model_dump() for c in payload.checklist_data] if payload.checklist_data else None
    )

    # Lấy thông tin khách hàng từ booking/user liên kết
    cust_id = booking.customer_id
    cust_user = db.query(User).filter(User.id == cust_id).first() if cust_id else None
    customer_name = getattr(payload, "customer_name", None) or (cust_user.full_name if (cust_user and cust_user.full_name) else "Khách thuê")
    customer_phone = getattr(payload, "customer_phone", None) or (cust_user.phone if (cust_user and cust_user.phone) else "")
    customer_cccd = getattr(payload, "customer_cccd", None) or getattr(cust_user, "cccd_number", None) or ""
    customer_license = getattr(payload, "customer_license", None) or getattr(cust_user, "license_number", None) or ""

    is_signed = bool(payload.customer_signature and payload.staff_signature)

    protocol = HandoverProtocol(
        protocol_code=payload.protocol_code,
        booking_id=booking.id,
        protocol_type=ProtocolType.CHECK_OUT.value,
        store_agent_id=actor.id,
        store_agent_name=actor.full_name or "Nhân viên bàn giao",
        store_agent_phone=actor.phone,
        customer_id=cust_id,
        customer_name=customer_name,
        customer_cccd=customer_cccd,
        customer_phone=customer_phone,
        customer_license=customer_license,
        handover_location=payload.handover_location,
        vehicle_id=booking.vehicle_id,
        vehicle_name=payload.vehicle_name,
        license_plate=payload.license_plate,
        vehicle_category=payload.vehicle_category,
        odo_checkout=payload.odo_checkout,
        fuel_checkout=payload.fuel_checkout,
        free_km_limit=payload.free_km_limit,
        damage_points=damage_json,
        checklist_data=checklist_json,
        deposit_original=payload.deposit_original or booking.deposit_amount or Decimal(0),
        customer_signature=payload.customer_signature,
        staff_signature=payload.staff_signature,
        signed_at=datetime.now() if is_signed else None,
        status=HandoverStatus.COMPLETED.value if is_signed else HandoverStatus.DRAFT.value,
        notes=payload.notes,
    )

    db.add(protocol)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Mã biên bản '{payload.protocol_code}' đã tồn tại trên hệ thống.",
        )
    db.refresh(protocol)

    logger.info(
        "[Handover] Tạo biên bản CHECK_OUT %s cho booking #%d bởi user #%d",
        protocol.protocol_code,
        protocol.booking_id,
        actor.id,
    )
    return protocol


# ---------------------------------------------------------------------------
# 2. Tạo biên bản CHECK_IN (Nhận lại xe) — BẢN GHI RIÊNG BIỆT
# ---------------------------------------------------------------------------

def create_checkin_protocol(
    payload: HandoverCheckinCreate,
    actor: User,
    db: Session,
) -> HandoverProtocol:
    """Tạo biên bản nhận lại xe (Check-in) riêng biệt khi khách trả xe.

    - Không ghi đè lên biên bản CHECK_OUT cũ.
    - Tự động liên kết với biên bản CHECK_OUT để lấy số ODO xuất phát và tiền cọc gốc.
    - Check-in CHỈ COMPLETED khi cả 2 chữ ký gửi ở lần này đều đầy đủ.
    """
    booking = _get_booking_or_404(payload.booking_id, db)
    _require_operator(actor, booking, db)

    # Tìm biên bản CHECK_OUT trước đó để đối chiếu ODO và cọc
    checkout_protocol = (
        db.query(HandoverProtocol)
        .filter(
            HandoverProtocol.booking_id == booking.id,
            HandoverProtocol.protocol_type == ProtocolType.CHECK_OUT.value,
        )
        .order_by(HandoverProtocol.id.desc())
        .first()
    )

    odo_out = checkout_protocol.odo_checkout if checkout_protocol else 0
    deposit_orig = (
        payload.deposit_original
        or (checkout_protocol.deposit_original if checkout_protocol else booking.deposit_amount)
        or Decimal(0)
    )
    free_km = checkout_protocol.free_km_limit if checkout_protocol else 0

    damage_json = (
        [d.model_dump() for d in payload.damage_points] if payload.damage_points else None
    )
    checklist_json = (
        [c.model_dump() for c in payload.checklist_data] if payload.checklist_data else None
    )

    # Lấy thông tin khách hàng
    cust_id = booking.customer_id
    cust_user = db.query(User).filter(User.id == cust_id).first() if cust_id else None
    customer_name = cust_user.full_name if (cust_user and cust_user.full_name) else (checkout_protocol.customer_name if checkout_protocol else "Khách thuê")
    customer_phone = cust_user.phone if (cust_user and cust_user.phone) else (checkout_protocol.customer_phone if checkout_protocol else "")
    customer_cccd = checkout_protocol.customer_cccd if checkout_protocol else ""
    customer_license = checkout_protocol.customer_license if checkout_protocol else ""

    # Kiểm tra chữ ký: Chỉ COMPLETED khi chữ ký gửi ở lần check-in này đủ cả hai bên
    is_signed = bool(payload.customer_signature and payload.staff_signature)

    checkin_protocol = HandoverProtocol(
        protocol_code=payload.protocol_code,
        booking_id=booking.id,
        protocol_type=ProtocolType.CHECK_IN.value,
        store_agent_id=actor.id,
        store_agent_name=actor.full_name or "Nhân viên nhận xe",
        store_agent_phone=actor.phone,
        customer_id=cust_id,
        customer_name=customer_name,
        customer_cccd=customer_cccd,
        customer_phone=customer_phone,
        customer_license=customer_license,
        handover_location=payload.handover_location or (checkout_protocol.handover_location if checkout_protocol else "Cửa hàng"),
        vehicle_id=booking.vehicle_id,
        vehicle_name=checkout_protocol.vehicle_name if checkout_protocol else "Xe thuê",
        license_plate=checkout_protocol.license_plate if checkout_protocol else "",
        vehicle_category=checkout_protocol.vehicle_category if checkout_protocol else "CAR",
        odo_checkout=odo_out,
        odo_checkin=payload.odo_checkin,
        fuel_checkout=checkout_protocol.fuel_checkout if checkout_protocol else "FULL",
        fuel_checkin=payload.fuel_checkin,
        free_km_limit=free_km,
        damage_points=damage_json,
        checklist_data=checklist_json,
        deposit_original=deposit_orig,
        fee_overtime=payload.fee_overtime or Decimal(0),
        fee_excess_km=payload.fee_excess_km or Decimal(0),
        fee_fuel=payload.fee_fuel or Decimal(0),
        fee_cleaning=payload.fee_cleaning or Decimal(0),
        fee_damage=payload.fee_damage or Decimal(0),
        hold_fine_deposit=payload.hold_fine_deposit or Decimal(0),
        refund_immediate=payload.refund_immediate or Decimal(0),
        customer_signature=payload.customer_signature,
        staff_signature=payload.staff_signature,
        signed_at=datetime.now() if is_signed else None,
        status=HandoverStatus.COMPLETED.value if is_signed else HandoverStatus.DRAFT.value,
        notes=payload.notes,
    )

    db.add(checkin_protocol)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Mã biên bản '{payload.protocol_code}' đã tồn tại trên hệ thống.",
        )
    db.refresh(checkin_protocol)

    logger.info(
        "[Handover] Tạo biên bản CHECK_IN %s cho booking #%d bởi user #%d (status=%s)",
        checkin_protocol.protocol_code,
        checkin_protocol.booking_id,
        actor.id,
        checkin_protocol.status,
    )
    return checkin_protocol


# Backward-compatible alias
update_checkin_protocol = create_checkin_protocol


# ---------------------------------------------------------------------------
# 3. Ký biên bản điện tử
# ---------------------------------------------------------------------------

def sign_protocol(
    protocol_id: int,
    payload: HandoverSignRequest,
    actor: User,
    db: Session,
) -> HandoverProtocol:
    """Ký biên bản bởi một bên (CUSTOMER hoặc STAFF).

    - Chặn ký lại khi biên bản đã COMPLETED.
    - Chặn ký khi booking không tồn tại.
    - STAFF: phải là operator của cửa hàng quản lý booking.
    - CUSTOMER: phải là khách của booking.
    - Khi cả 2 đã ký -> COMPLETED, ghi nhận signed_at.
    """
    protocol = _get_protocol_or_404(protocol_id, db)

    # Chặn ký lại khi đã COMPLETED
    if protocol.status == HandoverStatus.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Biên bản đã hoàn tất và đã đủ chữ ký của hai bên, không thể ký thêm.",
        )

    booking = db.query(Booking).filter(Booking.id == protocol.booking_id).first()
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Đơn đặt xe liên kết không tồn tại, không thể ký biên bản.",
        )

    if payload.signer == SignerRole.STAFF.value:
        _require_operator(actor, booking, db)
        protocol.staff_signature = payload.signature
        protocol.store_agent_id = actor.id
        protocol.store_agent_name = actor.full_name or protocol.store_agent_name
    elif payload.signer == SignerRole.CUSTOMER.value:
        role = (actor.role or "").lower()
        if role != "admin" and booking.customer_id != actor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Chỉ chính khách thuê của đơn này hoặc admin mới có quyền ký phần khách.",
            )
        protocol.customer_signature = payload.signature
        protocol.customer_id = actor.id

    # Nếu cả hai bên đã ký -> chuyển COMPLETED
    if protocol.customer_signature and protocol.staff_signature:
        protocol.status = HandoverStatus.COMPLETED.value
        protocol.signed_at = datetime.now()

    db.commit()
    db.refresh(protocol)

    logger.info(
        "[Handover] Ký biên bản #%d bởi %s (user #%d) -> status=%s",
        protocol.id,
        payload.signer,
        actor.id,
        protocol.status,
    )
    return protocol


# ---------------------------------------------------------------------------
# 4. Upload ảnh xe / ảnh biên bản đã ký
# ---------------------------------------------------------------------------

def upload_handover_media(
    protocol_id: int,
    files: List[UploadFile],
    media_type: str,
    actor: User,
    db: Session,
    captions: Optional[List[str]] = None,
) -> List[HandoverMedia]:
    """Upload ảnh đính kèm biên bản (đồng bộ, an toàn, hiệu năng cao).

    An toàn:
    - Kiểm tra MIME type và map sang extension chuẩn (không tin đuôi file từ client).
    - Đọc trước và kiểm tra dung lượng toàn bộ file trước khi lưu bất kỳ file nào vào ổ đĩa.
    - Dùng UUID4 đầy đủ cho tên file.
    """
    valid_types = {m.value for m in MediaType}
    if media_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"media_type không hợp lệ. Phải là: {', '.join(sorted(valid_types))}",
        )

    protocol = _get_protocol_or_404(protocol_id, db)
    booking = db.query(Booking).filter(Booking.id == protocol.booking_id).first()
    _require_operator(actor, booking, db)

    # 1. Đọc và kiểm tra toàn bộ file trong bộ nhớ trước
    file_buffers: List[Tuple[UploadFile, bytes, str]] = []
    for file in files:
        content_type = file.content_type or ""
        if content_type not in _MIME_TO_EXT:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"File '{file.filename}': định dạng '{content_type}' không được hỗ trợ. "
                       f"Chỉ chấp nhận: {', '.join(sorted(_MIME_TO_EXT.keys()))}",
            )

        # Đọc qua file handle nội bộ
        file_obj = getattr(file, "file", file)
        content = file_obj.read(_MAX_FILE_SIZE + 1)
        if len(content) > _MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File '{file.filename}' vượt quá giới hạn 10 MB.",
            )

        file_buffers.append((file, content, content_type))

    # 2. Toàn bộ file đều hợp lệ -> bắt đầu ghi đĩa và tạo bản ghi DB
    os.makedirs(_UPLOAD_DIR, exist_ok=True)
    saved: List[HandoverMedia] = []

    existing_count = (
        db.query(HandoverMedia)
        .filter(
            HandoverMedia.protocol_id == protocol_id,
            HandoverMedia.media_type == media_type,
        )
        .count()
    )

    for idx, (file, content, content_type) in enumerate(file_buffers):
        ext = _MIME_TO_EXT[content_type]
        safe_filename = f"{uuid.uuid4().hex}_{media_type.lower()}{ext}"
        physical_path = os.path.join(_UPLOAD_DIR, safe_filename)

        with open(physical_path, "wb") as f:
            f.write(content)

        public_url = f"/frontend/uploads/handover/{safe_filename}"
        caption = captions[idx] if (captions and idx < len(captions)) else None
        is_primary = (existing_count == 0 and idx == 0)

        media_record = HandoverMedia(
            protocol_id=protocol_id,
            media_type=media_type,
            file_url=public_url,
            file_name=file.filename,
            file_size=len(content),
            mime_type=content_type,
            caption=caption,
            sort_order=existing_count + idx,
            is_primary=is_primary,
            uploaded_by_id=actor.id,
        )
        db.add(media_record)
        saved.append(media_record)

    db.commit()
    for m in saved:
        db.refresh(m)

    return saved


# ---------------------------------------------------------------------------
# 5. Xoá ảnh đính kèm
# ---------------------------------------------------------------------------

def delete_handover_media(
    media_id: int,
    actor: User,
    db: Session,
) -> dict:
    """Xoá một ảnh đính kèm biên bản và file vật lý tương ứng.
    
    Lấy file_url TRƯỚC khi gọi db.delete để tránh detached instance error.
    """
    media = db.query(HandoverMedia).filter(HandoverMedia.id == media_id).first()
    if not media:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy ảnh #{media_id}.",
        )

    protocol = _get_protocol_or_404(media.protocol_id, db)
    booking = db.query(Booking).filter(Booking.id == protocol.booking_id).first()
    _require_operator(actor, booking, db)

    file_url = media.file_url

    # Xoá bản ghi khỏi DB trước
    db.delete(media)
    db.commit()

    # Xoá file vật lý sau khi commit thành công
    if file_url.startswith("/frontend/uploads/handover/"):
        file_name = file_url.split("/")[-1]
        physical_path = os.path.join(_UPLOAD_DIR, file_name)
        if os.path.exists(physical_path):
            try:
                os.remove(physical_path)
            except OSError as e:
                logger.warning("[Handover] Không thể xoá file vật lý %s: %s", physical_path, e)

    return {"deleted_media_id": media_id, "file_url": file_url}


# ---------------------------------------------------------------------------
# 6. Xem chi tiết & Danh sách có phân quyền theo cửa hàng
# ---------------------------------------------------------------------------

def get_protocol_detail(
    protocol_id: int,
    actor: User,
    db: Session,
) -> HandoverProtocol:
    """Lấy chi tiết biên bản kèm media.
    
    - Khách chỉ được xem biên bản của chính đơn mình.
    - Nhân viên/chủ cửa hàng chỉ được xem biên bản thuộc cửa hàng mình quản lý.
    - Admin xem được tất cả.
    """
    protocol = _get_protocol_or_404(protocol_id, db)
    booking = db.query(Booking).filter(Booking.id == protocol.booking_id).first()

    role = (actor.role or "").lower()
    if role == "admin":
        return protocol

    if booking and booking.customer_id == actor.id:
        return protocol

    if booking and _is_store_operator(actor, booking, db):
        return protocol

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Bạn không có quyền truy cập biên bản này.",
    )


def list_protocols_by_booking(
    booking_id: int,
    actor: User,
    db: Session,
) -> List[HandoverProtocol]:
    """Lấy danh sách biên bản của một đơn đặt xe (CHECK_OUT & CHECK_IN)."""
    booking = _get_booking_or_404(booking_id, db)

    role = (actor.role or "").lower()
    if role != "admin":
        if booking.customer_id != actor.id and not _is_store_operator(actor, booking, db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền xem biên bản của đơn đặt xe này.",
            )

    return (
        db.query(HandoverProtocol)
        .filter(HandoverProtocol.booking_id == booking_id)
        .order_by(HandoverProtocol.id.asc())
        .all()
    )


# ---------------------------------------------------------------------------
# Helper: Tính toán tóm tắt (phụ phí, km vượt sau khi trừ km miễn phí)
# ---------------------------------------------------------------------------

def compute_summary(protocol: HandoverProtocol) -> dict:
    """Tính toán nhanh tổng phụ phí và km vượt thực tế."""
    total_fees = (
        (protocol.fee_overtime or Decimal(0))
        + (protocol.fee_excess_km or Decimal(0))
        + (protocol.fee_fuel or Decimal(0))
        + (protocol.fee_cleaning or Decimal(0))
        + (protocol.fee_damage or Decimal(0))
    )

    excess_km = None
    if protocol.odo_checkin is not None and protocol.odo_checkout is not None:
        raw_diff = protocol.odo_checkin - protocol.odo_checkout
        free_km = protocol.free_km_limit or 0
        excess_km = max(0, raw_diff - free_km)

    is_fully_signed = bool(protocol.customer_signature and protocol.staff_signature)

    return {
        "total_extra_fees": total_fees,
        "excess_km": excess_km,
        "is_fully_signed": is_fully_signed,
    }


# ---------------------------------------------------------------------------
# 7. Xác nhận ảnh giao/nhận xe của 2 bên & Tự động chuyển trạng thái xe, đơn
# ---------------------------------------------------------------------------

def confirm_handover_photos(
    protocol_id: int,
    payload: PhotoConfirmationRequest,
    actor: User,
    db: Session,
) -> dict:
    """Xác nhận ảnh và tình trạng giao/nhận xe từ một bên (Khách thuê hoặc Nhân viên/Cửa hàng).
    
    Khi CẢ HAI BÊN đã xác nhận ảnh:
    - protocol.both_confirmed = True, protocol.status = COMPLETED.
    - CHECK_OUT: Booking CONFIRMED -> IN_PROGRESS, Vehicle AVAILABLE -> RENTED.
    - CHECK_IN: Booking IN_PROGRESS -> COMPLETED, Vehicle RENTED -> AVAILABLE (hoặc MAINTENANCE nếu có hỏng).
    - Tự động ghi nhật ký trạng thái BookingStatusHistory và VehicleStatusHistory.
    """
    protocol = _get_protocol_or_404(protocol_id, db)
    booking = _get_booking_or_404(protocol.booking_id, db)

    is_customer = (booking.customer_id == actor.id)
    is_operator = _is_store_operator(actor, booking, db)
    role = (actor.role or "").lower()

    if not is_customer and not is_operator and role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ khách thuê của đơn hoặc nhân viên phụ trách cửa hàng mới có quyền xác nhận ảnh.",
        )

    # Chặn xác nhận lại khi hai bên đã xác nhận xong
    if protocol.both_confirmed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Hai bên đã xác nhận ảnh, biên bản đã hoàn tất, không thể xác nhận lại.",
        )

     # Chỉ cho xác nhận khi booking đang ở đúng trạng thái
    expected_booking_status = (
        "CONFIRMED" if protocol.protocol_type == ProtocolType.CHECK_OUT.value else "IN_PROGRESS"
    )
    current_booking_status = getattr(booking.status, "value", booking.status)
    if str(current_booking_status) != expected_booking_status:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Đơn đang ở trạng thái {current_booking_status}, cần {expected_booking_status} để xác nhận ảnh.",
        )

    # Ghi nhận theo vai trò người gọi
    if is_customer:
        protocol.customer_confirmed = payload.confirmed
        protocol.customer_confirmed_at = datetime.now() if payload.confirmed else None
        protocol.customer_confirm_note = payload.note
    elif is_operator or role == "admin":
        protocol.staff_confirmed = payload.confirmed
        protocol.staff_confirmed_at = datetime.now() if payload.confirmed else None
        protocol.staff_confirm_note = payload.note

    vehicle = db.query(Vehicle).filter(Vehicle.id == booking.vehicle_id).first() if booking.vehicle_id else None
    actor_name = actor.full_name or "SYSTEM"
    status_msg = "Đã ghi nhận xác nhận ảnh từ bạn. Đang chờ đối tác xác nhận để hoàn tất bàn giao."

    # KIỂM TRA ĐIỀU KIỆN CẢ HAI BÊN ĐÃ XÁC NHẬN
    if protocol.customer_confirmed and protocol.staff_confirmed:
        protocol.both_confirmed = True
        protocol.both_confirmed_at = datetime.now()
        protocol.status = HandoverStatus.COMPLETED.value

        if protocol.protocol_type == ProtocolType.CHECK_OUT.value:
            # 1. GIAO XE THÀNH CÔNG: Chuyển đơn sang IN_PROGRESS, chuyển xe sang RENTED
            old_b_status = booking.status
            booking.status = "IN_PROGRESS"
            record_booking_status_change(
                db=db,
                booking=booking,
                from_status=old_b_status,
                to_status="IN_PROGRESS",
                changed_by="HANDOVER_CHECKOUT",
                changed_by_user_id=actor.id,
                reason="Cả khách thuê và cửa hàng đã xác nhận toàn bộ ảnh giao xe.",
            )

            if vehicle:
                old_v_status = vehicle.current_status
                vehicle.current_status = "RENTED"
                v_history = VehicleStatusHistory(
                    vehicle_id=vehicle.id,
                    from_status=old_v_status,
                    to_status="RENTED",
                    changed_by=actor_name,
                    reason="Khách đã nhận xe sau khi hai bên xác nhận ảnh bàn giao",
                    note=f"Booking #{booking.id}, Protocol {protocol.protocol_code}",
                )
                db.add(v_history)

            status_msg = "Cả hai bên đã xác nhận ảnh giao xe! Đơn hàng tự động chuyển sang IN_PROGRESS và xe chuyển sang RENTED."

        elif protocol.protocol_type == ProtocolType.CHECK_IN.value:
            # 2. NHẬN LẠI XE THÀNH CÔNG: Chuyển đơn sang COMPLETED, chuyển xe về AVAILABLE (hoặc MAINTENANCE)
            old_b_status = booking.status
            booking.status = "COMPLETED"
            record_booking_status_change(
                db=db,
                booking=booking,
                from_status=old_b_status,
                to_status="COMPLETED",
                changed_by="HANDOVER_CHECKIN",
                changed_by_user_id=actor.id,
                reason="Cả khách thuê và cửa hàng đã xác nhận toàn bộ ảnh nhận lại xe.",
            )

            if vehicle:
                old_v_status = vehicle.current_status
                # Nếu có phụ phí hư hại xe -> chuyển sang MAINTENANCE để kiểm tra sửa chữa
                new_v_status = "MAINTENANCE" if (protocol.fee_damage and protocol.fee_damage > 0) else "AVAILABLE"
                vehicle.current_status = new_v_status
                v_history = VehicleStatusHistory(
                    vehicle_id=vehicle.id,
                    from_status=old_v_status,
                    to_status=new_v_status,
                    changed_by=actor_name,
                    reason="Khách đã hoàn trả xe sau khi hai bên xác nhận ảnh",
                    note=f"Booking #{booking.id}, Protocol {protocol.protocol_code}",
                )
                db.add(v_history)

            status_msg = f"Cả hai bên đã xác nhận ảnh trả xe! Đơn hàng tự động chuyển sang COMPLETED và xe chuyển sang {vehicle.current_status if vehicle else 'AVAILABLE'}."

    db.commit()
    db.refresh(protocol)
    db.refresh(booking)
    if vehicle:
        db.refresh(vehicle)

    return {
        "protocol_id": protocol.id,
        "protocol_code": protocol.protocol_code,
        "protocol_type": protocol.protocol_type,
        "customer_confirmed": protocol.customer_confirmed,
        "customer_confirmed_at": protocol.customer_confirmed_at,
        "customer_confirm_note": protocol.customer_confirm_note,
        "staff_confirmed": protocol.staff_confirmed,
        "staff_confirmed_at": protocol.staff_confirmed_at,
        "staff_confirm_note": protocol.staff_confirm_note,
        "both_confirmed": protocol.both_confirmed,
        "both_confirmed_at": protocol.both_confirmed_at,
        "booking_id": booking.id,
        "booking_status": booking.status,
        "vehicle_id": vehicle.id if vehicle else None,
        "vehicle_status": vehicle.current_status if vehicle else None,
        "protocol_status": protocol.status,
        "message": status_msg,
    }

