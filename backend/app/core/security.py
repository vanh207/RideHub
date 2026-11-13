"""Tiện ích bảo mật: băm mật khẩu và tạo / giải mã JWT.

Dùng bcrypt và PyJWT.
"""
from datetime import datetime, timezone, timedelta
import bcrypt
import jwt
from fastapi import HTTPException, status

from app.core.config import settings

# ── Constants (đọc từ settings / .env) ───────────────────────────────────────
SECRET_KEY: str = settings.JWT_SECRET_KEY
ALGORITHM: str = "HS256"
EXPIRE_MINUTES: int = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_EXPIRE_MINUTES: int = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60


# ── Mật khẩu ─────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Băm mật khẩu trước khi lưu vào database."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """So sánh mật khẩu người dùng nhập với mật khẩu đã băm."""
    return bcrypt.checkpw(password.encode(), hashed.encode())


# ── JWT ───────────────────────────────────────────────────────────────────────

def _create_token(data: dict, expires_minutes: int, token_type: str) -> str:
    """Tạo JWT với payload, loại token và thời gian hết hạn."""
    payload = {
        **data,
        "type": token_type,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(data: dict) -> str:
    return _create_token(data, EXPIRE_MINUTES, "access")


def create_refresh_token(data: dict) -> str:
    return _create_token(data, REFRESH_EXPIRE_MINUTES, "refresh")


def decode_token(token: str, expected_type: str) -> dict | None:
    """Giải mã JWT và kiểm tra loại token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != expected_type:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token không hợp lệ",
            )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token đã hết hạn",
        )
    except jwt.PyJWTError:
        return None


def decode_access_token(token: str) -> dict | None:
    return decode_token(token, "access")


def decode_refresh_token(token: str) -> dict | None:
    return decode_token(token, "refresh")
