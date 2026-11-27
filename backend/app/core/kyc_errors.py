"""Mã lỗi nghiệp vụ eKYC và thông điệp tiếng Việt.

Frontend ánh xạ các mã này ở MỘT bảng duy nhất; backend không trả dữ liệu nhạy cảm
trong details (không ghi số CCCD đầy đủ, ảnh hay base64).
"""
from enum import Enum
from typing import Any, Optional


class KycErrorCode(str, Enum):
    KYC_DISABLED = "KYC_DISABLED"
    KYC_CONSENT_REQUIRED = "KYC_CONSENT_REQUIRED"
    KYC_SESSION_NOT_FOUND = "KYC_SESSION_NOT_FOUND"
    KYC_SESSION_EXPIRED = "KYC_SESSION_EXPIRED"
    KYC_SESSION_USED = "KYC_SESSION_USED"
    KYC_INVALID_TRANSITION = "KYC_INVALID_TRANSITION"
    KYC_ATTEMPTS_EXCEEDED = "KYC_ATTEMPTS_EXCEEDED"
    KYC_CHALLENGE_INVALID = "KYC_CHALLENGE_INVALID"
    KYC_UPLOAD_REQUIRED = "KYC_UPLOAD_REQUIRED"
    KYC_IMAGE_INVALID_FORMAT = "KYC_IMAGE_INVALID_FORMAT"
    KYC_IMAGE_TOO_LARGE = "KYC_IMAGE_TOO_LARGE"
    KYC_IMAGE_TOO_SMALL = "KYC_IMAGE_TOO_SMALL"
    KYC_IMAGE_LOW_RESOLUTION = "KYC_IMAGE_LOW_RESOLUTION"
    KYC_IMAGE_BAD_ASPECT = "KYC_IMAGE_BAD_ASPECT"
    KYC_IMAGE_TOO_BLURRY = "KYC_IMAGE_TOO_BLURRY"
    KYC_DECOMPRESSION_BOMB = "KYC_DECOMPRESSION_BOMB"
    KYC_QR_UNAVAILABLE = "KYC_QR_UNAVAILABLE"
    KYC_QR_UNPARSABLE = "KYC_QR_UNPARSABLE"
    KYC_QR_MISMATCH = "KYC_QR_MISMATCH"
    KYC_AGE_BELOW_MINIMUM = "KYC_AGE_BELOW_MINIMUM"
    KYC_ID_EXPIRED = "KYC_ID_EXPIRED"
    KYC_DUPLICATE_ID = "KYC_DUPLICATE_ID"
    KYC_NOT_APPROVED = "KYC_NOT_APPROVED"
    KYC_FORBIDDEN = "KYC_FORBIDDEN"
    KYC_PROVIDER_UNAVAILABLE = "KYC_PROVIDER_UNAVAILABLE"
    KYC_VENDOR_CONFIG_INVALID = "KYC_VENDOR_CONFIG_INVALID"
    KYC_DELETE_FAILED = "KYC_DELETE_FAILED"


ERROR_MESSAGES: dict[KycErrorCode, str] = {
    KycErrorCode.KYC_DISABLED: "Tính năng xác thực danh tính đang tắt.",
    KycErrorCode.KYC_CONSENT_REQUIRED: "Bạn cần đồng ý xử lý dữ liệu sinh trắc học trước khi tiếp tục.",
    KycErrorCode.KYC_SESSION_NOT_FOUND: "Không tìm thấy phiên xác thực hợp lệ.",
    KycErrorCode.KYC_SESSION_EXPIRED: "Phiên xác thực đã hết hạn. Vui lòng bắt đầu lại.",
    KycErrorCode.KYC_SESSION_USED: "Phiên xác thực này đã được gửi. Vui lòng tạo phiên mới nếu cần gửi lại.",
    KycErrorCode.KYC_INVALID_TRANSITION: "Trạng thái hồ sơ không cho phép thao tác này.",
    KycErrorCode.KYC_ATTEMPTS_EXCEEDED: "Bạn đã vượt quá số lần thử trong ngày. Vui lòng thử lại sau.",
    KycErrorCode.KYC_CHALLENGE_INVALID: "Yêu cầu quét mặt không còn hiệu lực. Vui lòng bắt đầu lại.",
    KycErrorCode.KYC_UPLOAD_REQUIRED: "Vui lòng tải đủ ảnh CCCD và ảnh khuôn mặt.",
    KycErrorCode.KYC_IMAGE_INVALID_FORMAT: "Ảnh không đúng định dạng cho phép (JPEG hoặc PNG).",
    KycErrorCode.KYC_IMAGE_TOO_LARGE: "Ảnh quá lớn. Vui lòng chọn ảnh nhỏ hơn.",
    KycErrorCode.KYC_IMAGE_TOO_SMALL: "Ảnh quá nhỏ. Vui lòng chọn ảnh khác.",
    KycErrorCode.KYC_IMAGE_LOW_RESOLUTION: "Độ phân giải ảnh chưa đạt yêu cầu. Vui lòng chụp lại.",
    KycErrorCode.KYC_IMAGE_BAD_ASPECT: "Tỷ lệ khung ảnh chưa phù hợp. Vui lòng chụp lại.",
    KycErrorCode.KYC_IMAGE_TOO_BLURRY: "Ảnh bị mờ. Vui lòng giữ điện thoại ổn định và chụp lại.",
    KycErrorCode.KYC_DECOMPRESSION_BOMB: "Ảnh có kích thước giải mã bất thường và đã bị từ chối.",
    KycErrorCode.KYC_QR_UNAVAILABLE: "Chưa kiểm được mã QR trên CCCD; admin sẽ xem xét thủ công.",
    KycErrorCode.KYC_QR_UNPARSABLE: "Không đọc được nội dung mã QR; admin sẽ xem xét thủ công.",
    KycErrorCode.KYC_QR_MISMATCH: "Thông tin mã QR chưa khớp với thông tin bạn khai báo; admin sẽ xem xét.",
    KycErrorCode.KYC_AGE_BELOW_MINIMUM: "Người thuê phải từ đủ 18 tuổi.",
    KycErrorCode.KYC_ID_EXPIRED: "CCCD đã hết hạn. Vui lòng dùng giấy tờ còn hiệu lực.",
    KycErrorCode.KYC_DUPLICATE_ID: "Số CCCD này đã được gắn với một hồ sơ khác.",
    KycErrorCode.KYC_NOT_APPROVED: "Hồ sơ định danh chưa được duyệt. Vui lòng hoàn tất xác thực danh tính.",
    KycErrorCode.KYC_FORBIDDEN: "Bạn không có quyền truy cập tài nguyên này.",
    KycErrorCode.KYC_PROVIDER_UNAVAILABLE: "Dịch vụ so khớp khuôn mặt hiện không khả dụng; hồ sơ sẽ do admin xem xét.",
    KycErrorCode.KYC_VENDOR_CONFIG_INVALID: "Cấu hình nhà cung cấp xác thực chưa đầy đủ.",
    KycErrorCode.KYC_DELETE_FAILED: "Không thể xóa toàn bộ dữ liệu xác thực. Vui lòng liên hệ bộ phận hỗ trợ.",
}


class KycBusinessError(Exception):
    """Lỗi nghiệp vụ eKYC có mã máy đọc được và thông điệp tiếng Việt."""

    def __init__(
        self,
        code: KycErrorCode,
        message: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        self.code = code
        self.message = message or ERROR_MESSAGES[code]
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code.value if isinstance(self.code, KycErrorCode) else self.code,
            "message": self.message,
            "details": self.details,
        }
