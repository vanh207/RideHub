"""Router API Biên bản Giao/Nhận xe điện tử — Handover Protocol Module.

Hỗ trợ các luồng:
  POST   /api/handover/checkout                  Tạo biên bản giao xe (CHECK_OUT)
  POST   /api/handover/checkin                   Tạo biên bản nhận lại xe (CHECK_IN, bản ghi riêng)
  POST   /api/handover                           Alias tạo biên bản giao xe
  PUT    /api/handover/{id}/checkin              Alias cập nhật/tạo check-in
  GET    /api/handover                           Danh sách biên bản (hỗ trợ phân trang, lọc theo store/booking)
  GET    /api/handover/{id}                      Xem chi tiết biên bản kèm ảnh, chữ ký, checklist
  POST   /api/handover/{id}/sign                 Ký biên bản điện tử (CUSTOMER hoặc STAFF)
  POST   /api/handover/{id}/media                Upload ảnh xe / ảnh biên bản đã ký
  DELETE /api/handover/media/{media_id}          Xoá ảnh đính kèm
  GET    /api/bookings/{booking_id}/handover     Lấy cả 2 biên bản (CHECK_OUT & CHECK_IN) của một đơn
"""
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
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
from app.db.session import get_db
from app.models.booking import Booking
from app.models.handover import HandoverProtocol as HP, ProtocolType
from app.models.store import Store, StoreStaff
from app.models.user import User
from app.schemas.handover import (
    HandoverCheckinCreate,
    HandoverMediaItem,
    HandoverProtocolCreate,
    HandoverProtocolResponse,
    HandoverSignRequest,
    PaginatedHandoverResponse,
    PhotoConfirmationRequest,
    PhotoConfirmationResponse,
)

router = APIRouter(prefix="/handover", tags=["Handover Protocol — Biên bản Giao/Nhận xe"])


def _build_response(protocol: HP, db: Session) -> HandoverProtocolResponse:
    """Ghép thêm các trường tính toán tóm tắt vào response."""
    summary = compute_summary(protocol)
    data = HandoverProtocolResponse.model_validate(protocol)
    data.total_extra_fees = summary["total_extra_fees"]
    data.excess_km = summary["excess_km"]
    data.is_fully_signed = summary["is_fully_signed"]
    return data


# ---------------------------------------------------------------------------
# 1. Tạo biên bản Giao xe (CHECK_OUT)
# ---------------------------------------------------------------------------

