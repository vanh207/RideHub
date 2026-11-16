"""Dependency FastAPI: lấy user hiện tại từ Bearer JWT trong header."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import decode_access_token
from app.models.user import User

_security = HTTPBearer()


def get_current_user(
    cred: HTTPAuthorizationCredentials = Depends(_security),
    db: Session = Depends(get_db),
) -> User:
    """Giải mã JWT và trả về đối tượng User từ DB."""
    token = cred.credentials
    payload = decode_access_token(token)
    subject = payload.get("sub") if payload else None

    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ",
        )

    try:
        user_id = int(subject)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Không tìm thấy người dùng",
        )

    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản đã bị vô hiệu hóa.",
        )
    return user


def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    """Chỉ user có role 'admin' mới được đi tiếp."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền admin",
        )
    return current_user


def get_current_store_owner(current_user: User = Depends(get_current_user)) -> User:
    """Chỉ user có role 'store_owner' hoặc 'admin' mới được đi tiếp."""
    if current_user.role not in ["store_owner", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền chủ cửa hàng (Store Owner)",
        )
    return current_user


def get_current_staff(current_user: User = Depends(get_current_user)) -> User:
    """Chỉ user có role 'store_staff', 'store_owner', hoặc 'admin' mới được đi tiếp."""
    if current_user.role not in ["store_staff", "store_owner", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền nhân viên cửa hàng (Store Staff)",
        )
    return current_user


def require_roles(*allowed_roles: str):
    """Dependency factory kiểm tra người dùng phải thuộc một trong các vai trò được cấp phép."""
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_role = (current_user.role or "").lower()
        normalized_allowed = [r.lower() for r in allowed_roles]
        if user_role not in normalized_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Truy cập bị từ chối. Yêu cầu một trong các vai trò: {', '.join(allowed_roles)}",
            )
        return current_user
    return role_checker
