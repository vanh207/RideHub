"""Bộ kiểm thử toàn diện cho Chatbot AI, Kho tri thức & Giới hạn lượt gọi (Rate Limiting).

10 Test Cases:
TC-CHAT-01: Tìm kiếm trong Kho tri thức (Knowledge Base Search) theo độ tương đồng.
TC-CHAT-02: Đóng gói Context tri thức (RAG Context Builder) cho mô hình AI.
TC-CHAT-03: Lớp tích hợp Mô hình AI (AI Integration Layer) phản hồi thông minh có trích dẫn.
TC-CHAT-04: Tiếp nhận tin nhắn người dùng, lưu DB lịch sử và trả lời tự động.
TC-CHAT-05: Giới hạn lượt gọi (Rate Limiting) — Chặn và trả về HTTP 429 khi vượt quá hạn mức.
TC-CHAT-06: Phục hồi hạn mức sau khi reset rate limit key.
TC-CHAT-07: Tự động phát hiện khiếu nại và chuyển tiếp nhân viên hỗ trợ (Agent Escalation).
TC-CHAT-08: Lấy toàn bộ lịch sử trò chuyện của một phiên hội thoại.
TC-CHAT-09: Reset làm mới phiên hội thoại để bắt đầu lại cuộc trò chuyện mới.
TC-CHAT-10: Quản lý Kho tri thức (CRUD Knowledge Base: Thêm mới, tra cứu và Xóa).
"""
from __future__ import annotations

import time
from datetime import datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Nạp TOÀN BỘ models trước để SQLAlchemy mapper biết tất cả class
import app.models  # noqa: F401

from app.db.session import Base
from app.models.chat import ChatConversation, ChatMessage
from app.models.faq import FAQ
from app.core.rate_limiter import InMemoryRateLimiter, enforce_chatbot_rate_limit
from app.services.knowledge_base import KnowledgeBaseService, calculate_relevance
from app.services.ai_service import AIService, KnowledgeFallbackProvider
from app.crud.chat import (
    add_knowledge_entry,
    delete_knowledge_entry,
    get_conversation_history,
    get_or_create_conversation,
    process_ai_chat_message,
    reset_conversation,
)
from app.schemas.chat import (
    ChatMessageRequest,
    KnowledgeEntryCreate,
)

# ---------------------------------------------------------------------------
# SQLite in-memory DB cho test
# ---------------------------------------------------------------------------

SQLITE_URL = "sqlite://"

engine = create_engine(
    SQLITE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="module", autouse=True)
def create_tables():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _seed_faqs(db):
    """Nạp dữ liệu mẫu vào Kho tri thức (FAQ Knowledge Base)."""
    faqs = [
        FAQ(
            category="ekyc",
            category_name="Thủ tục xác thực danh tính eKYC",
            question="Thủ tục xác thực giấy tờ eKYC cần chuẩn bị những gì?",
            answer="Quý khách chỉ cần chuẩn bị CCCD gắn chip (hoặc Hộ chiếu) và Giấy phép lái xe hợp lệ (Bằng B1/B2 cho ô tô, A1/A2 cho xe máy). AI sẽ phê duyệt tự động trong 3 đến 5 phút.",
            display_order=1,
            is_active=True,
        ),
        FAQ(
            category="deposit",
            category_name="Chính sách tiền cọc & Hoàn tiền",
            question="Khi nào tôi được nhận lại tiền cọc thuê xe?",
            answer="Tiền đặt cọc được RideHub hoàn trả tự động 100% vào tài khoản ngân hàng của Quý khách ngay khi hoàn tất biên bản nhận lại xe (Check-in) nếu xe nguyên vẹn và không phát sinh phụ phí.",
            display_order=2,
            is_active=True,
        ),
        FAQ(
            category="cancel",
            category_name="Chính sách hủy đơn & Hoàn tiền",
            question="Hủy đơn đặt xe trước bao lâu thì được hoàn tiền 100%?",
            answer="Quý khách được hủy đơn hoàn tiền 100% miễn phí nếu thực hiện trước giờ nhận xe tối thiểu 24 tiếng. Nếu cửa hàng hủy đơn vì lý do bất khả kháng, Quý khách luôn được hoàn 100% tiền cọc.",
            display_order=3,
            is_active=True,
        ),
        FAQ(
            category="emergency",
            category_name="Hỗ trợ sự cố & Cứu hộ khẩn cấp",
            question="Xe bị sự cố thủng lốp hoặc hỏng hóc trên đường thì làm thế nào?",
            answer="Quý khách hãy bật đèn Hazard khẩn cấp, tấp vào lề an toàn và bấm nút gọi ngay Hotline cứu hộ 24/7 của RideHub: 1900-7433 để kỹ thuật viên xuất phát cứu hộ tận nơi.",
            display_order=4,
            is_active=True,
        ),
    ]
    for f in faqs:
        existing = db.query(FAQ).filter(FAQ.question == f.question).first()
        if not existing:
            db.add(f)
    db.commit()


