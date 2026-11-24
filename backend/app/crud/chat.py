"""CRUD & Nghiệp vụ Hội thoại Chatbot AI, Kho tri thức & Giới hạn lượt gọi."""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limiter import enforce_chatbot_rate_limit
from app.models.booking import Booking
from app.models.chat import ChatConversation, ChatMessage
from app.models.faq import FAQ
from app.models.user import User
from app.models.vehicle import Vehicle
from app.schemas.chat import (
    ChatMessageItem,
    ChatMessageRequest,
    ChatMessageResponse,
    ConversationHistoryResponse,
    KnowledgeCitation,
    KnowledgeEntryCreate,
    KnowledgeEntryUpdate,
    RateLimitMeta,
    UserBookingLookupItem,
    VehicleSearchResultItem,
)
from app.services.ai_service import ai_service
from app.services.knowledge_base import KnowledgeBaseService

logger = logging.getLogger("ridehub.chat_crud")


def get_or_create_conversation(
    session_id: str,
    customer_name: Optional[str],
    customer_phone: Optional[str],
    db: Session,
) -> ChatConversation:
    """Lấy hoặc tạo mới một phiên hội thoại."""
    conv = (
        db.query(ChatConversation)
        .filter(ChatConversation.session_id == session_id)
        .first()
    )
    if not conv:
        conv = ChatConversation(
            session_id=session_id,
            customer_name=customer_name,
            customer_phone=customer_phone,
            status="AI_ACTIVE",
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)
    else:
        # Cập nhật thông tin nếu có bổ sung
        if customer_name and not conv.customer_name:
            conv.customer_name = customer_name
        if customer_phone and not conv.customer_phone:
            conv.customer_phone = customer_phone
        db.commit()
    return conv


def add_chat_message(
    session_id: str,
    sender: str,
    message: str,
    detected_intent: Optional[str],
    payload_json: Optional[Any],
    db: Session,
) -> ChatMessage:
    """Lưu một dòng tin nhắn vào cơ sở dữ liệu."""
    msg = ChatMessage(
        session_id=session_id,
        sender=sender,
        message=message,
        detected_intent=detected_intent,
        payload_json=payload_json,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def get_conversation_history(
    session_id: str,
    db: Session,
    limit: int = 50,
) -> Optional[ConversationHistoryResponse]:
    """Lấy toàn bộ lịch sử trò chuyện của một phiên."""
    conv = (
        db.query(ChatConversation)
        .filter(ChatConversation.session_id == session_id)
        .first()
    )
    if not conv:
        return None

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .limit(limit)
        .all()
    )

    return ConversationHistoryResponse(
        session_id=conv.session_id,
        customer_name=conv.customer_name,
        customer_phone=conv.customer_phone,
        status=conv.status,
        assigned_agent=conv.assigned_agent,
        escalation_reason=conv.escalation_reason,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=[ChatMessageItem.model_validate(m) for m in messages],
    )


def reset_conversation(session_id: str, db: Session) -> bool:
    """Xóa toàn bộ lịch sử của phiên chat để bắt đầu lại."""
    conv = (
        db.query(ChatConversation)
        .filter(ChatConversation.session_id == session_id)
        .first()
    )
    if not conv:
        return False

    db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
    conv.status = "AI_ACTIVE"
    conv.assigned_agent = None
    conv.escalation_reason = None
    db.commit()
    return True


