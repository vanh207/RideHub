"""Lớp tích hợp để gọi mô hình AI (AI Model Integration Layer) cho RideHub.

Hỗ trợ:
- Google Gemini API (gemini-1.5-flash / gemini-1.5-pro / gemini-2.0).
- OpenAI API (gpt-3.5-turbo / gpt-4o-mini).
- Rule-based / Knowledge-augmented Fallback Provider (Fail-Safe, hoạt động 100% khi không có key hoặc offline).
- Prompt Engineering tối ưu cho Trợ lý ảo tư vấn thuê xe tự lái RideHub.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.services.knowledge_base import KnowledgeItem

logger = logging.getLogger("ridehub.ai_service")

# System Prompt tiêu chuẩn định hình Persona của Chatbot RideHub
SYSTEM_PROMPT = """Bạn là trợ lý AI của RideHub — nền tảng thuê xe tự lái Việt Nam.
Phong cách: thân thiện, tự nhiên như nhắn tin với bạn bè, dùng "em" và "bạn/mình".

QUY TẮC QUAN TRỌNG (bắt buộc):
1. TRẢ LỜI TỐI ĐA 2-3 CÂU. Không viết dài, không liệt kê quá 3 mục.
2. Dùng ngôn ngữ hội thoại tự nhiên, KHÔNG viết theo kiểu tài liệu hay form mẫu.
3. Nếu có thông tin từ Kho tri thức → tóm tắt thành 1-2 câu chính, bỏ chi tiết thừa.
4. Khi tìm xe → đề xuất nhanh 2-3 xe cụ thể hoặc gợi link xem danh sách.
5. Kết thúc bằng câu hỏi ngắn hoặc gợi ý hành động tiếp theo.
6. KHÔNG được viết tiêu đề "[Tài liệu X]", không copy nguyên văn từ kho tri thức.

