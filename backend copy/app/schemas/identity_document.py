from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime

class IdentityDocumentBase(BaseModel):
    document_type: str
    document_number: str
    front_image_url: str
    back_image_url: str
    issued_date: date
    expiry_date: Optional[date] = None

class IdentityDocumentCreate(IdentityDocumentBase):
    user_id: int

class IdentityDocumentResponse(IdentityDocumentBase):
    id: int
    user_id: int
    status: str
    reject_reason: Optional[str] = None
    verified_by: Optional[int] = None
    verified_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True