"""Bảng phiên eKYC: lưu trạng thái, challenge, đường dẫn ảnh riêng và kết quả máy.

Không lưu ảnh/base64 trực tiếp trong bảng này; chỉ lưu đường dẫn tương đối do
KycFileStore cấp. Quyết định cuối cùng vẫn do admin duyệt.
"""
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Boolean,
    func,
)
from app.db.session import Base


class KycSession(Base):
    __tablename__ = "kyc_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(30), nullable=False, default="CREATED", index=True)

    challenge = Column(String(64), nullable=True)
    challenge_expires_at = Column(DateTime, nullable=True)

    attempt_count = Column(Integer, nullable=False, default=0)
    consent_version = Column(String(30), nullable=True)
    consented_at = Column(DateTime, nullable=True)
    consent_ip = Column(String(45), nullable=True)

    front_path = Column(String(500), nullable=True)
    back_path = Column(String(500), nullable=True)
    selfie_path = Column(String(500), nullable=True)

    qr_payload_hash = Column(String(64), nullable=True)
    qr_consistent = Column(Boolean, nullable=True)

    match_score = Column(Float, nullable=True)
    liveness_result = Column(String(30), nullable=True)
    provider = Column(String(30), nullable=True)
    flags = Column(JSON, nullable=False, default=list)

    identity_document_id = Column(
        Integer,
        ForeignKey("identity_documents.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
    expires_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_kyc_sessions_user_status", "user_id", "status"),
        Index("idx_kyc_sessions_expires_at", "expires_at"),
    )
