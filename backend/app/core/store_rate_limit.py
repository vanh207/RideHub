from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from fastapi import Depends, Request

from app.core.dependencies import get_current_user
from app.core.store_errors import StoreAPIError
from app.models.user import User


class StoreRegistrationRateLimiter:
    """Per-user in-process limit; replace the backend with Redis for multi-worker deployments."""

    def __init__(self, max_requests: int = 5, window_seconds: int = 3600):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._attempts: dict[int, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, user_id: int) -> None:
        now = monotonic()
        with self._lock:
            attempts = self._attempts[user_id]
            while attempts and now - attempts[0] >= self.window_seconds:
                attempts.popleft()
            if len(attempts) >= self.max_requests:
                raise StoreAPIError(
                    status_code=429,
                    message="Bạn đã gửi quá nhiều yêu cầu đăng ký cửa hàng. Vui lòng thử lại sau.",
                )
            attempts.append(now)

    def reset(self) -> None:
        with self._lock:
            self._attempts.clear()


store_registration_rate_limiter = StoreRegistrationRateLimiter()


def limit_store_registration(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> None:
    store_registration_rate_limiter.check(current_user.id)