def process_ai_chat_message(
    payload: ChatMessageRequest,
    client_identifier: str,
    db: Session,
    current_user: Optional[User] = None,
) -> ChatMessageResponse:
    """Quy trình xử lý tin nhắn Chatbot AI hoàn chỉnh:
    
    1. Kiểm tra Giới hạn lượt gọi (Rate Limiting).
    2. Lưu tin nhắn người dùng.
    3. Nhận diện ý định gọi công cụ:
       - Tra cứu đơn thuê của chính người dùng (được kiểm soát chặt theo current_user.id).
       - Tìm kiếm xe sẵn sàng phục vụ theo tiêu chí (giá, loại xe, chỗ ngồi).
    4. Tra cứu Kho tri thức (RAG - Knowledge Base Search).
    5. Xử lý kịch bản leo thang nhân viên (Agent Escalation) nếu có khiếu nại.
    6. Gọi Lớp tích hợp Mô hình AI (AI Integration Layer) với RAG Context.
    7. Lưu phản hồi của BOT kèm trích dẫn (Citations).
    8. Trả về Response chuẩn xác cho Frontend.
    """
    # 1. KIỂM TRA RATE LIMIT
    rate_limit_info = enforce_chatbot_rate_limit(client_identifier)

    # 2. TẠO HOẶC LẤY PHIÊN CHAT & LƯU TIN NHẮN USER
    conv = get_or_create_conversation(
        session_id=payload.session_id,
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
        db=db,
    )

    add_chat_message(
        session_id=payload.session_id,
        sender="USER",
        message=payload.message,
        detected_intent="user_query",
        payload_json=None,
        db=db,
    )

    query_text = payload.message.strip()
    query_lower = query_text.lower()

    # 3. KIỂM TRA TRẠNG THÁI ĐÃ LEO THANG NHÂN VIÊN CHƯA
    is_escalated = (conv.status == "ESCALATED_TO_AGENT")
    assigned_agent = conv.assigned_agent

    # 4. NHẬN DIỆN KỊCH BẢN YÊU CẦU GẶP NGƯỜI THẬT / KHIẾU NẠI NẶNG
    escalation_triggers = [
        "gặp người",
        "gặp nhân viên",
        "nhân viên hỗ trợ",
        "kết nối với nhân viên",
        "chuyển nhân viên",
        "nhân viên cskh",
        "tổng đài",
        "nói chuyện với nhân viên",
        "lừa đảo",
        "khiếu nại",
        "tố cáo",
        "hoàn cọc ngay",
    ]
    if any(k in query_lower for k in escalation_triggers) and not is_escalated:
        is_escalated = True
        assigned_agent = "Mai Linh (Trưởng ca CSKH RideHub)"
        conv.status = "ESCALATED_TO_AGENT"
        conv.assigned_agent = assigned_agent
        conv.escalation_reason = "Khách hàng yêu cầu hỗ trợ trực tiếp từ nhân viên CSKH"
        db.commit()

        bot_text = (
            f"Em đã kết nối bạn với **{assigned_agent}** rồi ạ! 👋\n"
            "Nhân viên sẽ phản hồi ngay tại đây. "
            "Nếu cần hỗ trợ gấp, bạn gọi tổng đài **1900 6868** (24/7) nhé!"
        )

        add_chat_message(
            session_id=payload.session_id,
            sender="AGENT",
            message=bot_text,
            detected_intent="agent_escalation",
            payload_json={"assigned_agent": assigned_agent, "is_escalated": True},
            db=db,
        )

        return ChatMessageResponse(
            sender="agent",
            message=bot_text,
            detected_intent="agent_escalation",
            payload={"assigned_agent": assigned_agent},
            is_escalated=True,
            assigned_agent=assigned_agent,
            ai_model="human-escalation-router",
            citations=[],
            rate_limit=RateLimitMeta(**rate_limit_info),
        )

    # 5. NẾU ĐANG TRONG TRẠNG THÁI NHÂN VIÊN QUẢN LÝ
    if is_escalated:
        agent_reply = (
            f"[{assigned_agent or 'CSKH RideHub'}]: Dạ em đã nhận được tin nhắn: "
            f"\"{payload.message}\". Em đang kiểm tra trực tiếp trên hệ thống và phản hồi Quý khách ngay đây ạ!"
        )
        add_chat_message(
            session_id=payload.session_id,
            sender="AGENT",
            message=agent_reply,
            detected_intent="agent_reply",
            payload_json=None,
            db=db,
        )
        return ChatMessageResponse(
            sender="agent",
            message=agent_reply,
            detected_intent="agent_reply",
            is_escalated=True,
            assigned_agent=assigned_agent,
            ai_model="agent-support-mode",
            citations=[],
            rate_limit=RateLimitMeta(**rate_limit_info),
        )

    # 5.5. NHẬN DIỆN Ý ĐỊNH TRA CỨU ĐƠN THUÊ CỦA CHÍNH NGƯỜI DÙNG
    booking_intent_keywords = ["đơn của tôi", "tra cứu đơn", "đơn thuê", "lịch sử thuê", "kiểm tra đơn", "đơn số", "đơn hàng"]
    if any(k in query_lower for k in booking_intent_keywords):
        # Yêu cầu bảo mật: Nếu chưa đăng nhập thì thông báo đăng nhập
        if not current_user:
            auth_msg = (
                "Dạ để bảo mật thông tin cá nhân và tài khoản, Quý khách vui lòng đăng nhập "
                "để em có thể tra cứu chính xác danh sách đơn thuê của Quý khách ạ! 🔐"
            )
            add_chat_message(
                session_id=payload.session_id,
                sender="BOT",
                message=auth_msg,
                detected_intent="lookup_booking_unauthorized",
                payload_json={"requires_auth": True},
                db=db,
            )
            return ChatMessageResponse(
                sender="bot",
                message=auth_msg,
                detected_intent="lookup_booking_unauthorized",
                payload={"requires_auth": True},
                is_escalated=False,
                ai_model="booking-assistant",
                citations=[],
                rate_limit=RateLimitMeta(**rate_limit_info),
            )

        # Trích xuất mã đơn nếu người dùng có nhập (vd: "đơn số 12", "đơn #12")
        booking_id_match = re.search(r"(?:đơn|mã đơn|đơn số|#)\s*(\d+)", query_lower)
        target_booking_id = int(booking_id_match.group(1)) if booking_id_match else None

        # Tra cứu: Đảm bảo CHỈ lấy đơn có customer_id == current_user.id
        user_bookings = lookup_user_bookings_for_chat(
            current_user_id=current_user.id,
            booking_id=target_booking_id,
            db=db,
            limit=5,
        )

        if not user_bookings:
            if target_booking_id:
                reply = f"Dạ em đã kiểm tra trên hệ thống, Quý khách không có đơn thuê nào mang mã #{target_booking_id} (hoặc đơn này thuộc tài khoản khác) ạ."
            else:
                reply = f"Dạ chào Quý khách {current_user.full_name or ''}, hiện tại Quý khách chưa có đơn thuê xe nào trên hệ thống RideHub ạ."
        else:
            reply_lines = [f"Dạ em xin gửi thông tin đơn thuê của Quý khách {current_user.full_name or ''}:"]
            for b in user_bookings:
                reply_lines.append(
                    f"• Đơn #{b.booking_id}: Xe {b.vehicle_name} (BS: {b.plate_number}) - "
                    f"Trạng thái: {b.status} - Tổng tiền: {b.total_amount:,.0f} VNĐ"
                )
            reply = "\n".join(reply_lines)

        add_chat_message(
            session_id=payload.session_id,
            sender="BOT",
            message=reply,
            detected_intent="lookup_user_booking",
            payload_json=None,
            db=db,
        )
        return ChatMessageResponse(
            sender="bot",
            message=reply,
            detected_intent="lookup_user_booking",
            payload={"bookings": [b.model_dump(mode="json") for b in user_bookings]},
            is_escalated=False,
            ai_model="booking-assistant",
            citations=[],
            rate_limit=RateLimitMeta(**rate_limit_info),
        )

    # 5.6. NHẬN DIỆN Ý ĐỊNH TÌM KIẾM XE SẴN CÓ
    vehicle_search_keywords = [
        "tìm xe", "thuê xe", "có xe nào", "xe 4 chỗ", "xe 7 chỗ",
        "xe máy", "ô tô", "giá xe", "xe sẵn", "gần tôi", "gần đây", "xe điện",
    ]
    if any(k in query_lower for k in vehicle_search_keywords) and not ("chính sách" in query_lower or "thủ tục" in query_lower):
        # Xác định loại xe
        v_type = None
        if "xe máy" in query_lower or "motorbike" in query_lower:
            v_type = "MOTORBIKE"
        elif "ô tô" in query_lower or "oto" in query_lower or "car" in query_lower:
            v_type = "CAR"

        # Chỗ ngồi
        seats = None
        seats_match = re.search(r"(\d+)\s*(?:chỗ|cho)", query_lower)
        if seats_match:
            seats = int(seats_match.group(1))

        vehicles = search_vehicles_for_chat(
            keyword=None if (v_type or seats) else query_text,
            vehicle_type=v_type,
            seats=seats,
            db=db,
            limit=5,
        )

        if vehicles:
            # Lấy loại xe để gợi ý đúng link lọc
            type_label = "xe máy" if v_type == "MOTORBIKE" else ("ô tô" if v_type == "CAR" else "xe")
            type_param = f"?type={v_type.lower()}" if v_type else ""

            # Câu trả lời ngắn gọn, tự nhiên — tối đa 3 xe + link
            intro = f"Có ngay {len(vehicles)} {type_label} đang trống bạn ơi! 🎉"
            car_lines = []
            for v in vehicles[:3]:
                car_lines.append(
                    f"• **{v.brand} {v.model}** — {v.price_per_day:,.0f}đ/ngày"
                )
            link_line = f"\n👉 Xem & đặt xe tại: /vehicles.html{type_param}"
            reply = intro + "\n" + "\n".join(car_lines) + link_line

            add_chat_message(
                session_id=payload.session_id,
                sender="BOT",
                message=reply,
                detected_intent="search_vehicles",
                payload_json={"vehicles": [v.model_dump() for v in vehicles]},
                db=db,
            )
            return ChatMessageResponse(
                sender="bot",
                message=reply,
                detected_intent="search_vehicles",
                payload={"vehicles": [v.model_dump() for v in vehicles]},
                is_escalated=False,
                ai_model="vehicle-assistant",
                citations=[],
                rate_limit=RateLimitMeta(**rate_limit_info),
            )
        else:
            type_label = "xe máy" if v_type == "MOTORBIKE" else ("ô tô" if v_type == "CAR" else "xe")
            type_param = f"?type={v_type.lower()}" if v_type else ""
            reply = (
                f"Hiện chưa có {type_label} phù hợp đang trống bạn ơi 😕 "
                f"Bạn thử xem danh sách xe tại 👉 /vehicles.html{type_param} nhé!"
            )
            add_chat_message(
                session_id=payload.session_id,
                sender="BOT",
                message=reply,
                detected_intent="search_vehicles",
                payload_json={"vehicles": []},
                db=db,
            )
            return ChatMessageResponse(
                sender="bot",
                message=reply,
                detected_intent="search_vehicles",
                payload={"vehicles": []},
                is_escalated=False,
                ai_model="vehicle-assistant",
                citations=[],
                rate_limit=RateLimitMeta(**rate_limit_info),
            )

    # 6. TRA CỨU KHO TRI THỨC (KNOWLEDGE BASE RAG)
    # (Nếu tìm xe không ra kết quả → vẫn thử RAG để trả lời tự nhiên)
    knowledge_results = KnowledgeBaseService.search_knowledge(
        query=query_text,
        db=db,
        limit=3,
        min_score=1.0,
    )
    rag_context = KnowledgeBaseService.build_rag_context(knowledge_results)

    citations = [
        KnowledgeCitation(
            faq_id=item.id,
            category=item.category,
            category_name=item.category_name,
            question=item.question,
            relevance_score=item.relevance_score,
        )
        for item in knowledge_results
    ]

    # 7. LẤY LỊCH SỬ HỘI THOẠI GẦN NHẤT ĐỂ TẠO TRÍ NHỚ CHO AI
    recent_messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == payload.session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(settings.CHATBOT_MAX_CONTEXT_MESSAGES)
        .all()
    )
    history_context = []
    for m in reversed(recent_messages):
        role = "user" if m.sender == "USER" else "model"
        history_context.append({"role": role, "content": m.message})

    # 8. GỌI LỚP TÍCH HỢP MÔ HÌNH AI (AI SERVICE)
    ai_result = ai_service.ask_ai(
        user_message=query_text,
        conversation_history=history_context,
        rag_context=rag_context,
    )

    ai_reply_text = ai_result.get("text", "Dạ em đã ghi nhận thông tin và đang xử lý ạ.")
    ai_model_name = ai_result.get("model", "knowledge-ai")

    # 9. LƯU PHẢN HỒI CỦA BOT VÀO DB
    add_chat_message(
        session_id=payload.session_id,
        sender="BOT",
        message=ai_reply_text,
        detected_intent="ai_answered",
        payload_json={"citations": [c.model_dump() for c in citations], "model": ai_model_name},
        db=db,
    )

    return ChatMessageResponse(
        sender="bot",
        message=ai_reply_text,
        detected_intent="ai_answered",
        payload={"citations": [c.model_dump() for c in citations]},
        is_escalated=False,
        assigned_agent=None,
        ai_model=ai_model_name,
        citations=citations,
        rate_limit=RateLimitMeta(**rate_limit_info),
    )


