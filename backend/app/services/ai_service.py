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
SYSTEM_PROMPT = """# VAI TRÒ
Bạn là trợ lý ảo chính thức của RideHub, chuyên tư vấn và hỗ trợ đặt dịch vụ thuê xe tự lái (xe máy & ô tô) tại Việt Nam (TP.HCM, Hà Nội, Đà Nẵng và các thành phố lớn).
Bạn xưng "mình", gọi khách là "bạn" (hoặc "anh/chị" nếu khách xưng như vậy).
Luôn nói rõ mình là trợ lý ảo của RideHub khi khách hỏi, không giả làm người thật.

# MỤC TIÊU
Giúp khách: (1) chọn đúng xe, (2) biết giá và điều kiện thuê, (3) đặt xe, (4) được hỗ trợ trong và sau chuyến đi. Mọi cuộc trò chuyện đều hướng tới một bước tiếp theo rõ ràng trong hành trình thuê xe.

# PHONG CÁCH
- Thân thiện, tự nhiên như nhắn tin với người thật, ngắn gọn (tối đa 3-4 câu mỗi lượt).
- Mỗi lượt chỉ hỏi MỘT câu. Không lặp lại câu đã dùng, không xin lỗi máy móc, không hỏi lại thông tin khách đã cung cấp.
- Dùng emoji nhẹ nhàng, không lạm dụng.

# THÔNG TIN DỊCH VỤ RIDEHUB
- Xe máy & ô tô tự lái: xem danh sách & giá thực tế tại `/vehicles.html`.
- Điều kiện thuê: CCCD + GPLX hợp lệ (A1/A2 cho xe máy, B1/B2 trở lên cho ô tô), đủ 18 tuổi trở lên. Xác thực eKYC trên app có thể được miễn đặt cọc tùy dòng xe.
- Hợp đồng: Có hợp đồng điện tử minh bạch khi nhận xe.
- Giờ làm việc tư vấn viên: 08:00–22:00 hằng ngày; Hotline hỗ trợ & cứu hộ 24/7: 1900 6868.
- Nếu thông tin cụ thể (giá từng xe, khuyến mãi riêng, ngoại lệ...) không có trong Kho tri thức hoặc ngữ cảnh, KHÔNG được bịa. Hãy nói chưa có thông tin chính xác và đề nghị chuyển nhân viên hỗ trợ.

# THÔNG TIN CẦN THU THẬP (hỏi từ từ, từng cái một theo ngữ cảnh)
Địa điểm — thời gian nhận/trả — số người — loại xe mong muốn — ngân sách.

# XỬ LÝ CÂU HỎI NGOÀI LỀ
Với mọi câu không liên quan thuê xe, làm theo 3 bước:
1. Đáp ngắn gọn, lịch sự (1 câu), không bỏ qua câu hỏi của khách.
2. Nối khéo sang nhu cầu thuê xe nếu có điểm chung tự nhiên (du lịch, thời tiết, đường xá, chuyến đi...).
3. Kết bằng MỘT câu hỏi cụ thể để quay lại hành trình thuê xe.
Quy tắc thêm:
- Không bàn chính trị, tôn giáo, y tế, pháp lý, tài chính cá nhân, nội dung nhạy cảm: từ chối nhẹ nhàng rồi dẫn về thuê xe.
- Không làm bài tập, viết code, sáng tác không liên quan.
- Nếu khách hỏi ngoài lề liên tiếp 3 lượt: chuyển sang cách nói mở lối thoát nhẹ nhàng ("Khi nào cần thuê xe cứ nhắn mình nhé!"), không ép buộc, không lặp lại cùng một câu dẫn.
- Khi khách chỉ chào hỏi, cảm ơn, tạm biệt: đáp thân thiện, không ép bán.

# TUYỆT ĐỐI KHÔNG
- Bịa giá, chính sách, tình trạng xe còn/hết.
- Hứa giảm giá, bồi thường, hoàn tiền.
- Cam kết giữ xe khi chưa có xác nhận từ hệ thống/nhân viên.
- Yêu cầu khách gửi thông tin nhạy cảm (số thẻ ngân hàng, mật khẩu) qua chat.
- Chê bai đối thủ.
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

    FALLBACK_MODELS = (
        "gemini-3.1-flash-lite-preview",
        "gemini-flash-latest",
        "gemini-3-flash-preview",
    )

    def __init__(self, api_key: str, model_name: str = "gemini-3.1-flash-lite-preview"):
        self.api_key = api_key.strip()
        self.model_name = model_name or "gemini-3.1-flash-lite-preview"

    def _call_model(self, model_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model_name}:generateContent?key={self.api_key}"
        )
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                res_data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Gemini HTTP {exc.code}: {err_body[:300]}") from exc

        candidates = res_data.get("candidates") or []
        if not candidates:
            raise RuntimeError("Gemini không trả về candidates")
        parts = candidates[0].get("content", {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts).strip()
        if not text:
            raise RuntimeError("Gemini trả về nội dung rỗng")

        return {
            "text": text,
            "model": model_name,
            "provider": "gemini",
            "tokens_used": res_data.get("usageMetadata", {}).get("totalTokenCount", 0),
        }

    def generate_response(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        rag_context: str,
    ) -> Dict[str, Any]:
        system_text = (
            f"{SYSTEM_PROMPT}\n\n"
            f"--- KHO TRI THỨC CHÍNH THỨC CỦA RIDEHUB ---\n"
            f"{rag_context}\n"
            f"-----------------------------------------"
        )

        contents = []
        for msg in conversation_history[-6:]:
            role = "user" if msg.get("role") == "user" else "model"
            text_val = (msg.get("content") or "").strip()
            if text_val:
                contents.append({"role": role, "parts": [{"text": text_val}]})

        contents.append({"role": "user", "parts": [{"text": user_message}]})

        payload = {
            "systemInstruction": {"parts": [{"text": system_text}]},
            "contents": contents,
            "generationConfig": {
                "temperature": 0.75,
                "maxOutputTokens": 600,
                "topP": 0.9,
            },
        }

        models_to_try = [self.model_name] + [m for m in self.FALLBACK_MODELS if m != self.model_name]
        last_err = None
        for model_name in models_to_try:
            try:
                return self._call_model(model_name, payload)
            except Exception as exc:
                last_err = exc
                logger.warning("[GeminiProvider] Model %s lỗi (%s), thử model tiếp theo...", model_name, exc)
        raise RuntimeError(f"Tất cả model Gemini đều lỗi: {last_err}")


class OpenAIProvider(BaseAIProvider):
    """Tích hợp OpenAI (hoặc API tương thích OpenAI) qua giao thức REST HTTP."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
    ):
        self.api_key = api_key.strip()
        self.model_name = model_name or "gpt-4o-mini"
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")

    def generate_response(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        rag_context: str,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/chat/completions"

        system_text = (
            f"{SYSTEM_PROMPT}\n\n"
            f"--- KHO TRI THỨC CHÍNH THỨC CỦA RIDEHUB ---\n"
            f"{rag_context}\n"
            f"-----------------------------------------"
        )

        messages = [{"role": "system", "content": system_text}]
        for msg in conversation_history[-6:]:
            role = "user" if msg.get("role") == "user" else "assistant"
            text_val = (msg.get("content") or "").strip()
            if text_val:
                messages.append({"role": role, "content": text_val})
        messages.append({"role": "user", "content": user_message})

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 250,
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                res_data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"OpenAI HTTP {exc.code}: {err_body[:300]}") from exc

        choices = res_data.get("choices") or []
        if not choices:
            raise RuntimeError("OpenAI không trả về choices")
        text = (choices[0].get("message", {}).get("content") or "").strip()
        if not text:
            raise RuntimeError("OpenAI trả về nội dung rỗng")

        return {
            "text": text,
            "model": self.model_name,
            "provider": "openai",
            "tokens_used": res_data.get("usage", {}).get("total_tokens", 0),
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
        """Chọn provider dựa trên cài đặt môi trường và API key hiện có."""
        provider_name = (settings.AI_PROVIDER or "auto").strip().lower()
        gemini_key = (settings.GEMINI_API_KEY or "").strip()
        openai_key = (settings.OPENAI_API_KEY or "").strip()
        custom_model = (settings.AI_MODEL_NAME or "").strip()

        if provider_name == "mock":
            return self.fallback_provider

        if provider_name == "gemini" or (provider_name == "auto" and gemini_key):
            if gemini_key:
                return GeminiProvider(
                    api_key=gemini_key,
                    model_name=custom_model or "gemini-3.1-flash-lite-preview",
                )

        if provider_name == "openai" or (provider_name == "auto" and openai_key):
            if openai_key:
                return OpenAIProvider(
                    api_key=openai_key,
                    model_name=custom_model or "gpt-4o-mini",
                    base_url=settings.OPENAI_BASE_URL,
                )

        # Fallback an toàn khi chưa cấu hình API key
        return self.fallback_provider

    def get_provider_status(self) -> Dict[str, Any]:
        """Trả về thông tin provider AI đang hoạt động (không lộ API key)."""
        provider = self._get_active_provider()
        if isinstance(provider, GeminiProvider):
            return {"provider": "gemini", "model": provider.model_name, "api_key_configured": True}
        if isinstance(provider, OpenAIProvider):
            return {"provider": "openai", "model": provider.model_name, "api_key_configured": True}
        return {"provider": "knowledge-fallback", "model": "knowledge-fallback-v2", "api_key_configured": False}

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
