from pydantic import BaseModel, Field
from typing import Optional, Any, List
from datetime import datetime

class ChatMessageRequest(BaseModel):
    session_id: str = Field(..., max_length=100)
    message: str = Field(..., min_length=1)
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None

class ChatMessageResponse(BaseModel):
    sender: str
    message: str
    detected_intent: Optional[str] = None
    payload: Optional[Any] = None
    is_escalated: bool = False
    assigned_agent: Optional[str] = None

