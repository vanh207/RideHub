"""Giới hạn tần suất (Rate Limiting) cho các endpoint xác thực (Login / Register / Forgot Password).

Chống tấn công Brute-force và Credential Stuffing:
- Mặc định tối đa 5 lần / 60 giây trên mỗi IP nguồn (cấu hình qua settings).
- Trả về HTTP 429 Too Many Requests kèm header Retry-After.
"""
from collections import defaultdict, deque
from math import ceil
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request, status

from app.core.config import settings


def _extract_client_ip(request: Request) -> str:
    """Lấy IP thực của client, hỗ trợ Reverse Proxy (X-Forwarded-For)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


class AuthRateLimiter:
    """Sliding-window rate limiter theo khóa (IP / scope) an toàn đa luồng."""

    def __init__(
        self,
        max_attempts: int | None = None,
        window_seconds: int | None = None,
    ):
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds
        self._attempts: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    @property
    def max_attempts(self) -> int:
        return (
            self._max_attempts
            if self._max_attempts is not None
            else settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS
        )

    @property
    def window_seconds(self) -> int:
        return (
            self._window_seconds
            if self._window_seconds is not None
            else settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS
        )

    def check(self, key: str) -> None:
        now = monotonic()
        limit = self.max_attempts
        window = self.window_seconds

        with self._lock:
            attempts = self._attempts[key]
            while attempts and now - attempts[0] >= window:
                attempts.popleft()

            if len(attempts) >= limit:
                retry_after = max(1, ceil(window - (now - attempts[0])))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        f"Bạn đã thử đăng nhập quá nhiều lần ({limit} lần/{window}s). "
                        f"Vui lòng thử lại sau {retry_after} giây."
                    ),
                    headers={"Retry-After": str(retry_after)},
                )
            attempts.append(now)

    def reset(self) -> None:
        """Xóa bộ đếm (dùng cho unit test)."""
        with self._lock:
            self._attempts.clear()


auth_rate_limiter = AuthRateLimiter()


def limit_login_attempts(request: Request) -> None:
    """Dependency FastAPI giới hạn tần suất gọi API đăng nhập theo IP."""
    client_ip = _extract_client_ip(request)
    auth_rate_limiter.check(f"login:{client_ip}")


def limit_auth_sensitive_attempts(request: Request) -> None:
    """Dependency FastAPI giới hạn tần suất cho đăng ký & quên mật khẩu theo IP."""
    client_ip = _extract_client_ip(request)
    auth_rate_limiter.check(f"auth_sensitive:{client_ip}")
