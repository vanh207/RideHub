from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class FAQBase(BaseModel):
    category: str = Field(..., max_length=50, description="Danh mục: ekyc, deposit, delivery, emergency, cancel, price...")
    category_name: str = Field(..., max_length=100, description="Tên danh mục hiển thị")
    question: str = Field(..., max_length=500, description="Câu hỏi thường gặp")
    answer: str = Field(..., description="Nội dung câu trả lời / chính sách giải đáp chi tiết")
    display_order: int = Field(0, description="Thứ tự hiển thị ưu tiên")
    is_active: bool = Field(True, description="Trạng thái kích hoạt")

class FAQCreate(FAQBase):
    pass

class FAQUpdate(BaseModel):
    category: Optional[str] = Field(None, max_length=50)
    category_name: Optional[str] = Field(None, max_length=100)
    question: Optional[str] = Field(None, max_length=500)
    answer: Optional[str] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None

class FAQResponse(FAQBase):
    id: int
    view_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

