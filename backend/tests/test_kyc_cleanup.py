"""Test job dọn dữ liệu eKYC hết hạn."""
from datetime import datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.db.session import Base
from app.models.audit_log import AuditLog
from app.models.identity_document import IdentityDocument
from app.models.kyc_session import KycSession
from app.models.user import User
from app.services.kyc_cleanup import cleanup_expired_kyc
from app.services.kyc_file_store import LocalKycFileStore


def test_cleanup_removes_expired_assets_and_keeps_recent(tmp_path):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    store = LocalKycFileStore(root=tmp_path)
    now = datetime.now()

    db.add(User(id=8202, phone="0900000002", status="active"))

    old_face = store.save("selfie", b"old-face", ".jpg")
    old_front = store.save("front", b"old-front", ".jpg")
    old_session = KycSession(
        user_id=8202,
        status="APPROVED",
        front_path=old_front,
        selfie_path=old_face,
        created_at=now - timedelta(days=181),
        expires_at=now - timedelta(days=31),
    )
    db.add(old_session)
    db.flush()

    old_id_front = store.save("front", b"old-id-front", ".jpg")
    old_id_selfie = store.save("selfie", b"old-id-selfie", ".jpg")
    document = IdentityDocument(
        user_id=8202,
        document_type="CCCD",
        document_number="001230000002",
        status="approved",
        front_image_url=old_id_front,
        selfie_path=old_id_selfie,
        created_at=now - timedelta(days=181),
    )
    db.add(document)
    db.flush()
    old_session.identity_document_id = document.id

    recent_selfie = store.save("selfie", b"recent-face", ".jpg")
    recent_session = KycSession(
        user_id=8202,
        status="SUBMITTED",
        selfie_path=recent_selfie,
        expires_at=now - timedelta(days=1),
    )
    db.add(recent_session)
    db.commit()

    result = cleanup_expired_kyc(db, now=now, store=store)

    assert result.face_sessions == 1
    assert result.deleted_sessions == 1
    assert result.deleted_documents == 1
    assert result.deleted_files == 4
    assert not store.exists(old_face)
    assert not store.exists(old_front)
    assert not store.exists(old_id_front)
    assert not store.exists(old_id_selfie)
    assert store.exists(recent_selfie)
    assert db.get(KycSession, old_session.id) is None
    assert db.get(IdentityDocument, document.id) is None
    assert db.get(KycSession, recent_session.id) is not None

    actions = {row.action for row in db.scalars(select(AuditLog)).all()}
    assert "KYC_CLEANUP_FACE" in actions
    assert "KYC_CLEANUP_DELETE" in actions

    db.close()
    engine.dispose()
