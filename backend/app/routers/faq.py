"""Router quản lý Câu hỏi thường gặp FAQ & Nội dung chính sách (Module FAQ API)
Hỗ trợ:
- Công khai: Tra cứu FAQ theo category, từ khóa.
- Admin (bảo vệ quyền Admin): Thêm, Sửa, Xóa FAQ và chính sách.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_admin
from app.db.session import get_db
from app.models.faq import FAQ
from app.models.user import User
from app.schemas.faq import FAQCreate, FAQResponse, FAQUpdate

router = APIRouter(prefix="/faqs", tags=["Frequently Asked Questions (FAQ) — Kho tri thức & Chính sách"])


@router.get("", response_model=List[FAQResponse], summary="Lấy danh sách các câu hỏi thường gặp FAQ (Công khai)")
def get_faqs(
    category: Optional[str] = Query(None, description="Lọc theo nhóm: ekyc, deposit, delivery, emergency, cancel, price..."),
    q: Optional[str] = Query(None, description="Từ khóa tìm kiếm"),
    include_inactive: bool = Query(False, description="Bao gồm cả các câu hỏi đã ẩn (dành cho Admin)"),
    db: Session = Depends(get_db),
):
    """Lấy danh sách các câu hỏi thường gặp FAQ và nội dung chính sách."""
    query = db.query(FAQ)
    if not include_inactive:
        query = query.filter(FAQ.is_active == True)
    if category and category != "all":
        query = query.filter(FAQ.category == category)
    if q:
        search_pattern = f"%{q}%"
        query = query.filter(
            (FAQ.question.ilike(search_pattern)) | (FAQ.answer.ilike(search_pattern))
        )
    return query.order_by(FAQ.display_order.asc(), FAQ.id.asc()).all()


@router.get("/{faq_id}", response_model=FAQResponse, summary="Chi tiết 1 câu hỏi FAQ")
def get_faq_detail(
    faq_id: int,
    db: Session = Depends(get_db),
):
    """Lấy chi tiết một câu hỏi FAQ theo ID."""
    faq = db.query(FAQ).filter(FAQ.id == faq_id).first()
    if not faq:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy câu hỏi FAQ #{faq_id}."
        )
    # Tăng view_count
    faq.view_count = (faq.view_count or 0) + 1
    db.commit()
    db.refresh(faq)
    return faq


@router.post("", response_model=FAQResponse, status_code=status.HTTP_201_CREATED, summary="[Admin] Thêm mới câu hỏi FAQ / chính sách")
def create_faq(
    payload: FAQCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    """Admin thêm một câu hỏi FAQ hoặc nội dung chính sách mới."""
    faq = FAQ(**payload.model_dump())
    db.add(faq)
    db.commit()
    db.refresh(faq)
    return faq


@router.put("/{faq_id}", response_model=FAQResponse, summary="[Admin] Sửa nội dung FAQ / chính sách trả lời")
def update_faq(
    faq_id: int,
    payload: FAQUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    """Admin cập nhật câu hỏi, câu trả lời, danh mục, thứ tự hiển thị hoặc trạng thái kích hoạt."""
    faq = db.query(FAQ).filter(FAQ.id == faq_id).first()
    if not faq:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy câu hỏi FAQ #{faq_id} để cập nhật."
        )

    update_data = payload.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(faq, field, val)

    db.commit()
    db.refresh(faq)
    return faq


@router.delete("/{faq_id}", status_code=status.HTTP_200_OK, summary="[Admin] Xóa câu hỏi FAQ")
def delete_faq(
    faq_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    """Admin xóa hoàn toàn câu hỏi FAQ khỏi kho tri thức."""
    faq = db.query(FAQ).filter(FAQ.id == faq_id).first()
    if not faq:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy câu hỏi FAQ #{faq_id} để xóa."
        )
    db.delete(faq)
    db.commit()
    return {"message": f"Đã xóa thành công câu hỏi FAQ #{faq_id}."}

