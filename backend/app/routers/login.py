"""Router xác thực tài khoản: Đăng nhập & Đăng ký.

Chỉ giữ lại các API thực sự được sử dụng trên giao diện web RideHub.
"""
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.core.dependencies import (
    get_current_user,
    get_current_admin,
    get_current_store_owner,
    get_current_staff,
    require_roles,
)
from app.models.user import User
from app.schemas.login import (
    UserCreate,
    UserLogin,
    FirebaseLoginRequest,
    EmailOnlyRequest,
)
from app.services.login import register_user, login_user, login_with_firebase
from app.core.firebase import (
    send_firebase_verification_email,
    send_firebase_password_reset_email,
    generate_verification_link,
    init_firebase,
    fb_auth,
)
from app.utils.response import create_response

router = APIRouter(prefix="/auth", tags=["Authentication & Login"])


def _set_auth_cookies(
    response: JSONResponse,
    access_token: str,
    refresh_token: str,
    remember_me: bool = False,
):
    """Thiết lập Cookie cho JWT token trên trình duyệt (thời hạn tùy theo remember_me)."""
    access_max_age = 30 * 24 * 3600 if remember_me else 7 * 24 * 3600
    refresh_max_age = 90 * 24 * 3600 if remember_me else 30 * 24 * 3600

    response.set_cookie(
        key="ridehub_token",
        value=access_token,
        max_age=access_max_age,
        httponly=False,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=access_max_age,
        httponly=False,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        key="ridehub_refresh_token",
        value=refresh_token,
        max_age=refresh_max_age,
        httponly=False,
        samesite="lax",
        path="/",
    )


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
    2. Gửi email xác thực chính thức từ Firebase tới hòm thư người dùng.
    3. Lưu bản ghi người dùng vào MySQL (bảng `users`).
    4. Cấp ngay cặp JWT Access + Refresh token để người dùng đăng nhập ngay.
    """
    new_user, access_token, refresh_token = register_user(db, body)
    response = create_response(
        status_code=201,
        message="Đăng ký tài khoản thành công. Email xác thực đã được gửi tới hộp thư của bạn.",
        data={
            "user_id": new_user.id,
            "firebase_uid": new_user.firebase_uid,
            "full_name": new_user.full_name,
            "email": new_user.email,
            "phone": new_user.phone,
            "role": new_user.role,
            "verification_link": getattr(new_user, "verification_link", None),
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        },
    )
    _set_auth_cookies(
        response,
        access_token,
        refresh_token,
        remember_me=bool(getattr(body, "remember_me", False)),
    )
    return response


@router.post("/login", summary="Đăng nhập bằng Email & Mật khẩu")
async def login(body: UserLogin, db: Session = Depends(get_db)):
    """
    **Đăng nhập tài khoản trên giao diện web RideHub:**
    - `email`: Email tài khoản
    - `password`: Mật khẩu
    """
    user, access_token, refresh_token = login_user(db, body)
    response = create_response(
        status_code=200,
        message="Đăng nhập thành công.",
        data={
            "user_id": user.id,
            "firebase_uid": user.firebase_uid,
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "avatar_url": user.avatar_url,
            "role": user.role,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        },
    )
    _set_auth_cookies(
        response,
        access_token,
        refresh_token,
        remember_me=bool(getattr(body, "remember_me", False)),
    )
    return response


@router.post("/firebase-login", summary="Đăng nhập bằng Firebase ID Token (Google / Phone OTP)")
async def firebase_login(body: FirebaseLoginRequest, db: Session = Depends(get_db)):
    """
    **Đăng nhập tài khoản bằng Firebase ID Token từ Client:**
    - `id_token`: Token do Firebase cấp sau khi đăng nhập Google hoặc OTP
    """
    user, access_token, refresh_token = login_with_firebase(db, body.id_token)
    response = create_response(
        status_code=200,
        message="Đăng nhập qua Firebase thành công.",
        data={
            "user_id": user.id,
            "firebase_uid": user.firebase_uid,
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "avatar_url": user.avatar_url,
            "role": user.role,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        },
    )
    _set_auth_cookies(
        response,
        access_token,
        refresh_token,
        remember_me=bool(getattr(body, "remember_me", False)),
    )
    return response


@router.post("/logout", summary="Đăng xuất và xoá Cookie phiên đăng nhập")
async def logout_cookie():
    response = create_response(status_code=200, message="Đăng xuất thành công.")
    response.delete_cookie(key="ridehub_token", path="/")
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="ridehub_refresh_token", path="/")
    return response


@router.post("/resend-verification", summary="Gửi lại email xác thực tài khoản qua Firebase")
async def resend_verification(body: EmailOnlyRequest, db: Session = Depends(get_db)):
    """Gửi lại email xác thực chính thức từ Firebase Authentication."""
    user = db.query(User).filter(User.email == body.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản với email này.")

    if user.firebase_uid:
        sent = send_firebase_verification_email(user.firebase_uid, user.email)
        if sent:
            return create_response(
                status_code=200,
                message=f"Đã gửi email xác thực Firebase tới {user.email}. Vui lòng kiểm tra hộp thư!",
            )

    link = generate_verification_link(user.email)
    return create_response(
        status_code=200,
        message="Đã tạo liên kết xác thực.",
        data={"verification_link": link},
    )


@router.get("/check-verification", summary="Kiểm tra trạng thái xác thực email từ Firebase")
async def check_verification(email: str):
    """Kiểm tra xem người dùng đã nhấp vào link kích hoạt trong email của Firebase chưa."""
    init_firebase()
    try:
        fb_user = fb_auth.get_user_by_email(email.strip())
        return create_response(
            status_code=200,
            message="Kiểm tra trạng thái email thành công.",
            data={"verified": bool(fb_user.email_verified), "email": email.strip()},
        )
    except Exception as exc:
        return create_response(
            status_code=200,
            message="Chưa thể lấy thông tin Firebase.",
            data={"verified": False, "detail": str(exc), "email": email.strip()},
        )


@router.post("/forgot-password", summary="Gửi email đặt lại mật khẩu từ Firebase")
async def forgot_password_api(body: EmailOnlyRequest, db: Session = Depends(get_db)):
    """Gửi email đặt lại mật khẩu thật từ Firebase tới hòm thư người dùng."""
    user = db.query(User).filter(User.email == body.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Email này chưa đăng ký tài khoản trên RideHub.")

    sent = send_firebase_password_reset_email(body.email)
    if sent:
        return create_response(
            status_code=200,
            message=f"Đã gửi email đặt lại mật khẩu tới {body.email}. Vui lòng kiểm tra hộp thư!",
        )

    raise HTTPException(status_code=500, detail="Không thể gửi email đặt lại mật khẩu vào lúc này.")


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


@router.get("/config", summary="Lấy cấu hình công khai (Firebase Web API Key, v.v.)")
async def get_public_auth_config():
    """Trả về cấu hình công khai cho frontend (đọc an toàn từ file .env)."""
    return create_response(
        status_code=200,
        message="Lấy cấu hình hệ thống thành công.",
        data={
            "app_name": settings.APP_NAME,
            "firebase": {
                "apiKey": settings.FIREBASE_WEB_API_KEY,
                "projectId": settings.FIREBASE_PROJECT_ID,
                "authDomain": settings.FIREBASE_AUTH_DOMAIN,
                "storageBucket": settings.FIREBASE_STORAGE_BUCKET,
            },
        },
    )

