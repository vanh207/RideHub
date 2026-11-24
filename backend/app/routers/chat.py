"""Router xử lý Hội thoại Chatbot AI, Kho tri thức & Giới hạn lượt gọi (Chatbot API)."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.rate_limiter import chatbot_rate_limiter
from app.crud.chat import (
    add_knowledge_entry,
    delete_knowledge_entry,
    get_conversation_history,
    process_ai_chat_message,
    reset_conversation,
)
from app.db.session import get_db
from app.models.faq import FAQ
from app.models.user import User
from app.schemas.chat import (
    ChatMessageRequest,
    ChatMessageResponse,
    ConversationHistoryResponse,
    KnowledgeEntryCreate,
    KnowledgeItemResponse,
    RateLimitMeta,
)
from app.services.knowledge_base import KnowledgeBaseService

router = APIRouter(prefix="/chat", tags=["AI Chatbot — Hội thoại, Kho tri thức & Rate Limit"])


def require_admin(actor: User = Depends(get_current_user)) -> User:
    """Chỉ user có role 'admin' mới được quản lý kho tri thức."""
    if (actor.role or "").lower() != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ admin mới được quản lý kho tri thức.",
        )
    return actor


def _get_client_identifier(request: Request, session_id: str) -> str:
    """Xác định danh tính client từ session_id hoặc IP để áp dụng Rate Limiting."""
    # Ưu tiên session_id nếu có, kèm theo client IP
    client_ip = request.client.host if request.client else "127.0.0.1"
    return f"{session_id}@{client_ip}"


# ---------------------------------------------------------------------------
# 1. Gửi tin nhắn & Nhận phản hồi AI (có Rate Limiting & RAG)
# ---------------------------------------------------------------------------

@router.post(
    "/message",
    response_model=ChatMessageResponse,
    summary="Gửi tin nhắn tới Chatbot AI (Tự động tra cứu Kho tri thức & Giới hạn lượt gọi)",
)
def handle_chat_message(
    payload: ChatMessageRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Tiếp nhận câu hỏi của người dùng, kiểm tra hạn mức gọi, tìm kiếm tri thức và sinh phản hồi thông minh."""
    client_key = _get_client_identifier(request, payload.session_id)
    return process_ai_chat_message(payload, client_key, db)


# ---------------------------------------------------------------------------
# 2. Lịch sử hội thoại (Conversation History)
# ---------------------------------------------------------------------------

@router.get(
    "/conversations/{session_id}/messages",
    response_model=ConversationHistoryResponse,
    summary="Lấy toàn bộ lịch sử trò chuyện của phiên hội thoại",
)
def api_get_conversation_history(
    session_id: str = Path(..., min_length=32, max_length=100, pattern=r"^[A-Za-z0-9-]+$", description="Mã phiên hội thoại UUID4"),
    limit: int = Query(50, ge=1, le=200, description="Số lượng tin nhắn tối đa"),
    db: Session = Depends(get_db),
):
    """Lấy danh sách các tin nhắn đã gửi giữa User và Bot/Agent trong phiên này."""
    history = get_conversation_history(session_id, db, limit)
    if not history:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy phiên trò chuyện '{session_id}'.",
        )
    return history


@router.post(
    "/conversations/{session_id}/reset",
    summary="Reset phiên hội thoại để bắt đầu lại cuộc trò chuyện mới",
)
def api_reset_conversation(
    session_id: str = Path(..., min_length=32, max_length=100, pattern=r"^[A-Za-z0-9-]+$", description="Mã phiên hội thoại UUID4"),
    db: Session = Depends(get_db),
):
    """Xóa các tin nhắn cũ và đưa trạng thái phiên chat về AI_ACTIVE ban đầu."""
    success = reset_conversation(session_id, db)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy phiên trò chuyện '{session_id}' để reset.",
        )
    return {"message": "Phiên trò chuyện đã được làm mới thành công.", "session_id": session_id}


# ---------------------------------------------------------------------------
# 3. Trạng thái Giới hạn lượt gọi (Rate Limit Status)
# ---------------------------------------------------------------------------

@router.get(
    "/rate-limit-status",
    response_model=RateLimitMeta,
    summary="Kiểm tra hạn mức lượt gọi AI còn lại của phiên/IP",
)
def api_get_rate_limit_status(
    request: Request,
    session_id: str = Query("anonymous-session", description="Mã phiên hội thoại cần kiểm tra"),
):
    """Xem số lượt gọi Chatbot AI còn lại trong phút và trong ngày hiện tại."""
    client_key = _get_client_identifier(request, session_id)
    _, info = chatbot_rate_limiter.check(client_key)
    return RateLimitMeta(**info)


# ---------------------------------------------------------------------------
# 4. Quản lý Kho tri thức (Knowledge Base Management)
# ---------------------------------------------------------------------------

@router.get(
    "/knowledge-base",
    response_model=List[KnowledgeItemResponse],
    summary="Tìm kiếm và tra cứu trong kho tri thức của Chatbot",
)
def api_search_knowledge_base(
    q: Optional[str] = Query(None, description="Từ khóa hoặc câu hỏi cần tra cứu"),
    category: Optional[str] = Query(None, description="Nhóm tri thức: ekyc, deposit, cancel, emergency"),
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """Tìm kiếm các mẩu tri thức liên quan nhất dựa theo thuật toán tính điểm ngữ nghĩa/từ khóa."""
    if q:
        items = KnowledgeBaseService.search_knowledge(
            query=q,
            db=db,
            limit=limit,
            category=category,
        )
        return [
            KnowledgeItemResponse(
                id=item.id,
                category=item.category,
                category_name=item.category_name,
                question=item.question,
                answer=item.answer,
                relevance_score=item.relevance_score,
                created_at=getattr(item, "created_at", None) or None,  # FAQ model fields
            )
            for item in items
        ]

    # Nếu không truyền query -> trả về danh sách FAQ đang hoạt động
    query = db.query(FAQ).filter(FAQ.is_active == True)
    if category and category != "all":
        query = query.filter(FAQ.category == category)
    faqs = query.order_by(FAQ.display_order.asc()).limit(limit).all()
    return [KnowledgeItemResponse.model_validate(f) for f in faqs]


@router.post(
    "/knowledge-base",
    response_model=KnowledgeItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Thêm một câu hỏi / chính sách mới vào Kho tri thức (Chỉ Admin)",
)
def api_add_knowledge_entry(
    payload: KnowledgeEntryCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Thêm tài liệu/chính sách mới vào kho tri thức để Chatbot AI học và trả lời."""
    faq = add_knowledge_entry(payload, db)
    return KnowledgeItemResponse.model_validate(faq)


@router.delete(
    "/knowledge-base/{faq_id}",
    summary="Xóa một mục khỏi Kho tri thức (Chỉ Admin)",
)
def api_delete_knowledge_entry(
    faq_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Xóa mục tri thức theo ID."""
    success = delete_knowledge_entry(faq_id, db)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy mục tri thức #{faq_id}.",
        )
    return {"message": f"Đã xóa thành công mục tri thức #{faq_id}."}