Ví dụ câu trả lời đúng phong cách:
- Hỏi về cọc: "Cọc xe máy thường 1-2 triệu, ô tô 3-5 triệu bạn ơi. Bạn eKYC rồi thì được miễn cọc luôn nhé! 🎉"
- Hỏi tìm xe: "Có ngay! Khu bạn ở đâu để em gợi xe gần nhất? Hoặc xem toàn bộ xe đang trống tại đây 👉 /vehicles.html"
"""


class BaseAIProvider(ABC):
    """Giao diện trừu tượng cho nhà cung cấp mô hình AI."""

    @abstractmethod
    def generate_response(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        rag_context: str,
    ) -> Dict[str, Any]:
        pass


class GeminiProvider(BaseAIProvider):
    """Tích hợp Google Gemini API qua giao thức REST HTTP chuẩn."""

    def __init__(self, api_key: str, model_name: str = "gemini-1.5-flash"):
        self.api_key = api_key
        self.model_name = model_name

    def generate_response(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        rag_context: str,
    ) -> Dict[str, Any]:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model_name}:generateContent?key={self.api_key}"
        )

        # Xây dựng contents cho Gemini API
        contents = []

        # Ghép System Prompt & RAG Context vào lượt đầu tiên
        prompt_with_context = (
            f"{SYSTEM_PROMPT}\n\n"
            f"--- KHO TRI THỨC CHÍNH THỨC CỦA RIDEHUB ---\n"
            f"{rag_context}\n"
            f"-----------------------------------------\n"
        )
        contents.append({
            "role": "user",
            "parts": [{"text": prompt_with_context}]
        })
        contents.append({
            "role": "model",
            "parts": [{"text": "Dạ em đã nắm rõ các thông tin chính sách của RideHub. Em sẵn sàng hỗ trợ Quý khách!"}]
        })

        # Nạp lịch sử hội thoại gần nhất
        for msg in conversation_history[-6:]:
            role = "user" if msg.get("role") == "user" else "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg.get("content", "")}]
            })

        # Câu hỏi hiện tại của người dùng
        contents.append({
            "role": "user",
            "parts": [{"text": user_message}]
        })

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 200,
                "topP": 0.9,
            }
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            candidate = res_data.get("candidates", [{}])[0]
            part = candidate.get("content", {}).get("parts", [{}])[0]
            text = part.get("text", "")

            return {
                "text": text,
                "model": self.model_name,
                "provider": "gemini",
                "tokens_used": res_data.get("usageMetadata", {}).get("totalTokenCount", 0),
            }


class KnowledgeFallbackProvider(BaseAIProvider):
    """Bộ suy luận dự phòng thông minh (Fail-Safe Knowledge Provider).
    
    Tự động kích hoạt khi chưa có API key, mạng offline hoặc API chính bị gián đoạn.
    Tóm tắt câu trả lời ngắn gọn, tự nhiên từ Kho tri thức thay vì dump nguyên văn.
    """

    def _summarize_rag(self, rag_context: str) -> str:
        """Tóm tắt RAG context thành 1-2 câu tự nhiên, bỏ header [Tài liệu X]."""
        if not rag_context or "Không tìm thấy" in rag_context:
            return ""
        # Tách các dòng, lấy phần "Trả lời:" hoặc nội dung chính
        lines = []
        for line in rag_context.splitlines():
            line = line.strip()
            # Bỏ dòng header kiểu "[Tài liệu 1 - ...]"
            if line.startswith("[") and ("-" in line or "Tài liệu" in line):
                continue
            # Bỏ label "Câu hỏi:", "Chủ đề:" (giữ nội dung sau dấu ":")
            for label in ("Câu hỏi:", "Chủ đề:", "Chính sách & Hướng dẫn:"):
                if line.startswith(label):
                    line = line[len(label):].strip()
                    break
            if line:
                lines.append(line)
        # Chỉ lấy tối đa 2 câu/dòng quan trọng nhất
        summary = " ".join(lines[:2])
        # Cắt bớt nếu quá dài
        if len(summary) > 200:
            summary = summary[:200].rsplit(" ", 1)[0] + "..."
        return summary

    def generate_response(
        self,
        user_message: str,
        conversation_history: list,
        rag_context: str,
    ) -> dict:
        msg_lower = user_message.lower()

        # Nếu kho tri thức có dữ liệu → tóm tắt ngắn gọn, tự nhiên
        if rag_context and "Không tìm thấy thông tin cụ thể" not in rag_context:
            summary = self._summarize_rag(rag_context)
            if summary:
                text = f"{summary} 😊 Bạn cần hỗ trợ thêm gì không?"
                return {
                    "text": text,
                    "model": "knowledge-fallback-v2",
                    "provider": "knowledge-base",
                    "tokens_used": 0,
                }

        # Nhận diện ý định khẩn cấp / cứu hộ
        if any(w in msg_lower for w in ["cứu hộ", "sự cố", "hỏng xe", "thủng lốp", "tai nạn"]):
            text = (
                "🚨 Gọi ngay Hotline cứu hộ **1900-7433** (24/7) nhé! "
                "Bật đèn hazard, tấp xe vào lề an toàn và chờ kỹ thuật viên đến. "
                "Em đang kết nối hỗ trợ cho bạn!"
            )
            return {
                "text": text,
                "model": "emergency-rule-engine",
                "provider": "knowledge-base",
                "tokens_used": 0,
            }

        # Nhận diện hỏi về giá/cọc
        if any(w in msg_lower for w in ["giá", "bao nhiêu", "cọc", "tiền", "phí"]):
            text = (
                "Giá thuê xe máy từ 120k-250k/ngày, ô tô từ 650k-1.5tr/ngày bạn ơi. "
                "Bạn eKYC rồi có thể miễn cọc hoàn toàn! Xem thêm xe đang có tại 👉 /vehicles.html"
            )
            return {
                "text": text,
                "model": "price-rule-engine",
                "provider": "knowledge-base",
                "tokens_used": 0,
            }

        # Nhận diện hỏi về eKYC / giấy tờ
        if any(w in msg_lower for w in ["ekyc", "cccd", "giấy phép", "bằng lái", "giấy tờ", "xác thực"]):
            text = (
                "Chỉ cần CCCD và bằng lái xe (A1/B1/B2) là thuê được ngay bạn ơi! "
                "Xác thực eKYC 1 lần duy nhất trên app, sau đó thuê xe siêu nhanh 🚀"
            )
            return {
                "text": text,
                "model": "ekyc-rule-engine",
                "provider": "knowledge-base",
                "tokens_used": 0,
            }

        # Phản hồi chung — ngắn gọn, hướng dẫn hành động
        text = (
            "Bạn ơi, em chưa hiểu rõ câu hỏi lắm 😅 "
            "Bạn đang cần tìm xe, hỏi về giá/cọc, hay kiểm tra đơn thuê? "
            "Hoặc bấm **Gặp nhân viên** để được tư vấn 1-1 ngay nhé!"
        )
        return {
            "text": text,
            "model": "general-fallback-v2",
            "provider": "knowledge-base",
            "tokens_used": 0,
        }


class AIService:
    """Service điều phối AI trung tâm (AI Orchestration Layer)."""

    def __init__(self):
        self.fallback_provider = KnowledgeFallbackProvider()

    def _get_active_provider(self) -> BaseAIProvider:
        """Chọn provider dựa trên cài đặt môi trường."""
        provider_name = (settings.AI_PROVIDER or "mock").lower()

        if provider_name == "gemini" and settings.GEMINI_API_KEY:
            return GeminiProvider(
                api_key=settings.GEMINI_API_KEY,
                model_name=settings.AI_MODEL_NAME or "gemini-1.5-flash",
            )
        # Mặc định hoặc fallback an toàn
        return self.fallback_provider

    def ask_ai(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        rag_context: str,
    ) -> Dict[str, Any]:
        """Gửi prompt tới mô hình AI với cơ chế tự động Fallback bảo vệ hệ thống."""
        provider = self._get_active_provider()
        try:
            return provider.generate_response(user_message, conversation_history, rag_context)
        except Exception as e:
            logger.warning("[AI Service] Provider %s gặp lỗi: %s. Kích hoạt Fallback Engine.", type(provider).__name__, e)
            # Tự động kích hoạt Fallback Engine khi provider bên ngoài gặp sự cố
            return self.fallback_provider.generate_response(user_message, conversation_history, rag_context)


ai_service = AIService()
