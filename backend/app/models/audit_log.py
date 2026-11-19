"""Mô hình dữ liệu Nhật ký kiểm toán (Audit Log) cho RideHub.

Lưu vết toàn bộ các thao tác nhạy cảm:
- Ai (user_id, user_email, user_role, ip_address, user_agent)
- Làm gì (action, resource_type, resource_id, http_method, endpoint, payload, description)
- Lúc nào (created_at, execution_time_ms)
- Kết quả (status_code, status SUCCESS/FAILED, error_message)
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey, JSON, func
from sqlalchemy.orm import relationship

from app.db.session import Base


class AuditLog(Base):
    """Bảng lưu trữ vết kiểm toán (Audit Trail) của hệ thống."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # 1. AI (WHO)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    user_email = Column(String(150), nullable=True, index=True)
    user_role = Column(String(50), nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)

    # 2. LÀM GÌ (WHAT)
    action = Column(String(100), nullable=False, index=True)  # REVIEW_APPROVE, REVIEW_REJECT, VEHICLE_STATUS_CHANGE, PAYMENT_REFUND,...
    resource_type = Column(String(100), nullable=False, index=True)  # store, identity_document, driver_license, vehicle, booking, payment,...
    resource_id = Column(String(100), nullable=True, index=True)
    http_method = Column(String(10), nullable=False)
    endpoint = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    request_payload = Column(JSON, nullable=True)
    response_summary = Column(Text, nullable=True)

    # 3. KẾT QUẢ & HIỆU NĂNG
    status_code = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="SUCCESS")  # SUCCESS hoặc FAILED
    error_message = Column(Text, nullable=True)
    execution_time_ms = Column(Float, nullable=True)

    # 4. LÚC NÀO (WHEN)
    created_at = Column(DateTime, server_default=func.now(), default=datetime.now, nullable=False, index=True)

    # Liên kết hai chiều với bảng users
    user = relationship("User", back_populates="audit_logs")

    def __repr__(self) -> str:
        return (
            f"<AuditLog id={self.id} user={self.user_email or self.user_id} "
            f"action={self.action} resource={self.resource_type}:{self.resource_id} "
            f"status={self.status} at={self.created_at}>"
        )
