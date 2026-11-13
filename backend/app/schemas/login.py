"""Pydantic schemas cho đăng nhập & đăng ký RideHub."""
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, model_validator


# ── Request ───────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    """Schema đăng ký tài khoản khớp form giao diện UI."""
    full_name: str = Field(..., min_length=2, max_length=150, description="Họ và tên")
    email: EmailStr = Field(..., description="Địa chỉ email đăng nhập")
    phone: str = Field(..., min_length=9, max_length=15, description="Số điện thoại")
    password: str = Field(..., min_length=6, max_length=100, description="Mật khẩu")
    confirm_password: Optional[str] = Field(None, description="Nhập lại mật khẩu")
    firebase_token: Optional[str] = Field(None, description="ID Token nếu đã xác thực OTP Firebase trên client")

    @model_validator(mode="after")
    def check_passwords_match(self):
        if self.confirm_password is not None and self.password != self.confirm_password:
            raise ValueError("Mật khẩu nhập lại không trùng khớp.")
        return self


class UserLogin(BaseModel):
    """Đăng nhập bằng email + mật khẩu."""
    email: EmailStr
    password: str


# ── Response ──────────────────────────────────────────────────────────────────

class RegisterResponse(BaseModel):
    """Thông tin trả về sau khi đăng ký thành công."""
    user_id: int
    full_name: str
    email: str
    phone: Optional[str] = None
    firebase_uid: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
