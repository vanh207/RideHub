from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, Integer, String, TIMESTAMP
from sqlalchemy.sql import func

from app.db.session import Base


class VehicleSchedule(Base):
    """Time blocks that make a vehicle unavailable for rental."""

    __tablename__ = "vehicle_schedules"

    __table_args__ = (
        CheckConstraint("start_time < end_time", name="ck_schedule_time_range"),
        Index(
            "ix_schedules_vehicle_time",
            "vehicle_id",
            "start_time",
            "end_time",
        ),
        Index(
            "ix_schedules_vehicle_status_time",
            "vehicle_id",
            "status",
            "start_time",
            "end_time",
        ),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False)
    booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="SET NULL"), nullable=True)
    reservation_id = Column(
        Integer,
        ForeignKey("vehicle_reservations.id", ondelete="SET NULL"),
        nullable=True,
    )
    schedule_type = Column(String(20), nullable=False, default="RENTAL")
    start_time = Column(TIMESTAMP, nullable=False)
    end_time = Column(TIMESTAMP, nullable=False)
    status = Column(String(20), nullable=False, default="ACTIVE")
    note = Column(String(500), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
