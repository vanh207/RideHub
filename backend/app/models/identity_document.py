from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.session import Base

class IdentityDocument(Base):
    __tablename__ = "identity_documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    document_type = Column(String(30)) # VD: CCCD, CMND, Passport
    document_number = Column(String(50), unique=True, index=True)
    front_image_url = Column(String(500))
    back_image_url = Column(String(500))
    issued_date = Column(Date)
    expiry_date = Column(Date)
    
    # Trạng thái duyệt
    status = Column(String(30), default="pending") # pending, approved, rejected
    reject_reason = Column(Text, nullable=True)
    verified_by = Column(Integer, nullable=True) # ID của admin duyệt
    verified_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="identity_documents")