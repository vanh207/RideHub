"""CRUD & Nghiệp vụ Hội thoại Chatbot AI, Kho tri thức & Giới hạn lượt gọi."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

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

    # 4. NHẬN DIỆN KỊCH BẢN YÊU CẦU GẶP NGƯỜI THẬT / SỰ CỐ / KHIẾU NẠI / NGOẠI LỆ
    escalation_triggers = [
        "gặp người",
        "gặp nhân viên",
        "nhân viên hỗ trợ",
        "kết nối với nhân viên",
        "chuyển nhân viên",
        "nhân viên cskh",
        "tổng đài",
        "nói chuyện với nhân viên",
        "tư vấn viên",
        "lừa đảo",
        "khiếu nại",
        "tố cáo",
        "hoàn cọc ngay",
        "tai nạn",
        "sự cố xe",
        "hỏng xe",
        "mất đồ",
        "tranh chấp",
        "bồi thường",
        "giảm giá đặc biệt",
        "thuê dài hạn",
        "hợp đồng doanh nghiệp",
        "số lượng lớn",
    ]
    if any(k in query_lower for k in escalation_triggers) and not is_escalated:
        from datetime import datetime, timezone, timedelta

        is_escalated = True
        assigned_agent = "Mai Linh (Trưởng ca CSKH RideHub)"

        # Trích xuất SĐT nếu khách có nhắn kèm
        phone_match = re.search(r"\b(0[35789]\d{8})\b", query_text)
        if phone_match and not conv.customer_phone:
            conv.customer_phone = phone_match.group(1)

        customer_label = (
            f"{current_user.full_name or current_user.email} ({conv.customer_phone or current_user.phone or 'Chưa có SĐT'})"
            if current_user
            else f"{conv.customer_name or 'Khách vãng lai'} ({conv.customer_phone or 'Chưa có SĐT'})"
        )

        # Lấy ngữ cảnh hội thoại để tóm tắt bàn giao cho nhân viên
        prev_msgs = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == payload.session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(8)
            .all()
        )
        user_history = [m.message for m in reversed(prev_msgs) if m.sender == "USER"]
        bot_history = [m.message for m in reversed(prev_msgs) if m.sender == "BOT"]

        # Đánh giá cảm xúc khách
        if any(w in query_lower for w in ["lừa đảo", "tố cáo", "rất bực", "quá tệ", "vô trách nhiệm", "hoàn cọc ngay"]):
            sentiment = "rất bực"
        elif any(w in query_lower for w in ["khiếu nại", "bồi thường", "tranh chấp", "chậm", "bực", "hỏng xe", "tai nạn"]):
            sentiment = "hơi bực"
        else:
            sentiment = "bình thường"

        # Việc nhân viên cần làm
        if any(w in query_lower for w in ["tai nạn", "sự cố xe", "hỏng xe", "mất đồ"]):
            action_needed = "Liên hệ khẩn cấp hỗ trợ sự cố/cứu hộ và điều phối xe thay thế."
        elif any(w in query_lower for w in ["khiếu nại", "bồi thường", "tranh chấp", "hoàn cọc", "lừa đảo"]):
            action_needed = "Kiểm tra đơn thuê/giao dịch cọc, xác minh với cửa hàng và xử lý khiếu nại."
        elif any(w in query_lower for w in ["doanh nghiệp", "dài hạn", "số lượng lớn", "giảm giá"]):
            action_needed = "Báo giá gói thuê doanh nghiệp/dài hạn và làm hợp đồng riêng."
        else:
            action_needed = "Tiếp nhận tư vấn trực tiếp 1-1 và chốt xe cho khách."

        handoff_summary = {
            "ticket_code": f"RH-{conv.id}",
            "customer": customer_label,
            "needs": " | ".join(user_history[-3:]) if user_history else query_text,
            "current_issue": query_text,
            "bot_proposed": bot_history[-1][:200] if bot_history else "Chưa có đề xuất trước đó",
            "sentiment": sentiment,
            "action_required": action_needed,
        }

        conv.status = "ESCALATED_TO_AGENT"
        conv.assigned_agent = assigned_agent
        conv.escalation_reason = (
            f"[{handoff_summary['ticket_code']}] Cảm xúc: {sentiment} | "
            f"Vấn đề: {query_text[:120]} | Cần làm: {action_needed}"
        )
        db.commit()

        # Kiểm tra giờ làm việc tư vấn viên tại VN (UTC+7: 08:00 - 22:00)
        vn_now = datetime.now(timezone.utc) + timedelta(hours=7)
        in_working_hours = 8 <= vn_now.hour < 22

        if in_working_hours:
            bot_text = (
                f"Mình đã chuyển bạn sang nhân viên hỗ trợ (**{assigned_agent}**), "
                f"dự kiến phản hồi trong **2–5 phút** (mã phiếu `#RH-{conv.id}`). 👋\n"
                "Nếu cần xử lý gấp ngay, bạn gọi tổng đài **1900 6868** (24/7) nhé!"
            )
        else:
            bot_text = (
                f"Hiện đang ngoài giờ trực của tư vấn viên (08:00–22:00), mình đã tạo phiếu `#RH-{conv.id}` "
                "để nhân viên phản hồi sớm nhất từ **08:00 sáng**. 🌙\n"
                "Bạn nhắn giúp mình **SĐT/Zalo** tại đây để bên mình chủ động liên hệ lại, "
                "hoặc gọi tổng đài cứu hộ 24/7 **1900 6868** nếu đang gặp sự cố gấp nhé!"
            )

        add_chat_message(
            session_id=payload.session_id,
            sender="AGENT",
            message=bot_text,
            detected_intent="agent_escalation",
            payload_json={
                "assigned_agent": assigned_agent,
                "is_escalated": True,
                "in_working_hours": in_working_hours,
                "handoff_summary": handoff_summary,
            },
            db=db,
        )

        return ChatMessageResponse(
            sender="agent",
            message=bot_text,
            detected_intent="agent_escalation",
            payload={
                "assigned_agent": assigned_agent,
                "in_working_hours": in_working_hours,
                "handoff_summary": handoff_summary,
            },
            is_escalated=True,
            assigned_agent=assigned_agent,
            ai_model="human-escalation-router",
            citations=[],
            rate_limit=RateLimitMeta(**rate_limit_info),
        )

    # 5. NẾU ĐANG TRONG TRẠNG THÁI NHÂN VIÊN QUẢN LÝ
    if is_escalated:
        phone_match = re.search(r"\b(0[35789]\d{8})\b", query_text)
        if phone_match:
            conv.customer_phone = phone_match.group(1)
            db.commit()
            agent_reply = (
                f"Mình đã ghi nhận số **{conv.customer_phone}** vào phiếu `#RH-{conv.id}` rồi nha! "
                f"Chuyên viên {assigned_agent or 'CSKH RideHub'} sẽ liên hệ hỗ trợ bạn sớm nhất."
            )
        elif any(w in query_lower for w in ["gấp", "khẩn", "lâu quá", "chưa thấy"]):
            agent_reply = (
                f"Rất xin lỗi để bạn chờ! Phiếu `#RH-{conv.id}` đang được ưu tiên cho {assigned_agent or 'CSKH RideHub'}. "
                "Nếu cần xử lý ngay lập tức, bạn gọi tổng đài **1900 6868** (24/7) để gặp trực tiếp tổng đài viên nhé!"
            )
        else:
            agent_reply = (
                f"Mình đã đính kèm thông tin này vào phiếu `#RH-{conv.id}` gửi tới {assigned_agent or 'CSKH RideHub'} rồi ạ. "
                "Nhân viên sẽ phản hồi bạn ngay tại đây (hoặc qua SĐT nếu bạn đã để lại)."
            )

        add_chat_message(
            session_id=payload.session_id,
            sender="AGENT",
            message=agent_reply,
            detected_intent="agent_reply",
            payload_json={"ticket_code": f"RH-{conv.id}"},
            db=db,
        )
        return ChatMessageResponse(
            sender="agent",
            message=agent_reply,
            detected_intent="agent_reply",
            payload={"ticket_code": f"RH-{conv.id}"},
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

    # 5.6. NHẬN DIỆN Ý ĐỊNH TÌM KIẾM XE SẴN CÓ (KÈM LỌC THEO KHUNG GIỜ)
    vehicle_search_keywords = [
        "tìm xe", "có xe nào", "xe 4 chỗ", "xe 7 chỗ", "xe sẵn", "xe trống",
        "thuê xe máy", "thuê ô tô", "thuê xe 4", "thuê xe 7", "thuê xe điện",
        "gần tôi", "gần đây", "gợi ý xe", "muốn thuê xe",
    ]
    non_search_keywords = [
        "chính sách", "thủ tục", "hợp đồng", "tiền cọc", "đặt cọc", "giấy tờ",
        "cccd", "bằng lái", "ekyc", "bảo hiểm", "hủy đơn", "hoàn tiền", "có được không",
    ]
    if any(k in query_lower for k in vehicle_search_keywords) and not any(k in query_lower for k in non_search_keywords):
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

        # Lấy thêm các tin nhắn user gần nhất trong phiên để nhớ khung giờ khách vừa nêu (vd lượt trước nói "12h hôm nay", lượt này nói "thuê xe máy")
        recent_user_msgs = (
            db.query(ChatMessage.message)
            .filter(ChatMessage.session_id == payload.session_id, ChatMessage.sender == "USER")
            .order_by(ChatMessage.created_at.desc())
            .limit(4)
            .all()
        )
        candidate_texts = [query_text] + [m[0] for m in recent_user_msgs if m[0] and m[0] != query_text]
        start_time, end_time, time_label = _extract_time_window_from_messages(candidate_texts)

        vehicles = search_vehicles_for_chat(
            keyword=None if (v_type or seats or start_time) else query_text,
            vehicle_type=v_type,
            seats=seats,
            start_time=start_time,
            end_time=end_time,
            db=db,
            limit=5,
        )

        type_label = "xe máy" if v_type == "MOTORBIKE" else ("ô tô" if v_type == "CAR" else "xe")
        type_param = f"?type={v_type.lower()}" if v_type else ""
        if start_time and end_time:
            sep = "&" if type_param else "?"
            time_query = f"{type_param}{sep}start_time={start_time.strftime('%Y-%m-%dT%H:%M:%S')}&end_time={end_time.strftime('%Y-%m-%dT%H:%M:%S')}"
        else:
            time_query = type_param

        if vehicles:
            if time_label:
                intro = f"Tin vui cho bạn nè! Khung giờ **{time_label}** bên mình vẫn còn {len(vehicles)} {type_label} trống sẵn sàng giao xe: 🎉"
            else:
                intro = f"Bên mình đang có {len(vehicles)} {type_label} sẵn sàng phục vụ bạn ngay nè: 🎉"
            car_lines = [
                f"• **{v.brand} {v.model}** — {v.price_per_day:,.0f}đ/ngày"
                for v in vehicles[:3]
            ]
            link_line = f"\n👉 Bạn xem chi tiết và đặt giữ chỗ tại: /vehicles.html{time_query}"
            reply = intro + "\n" + "\n".join(car_lines) + link_line

            add_chat_message(
                session_id=payload.session_id,
                sender="BOT",
                message=reply,
                detected_intent="search_vehicles",
                payload_json={"vehicles": [v.model_dump() for v in vehicles], "time_label": time_label},
                db=db,
            )
            return ChatMessageResponse(
                sender="bot",
                message=reply,
                detected_intent="search_vehicles",
                payload={"vehicles": [v.model_dump() for v in vehicles], "time_label": time_label},
                is_escalated=False,
                ai_model="vehicle-assistant",
                citations=[],
                rate_limit=RateLimitMeta(**rate_limit_info),
            )
        elif v_type or seats or start_time:
            # Nếu có khung giờ cụ thể mà hết xe -> tìm khung giờ khác còn trống trong ngày
            alt_suggestions = []
            if start_time and end_time:
                alt_suggestions = _find_same_day_alternative_slots(
                    vehicle_type=v_type,
                    seats=seats,
                    target_date=start_time.date(),
                    requested_start=start_time,
                    requested_end=end_time,
                    db=db,
                    limit=3,
                )

            if alt_suggestions:
                alt_lines = [
                    f"• **{item['vehicle'].brand} {item['vehicle'].model}** ({item['vehicle'].price_per_day:,.0f}đ/ngày) — trống khung **{item['slot_label']}**"
                    for item in alt_suggestions
                ]
                reply = (
                    f"Tiếc quá, tầm **{time_label}** bên mình vừa kín lịch hết {type_label} mất rồi bạn ơi 🥺\n"
                    f"Nhưng bạn đừng lo, cùng ngày hôm đó vẫn còn mấy chiếc {type_label} đang trống ở khung giờ khác rất tiện nè:\n"
                    + "\n".join(alt_lines)
                    + f"\nBạn xem mình có linh động đổi sang khung giờ trên được không, hoặc bấm 👉 /vehicles.html{type_param} để chọn giờ khác nhé!"
                )
                alt_vehicles_payload = [item["vehicle"].model_dump() for item in alt_suggestions]
            else:
                time_note = f"trong khung giờ **{time_label}** " if time_label else ""
                reply = (
                    f"Tiếc quá bạn ơi, hiện tại {time_note}bên mình đang tạm hết {type_label} trống mất rồi 🥺\n"
                    f"Bạn thử linh động sang ngày mai hoặc xem các dòng xe khác đang sẵn sàng tại 👉 /vehicles.html nhé, "
                    "hoặc bấm **Gặp nhân viên hỗ trợ** để bên mình kiểm tra điều phối xe từ chi nhánh gần nhất cho bạn nha!"
                )
                alt_vehicles_payload = []

            add_chat_message(
                session_id=payload.session_id,
                sender="BOT",
                message=reply,
                detected_intent="search_vehicles",
                payload_json={"vehicles": alt_vehicles_payload, "time_label": time_label},
                db=db,
            )
            return ChatMessageResponse(
                sender="bot",
                message=reply,
                detected_intent="search_vehicles",
                payload={"vehicles": alt_vehicles_payload, "time_label": time_label},
                is_escalated=False,
                ai_model="vehicle-assistant",
                citations=[],
                rate_limit=RateLimitMeta(**rate_limit_info),
            )

    # 6. TRA CỨU KHO TRI THỨC (KNOWLEDGE BASE RAG)
    # Bỏ qua RAG cho các câu chào hỏi / cảm ơn ngắn để tránh gắn nhầm FAQ không liên quan
    greeting_phrases = {
        "hi", "hello", "hey", "alo", "chào", "xin chào", "chào bạn", "chào em", "hello bạn",
        "cảm ơn", "cam on", "thanks", "thank you", "ok", "oke", "tạm biệt", "bye",
    }
    is_smalltalk = query_lower in greeting_phrases or (
        len(query_lower.split()) <= 3
        and any(g in query_lower for g in ("hello", "chào", "cảm ơn", "thanks", "bye"))
    )

    if is_smalltalk:
        knowledge_results = []
        rag_context = "Khách hàng đang chào hỏi hoặc trò chuyện tự nhiên. Hãy đáp lại thân thiện và khéo léo hỏi nhu cầu thuê xe của khách."
    else:
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

def _extract_time_window_from_messages(
    texts: List[str],
) -> Tuple[Optional[datetime], Optional[datetime], Optional[str]]:
    """Trích xuất khung thời gian thuê xe (start_time, end_time, nhãn hiển thị) từ tin nhắn."""
    vn_now = (datetime.now(timezone.utc) + timedelta(hours=7)).replace(tzinfo=None)

    for raw in texts:
        t = (raw or "").lower()
        if not t:
            continue

        # Xác định ngày
        target_date = vn_now.date()
        date_label = "hôm nay"
        if "ngày kia" in t:
            target_date = (vn_now + timedelta(days=2)).date()
            date_label = target_date.strftime("%d/%m")
        elif "ngày mai" in t or re.search(r"\bmai\b", t):
            target_date = (vn_now + timedelta(days=1)).date()
            date_label = "ngày mai"
        else:
            dm = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{4}))?\b", t)
            if dm:
                day, month = int(dm.group(1)), int(dm.group(2))
                year = int(dm.group(3)) if dm.group(3) else vn_now.year
                try:
                    target_date = datetime(year, month, day).date()
                    date_label = target_date.strftime("%d/%m")
                except ValueError:
                    pass

        # 1) Dạng khoảng giờ: "từ 9h đến 15h", "12h - 16h", "9:30 đến 14:00"
        range_match = re.search(
            r"(\d{1,2})\s*(?:h|:|giờ)\s*(\d{0,2})\s*(?:đến|tới|-|–)\s*(\d{1,2})\s*(?:h|:|giờ)?\s*(\d{0,2})",
            t,
        )
        if range_match:
            sh = int(range_match.group(1))
            sm = int(range_match.group(2) or 0)
            eh = int(range_match.group(3))
            em = int(range_match.group(4) or 0)
            if 0 <= sh <= 23 and 0 <= eh <= 23 and 0 <= sm <= 59 and 0 <= em <= 59:
                start_dt = datetime(target_date.year, target_date.month, target_date.day, sh, sm)
                end_dt = datetime(target_date.year, target_date.month, target_date.day, eh, em)
                if end_dt <= start_dt:
                    end_dt = end_dt + timedelta(days=1)
                label = f"{start_dt.strftime('%H:%M')}–{end_dt.strftime('%H:%M')} {date_label}"
                return start_dt, end_dt, label

        # 2) Dạng 1 mốc giờ: "12h", "12h30", "14:00", "2h chiều", "7h tối"
        single_match = re.search(
            r"(\d{1,2})\s*(?:h|:|giờ)\s*(\d{0,2})\s*(sáng|trưa|chiều|tối)?",
            t,
        )
        if single_match:
            sh = int(single_match.group(1))
            sm = int(single_match.group(2) or 0)
            period = single_match.group(3) or ""
            if period in ("chiều", "tối") and 1 <= sh <= 11:
                sh += 12
            if 0 <= sh <= 23 and 0 <= sm <= 59:
                start_dt = datetime(target_date.year, target_date.month, target_date.day, sh, sm)
                end_dt = start_dt + timedelta(hours=4)
                label = f"{start_dt.strftime('%H:%M')}–{end_dt.strftime('%H:%M')} {date_label}"
                return start_dt, end_dt, label

        # 3) Buổi trong ngày khi không nói giờ cụ thể
        for word, (sh, eh) in (("sáng", (8, 12)), ("trưa", (11, 15)), ("chiều", (14, 18)), ("tối", (18, 22))):
            if re.search(rf"\b{word}\b", t) and any(d in t for d in ("hôm nay", "ngày mai", "mai", "ngày kia", "tầm", "lúc", "khoảng")):
                start_dt = datetime(target_date.year, target_date.month, target_date.day, sh, 0)
                end_dt = datetime(target_date.year, target_date.month, target_date.day, eh, 0)
                label = f"buổi {word} ({sh:02d}:00–{eh:02d}:00) {date_label}"
                return start_dt, end_dt, label

    return None, None, None


def _chat_no_conflict_conditions(
    vehicle_id_column,
    start_time: datetime,
    end_time: datetime,
    current_time: datetime,
):
    """Kiểm tra xe không trùng lịch đặt/giữ chỗ/chặn lịch (không dùng FORCE INDEX để tránh lỗi DB thiếu index)."""
    from sqlalchemy import or_, select
    from app.models.vehicle_reservation import VehicleReservation
    from app.models.vehicle_schedule import VehicleSchedule

    buffer = timedelta(minutes=settings.BOOKING_BUFFER_MINUTES)
    latest_start = end_time + buffer
    earliest_end = start_time - buffer
    blocking_statuses = (
        "PENDING",
        "PENDING_PAYMENT",
        "PENDING_STORE_CONFIRM",
        "CONFIRMED",
        "DEPOSIT_PAID",
        "BOOKED",
        "IN_PROGRESS",
        "PENDING_SETTLEMENT",
    )
    expirable_statuses = ("PENDING", "PENDING_PAYMENT")

    def _expired_hold_for(booking_fk):
        return (
            select(Booking.id)
            .where(
                Booking.id == booking_fk,
                Booking.status.in_(expirable_statuses),
                Booking.hold_expires_at.is_not(None),
                Booking.hold_expires_at <= current_time,
            )
            .exists()
        )

    booking_conflict = (
        select(Booking.id)
        .where(
            Booking.vehicle_id == vehicle_id_column,
            Booking.status.in_(blocking_statuses),
            Booking.start_time < latest_start,
            Booking.end_time > earliest_end,
            or_(
                Booking.status.notin_(expirable_statuses),
                Booking.hold_expires_at.is_(None),
                Booking.hold_expires_at > current_time,
            ),
        )
        .exists()
    )
    reservation_conflict = (
        select(VehicleReservation.id)
        .where(
            VehicleReservation.vehicle_id == vehicle_id_column,
            VehicleReservation.status == "ACTIVE",
            VehicleReservation.expires_at > current_time,
            VehicleReservation.start_time < latest_start,
            VehicleReservation.end_time > earliest_end,
            ~_expired_hold_for(VehicleReservation.booking_id),
        )
        .exists()
    )
    schedule_conflict = (
        select(VehicleSchedule.id)
        .where(
            VehicleSchedule.vehicle_id == vehicle_id_column,
            VehicleSchedule.status == "ACTIVE",
            VehicleSchedule.start_time < latest_start,
            VehicleSchedule.end_time > earliest_end,
            ~_expired_hold_for(VehicleSchedule.booking_id),
        )
        .exists()
    )
    return [~booking_conflict, ~reservation_conflict, ~schedule_conflict]


def search_vehicles_for_chat(
    keyword: Optional[str] = None,
    vehicle_type: Optional[str] = None,
    max_price: Optional[float] = None,
    seats: Optional[int] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    db: Session = None,
    limit: int = 5,
) -> List[VehicleSearchResultItem]:
    """Tìm kiếm xe đang sẵn sàng (AVAILABLE và không trùng lịch nếu có khung giờ) để chatbot tư vấn."""
    query = db.query(Vehicle).filter(Vehicle.is_active == True)

    if start_time is not None and end_time is not None:
        vn_now = (datetime.now(timezone.utc) + timedelta(hours=7)).replace(tzinfo=None)
        query = query.filter(
            Vehicle.current_status != "MAINTENANCE",
            *_chat_no_conflict_conditions(Vehicle.id, start_time, end_time, vn_now),
        )
    else:
        query = query.filter(Vehicle.current_status == "AVAILABLE")

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


def _find_same_day_alternative_slots(
    vehicle_type: Optional[str],
    seats: Optional[int],
    target_date,
    requested_start: datetime,
    requested_end: datetime,
    db: Session,
    limit: int = 3,
) -> List[Dict[str, Any]]:
    """Khi khung giờ khách chọn đã hết xe, tìm các khung giờ khác còn trống trong cùng ngày."""
    vn_now = (datetime.now(timezone.utc) + timedelta(hours=7)).replace(tzinfo=None)
    candidate_hours = [(8, 12), (12, 16), (14, 18), (16, 20), (18, 22)]

    suggestions: List[Dict[str, Any]] = []
    seen_vehicle_ids = set()

    for sh, eh in candidate_hours:
        slot_start = datetime(target_date.year, target_date.month, target_date.day, sh, 0)
        slot_end = datetime(target_date.year, target_date.month, target_date.day, eh, 0)
        # Bỏ qua khung giờ trùng hoàn toàn với khung vừa hỏi hoặc đã qua trong ngày
        if slot_start == requested_start and slot_end == requested_end:
            continue
        if target_date == vn_now.date() and slot_end <= vn_now + timedelta(minutes=30):
            continue

        free_vehicles = search_vehicles_for_chat(
            vehicle_type=vehicle_type,
            seats=seats,
            start_time=slot_start,
            end_time=slot_end,
            db=db,
            limit=limit,
        )
        for v in free_vehicles:
            if v.id in seen_vehicle_ids:
                continue
            seen_vehicle_ids.add(v.id)
            suggestions.append({
                "vehicle": v,
                "slot_label": f"{slot_start.strftime('%H:%M')}–{slot_end.strftime('%H:%M')}",
            })
            if len(suggestions) >= limit:
                return suggestions

    return suggestions


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