@router.post(
    "/checkout",
    response_model=HandoverProtocolResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo biên bản giao xe (Check-out)",
)
@router.post(
    "",
    response_model=HandoverProtocolResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo biên bản giao xe (Check-out, default endpoint)",
)
def api_create_checkout(
    payload: HandoverProtocolCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    """Tạo biên bản giao xe ban đầu (Check-out).

    - Ghi nhận: ODO xuất phát, mức nhiên liệu, checklist ban đầu, sơ đồ vết xước hiện có.
    - Chữ ký: có thể ký ngay hoặc ký sau qua endpoint /sign.
    - Phân quyền: chỉ nhân viên / chủ cửa hàng phụ trách đơn hoặc admin.
    """
    protocol = create_handover_protocol(payload, actor, db)
    return _build_response(protocol, db)


# ---------------------------------------------------------------------------
# 2. Tạo biên bản Nhận lại xe (CHECK_IN) — TÁCH BẢN GHI RIÊNG
# ---------------------------------------------------------------------------

@router.post(
    "/checkin",
    response_model=HandoverProtocolResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo biên bản nhận lại xe (Check-in, bản ghi độc lập)",
)
@router.put(
    "/{protocol_id}/checkin",
    response_model=HandoverProtocolResponse,
    summary="Cập nhật hoặc tạo biên bản Check-in (Backward-compatible)",
)
def api_create_checkin(
    payload: HandoverCheckinCreate,
    protocol_id: Optional[int] = None,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    """Tạo biên bản nhận lại xe (Check-in) riêng biệt khi khách hoàn trả xe.

    - Không làm mất biên bản CHECK_OUT cũ.
    - Đối chiếu ODO và cọc từ lần CHECK_OUT.
    - Check-in chỉ hoàn tất (COMPLETED) khi có đủ chữ ký của cả 2 bên.
    """
    protocol = create_checkin_protocol(payload, actor, db)
    return _build_response(protocol, db)


# ---------------------------------------------------------------------------
# 3. Ký biên bản điện tử
# ---------------------------------------------------------------------------

@router.post(
    "/{protocol_id}/sign",
    response_model=HandoverProtocolResponse,
    summary="Ký biên bản điện tử (Customer hoặc Staff)",
)
def api_sign_handover(
    protocol_id: int,
    payload: HandoverSignRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    """Ký biên bản số bởi từng bên:

    - `signer='STAFF'` -> Nhân viên cửa hàng hoặc admin ký.
    - `signer='CUSTOMER'` -> Chính khách thuê của đơn hoặc admin ký.
    - Chặn ký lại nếu biên bản đã COMPLETED.
    - Khi cả 2 bên đã ký -> status=COMPLETED và ghi nhận signed_at.
    """
    protocol = sign_protocol(protocol_id, payload, actor, db)
    return _build_response(protocol, db)


# ---------------------------------------------------------------------------
# 4. Upload ảnh xe & ảnh biên bản đã ký
# ---------------------------------------------------------------------------

@router.post(
    "/{protocol_id}/media",
    response_model=List[HandoverMediaItem],
    status_code=status.HTTP_201_CREATED,
    summary="Upload ảnh đính kèm biên bản (Ảnh xe 360°, Ảnh biên bản ký)",
)
def api_upload_media(
    protocol_id: int,
    files: List[UploadFile] = File(..., description="Danh sách file ảnh (JPEG, PNG, WEBP, PDF)"),
    media_type: str = Form("VEHICLE_PHOTO", description="VEHICLE_PHOTO | SIGNED_DOCUMENT | DAMAGE_PHOTO"),
    captions: Optional[str] = Form(None, description="Chú thích các ảnh, cách nhau bởi dấu |"),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    """Upload ảnh đính kèm an toàn:

    - Extension được suy ra từ Content-Type thực tế, không tin đuôi file client.
    - Đọc và kiểm tra kích thước tối đa 10 MB trước khi lưu đĩa.
    - Lưu với UUID đầy đủ.
    """
    caption_list = [c.strip() for c in captions.split("|")] if captions else None
    saved = upload_handover_media(
        protocol_id=protocol_id,
        files=files,
        media_type=media_type,
        actor=actor,
        db=db,
        captions=caption_list,
    )
    return [HandoverMediaItem.model_validate(m) for m in saved]


# ---------------------------------------------------------------------------
# 5. Xoá ảnh đính kèm
# ---------------------------------------------------------------------------

@router.delete(
    "/media/{media_id}",
    summary="Xoá một ảnh đính kèm biên bản",
)
def api_delete_media(
    media_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    """Xoá một ảnh đính kèm và file vật lý tương ứng."""
    return delete_handover_media(media_id, actor, db)


# ---------------------------------------------------------------------------
# 6. Xác nhận ảnh giao/nhận xe & Tự động chuyển trạng thái đơn hàng & xe
# ---------------------------------------------------------------------------

@router.post(
    "/{protocol_id}/confirm-photos",
    response_model=PhotoConfirmationResponse,
    summary="Xác nhận ảnh giao/nhận xe của hai bên và tự động chuyển trạng thái",
)
def api_confirm_photos(
    protocol_id: int,
    payload: PhotoConfirmationRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    """Xác nhận ảnh giao hoặc nhận xe từ Khách thuê hoặc Cửa hàng.

    - Khách thuê (Customer) gọi -> ghi nhận customer_confirmed = True.
    - Cửa hàng (Store Staff/Owner) gọi -> ghi nhận staff_confirmed = True.
    - Khi CẢ HAI BÊN đều đã xác nhận -> Tự động chuyển trạng thái đơn (Booking) và xe (Vehicle):
      * CHECK_OUT: Booking -> IN_PROGRESS, Vehicle -> RENTED.
      * CHECK_IN: Booking -> COMPLETED, Vehicle -> AVAILABLE (hoặc MAINTENANCE nếu có hỏng hóc).
      * Tự động ghi nhật ký trạng thái BookingStatusHistory và VehicleStatusHistory.
    """
    return confirm_handover_photos(protocol_id, payload, actor, db)


@router.get(
    "/{protocol_id}/confirm-status",
    summary="Xem trạng thái xác nhận ảnh của hai bên",
)
def api_get_confirm_status(
    protocol_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    """Xem tiến độ xác nhận ảnh của Khách và Cửa hàng."""
    protocol = get_protocol_detail(protocol_id, actor, db)
    booking = db.query(Booking).filter(Booking.id == protocol.booking_id).first()
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
        "booking_status": booking.status if booking else None,
        "protocol_status": protocol.status,
    }


# ---------------------------------------------------------------------------
# 7. Chi tiết biên bản
# ---------------------------------------------------------------------------

@router.get(
    "/{protocol_id}",
    response_model=HandoverProtocolResponse,
    summary="Xem chi tiết biên bản",
)
def api_get_handover(
    protocol_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    """Lấy chi tiết biên bản. Phân quyền chặt chẽ theo cửa hàng và khách thuê."""
    protocol = get_protocol_detail(protocol_id, actor, db)
    return _build_response(protocol, db)


# ---------------------------------------------------------------------------
# 7. Danh sách biên bản có phân trang
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=PaginatedHandoverResponse,
    summary="Danh sách biên bản giao nhận (có phân trang)",
)
def api_list_handover(
    booking_id: Optional[int] = Query(None, description="Lọc theo mã đặt chỗ"),
    protocol_type: Optional[str] = Query(None, description="CHECK_OUT hoặc CHECK_IN"),
    skip: int = Query(0, ge=0, description="Vị trí bắt đầu"),
    limit: int = Query(20, ge=1, le=100, description="Số lượng bản ghi tối đa"),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    """Lấy danh sách biên bản có phân quyền theo cửa hàng và phân trang."""
    role = (actor.role or "").lower()

    # Nếu truyền booking_id -> dùng hàm list_protocols_by_booking để kiểm tra quyền
    if booking_id is not None:
        protocols = list_protocols_by_booking(booking_id, actor, db)
        if protocol_type:
            protocols = [p for p in protocols if p.protocol_type == protocol_type]
        total = len(protocols)
        paged_items = protocols[skip : skip + limit]
        return PaginatedHandoverResponse(
            total=total,
            skip=skip,
            limit=limit,
            items=[_build_response(p, db) for p in paged_items],
        )

    # Nếu không truyền booking_id: chỉ admin hoặc operator cửa hàng mới được xem danh sách
    if role == "admin":
        query = db.query(HP)
    elif role in {"store_owner", "store_staff"}:
        # Lấy danh sách store_id mà user này quản lý
        owned_store_ids = [s.id for s in db.query(Store).filter(Store.owner_user_id == actor.id).all()]
        staff_store_ids = [
            st.store_id
            for st in db.query(StoreStaff).filter(StoreStaff.user_id == actor.id, StoreStaff.status == "ACTIVE").all()
        ]
        allowed_store_ids = list(set(owned_store_ids + staff_store_ids))

        if not allowed_store_ids:
            return PaginatedHandoverResponse(total=0, skip=skip, limit=limit, items=[])

        # Lọc các booking thuộc cửa hàng được phép
        allowed_booking_ids = [
            b.id for b in db.query(Booking.id).filter(Booking.store_id.in_(allowed_store_ids)).all()
        ]
        query = db.query(HP).filter(HP.booking_id.in_(allowed_booking_ids))
    else:
        # Customer: chỉ xem các biên bản của đơn của mình
        cust_booking_ids = [b.id for b in db.query(Booking.id).filter(Booking.customer_id == actor.id).all()]
        query = db.query(HP).filter(HP.booking_id.in_(cust_booking_ids))

    if protocol_type:
        query = query.filter(HP.protocol_type == protocol_type)

    total = query.count()
    items = query.order_by(HP.id.desc()).offset(skip).limit(limit).all()

    return PaginatedHandoverResponse(
        total=total,
        skip=skip,
        limit=limit,
        items=[_build_response(p, db) for p in items],
    )


# ---------------------------------------------------------------------------
# 8. Lấy toàn bộ biên bản của một booking (alias endpoint)
# ---------------------------------------------------------------------------

booking_handover_router = APIRouter(
    prefix="/bookings",
    tags=["Handover Protocol — Biên bản Giao/Nhận xe"],
)


@booking_handover_router.get(
    "/{booking_id}/handover",
    response_model=List[HandoverProtocolResponse],
    summary="Lấy cả 2 biên bản CHECK_OUT và CHECK_IN của một đơn",
)
def api_booking_handover_list(
    booking_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    """Trả về danh sách tất cả biên bản của một đơn đặt xe (CHECK_OUT & CHECK_IN độc lập)."""
    protocols = list_protocols_by_booking(booking_id, actor, db)
    return [_build_response(p, db) for p in protocols]
