"""Model lưu trữ Biên bản Giao/Nhận xe & File đính kèm (Ảnh xe, Ảnh biên bản ký)."""
from enum import Enum
from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    TIMESTAMP,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.session import Base


class ProtocolType(str, Enum):
    CHECK_OUT = "CHECK_OUT"
    CHECK_IN = "CHECK_IN"


class HandoverStatus(str, Enum):
    DRAFT = "DRAFT"
    COMPLETED = "COMPLETED"


class MediaType(str, Enum):
    VEHICLE_PHOTO = "VEHICLE_PHOTO"       # Ảnh xe đa góc lúc giao / nhận
    SIGNED_DOCUMENT = "SIGNED_DOCUMENT"   # Ảnh biên bản giấy đã ký tay của 2 bên
    DAMAGE_PHOTO = "DAMAGE_PHOTO"         # Ảnh chi tiết vết xước / hư hại


class SignerRole(str, Enum):
    CUSTOMER = "CUSTOMER"
    STAFF = "STAFF"


class HandoverProtocol(Base):
    """Biên bản giao/nhận xe điện tử.
    
    Quy tắc nghiệp vụ:
    - Giao xe: tạo 1 bản ghi với protocol_type = 'CHECK_OUT'.
    - Trả xe: tạo 1 bản ghi RIÊNG với protocol_type = 'CHECK_IN', không ghi đè CHECK_OUT.
    - Biên bản chỉ chuyển COMPLETED khi cả 2 bên (customer và staff) đều đã ký.
    """

    __tablename__ = "handover_protocols"
    __table_args__ = (
        UniqueConstraint("protocol_code", name="uq_handover_protocol_code"),
        Index("ix_handover_booking_type", "booking_id", "protocol_type"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    protocol_code = Column(String(50), unique=True, index=True, nullable=False)
    booking_id = Column(Integer, index=True, nullable=False)
    protocol_type = Column(String(20), default=ProtocolType.CHECK_OUT.value, nullable=False)

    # Người thực hiện bàn giao
    store_agent_id = Column(Integer, nullable=True)   # user_id của nhân viên / chủ cửa hàng
    store_agent_name = Column(String(100), nullable=False)
    store_agent_phone = Column(String(20), nullable=True)
    customer_id = Column(Integer, nullable=True)      # user_id của khách
    customer_name = Column(String(100), nullable=False)
    customer_cccd = Column(String(20), nullable=False)
    customer_phone = Column(String(20), nullable=False)
    customer_license = Column(String(50), nullable=False)
    handover_location = Column(String(255), nullable=False)

    # Thông tin xe
    vehicle_id = Column(Integer, nullable=True)
    vehicle_name = Column(String(150), nullable=False)
    license_plate = Column(String(20), nullable=False)
    vehicle_category = Column(String(20), default="CAR", nullable=False)

    # Vận hành & Nhiên liệu
    odo_checkout = Column(Integer, default=0, nullable=False)
    odo_checkin = Column(Integer, nullable=True)
    fuel_checkout = Column(String(20), default="FULL", nullable=False)   # FULL | 3/4 | 1/2 | 1/4 | EMPTY
    fuel_checkin = Column(String(20), nullable=True)
    free_km_limit = Column(Integer, default=0, nullable=False)          # Giới hạn km miễn phí

    # Sơ đồ tổn hại & Checklist (JSON)
    damage_points = Column(JSON, nullable=True)   # [{x, y, label, color}]
    checklist_data = Column(JSON, nullable=True)  # [{item, ok, note}]

    # Quyết toán cọc & Tài sản thế chấp
    deposit_type = Column(String(30), default="CASH", nullable=False)  # CASH | VEHICLE_PLEDGE
    collateral_info = Column(Text, nullable=True)                       # Xe & giấy tờ thế chấp (khi chọn cắm xe)
    collateral_status = Column(String(30), nullable=True)               # HELD (Đang giữ) | RETURNED (Đã trả)
    deposit_original = Column(Numeric(12, 2), default=0, nullable=False)
    fee_overtime = Column(Numeric(12, 2), default=0, nullable=False)
    fee_excess_km = Column(Numeric(12, 2), default=0, nullable=False)
    fee_fuel = Column(Numeric(12, 2), default=0, nullable=False)
    fee_cleaning = Column(Numeric(12, 2), default=0, nullable=False)
    fee_damage = Column(Numeric(12, 2), default=0, nullable=False)
    hold_fine_deposit = Column(Numeric(12, 2), default=0, nullable=False)
    refund_immediate = Column(Numeric(12, 2), default=0, nullable=False)

    # Chữ ký số (Base64 PNG hoặc URL đã upload)
    customer_signature = Column(Text, nullable=True)
    staff_signature = Column(Text, nullable=True)
    signed_at = Column(TIMESTAMP, nullable=True)

    # Xác nhận ảnh của hai bên (Photo confirmation)
    customer_confirmed = Column(Boolean, default=False, nullable=False)
    customer_confirmed_at = Column(TIMESTAMP, nullable=True)
    customer_confirm_note = Column(String(255), nullable=True)

    staff_confirmed = Column(Boolean, default=False, nullable=False)
    staff_confirmed_at = Column(TIMESTAMP, nullable=True)
    staff_confirm_note = Column(String(255), nullable=True)

    both_confirmed = Column(Boolean, default=False, nullable=False)
    both_confirmed_at = Column(TIMESTAMP, nullable=True)

    status = Column(String(30), default=HandoverStatus.DRAFT.value, nullable=False)
    notes = Column(Text, nullable=True)

    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    # Relationships
    media = relationship(
        "HandoverMedia",
        back_populates="protocol",
        cascade="all, delete-orphan",
        order_by="HandoverMedia.sort_order",
    )


class HandoverMedia(Base):
    """Lưu tất cả file ảnh đính kèm biên bản: ảnh xe 360°, ảnh biên bản đã ký."""

    __tablename__ = "handover_media"
    __table_args__ = (
        Index("ix_handover_media_protocol_type", "protocol_id", "media_type"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    protocol_id = Column(
        Integer,
        ForeignKey("handover_protocols.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    media_type = Column(String(30), nullable=False)   # VEHICLE_PHOTO | SIGNED_DOCUMENT | DAMAGE_PHOTO
    file_url = Column(String(500), nullable=False)    # Đường dẫn file sau khi upload an toàn
    file_name = Column(String(255), nullable=True)    # Tên file gốc
    file_size = Column(Integer, nullable=True)        # Byte
    mime_type = Column(String(80), nullable=True)     # image/jpeg, image/png, ...
    caption = Column(String(255), nullable=True)      # Chú thích ảnh
    sort_order = Column(Integer, default=0, nullable=False)
    is_primary = Column(Boolean, default=False, nullable=False)

    uploaded_by_id = Column(Integer, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    protocol = relationship("HandoverProtocol", back_populates="media")
