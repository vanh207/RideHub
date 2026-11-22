from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    TIMESTAMP,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from app.db.session import Base


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_reviews_rating"),
        UniqueConstraint("booking_id", "reviewer_id", name="uq_reviews_booking_reviewer"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False)
    reviewer_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), nullable=False)


class Complaint(Base):
    __tablename__ = "complaints"
    __table_args__ = (
        CheckConstraint(
            "status IN ('OPEN', 'IN_PROGRESS', 'WAITING_FOR_CUSTOMER', "
            "'RESOLVED', 'REJECTED', 'CLOSED')",
            name="ck_complaints_status",
        ),
        CheckConstraint(
            "priority IN ('NORMAL', 'HIGH', 'URGENT')",
            name="ck_complaints_priority",
        ),
        Index("ix_complaints_status_created_at", "status", "created_at"),
        Index("ix_complaints_booking_id", "booking_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False)
    reporter_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    against_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    category = Column(String(50), nullable=False)
    subject = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String(30), nullable=False, default="OPEN", server_default="OPEN")
    priority = Column(String(20), nullable=False, default="NORMAL", server_default="NORMAL")
    assigned_to = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolution = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), nullable=False)
    updated_at = Column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )
    resolved_at = Column(TIMESTAMP, nullable=True)


class ComplaintEvidence(Base):
    __tablename__ = "complaint_evidence"
    __table_args__ = (
        Index("ix_complaint_evidence_complaint_id", "complaint_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    complaint_id = Column(
        Integer, ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False
    )
    uploaded_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    image_url = Column(String(500), nullable=False)
    caption = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), nullable=False)


class ComplaintStatusHistory(Base):
    __tablename__ = "complaint_status_histories"
    __table_args__ = (
        CheckConstraint(
            "to_status IN ('OPEN', 'IN_PROGRESS', 'WAITING_FOR_CUSTOMER', "
            "'RESOLVED', 'REJECTED', 'CLOSED')",
            name="ck_complaint_status_histories_to_status",
        ),
        CheckConstraint(
            "from_status IS NULL OR from_status IN "
            "('OPEN', 'IN_PROGRESS', 'WAITING_FOR_CUSTOMER', "
            "'RESOLVED', 'REJECTED', 'CLOSED')",
            name="ck_complaint_status_histories_from_status",
        ),
        Index(
            "ix_complaint_status_histories_complaint_created",
            "complaint_id",
            "created_at",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    complaint_id = Column(
        Integer, ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False
    )
    from_status = Column(String(30), nullable=True)
    to_status = Column(String(30), nullable=False)
    changed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), nullable=False)
