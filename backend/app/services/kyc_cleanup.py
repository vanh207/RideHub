"""Dọn dữ liệu eKYC hết hạn theo chính sách lưu trữ."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.audit_log import AuditLog
from app.models.identity_document import IdentityDocument
from app.models.kyc_session import KycSession
from app.services.kyc_file_store import KycFileStore, kyc_file_store

logger = logging.getLogger("ridehub.kyc_cleanup")


@dataclass
class KycCleanupResult:
    face_sessions: int = 0
    deleted_sessions: int = 0
    deleted_documents: int = 0
    deleted_files: int = 0

    @property
    def total(self) -> int:
        return (
            self.face_sessions
            + self.deleted_sessions
            + self.deleted_documents
            + self.deleted_files
        )


def _audit(
    db: Session,
    now: datetime,
    action: str,
    resource_type: str,
    resource_id: int,
    description: str,
) -> None:
    db.add(
        AuditLog(
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id),
            http_method="SYSTEM",
            endpoint="job:kyc_cleanup",
            description=description,
            status_code=200,
            status="SUCCESS",
            created_at=now,
        )
    )


def _delete_files(store: KycFileStore, paths: set[str], result: KycCleanupResult) -> None:
    for path in sorted(item for item in paths if item):
        try:
            if store.delete(path):
                result.deleted_files += 1
        except Exception:
            logger.warning("Không xóa được ảnh eKYC đã hết hạn: %s", path)


def _cleanup_faces(
    db: Session,
    now: datetime,
    cutoff: datetime,
    store: KycFileStore,
    result: KycCleanupResult,
) -> None:
    sessions = db.scalars(
        select(KycSession)
        .where(func.coalesce(KycSession.expires_at, KycSession.created_at) <= cutoff)
        .limit(settings.KYC_CLEANUP_BATCH_SIZE)
    ).all()
    if not sessions:
        return

    document_ids = {
        session.identity_document_id
        for session in sessions
        if session.identity_document_id is not None
    }
    documents: dict[int, IdentityDocument] = {}
    if document_ids:
        linked = db.scalars(
            select(IdentityDocument).where(IdentityDocument.id.in_(document_ids))
        ).all()
        documents = {document.id: document for document in linked}

    paths: set[str] = set()
    for session in sessions:
        if session.selfie_path:
            paths.add(session.selfie_path)
            session.selfie_path = None
            result.face_sessions += 1
            _audit(
                db,
                now,
                "KYC_CLEANUP_FACE",
                "kyc_session",
                session.id,
                "Đã xóa ảnh khuôn mặt theo chính sách lưu trữ.",
            )
        document = documents.get(session.identity_document_id)
        if document and document.selfie_path:
            paths.add(document.selfie_path)
            document.selfie_path = None

    db.commit()
    _delete_files(store, paths, result)


def _cleanup_ids(
    db: Session,
    now: datetime,
    cutoff: datetime,
    store: KycFileStore,
    result: KycCleanupResult,
) -> None:
    sessions = db.scalars(
        select(KycSession)
        .where(KycSession.created_at <= cutoff)
        .limit(settings.KYC_CLEANUP_BATCH_SIZE)
    ).all()
    documents = db.scalars(
        select(IdentityDocument)
        .where(IdentityDocument.created_at <= cutoff)
        .limit(settings.KYC_CLEANUP_BATCH_SIZE)
    ).all()

    linked_ids = {
        session.identity_document_id
        for session in sessions
        if session.identity_document_id is not None
    }
    if linked_ids:
        linked = db.scalars(
            select(IdentityDocument).where(IdentityDocument.id.in_(linked_ids))
        ).all()
        documents.extend(document for document in linked if document not in documents)

    if not sessions and not documents:
        return

    paths: set[str] = set()
    for session in sessions:
        paths.update(
            path
            for path in (session.front_path, session.back_path, session.selfie_path)
            if path
        )
        result.deleted_sessions += 1
        _audit(
            db,
            now,
            "KYC_CLEANUP_DELETE",
            "kyc_session",
            session.id,
            "Đã xóa phiên eKYC theo chính sách lưu trữ.",
        )
        db.delete(session)

    for document in documents:
        paths.update(
            path
            for path in (
                document.front_image_url,
                document.back_image_url,
                document.selfie_path,
            )
            if path
        )
        result.deleted_documents += 1
        _audit(
            db,
            now,
            "KYC_CLEANUP_DELETE",
            "identity_document",
            document.id,
            "Đã xóa hồ sơ định danh theo chính sách lưu trữ.",
        )
        db.delete(document)

    db.commit()
    _delete_files(store, paths, result)


def cleanup_expired_kyc(
    db: Session,
    now: Optional[datetime] = None,
    store: Optional[KycFileStore] = None,
) -> KycCleanupResult:
    """Xóa ảnh mặt sau 30 ngày và toàn bộ hồ sơ sau 180 ngày."""
    current = now or datetime.now()
    active_store = store or kyc_file_store
    result = KycCleanupResult()

    _cleanup_faces(
        db,
        current,
        current - timedelta(days=settings.KYC_FACE_RETENTION_DAYS),
        active_store,
        result,
    )
    _cleanup_ids(
        db,
        current,
        current - timedelta(days=settings.KYC_ID_RETENTION_DAYS),
        active_store,
        result,
    )
    return result
