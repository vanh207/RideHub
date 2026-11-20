"""Trạng thái đơn hàng dùng chung cho luồng đặt xe, thanh toán và hủy đơn.

Các trạng thái legacy vẫn được chấp nhận khi đọc dữ liệu cũ nhưng không được
dùng khi ghi trạng thái mới.
"""
from typing import Optional

PENDING_PAYMENT = "PENDING_PAYMENT"
DEPOSIT_PAID = "DEPOSIT_PAID"
CONFIRMED = "CONFIRMED"
IN_PROGRESS = "IN_PROGRESS"
PENDING_SETTLEMENT = "PENDING_SETTLEMENT"
COMPLETED = "COMPLETED"
CANCELLED = "CANCELLED"
EXPIRED = "EXPIRED"

LEGACY_STATUS_ALIASES = {
    "PENDING": PENDING_PAYMENT,
    "PENDING_STORE_CONFIRM": DEPOSIT_PAID,
    "BOOKED": DEPOSIT_PAID,
}

CANONICAL_STATUSES = {
    PENDING_PAYMENT,
    DEPOSIT_PAID,
    CONFIRMED,
    IN_PROGRESS,
    PENDING_SETTLEMENT,
    COMPLETED,
    CANCELLED,
    EXPIRED,
}

TERMINAL_STATUSES = {COMPLETED, CANCELLED, EXPIRED}

BLOCKING_STATUSES = {
    PENDING_PAYMENT,
    DEPOSIT_PAID,
    CONFIRMED,
    IN_PROGRESS,
    PENDING_SETTLEMENT,
}

BLOCKING_STATUSES_INCLUDING_LEGACY = BLOCKING_STATUSES | set(
    LEGACY_STATUS_ALIASES
)

CANCELLABLE_STATUSES = {
    PENDING_PAYMENT,
    DEPOSIT_PAID,
    CONFIRMED,
}

ALLOWED_TRANSITIONS = {
    PENDING_PAYMENT: {DEPOSIT_PAID, EXPIRED, CANCELLED},
    DEPOSIT_PAID: {CONFIRMED, CANCELLED},
    CONFIRMED: {IN_PROGRESS, CANCELLED},
    IN_PROGRESS: {PENDING_SETTLEMENT, CANCELLED},
    PENDING_SETTLEMENT: {COMPLETED, CANCELLED},
    COMPLETED: set(),
    CANCELLED: set(),
    EXPIRED: set(),
}

CANCEL_ACTOR_CUSTOMER = "CUSTOMER"
CANCEL_ACTOR_STORE = "STORE"
CANCEL_ACTOR_ADMIN = "ADMIN"
CANCEL_ACTOR_SYSTEM = "SYSTEM"


def normalize_status(status: Optional[str]) -> str:
    """Chuyển trạng thái legacy về trạng thái chuẩn, giữ nguyên nếu không biết."""
    if not status:
        return ""
    cleaned = str(status).strip().upper()
    return LEGACY_STATUS_ALIASES.get(cleaned, cleaned)


def is_terminal(status: Optional[str]) -> bool:
    return normalize_status(status) in TERMINAL_STATUSES


def is_blocking(status: Optional[str]) -> bool:
    raw = str(status or "").strip().upper()
    return raw in BLOCKING_STATUSES_INCLUDING_LEGACY


def can_transition(current_status: Optional[str], target_status: Optional[str]) -> bool:
    current = normalize_status(current_status)
    target = normalize_status(target_status)
    if not current or not target or current == target:
        return False
    return target in ALLOWED_TRANSITIONS.get(current, set())
