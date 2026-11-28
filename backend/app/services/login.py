"""Service nghiệp vụ xác thực: đăng ký kết hợp Firebase & đăng nhập."""
from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.user import User
from app.models.role import Role, UserRole
from app.schemas.login import UserCreate, UserLogin
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
)
from app.core.firebase import (
    create_firebase_user,
    verify_firebase_id_token,
    generate_verification_link,
    send_firebase_verification_email,
    fb_auth,
)


def assign_user_role(db: Session, user_id: int, role_code: str = "customer"):
    """Gán vai trò cho người dùng thông qua bảng roles và user_roles chuẩn hóa."""
    role_code_clean = role_code.strip().lower()
    role_obj = db.query(Role).filter(func.lower(Role.code) == role_code_clean).first()
    if not role_obj:
        role_names = {
            "admin": "Quản trị viên",
            "store_owner": "Chủ cửa hàng",
            "store_staff": "Nhân viên cửa hàng",
            "operator": "Điều hành",
            "customer": "Khách thuê",
        }
        role_obj = Role(
            code=role_code_clean,
            name=role_names.get(role_code_clean, role_code_clean.title()),
            description=f"Vai trò {role_code_clean} trên hệ thống RideHub",
        )
        db.add(role_obj)
        db.commit()
        db.refresh(role_obj)

    existing_ur = db.query(UserRole).filter(
        UserRole.user_id == user_id,
        UserRole.role_id == role_obj.id,
    ).first()
    if not existing_ur:
        ur = UserRole(user_id=user_id, role_id=role_obj.id)
        db.add(ur)
        db.commit()


# ── Đăng ký ──────────────────────────────────────────────────────────────────

def register_user(db: Session, body: UserCreate):
    """Tạo tài khoản mới kết hợp Firebase Authentication.

    Quy trình:
      1. Kiểm tra trùng lặp email và số điện thoại trong MySQL.
      2. Tạo user trên Firebase Auth (lấy firebase_uid) hoặc verify Firebase ID token nếu có.
      3. Băm mật khẩu bằng bcrypt và lưu thông tin vào MySQL (không có cột role).
      4. Gán vai trò vào bảng user_roles.
      5. Cấp access_token + refresh_token để đăng nhập tức thì.
    """
    # 1. Kiểm tra email (nếu tài khoản đã bị xóa trên Firebase thì tự động dọn dẹp bản ghi cũ trong MySQL)
    existing_user = db.query(User).filter(User.email == body.email).first()
    if existing_user:
        exists_in_fb = False
        try:
            if existing_user.firebase_uid:
                fb_auth.get_user(existing_user.firebase_uid)
                exists_in_fb = True
        except Exception:
            exists_in_fb = False

        if not exists_in_fb:
            db.delete(existing_user)
            db.commit()
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email đã được sử dụng.",
            )

    # 2. Kiểm tra số điện thoại (tương tự)
    if body.phone:
        existing_phone = db.query(User).filter(User.phone == body.phone).first()
        if existing_phone:
            exists_in_fb = False
            try:
                if existing_phone.firebase_uid:
                    fb_auth.get_user(existing_phone.firebase_uid)
                    exists_in_fb = True
            except Exception:
                exists_in_fb = False

            if not exists_in_fb:
                db.delete(existing_phone)
                db.commit()
            else:
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

    # 4. Lưu vào Database nội bộ (chuẩn hóa không có cột role)
    new_user = User(
        firebase_uid=firebase_uid,
        email=body.email,
        phone=body.phone,
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
        status="active",
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # 5. Gán vai trò vào bảng user_roles
    assign_user_role(db, new_user.id, "customer")
    db.refresh(new_user)

    # 6. Cấp cặp JWT Access + Refresh token
    token_data = {"sub": str(new_user.id), "email": new_user.email, "role": new_user.role}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    # 6. Gửi email xác thực chính thức từ Firebase tới hòm thư người dùng
    sent = False
    if new_user.firebase_uid:
        sent = send_firebase_verification_email(new_user.firebase_uid, new_user.email)

    new_user.verification_link = None if sent else generate_verification_link(new_user.email)

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


# ── Đăng nhập bằng Firebase ID Token ──────────────────────────────────────────

def login_with_firebase(db: Session, id_token: str):
    """Xác thực Firebase ID Token (từ Google Login hoặc Phone OTP), cấp JWT nội bộ."""
    decoded_token = verify_firebase_id_token(id_token)
    firebase_uid = decoded_token.get("uid")
    email = decoded_token.get("email")
    phone = decoded_token.get("phone_number")
    name = decoded_token.get("name") or "Người dùng RideHub"
    picture = decoded_token.get("picture")

    if not firebase_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase Token không hợp lệ.",
        )

    # Tìm user theo firebase_uid hoặc email
    user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not user and email:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.firebase_uid = firebase_uid
            if picture and not user.avatar_url:
                user.avatar_url = picture

    # Nếu chưa có user -> tự động đăng ký mới (Auto-provisioning)
    if not user:
        user = User(
            firebase_uid=firebase_uid,
            email=email,
            phone=phone,
            full_name=name,
            avatar_url=picture,
            status="active",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        assign_user_role(db, user.id, "customer")

    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản đã bị vô hiệu hóa.",
        )

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    token_data = {"sub": str(user.id), "email": user.email, "role": user.role}
    return user, create_access_token(token_data), create_refresh_token(token_data)
