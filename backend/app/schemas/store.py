from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class StoreBase(BaseModel):
    name: str
    address: str
    city: str
    business_license: Optional[str] = None
    bank_account_info: Optional[str] = None

class StoreCreate(StoreBase):
    owner_user_id: int

class StoreResponse(StoreBase):
    id: int
    owner_user_id: int
    status: str
    reject_reason: Optional[str] = None
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True