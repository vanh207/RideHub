"""Router xác thực tài khoản: Đăng nhập & Đăng ký.

Chỉ giữ lại các API thực sự được sử dụng trên giao diện web RideHub.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import (
    get_current_user,
    get_current_admin,
    get_current_store_owner,
    get_current_staff,
    require_roles,
)
from app.models.user import User
from app.schemas.login import UserCreate, UserLogin, FirebaseLoginRequest
from app.services.login import register_user, login_user, login_with_firebase
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


@router.post("/firebase-login", summary="Đăng nhập bằng Firebase ID Token (Google / Phone OTP)")
async def firebase_login(body: FirebaseLoginRequest, db: Session = Depends(get_db)):
    """
    **Đăng nhập tài khoản bằng Firebase ID Token từ Client:**
    - `id_token`: Token do Firebase cấp sau khi đăng nhập Google hoặc OTP
    """
    user, access_token, refresh_token = login_with_firebase(db, body.id_token)
    return create_response(
        status_code=200,
        message="Đăng nhập qua Firebase thành công.",
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


@router.get("/me", summary="Lấy thông tin người dùng hiện tại (yêu cầu đăng nhập)")
async def get_me(current_user: User = Depends(get_current_user)):
    """API yêu cầu Access Token hợp lệ."""
    return create_response(
        status_code=200,
        message="Lấy thông tin thành công.",
        data={
            "user_id": current_user.id,
            "full_name": current_user.full_name,
            "email": current_user.email,
            "role": current_user.role,
            "status": current_user.status,
        },
    )


@router.get("/admin-dashboard", summary="Báo cáo quản trị hệ thống (Chỉ Admin)")
async def admin_dashboard(admin: User = Depends(get_current_admin)):
    """API độc quyền chỉ dành riêng cho role admin."""
    return create_response(
        status_code=200,
        message="Truy cập Dashboard Quản trị viên thành công.",
        data={"access_granted": True, "admin_id": admin.id, "role": admin.role},
    )


@router.get("/store-management", summary="Khu vực quản trị cửa hàng (Store Owner hoặc Admin)")
async def store_management(owner: User = Depends(get_current_store_owner)):
    """API dành cho Store Owner quản lý cửa hàng và danh sách xe."""
    return create_response(
        status_code=200,
        message="Truy cập Khu vực Quản lý Cửa hàng thành công.",
        data={"access_granted": True, "owner_id": owner.id, "role": owner.role},
    )


@router.get("/staff-handover", summary="Khu vực nhân viên giao nhận xe (Store Staff, Owner hoặc Admin)")
async def staff_handover(staff: User = Depends(get_current_staff)):
    """API dành cho Store Staff thực hiện biên bản giao nhận xe."""
    return create_response(
        status_code=200,
        message="Truy cập Khu vực Bàn giao xe thành công.",
        data={"access_granted": True, "staff_id": staff.id, "role": staff.role},
    )


@router.get("/customer-orders", summary="Khu vực đơn đặt xe cá nhân (Customer hoặc Admin)")
async def customer_orders(user: User = Depends(require_roles("customer", "admin"))):
    """API dành cho Customer xem các đơn thuê của mình."""
    return create_response(
        status_code=200,
        message="Truy cập Danh sách đơn thuê khách hàng thành công.",
        data={"access_granted": True, "user_id": user.id, "role": user.role},
    )
