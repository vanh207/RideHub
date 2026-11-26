"""Kiểm tra dữ liệu mẫu TF1AE49 trên DB demo/dev/test.

Chạy từ thư mục backend:
    DB_NAME=ridehub_test ../.venv/bin/python -m pytest tests/test_seed_demo_bookings.py -v

Test sẽ reset dữ liệu TF1AE49 trước và sau khi chạy; không đụng dữ liệu thật.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from scripts.seed_demo_bookings import (
    CODE_PREFIX,
    DEMO_TAG,
    TABLE_BOOKINGS,
    TABLE_COMPLAINTS,
    TABLE_HANDOVERS,
    TABLE_HISTORIES,
    TABLE_PAYMENTS,
    TABLE_REFUNDS,
    TABLE_RESERVATIONS,
    TABLE_SCHEDULES,
    TABLE_VEHICLE_HISTORIES,
    assert_safe_environment,
    build_specs,
    reset_demo_data,
    seed_once,
)
from app.main import app

MARK = f"{DEMO_TAG}:%"


def _skip_if_unsafe() -> None:
    try:
        assert_safe_environment(require_yes=False, dry_run=True)
    except RuntimeError as exc:
        pytest.skip(str(exc))


def _demo_bookings(db: Session) -> dict[str, dict[str, Any]]:
    db.rollback()
    rows = db.execute(
        text(
            """
            SELECT b.* FROM bookings b
            WHERE b.id IN (
                SELECT DISTINCT booking_id FROM booking_status_history WHERE reason LIKE :mark
            )
            """
        ),
        {"mark": MARK},
    ).mappings()
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        reason = db.execute(
            text(
                "SELECT reason FROM booking_status_history "
                "WHERE booking_id = :id AND reason LIKE :mark ORDER BY created_at LIMIT 1"
            ),
            {"id": row["id"], "mark": MARK},
        ).scalar()
        code = str(reason).split(":", 1)[1].split("|", 1)[0]
        result[code] = dict(row)
    return result


def _counts(db: Session) -> dict[str, int]:
    db.rollback()
    tables = (
        TABLE_BOOKINGS,
        TABLE_HISTORIES,
        TABLE_RESERVATIONS,
        TABLE_SCHEDULES,
        TABLE_PAYMENTS,
        TABLE_REFUNDS,
        TABLE_HANDOVERS,
        TABLE_COMPLAINTS,
        TABLE_VEHICLE_HISTORIES,
    )
    return {
        table: int(db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0)
        for table in tables
    }


def _base_counts(db: Session) -> tuple[int, int, int]:
    db.rollback()
    return tuple(
        int(db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0)
        for table in ("users", "stores", "vehicles")
    )


def _demo_marker_counts(db: Session) -> dict[str, int]:
    """Số dòng còn mang dấu TF1AE49; không phụ thuộc dữ liệu nền có sẵn."""
    db.rollback()
    queries = {
        "histories": (
            "SELECT COUNT(*) FROM booking_status_history WHERE reason LIKE :mark",
            {"mark": MARK},
        ),
        "schedules": (
            "SELECT COUNT(*) FROM vehicle_schedules WHERE note LIKE :mark",
            {"mark": MARK},
        ),
        "payments": (
            "SELECT COUNT(*) FROM payment_transactions WHERE transaction_code LIKE :code_mark",
            {"code_mark": f"{CODE_PREFIX}%"},
        ),
        "handovers": (
            "SELECT COUNT(*) FROM handover_protocols WHERE protocol_code LIKE :code_mark",
            {"code_mark": f"{CODE_PREFIX}%"},
        ),
        "complaints": (
            "SELECT COUNT(*) FROM complaints WHERE description LIKE :mark",
            {"mark": MARK},
        ),
        "vehicle_histories": (
            "SELECT COUNT(*) FROM vehicle_status_history WHERE note LIKE :note_mark",
            {"note_mark": f"{DEMO_TAG}%"},
        ),
    }
    return {
        name: int(db.execute(text(sql), params).scalar() or 0)
        for name, (sql, params) in queries.items()
    }


def _write(action) -> None:
    """Mỗi lần ghi dùng session mới để tránh transaction đọc còn mở."""
    db = SessionLocal()
    try:
        with db.begin():
            action(db.connection())
    finally:
        db.close()


@pytest.fixture(scope="module")
def seeded_db():
    """Seed lại dữ liệu mẫu cho module test, dọn dẹp khi kết thúc."""
    _skip_if_unsafe()
    db = SessionLocal()
    try:
        _write(lambda conn: reset_demo_data(conn))
        _write(lambda conn: seed_once(conn, now=datetime.now()))
        yield db
    finally:
        try:
            _write(lambda conn: reset_demo_data(conn))
        finally:
            db.close()


def test_TF1AE49_C1_du_trang_thai(seeded_db: Session) -> None:
    """Mọi trạng thái trong danh sách TF1AE49 đều có ít nhất một đơn."""
    bookings = _demo_bookings(seeded_db)
    actual = {str(row["status"]) for row in bookings.values()}
    expected = {spec.status for spec in build_specs()}
    assert expected <= actual, f"Thiếu trạng thái: {sorted(expected - actual)}"
    assert len(bookings) == len(build_specs())


def test_TF1AE49_C2_idempotent_va_reset(seeded_db: Session) -> None:
    """Chạy seed lần 2 không đổi số dòng; reset chỉ xóa dữ liệu có dấu DEMO."""
    before = _counts(seeded_db)
    base_before = _base_counts(seeded_db)

    _write(lambda conn: seed_once(conn, now=datetime.now()))

    assert _counts(seeded_db) == before

    _write(lambda conn: reset_demo_data(conn))

    assert _demo_bookings(seeded_db) == {}
    assert all(value == 0 for value in _demo_marker_counts(seeded_db).values())
    assert _base_counts(seeded_db) == base_before

    _write(lambda conn: seed_once(conn, now=datetime.now()))
    assert _counts(seeded_db) == before


def test_TF1AE49_C3_bat_bien_nhat_quan(seeded_db: Session) -> None:
    """Kiểm tra tiền, lịch, thanh toán, hoàn tiền, lịch sử và biên bản."""
    bookings = _demo_bookings(seeded_db)
    specs = {spec.code: spec for spec in build_specs()}
    assert set(bookings) == set(specs)

    terminal = {"CANCELLED", "EXPIRED", "REJECTED", "COMPLETED"}
    active_schedules: list[dict[str, Any]] = []

    for code, spec in specs.items():
        booking = bookings[code]
        booking_id = int(booking["id"])
        rental = Decimal(str(booking["rental_amount"]))
        delivery = Decimal(str(booking["delivery_fee"]))
        deposit = Decimal(str(booking["deposit_amount"]))
        total = Decimal(str(booking["total_amount"]))
        assert total == (rental + delivery).quantize(Decimal("0.01"))

        store_id = seeded_db.execute(
            text("SELECT store_id FROM vehicles WHERE id = :id"),
            {"id": booking["vehicle_id"]},
        ).scalar()
        assert int(store_id or 0) == int(booking["store_id"])

        payments = list(
            seeded_db.execute(
                text("SELECT * FROM payment_transactions WHERE booking_id = :id"),
                {"id": booking_id},
            ).mappings()
        )
        success_payments = [p for p in payments if p["status"] == "SUCCESS"]
        if spec.status == "PENDING_PAYMENT":
            assert payments and all(p["status"] == "PENDING" for p in payments)
        elif spec.status == "EXPIRED":
            assert not success_payments
        else:
            assert success_payments, f"Thiếu giao dịch cọc thành công cho {code}"
            paid = sum((Decimal(str(p["amount"])) for p in success_payments), Decimal("0"))
            assert paid >= deposit

        reservation = seeded_db.execute(
            text("SELECT * FROM vehicle_reservations WHERE booking_id = :id"),
            {"id": booking_id},
        ).mappings().first()
        assert reservation is not None
        if booking["hold_expires_at"] is not None:
            assert reservation["expires_at"] == booking["hold_expires_at"]

        schedules = list(
            seeded_db.execute(
                text("SELECT * FROM vehicle_schedules WHERE booking_id = :id"),
                {"id": booking_id},
            ).mappings()
        )
        active = [s for s in schedules if s["status"] == "ACTIVE"]
        if spec.status in terminal:
            assert not active, f"Đơn kết thúc {code} vẫn có schedule ACTIVE"
        else:
            assert len(active) == 1, f"Đơn {code} thiếu schedule ACTIVE"
            assert active[0]["start_time"] == booking["start_time"]
            assert active[0]["end_time"] == booking["end_time"]
            active_schedules.extend(active)

        if spec.refund_rate is not None:
            refunds = list(
                seeded_db.execute(
                    text("SELECT * FROM refunds WHERE booking_id = :id"),
                    {"id": booking_id},
                ).mappings()
            )
            assert len(refunds) == 1
            expected = (deposit * spec.refund_rate).quantize(Decimal("0.01"))
            assert Decimal(str(refunds[0]["amount"])) == expected
            assert Decimal(str(refunds[0]["amount"])) <= deposit

        histories = list(
            seeded_db.execute(
                text(
                    "SELECT from_status, to_status, changed_by, reason, created_at "
                    "FROM booking_status_history WHERE booking_id = :id "
                    "ORDER BY created_at, id"
                ),
                {"id": booking_id},
            ).mappings()
        )
        assert len(histories) >= 1
        assert histories[-1]["to_status"] == spec.status
        times = [row["created_at"] for row in histories]
        assert times == sorted(times)
        assert all(spec.marker in str(row["reason"]) for row in histories)

        if spec.status in {"IN_PROGRESS", "PENDING_SETTLEMENT", "COMPLETED"}:
            protocols = list(
                seeded_db.execute(
                    text("SELECT * FROM handover_protocols WHERE booking_id = :id"),
                    {"id": booking_id},
                ).mappings()
            )
            expected_protocols = 1 if spec.status == "IN_PROGRESS" else 2
            assert len(protocols) == expected_protocols
            assert all(p["status"] == "COMPLETED" for p in protocols)

        if spec.complaint:
            complaint = seeded_db.execute(
                text("SELECT * FROM complaints WHERE booking_id = :id"),
                {"id": booking_id},
            ).mappings().first()
            assert complaint is not None
            assert complaint["status"] == "OPEN"
            assert spec.marker in str(complaint["description"])

        if spec.settlement:
            assert any(
                p["provider"] == "INTERNAL" and p["status"] == "SUCCESS"
                for p in payments
            )

    buffer_delta = timedelta(minutes=settings.BOOKING_BUFFER_MINUTES)
    for index, left in enumerate(active_schedules):
        for right in active_schedules[index + 1 :]:
            if left["vehicle_id"] != right["vehicle_id"]:
                continue
            overlap = (
                left["start_time"] < right["end_time"] + buffer_delta
                and right["start_time"] < left["end_time"] + buffer_delta
            )
            assert not overlap, "Hai đơn chiếm lịch cùng xe bị giao nhau sau khi cộng đệm"


def test_TF1AE49_C4_api_tim_xe_phu_anhr(seeded_db: Session) -> None:
    """API tìm xe phản ánh đúng: đơn CONFIRMED chiếm xe, đơn CANCELLED nhả xe."""
    bookings = _demo_bookings(seeded_db)
    by_suffix = {code.split("-", 2)[2]: row for code, row in bookings.items()}
    confirmed = by_suffix["05-CONFIRMED"]
    cancelled = by_suffix["11-CANCEL-FULL"]

    params = {
        "start_time": confirmed["start_time"].isoformat(),
        "end_time": confirmed["end_time"].isoformat(),
        "page": 1,
        "page_size": 50,
    }
    response = TestClient(app).get("/api/vehicles/search", params=params)
    assert response.status_code == 200, response.text
    vehicle_ids = {item["id"] for item in response.json()["items"]}
    assert int(confirmed["vehicle_id"]) not in vehicle_ids

    cancelled_params = {
        "start_time": cancelled["start_time"].isoformat(),
        "end_time": cancelled["end_time"].isoformat(),
        "page": 1,
        "page_size": 50,
    }
    cancelled_response = TestClient(app).get(
        "/api/vehicles/search", params=cancelled_params
    )
    assert cancelled_response.status_code == 200, cancelled_response.text
    cancelled_ids = {item["id"] for item in cancelled_response.json()["items"]}
    assert int(cancelled["vehicle_id"]) in cancelled_ids
