from sqlalchemy import Column, Integer, String, Text, JSON, TIMESTAMP, Enum
from sqlalchemy.sql import func
from app.db.session import Base

class ChatConversation(Base):
    __tablename__ = "chat_conversations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String(100), unique=True, index=True, nullable=False)
    customer_name = Column(String(100), nullable=True)
    customer_phone = Column(String(20), nullable=True)
    status = Column(String(30), default="AI_ACTIVE", nullable=False)  # AI_ACTIVE, ESCALATED_TO_AGENT, CLOSED
    assigned_agent = Column(String(100), nullable=True)
    escalation_reason = Column(String(255), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String(100), index=True, nullable=False)
    sender = Column(String(20), nullable=False)  # USER, BOT, AGENT, SYSTEM
    message = Column(Text, nullable=False)
    detected_intent = Column(String(50), nullable=True)
    payload_json = Column(JSON, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

