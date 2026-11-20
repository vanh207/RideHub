from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    TIMESTAMP,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base


class Booking(Base):
    __tablename__ = "bookings"

    __table_args__ = (
        CheckConstraint("start_time < end_time", name="ck_booking_time_range"),
        CheckConstraint("rental_amount >= 0", name="ck_booking_rental_amount"),
        CheckConstraint("delivery_fee >= 0", name="ck_booking_delivery_fee"),
        CheckConstraint("deposit_amount >= 0", name="ck_booking_deposit_amount"),
        CheckConstraint("total_amount >= 0", name="ck_booking_total_amount"),
        Index("ix_bookings_vehicle_time", "vehicle_id", "start_time", "end_time"),
        Index(
            "ix_bookings_vehicle_status_time",
            "vehicle_id",
            "status",
            "start_time",
            "end_time",
        ),
        Index("ix_bookings_status_hold_expires", "status", "hold_expires_at"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=True)
    delivery_point_id = Column(Integer, ForeignKey("delivery_points.id"), nullable=True)
    start_time = Column(TIMESTAMP, nullable=False)
    end_time = Column(TIMESTAMP, nullable=False)
    hold_expires_at = Column(TIMESTAMP, nullable=True)
    status = Column(String(40), default='PENDING')
    rental_amount = Column(Numeric(12, 2), nullable=False)
    delivery_fee = Column(Numeric(12, 2), default=0)
    deposit_amount = Column(Numeric(12, 2), default=0)
    total_amount = Column(Numeric(12, 2), nullable=False)
    cancelled_at = Column(TIMESTAMP, nullable=True)
    cancelled_by = Column(String(30), nullable=True)
    cancel_reason = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    status_histories = relationship(
        "BookingStatusHistory",
        back_populates="booking",
        cascade="all, delete-orphan",
        order_by="BookingStatusHistory.created_at",
    )


class BookingStatusHistory(Base):
    __tablename__ = "booking_status_history"

    __table_args__ = (
        Index("ix_booking_status_history_booking_created", "booking_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    booking_id = Column(
        Integer,
        ForeignKey("bookings.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_status = Column(String(40), nullable=True)
    to_status = Column(String(40), nullable=False)
    changed_by = Column(String(30), nullable=False)
    changed_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reason = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.current_timestamp())

    booking = relationship("Booking", back_populates="status_histories")