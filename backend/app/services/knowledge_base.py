"""Kho tri thức (Knowledge Base) phục vụ Chatbot AI — RAG Engine cho RideHub.

Chức năng:
- Truy xuất các mẩu thông tin chính sách, giá cả, eKYC, hoàn tiền từ bảng FAQ.
- Tìm kiếm thông minh dựa trên độ tương đồng từ khóa, ngữ cảnh câu hỏi (Relevance Scoring).
- Định dạng Context chuẩn để cung cấp cho mô hình AI làm căn cứ trả lời, chống bịa đặt (anti-hallucination).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session
from app.models.faq import FAQ


@dataclass
class KnowledgeItem:
    id: int
    category: str
    category_name: str
    question: str
    answer: str
    relevance_score: float = 0.0


def _remove_accents(text: str) -> str:
    """Loại bỏ dấu tiếng Việt để tìm kiếm không dấu/có dấu."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def _tokenize(text: str) -> set[str]:
    """Tách từ đơn giản và loại bỏ từ vô nghĩa."""
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    words = cleaned.split()
    stop_words = {"là", "có", "không", "gì", "cho", "của", "và", "ở", "tại", "thì", "được", "ạ", "dạ", "em", "tôi", "mình"}
    return {w for w in words if len(w) > 1 and w not in stop_words}


def calculate_relevance(query: str, question: str, answer: str, category: str) -> float:
    """Tính điểm độ liên quan giữa câu hỏi người dùng và một mục tri thức."""
    q_tokens = _tokenize(query)
    if not q_tokens:
        return 0.0

    target_tokens = _tokenize(question)
    ans_tokens = _tokenize(answer)
    cat_tokens = _tokenize(category)

    # 1. Trùng khớp chính xác từ ngữ trong câu hỏi FAQ (trọng số cao nhất)
    question_overlap = len(q_tokens & target_tokens)
    # 2. Trùng khớp trong câu trả lời FAQ
    answer_overlap = len(q_tokens & ans_tokens)
    # 3. Trùng khớp nhóm danh mục (ekyc, deposit, cancel, etc.)
    category_overlap = len(q_tokens & cat_tokens)

    # Kiểm tra chuỗi con không dấu
    norm_query = _remove_accents(query)
    norm_question = _remove_accents(question)
    substring_bonus = 2.0 if norm_query in norm_question or norm_question in norm_query else 0.0

    score = (
        (question_overlap * 3.0)
        + (answer_overlap * 1.0)
        + (category_overlap * 2.0)
        + substring_bonus
    )
    return score


class KnowledgeBaseService:
    """Service tìm kiếm và quản lý kho tri thức của hệ thống."""

    @staticmethod
    def search_knowledge(
        query: str,
        db: Session,
        limit: int = 3,
        min_score: float = 1.0,
        category: Optional[str] = None,
    ) -> List[KnowledgeItem]:
        """Tìm kiếm các mục tri thức phù hợp nhất với câu hỏi của khách hàng."""
        faq_query = db.query(FAQ).filter(FAQ.is_active == True)
        if category and category != "all":
            faq_query = faq_query.filter(FAQ.category == category)

        all_faqs = faq_query.all()
        scored_items: List[KnowledgeItem] = []

        for f in all_faqs:
            score = calculate_relevance(
                query=query,
                question=f.question,
                answer=f.answer,
                category=f"{f.category} {f.category_name}",
            )
            if score >= min_score:
                scored_items.append(
                    KnowledgeItem(
                        id=f.id,
                        category=f.category,
                        category_name=f.category_name,
                        question=f.question,
                        answer=f.answer,
                        relevance_score=score,
                    )
                )

        # Sắp xếp theo điểm liên quan giảm dần
        scored_items.sort(key=lambda x: x.relevance_score, reverse=True)
        return scored_items[:limit]

    @staticmethod
    def build_rag_context(knowledge_items: List[KnowledgeItem]) -> str:
        """Đóng gói các đoạn tri thức thành đoạn Context để gửi vào Prompt cho AI Model."""
        if not knowledge_items:
            return "Không tìm thấy thông tin cụ thể trong kho tri thức cho câu hỏi này."

        context_parts = []
        for idx, item in enumerate(knowledge_items, 1):
            context_parts.append(
                f"[Tài liệu {idx} - Chủ đề: {item.category_name}]\n"
                f"Câu hỏi thường gặp: {item.question}\n"
                f"Chính sách & Hướng dẫn: {item.answer}"
            )
        return "\n\n".join(context_parts)
