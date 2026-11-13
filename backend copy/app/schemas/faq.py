from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class FAQBase(BaseModel):
    category: str = Field(..., max_length=50)
    category_name: str = Field(..., max_length=100)
    question: str = Field(..., max_length=500)
    answer: str
    display_order: int = 0
    is_active: bool = True

class FAQCreate(FAQBase):
    pass

class FAQResponse(FAQBase):
    id: int
    view_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

