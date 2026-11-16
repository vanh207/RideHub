"""Router quản lý Câu hỏi thường gặp FAQ (Module FAQ API)"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.faq import FAQ
from app.schemas.faq import FAQCreate, FAQResponse

router = APIRouter(prefix="/faqs", tags=["Frequently Asked Questions (FAQ)"])


@router.get("", response_model=List[FAQResponse])
def get_faqs(
    category: Optional[str] = Query(None, description="Lọc theo nhóm: ekyc, deposit, delivery, emergency, cancel"),
    q: Optional[str] = Query(None, description="Từ khóa tìm kiếm"),
    db: Session = Depends(get_db),
):
    """Lấy danh sách các câu hỏi thường gặp FAQ."""
    query = db.query(FAQ).filter(FAQ.is_active == True)
    if category and category != "all":
        query = query.filter(FAQ.category == category)
    if q:
        search_pattern = f"%{q}%"
        query = query.filter(
            (FAQ.question.ilike(search_pattern)) | (FAQ.answer.ilike(search_pattern))
        )
    return query.order_by(FAQ.display_order.asc(), FAQ.id.asc()).all()


@router.post("", response_model=FAQResponse, status_code=status.HTTP_201_CREATED)
def create_faq(
    payload: FAQCreate,
    db: Session = Depends(get_db),
):
    """Thêm một câu hỏi FAQ mới."""
    faq = FAQ(**payload.model_dump())
    db.add(faq)
    db.commit()
    db.refresh(faq)
    return faq

