"""Router API Quản trị Tra cứu & Thống kê Nhật ký kiểm toán (Audit Logs).

Chỉ dành cho tài khoản Admin (xác thực qua dependency get_current_admin).
"""
from datetime import datetime
from math import ceil
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_admin
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit_log import AuditLogPaginationResponse, AuditLogResponse

router = APIRouter(
    prefix="/admin/audit-logs",
    tags=["Admin - Nhật ký kiểm toán (Audit Logs)"],
)


@router.get(
    "",
    response_model=AuditLogPaginationResponse,
    summary="Tra cứu danh sách nhật ký kiểm toán (Có lọc & phân trang)",
)
def get_audit_logs(
    page: int = Query(1, ge=1, description="Trang hiện tại (bắt đầu từ 1)"),
    size: int = Query(20, ge=1, le=100, description="Số bản ghi mỗi trang (tối đa 100)"),
    action: Optional[str] = Query(None, description="Lọc theo hành động (VD: REVIEW_APPROVE, VEHICLE_STATUS_CHANGE, PAYMENT_REFUND)"),
    resource_type: Optional[str] = Query(None, description="Lọc loại tài nguyên (VD: store, vehicle, payment, booking)"),
    resource_id: Optional[str] = Query(None, description="Lọc theo mã định danh tài nguyên"),
    user_id: Optional[int] = Query(None, description="Lọc theo ID người thực hiện"),
    status: Optional[str] = Query(None, description="Lọc theo trạng thái (SUCCESS / FAILED)"),
    search: Optional[str] = Query(None, description="Tìm kiếm theo email, endpoint hoặc mô tả"),
    from_date: Optional[datetime] = Query(None, description="Từ thời điểm (ISO-8601)"),
    to_date: Optional[datetime] = Query(None, description="Đến thời điểm (ISO-8601)"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    query = db.query(AuditLog)

    if action:
        query = query.filter(AuditLog.action == action)
    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)
    if resource_id:
        query = query.filter(AuditLog.resource_id == str(resource_id))
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if status:
        query = query.filter(AuditLog.status == status.upper())
    if from_date:
        query = query.filter(AuditLog.created_at >= from_date)
    if to_date:
        query = query.filter(AuditLog.created_at <= to_date)
    if search:
        search_fmt = f"%{search.strip()}%"
        query = query.filter(
            or_(
                AuditLog.user_email.ilike(search_fmt),
                AuditLog.endpoint.ilike(search_fmt),
                AuditLog.description.ilike(search_fmt),
            )
        )

    total = query.count()
    total_pages = ceil(total / size) if total > 0 else 0
    offset = (page - 1) * size

    items = query.order_by(desc(AuditLog.created_at), desc(AuditLog.id)).offset(offset).limit(size).all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": total_pages,
    }


@router.get(
    "/stats/summary",
    summary="Thống kê tóm tắt các hoạt động kiểm toán",
)
def get_audit_summary_stats(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Trả về số liệu tổng quan về các hoạt động duyệt, đổi trạng thái và hoàn tiền."""
    total_logs = db.query(func.count(AuditLog.id)).scalar() or 0
    total_success = db.query(func.count(AuditLog.id)).filter(AuditLog.status == "SUCCESS").scalar() or 0
    total_failed = db.query(func.count(AuditLog.id)).filter(AuditLog.status == "FAILED").scalar() or 0

    review_count = (
        db.query(func.count(AuditLog.id))
        .filter(AuditLog.action.like("REVIEW_%"))
        .scalar()
        or 0
    )
    status_change_count = (
        db.query(func.count(AuditLog.id))
        .filter(AuditLog.action.like("%STATUS%"))
        .scalar()
        or 0
    )
    refund_count = (
        db.query(func.count(AuditLog.id))
        .filter(AuditLog.action.like("%REFUND%"))
        .scalar()
        or 0
    )

    return {
        "total_logs": total_logs,
        "total_success": total_success,
        "total_failed": total_failed,
        "by_category": {
            "reviews": review_count,
            "status_changes": status_change_count,
            "refunds": refund_count,
        },
    }


@router.get(
    "/{log_id}",
    response_model=AuditLogResponse,
    summary="Xem chi tiết một bản ghi nhật ký kiểm toán",
)
def get_audit_log_detail(
    log_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    record = db.query(AuditLog).filter(AuditLog.id == log_id).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy bản ghi Audit Log #{log_id}",
        )
    return record