# ---------------------------------------------------------------------------
# Trợ lý Chatbot gọi API tìm xe & tra cứu đơn có kiểm soát
# ---------------------------------------------------------------------------

def search_vehicles_for_chat(
    keyword: Optional[str] = None,
    vehicle_type: Optional[str] = None,
    max_price: Optional[float] = None,
    seats: Optional[int] = None,
    db: Session = None,
    limit: int = 5,
) -> List[VehicleSearchResultItem]:
    """Tìm kiếm xe đang sẵn sàng (AVAILABLE) để chatbot tư vấn cho khách."""
    query = db.query(Vehicle).filter(
        Vehicle.is_active == True,
        Vehicle.current_status == "AVAILABLE",
    )

    if vehicle_type:
        query = query.filter(Vehicle.vehicle_type == vehicle_type.upper())

    if max_price is not None and max_price > 0:
        query = query.filter(Vehicle.price_per_day <= max_price)

    if seats is not None and seats > 0:
        query = query.filter(Vehicle.seats == seats)

    if keyword:
        kw = f"%{keyword.strip()}%"
        query = query.filter(
            (Vehicle.brand.ilike(kw)) | (Vehicle.model.ilike(kw)) | (Vehicle.description.ilike(kw))
        )

    vehicles = query.order_by(Vehicle.price_per_day.asc()).limit(limit).all()

    return [
        VehicleSearchResultItem(
            id=v.id,
            brand=v.brand,
            model=v.model,
            vehicle_type=v.vehicle_type,
            plate_number=v.plate_number,
            price_per_day=float(v.price_per_day),
            current_status=v.current_status,
            seats=v.seats,
            transmission_type=v.transmission_type,
            fuel_type=v.fuel_type,
        )
        for v in vehicles
    ]


