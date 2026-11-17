from dataclasses import dataclass
import os
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.store_errors import StoreAPIError

PRIVATE_UPLOAD_ROOT = Path(__file__).resolve().parents[2] / "private_uploads"

_SIGNATURES = {
    "application/pdf": (".pdf", lambda data: data.startswith(b"%PDF-")),
    "image/jpeg": (".jpg", lambda data: data.startswith(b"\xff\xd8\xff")),
    "image/png": (".png", lambda data: data.startswith(b"\x89PNG\r\n\x1a\n")),
}


@dataclass(frozen=True)
class ValidatedUpload:
    content: bytes
    media_type: str
    extension: str


async def validate_upload(
    upload: UploadFile | None,
    *,
    field_name: str,
    allowed_types: tuple[str, ...],
    max_bytes: int,
    required: bool,
) -> ValidatedUpload | None:
    if upload is None or not upload.filename:
        if required:
            raise StoreAPIError(
                status_code=400,
                message="Thiếu tệp bắt buộc.",
                errors={field_name: ["Vui lòng tải lên tệp này."]},
            )
        return None

    content = await upload.read(max_bytes + 1)
    await upload.seek(0)
    if len(content) > max_bytes:
        raise StoreAPIError(
            status_code=413,
            message=f"Tệp {field_name} vượt quá dung lượng cho phép.",
            errors={field_name: [f"Kích thước tối đa là {max_bytes // (1024 * 1024)}MB."]},
        )
    if not content:
        raise StoreAPIError(
            status_code=400,
            message="Tệp tải lên không hợp lệ.",
            errors={field_name: ["Tệp không được để trống."]},
        )

    detected = None
    for media_type in allowed_types:
        extension, matches_signature = _SIGNATURES[media_type]
        if matches_signature(content):
            detected = ValidatedUpload(content, media_type, extension)
            break
    if detected is None:
        raise StoreAPIError(
            status_code=415,
            message=f"Định dạng tệp {field_name} không được hỗ trợ.",
            errors={field_name: ["Nội dung tệp không đúng PDF/JPG/PNG được hỗ trợ."]},
        )
    return detected


def save_private_upload(upload: ValidatedUpload, category: str) -> str:
    if category not in {"business_licenses", "store_logos"}:
        raise ValueError("Unsupported private upload category")
    relative_path = Path(category) / f"{uuid4().hex}{upload.extension}"
    destination = (PRIVATE_UPLOAD_ROOT / relative_path).resolve()
    root = PRIVATE_UPLOAD_ROOT.resolve()
    if root not in destination.parents:
        raise ValueError("Generated upload path escaped private storage")

    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        file_descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(file_descriptor, "wb") as target:
            target.write(upload.content)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return relative_path.as_posix()


def delete_private_upload(relative_path: str | None) -> None:
    if not relative_path:
        return
    path = resolve_private_upload(relative_path)
    if path is not None:
        path.unlink(missing_ok=True)


def resolve_private_upload(relative_path: str | None) -> Path | None:
    if not relative_path:
        return None
    root = PRIVATE_UPLOAD_ROOT.resolve()
    candidate = (root / relative_path).resolve()
    if root not in candidate.parents or not candidate.is_file():
        return None
    return candidate
