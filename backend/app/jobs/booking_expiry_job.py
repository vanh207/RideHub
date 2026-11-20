"""Background job tự hủy các đơn hết hạn giữ chỗ."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from app.core.config import settings
from app.crud.booking_cancellation import expire_hold_bookings
from app.db.session import SessionLocal

logger = logging.getLogger("ridehub.booking_expiry_job")

_task: asyncio.Task | None = None
_stop_event: asyncio.Event | None = None


async def run_expiry_once(now: datetime | None = None) -> None:
    """Chạy một lượt quét, mở session riêng để dùng được trong job/tests."""
    with SessionLocal() as db:
        result = expire_hold_bookings(db, now=now)
    if result.scanned:
        logger.info(
            "Expiry job: scanned=%s expired=%s paid_race=%s skipped=%s",
            result.scanned,
            result.expired,
            result.paid_race,
            result.skipped,
        )


async def _worker(stop_event: asyncio.Event) -> None:
    interval = max(1, settings.BOOKING_EXPIRY_JOB_INTERVAL_SECONDS)
    while not stop_event.is_set():
        try:
            await run_expiry_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Lỗi khi chạy booking expiry job")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except TimeoutError:
            pass


async def start_expiry_job() -> None:
    global _task, _stop_event
    if not settings.BOOKING_EXPIRY_JOB_ENABLED:
        logger.info("Booking expiry job bị tắt qua cấu hình")
        return
    if _task is not None and not _task.done():
        return
    _stop_event = asyncio.Event()
    _task = asyncio.create_task(_worker(_stop_event))
    logger.info("Đã khởi động booking expiry job (mỗi %ss)", settings.BOOKING_EXPIRY_JOB_INTERVAL_SECONDS)


async def stop_expiry_job() -> None:
    global _task, _stop_event
    if _stop_event is not None:
        _stop_event.set()
    if _task is not None:
        try:
            await asyncio.wait_for(_task, timeout=5)
        except TimeoutError:
            _task.cancel()
        except asyncio.CancelledError:
            pass
    _task = None
    _stop_event = None