@pytest.fixture()
def db():
    session = TestSession()
    try:
        _seed_faqs(session)
        yield session
    finally:
        session.close()


# ---------------------------------------------------------------------------
# TC-CHAT-01: Tìm kiếm trong Kho tri thức theo độ liên quan
# ---------------------------------------------------------------------------

def test_01_knowledge_base_search(db):
    """TC-CHAT-01: Tra cứu câu hỏi về 'xác thực eKYC bằng lái' tìm ra đúng bài eKYC."""
    results = KnowledgeBaseService.search_knowledge(
        query="cần chuẩn bị bằng lái và cccd ekyc như thế nào",
        db=db,
        limit=2,
    )
    assert len(results) > 0
    top_item = results[0]
    assert top_item.category == "ekyc"
    assert "eKYC" in top_item.question
    assert top_item.relevance_score > 0.0


# ---------------------------------------------------------------------------
# TC-CHAT-02: Đóng gói RAG Context cho mô hình AI
# ---------------------------------------------------------------------------

def test_02_knowledge_base_rag_context_building(db):
    """TC-CHAT-02: Tạo chuỗi ngữ cảnh RAG từ các mẩu tri thức liên quan."""
    results = KnowledgeBaseService.search_knowledge(query="hoàn tiền cọc", db=db, limit=1)
    context_str = KnowledgeBaseService.build_rag_context(results)

    assert "Chính sách tiền cọc & Hoàn tiền" in context_str
    assert "hoàn trả tự động 100%" in context_str


# ---------------------------------------------------------------------------
# TC-CHAT-03: Lớp tích hợp Mô hình AI phản hồi thông minh
# ---------------------------------------------------------------------------

def test_03_ai_service_integration_fallback():
    """TC-CHAT-03: Gọi AI Service, tự động fallback sang knowledge engine trả lời đúng chính sách."""
    provider = KnowledgeFallbackProvider()
    rag_context = "Quý khách được hoàn cọc 100% ngay khi hoàn tất biên bản nhận lại xe."
    
    res = provider.generate_response(
        user_message="Khi nào tôi được nhận lại tiền cọc?",
        conversation_history=[],
        rag_context=rag_context,
    )

    assert "100%" in res["text"]
    assert res["provider"] == "knowledge-base"


# ---------------------------------------------------------------------------
# TC-CHAT-04: Tiếp nhận tin nhắn, lưu lịch sử và trả lời tự động
# ---------------------------------------------------------------------------

def test_04_chat_message_success_and_save_history(db):
    """TC-CHAT-04: Gửi tin nhắn -> Lưu DB tin nhắn của User & Bot, trả về trích dẫn tri thức."""
    session_id = "c3a2f871-6c2e-4b41-9fb8-53e390c58e6e"
    req = ChatMessageRequest(
        session_id=session_id,
        message="Thủ tục xác thực ekyc cần những gì?",
        customer_name="Nguyễn Văn A",
    )

    res = process_ai_chat_message(req, client_identifier=session_id, db=db)

    assert res.sender == "bot"
    assert len(res.citations) > 0
    assert res.citations[0].category == "ekyc"
    assert res.rate_limit is not None

    # Kiểm tra DB đã lưu đủ 2 tin nhắn (1 USER, 1 BOT)
    msgs = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).all()
    assert len(msgs) == 2
    assert msgs[0].sender == "USER"
    assert msgs[1].sender == "BOT"


# ---------------------------------------------------------------------------
# TC-CHAT-05: Rate Limiting — Chặn khi vượt quá quota gọi
# ---------------------------------------------------------------------------

def test_05_rate_limiter_enforcement_blocks_spam():
    """TC-CHAT-05: Rate limiter giới hạn 3 calls/phút, call thứ 4 bị raise HTTP 429."""
    limiter = InMemoryRateLimiter(requests_per_minute=3, requests_per_day=10)
    key = "spammer-ip-05"

    # 3 calls đầu hợp lệ
    for _ in range(3):
        allowed, info = limiter.check(key)
        assert allowed is True

    # Call thứ 4 bị chặn
    allowed, info = limiter.check(key)
    assert allowed is False
    assert info["remaining_minute"] == 0
    assert "Vượt quá giới hạn" in info["reason"]


# ---------------------------------------------------------------------------
# TC-CHAT-06: Phục hồi hạn mức sau khi reset rate limit key
# ---------------------------------------------------------------------------

