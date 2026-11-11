from sqlalchemy import Column, Integer, Numeric, String, TIMESTAMP, ForeignKey
from sqlalchemy.sql import func
from app.db.session import Base

class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    customer_id = Column(Integer, nullable=False) # Liên kết tới bảng users/customers
    vehicle_id = Column(Integer, nullable=False)  # Liên kết tới bảng vehicles
    store_id = Column(Integer, nullable=True)
    delivery_point_id = Column(Integer, nullable=True)
    start_time = Column(TIMESTAMP, nullable=False)
    end_time = Column(TIMESTAMP, nullable=False)
    hold_expires_at = Column(TIMESTAMP, nullable=True)
    status = Column(String(40), default='PENDING')
    rental_amount = Column(Numeric(12, 2), nullable=False)
    delivery_fee = Column(Numeric(12, 2), default=0)
    deposit_amount = Column(Numeric(12, 2), default=0)
    total_amount = Column(Numeric(12, 2), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())