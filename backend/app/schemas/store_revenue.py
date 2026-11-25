from datetime import date
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field


class RevenueSummary(BaseModel):
    total_revenue: Decimal = Field(..., description="Tổng doanh thu thực tế (thuê + phụ phí)")
    rental_revenue: Decimal = Field(..., description="Tổng tiền thuê xe thuần")
    delivery_revenue: Decimal = Field(..., description="Tổng phụ phí giao nhận")
    completed_orders: int = Field(..., description="Số đơn hoàn tất thành công")
    cancelled_orders: int = Field(..., description="Số đơn bị hủy")
    total_orders: int = Field(..., description="Tổng số đơn phát sinh")
    avg_order_value: Decimal = Field(..., description="Giá trị trung bình mỗi đơn hoàn thành")


class RevenueTimelineItem(BaseModel):
    time_bucket: str = Field(..., description="Ngày (YYYY-MM-DD) hoặc Tháng (YYYY-MM)")
    completed_orders: int = Field(..., description="Số đơn hoàn tất trong kỳ")
    cancelled_orders: int = Field(..., description="Số đơn bị hủy trong kỳ")
    total_orders: int = Field(..., description="Tổng số đơn trong kỳ")
    rental_revenue: Decimal = Field(..., description="Tiền thuê xe trong kỳ")
    delivery_revenue: Decimal = Field(..., description="Phụ phí giao xe trong kỳ")
    net_revenue: Decimal = Field(..., description="Doanh thu thực nhận trong kỳ")


class TopRentedVehicleItem(BaseModel):
    vehicle_id: int
    plate_number: str
    brand: str
    model: str
    vehicle_type: str
    rental_count: int = Field(..., description="Số lượt xe được thuê thành công")
    total_revenue: Decimal = Field(..., description="Tổng doanh thu do xe này mang lại")


class StoreRevenueReportResponse(BaseModel):
    store_id: int
    store_name: str
    period: str = Field(..., description="'day' hoặc 'month'")
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    summary: RevenueSummary
    timeline: List[RevenueTimelineItem]
    top_vehicles: List[TopRentedVehicleItem]