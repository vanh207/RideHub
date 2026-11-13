
from sqlalchemy import Column, Integer, Numeric, String, Boolean, TIMESTAMP, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from app.db.session import Base

class DeliveryFeeZone(Base):
    __tablename__ = "delivery_fee_zones"
    __table_args__ = (
        UniqueConstraint("store_id", "area", name="uq_delivery_zone_store_area"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    store_id = Column(Integer, nullable=False)
    area = Column(String(255), nullable=False)
    delivery_fee = Column(Numeric(12, 2), nullable=False)

    is_active = Column(Boolean, default=True)

    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp()
    )


class DeliveryPoint(Base):
    __tablename__ = "delivery_points"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    store_id = Column(Integer, nullable=False)

    delivery_fee_zone_id = Column(
        Integer,
        ForeignKey("delivery_fee_zones.id"),
        nullable=True
    )

    name = Column(String(255), nullable=False)
    address = Column(String(500), nullable=False)
    area = Column(String(255), nullable=True)
    delivery_fee = Column(Numeric(12, 2), default=0)

    is_active = Column(Boolean, default=True)

    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp()
    )
