from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.session import Base

class DriverLicense(Base):
    __tablename__ = "driver_licenses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    license_class = Column(String(10)) # VD: A1, B2
    license_number = Column(String(50), unique=True, index=True)
    image_url = Column(String(500))
    issued_date = Column(Date)
    expiry_date = Column(Date)
    
    # Trạng thái duyệt
    status = Column(String(30), default="pending") 
    reject_reason = Column(Text, nullable=True)
    verified_by = Column(Integer, nullable=True)
    verified_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="driver_licenses")