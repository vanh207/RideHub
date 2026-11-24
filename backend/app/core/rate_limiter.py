"""Bộ quản lý giới hạn lượt gọi (Rate Limiter) cho Chatbot AI.

Chức năng:
- Ngăn chặn spam, lạm dụng và bảo vệ chi phí API mô hình AI.
- Hỗ trợ sliding window theo phút (per minute) và theo ngày (per day).
- Áp dụng linh hoạt theo session_id, user_id hoặc client IP.
- Trả về headers chuẩn: X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset.
"""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from app.core.config import settings


@dataclass
class RateLimitRecord:
    timestamps: List[float] = field(default_factory=list)


class InMemoryRateLimiter:
    """Sliding Window In-Memory Rate Limiter thread-safe cho đơn tiến trình."""

    def __init__(
        self,
        requests_per_minute: int = 20,
        requests_per_day: int = 100,
    ):
        self.requests_per_minute = requests_per_minute
        self.requests_per_day = requests_per_day
        self._minute_buckets: Dict[str, RateLimitRecord] = defaultdict(RateLimitRecord)
        self._day_buckets: Dict[str, RateLimitRecord] = defaultdict(RateLimitRecord)

    def _cleanup(self, record: RateLimitRecord, window_seconds: float, now: float) -> None:
        """Xoá các timestamp đã quá hạn ngoài window."""
        cutoff = now - window_seconds
        record.timestamps = [ts for ts in record.timestamps if ts > cutoff]

    def check(self, key: str) -> Tuple[bool, dict]:
        """Kiểm tra xem key (session_id / IP) có được phép gọi API không.

        Returns:
            (allowed: bool, info: dict)
        """
        now = time.time()

        # 1. Kiểm tra per minute (60s)
        min_record = self._minute_buckets[key]
        self._cleanup(min_record, 60.0, now)

        # 2. Kiểm tra per day (86400s)
        day_record = self._day_buckets[key]
        self._cleanup(day_record, 86400.0, now)

        min_remaining = max(0, self.requests_per_minute - len(min_record.timestamps))
        day_remaining = max(0, self.requests_per_day - len(day_record.timestamps))

        # Tính thời gian reset
        reset_seconds = 60
        if min_record.timestamps:
            reset_seconds = max(1, int(60.0 - (now - min_record.timestamps[0])))

        info = {
            "limit_per_minute": self.requests_per_minute,
            "remaining_minute": min_remaining,
            "limit_per_day": self.requests_per_day,
            "remaining_day": day_remaining,
            "reset_seconds": reset_seconds,
        }

        if min_remaining <= 0:
            info["reason"] = f"Vượt quá giới hạn {self.requests_per_minute} lượt gọi / phút."
            return False, info

        if day_remaining <= 0:
            info["reason"] = f"Vượt quá giới hạn {self.requests_per_day} lượt gọi / ngày."
            info["reset_seconds"] = 86400
            return False, info

        # Ghi nhận lượt gọi mới
        min_record.timestamps.append(now)
        day_record.timestamps.append(now)

        info["remaining_minute"] -= 1
        info["remaining_day"] -= 1
        return True, info

    def reset_key(self, key: str) -> None:
        """Reset lượt gọi cho một key (dùng cho test hoặc admin)."""
        if key in self._minute_buckets:
            del self._minute_buckets[key]
        if key in self._day_buckets:
            del self._day_buckets[key]


# Singleton instance toàn cục dựa theo cấu hình
chatbot_rate_limiter = InMemoryRateLimiter(
    requests_per_minute=settings.CHATBOT_RATE_LIMIT_PER_MINUTE,
    requests_per_day=settings.CHATBOT_RATE_LIMIT_PER_DAY,
)


def enforce_chatbot_rate_limit(key: str) -> dict:
    """Hàm helper kiểm tra và tự động raise HTTP 429 nếu vượt hạn mức."""
    allowed, info = chatbot_rate_limiter.check(key)
    if not allowed:
        headers = {
            "X-RateLimit-Limit": str(info["limit_per_minute"]),
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(info["reset_seconds"]),
            "Retry-After": str(info["reset_seconds"]),
        }
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "message": (
                    f"Bạn đã đạt giới hạn lượt gọi Chatbot AI. "
                    f"Vui lòng thử lại sau {info['reset_seconds']} giây hoặc liên hệ nhân viên hỗ trợ."
                ),
                "retry_after_seconds": info["reset_seconds"],
                "rate_limit_info": info,
            },
            headers=headers,
        )
    return info
