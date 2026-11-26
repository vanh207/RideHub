"""Mô hình dữ liệu Thông báo trong ứng dụng theo vai trò (Notification)."""
from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.db.session import Base


class Notification(Base):
    """Bảng lưu trữ thông báo theo từng role (customer, store_owner, admin) hoặc user cụ thể."""
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    role = Column(String(40), nullable=False, index=True)  # customer, store_owner, admin
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    type = Column(String(30), nullable=False, default="booking")  # booking, payment, alert, system
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    link = Column(String(255), nullable=True)
    is_read = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime, server_default=func.now(), default=datetime.now, index=True)

    user = relationship("User")