def test_06_rate_limiter_recovery_after_reset():
    """TC-CHAT-06: Sau khi reset key, người dùng được tiếp tục gọi bình thường."""
    limiter = InMemoryRateLimiter(requests_per_minute=2, requests_per_day=5)
    key = "blocked-user-06"

    limiter.check(key)
    limiter.check(key)
    allowed, _ = limiter.check(key)
    assert allowed is False

    # Reset
    limiter.reset_key(key)
    allowed, info = limiter.check(key)
    assert allowed is True
    assert info["remaining_minute"] == 1


# ---------------------------------------------------------------------------
# TC-CHAT-07: Tự động chuyển tiếp nhân viên khi có khiếu nại (Agent Escalation)
# ---------------------------------------------------------------------------

def test_07_agent_escalation_on_complaint(db):
    """TC-CHAT-07: Khách hàng gõ 'khiếu nại lừa đảo' -> chuyển tiếp nhân viên CSKH."""
    session_id = "d4b3c2a1-7d3f-4e52-a0c9-64f401d69f7f"
    req = ChatMessageRequest(
        session_id=session_id,
        message="Tôi muốn khiếu nại nhân viên vì chưa thấy hoàn cọc!",
    )

    res = process_ai_chat_message(req, client_identifier=session_id, db=db)

    assert res.is_escalated is True
    assert res.sender == "agent"
    assert res.assigned_agent is not None

    conv = db.query(ChatConversation).filter(ChatConversation.session_id == session_id).first()
    assert conv.status == "ESCALATED_TO_AGENT"
    assert conv.assigned_agent is not None


# ---------------------------------------------------------------------------
# TC-CHAT-08: Lấy toàn bộ lịch sử trò chuyện của một phiên
# ---------------------------------------------------------------------------

def test_08_conversation_history_retrieval(db):
    """TC-CHAT-08: Lấy lịch sử hội thoại hiển thị đầy đủ tin nhắn."""
    session_id = "e5c4d3b2-8e4a-4f63-b1da-75a512e70a8a"
    get_or_create_conversation(session_id, "Khách B", "0901234567", db)

    req1 = ChatMessageRequest(session_id=session_id, message="Chào bạn")
    process_ai_chat_message(req1, client_identifier=session_id, db=db)

    req2 = ChatMessageRequest(session_id=session_id, message="Cho mình hỏi giá xe")
    process_ai_chat_message(req2, client_identifier=session_id, db=db)

    history = get_conversation_history(session_id, db)
    assert history is not None
    assert history.session_id == session_id
    assert len(history.messages) == 4  # 2 user msgs + 2 bot msgs


# ---------------------------------------------------------------------------
# TC-CHAT-09: Reset phiên hội thoại
# ---------------------------------------------------------------------------

def test_09_reset_conversation(db):
    """TC-CHAT-09: Reset phiên trò chuyện xóa sạch tin nhắn và trả về AI_ACTIVE."""
    session_id = "f6d5e4c3-9f5b-4a74-82eb-86b623f81b9b"
    req = ChatMessageRequest(session_id=session_id, message="Tin nhắn thử nghiệm")
    process_ai_chat_message(req, client_identifier=session_id, db=db)

    # Đảm bảo đã có tin nhắn
    assert db.query(ChatMessage).filter(ChatMessage.session_id == session_id).count() > 0

    # Reset
    success = reset_conversation(session_id, db)
    assert success is True
    assert db.query(ChatMessage).filter(ChatMessage.session_id == session_id).count() == 0

    conv = db.query(ChatConversation).filter(ChatConversation.session_id == session_id).first()
    assert conv.status == "AI_ACTIVE"


# ---------------------------------------------------------------------------
# TC-CHAT-10: Quản lý Kho tri thức (Thêm mới & Xóa) & Phân quyền Admin
# ---------------------------------------------------------------------------

def test_10_crud_knowledge_base_add_and_delete(db):
    """TC-CHAT-10: Thêm tài liệu mới vào Kho tri thức, tra cứu thấy, rồi xóa thành công."""
    entry = KnowledgeEntryCreate(
        category="insurance",
        category_name="Bảo hiểm xe tự lái",
        question="Gói bảo hiểm vật chất xe gồm những quyền lợi gì?",
        answer="Gói bảo hiểm vật chất RideHub bồi thường toàn bộ chi phí sửa chữa thân vỏ do va chạm không mong muốn.",
        display_order=10,
        is_active=True,
    )

    created_faq = add_knowledge_entry(entry, db)
    assert created_faq.id is not None
    assert created_faq.category == "insurance"

    # Tra cứu ngay trong kho tri thức
    search_res = KnowledgeBaseService.search_knowledge(query="bảo hiểm vật chất", db=db, limit=1)
    assert len(search_res) > 0
    assert search_res[0].id == created_faq.id

    # Xóa
    del_ok = delete_knowledge_entry(created_faq.id, db)
    assert del_ok is True
    assert db.query(FAQ).filter(FAQ.id == created_faq.id).first() is None


