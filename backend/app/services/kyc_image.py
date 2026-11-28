"""Kiểm tra ảnh eKYC bằng Pillow và chuẩn hóa để xóa EXIF/metadata.

Không tự chấm điểm duyệt hồ sơ; các phát hiện như mờ/QR trả về dạng cờ để
admin xem xét. Ảnh đầu ra luôn được mã hóa lại trước khi lưu vào kho riêng.
"""
from dataclasses import dataclass, field
from io import BytesIO
from threading import Lock
from typing import Optional
import warnings

from PIL import Image, ImageFilter, ImageOps, ImageStat, UnidentifiedImageError

from app.core.config import Settings, settings
from app.core.kyc_errors import KycBusinessError, KycErrorCode
from app.schemas.kyc import KycImageKind
from app.services.kyc_qr import compare_qr_with_consent, extract_qr_payload, hash_payload

_PIXEL_LIMIT_LOCK = Lock()
_BLUR_MEAN_THRESHOLD = 8.0


@dataclass
class KycImageInspection:
    content: bytes
    extension: str
    width: int
    height: int
    flags: list[str] = field(default_factory=list)
    qr_payload_hash: Optional[str] = None
    qr_consistent: Optional[bool] = None


def _normalized_bytes(image: Image.Image, source_format: str) -> tuple[bytes, str]:
    output = BytesIO()
    if source_format == "JPEG":
        image.convert("RGB").save(output, format="JPEG", quality=90, optimize=True)
        return output.getvalue(), ".jpg"
    image.convert("RGBA").save(output, format="PNG", optimize=True)
    return output.getvalue(), ".png"


def _blur_flag(image: Image.Image) -> Optional[str]:
    gray = ImageOps.grayscale(image)
    width, height = gray.size
    scale = min(1.0, 320 / max(width, height))
    small = gray.resize((max(1, int(width * scale)), max(1, int(height * scale))))
    edges = small.filter(ImageFilter.FIND_EDGES)
    mean = ImageStat.Stat(edges).mean[0]
    return "low_sharpness" if mean < _BLUR_MEAN_THRESHOLD else None


def inspect_and_normalize_image(
    content: bytes,
    kind: KycImageKind | str,
    config: Settings | None = None,
    consent: object | None = None,
) -> KycImageInspection:
    config = config or settings
    kind_value = getattr(kind, "value", str(kind)).strip().lower()
    if len(content) > config.KYC_MAX_UPLOAD_BYTES:
        raise KycBusinessError(KycErrorCode.KYC_IMAGE_TOO_LARGE)
    if len(content) < 32:
        raise KycBusinessError(KycErrorCode.KYC_IMAGE_TOO_SMALL)

    flags: list[str] = []
    original_limit = Image.MAX_IMAGE_PIXELS
    with _PIXEL_LIMIT_LOCK:
        Image.MAX_IMAGE_PIXELS = config.KYC_MAX_IMAGE_PIXELS
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(content)) as opened:
                    source_format = (opened.format or "").upper()
                    if source_format not in {"JPEG", "PNG"}:
                        raise KycBusinessError(KycErrorCode.KYC_IMAGE_INVALID_FORMAT)
                    image = ImageOps.exif_transpose(opened).copy()
        except (Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise KycBusinessError(KycErrorCode.KYC_DECOMPRESSION_BOMB)
        except UnidentifiedImageError:
            raise KycBusinessError(KycErrorCode.KYC_IMAGE_INVALID_FORMAT)
        finally:
            Image.MAX_IMAGE_PIXELS = original_limit

    width, height = image.size
    if width < config.KYC_MIN_IMAGE_WIDTH or height < config.KYC_MIN_IMAGE_HEIGHT:
        raise KycBusinessError(KycErrorCode.KYC_IMAGE_LOW_RESOLUTION)

    aspect = width / height
    if kind_value in {KycImageKind.FRONT.value, KycImageKind.BACK.value}:
        low, high = config.KYC_ID_ASPECT_MIN, config.KYC_ID_ASPECT_MAX
    elif kind_value == KycImageKind.SELFIE.value:
        low, high = config.KYC_SELFIE_ASPECT_MIN, config.KYC_SELFIE_ASPECT_MAX
    else:
        raise KycBusinessError(KycErrorCode.KYC_FORBIDDEN, "Loại ảnh eKYC không hợp lệ.")
    if not low <= aspect <= high:
        raise KycBusinessError(KycErrorCode.KYC_IMAGE_BAD_ASPECT)

    if config.KYC_BLUR_CHECK_ENABLED:
        blur_flag = _blur_flag(image)
        if blur_flag:
            flags.append(blur_flag)

    qr_hash: str | None = None
    qr_consistent: bool | None = None
    if config.KYC_QR_CHECK_ENABLED and kind_value in {
        KycImageKind.FRONT.value,
        KycImageKind.BACK.value,
    }:
        payload = extract_qr_payload(image)
        if payload:
            qr_hash = hash_payload(payload)
            qr_consistent, qr_flags = compare_qr_with_consent(payload, consent)
            flags.extend(qr_flags)
        else:
            flags.append("qr_unavailable")

    normalized, extension = _normalized_bytes(image, source_format)
    return KycImageInspection(
        content=normalized,
        extension=extension,
        width=width,
        height=height,
        flags=flags,
        qr_payload_hash=qr_hash,
        qr_consistent=qr_consistent,
    )
