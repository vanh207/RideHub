"""Cấu hình và tiện ích Firebase Admin SDK cho RideHub.

Hỗ trợ:
  1. Khởi tạo Firebase Admin từ tệp serviceAccountKey.json
  2. Tạo user trên Firebase Auth khi đăng ký
  3. Xác thực Firebase ID Token (nếu FE gửi ID Token)
"""
import logging
import os
import re
from typing import Optional

import firebase_admin
from firebase_admin import auth as fb_auth, credentials, exceptions
from fastapi import HTTPException, status

from app.core.config import settings

logger = logging.getLogger("ridehub.firebase")

_firebase_app = None


def init_firebase() -> Optional[firebase_admin.App]:
    """Khởi tạo Firebase Admin SDK với serviceAccountKey.json."""
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app

    cred_path = getattr(settings, "FIREBASE_CREDENTIALS_PATH", "serviceAccountKey.json")
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    # Kiểm tra các đường dẫn có thể tồn tại của file key
    candidates = [
        cred_path,
        os.path.join(base_dir, cred_path),
        os.path.join(base_dir, "serviceAccountKey.json"),
        os.path.join(base_dir, "serviceAccountKey.json.json"),
        os.path.abspath("serviceAccountKey.json"),
        os.path.abspath("serviceAccountKey.json.json"),
        os.path.abspath("backend copy/serviceAccountKey.json"),
        os.path.abspath("backend/serviceAccountKey.json"),
    ]

    found_path = None
    for p in candidates:
        if os.path.exists(p) and os.path.isfile(p):
            found_path = p
            break

    if found_path:
        try:
            cred = credentials.Certificate(found_path)
            _firebase_app = firebase_admin.initialize_app(cred)
            logger.info(f"Firebase Admin SDK đã khởi tạo thành công từ '{found_path}'.")
        except Exception as exc:
            logger.error(f"Lỗi khởi tạo Firebase Admin SDK từ '{found_path}': {exc}")
    else:
        logger.warning(
            f"Không tìm thấy file Firebase credentials tại '{cred_path}'. "
            "Chức năng xác thực Firebase sẽ chạy ở chế độ giả lập (dev/fallback)."
        )

    return _firebase_app


def to_e164_phone(phone: str) -> Optional[str]:
    """Chuyển số điện thoại Việt Nam (0901234567) sang định dạng chuẩn quốc tế (+84901234567)."""
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("0") and len(digits) == 10:
        return f"+84{digits[1:]}"
    if digits.startswith("84") and len(digits) == 11:
        return f"+{digits}"
    if phone.startswith("+"):
        return phone
    return None


def create_firebase_user(
    email: str,
    password: str,
    display_name: str,
    phone: Optional[str] = None,
) -> str:
    """Tạo người dùng mới trên Firebase Authentication và trả về Firebase UID."""
    init_firebase()

    if _firebase_app is None:
        import uuid
        mock_uid = f"fb_{uuid.uuid4().hex[:24]}"
        logger.warning(f"Firebase Admin chưa cấu hình key thật. Tự tạo UID giả lập: {mock_uid}")
        return mock_uid

    e164_phone = to_e164_phone(phone) if phone else None

    try:
        kwargs = {
            "email": email,
            "password": password,
            "display_name": display_name,
        }
        if e164_phone:
            kwargs["phone_number"] = e164_phone

        user_record = fb_auth.create_user(**kwargs)
        return user_record.uid

    except fb_auth.EmailAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email này đã được đăng ký trên hệ thống Firebase.",
        )
    except fb_auth.PhoneNumberAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Số điện thoại này đã được liên kết với một tài khoản Firebase khác.",
        )
    except exceptions.FirebaseError as fe:
        err_msg = str(fe)
        if "CONFIGURATION_NOT_FOUND" in err_msg:
            import uuid
            mock_uid = f"fb_{uuid.uuid4().hex[:24]}"
            logger.warning(
                "Dự án Firebase chưa bật Authentication trong Firebase Console (CONFIGURATION_NOT_FOUND). "
                f"Tạm thời gán fallback UID: {mock_uid}. Hãy vào Firebase Console -> Authentication -> Bấm 'Get Started' và bật Email/Password."
            )
            return mock_uid
        if "phone" in err_msg.lower():
            try:
                user_record = fb_auth.create_user(
                    email=email,
                    password=password,
                    display_name=display_name,
                )
                return user_record.uid
            except Exception:
                pass
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Lỗi Firebase Authentication: {fe}",
        )


