
from sqlalchemy import Column, Integer, Numeric, String, Text, Boolean, TIMESTAMP, UniqueConstraint
from sqlalchemy.sql import func
from app.db.session import Base
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

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

class VehicleStatusHistory(Base):
    """Bảng Audit Log lưu vết lịch sử mọi lần đổi trạng thái của xe."""
    __tablename__ = "vehicle_status_history"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False, index=True)
    from_status = Column(String(40), nullable=True)       # Trạng thái trước đó
    to_status = Column(String(40), nullable=False)        # Trạng thái mới
    changed_by = Column(String(100), nullable=False)      # Tên nhân viên / Mã NV / SYSTEM
    reason = Column(String(255), nullable=True)           # Lý do chuyển trạng thái
    note = Column(Text, nullable=True)                    # Ghi chú chi tiết
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    # Khai báo quan hệ liên kết ngược với bảng xe
    vehicle = relationship("Vehicle", back_populates="status_histories")
    
Vehicle.status_histories = relationship("VehicleStatusHistory", back_populates="vehicle", cascade="all, delete-orphan")