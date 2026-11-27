"""Kiểm tra xử lý ảnh eKYC bằng Pillow và QR chịu lỗi."""
from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image

from app.core.config import Settings
from app.core.kyc_errors import KycBusinessError, KycErrorCode
from app.schemas.kyc import KycImageKind
from app.services import kyc_image
from app.services.kyc_qr import compare_qr_with_consent, hash_payload, parse_qr_fields


def make_image(width: int = 800, height: int = 500, exif: object | None = None) -> bytes:
    image = Image.new("RGB", (width, height), "white")
    output = BytesIO()
    if exif is None:
        image.save(output, format="JPEG")
    else:
        image.save(output, format="JPEG", exif=exif)
    return output.getvalue()


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {"KYC_QR_CHECK_ENABLED": False}
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_valid_image_is_normalized_without_exif() -> None:
    exif = Image.Exif()
    exif[270] = "secret-metadata"
    inspection = kyc_image.inspect_and_normalize_image(
        make_image(exif=exif), KycImageKind.FRONT, config=settings()
    )
    assert inspection.width == 800
    assert inspection.height == 500
    assert inspection.extension == ".jpg"
    assert b"secret-metadata" not in inspection.content
    assert inspection.qr_payload_hash is None


def test_image_size_resolution_format_and_aspect_are_rejected() -> None:
    with pytest.raises(KycBusinessError) as large:
        kyc_image.inspect_and_normalize_image(
            make_image(), KycImageKind.FRONT, config=settings(KYC_MAX_UPLOAD_BYTES=10)
        )
    assert large.value.code == KycErrorCode.KYC_IMAGE_TOO_LARGE

    with pytest.raises(KycBusinessError) as small:
        kyc_image.inspect_and_normalize_image(
            make_image(400, 400), KycImageKind.FRONT, config=settings()
        )
    assert small.value.code == KycErrorCode.KYC_IMAGE_LOW_RESOLUTION

    with pytest.raises(KycBusinessError) as aspect:
        kyc_image.inspect_and_normalize_image(
            make_image(1300, 500), KycImageKind.FRONT, config=settings()
        )
    assert aspect.value.code == KycErrorCode.KYC_IMAGE_BAD_ASPECT

    with pytest.raises(KycBusinessError) as invalid:
            kyc_image.inspect_and_normalize_image(
                b"khong phai anh" * 5, KycImageKind.FRONT, config=settings()
            )
    assert invalid.value.code == KycErrorCode.KYC_IMAGE_INVALID_FORMAT


def test_missing_qr_reader_only_adds_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(kyc_image, "extract_qr_payload", lambda image: None)
    inspection = kyc_image.inspect_and_normalize_image(
        make_image(), KycImageKind.FRONT, config=settings(KYC_QR_CHECK_ENABLED=True)
    )
    assert "qr_unavailable" in inspection.flags
    assert inspection.qr_consistent is None


def test_qr_fields_and_hash_do_not_expose_raw_payload() -> None:
    payload = "001230000001|Nguyen Van A|01/01/1990|Ho Chi Minh"
    fields = parse_qr_fields(payload)
    assert fields["document_number"] == "001230000001"
    assert fields["full_name"] == "Nguyen Van A"
    assert hash_payload(payload) != payload
    assert len(hash_payload(payload)) == 64

    consent = SimpleNamespace(
        document_number="001230000001",
        full_name="Nguyễn Văn A",
        date_of_birth="1990-01-01",
        issued_date=None,
        address=None,
    )
    consistent, flags = compare_qr_with_consent(payload, consent)
    assert consistent is True
    assert flags == []

    mismatched, flags = compare_qr_with_consent(
        payload,
        SimpleNamespace(
            document_number="999999999999",
            full_name="Khac",
            date_of_birth="2000-01-01",
            issued_date=None,
            address=None,
        ),
    )
    assert mismatched is False
    assert flags == ["qr_mismatch"]
