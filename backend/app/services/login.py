"""Service nghiệp vụ xác thực: đăng ký kết hợp Firebase & đăng nhập."""
from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.login import UserCreate, UserLogin
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
)
from app.core.firebase import create_firebase_user, verify_firebase_id_token


# ── Đăng ký ──────────────────────────────────────────────────────────────────

def register_user(db: Session, body: UserCreate):
    """Tạo tài khoản mới kết hợp Firebase Authentication.

    Quy trình:
      1. Kiểm tra trùng lặp email và số điện thoại trong MySQL.
      2. Tạo user trên Firebase Auth (lấy firebase_uid) hoặc verify Firebase ID token nếu có.
      3. Băm mật khẩu bằng bcrypt và lưu thông tin vào MySQL.
      4. Cấp access_token + refresh_token để đăng nhập tức thì.
    """
    # 1. Kiểm tra email
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email đã được sử dụng.",
        )

    # 2. Kiểm tra số điện thoại
    if body.phone and db.query(User).filter(User.phone == body.phone).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Số điện thoại này đã được sử dụng.",
        )

    # 3. Tạo / xác thực tài khoản qua Firebase
    firebase_uid = None
    if body.firebase_token:
        decoded_token = verify_firebase_id_token(body.firebase_token)
        firebase_uid = decoded_token.get("uid")
    else:
        firebase_uid = create_firebase_user(
            email=body.email,
            password=body.password,
            display_name=body.full_name,
            phone=body.phone,
        )

    # 4. Lưu vào Database nội bộ
    new_user = User(
        firebase_uid=firebase_uid,
        email=body.email,
        phone=body.phone,
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
        role="customer",
        status="active",
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # 5. Cấp cặp JWT Access + Refresh token
    token_data = {"sub": str(new_user.id), "email": new_user.email, "role": new_user.role}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    return new_user, access_token, refresh_token


# ── Đăng nhập bằng Email & Mật khẩu ──────────────────────────────────────────

def login_user(db: Session, body: UserLogin):
    """Xác thực email + mật khẩu, trả về (user, access_token, refresh_token)."""
    user = db.query(User).filter(User.email == body.email).first()

    password_valid = False
    if user and user.hashed_password:
        try:
            password_valid = verify_password(body.password, user.hashed_password)
        except (ValueError, TypeError):
            password_valid = False

    if not user or not password_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không đúng.",
        )

    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản đã bị vô hiệu hóa.",
        )

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    token_data = {"sub": str(user.id), "email": user.email, "role": user.role}
    return user, create_access_token(token_data), create_refresh_token(token_data)
