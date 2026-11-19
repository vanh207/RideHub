from sqlalchemy import Column, Integer, String, Text, Date, DateTime, func
from sqlalchemy.orm import relationship
from app.db.session import Base 

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    firebase_uid = Column(String(128), unique=True, index=True)
    phone = Column(String(15), unique=True, index=True)
    email = Column(String(150), unique=True, index=True)
    hashed_password = Column(String(255), nullable=True)
    full_name = Column(String(150))
    date_of_birth = Column(Date)
    address = Column(Text)
    avatar_url = Column(String(500))
    status = Column(String(30), default="active")
    last_login_at = Column(DateTime)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    user_roles = relationship("UserRole", back_populates="user", cascade="all, delete-orphan", lazy="joined")
    identity_documents = relationship("IdentityDocument", back_populates="user")
    driver_licenses = relationship("DriverLicense", back_populates="user")
    stores = relationship("Store", back_populates="owner")
    audit_logs = relationship("AuditLog", back_populates="user")

    @property
    def role(self) -> str:
        """Lấy mã role đầu tiên từ bảng user_roles (VD: 'customer', 'admin')."""
        if self.user_roles:
            for ur in self.user_roles:
                if ur.role and ur.role.code:
                    return ur.role.code.lower()
        return "customer"

    @property
    def roles_list(self) -> list[str]:
        """Danh sách tất cả mã role của người dùng."""
        return [ur.role.code.lower() for ur in self.user_roles if ur.role and ur.role.code]
