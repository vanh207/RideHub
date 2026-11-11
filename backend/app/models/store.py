from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.session import Base

class Store(Base):
    __tablename__ = "stores"

    id = Column(Integer, primary_key=True, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(200))
    address = Column(Text)
    city = Column(String(100))
    business_license = Column(String(100), nullable=True)
    bank_account_info = Column(Text, nullable=True)
    
    # Trạng thái duyệt
    status = Column(String(30), default="pending")
    reject_reason = Column(Text, nullable=True)
    approved_by = Column(Integer, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    owner = relationship("User", back_populates="stores")