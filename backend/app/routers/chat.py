"""Router xử lý Hội thoại Chatbot AI, Kho tri thức & Giới hạn lượt gọi (Chatbot API)."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_current_admin
from app.core.rate_limiter import chatbot_rate_limiter
from app.crud.chat import (
    add_knowledge_entry,
    delete_knowledge_entry,
    get_conversation_history,
    lookup_user_bookings_for_chat,
    process_ai_chat_message,
    reset_conversation,
    search_vehicles_for_chat,
    update_knowledge_entry,
)
from app.db.session import get_db
from app.models.faq import FAQ
from app.models.user import User
from app.schemas.chat import (
    ChatMessageRequest,
    ChatMessageResponse,
    ConversationHistoryResponse,
    KnowledgeEntryCreate,
    KnowledgeEntryUpdate,
    KnowledgeItemResponse,
    RateLimitMeta,
    UUID4_PATTERN,
    UserBookingLookupItem,
    VehicleSearchResultItem,
)
from app.services.ai_service import ai_service
from app.services.knowledge_base import KnowledgeBaseService

router = APIRouter(prefix="/chat", tags=["AI Chatbot — Hội thoại, Kho tri thức & Rate Limit"])


@router.get(
    "/status",
    summary="Kiểm tra trạng thái AI Provider & API Key đang dùng",
)
def get_chatbot_ai_status():
    """Trả về provider AI đang kích hoạt (gemini / openai / knowledge-fallback) mà không lộ API key."""
    return ai_service.get_provider_status()


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


def _try_get_optional_user(request: Request, db: Session) -> Optional[User]:
    """Lấy user nếu có gửi token hợp lệ, nếu không có token hoặc lỗi token thì trả về None (cho phép khách vãng lai chat)."""
    from app.core.security import decode_access_token
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
    elif request:
        token = (
            request.cookies.get("ridehub_token")
            or request.cookies.get("access_token")
            or request.cookies.get("token")
        )

    if not token:
        return None

    try:
        payload = decode_access_token(token)
        subject = payload.get("sub") if payload else None
        if not subject:
            return None
        user_id = int(subject)
        return db.query(User).filter(User.id == user_id, User.status == "active").first()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 1. Gửi tin nhắn & Nhận phản hồi AI (có Rate Limiting, RAG & Tool Execution)
# ---------------------------------------------------------------------------

@router.post(
    "/message",
    response_model=ChatMessageResponse,
    summary="Gửi tin nhắn tới Chatbot AI (Tự động tra cứu Kho tri thức, Tìm xe & Tra cứu đơn chính chủ)",
)
def handle_chat_message(
    payload: ChatMessageRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Tiếp nhận câu hỏi của người dùng, kiểm tra hạn mức gọi, tìm kiếm tri thức, tìm xe hoặc tra cứu đơn của chính user."""
    client_key = _get_client_identifier(request, payload.session_id)
    current_user = _try_get_optional_user(request, db)
    return process_ai_chat_message(payload, client_key, db, current_user=current_user)


# ---------------------------------------------------------------------------
# 2. Lịch sử hội thoại (Conversation History)
# ---------------------------------------------------------------------------

@router.get(
    "/conversations/{session_id}/messages",
    response_model=ConversationHistoryResponse,
    summary="Lấy toàn bộ lịch sử trò chuyện của phiên hội thoại",
)
def api_get_conversation_history(
    session_id: str = Path(..., pattern=UUID4_PATTERN, description="Mã phiên hội thoại UUID4 chuẩn RFC 4122"),
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
    session_id: str = Path(..., pattern=UUID4_PATTERN, description="Mã phiên hội thoại UUID4 chuẩn RFC 4122"),
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


@router.get(
    "/knowledge-base/admin",
    response_model=List[KnowledgeItemResponse],
    summary="Lấy toàn bộ danh sách FAQ kể cả mục tạm ẩn (Chỉ Admin)",
)
def api_admin_list_knowledge_base(
    q: Optional[str] = Query(None, description="Từ khóa tìm theo câu hỏi hoặc câu trả lời"),
    category: Optional[str] = Query(None, description="Lọc theo mã nhóm tri thức"),
    is_active: Optional[bool] = Query(None, description="Lọc theo trạng thái bật/tắt"),
    limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """API dành riêng cho trang Admin quản lý FAQ: trả về toàn bộ FAQ (kể cả đang tắt)."""
    query = db.query(FAQ)
    if category and category != "all":
        query = query.filter(FAQ.category == category)
    if is_active is not None:
        query = query.filter(FAQ.is_active == is_active)
    if q and q.strip():
        kw = f"%{q.strip()}%"
        query = query.filter((FAQ.question.ilike(kw)) | (FAQ.answer.ilike(kw)) | (FAQ.category_name.ilike(kw)))
    faqs = query.order_by(FAQ.display_order.asc(), FAQ.id.desc()).limit(limit).all()
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


@router.put(
    "/knowledge-base/{faq_id}",
    response_model=KnowledgeItemResponse,
    summary="Cập nhật một câu hỏi / chính sách trong Kho tri thức (Chỉ Admin)",
)
def api_update_knowledge_entry(
    faq_id: int,
    payload: KnowledgeEntryUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Cập nhật nội dung câu hỏi hoặc chính sách trong kho tri thức."""
    faq = update_knowledge_entry(faq_id, payload, db)
    if not faq:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy mục tri thức #{faq_id} để cập nhật.",
        )
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


# ---------------------------------------------------------------------------
# 5. Các API trợ lý Chatbot tìm xe & tra cứu đơn có kiểm soát
# ---------------------------------------------------------------------------

@router.get(
    "/tools/search-vehicles",
    response_model=List[VehicleSearchResultItem],
    summary="Công cụ tìm xe khả dụng cho Chatbot",
)
def api_search_vehicles_tool(
    keyword: Optional[str] = Query(None, description="Tên hãng hoặc mẫu xe"),
    vehicle_type: Optional[str] = Query(None, description="MOTORBIKE hoặc CAR"),
    max_price: Optional[float] = Query(None, description="Mức giá thuê tối đa theo ngày"),
    seats: Optional[int] = Query(None, description="Số chỗ ngồi (4, 5, 7...)"),
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """API tìm kiếm phương tiện có sẵn để Chatbot gợi ý cho khách thuê."""
    return search_vehicles_for_chat(
        keyword=keyword,
        vehicle_type=vehicle_type,
        max_price=max_price,
        seats=seats,
        db=db,
        limit=limit,
    )


@router.get(
    "/tools/my-bookings",
    response_model=List[UserBookingLookupItem],
    summary="Công cụ tra cứu đơn thuê có kiểm soát cho Chatbot (Chỉ trả đơn của chính user)",
)
def api_my_bookings_tool(
    booking_id: Optional[int] = Query(None, description="Mã đơn thuê cụ thể"),
    status: Optional[str] = Query(None, description="Lọc theo trạng thái đơn"),
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """API tra cứu đơn thuê có kiểm soát: CHỈ TRẢ ĐƠN CỦA CHÍNH NGƯỜI DÙNG ĐANG ĐĂNG NHẬP."""
    return lookup_user_bookings_for_chat(
        current_user_id=current_user.id,
        booking_id=booking_id,
        status_filter=status,
        db=db,
        limit=limit,
    )
