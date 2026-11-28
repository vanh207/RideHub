"""Cổng so khớp khuôn mặt và các bộ chuyển đổi mặc định.

Không nhúng mô hình học máy vào ứng dụng chính. Manual là mặc định; Mock chỉ dùng
cho test/demo; Vendor là bộ khung, chưa gọi nhà cung cấp thật.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from app.core.config import Settings, settings
from app.core.kyc_errors import KycBusinessError, KycErrorCode


@dataclass
class FaceDetectionResult:
    face_count: Optional[int] = None
    flags: list[str] = field(default_factory=list)


@dataclass
class FaceComparisonResult:
    score: Optional[float] = None
    flags: list[str] = field(default_factory=list)
    provider: str = "manual"


@dataclass
class LivenessResult:
    result: str = "manual_review"
    flags: list[str] = field(default_factory=list)


class FaceVerificationProvider(ABC):
    """Hợp đồng duy nhất để backend gọi, bất kể nhà cung cấp bên dưới."""

    name = "base"

    @abstractmethod
    def detect_face(self, image_path: str) -> FaceDetectionResult:
        """Đếm số khuôn mặt trong ảnh; trả None nếu không tự đánh giá được."""

    @abstractmethod
    def compare(self, id_photo_path: str, selfie_path: str) -> FaceComparisonResult:
        """So khớp ảnh CCCD với selfie; không nhận điểm do client gửi."""

    @abstractmethod
    def check_liveness(self, frame_paths: list[str], challenge: str) -> LivenessResult:
        """Đánh giá liveness dựa trên challenge do server sinh."""


class ManualProvider(FaceVerificationProvider):
    """Mặc định: không tự chấm điểm, để admin xem xét."""

    name = "manual"

    def detect_face(self, image_path: str) -> FaceDetectionResult:
        return FaceDetectionResult(face_count=None, flags=["manual_review_required"])

    def compare(self, id_photo_path: str, selfie_path: str) -> FaceComparisonResult:
        return FaceComparisonResult(
            score=None,
            flags=["manual_review_required"],
            provider=self.name,
        )

    def check_liveness(self, frame_paths: list[str], challenge: str) -> LivenessResult:
        return LivenessResult(result="manual_review", flags=["manual_review_required"])


class MockProvider(FaceVerificationProvider):
    """Kết quả xác định cho test/demo; không phải mô hình thật."""

    name = "mock"

    def __init__(self, score: float = 0.82) -> None:
        self.score = score

    def detect_face(self, image_path: str) -> FaceDetectionResult:
        return FaceDetectionResult(face_count=1, flags=["mock_provider"])

    def compare(self, id_photo_path: str, selfie_path: str) -> FaceComparisonResult:
        return FaceComparisonResult(
            score=self.score,
            flags=["mock_provider", "score_not_calibrated"],
            provider=self.name,
        )

    def check_liveness(self, frame_paths: list[str], challenge: str) -> LivenessResult:
        passed = bool(frame_paths) and bool(challenge)
        return LivenessResult(
            result="pass" if passed else "manual_review",
            flags=["mock_provider", "score_not_calibrated"],
        )


class VendorProvider(FaceVerificationProvider):
    """Bộ khung cho eKYC bên ngoài; chưa thực hiện gọi mạng."""

    name = "vendor"

    def __init__(self, base_url: str, api_key: str, timeout_seconds: int = 10) -> None:
        if not base_url or not api_key:
            raise KycBusinessError(KycErrorCode.KYC_VENDOR_CONFIG_INVALID)
        self.base_url = base_url
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def detect_face(self, image_path: str) -> FaceDetectionResult:
        return FaceDetectionResult(face_count=None, flags=["vendor_not_implemented"])

    def compare(self, id_photo_path: str, selfie_path: str) -> FaceComparisonResult:
        return FaceComparisonResult(
            score=None,
            flags=["vendor_not_implemented"],
            provider=self.name,
        )

    def check_liveness(self, frame_paths: list[str], challenge: str) -> LivenessResult:
        return LivenessResult(result="manual_review", flags=["vendor_not_implemented"])


def create_kyc_provider(
    provider_name: Optional[str] = None,
    settings_obj: Optional[Settings] = None,
) -> FaceVerificationProvider:
    """Tạo provider theo cấu hình; vendor thiếu khóa thì báo lỗi rõ ràng."""
    config = settings_obj or settings
    name = (provider_name or config.KYC_FACE_PROVIDER).strip().lower()

    if name == "manual":
        return ManualProvider()
    if name == "mock":
        return MockProvider(score=config.KYC_MOCK_SCORE)
    if name == "vendor":
        return VendorProvider(
            base_url=config.KYC_VENDOR_BASE_URL,
            api_key=config.KYC_VENDOR_API_KEY,
            timeout_seconds=config.KYC_VENDOR_TIMEOUT_SECONDS,
        )
    raise KycBusinessError(
        KycErrorCode.KYC_PROVIDER_UNAVAILABLE,
        f"Nhà cung cấp xác thực '{name}' không được hỗ trợ.",
    )
