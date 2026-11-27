"""Kiểm tra mọi mã lỗi nghiệp vụ đều có thông điệp tiếng Việt."""
from app.core.kyc_errors import ERROR_MESSAGES, KycBusinessError, KycErrorCode


def test_every_error_code_has_message() -> None:
    assert set(ERROR_MESSAGES) == set(KycErrorCode)
    for code, message in ERROR_MESSAGES.items():
        assert message.strip()
        assert KycBusinessError(code).message == message


def test_error_to_dict_is_machine_readable() -> None:
    error = KycBusinessError(KycErrorCode.KYC_DUPLICATE_ID)
    payload = error.to_dict()
    assert payload["code"] == "KYC_DUPLICATE_ID"
    assert "đã được gắn" in payload["message"]
    assert payload["details"] == {}
