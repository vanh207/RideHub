from sqlalchemy import Column, Integer, Numeric, String, TIMESTAMP, ForeignKey, Text, JSON
from sqlalchemy.sql import func
from app.db.session import Base

class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False)
    transaction_code = Column(String(100), unique=True, nullable=False)
    provider = Column(String(50), nullable=False)
    provider_txn_id = Column(String(150), nullable=True)
    amount = Column(Numeric(12, 2), nullable=False)
    status = Column(String(30), default='PENDING')
    payment_method = Column(String(50), nullable=True)
    qr_code_url = Column(String(500), nullable=True)
    paid_at = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())


class Refund(Base):
    __tablename__ = "refunds"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False)
    payment_transaction_id = Column(Integer, ForeignKey("payment_transactions.id", ondelete="SET NULL"), nullable=True)
    amount = Column(Numeric(12, 2), nullable=False)
    reason = Column(Text, nullable=True)
    status = Column(String(30), default='PENDING')
    processed_by = Column(Integer, nullable=True)
    processed_at = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())


class PaymentWebhookLog(Base):
    __tablename__ = "payment_webhook_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    provider_txn_id = Column(String(150), nullable=True)
    transaction_code = Column(String(100), nullable=True)
    payload = Column(JSON, nullable=True)
    signature_valid = Column(String(10), nullable=True)
    process_result = Column(String(50), nullable=True)
    queue_reason = Column(Text, nullable=True)
    processed_at = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())