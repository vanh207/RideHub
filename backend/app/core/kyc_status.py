"""Máy trạng thái phiên KYC, đặt tập trung để mọi luồng cùng tuân thủ."""
from typing import Any, Optional

from app.core.kyc_errors import KycBusinessError, KycErrorCode

CREATED = "CREATED"
CONSENTED = "CONSENTED"
ID_UPLOADED = "ID_UPLOADED"
FACE_UPLOADED = "FACE_UPLOADED"
SUBMITTED = "SUBMITTED"
APPROVED = "APPROVED"
REJECTED = "REJECTED"
EXPIRED = "EXPIRED"
NOT_STARTED = "NOT_STARTED"

ALL_STATUSES = {
    CREATED,
    CONSENTED,
    ID_UPLOADED,
    FACE_UPLOADED,
    SUBMITTED,
    APPROVED,
    REJECTED,
    EXPIRED,
}

TERMINAL_STATUSES = {APPROVED, REJECTED, EXPIRED}

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    CREATED: {CONSENTED, EXPIRED},
    CONSENTED: {ID_UPLOADED, EXPIRED},
    ID_UPLOADED: {FACE_UPLOADED, EXPIRED},
    FACE_UPLOADED: {SUBMITTED, EXPIRED},
    SUBMITTED: {APPROVED, REJECTED},
    APPROVED: set(),
    REJECTED: set(),
    EXPIRED: set(),
}


def normalize_status(status: Optional[str]) -> str:
    """Chuẩn hóa chuỗi trạng thái; trả chuỗi rỗng nếu thiếu."""
    if not status:
        return ""
    return str(status).strip().upper()


def can_transition(current_status: Optional[str], target_status: Optional[str]) -> bool:
    current = normalize_status(current_status)
    target = normalize_status(target_status)
    if not current or not target or current == target:
        return False
    return target in ALLOWED_TRANSITIONS.get(current, set())


def assert_transition(current_status: Optional[str], target_status: Optional[str]) -> None:
    if not can_transition(current_status, target_status):
        raise KycBusinessError(
            KycErrorCode.KYC_INVALID_TRANSITION,
            details={
                "from": normalize_status(current_status),
                "to": normalize_status(target_status),
            },
        )


def apply_transition(session: Any, target_status: str) -> str:
    """Chuyển trạng thái đối tượng KycSession và trả trạng thái mới."""
    target = normalize_status(target_status)
    assert_transition(getattr(session, "status", None), target)
    setattr(session, "status", target)
    return target


def is_terminal(status: Optional[str]) -> bool:
    return normalize_status(status) in TERMINAL_STATUSES
