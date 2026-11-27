"""Giao diện lưu ảnh eKYC và cài đặt thư mục riêng bản đầu.

Đổi sang lưu trữ đám mây sau này chỉ cần thay lớp này; router/service không biết
ảnh được lưu ở đâu. Không bao giờ trả về URL công khai cho ảnh ở đây.
"""
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
from uuid import uuid4

from app.core.config import settings
from app.core.kyc_errors import KycBusinessError, KycErrorCode

ALLOWED_KINDS = frozenset({"front", "back", "selfie"})
ALLOWED_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png"})


class KycFileStore(ABC):
    """Hợp đồng lưu/đọc/xóa ảnh eKYC."""

    @abstractmethod
    def save(self, kind: str, content: bytes, extension: str) -> str:
        """Lưu ảnh và trả đường dẫn tương đối do hệ thống sinh ra."""

    @abstractmethod
    def read(self, relative_path: str) -> bytes:
        """Đọc ảnh từ đường dẫn tương đối đã lưu."""

    @abstractmethod
    def delete(self, relative_path: str) -> bool:
        """Xóa ảnh; trả True nếu file tồn tại và đã xóa."""

    @abstractmethod
    def exists(self, relative_path: str) -> bool:
        """Kiểm tra file có tồn tại hay không."""


class LocalKycFileStore(KycFileStore):
    """Lưu ảnh trong private_uploads/kyc/<kind>/<uuid>.<ext>."""

    def __init__(self, root: Optional[Path] = None) -> None:
        configured = Path(getattr(settings, "KYC_PRIVATE_UPLOAD_DIR", "private_uploads/kyc"))
        if not configured.is_absolute():
            configured = Path(__file__).resolve().parents[2] / configured
        self.root = (root or configured).resolve()

    def _resolve(self, relative_path: str) -> Path:
        candidate = Path(relative_path)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise KycBusinessError(KycErrorCode.KYC_FORBIDDEN, "Đường dẫn ảnh không hợp lệ.")
        target = (self.root / candidate).resolve()
        if not target.is_relative_to(self.root):
            raise KycBusinessError(KycErrorCode.KYC_FORBIDDEN, "Đường dẫn ảnh không hợp lệ.")
        return target

    def save(self, kind: str, content: bytes, extension: str) -> str:
        if kind not in ALLOWED_KINDS:
            raise KycBusinessError(KycErrorCode.KYC_FORBIDDEN, "Loại ảnh eKYC không hợp lệ.")
        ext = extension.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise KycBusinessError(KycErrorCode.KYC_IMAGE_INVALID_FORMAT)
        if not isinstance(content, (bytes, bytearray)) or not content:
            raise KycBusinessError(KycErrorCode.KYC_IMAGE_TOO_SMALL)

        folder = self.root / kind
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)
        os.chmod(folder, 0o700)

        name = f"{uuid4().hex}{ext}"
        target = folder / name
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(content)
        except Exception:
            target.unlink(missing_ok=True)
            raise
        return f"{kind}/{name}"

    def read(self, relative_path: str) -> bytes:
        target = self._resolve(relative_path)
        if not target.is_file():
            raise KycBusinessError(KycErrorCode.KYC_SESSION_NOT_FOUND, "Không tìm thấy ảnh đã lưu.")
        return target.read_bytes()

    def delete(self, relative_path: str) -> bool:
        target = self._resolve(relative_path)
        if not target.is_file():
            return False
        target.unlink()
        return True

    def exists(self, relative_path: str) -> bool:
        return self._resolve(relative_path).is_file()


kyc_file_store: KycFileStore = LocalKycFileStore()
