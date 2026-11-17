from sqlalchemy import Column, ForeignKey, Index, Integer, String, Text, DateTime, func
from sqlalchemy.orm import relationship, synonym
from app.db.session import Base

class Store(Base):
    __tablename__ = "stores"
    __table_args__ = (
        Index("ix_stores_owner_id_status", "owner_user_id", "status"),
        Index("ix_stores_status", "status"),
        Index("uq_stores_business_license_number", "business_license", unique=True),
        Index("uq_stores_email", "email", unique=True),
        Index("uq_stores_name", "name", unique=True),
    )

    id = Column(Integer, primary_key=True, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    owner_id = synonym("owner_user_id")
    name = Column(String(200))
    description = Column(Text, nullable=True)
    phone = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    address = Column(Text)
    city = Column(String(100))
    district = Column(String(100), nullable=True)
    ward = Column(String(100), nullable=True)
    address_detail = Column(Text, nullable=True)
    business_license = Column(String(100), nullable=True)
    business_license_number = synonym("business_license")
    business_license_file = Column(String(255), nullable=True)
    logo_file = Column(String(255), nullable=True)
    bank_account_info = Column(Text, nullable=True)
    
    # Trạng thái duyệt
    status = Column(String(30), default="PENDING", server_default="PENDING", nullable=False)
    reject_reason = Column(Text, nullable=True)
    approved_by = Column(Integer, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    owner = relationship("User", back_populates="stores")


# quản lý nhân viên cửa hàng
class StoreStaff(Base):
    __tablename__ = "store_staff"
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, nullable=False)
    user_id = Column(Integer, nullable=False)
    staff_role = Column(String(30), default="STAFF")
    status = Column(String(30), default="ACTIVE")