def lookup_user_bookings_for_chat(
    current_user_id: int,
    booking_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    db: Session = None,
    limit: int = 5,
) -> List[UserBookingLookupItem]:
    """Tra cứu đơn thuê xe có kiểm soát: CHỈ TRẢ ĐƠN CỦA CHÍNH NGƯỜI DÙNG ĐANG CHAT."""
    if not current_user_id:
        return []

    # Cố định điều kiện customer_id == current_user_id để chống rò rỉ dữ liệu của khách khác
    query = (
        db.query(Booking, Vehicle)
        .join(Vehicle, Booking.vehicle_id == Vehicle.id)
        .filter(Booking.customer_id == current_user_id)
    )

    if booking_id:
        query = query.filter(Booking.id == booking_id)

    if status_filter:
        query = query.filter(Booking.status == status_filter.upper())

    results = query.order_by(Booking.created_at.desc() if hasattr(Booking, "created_at") else Booking.id.desc()).limit(limit).all()

    items = []
    for booking, vehicle in results:
        items.append(
            UserBookingLookupItem(
                booking_id=booking.id,
                vehicle_name=f"{vehicle.brand} {vehicle.model}",
                plate_number=vehicle.plate_number,
                start_time=booking.start_time,
                end_time=booking.end_time,
                status=booking.status,
                total_amount=float(booking.total_amount),
                deposit_amount=float(booking.deposit_amount or 0),
            )
        )
    return items


def update_knowledge_entry(faq_id: int, payload: KnowledgeEntryUpdate, db: Session) -> Optional[FAQ]:
    """Cập nhật một mục tri thức."""
    faq = db.query(FAQ).filter(FAQ.id == faq_id).first()
    if not faq:
        return None
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(faq, k, v)
    db.commit()
    db.refresh(faq)
    return faq

def add_knowledge_entry(payload: KnowledgeEntryCreate, db: Session) -> FAQ:
    """Thêm một mục tri thức mới vào kho."""
    faq = FAQ(
        category=payload.category,
        category_name=payload.category_name,
        question=payload.question,
        answer=payload.answer,
        display_order=payload.display_order,
        is_active=payload.is_active,
    )
    db.add(faq)
    db.commit()
    db.refresh(faq)
    return faq


def delete_knowledge_entry(faq_id: int, db: Session) -> bool:
    """Xóa một mục tri thức khỏi kho."""
    faq = db.query(FAQ).filter(FAQ.id == faq_id).first()
    if not faq:
        return False
    db.delete(faq)
    db.commit()
    return True
