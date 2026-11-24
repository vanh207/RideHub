"""Pydantic schemas cho module Chatbot AI, Hội thoại & Kho tri thức."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Schemas Tin nhắn & Hội thoại
# ---------------------------------------------------------------------------

class ChatMessageRequest(BaseModel):
    """Payload gửi tin nhắn người dùng."""

    session_id: str = Field(
        ...,
        min_length=32,
        max_length=100,
        pattern=r"^[A-Za-z0-9-]+$",
        description="Mã phiên hội thoại (UUID4 do client sinh ngẫu nhiên)",
    )
    message: str = Field(..., min_length=1, max_length=2000, description="Nội dung câu hỏi của khách hàng")
    customer_name: Optional[str] = Field(None, max_length=100)
    customer_phone: Optional[str] = Field(None, max_length=20)


class KnowledgeCitation(BaseModel):
    """Trích dẫn tri thức được AI sử dụng để trả lời."""

    faq_id: int
    category: str
    category_name: str
    question: str
    relevance_score: float


class RateLimitMeta(BaseModel):
    """Thông tin hạn mức gọi Chatbot AI."""

    limit_per_minute: int
    remaining_minute: int
    limit_per_day: int
    remaining_day: int
    reset_seconds: int


class ChatMessageResponse(BaseModel):
    """Phản hồi thông minh từ Chatbot AI."""

    sender: str = Field("bot", description="bot | agent | system")
    message: str = Field(..., description="Câu trả lời từ Chatbot AI")
    detected_intent: Optional[str] = Field("general", description="Ý định phát hiện được")
    payload: Optional[Any] = None
    is_escalated: bool = Field(False, description="Đã chuyển tiếp tới nhân viên CSKH chưa")
    assigned_agent: Optional[str] = None

    # Thông tin AI & RAG
    ai_model: Optional[str] = Field(None, description="Tên mô hình AI sinh câu trả lời")
    citations: List[KnowledgeCitation] = Field(default_factory=list, description="Các tài liệu tri thức liên quan")
    rate_limit: Optional[RateLimitMeta] = Field(None, description="Hạn mức lượt gọi còn lại")
    created_at: datetime = Field(default_factory=datetime.now)


class ChatMessageItem(BaseModel):
    """Một dòng tin nhắn trong lịch sử trò chuyện."""

    id: int
    session_id: str
    sender: str
    message: str
    detected_intent: Optional[str] = None
    payload_json: Optional[Any] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationHistoryResponse(BaseModel):
    """Toàn bộ lịch sử hội thoại của một phiên."""

    session_id: str
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    status: str
    assigned_agent: Optional[str] = None
    escalation_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    messages: List[ChatMessageItem] = []


# ---------------------------------------------------------------------------
# Schemas Kho tri thức (Knowledge Base)
# ---------------------------------------------------------------------------

class KnowledgeSearchRequest(BaseModel):
    """Tìm kiếm trong kho tri thức."""

    query: str = Field(..., min_length=1, description="Từ khóa hoặc câu hỏi cần tra cứu")
    category: Optional[str] = Field(None, description="Lọc theo nhóm tri thức")
    limit: int = Field(3, ge=1, le=10, description="Số lượng kết quả tối đa")


class KnowledgeItemResponse(BaseModel):
    """Một mục tri thức."""

    id: int
    category: str
    category_name: str
    question: str
    answer: str
    display_order: int = 0
    is_active: bool = True
    view_count: int = 0
    relevance_score: Optional[float] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KnowledgeEntryCreate(BaseModel):
    """Thêm mới một mục vào kho tri thức."""

    category: str = Field(..., min_length=2, max_length=50, description="Mã nhóm: ekyc | deposit | delivery | emergency | cancel")
    category_name: str = Field(..., min_length=2, max_length=100, description="Tên nhóm hiển thị")
    question: str = Field(..., min_length=5, max_length=500, description="Câu hỏi hoặc chủ đề tri thức")
    answer: str = Field(..., min_length=10, description="Câu trả lời / chính sách chi tiết")
    display_order: int = Field(0, ge=0)
    is_active: bool = True
