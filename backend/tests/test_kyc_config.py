"""Kiểm tra cấu hình eKYC, đặc biệt lỗi cấu hình vendor."""
import pytest
from pydantic import ValidationError

from app.core.config import Settings


def make_settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_default_kyc_settings_do_not_break_existing_flow() -> None:
    config = make_settings()
    assert config.KYC_ENABLED is True
    assert config.KYC_REQUIRED_FOR_BOOKING is False
    assert config.KYC_FACE_PROVIDER == "manual"
    assert config.KYC_FACE_RETENTION_DAYS == 30
    assert config.KYC_ID_RETENTION_DAYS == 180
    assert config.KYC_CONSENT_VERSION == "2026-11-v1"
    assert config.KYC_MATCH_THRESHOLD is None


def test_provider_name_is_normalized() -> None:
    config = make_settings(KYC_FACE_PROVIDER=" MANUAL ")
    assert config.KYC_FACE_PROVIDER == "manual"


def test_unknown_provider_is_rejected_with_vietnamese_message() -> None:
    with pytest.raises(ValidationError) as exc:
        make_settings(KYC_FACE_PROVIDER="magic-ai")
    assert "KYC_FACE_PROVIDER" in str(exc.value)


def test_vendor_requires_credentials() -> None:
    with pytest.raises(ValidationError) as exc:
        make_settings(KYC_FACE_PROVIDER="vendor")
    message = str(exc.value)
    assert "KYC_VENDOR_BASE_URL" in message
    assert "KYC_VENDOR_API_KEY" in message


def test_vendor_with_credentials_is_valid() -> None:
    config = make_settings(
        KYC_FACE_PROVIDER="vendor",
        KYC_VENDOR_BASE_URL="https://vendor.example",
        KYC_VENDOR_API_KEY="khoa-khong-that",
    )
    assert config.KYC_FACE_PROVIDER == "vendor"


def test_invalid_match_threshold_is_rejected() -> None:
    with pytest.raises(ValidationError):
        make_settings(KYC_MATCH_THRESHOLD=1.5)


def test_non_positive_retention_is_rejected() -> None:
    with pytest.raises(ValidationError):
        make_settings(KYC_FACE_RETENTION_DAYS=0)
