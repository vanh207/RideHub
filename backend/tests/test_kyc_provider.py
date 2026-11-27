"""Kiểm tra provider eKYC: manual/mock/vendor và việc bỏ qua điểm client."""
import pytest

from app.core.config import Settings
from app.core.kyc_errors import KycBusinessError, KycErrorCode
from app.services.kyc_provider import (
    FaceVerificationProvider,
    ManualProvider,
    MockProvider,
    VendorProvider,
    create_kyc_provider,
)


def config(**overrides: object) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_manual_provider_never_scores() -> None:
    provider = ManualProvider()
    result = provider.compare("front.jpg", "selfie.jpg")
    assert result.score is None
    assert result.provider == "manual"
    assert "manual_review_required" in result.flags
    assert provider.check_liveness(["a.jpg"], "quay-trai").result == "manual_review"


def test_mock_provider_is_deterministic() -> None:
    provider = MockProvider(score=0.73)
    assert provider.compare("a.jpg", "b.jpg").score == 0.73
    assert provider.detect_face("a.jpg").face_count == 1
    assert provider.check_liveness(["a.jpg"], "challenge").result == "pass"


def test_provider_does_not_accept_client_score() -> None:
    provider: FaceVerificationProvider = MockProvider()
    with pytest.raises(TypeError):
        provider.compare("a.jpg", "b.jpg", score=0.99)


def test_vendor_provider_is_only_a_framework() -> None:
    provider = VendorProvider("https://vendor.example", "khoa-khong-that")
    assert provider.compare("a.jpg", "b.jpg").score is None
    assert "vendor_not_implemented" in provider.compare("a.jpg", "b.jpg").flags
    with pytest.raises(KycBusinessError) as exc:
        VendorProvider("", "")
    assert exc.value.code == KycErrorCode.KYC_VENDOR_CONFIG_INVALID


def test_factory_uses_configuration() -> None:
    assert isinstance(create_kyc_provider(settings_obj=config()), ManualProvider)
    assert isinstance(
        create_kyc_provider(settings_obj=config(KYC_FACE_PROVIDER="mock")),
        MockProvider,
    )
    assert isinstance(
        create_kyc_provider(
            settings_obj=config(
                KYC_FACE_PROVIDER="vendor",
                KYC_VENDOR_BASE_URL="https://vendor.example",
                KYC_VENDOR_API_KEY="khoa-khong-that",
            )
        ),
        VendorProvider,
    )


def test_factory_rejects_unknown_provider() -> None:
    with pytest.raises(KycBusinessError) as exc:
        create_kyc_provider("unknown", settings_obj=config())
    assert exc.value.code == KycErrorCode.KYC_PROVIDER_UNAVAILABLE
