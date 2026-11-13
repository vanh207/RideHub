
from sqlalchemy import Column, Integer, Numeric, String, Text, Boolean, TIMESTAMP, UniqueConstraint, ForeignKey
from sqlalchemy.sql import func
from app.db.session import Base


class Vehicle(Base):
    __tablename__ = "vehicles"

    __table_args__ = (
        UniqueConstraint("store_id", "plate_number", name="uq_vehicle_store_plate"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    store_id = Column(Integer, nullable=False)

    vehicle_type = Column(String(30), nullable=False)
    plate_number = Column(String(20), nullable=False)
    brand = Column(String(100), nullable=False)
    model = Column(String(100), nullable=False)

    year_of_manufacture = Column(Integer, nullable=True)
    engine_capacity = Column(Integer, nullable=True)
    transmission_type = Column(String(30), nullable=True)
    seats = Column(Integer, nullable=True)
    body_type = Column(String(50), nullable=True)
    fuel_type = Column(String(30), nullable=True)

    price_per_day = Column(Numeric(12, 2), nullable=False)
    price_per_hour = Column(Numeric(12, 2), nullable=True)

    current_status = Column(String(40), default="AVAILABLE")
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)

    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp()
    )


class VehicleImage(Base):
    __tablename__ = "vehicle_images"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    vehicle_id = Column(
        Integer,
        ForeignKey("vehicles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    image_url = Column(String(500), nullable=False)
    is_primary = Column(Boolean, default=False)
    sort_order = Column(Integer, nullable=True)

    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
