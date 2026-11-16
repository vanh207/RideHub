"""Router quản lý gửi email thông báo đơn hàng và dịch vụ thông báo RideHub.
Hỗ trợ BackgroundTasks để gửi email bất đồng bộ không làm chậm phản hồi API.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from app.services.email_service import email_service, MockEmailSender

router = APIRouter(prefix="/notifications", tags=["Email Notifications Service"])


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

