"""Router xử lý Hội thoại & Tin nhắn Chatbot AI (Module Chatbot API)"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.db.session import get_db
from app.models.chat import ChatConversation, ChatMessage
from app.schemas.chat import ChatMessageRequest, ChatMessageResponse

router = APIRouter(prefix="/chat", tags=["AI Chatbot Conversations"])


@router.post("/message", response_model=ChatMessageResponse)
def handle_chat_message(
    payload: ChatMessageRequest,
    db: Session = Depends(get_db),
):
    """Tiếp nhận tin nhắn người dùng, phân tích intent và sinh phản hồi tự động."""
    # 1. Tìm hoặc tạo phiên hội thoại
    conv = db.query(ChatConversation).filter(ChatConversation.session_id == payload.session_id).first()
    if not conv:
        conv = ChatConversation(
            session_id=payload.session_id,
            customer_name=payload.customer_name,
            customer_phone=payload.customer_phone,
            status="AI_ACTIVE"
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)

    # 2. Lưu tin nhắn của User vào DB
    user_msg = ChatMessage(
        session_id=payload.session_id,
        sender="USER",
        message=payload.message
    )
    db.add(user_msg)

    # 3. Phân tích Intent & sinh phản hồi tiếng Việt tự nhiên
    query = payload.message.lower()
    intent = "general"
    response_text = ""
    extra_payload = None
    is_escalated = (conv.status == "ESCALATED_TO_AGENT")
    assigned_agent = conv.assigned_agent

    # Nếu đang trong trạng thái đã chuyển tiếp nhân viên
    if is_escalated:
        intent = "agent_reply"
        response_text = (
            f"[{assigned_agent or 'CSKH RideHub'}]: Dạ em đã nhận được tin nhắn: "
            f"\"{payload.message}\". Em đang kiểm tra trực tiếp trên hệ thống và hỗ trợ Quý khách ngay đây ạ!"
        )
    # Kịch bản 1: Tìm xe / Báo giá
    elif any(k in query for k in ["tìm xe", "7 chỗ", "xe máy", "giá", "thuê", "ô tô"]):
        intent = "search_vehicle"
        response_text = "Dạ RideHub có các mẫu xe 7 chỗ tự lái rất phù hợp cho lịch trình của Quý khách tại Đà Nẵng ạ:"
        extra_payload = {
            "vehicles": [
                {
                    "name": "Mitsubishi Xpander 2023 (Tự động)",
                    "type": "7 chỗ · Gầm cao · Xăng 6.5L/100km",
                    "price": 950000,
                    "price_text": "950.000 đ/ngày",
                    "badge": "Đã gồm bảo hiểm"
                },
                {
                    "name": "Toyota Innova Cross 2024",
                    "type": "7 chỗ VIP · Khoang cực rộng · Camera 360",
                    "price": 1200000,
                    "price_text": "1.200.000 đ/ngày",
                    "badge": "Xe mới 100%"
                }
            ],
            "quick_replies": ["Xem thủ tục giấy tờ eKYC", "Có giao xe tận nơi không?"]
        }
    # Kịch bản 2: eKYC / Giấy tờ
    elif any(k in query for k in ["ekyc", "bằng lái", "giấy tờ", "cccd", "b1", "b2"]):
        intent = "ekyc_guidance"
        response_text = (
            "Dạ thủ tục xác thực eKYC trên RideHub chỉ mất 3 đến 5 phút để AI phê duyệt! ⚡\n\n"
            "Quý khách chỉ cần chuẩn bị:\n"
            "1. CCCD gắn chip hoặc Hộ chiếu còn hạn.\n"
            "2. GPLX tương ứng: Bằng B1/B2 (cho ô tô) hoặc A1/A2 (cho xe máy).\n\n"
            "💡 Mẹo nhỏ: Chụp nơi đủ sáng, không lóa đèn và không để mất góc để được duyệt tự động ngay lần đầu ạ!"
        )
        extra_payload = {
            "quick_replies": ["Bằng lái quốc tế có được không?", "Tìm xe 7 chỗ ngay"]
        }
    # Kịch bản 3: Tra cứu đơn hàng / Biên bản
    elif any(k in query for k in ["đơn", "bk-88421", "biên bản", "giao xe"]):
        intent = "check_booking"
        response_text = "Dạ em đã kiểm tra thông tin đơn đặt xe #BK-88421 của Quý khách trên hệ thống:"
        extra_payload = {
            "booking": {
                "id": "BK-88421",
                "vehicle": "Mazda CX-5 2024 (BKS: 43A-688.92)",
                "location": "Ga T1 - Sân bay Đà Nẵng (14:00 hôm nay)",
                "agent": "Nguyễn Tuấn Minh (0905.123.456)"
            },
            "quick_replies": ["Mở Biên bản giao xe điện tử", "Khi nào hoàn tiền cọc?"]
        }
    # Kịch bản 4: Cứu hộ khẩn cấp
    elif any(k in query for k in ["cứu hộ", "xịt lốp", "thủng lốp", "sự cố", "hỏng", "đèo"]):
        intent = "report_incident"
        response_text = (
            "🚨 RIDEHUB ĐANG KÍCH HOẠT HỖ TRỢ KHẨN CẤP!\n\n"
            "Quý khách hãy giữ bình tĩnh và thực hiện ngay các bước an toàn:\n"
            "1. Bật ngay đèn cảnh báo khẩn cấp (hazard).\n"
            "2. Tấp xe sát lề phải, kéo phanh tay chắc chắn.\n"
            "3. Mọi người vui lòng bước ra ngoài xe đứng ở vị trí an toàn phía sau taluy đường.\n\n"
            "Quý khách hãy bấm Gửi vị trí GPS bên dưới hoặc gọi ngay Hotline cứu hộ 24/7 để đội cơ động xuất phát ngay:"
        )
        extra_payload = {
            "is_emergency": True,
            "hotline": "1900-7433",
            "quick_replies": ["📍 Gửi vị trí GPS ngay", "📞 Gọi Cứu hộ 1900-7433"]
        }
    # Kịch bản 5: Khiếu nại cọc / Leo thang nhân viên
    elif any(k in query for k in ["cọc", "hoàn tiền", "lừa đảo", "khiếu nại", "nhân viên", "gặp người"]):
        intent = "agent_escalation"
        is_escalated = True
        assigned_agent = "Mai Linh (Trưởng ca CSKH)"
        conv.status = "ESCALATED_TO_AGENT"
        conv.assigned_agent = assigned_agent
        conv.escalation_reason = "Khách hàng cần hỗ trợ tra soát hoàn cọc / khiếu nại"
        db.commit()

        response_text = (
            "Dạ em rất hiểu sự băn khoăn và sốt ruột của Quý khách về khoản tiền cọc. Em chân thành xin lỗi Quý khách! 🙏\n\n"
            "Em đang kết nối trực tiếp phiên chat này đến Chuyên viên Quản lý Vận hành RideHub (Mai Linh) "
            "để kiểm tra trực tiếp tài khoản và xử lý cho Quý khách ngay đây ạ."
        )
    else:
        intent = "general_fallback"
        response_text = (
            f"Dạ em đã ghi nhận câu hỏi của Quý khách: \"{payload.message}\". "
            "Quý khách có thể chọn nhanh các chủ đề trợ giúp bên dưới hoặc bấm nút gặp nhân viên hỗ trợ ạ:"
        )
        extra_payload = {
            "quick_replies": ["Tìm xe tự lái", "Hướng dẫn eKYC", "Xem FAQ", "Gặp nhân viên hỗ trợ"]
        }

    # 4. Lưu phản hồi của BOT vào DB
    bot_msg = ChatMessage(
        session_id=payload.session_id,
        sender="BOT" if not is_escalated else "AGENT",
        message=response_text,
        detected_intent=intent,
        payload_json=extra_payload
    )
    db.add(bot_msg)
    db.commit()

    return ChatMessageResponse(
        sender="bot" if not is_escalated else "agent",
        message=response_text,
        detected_intent=intent,
        payload=extra_payload,
        is_escalated=is_escalated,
        assigned_agent=assigned_agent
    )

