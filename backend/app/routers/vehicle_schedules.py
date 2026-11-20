"""Router API Lịch xe theo ngày/tuần & Cảnh báo xung đột (FR-21, FR-60)."""
from datetime import datetime, date, time, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.vehicle import Vehicle
from app.models.booking import Booking
from app.models.user import User
from app.models.vehicle_schedule import VehicleSchedule
from app.schemas.vehicle_schedule import (
    StoreVehicleScheduleOverview,
    ScheduleEventItem,
    ConflictAlert,
    MaintenanceAlert,
    ScheduleSummary,
)

router = APIRouter(prefix="/vehicle-schedules", tags=["Vehicle Schedules & Alerts"])


def _is_overlapping(start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime) -> bool:
    """Kiểm tra 2 khoảng thời gian có giao nhau không."""
    return max(start_a, start_b) < min(end_a, end_b)


@router.get("", response_model=StoreVehicleScheduleOverview)
def get_store_vehicle_schedules(
    store_id: int = Query(..., description="ID cửa hàng cần xem lịch"),
    target_date: Optional[date] = Query(None, description="Ngày mốc (mặc định hôm nay)"),
    view_mode: str = Query("week", regex="^(day|week|month)$", description="Chế độ: day, week, month"),
    vehicle_id: Optional[int] = Query(None, description="Lọc riêng 1 xe"),
    db: Session = Depends(get_db),
):
    """Lấy danh sách lịch xe theo Ngày/Tuần/Tháng, tự động quét xung đột và cảnh báo bảo trì."""
    if target_date is None:
        target_date = date.today()

    # 1. Tính toán khoảng thời gian xem theo view_mode
    if view_mode == "day":
        start_range = datetime.combine(target_date, time.min)
        end_range = datetime.combine(target_date, time.max)
    elif view_mode == "week":
        weekday = target_date.weekday()  # 0: Thứ 2
        start_of_week = target_date - timedelta(days=weekday)
        end_of_week = start_of_week + timedelta(days=6)
        start_range = datetime.combine(start_of_week, time.min)
        end_range = datetime.combine(end_of_week, time.max)
    else:  # month
        first_day = target_date.replace(day=1)
        next_month = (first_day.replace(day=28) + timedelta(days=4)).replace(day=1)
        last_day = next_month - timedelta(days=1)
        start_range = datetime.combine(first_day, time.min)
        end_range = datetime.combine(last_day, time.max)

    # 2. Lấy danh sách xe của cửa hàng
    veh_query = db.query(Vehicle).filter(Vehicle.store_id == store_id, Vehicle.is_active == True)
    if vehicle_id:
        veh_query = veh_query.filter(Vehicle.id == vehicle_id)
    vehicles = veh_query.all()
    veh_map = {v.id: v for v in vehicles}

    if not veh_map:
        return StoreVehicleScheduleOverview(
            store_id=store_id,
            start_date=start_range,
            end_date=end_range,
            view_mode=view_mode,
            summary=ScheduleSummary(total_events=0, total_conflicts=0, total_maintenance_due=0, total_active_rentals=0),
            conflicts=[],
            maintenance_alerts=[],
            events=[],
        )

    veh_ids = list(veh_map.keys())

    # 3. Lấy các đơn thuê xe (Bookings) hợp lệ trong khoảng thời gian này
    bookings = (
        db.query(Booking, User)
        .outerjoin(User, Booking.customer_id == User.id)
        .filter(
            Booking.vehicle_id.in_(veh_ids),
            Booking.status.notin_(["CANCELLED", "EXPIRED"]),
            Booking.start_time <= end_range,
            Booking.end_time >= start_range,
        )
        .all()
    )

    # 4. Lấy các ca chặn xe (VehicleSchedule: Bảo dưỡng, Vệ sinh...)
    schedules = (
        db.query(VehicleSchedule)
        .filter(
            VehicleSchedule.vehicle_id.in_(veh_ids),
            VehicleSchedule.status == "ACTIVE",
            VehicleSchedule.start_time <= end_range,
            VehicleSchedule.end_time >= start_range,
        )
        .all()
    )

    # 5. Đưa toàn bộ vào danh sách sự kiện tạm
    raw_events = []

    # Map đơn thuê xe
    for b, customer in bookings:
        v = veh_map.get(b.vehicle_id)
        v_name = f"{v.brand} {v.model}" if v else "Phương tiện"
        plate = v.plate_number if v else ""
        cust_name = customer.full_name if customer else "Khách thuê"
        cust_phone = customer.phone if customer else ""

        raw_events.append({
            "id": f"booking-{b.id}",
            "event_type": "RENTAL",
            "vehicle_id": b.vehicle_id,
            "vehicle_name": v_name,
            "plate_number": plate,
            "title": f"Đơn #{b.id} • {v_name}",
            "start_time": b.start_time,
            "end_time": b.end_time,
            "status": b.status,
            "customer_name": cust_name,
            "customer_phone": cust_phone,
            "note": f"Khách thuê: {cust_name} ({cust_phone})",
        })

    # Map ca bảo dưỡng/vệ sinh
    for s in schedules:
        v = veh_map.get(s.vehicle_id)
        v_name = f"{v.brand} {v.model}" if v else "Phương tiện"
        plate = v.plate_number if v else ""
        s_type = (s.schedule_type or "MAINTENANCE").upper()
        title_prefix = "Bảo dưỡng" if s_type == "MAINTENANCE" else "Vệ sinh/Kiểm tra"

        raw_events.append({
            "id": f"schedule-{s.id}",
            "event_type": s_type,
            "vehicle_id": s.vehicle_id,
            "vehicle_name": v_name,
            "plate_number": plate,
            "title": f"{title_prefix} • {v_name}",
            "start_time": s.start_time,
            "end_time": s.end_time,
            "status": s.status,
            "customer_name": None,
            "customer_phone": None,
            "note": s.note or f"Ca {title_prefix.lower()} định kỳ",
        })

    # 6. THUẬT TOÁN PHÁT HIỆN XUNG ĐỘT (CONFLICT DETECTION)
    conflicts_list: List[ConflictAlert] = []
    conflict_event_ids = set()
    conflict_reasons = {}

    # Gom theo từng xe để so sánh chéo các ca
    events_by_veh = {}
    for ev in raw_events:
        events_by_veh.setdefault(ev["vehicle_id"], []).append(ev)

    for v_id, ev_list in events_by_veh.items():
        n = len(ev_list)
        for i in range(n):
            for j in range(i + 1, n):
                ev1 = ev_list[i]
                ev2 = ev_list[j]
                if _is_overlapping(ev1["start_time"], ev1["end_time"], ev2["start_time"], ev2["end_time"]):
                    conflict_event_ids.add(ev1["id"])
                    conflict_event_ids.add(ev2["id"])

                    conflict_type = (
                        "MAINTENANCE_OVERLAP"
                        if ev1["event_type"] == "MAINTENANCE" or ev2["event_type"] == "MAINTENANCE"
                        else "DOUBLE_BOOKING"
                    )

                    desc = (
                        f"Xe {ev1['plate_number']} ({ev1['vehicle_name']}) bị trùng giờ giữa "
                        f"'{ev1['title']}' ({ev1['start_time'].strftime('%d/%m %H:%M')}) và "
                        f"'{ev2['title']}' ({ev2['start_time'].strftime('%d/%m %H:%M')})"
                    )

                    conflicts_list.append(
                        ConflictAlert(
                            vehicle_id=v_id,
                            vehicle_name=ev1["vehicle_name"],
                            plate_number=ev1["plate_number"],
                            conflict_type=conflict_type,
                            event_id_1=ev1["id"],
                            event_id_2=ev2["id"],
                            description=desc,
                        )
                    )
                    conflict_reasons[ev1["id"]] = f"Xung đột lịch với {ev2['title']}"
                    conflict_reasons[ev2["id"]] = f"Xung đột lịch với {ev1['title']}"

    # 7. CẢNH BÁO XE TỚI HẠN BẢO TRÌ (FR-60)
    maintenance_alerts: List[MaintenanceAlert] = []
    for ev in raw_events:
        if ev["event_type"] == "MAINTENANCE":
            maintenance_alerts.append(
                MaintenanceAlert(
                    vehicle_id=ev["vehicle_id"],
                    vehicle_name=ev["vehicle_name"],
                    plate_number=ev["plate_number"],
                    title=f"Cảnh báo bảo dưỡng định kỳ: {ev['vehicle_name']}",
                    description=f"Xe {ev['plate_number']} có ca bảo dưỡng vào {ev['start_time'].strftime('%d/%m/%Y %H:%M')}.",
                    maintenance_date=ev["start_time"],
                    status="MAINTENANCE",
                )
            )

    for v in vehicles:
        if v.current_status == "MAINTENANCE":
            if not any(m.vehicle_id == v.id for m in maintenance_alerts):
                maintenance_alerts.append(
                    MaintenanceAlert(
                        vehicle_id=v.id,
                        vehicle_name=f"{v.brand} {v.model}",
                        plate_number=v.plate_number,
                        title=f"Xe đang bảo trì tại xưởng: {v.brand} {v.model}",
                        description=f"Xe {v.plate_number} đang ở trạng thái Bảo dưỡng, đã tự động ẩn khỏi tìm kiếm.",
                        maintenance_date=v.updated_at or datetime.now(),
                        status="MAINTENANCE",
                    )
                )

    # 8. Chuẩn hóa sự kiện trả về
    final_events: List[ScheduleEventItem] = []
    for ev in raw_events:
        is_conflict = ev["id"] in conflict_event_ids
        final_events.append(
            ScheduleEventItem(
                id=ev["id"],
                event_type=ev["event_type"],
                vehicle_id=ev["vehicle_id"],
                vehicle_name=ev["vehicle_name"],
                plate_number=ev["plate_number"],
                title=ev["title"],
                start_time=ev["start_time"],
                end_time=ev["end_time"],
                status=ev["status"],
                customer_name=ev["customer_name"],
                customer_phone=ev["customer_phone"],
                note=ev["note"],
                has_conflict=is_conflict,
                conflict_reason=conflict_reasons.get(ev["id"]),
            )
        )

    final_events.sort(key=lambda x: x.start_time)

    # 9. Chỉ số tổng hợp KPIs
    summary = ScheduleSummary(
        total_events=len(final_events),
        total_conflicts=len(conflicts_list),
        total_maintenance_due=len(maintenance_alerts),
        total_active_rentals=sum(1 for e in final_events if e.event_type == "RENTAL"),
    )

    return StoreVehicleScheduleOverview(
        store_id=store_id,
        start_date=start_range,
        end_date=end_range,
        view_mode=view_mode,
        summary=summary,
        conflicts=conflicts_list,
        maintenance_alerts=maintenance_alerts,
        events=final_events,
    )