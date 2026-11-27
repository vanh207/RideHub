"""Background job dọn dữ liệu eKYC theo chính sách lưu trữ."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.kyc_cleanup import cleanup_expired_kyc
from app.services.kyc_file_store import KycFileStore

logger = logging.getLogger("ridehub.kyc_cleanup_job")

_task: asyncio.Task | None = None
_stop_event: asyncio.Event | None = None


async def run_cleanup_once(
    now: datetime | None = None,
    db: Session | None = None,
    store: KycFileStore | None = None,
) -> None:
    """Chạy một lượt dọn; nhận db/store để test mà không đụng MySQL."""
    if db is not None:
        result = cleanup_expired_kyc(db, now=now, store=store)
    else:
        with SessionLocal() as session:
            result = cleanup_expired_kyc(session, now=now, store=store)
    if result.total:
        logger.info(
            "Kyc cleanup job: face=%s sessions=%s documents=%s files=%s",
            result.face_sessions,
            result.deleted_sessions,
            result.deleted_documents,
            result.deleted_files,
        )


async def _worker(stop_event: asyncio.Event) -> None:
    interval = max(1, settings.KYC_CLEANUP_JOB_INTERVAL_SECONDS)
    while not stop_event.is_set():
        try:
            await run_cleanup_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Lỗi khi chạy kyc cleanup job")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except TimeoutError:
            pass


async def start_cleanup_job() -> None:
    global _task, _stop_event
    if not settings.KYC_CLEANUP_JOB_ENABLED:
        logger.info("Kyc cleanup job bị tắt qua cấu hình")
        return
    if _task is not None and not _task.done():
        return
    _stop_event = asyncio.Event()
    _task = asyncio.create_task(_worker(_stop_event))
    logger.info(
        "Đã khởi động kyc cleanup job (mỗi %ss)",
        settings.KYC_CLEANUP_JOB_INTERVAL_SECONDS,
    )


async def stop_cleanup_job() -> None:
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
