"""CRUD & Nghiệp vụ Hội thoại Chatbot AI, Kho tri thức & Giới hạn lượt gọi."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limiter import enforce_chatbot_rate_limit
from app.models.chat import ChatConversation, ChatMessage
from app.models.faq import FAQ
from app.schemas.chat import (
    ChatMessageItem,
    ChatMessageRequest,
    ChatMessageResponse,
    ConversationHistoryResponse,
    KnowledgeCitation,
    KnowledgeEntryCreate,
    RateLimitMeta,
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
) -> ChatMessageResponse:
    """Quy trình xử lý tin nhắn Chatbot AI hoàn chỉnh:
    
    1. Kiểm tra Giới hạn lượt gọi (Rate Limiting).
    2. Lưu tin nhắn người dùng.
    3. Tra cứu Kho tri thức (RAG - Knowledge Base Search).
    4. Xử lý kịch bản leo thang nhân viên (Agent Escalation) nếu có khiếu nại.
    5. Gọi Lớp tích hợp Mô hình AI (AI Integration Layer) với RAG Context.
    6. Lưu phản hồi của BOT kèm trích dẫn (Citations).
    7. Trả về Response chuẩn xác cho Frontend.
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
    escalation_triggers = ["gặp người", "gặp nhân viên", "nhân viên cskh", "lừa đảo", "khiếu nại", "tố cáo", "hoàn cọc ngay"]
    if any(k in query_lower for k in escalation_triggers) and not is_escalated:
        is_escalated = True
        assigned_agent = "Mai Linh (Trưởng ca CSKH RideHub)"
        conv.status = "ESCALATED_TO_AGENT"
        conv.assigned_agent = assigned_agent
        conv.escalation_reason = "Khách hàng yêu cầu hỗ trợ trực tiếp từ nhân viên CSKH"
        db.commit()

        bot_text = (
            "Dạ em rất hiểu Quý khách đang cần được xử lý nhanh nhất ạ! 🙏\n\n"
            f"Em đang kết nối cuộc trò chuyện này trực tiếp đến Chuyên viên Quản lý Vận hành RideHub ({assigned_agent}) "
            "để hỗ trợ xử lý ngay lập tức cho Quý khách. Chuyên viên sẽ phản hồi trong giây lát!"
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

    # 6. TRA CỨU KHO TRI THỨC (KNOWLEDGE BASE RAG)
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
# Quản lý Kho tri thức (Knowledge Base Management)
# ---------------------------------------------------------------------------

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
