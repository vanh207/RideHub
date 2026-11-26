"""Script tạo dữ liệu mẫu đơn thuê nhiều trạng thái cho TF1AE49.

Chỉ chạy trên DB demo/dev/test. Mọi thay đổi nằm trong một transaction;
không gọi cổng thanh toán, không gửi email, không kích hoạt webhook.

Cách chạy từ thư mục backend:
    DB_NAME=ridehub_test ../.venv/bin/python -m scripts.seed_demo_bookings --dry-run
    DB_NAME=ridehub_test ../.venv/bin/python -m scripts.seed_demo_bookings --yes
    DB_NAME=ridehub_test ../.venv/bin/python -m scripts.seed_demo_bookings --reset --yes
    DB_NAME=ridehub_test ../.venv/bin/python -m scripts.seed_demo_bookings --reseed --yes
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Iterable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.core.booking_status import (
    CANCEL_ACTOR_ADMIN,
    CANCEL_ACTOR_CUSTOMER,
    CANCEL_ACTOR_STORE,
    CANCEL_ACTOR_SYSTEM,
)
from app.crud.booking import calculate_deposit_amount, calculate_rental_amount
from app.db.seed_data import SEED_ACCOUNTS
from app.db.seed_vehicles_delivery import SAMPLE_VEHICLES
from app.db.session import SessionLocal, engine
from app.services.cancellation_policy import calculate_refund_quote

DEMO_TAG = "[DEMO] TF1AE49"
CODE_PREFIX = "DEMO-TF1AE49-"
ALLOWED_DB_MARKERS = ("test", "demo", "dev")
FORBIDDEN_ENV_TOKENS = ("prod", "production", "live")

CUSTOMER_EMAIL = next(
    item["email"] for item in SEED_ACCOUNTS if item["role_code"] == "customer"
)
MOTORBIKE_PLATES = [
    item["plate_number"]
    for item in SAMPLE_VEHICLES
    if item["vehicle_type"] == "MOTORBIKE"
]
CAR_PLATES = [
    item["plate_number"]
    for item in SAMPLE_VEHICLES
    if item["vehicle_type"] == "CAR"
]

TABLE_BOOKINGS = "bookings"
TABLE_HISTORIES = "booking_status_history"
TABLE_RESERVATIONS = "vehicle_reservations"
TABLE_SCHEDULES = "vehicle_schedules"
TABLE_PAYMENTS = "payment_transactions"
TABLE_REFUNDS = "refunds"
TABLE_HANDOVERS = "handover_protocols"
TABLE_HANDOVER_MEDIA = "handover_media"
TABLE_COMPLAINTS = "complaints"
TABLE_COMPLAINT_HISTORIES = "complaint_status_histories"
TABLE_VEHICLE_HISTORIES = "vehicle_status_history"
TABLE_VEHICLES = "vehicles"

TABLES_IN_SCOPE = (
    TABLE_BOOKINGS,
    TABLE_HISTORIES,
    TABLE_RESERVATIONS,
    TABLE_SCHEDULES,
    TABLE_PAYMENTS,
    TABLE_REFUNDS,
    TABLE_HANDOVERS,
    TABLE_HANDOVER_MEDIA,
    TABLE_COMPLAINTS,
    TABLE_COMPLAINT_HISTORIES,
    TABLE_VEHICLE_HISTORIES,
)


@dataclass(frozen=True)
class BookingSpec:
    """Một đơn mẫu. Các mốc thời gian là số giờ/phút tương đối từ now."""

    suffix: str
    status: str
    plate: str
    start_hours: float
    duration_hours: float
    note: str
    hold_minutes: Optional[int] = None
    with_delivery: bool = False
    payment_status: Optional[str] = None
    refund_rate: Optional[Decimal] = None
    handover: Optional[str] = None
    settlement: bool = False
    complaint: bool = False
    legacy: bool = False

    @property
    def code(self) -> str:
        return f"{CODE_PREFIX}{self.suffix}"

    @property
    def marker(self) -> str:
        return f"{DEMO_TAG}:{self.code}"


def _status_label(status: str) -> str:
    return " (legacy)" if status in {"PENDING_STORE_CONFIRM", "BOOKED"} else ""


def build_specs() -> list[BookingSpec]:
    """Danh sách 15 đơn mẫu, mỗi đơn dùng một xe riêng để tránh chồng lịch."""
    return [
        BookingSpec(
            "01-PP-FRESH",
            "PENDING_PAYMENT",
            MOTORBIKE_PLATES[0],
            30,
            26,
            "Chờ thanh toán, còn nhiều thời gian giữ chỗ",
            hold_minutes=28,
            payment_status="PENDING",
        ),
        BookingSpec(
            "02-PP-SOON",
            "PENDING_PAYMENT",
            MOTORBIKE_PLATES[1],
            18,
            24,
            "Chờ thanh toán, sắp hết hạn giữ chỗ",
            hold_minutes=3,
            payment_status="PENDING",
        ),
        BookingSpec(
            "03-DEPOSIT-PAID",
            "DEPOSIT_PAID",
            MOTORBIKE_PLATES[2],
            28,
            25,
            "Đã cọc, chờ cửa hàng duyệt",
            with_delivery=True,
            payment_status="SUCCESS",
        ),
        BookingSpec(
            "04-PENDING-STORE",
            "PENDING_STORE_CONFIRM",
            MOTORBIKE_PLATES[3],
            34,
            26,
            "Trạng thái legacy chờ duyệt cửa hàng, tương đương DEPOSIT_PAID",
            with_delivery=True,
            payment_status="SUCCESS",
            legacy=True,
        ),
        BookingSpec(
            "05-CONFIRMED",
            "CONFIRMED",
            CAR_PLATES[0],
            24,
            48,
            "Đã duyệt, bắt đầu trong tương lai gần để demo giao xe",
            with_delivery=True,
            payment_status="SUCCESS",
        ),
        BookingSpec(
            "06-IN-PROGRESS",
            "IN_PROGRESS",
            CAR_PLATES[1],
            -5,
            24,
            "Đang thuê, đã có biên bản giao xe",
            payment_status="SUCCESS",
            handover="CHECK_OUT",
        ),
        BookingSpec(
            "07-PENDING-SETTLEMENT",
            "PENDING_SETTLEMENT",
            CAR_PLATES[2],
            -29,
            26,
            "Đã trả xe, chờ tất toán",
            payment_status="SUCCESS",
            handover="BOTH",
        ),
        BookingSpec(
            "08-DISPUTED",
            "DISPUTED",
            MOTORBIKE_PLATES[4],
            -8,
            20,
            "Đơn có khiếu nại; trạng thái SRS chưa có canonical trong backend",
            payment_status="SUCCESS",
            complaint=True,
        ),
        BookingSpec(
            "09-COMPLETED",
            "COMPLETED",
            CAR_PLATES[3],
            -96,
            48,
            "Hoàn tất đủ đường: cọc, giao xe, nhận xe, tất toán",
            with_delivery=True,
            payment_status="SUCCESS",
            handover="BOTH",
            settlement=True,
        ),
        BookingSpec(
            "10-EXPIRED",
            "EXPIRED",
            MOTORBIKE_PLATES[5],
            12,
            24,
            "Hết hạn giữ chỗ 2 giờ trước, reservation EXPIRED, lịch đã nhả",
            hold_minutes=-120,
            payment_status="EXPIRED",
        ),
        BookingSpec(
            "11-CANCEL-FULL",
            "CANCELLED",
            MOTORBIKE_PLATES[6],
            72,
            48,
            "Hủy trước 72 giờ, hoàn 100% tiền cọc theo BR-04",
            payment_status="SUCCESS",
            refund_rate=Decimal("1"),
        ),
        BookingSpec(
            "12-CANCEL-PARTIAL",
            "CANCELLED",
            CAR_PLATES[4],
            12,
            30,
            "Hủy trước 12 giờ, hoàn 50% tiền cọc theo BR-04",
            with_delivery=True,
            payment_status="SUCCESS",
            refund_rate=Decimal("0.5"),
        ),
        BookingSpec(
            "13-CANCEL-LATE",
            "CANCELLED",
            CAR_PLATES[5],
            2,
            24,
            "Hủy trong vòng 6 giờ, không hoàn tiền theo BR-04",
            payment_status="SUCCESS",
            refund_rate=Decimal("0"),
        ),
        BookingSpec(
            "14-REJECTED",
            "REJECTED",
            MOTORBIKE_PLATES[7],
            48,
            30,
            "Cửa hàng từ chối; trạng thái SRS, backend hiện ghi CANCELLED",
            payment_status="SUCCESS",
            refund_rate=Decimal("1"),
        ),
        BookingSpec(
            "15-BOOKED-LEGACY",
            "BOOKED",
            MOTORBIKE_PLATES[8],
            40,
            28,
            "Dạng payment hiện tại vẫn ghi BOOKED, normalize thành DEPOSIT_PAID",
            payment_status="SUCCESS",
            legacy=True,
        ),
    ]


def assert_safe_environment(*, require_yes: bool, dry_run: bool) -> str:
    """Chặn production theo tên DB và APP_ENV; trả về tên DB để in log."""
    app_env = os.getenv("APP_ENV", "").strip().lower()
    if any(token in app_env for token in FORBIDDEN_ENV_TOKENS):
        raise RuntimeError(f"Từ chối chạy: APP_ENV='{app_env}' là môi trường production.")

    database = (engine.url.database or "").strip().lower()
    if any(token in database for token in FORBIDDEN_ENV_TOKENS):
        raise RuntimeError(f"Từ chối chạy: DB '{database}' có dấu hiệu production.")

    if not any(marker in database for marker in ALLOWED_DB_MARKERS):
        raise RuntimeError(
            f"Từ chối chạy: DB '{database}' không chứa test/demo/dev. "
            "Đặt DB_NAME=ridehub_test trước khi chạy."
        )

    with engine.connect() as conn:
        current = str(conn.execute(text("SELECT DATABASE()")).scalar() or "").lower()
    if current != database:
        raise RuntimeError(f"Từ chối chạy: DB khai báo '{database}' khác DB hiện tại '{current}'.")

    if not dry_run and not require_yes:
        raise RuntimeError("Chế độ ghi cần cờ --yes. Dùng --dry-run để xem kế hoạch trước.")

    return database


def _insert(conn: Connection, table: str, values: dict) -> int:
    """Chèn bằng SQL có tham số; tên bảng/cột chỉ lấy từ hằng số trong file."""
    columns = list(values)
    column_sql = ", ".join(columns)
    value_sql = ", ".join(f":{column}" for column in columns)
    result = conn.execute(
        text(f"INSERT INTO {table} ({column_sql}) VALUES ({value_sql})"), values
    )
    return int(result.lastrowid or 0)


def _rows_in(conn: Connection, table: str, column: str, ids: Iterable[int]) -> list:
    id_list = list(ids)
    if not id_list:
        return []
    return list(
        conn.execute(
            text(f"SELECT * FROM {table} WHERE {column} IN :ids"),
            {"ids": id_list},
        ).mappings()
    )


def _count_in(conn: Connection, table: str, column: str, ids: Iterable[int]) -> int:
    id_list = list(ids)
    if not id_list:
        return 0
    return int(
        conn.execute(
            text(f"SELECT COUNT(*) FROM {table} WHERE {column} IN :ids"),
            {"ids": id_list},
        ).scalar()
        or 0
    )


def _delete_in(conn: Connection, table: str, column: str, ids: Iterable[int]) -> int:
    id_list = list(ids)
    if not id_list:
        return 0
    result = conn.execute(
        text(f"DELETE FROM {table} WHERE {column} IN :ids"), {"ids": id_list}
    )
    return max(int(result.rowcount or 0), 0)


def _demo_booking_ids(conn: Connection) -> list[int]:
    """Tìm booking mẫu qua các dấu nhận diện, không qua ID cố định."""
    mark = f"{DEMO_TAG}:%"
    rows = conn.execute(
        text(
            """
            SELECT DISTINCT booking_id AS id FROM booking_status_history WHERE reason LIKE :mark
            UNION
            SELECT DISTINCT booking_id AS id FROM vehicle_schedules WHERE note LIKE :mark
            UNION
            SELECT DISTINCT booking_id AS id FROM payment_transactions WHERE transaction_code LIKE :code_mark
            UNION
            SELECT DISTINCT booking_id AS id FROM handover_protocols WHERE protocol_code LIKE :code_mark
            """
        ),
        {"mark": mark, "code_mark": f"{CODE_PREFIX}%"},
    ).mappings()
    return sorted(int(row["id"]) for row in rows if row["id"] is not None)


def _reset_plan(conn: Connection) -> tuple[list[int], list[int], list[int], dict[str, int]]:
    """Chỉ đếm và trả danh sách ID sẽ xóa; không thực hiện xóa."""
    booking_ids = _demo_booking_ids(conn)
    protocol_ids = [
        int(row["id"])
        for row in _rows_in(conn, TABLE_HANDOVERS, "booking_id", booking_ids)
    ]
    complaint_ids = [
        int(row["id"])
        for row in _rows_in(conn, TABLE_COMPLAINTS, "booking_id", booking_ids)
    ]
    counts = {
        TABLE_COMPLAINT_HISTORIES: _count_in(
            conn, TABLE_COMPLAINT_HISTORIES, "complaint_id", complaint_ids
        ),
        TABLE_COMPLAINTS: len(complaint_ids),
        TABLE_HANDOVER_MEDIA: _count_in(
            conn, TABLE_HANDOVER_MEDIA, "protocol_id", protocol_ids
        ),
        TABLE_HANDOVERS: len(protocol_ids),
        TABLE_REFUNDS: _count_in(conn, TABLE_REFUNDS, "booking_id", booking_ids),
        TABLE_PAYMENTS: _count_in(conn, TABLE_PAYMENTS, "booking_id", booking_ids),
        TABLE_SCHEDULES: _count_in(conn, TABLE_SCHEDULES, "booking_id", booking_ids),
        TABLE_RESERVATIONS: _count_in(
            conn, TABLE_RESERVATIONS, "booking_id", booking_ids
        ),
        TABLE_HISTORIES: _count_in(
            conn, TABLE_HISTORIES, "booking_id", booking_ids
        ),
        TABLE_BOOKINGS: len(booking_ids),
        TABLE_VEHICLE_HISTORIES: int(
            conn.execute(
                text(
                    "SELECT COUNT(*) FROM vehicle_status_history WHERE note LIKE :mark"
                ),
                {"mark": f"{DEMO_TAG}:%"},
            ).scalar()
            or 0
        ),
    }
    return booking_ids, protocol_ids, complaint_ids, counts


def describe_reset(conn: Connection) -> dict[str, int]:
    """In số dòng sẽ xóa cho --dry-run, không ghi DB."""
    _, _, _, counts = _reset_plan(conn)
    print("Số dòng sẽ xóa (chỉ dữ liệu có dấu TF1AE49):")
    for table, count in counts.items():
        print(f"  - {table}: {count}")
    return counts


def reset_demo_data(conn: Connection) -> dict[str, int]:
    """Xóa đúng dữ liệu TF1AE49 theo dấu nhận diện, trả số dòng từng bảng."""
    booking_ids, protocol_ids, complaint_ids, counts = _reset_plan(conn)
    if not booking_ids:
        print("Không tìm thấy đơn mẫu TF1AE49 để xóa.")
        return {}
    print("Số dòng sẽ xóa (chỉ dữ liệu có dấu TF1AE49):")
    for table, count in counts.items():
        print(f"  - {table}: {count}")

    vehicle_rows = list(
        conn.execute(
            text("SELECT vehicle_id, note FROM vehicle_status_history WHERE note LIKE :mark"),
            {"mark": f"{DEMO_TAG}:%"},
        ).mappings()
    )
    for row in vehicle_rows:
        previous = ""
        if "|prev=" in str(row["note"]):
            previous = str(row["note"]).split("|prev=", 1)[1]
        if previous:
            conn.execute(
                text("UPDATE vehicles SET current_status = :status WHERE id = :id"),
                {"status": previous, "id": row["vehicle_id"]},
            )

    deleted: dict[str, int] = {}
    deleted[TABLE_COMPLAINT_HISTORIES] = _delete_in(
        conn, TABLE_COMPLAINT_HISTORIES, "complaint_id", complaint_ids
    )
    deleted[TABLE_COMPLAINTS] = _delete_in(conn, TABLE_COMPLAINTS, "id", complaint_ids)
    deleted[TABLE_HANDOVER_MEDIA] = _delete_in(
        conn, TABLE_HANDOVER_MEDIA, "protocol_id", protocol_ids
    )
    deleted[TABLE_HANDOVERS] = _delete_in(
        conn, TABLE_HANDOVERS, "id", protocol_ids
    )
    deleted[TABLE_REFUNDS] = _delete_in(conn, TABLE_REFUNDS, "booking_id", booking_ids)
    deleted[TABLE_PAYMENTS] = _delete_in(
        conn, TABLE_PAYMENTS, "booking_id", booking_ids
    )
    deleted[TABLE_SCHEDULES] = _delete_in(
        conn, TABLE_SCHEDULES, "booking_id", booking_ids
    )
    deleted[TABLE_RESERVATIONS] = _delete_in(
        conn, TABLE_RESERVATIONS, "booking_id", booking_ids
    )
    deleted[TABLE_HISTORIES] = _delete_in(
        conn, TABLE_HISTORIES, "booking_id", booking_ids
    )
    deleted[TABLE_BOOKINGS] = _delete_in(conn, TABLE_BOOKINGS, "id", booking_ids)
    result = conn.execute(
        text("DELETE FROM vehicle_status_history WHERE note LIKE :mark"),
        {"mark": f"{DEMO_TAG}%"},
    )
    deleted[TABLE_VEHICLE_HISTORIES] = max(int(result.rowcount or 0), 0)
    return deleted


def _load_base(conn: Connection) -> tuple[int, int, dict[str, dict], Optional[int]]:
    """Tra cứu khách/cửa hàng/xe/điểm giao bằng email, tên, biển số."""
    customer_id = conn.execute(
        text("SELECT id FROM users WHERE email = :email"), {"email": CUSTOMER_EMAIL}
    ).scalar()
    if customer_id is None:
        raise RuntimeError(
            f"Thiếu tài khoản khách nền ({CUSTOMER_EMAIL}). "
            "Chạy seed nền trước: từ backend, python -c "
            "'from app.db.seed_data import seed_default_accounts; seed_default_accounts()'"
        )
    all_plates = MOTORBIKE_PLATES + CAR_PLATES
    vehicle_rows = conn.execute(
        text(
            """
            SELECT id, store_id, plate_number, vehicle_type, brand, model,
                   price_per_day, price_per_hour, current_status
            FROM vehicles WHERE plate_number IN :plates
            """
        ),
        {"plates": all_plates},
    ).mappings()
    vehicles = {str(row["plate_number"]): dict(row) for row in vehicle_rows}
    missing = [plate for plate in all_plates if plate not in vehicles]
    if missing:
        raise RuntimeError(
            "Thiếu xe nền theo biển số: "
            + ", ".join(missing)
            + ". Chạy seed nền trước: python -c "
            "'from app.db.seed_vehicles_delivery import seed_vehicles_and_delivery; "
            "seed_vehicles_and_delivery()'"
        )
    first_plate = all_plates[0]
    base_store_id = int(vehicles[first_plate]["store_id"])
    store = conn.execute(
        text("SELECT id, name FROM stores WHERE id = :id AND UPPER(status) = 'APPROVED'"),
        {"id": base_store_id},
    ).mappings().first()
    if store is None:
        raise RuntimeError(
            f"Cửa hàng {base_store_id} của xe nền không ở trạng thái APPROVED."
        )
    for plate, vehicle in vehicles.items():
        if int(vehicle["store_id"]) != base_store_id:
            raise RuntimeError(
                f"Xe {plate} không cùng cửa hàng với xe nền {first_plate}."
            )

    delivery_point_id = conn.execute(
        text(
            "SELECT id FROM delivery_points WHERE store_id = :store_id AND is_active = 1 "
            "ORDER BY id LIMIT 1"
        ),
        {"store_id": base_store_id},
    ).scalar()
    if delivery_point_id is None:
        raise RuntimeError("Cửa hàng nền chưa có điểm giao nhận hoạt động.")

    return int(customer_id), int(store["id"]), vehicles, (
        int(delivery_point_id) if delivery_point_id is not None else None
    )


def _money_values(
    vehicle: dict, start_time: datetime, end_time: datetime, delivery_fee: Decimal
) -> tuple[Decimal, Decimal, Decimal]:
    fake_vehicle = SimpleNamespace(
        price_per_day=vehicle["price_per_day"],
        price_per_hour=vehicle["price_per_hour"],
    )
    rental = calculate_rental_amount(fake_vehicle, start_time, end_time)
    deposit = calculate_deposit_amount(rental)
    total = (rental + delivery_fee).quantize(Decimal("0.01"))
    return rental, deposit, total


def _history_steps(
    spec: BookingSpec,
    *,
    created_at: datetime,
    start_time: datetime,
    end_time: datetime,
    hold_expires_at: Optional[datetime],
) -> list[tuple[Optional[str], str, str, datetime]]:
    """Trả chuỗi (from, to, actor, time) dẫn tới trạng thái hiện tại."""
    steps: list[tuple[Optional[str], str, str, datetime]] = [
        (None, "PENDING_PAYMENT", CANCEL_ACTOR_CUSTOMER, created_at)
    ]
    paid = spec.payment_status == "SUCCESS"
    if paid or spec.status in {"PENDING_STORE_CONFIRM", "BOOKED"}:
        after_payment = (
            spec.status
            if spec.status in {"PENDING_STORE_CONFIRM", "BOOKED"}
            else "DEPOSIT_PAID"
        )
        steps.append(
            (
                "PENDING_PAYMENT",
                after_payment,
                CANCEL_ACTOR_CUSTOMER,
                created_at + timedelta(minutes=10),
            )
        )
    if spec.status in {
        "CONFIRMED",
        "IN_PROGRESS",
        "PENDING_SETTLEMENT",
        "COMPLETED",
        "DISPUTED",
    }:
        steps.append(
            (
                "DEPOSIT_PAID",
                "CONFIRMED",
                CANCEL_ACTOR_STORE,
                created_at + timedelta(minutes=20),
            )
        )
    if spec.status in {"IN_PROGRESS", "PENDING_SETTLEMENT", "COMPLETED"}:
        steps.append(("CONFIRMED", "IN_PROGRESS", CANCEL_ACTOR_STORE, start_time))
    if spec.status in {"PENDING_SETTLEMENT", "COMPLETED"}:
        steps.append(
            ("IN_PROGRESS", "PENDING_SETTLEMENT", CANCEL_ACTOR_STORE, end_time)
        )
    if spec.status == "COMPLETED":
        steps.append(
            (
                "PENDING_SETTLEMENT",
                "COMPLETED",
                CANCEL_ACTOR_ADMIN,
                end_time + timedelta(minutes=5),
            )
        )
    if spec.status == "CANCELLED":
        steps.append(
            (
                "DEPOSIT_PAID",
                "CANCELLED",
                CANCEL_ACTOR_CUSTOMER,
                created_at + timedelta(minutes=30),
            )
        )
    if spec.status == "REJECTED":
        steps.append(
            (
                "DEPOSIT_PAID",
                "REJECTED",
                CANCEL_ACTOR_STORE,
                created_at + timedelta(minutes=30),
            )
        )
    if spec.status == "DISPUTED":
        steps.append(
            (
                "CONFIRMED",
                "DISPUTED",
                CANCEL_ACTOR_ADMIN,
                created_at + timedelta(minutes=40),
            )
        )
    if spec.status == "EXPIRED":
        expiry_time = hold_expires_at or created_at + timedelta(hours=1)
        steps.append(("PENDING_PAYMENT", "EXPIRED", CANCEL_ACTOR_SYSTEM, expiry_time))
    return steps


def _vehicle_target_status(status: str) -> str:
    if status == "IN_PROGRESS":
        return "RENTED"
    if status in {
        "PENDING_PAYMENT",
        "DEPOSIT_PAID",
        "PENDING_STORE_CONFIRM",
        "CONFIRMED",
        "DISPUTED",
        "BOOKED",
    }:
        return "RESERVED"
    return "AVAILABLE"


def seed_once(conn: Connection, *, now: datetime) -> dict[str, int]:
    """Tạo các đơn mẫu; bỏ qua logical code đã tồn tại."""
    customer_id, store_id, vehicles, delivery_point_id = _load_base(conn)
    specs = build_specs()
    existing_codes = {
        str(row["reason"]).split(":", 1)[1].split("|", 1)[0]
        for row in conn.execute(
            text(
                "SELECT reason FROM booking_status_history WHERE reason LIKE :mark"
            ),
            {"mark": f"{DEMO_TAG}:%"},
        ).mappings()
        if ":" in str(row["reason"])
    }

    added = {table: 0 for table in TABLES_IN_SCOPE}
    skipped = 0
    by_status: dict[str, int] = {}

    for spec in specs:
        if spec.code in existing_codes:
            skipped += 1
            print(f"  BỎ QUA {spec.code} (đã tồn tại)")
            continue
        if spec.with_delivery and delivery_point_id is None:
            raise RuntimeError("Không tìm thấy điểm giao nhận để tạo đơn có phí giao.")

        vehicle = vehicles[spec.plate]
        start_time = now + timedelta(hours=spec.start_hours)
        end_time = start_time + timedelta(hours=spec.duration_hours)
        if start_time >= end_time:
            raise RuntimeError(f"Khoảng thời gian không hợp lệ cho {spec.code}.")

        hold_expires_at = (
            now + timedelta(minutes=spec.hold_minutes)
            if spec.hold_minutes is not None
            else None
        )
        delivery_fee = Decimal("0.00")
        if spec.with_delivery:
            fee = conn.execute(
                text("SELECT delivery_fee FROM delivery_points WHERE id = :id"),
                {"id": delivery_point_id},
            ).scalar()
            delivery_fee = Decimal(str(fee or 0)).quantize(Decimal("0.01"))

        rental, deposit, total = _money_values(
            vehicle, start_time, end_time, delivery_fee
        )
        cancelled_at = now if spec.status in {"CANCELLED", "REJECTED"} else None

        booking_id = _insert(
            conn,
            TABLE_BOOKINGS,
            {
                "customer_id": customer_id,
                "vehicle_id": vehicle["id"],
                "store_id": store_id,
                "delivery_point_id": delivery_point_id if spec.with_delivery else None,
                "start_time": start_time,
                "end_time": end_time,
                "hold_expires_at": hold_expires_at,
                "status": spec.status,
                "rental_amount": rental,
                "delivery_fee": delivery_fee,
                "deposit_amount": deposit,
                "total_amount": total,
                "cancelled_at": cancelled_at,
                "cancelled_by": (
                    CANCEL_ACTOR_STORE
                    if spec.status == "REJECTED"
                    else CANCEL_ACTOR_CUSTOMER
                    if spec.status == "CANCELLED"
                    else None
                ),
                "cancel_reason": f"{spec.marker}|{spec.note}",
            },
        )
        added[TABLE_BOOKINGS] += 1
        by_status[spec.status] = by_status.get(spec.status, 0) + 1

        event_times = [step[3] for step in _history_steps(
            spec,
            created_at=min(
                now - timedelta(hours=2),
                start_time - timedelta(hours=2),
                (hold_expires_at - timedelta(hours=1))
                if hold_expires_at is not None
                else now - timedelta(hours=2),
            ),
            start_time=start_time,
            end_time=end_time,
            hold_expires_at=hold_expires_at,
        )]
        created_at = min(event_times)
        for from_status, to_status, actor, changed_at in _history_steps(
            spec,
            created_at=created_at,
            start_time=start_time,
            end_time=end_time,
            hold_expires_at=hold_expires_at,
        ):
            _insert(
                conn,
                TABLE_HISTORIES,
                {
                    "booking_id": booking_id,
                    "from_status": from_status,
                    "to_status": to_status,
                    "changed_by": actor,
                    "changed_by_user_id": customer_id if actor == CANCEL_ACTOR_CUSTOMER else None,
                    "reason": f"{spec.marker}|{from_status or 'NEW'}->{to_status}",
                    "created_at": changed_at,
                },
            )
            added[TABLE_HISTORIES] += 1

        if spec.status == "EXPIRED":
            reservation_status = "EXPIRED"
            schedule_status = "CANCELLED"
        elif spec.status in {"CANCELLED", "REJECTED"}:
            reservation_status = "CANCELLED"
            schedule_status = "CANCELLED"
        elif spec.status == "COMPLETED":
            reservation_status = "COMPLETED"
            schedule_status = "COMPLETED"
        elif spec.status in {"DEPOSIT_PAID", "CONFIRMED", "IN_PROGRESS", "PENDING_SETTLEMENT", "DISPUTED", "BOOKED"}:
            reservation_status = "CONFIRMED"
            schedule_status = "ACTIVE"
        else:
            reservation_status = "ACTIVE"
            schedule_status = "ACTIVE"

        reservation_id = _insert(
            conn,
            TABLE_RESERVATIONS,
            {
                "vehicle_id": vehicle["id"],
                "customer_id": customer_id,
                "booking_id": booking_id,
                "start_time": start_time,
                "end_time": end_time,
                "expires_at": hold_expires_at or start_time,
                "status": reservation_status,
                "created_at": created_at,
                "updated_at": now,
            },
        )
        added[TABLE_RESERVATIONS] += 1

        _insert(
            conn,
            TABLE_SCHEDULES,
            {
                "vehicle_id": vehicle["id"],
                "booking_id": booking_id,
                "reservation_id": reservation_id,
                "schedule_type": "RENTAL",
                "start_time": start_time,
                "end_time": end_time,
                "status": schedule_status,
                "note": spec.marker,
                "created_at": created_at,
                "updated_at": now,
            },
        )
        added[TABLE_SCHEDULES] += 1

        payment_id: Optional[int] = None
        if spec.payment_status is not None:
            payment_id = _insert(
                conn,
                TABLE_PAYMENTS,
                {
                    "booking_id": booking_id,
                    "transaction_code": f"{CODE_PREFIX}{spec.suffix}-DEP",
                    "provider": "MOCK",
                    "provider_txn_id": f"{CODE_PREFIX}{spec.suffix}-PGW",
                    "amount": deposit,
                    "status": spec.payment_status,
                    "payment_method": "DEMO_MOCK",
                    "qr_code_url": None,
                    "bank_name": None,
                    "bank_bin": None,
                    "account_number": None,
                    "account_name": None,
                    "beneficiary_source": None,
                    "paid_at": now if spec.payment_status == "SUCCESS" else None,
                    "created_at": created_at,
                    "updated_at": now,
                },
            )
            added[TABLE_PAYMENTS] += 1

        if spec.refund_rate is not None and payment_id is not None:
            quote = calculate_refund_quote(
                booking_status="CONFIRMED",
                start_time=start_time,
                deposit_amount=deposit,
                paid_amount=deposit,
                already_refunded=Decimal("0"),
                cancelled_at=cancelled_at or now,
                cancelled_by=(
                    CANCEL_ACTOR_STORE
                    if spec.status == "REJECTED"
                    else CANCEL_ACTOR_CUSTOMER
                ),
                now=now,
            )
            _insert(
                conn,
                TABLE_REFUNDS,
                {
                    "booking_id": booking_id,
                    "payment_transaction_id": payment_id,
                    "amount": quote.amount,
                    "reason": f"{spec.marker}|{quote.policy_code}|{spec.note}",
                    "status": "SUCCESS",
                    "processed_by": None,
                    "processed_at": now,
                    "created_at": now,
                },
            )
            added[TABLE_REFUNDS] += 1

        if spec.settlement:
            due = max(total - deposit, Decimal("0.00")).quantize(Decimal("0.01"))
            if due > 0:
                _insert(
                    conn,
                    TABLE_PAYMENTS,
                    {
                        "booking_id": booking_id,
                        "transaction_code": f"{CODE_PREFIX}{spec.suffix}-SET",
                        "provider": "INTERNAL",
                        "provider_txn_id": None,
                        "amount": due,
                        "status": "SUCCESS",
                        "payment_method": "DEMO_NO_CHARGE" if due == 0 else "DEMO_CASH",
                        "paid_at": end_time + timedelta(minutes=5),
                        "created_at": end_time + timedelta(minutes=5),
                        "updated_at": now,
                    },
                )
                added[TABLE_PAYMENTS] += 1

        if spec.handover in {"CHECK_OUT", "BOTH"}:
            _insert(
                conn,
                TABLE_HANDOVERS,
                {
                    "protocol_code": f"{CODE_PREFIX}{spec.suffix}-OUT",
                    "booking_id": booking_id,
                    "protocol_type": "CHECK_OUT",
                    "store_agent_name": "Nhân viên cửa hàng DEMO",
                    "store_agent_phone": "0900000000",
                    "customer_name": "Khách hàng DEMO",
                    "customer_cccd": "DEMO-CCCD-001",
                    "customer_phone": "0900000001",
                    "customer_license": "DEMO-GPLX-001",
                    "handover_location": "Điểm giao nhận DEMO",
                    "vehicle_name": f"{vehicle['brand'] if 'brand' in vehicle else 'Xe'} {vehicle['model'] if 'model' in vehicle else ''}".strip(),
                    "license_plate": spec.plate,
                    "vehicle_category": vehicle["vehicle_type"],
                    "odo_checkout": 1000,
                    "fuel_checkout": "FULL",
                    "deposit_original": deposit,
                    "fee_overtime": Decimal("0.00"),
                    "fee_excess_km": Decimal("0.00"),
                    "fee_fuel": Decimal("0.00"),
                    "fee_cleaning": Decimal("0.00"),
                    "fee_damage": Decimal("0.00"),
                    "hold_fine_deposit": Decimal("0.00"),
                    "refund_immediate": Decimal("0.00"),
                    "signed_at": start_time,
                    "status": "COMPLETED",
                    "notes": f"{spec.marker}|CHECK_OUT",
                    "created_at": created_at,
                    "updated_at": now,
                },
            )
            added[TABLE_HANDOVERS] += 1

        if spec.handover == "BOTH":
            _insert(
                conn,
                TABLE_HANDOVERS,
                {
                    "protocol_code": f"{CODE_PREFIX}{spec.suffix}-IN",
                    "booking_id": booking_id,
                    "protocol_type": "CHECK_IN",
                    "store_agent_name": "Nhân viên cửa hàng DEMO",
                    "store_agent_phone": "0900000000",
                    "customer_name": "Khách hàng DEMO",
                    "customer_cccd": "DEMO-CCCD-001",
                    "customer_phone": "0900000001",
                    "customer_license": "DEMO-GPLX-001",
                    "handover_location": "Điểm giao nhận DEMO",
                    "vehicle_name": f"{vehicle['vehicle_type']} {spec.plate}",
                    "license_plate": spec.plate,
                    "vehicle_category": vehicle["vehicle_type"],
                    "odo_checkout": 1000,
                    "odo_checkin": 1200,
                    "fuel_checkout": "FULL",
                    "fuel_checkin": "3/4",
                    "deposit_original": deposit,
                    "fee_overtime": Decimal("0.00"),
                    "fee_excess_km": Decimal("0.00"),
                    "fee_fuel": Decimal("0.00"),
                    "fee_cleaning": Decimal("0.00"),
                    "fee_damage": Decimal("0.00"),
                    "hold_fine_deposit": Decimal("0.00"),
                    "refund_immediate": Decimal("0.00"),
                    "signed_at": end_time,
                    "status": "COMPLETED",
                    "notes": f"{spec.marker}|CHECK_IN",
                    "created_at": created_at,
                    "updated_at": now,
                },
            )
            added[TABLE_HANDOVERS] += 1

        if spec.complaint:
            complaint_id = _insert(
                conn,
                TABLE_COMPLAINTS,
                {
                    "booking_id": booking_id,
                    "reporter_id": customer_id,
                    "against_user_id": None,
                    "category": "RENTAL_ISSUE",
                    "subject": f"{spec.marker}|Khiếu nại demo",
                    "description": f"{spec.marker}|{spec.note}",
                    "status": "OPEN",
                    "priority": "HIGH",
                    "created_at": now,
                    "updated_at": now,
                },
            )
            added[TABLE_COMPLAINTS] += 1
            _insert(
                conn,
                TABLE_COMPLAINT_HISTORIES,
                {
                    "complaint_id": complaint_id,
                    "from_status": None,
                    "to_status": "OPEN",
                    "changed_by": customer_id,
                    "note": spec.marker,
                    "created_at": now,
                },
            )
            added[TABLE_COMPLAINT_HISTORIES] += 1

        target_status = _vehicle_target_status(spec.status)
        old_status = str(vehicle["current_status"] or "")
        if old_status != target_status:
            _insert(
                conn,
                TABLE_VEHICLE_HISTORIES,
                {
                    "vehicle_id": vehicle["id"],
                    "from_status": old_status or None,
                    "to_status": target_status,
                    "changed_by": f"{DEMO_TAG}|{spec.code}",
                    "reason": "DEMO_BOOKING_STATUS",
                    "note": f"{spec.marker}|prev={old_status}",
                    "created_at": now,
                },
            )
            conn.execute(
                text("UPDATE vehicles SET current_status = :status WHERE id = :id"),
                {"status": target_status, "id": vehicle["id"]},
            )
            added[TABLE_VEHICLE_HISTORIES] += 1

    print(f"Đã tạo {sum(added.values())} dòng dữ liệu mẫu; bỏ qua {skipped} đơn.")
    print("Số đơn theo trạng thái:")
    for status in sorted(by_status):
        print(f"  - {status}{_status_label(status)}: {by_status[status]}")
    print("Số dòng thêm mới theo bảng:")
    for table in TABLES_IN_SCOPE:
        print(f"  - {table}: {added[table]}")
    return added


def print_plan(now: datetime) -> None:
    """In kế hoạch cho --dry-run, không ghi DB."""
    print("=" * 76)
    print(f"{DEMO_TAG} | DRY RUN | không ghi dữ liệu")
    print("=" * 76)
    print(f"now = {now.isoformat(sep=' ')} (datetime.now() giờ địa phương)")
    print(f"Khách nền: {CUSTOMER_EMAIL}")
    print("Cửa hàng nền: lấy từ xe nền theo biển số, không hard-code ID")
    print(f"Số đơn dự kiến: {len(build_specs())}")
    for spec in build_specs():
        start = now + timedelta(hours=spec.start_hours)
        end = start + timedelta(hours=spec.duration_hours)
        print(
            f"  {spec.code:<28} {spec.status:<22} {spec.plate:<12} "
            f"{start:%d/%m %H:%M} -> {end:%d/%m %H:%M} | {spec.note}"
        )
    print("Dấu nhận diện: booking_status_history.reason, vehicle_schedules.note,")
    print("payment_transactions.transaction_code, handover_protocols.protocol_code.")
    print("=" * 76)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Seed đơn thuê mẫu nhiều trạng thái cho TF1AE49 (demo/dev Only)."
    )
    parser.add_argument("--dry-run", action="store_true", help="In kế hoạch, không ghi DB")
    parser.add_argument("--yes", action="store_true", help="Xác nhận ghi dữ liệu")
    parser.add_argument("--reset", action="store_true", help="Chỉ xóa dữ liệu mẫu TF1AE49")
    parser.add_argument(
        "--reseed", action="store_true", help="Reset rồi tạo lại dữ liệu mẫu"
    )
    args = parser.parse_args(argv)

    if len(argv if argv is not None else sys.argv[1:]) == 0:
        parser.print_help()
        print("\nKhông có tham số nên không ghi gì. Dùng --dry-run để xem kế hoạch.")
        return 0
    if args.reset and args.reseed:
        print("Không dùng --reset và --reseed cùng lúc.", file=sys.stderr)
        return 2
    if args.dry_run and args.reseed:
        print("--dry-run không đi cùng --reseed; dùng --dry-run riêng.", file=sys.stderr)
        return 2

    write_mode = args.reset or args.reseed or not args.dry_run
    database = assert_safe_environment(require_yes=args.yes, dry_run=args.dry_run)
    print(f"DB được phép thao tác: {database}")

    now = datetime.now()
    if args.dry_run:
        if args.reset:
            session = SessionLocal()
            try:
                describe_reset(session.connection())
            finally:
                session.close()
            print("DRY RUN reset: đã liệt kê số dòng, không xóa.")
        else:
            print_plan(now)
        return 0

    session = SessionLocal()
    try:
        with session.begin():
            conn = session.connection()
            if args.reseed:
                reset_demo_data(conn)
            if args.reset:
                reset_demo_data(conn)
            else:
                seed_once(conn, now=now)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
