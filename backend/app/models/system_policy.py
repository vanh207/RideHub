"""Mô hình dữ liệu Cấu hình Chính sách Hệ thống (SystemPolicy)."""
from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.db.session import Base


class SystemPolicy(Base):
    """Bảng lưu trữ các tham số chính sách vận hành, đặt cọc, hủy đơn và bảo mật."""
    __tablename__ = "system_policies"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    policy_key = Column(String(100), unique=True, nullable=False, index=True)
    category = Column(String(50), nullable=False, index=True)  # DEPOSIT, CANCELLATION, BOOKING, SECURITY
    label = Column(String(200), nullable=False)
    value = Column(String(255), nullable=False)
    value_type = Column(String(20), nullable=False, default="number")  # number, percent, text, boolean
    unit = Column(String(30), nullable=True)
    description = Column(Text, nullable=True)
    updated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), default=datetime.now)

    updater = relationship("User")
