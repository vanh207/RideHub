"""Router quản lý gửi email thông báo đơn hàng và dịch vụ thông báo RideHub.
Hỗ trợ BackgroundTasks để gửi email bất đồng bộ không làm chậm phản hồi API.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.notification import Notification
from app.models.user import User
from app.services.email_service import email_service, MockEmailSender

router = APIRouter(prefix="/notifications", tags=["Notifications & Email Service"])

ROLE_ALIASES = {
    "store_staff": "store_owner",
    "operator": "admin",
}

DEFAULT_NOTIFICATIONS_BY_ROLE: Dict[str, List[Dict[str, Any]]] = {
    "customer": [
        {
            "type": "booking",
            "title": "Đặt xe thành công & giữ chỗ 30 phút",
            "body": "Đơn thuê xe của bạn đã được tạo. Vui lòng hoàn tất thanh toán cọc qua VietQR trước khi hết thời gian giữ chỗ.",
            "link": "trips.html",
            "is_read": False,
        },
        {
            "type": "payment",
            "title": "Chính sách hoàn cọc minh bạch 100%",
            "body": "Tiền cọc sẽ được hoàn tự động về tài khoản sau khi hoàn tất biên bản trả xe.",
            "link": "trips.html",
            "is_read": False,
        },
        {
            "type": "system",
            "title": "Hoàn tất hồ sơ eKYC",
            "body": "Cập nhật CCCD gắn chip và GPLX để được duyệt tự động khi nhận xe.",
            "link": "profile.html",
            "is_read": True,
        },
    ],
    "store_owner": [
        {
            "type": "booking",
            "title": "Có đơn đặt xe mới cần xác nhận",
            "body": "Khách hàng vừa đặt cọc đơn thuê xe. Kiểm tra và xác nhận lịch bàn giao ngay.",
            "link": "pages/store-orders.html",
            "is_read": False,
        },
        {
            "type": "alert",
            "title": "Lịch bàn giao xe sắp tới",
            "body": "Kiểm tra danh sách xe cần bàn giao và chuẩn bị biên bản Check-out 4 bước.",
            "link": "pages/handover.html",
            "is_read": False,
        },
        {
            "type": "payment",
            "title": "Quản lý lịch xe & doanh thu cửa hàng",
            "body": "Theo dõi trạng thái xe trống và lịch giao nhận tại cổng cửa hàng.",
            "link": "pages/vehicle_schedule.html",
            "is_read": True,
        },
    ],
    "admin": [
        {
            "type": "system",
            "title": "Phê duyệt đối tác mới",
            "body": "Kiểm tra các hồ sơ chủ cửa hàng và eKYC đang chờ Admin phê duyệt trên hệ thống.",
            "link": "profile.html#admin-reviews",
            "is_read": False,
        },
        {
            "type": "payment",
            "title": "Đối soát giao dịch bất thường",
            "body": "Theo dõi hàng chờ giao dịch VietQR, webhook và yêu cầu hoàn tiền cần xử lý.",
            "link": "pages/operations-anomalies.html",
            "is_read": False,
        },
        {
            "type": "alert",
            "title": "Cấu hình chính sách & Nhật ký Audit",
            "body": "Quản lý tham số giữ chỗ, đặt cọc, hoàn tiền và tra cứu lịch sử thao tác hệ thống.",
            "link": "pages/admin-policies-audit.html",
            "is_read": True,
        },
    ],
}


def _normalize_role(raw_role: Optional[str]) -> str:
    role = (raw_role or "customer").strip().lower()
    return ROLE_ALIASES.get(role, role)


def _format_relative_time(dt: Optional[datetime]) -> str:
    if not dt:
        return "Vừa xong"
    delta = max(0, int((datetime.now() - dt).total_seconds()))
    if delta < 60:
        return "Vừa xong"
    if delta < 3600:
        return f"{delta // 60} phút trước"
    if delta < 86400:
        return f"{delta // 3600} giờ trước"
    if delta < 172800:
        return "Hôm qua"
    return dt.strftime("%d/%m/%Y %H:%M")


def _ensure_role_notifications(db: Session, role: str) -> None:
    if role not in DEFAULT_NOTIFICATIONS_BY_ROLE:
        return
    exists = db.query(Notification.id).filter(Notification.role == role).first()
    if exists:
        return
    for item in DEFAULT_NOTIFICATIONS_BY_ROLE[role]:
        db.add(
            Notification(
                role=role,
                type=item["type"],
                title=item["title"],
                body=item["body"],
                link=item.get("link"),
                is_read=item.get("is_read", False),
            )
        )
    db.commit()


def _serialize_notification(n: Notification) -> Dict[str, Any]:
    return {
        "id": n.id,
        "role": n.role,
        "user_id": n.user_id,
        "type": n.type,
        "title": n.title,
        "body": n.body,
        "link": n.link or "",
        "read": bool(n.is_read),
        "is_read": bool(n.is_read),
        "time": _format_relative_time(n.created_at),
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }


class CreateNotificationRequest(BaseModel):
    role: str = Field(..., description="Role nhận thông báo: customer, store_owner, admin")
    user_id: Optional[int] = None
    type: str = Field("booking", description="booking, payment, alert, system")
    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1)
    link: Optional[str] = None


@router.get("", summary="Lấy danh sách thông báo theo role đang đăng nhập")
def list_role_notifications(
    unread_only: bool = Query(False, description="Chỉ lấy thông báo chưa đọc"),
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    role = _normalize_role(current_user.role)
    _ensure_role_notifications(db, role)

    base_q = db.query(Notification).filter(
        Notification.role == role,
        or_(Notification.user_id.is_(None), Notification.user_id == current_user.id),
    )
    unread_count = base_q.filter(Notification.is_read.is_(False)).count()

    q = base_q
    if unread_only:
        q = q.filter(Notification.is_read.is_(False))
    rows = q.order_by(desc(Notification.created_at), desc(Notification.id)).limit(limit).all()

    return {
        "success": True,
        "role": role,
        "unread_count": unread_count,
        "items": [_serialize_notification(r) for r in rows],
    }


@router.post("", status_code=status.HTTP_201_CREATED, summary="Tạo thông báo mới cho role")
def create_role_notification(
    payload: CreateNotificationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    caller_role = _normalize_role(current_user.role)
    target_role = _normalize_role(payload.role)
    if caller_role not in ("admin", "store_owner") and target_role != caller_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền tạo thông báo cho vai trò khác.",
        )
    notif = Notification(
        role=target_role,
        user_id=payload.user_id,
        type=payload.type,
        title=payload.title.strip(),
        body=payload.body.strip(),
        link=payload.link,
        is_read=False,
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return {"success": True, "item": _serialize_notification(notif)}


@router.patch("/read-all", summary="Đánh dấu tất cả thông báo của role hiện tại là đã đọc")
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    role = _normalize_role(current_user.role)
    updated = (
        db.query(Notification)
        .filter(
            Notification.role == role,
            or_(Notification.user_id.is_(None), Notification.user_id == current_user.id),
            Notification.is_read.is_(False),
        )
        .update({"is_read": True}, synchronize_session=False)
    )
    db.commit()
    return {"success": True, "role": role, "updated_count": updated}


@router.patch("/{notif_id}/read", summary="Đánh dấu một thông báo là đã đọc")
def mark_notification_read(
    notif_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    role = _normalize_role(current_user.role)
    notif = (
        db.query(Notification)
        .filter(
            Notification.id == notif_id,
            Notification.role == role,
            or_(Notification.user_id.is_(None), Notification.user_id == current_user.id),
        )
        .first()
    )
    if not notif:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy thông báo #{notif_id}.",
        )
    if not notif.is_read:
        notif.is_read = True
        db.commit()
        db.refresh(notif)
    return {"success": True, "item": _serialize_notification(notif)}


class SendBookingEmailRequest(BaseModel):
    to_email: str = Field(..., example="khachhang@example.com")
    customer_name: str = Field(..., example="Nguyễn Văn A")
    booking_id: int = Field(..., example=88421)
    vehicle_name: str = Field(..., example="Mazda CX-5 2.0L Premium (2024)")
    start_time: str = Field(..., example="14:00 - 10/11/2026")
    end_time: str = Field(..., example="14:00 - 13/11/2026")
    total_amount: float = Field(..., example=2850000)
    deposit_amount: float = Field(..., example=10000000)
    pickup_location: str = Field("Sân bay Quốc tế Đà Nẵng (Ga T1)", example="Sân bay Quốc tế Đà Nẵng")


class SendHandoverEmailRequest(BaseModel):
    to_email: str = Field(..., example="khachhang@example.com")
    customer_name: str = Field(..., example="Nguyễn Văn A")
    protocol_code: str = Field(..., example="BB-202611-0891")
    booking_id: int = Field(..., example=88421)
    vehicle_name: str = Field(..., example="Mazda CX-5 2.0L Premium (2024)")
    license_plate: str = Field(..., example="43A-688.92")
    protocol_type: str = Field("CHECK_OUT", example="CHECK_OUT")
    odo_reading: int = Field(..., example=18420)
    fuel_level: str = Field("FULL", example="FULL")


class SendRefundEmailRequest(BaseModel):
    to_email: str = Field(..., example="khachhang@example.com")
    customer_name: str = Field(..., example="Nguyễn Văn A")
    booking_id: int = Field(..., example=88421)
    refund_amount: float = Field(..., example=8000000)
    hold_fine_deposit: float = Field(2000000, example=2000000)
    bank_name: str = Field("Vietcombank (STK: 0988765432)", example="Vietcombank")


@router.post("/send-booking-email", status_code=status.HTTP_200_OK)
def trigger_booking_email(payload: SendBookingEmailRequest, background_tasks: BackgroundTasks):
    """Gửi email thông báo xác nhận đơn đặt xe (chạy ngầm qua BackgroundTasks)."""
    background_tasks.add_task(
        email_service.send_booking_confirmation,
        to_email=payload.to_email,
        customer_name=payload.customer_name,
        booking_id=payload.booking_id,
        vehicle_name=payload.vehicle_name,
        start_time=payload.start_time,
        end_time=payload.end_time,
        total_amount=payload.total_amount,
        deposit_amount=payload.deposit_amount,
        pickup_location=payload.pickup_location,
    )
    return {
        "success": True,
        "message": f"Đã lên lịch gửi email thông báo đơn #{payload.booking_id} tới {payload.to_email}",
        "backend": email_service.backend_name,
    }


@router.post("/send-handover-email", status_code=status.HTTP_200_OK)
def trigger_handover_email(payload: SendHandoverEmailRequest, background_tasks: BackgroundTasks):
    """Gửi email biên bản giao nhận xe điện tử có chữ ký số."""
    background_tasks.add_task(
        email_service.send_handover_protocol_notification,
        to_email=payload.to_email,
        customer_name=payload.customer_name,
        protocol_code=payload.protocol_code,
        booking_id=payload.booking_id,
        vehicle_name=payload.vehicle_name,
        license_plate=payload.license_plate,
        protocol_type=payload.protocol_type,
        odo_reading=payload.odo_reading,
        fuel_level=payload.fuel_level,
    )
    return {
        "success": True,
        "message": f"Đã lên lịch gửi email biên bản #{payload.protocol_code} tới {payload.to_email}",
        "backend": email_service.backend_name,
    }


@router.post("/send-refund-email", status_code=status.HTTP_200_OK)
def trigger_refund_email(payload: SendRefundEmailRequest, background_tasks: BackgroundTasks):
    """Gửi email thông báo hoàn tiền cọc & quyết toán chi phí."""
    background_tasks.add_task(
        email_service.send_deposit_refund_notification,
        to_email=payload.to_email,
        customer_name=payload.customer_name,
        booking_id=payload.booking_id,
        refund_amount=payload.refund_amount,
        hold_fine_deposit=payload.hold_fine_deposit,
        bank_name=payload.bank_name,
    )
    return {
        "success": True,
        "message": f"Đã lên lịch gửi email hoàn cọc đơn #{payload.booking_id} tới {payload.to_email}",
        "backend": email_service.backend_name,
    }


@router.get("/mock-history")
def get_mock_sent_history():
    """Xem danh sách các email đã gửi trong chế độ Mock (rất tiện để chụp màn hình làm bài nộp)."""
    if isinstance(email_service.sender, MockEmailSender):
        history = [
            {
                "to_email": p.to_email,
                "subject": p.subject,
                "created_at": p.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "text_preview": p.text_content[:200] if p.text_content else "HTML format",
            }
            for p in email_service.sender.sent_history
        ]
        return {
            "total_sent": len(history),
            "backend": "MockEmailSender",
            "history": history,
        }
    return {
        "total_sent": 0,
        "backend": email_service.backend_name,
        "message": "Hệ thống đang chạy chế độ SMTP thật, không lưu log bộ nhớ mock.",
    }