# ---------------------------------------------------------------------------
# TC-CHAT-11: Kiểm tra phân quyền require_admin bảo vệ Kho tri thức
# ---------------------------------------------------------------------------

def test_11_require_admin_guard():
    """TC-CHAT-11: require_admin chặn user không phải admin bằng HTTP 403, cho phép admin."""
    from unittest.mock import MagicMock
    from fastapi import HTTPException
    from app.routers.chat import require_admin

    # Khách hoặc user thường (role: customer)
    normal_user = MagicMock()
    normal_user.role = "customer"
    with pytest.raises(HTTPException) as exc_info:
        require_admin(actor=normal_user)
    assert exc_info.value.status_code == 403
    assert "Chỉ admin mới được quản lý" in exc_info.value.detail

    # Nhân viên cửa hàng (role: store_staff)
    staff_user = MagicMock()
    staff_user.role = "store_staff"
    with pytest.raises(HTTPException) as exc_info:
        require_admin(actor=staff_user)
    assert exc_info.value.status_code == 403

    # Quản trị viên (role: admin)
    admin_user = MagicMock()
    admin_user.id = 3
    admin_user.role = "admin"
    validated_admin = require_admin(actor=admin_user)
    assert validated_admin.id == 3
    assert validated_admin.role == "admin"


def test_12_session_id_uuid_validation_blocks_predictable_id():
    """TC-CHAT-12: Chặn session_id không đúng định dạng UUID4 chuẩn RFC 4122."""
    from pydantic import ValidationError

    # Session ID quá ngắn (dễ đoán) -> Bị ValidationError
    with pytest.raises(ValidationError):
        ChatMessageRequest(
            session_id="short-id",
            message="Xin chào",
        )

    # Session ID toàn chữ lặp lại 32 ký tự (aaaaaaaa...) không đúng format UUID4 -> Bị chặn
    with pytest.raises(ValidationError):
        ChatMessageRequest(
            session_id="a" * 32,
            message="Xin chào",
        )

    with pytest.raises(ValidationError):
        ChatMessageRequest(
            session_id="user-1",
            message="Xin chào",
        )

    # Session ID chuẩn UUID4 hợp lệ
    valid_req = ChatMessageRequest(
        session_id="c3a2f871-6c2e-4b41-9fb8-53e390c58e6e",
        message="Xin chào",
    )
    assert valid_req.session_id == "c3a2f871-6c2e-4b41-9fb8-53e390c58e6e"


# ---------------------------------------------------------------------------
# TC-CHAT-13: Kiểm tra Router Endpoints với validation UUID4 và xử lý lỗi
# ---------------------------------------------------------------------------

def test_13_api_router_endpoints_validation_and_flow(db):
    """TC-CHAT-13: Kiểm tra trực tiếp handler router api /api/chat với session_id hợp lệ và không hợp lệ."""
    from app.routers.chat import handle_chat_message, api_get_conversation_history, api_reset_conversation
    from starlette.requests import Request
    from pydantic import ValidationError

    # 1. Thử tạo ChatMessageRequest với session_id sai (ngắn / không đúng UUID4) -> Bị ValidationError ngay lập tức (Pydantic trả về 422 trên FastAPI)
    with pytest.raises(ValidationError):
        ChatMessageRequest(
            session_id="short-id",
            message="Giá thuê xe thế nào?",
        )

    with pytest.raises(ValidationError):
        ChatMessageRequest(
            session_id="a" * 32,  # Chuỗi 32 ký tự không gạch nối
            message="Giá thuê xe thế nào?",
        )

    # 2. Gửi request hợp lệ với UUID4 chuẩn RFC 4122
    valid_uuid = "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"
    req = ChatMessageRequest(
        session_id=valid_uuid,
        message="Thủ tục xác thực ekyc cần những gì?",
    )

    # Giả lập Request object
    scope = {"type": "http", "client": ("127.0.0.1", 12345), "headers": []}
    mock_request = Request(scope)

    res = handle_chat_message(payload=req, request=mock_request, db=db)
    assert res.sender in ["bot", "agent"]
    assert len(res.citations) > 0
    assert res.rate_limit is not None

    # 3. Lấy lịch sử qua api_get_conversation_history
    history = api_get_conversation_history(session_id=valid_uuid, limit=10, db=db)
    assert history.session_id == valid_uuid
    assert len(history.messages) == 2

    # 4. Reset phiên qua api_reset_conversation
    reset_res = api_reset_conversation(session_id=valid_uuid, db=db)
    assert "thành công" in reset_res["message"]
