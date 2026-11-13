"""Router xác thực tài khoản: Đăng nhập & Đăng ký.

Chỉ giữ lại các API thực sự được sử dụng trên giao diện web RideHub.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.login import UserCreate, UserLogin
from app.services.login import register_user, login_user
from app.utils.response import create_response

router = APIRouter(prefix="/auth", tags=["Authentication & Login"])


@router.post("/register", status_code=201, summary="Đăng ký tài khoản (kết hợp Firebase)")
async def register(body: UserCreate, db: Session = Depends(get_db)):
    """
    **Đăng ký tài khoản mới theo đúng form giao diện web RideHub:**
    - `full_name`: Họ và tên
    - `email`: Địa chỉ email
    - `phone`: Số điện thoại
    - `password`: Mật khẩu
    - `confirm_password`: Xác nhận mật khẩu

    Hệ thống sẽ:
    1. Xác thực thông tin và tạo tài khoản trên Firebase Auth.
    2. Lưu bản ghi người dùng vào MySQL (bảng `users`).
    3. Cấp ngay cặp JWT Access + Refresh token để người dùng đăng nhập ngay.
    """
    new_user, access_token, refresh_token = register_user(db, body)
    return create_response(
        status_code=201,
        message="Đăng ký tài khoản thành công.",
        data={
            "user_id": new_user.id,
            "firebase_uid": new_user.firebase_uid,
            "full_name": new_user.full_name,
            "email": new_user.email,
            "phone": new_user.phone,
            "role": new_user.role,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        },
    )


@router.post("/login", summary="Đăng nhập bằng Email & Mật khẩu")
async def login(body: UserLogin, db: Session = Depends(get_db)):
    """
    **Đăng nhập tài khoản trên giao diện web RideHub:**
    - `email`: Email tài khoản
    - `password`: Mật khẩu
    """
    user, access_token, refresh_token = login_user(db, body)
    return create_response(
        status_code=200,
        message="Đăng nhập thành công.",
        data={
            "user_id": user.id,
            "firebase_uid": user.firebase_uid,
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "role": user.role,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        },
    )
