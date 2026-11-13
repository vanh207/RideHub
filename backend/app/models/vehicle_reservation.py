from datetime import datetime, timedelta

from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, Integer, String, TIMESTAMP
from sqlalchemy.sql import func

from app.db.session import Base


def reservation_expiry() -> datetime:
    return datetime.utcnow() + timedelta(minutes=30)


class VehicleReservation(Base):
    """Temporary hold on a vehicle before a rental order is confirmed."""

    __tablename__ = "vehicle_reservations"

    __table_args__ = (
        CheckConstraint("start_time < end_time", name="ck_reservation_time_range"),
        Index(
            "ix_reservations_vehicle_time",
            "vehicle_id",
            "start_time",
            "end_time",
        ),
        Index(
            "ix_reservations_vehicle_status_expiry",
            "vehicle_id",
            "status",
            "expires_at",
        ),
        Index("ix_reservations_status_expiry", "status", "expires_at"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False)
    customer_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="SET NULL"), nullable=True)
    start_time = Column(TIMESTAMP, nullable=False)
    end_time = Column(TIMESTAMP, nullable=False)
    expires_at = Column(TIMESTAMP, nullable=False, default=reservation_expiry)
    status = Column(String(20), nullable=False, default="ACTIVE")
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
