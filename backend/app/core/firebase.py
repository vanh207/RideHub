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
        if "phone" in str(fe).lower():
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
    """Xác thực Firebase ID Token do Frontend gửi lên (khi đăng nhập / OTP)."""
    init_firebase()

    if _firebase_app is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Firebase Admin SDK chưa được cấu hình tệp serviceAccountKey.json.",
        )

    try:
        decoded = fb_auth.verify_id_token(id_token)
        return decoded
    except exceptions.FirebaseError as fe:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Firebase ID Token không hợp lệ hoặc đã hết hạn: {fe}",
        )