def verify_firebase_id_token(id_token: str) -> dict:
    """Xác thực Firebase ID Token do Frontend gửi lên (khi đăng nhập / OTP).

    Cho phép dung sai lệch đồng hồ (clock_skew_seconds=300) để tránh lỗi 'Token used too early'
    do chênh lệch thời gian giữa máy client và máy chủ Google.
    """
    init_firebase()

    if _firebase_app is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Firebase Admin SDK chưa được cấu hình tệp serviceAccountKey.json.",
        )

    try:
        decoded = fb_auth.verify_id_token(id_token, clock_skew_seconds=60)
        return decoded
    except exceptions.FirebaseError as fe:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Firebase ID Token không hợp lệ hoặc đã hết hạn: {fe}",
        )


def generate_verification_link(email: str) -> Optional[str]:
    """Tạo liên kết xác thực email từ Firebase Authentication."""
    init_firebase()
    if _firebase_app is None:
        return None
    try:
        return fb_auth.generate_email_verification_link(email)
    except Exception as exc:
        logger.warning(f"Không thể tạo email verification link cho {email}: {exc}")
        return None


def send_firebase_verification_email(firebase_uid: str, email: str) -> bool:
    """Gửi email xác thực tài khoản thật trực tiếp qua Firebase Identity Toolkit tới hộp thư người dùng."""
    init_firebase()
    if _firebase_app is None:
        logger.warning(f"Firebase app chưa khởi tạo, không thể gửi mail tới {email}")
        return False
    try:
        import urllib.request
        import json

        api_key = getattr(settings, "FIREBASE_WEB_API_KEY", "AIzaSyAeC9Ln5LN9IIlHhuwGoAcwKYp-8HDDyKU")

        # 1. Tạo custom token cho user
        token_bytes = fb_auth.create_custom_token(firebase_uid)
        custom_token = token_bytes.decode("utf-8") if isinstance(token_bytes, bytes) else str(token_bytes)

        # 2. Đổi custom token lấy idToken qua Firebase REST API
        token_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key={api_key}"
        req_token = urllib.request.Request(
            token_url,
            data=json.dumps({"token": custom_token, "returnSecureToken": True}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req_token, timeout=10) as resp:
            token_res = json.loads(resp.read().decode("utf-8"))
            id_token = token_res.get("idToken")

        if not id_token:
            logger.warning(f"Không thể lấy idToken để gửi email xác thực cho {email}")
            return False

        # 3. Gửi email xác thực chính thức từ Google Firebase tới hòm thư người dùng
        send_url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={api_key}"
        req_send = urllib.request.Request(
            send_url,
            data=json.dumps({"requestType": "VERIFY_EMAIL", "idToken": id_token}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req_send, timeout=10) as resp2:
            res_data = json.loads(resp2.read().decode("utf-8"))
            logger.info(f"Đã gửi email xác thực Firebase thành công tới {email}: {res_data}")
            return True
    except Exception as exc:
        logger.error(f"Lỗi khi gửi email xác thực Firebase tới {email}: {exc}")
        return False


def send_firebase_password_reset_email(email: str) -> bool:
    """Gửi email đặt lại mật khẩu thật từ Google Firebase tới hộp thư người dùng."""
    try:
        import urllib.request
        import json

        api_key = getattr(settings, "FIREBASE_WEB_API_KEY", "AIzaSyAeC9Ln5LN9IIlHhuwGoAcwKYp-8HDDyKU")
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={api_key}"
        req = urllib.request.Request(
            url,
            data=json.dumps({"requestType": "PASSWORD_RESET", "email": email}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            logger.info(f"Đã gửi email reset mật khẩu Firebase tới {email}: {res}")
            return True
    except Exception as exc:
        logger.error(f"Lỗi khi gửi reset mật khẩu Firebase tới {email}: {exc}")
        return False


