from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.crud.booking_cancellation import BookingPermissionError
from app.crud.store_order_review import get_user_store_ids
from app.models.booking import Booking
from app.models.store import Store
from app.models.user import User
from app.models.vehicle import Vehicle
from app.schemas.store_revenue import (
    RevenueSummary,
    RevenueTimelineItem,
    StoreRevenueReportResponse,
    TopRentedVehicleItem,
)

VALID_STATUSES = ("COMPLETED", "PAID", "CONFIRMED", "completed", "paid", "confirmed")


def get_store_revenue_report(
    db: Session,
    user: User,
    store_id: int,
    period: str = "day",
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    limit_top_vehicles: int = 5,
) -> StoreRevenueReportResponse:
    # 1. Kiểm tra cửa hàng có tồn tại không
    store = db.get(Store, store_id)
    if not store:
        raise ValueError(f"Không tìm thấy cửa hàng với ID {store_id}")

    # 2. Kiểm tra phân quyền: User phải là Admin, chủ cửa hàng hoặc nhân viên thuộc cửa hàng
    user_role = (user.role or "").lower()
    if user_role != "admin":
        allowed_store_ids = get_user_store_ids(db, user)
        if store_id not in allowed_store_ids:
            raise BookingPermissionError("Bạn không có quyền xem báo cáo doanh thu của cửa hàng này.")

    # 3. Chuẩn hóa khoảng thời gian mặc định
    today = date.today()
    if to_date is None:
        to_date = today
    if from_date is None:
        # Nếu theo tháng: mặc định lấy 12 tháng gần nhất; nếu theo ngày: lấy 30 ngày gần nhất
        from_date = today - timedelta(days=365 if period == "month" else 30)

    # 4. Điều kiện lọc cơ bản theo store và thời gian
    base_filter = [
        Booking.store_id == store_id,
        func.date(Booking.created_at) >= from_date,
        func.date(Booking.created_at) <= to_date,
    ]

    # 5. Truy vấn tổng quan (Summary)
    completed_case = case((func.upper(Booking.status).in_(("COMPLETED", "PAID", "CONFIRMED")), 1), else_=0)
    cancelled_case = case((func.upper(Booking.status) == "CANCELLED", 1), else_=0)
    rental_case = case((func.upper(Booking.status).in_(("COMPLETED", "PAID", "CONFIRMED")), Booking.rental_amount), else_=Decimal("0"))
    delivery_case = case((func.upper(Booking.status).in_(("COMPLETED", "PAID", "CONFIRMED")), Booking.delivery_fee), else_=Decimal("0"))
    
    summary_stmt = select(
        func.count(Booking.id).label("total_orders"),
        func.sum(completed_case).label("completed_orders"),
        func.sum(cancelled_case).label("cancelled_orders"),
        func.coalesce(func.sum(rental_case), Decimal("0")).label("rental_revenue"),
        func.coalesce(func.sum(delivery_case), Decimal("0")).label("delivery_revenue"),
    ).where(*base_filter)

    summary_row = db.execute(summary_stmt).one()
    tot_orders = summary_row.total_orders or 0
    comp_orders = int(summary_row.completed_orders or 0)
    canc_orders = int(summary_row.cancelled_orders or 0)
    rent_rev = Decimal(str(summary_row.rental_revenue or 0))
    deliv_rev = Decimal(str(summary_row.delivery_revenue or 0))
    total_rev = rent_rev + deliv_rev
    avg_val = Decimal(round(total_rev / comp_orders, 2)) if comp_orders > 0 else Decimal("0")

    summary_data = RevenueSummary(
        total_revenue=total_rev,
        rental_revenue=rent_rev,
        delivery_revenue=deliv_rev,
        completed_orders=comp_orders,
        cancelled_orders=canc_orders,
        total_orders=tot_orders,
        avg_order_value=avg_val,
    )

    # 6. Truy vấn chuỗi thời gian (Timeline: Gom nhóm theo ngày hoặc tháng)
    time_expr = (
        func.date_format(Booking.created_at, "%Y-%m")
        if period == "month"
        else func.date(Booking.created_at)
    )

    timeline_stmt = (
        select(
            time_expr.label("time_bucket"),
            func.count(Booking.id).label("total_orders"),
            func.sum(completed_case).label("completed_orders"),
            func.sum(cancelled_case).label("cancelled_orders"),
            func.coalesce(func.sum(rental_case), Decimal("0")).label("rental_revenue"),
            func.coalesce(func.sum(delivery_case), Decimal("0")).label("delivery_revenue"),
        )
        .where(*base_filter)
        .group_by("time_bucket")
        .order_by("time_bucket")
    )

    timeline_rows = db.execute(timeline_stmt).all()
    timeline_items = [
        RevenueTimelineItem(
            time_bucket=str(row.time_bucket),
            completed_orders=int(row.completed_orders or 0),
            cancelled_orders=int(row.cancelled_orders or 0),
            total_orders=int(row.total_orders or 0),
            rental_revenue=Decimal(str(row.rental_revenue or 0)),
            delivery_revenue=Decimal(str(row.delivery_revenue or 0)),
            net_revenue=Decimal(str(row.rental_revenue or 0)) + Decimal(str(row.delivery_revenue or 0)),
        )
        for row in timeline_rows
    ]

    # 7. Truy vấn Top xe được thuê nhiều nhất (Top Rented Vehicles)
    top_vehicles_stmt = (
        select(
            Vehicle.id.label("vehicle_id"),
            Vehicle.plate_number,
            Vehicle.brand,
            Vehicle.model,
            Vehicle.vehicle_type,
            func.count(Booking.id).label("rental_count"),
            func.coalesce(
                func.sum(Booking.rental_amount + Booking.delivery_fee), Decimal("0")
            ).label("total_revenue"),
        )
        .join(Booking, Booking.vehicle_id == Vehicle.id)
        .where(
            Booking.store_id == store_id,
            Booking.status.in_(VALID_STATUSES),
            func.date(Booking.created_at) >= from_date,
            func.date(Booking.created_at) <= to_date,
        )
        .group_by(
            Vehicle.id,
            Vehicle.plate_number,
            Vehicle.brand,
            Vehicle.model,
            Vehicle.vehicle_type,
        )
        .order_by(func.count(Booking.id).desc(), func.sum(Booking.rental_amount).desc())
        .limit(limit_top_vehicles)
    )

    top_vehicle_rows = db.execute(top_vehicles_stmt).all()
    top_vehicles = [
        TopRentedVehicleItem(
            vehicle_id=row.vehicle_id,
            plate_number=row.plate_number,
            brand=row.brand,
            model=row.model,
            vehicle_type=row.vehicle_type,
            rental_count=int(row.rental_count or 0),
            total_revenue=Decimal(str(row.total_revenue or 0)),
        )
        for row in top_vehicle_rows
    ]

    return StoreRevenueReportResponse(
        store_id=store.id,
        store_name=store.name,
        period=period,
        from_date=from_date,
        to_date=to_date,
        summary=summary_data,
        timeline=timeline_items,
        top_vehicles=top_vehicles,
    )