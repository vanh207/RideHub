from sqlalchemy import Column, Integer, Numeric, String, Text, TIMESTAMP, JSON
from sqlalchemy.sql import func
from app.db.session import Base

class HandoverProtocol(Base):
    __tablename__ = "handover_protocols"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    protocol_code = Column(String(50), unique=True, index=True, nullable=False)
    booking_id = Column(Integer, index=True, nullable=False)
    protocol_type = Column(String(20), default="CHECK_OUT", nullable=False)  # CHECK_OUT, CHECK_IN

    # Thông tin các bên
    store_agent_name = Column(String(100), nullable=False)
    store_agent_phone = Column(String(20), nullable=True)
    customer_name = Column(String(100), nullable=False)
    customer_cccd = Column(String(20), nullable=False)
    customer_phone = Column(String(20), nullable=False)
    customer_license = Column(String(50), nullable=False)
    handover_location = Column(String(255), nullable=False)

    # Thông tin xe
    vehicle_name = Column(String(150), nullable=False)
    license_plate = Column(String(20), nullable=False)
    vehicle_category = Column(String(20), default="CAR", nullable=False)

    # Vận hành & Nhiên liệu
    odo_checkout = Column(Integer, default=0, nullable=False)
    odo_checkin = Column(Integer, nullable=True)
    fuel_checkout = Column(String(20), default="FULL", nullable=False)
    fuel_checkin = Column(String(20), nullable=True)

    # Tổn hại & Kiểm tra (JSON)
    damage_points = Column(JSON, nullable=True)
    checklist_data = Column(JSON, nullable=True)

    # Quyết toán cọc
    deposit_original = Column(Numeric(12, 2), default=0, nullable=False)
    fee_overtime = Column(Numeric(12, 2), default=0, nullable=False)
    fee_excess_km = Column(Numeric(12, 2), default=0, nullable=False)
    fee_fuel = Column(Numeric(12, 2), default=0, nullable=False)
    fee_cleaning = Column(Numeric(12, 2), default=0, nullable=False)
    fee_damage = Column(Numeric(12, 2), default=0, nullable=False)
    hold_fine_deposit = Column(Numeric(12, 2), default=0, nullable=False)
    refund_immediate = Column(Numeric(12, 2), default=0, nullable=False)

    # Chữ ký số điện tử (Base64 PNG hoặc URL)
    customer_signature = Column(Text, nullable=True)
    staff_signature = Column(Text, nullable=True)
    signed_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    status = Column(String(30), default="COMPLETED", nullable=False)
    notes = Column(Text, nullable=True)

    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

