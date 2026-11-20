"""Ghi lại lịch sử chuyển trạng thái của đơn đặt xe."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.core.booking_status import normalize_status
from app.models.booking import Booking, BookingStatusHistory


def record_booking_status_change(
    db: Session,
    booking: Booking,
    from_status: Optional[str],
    to_status: Optional[str],
    *,
    changed_by: str,
    changed_by_user_id: Optional[int] = None,
    reason: Optional[str] = None,
    created_at: Optional[datetime] = None,
) -> Optional[BookingStatusHistory]:
    old_status = normalize_status(from_status)
    new_status = normalize_status(to_status)
    if not new_status or old_status == new_status:
        return None

    row = BookingStatusHistory(
        booking_id=booking.id,
        from_status=old_status,
        to_status=new_status,
        changed_by=(changed_by or "SYSTEM").strip().upper()[:30],
        changed_by_user_id=changed_by_user_id,
        reason=reason,
        created_at=created_at or datetime.now(),
    )
    db.add(row)
    db.flush()
    return row
