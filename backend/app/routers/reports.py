from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.reconciliation import PlatformReportResponse
from app.services.platform_reporting import build_platform_report

router = APIRouter(prefix="/reports", tags=["Platform Reports"])
get_current_report_operator = require_roles("admin", "operator")


@router.get(
    "/platform",
    response_model=PlatformReportResponse,
    summary="Báo cáo tổng hợp toàn nền tảng",
    description=(
        "Tổng hợp thanh toán, hoàn tiền, đơn thuê, phí CHECK_IN, người dùng, "
        "phương tiện và giao dịch/webhook bất thường. Chỉ admin/operator."
    ),
)
def get_platform_report(
    from_date: Optional[date] = Query(
        None,
        description="Ngày bắt đầu bao gồm; mặc định 30 ngày gần nhất.",
    ),
    to_date: Optional[date] = Query(
        None,
        description="Ngày kết thúc bao gồm; mặc định hôm nay.",
    ),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_report_operator),
):
    today = date.today()
    if from_date is None and to_date is None:
        to_date = today
        from_date = today - timedelta(days=29)
    elif from_date is None:
        from_date = to_date - timedelta(days=29)
    elif to_date is None:
        to_date = today

    if from_date > to_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="from_date phải nhỏ hơn hoặc bằng to_date.",
        )
    if (to_date - from_date).days > 366:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Khoảng thời gian báo cáo không được vượt quá 367 ngày.",
        )
    return build_platform_report(
        db,
        from_date=from_date,
        to_date=to_date,
    )
