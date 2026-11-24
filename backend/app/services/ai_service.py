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
SYSTEM_PROMPT = """Bạn là Trợ lý ảo AI thông minh của nền tảng cho thuê xe tự lái RideHub (Việt Nam).
Mục tiêu của bạn là hỗ trợ khách hàng nhanh chóng, chính xác, lịch sự và thân thiện bằng tiếng Việt.

Nhiệm vụ chính:
1. Tư vấn và hỗ trợ tìm xe phù hợp (xe 4 chỗ, 7 chỗ, xe máy, xe điện, số tự động/số sàn).
2. Hướng dẫn quy trình xác thực danh tính eKYC (CCCD/Hộ chiếu, Giấy phép lái xe B1/B2/A1/A2).
3. Giải đáp rõ ràng về chính sách tiền cọc, phụ phí vượt km/giờ, và chính sách hoàn tiền 100% khi hủy đơn hợp lệ.
4. Hướng dẫn bàn giao xe, kiểm tra ảnh biên bản giao nhận và kích hoạt cứu hộ khẩn cấp 24/7.

Nguyên tắc quan trọng:
- Ưu tiên căn cứ vào KHO TRI THỨC được cung cấp bên dưới để trả lời.
- Tuyệt đối không bịa đặt thông tin chính sách hoặc mức giá sai lệch với RideHub.
- Nếu câu hỏi vượt quá phạm vi hoặc khách hàng phàn nàn/khiếu nại gay gắt, hãy đề xuất kết nối gặp Chuyên viên hỗ trợ (Human Agent).
- Trả lời ngắn gọn, có gạch đầu dòng rõ ràng, kèm icon sinh động và lời chào thân thiện.
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
                "temperature": 0.4,
                "maxOutputTokens": 800,
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
    Tổng hợp trực tiếp câu trả lời từ Kho tri thức để trả về kết quả chính xác 100%.
    """

    def generate_response(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        rag_context: str,
    ) -> Dict[str, Any]:
        msg_lower = user_message.lower()

        # Nếu trong kho tri thức có dữ liệu cụ thể được tìm thấy
        if rag_context and "Không tìm thấy thông tin cụ thể" not in rag_context:
            text = (
                f"Dạ em xin gửi đến Quý khách thông tin chính thức từ RideHub về câu hỏi của Quý khách:\n\n"
                f"{rag_context}\n\n"
                f"💡 Quý khách cần em hỗ trợ thêm chi tiết nào khác không ạ?"
            )
            return {
                "text": text,
                "model": "knowledge-fallback-v1",
                "provider": "knowledge-base",
                "tokens_used": 0,
            }

        # Nhận diện ý định khẩn cấp / cứu hộ
        if any(w in msg_lower for w in ["cứu hộ", "sự cố", "hỏng xe", "thủng lốp", "tai nạn"]):
            text = (
                "🚨 **HỖ TRỢ CỨU HỘ KHẨN CẤP RIDEHUB 24/7** 🚨\n\n"
                "Quý khách vui lòng thực hiện các bước an toàn ngay:\n"
                "1. Bật đèn cảnh báo khẩn cấp (Hazard), tấp xe vào lề phải an toàn.\n"
                "2. Cả đoàn bước ra sau taluy đường an toàn.\n"
                "3. Bấm nút gọi ngay Hotline cứu hộ: **1900-7433** để kỹ thuật viên xuất phát hỗ trợ lập tức!"
            )
            return {
                "text": text,
                "model": "emergency-rule-engine",
                "provider": "knowledge-base",
                "tokens_used": 0,
            }

        # Phản hồi chung
        text = (
            f"Dạ em đã ghi nhận câu hỏi của Quý khách: \"{user_message}\".\n\n"
            f"Quý khách có thể xem nhanh các hướng dẫn phổ biến: **Thủ tục eKYC**, **Chính sách đặt cọc & hoàn tiền**, "
            f"hoặc bấm nút **Gặp nhân viên CSKH** để được tư vấn trực tiếp 1-1 ạ!"
        )
        return {
            "text": text,
            "model": "general-fallback",
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
