"""So sánh kết quả SQL gốc và SQL sau khi thêm hint/index cho TF199BD."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

from db_guard import assert_safe_database, get_perf_url, make_perf_engine
from scenarios import (
    CONFLICT_SCENARIOS,
    SEARCH_SCENARIOS,
    build_conflict_stmt,
    build_count_stmt,
    build_select_stmt,
    compile_mysql,
)

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "docs/perf/TF199BD-kiem-chung-tuong-duong.json"
HINT = "FORCE INDEX (ix_bookings_end_start_status_vehicle_hold)"


def for_driver(sql: str) -> str:
    return sql.replace("%", "%%")


def fingerprint(rows: list[tuple]) -> str:
    payload = json.dumps(rows, default=str, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def run(conn, sql: str):
    return conn.exec_driver_sql(for_driver(sql)).fetchall()


def compare(conn, original: str, after: str, label: str) -> dict:
    before_rows = [tuple(r) for r in run(conn, original)]
    after_rows = [tuple(r) for r in run(conn, after)]
    same = before_rows == after_rows
    return {
        "kich_ban": label,
        "giong_nhau": same,
        "so_dong": len(after_rows),
        "fingerprint_truoc": fingerprint(before_rows),
        "fingerprint_sau": fingerprint(after_rows),
    }


def main() -> None:
    engine = make_perf_engine(get_perf_url())
    database = assert_safe_database(engine)
    results = []
    with engine.connect() as conn:
        for code, scenario in SEARCH_SCENARIOS.items():
            count_after = compile_mysql(build_count_stmt(scenario))
            select_after = compile_mysql(build_select_stmt(scenario))
            results.append(
                compare(conn, count_after.replace(HINT, ""), count_after, f"{code}/COUNT")
            )
            results.append(
                compare(conn, select_after.replace(HINT, ""), select_after, f"{code}/SELECT")
            )

        for code, scenario in CONFLICT_SCENARIOS.items():
            conflict_after = compile_mysql(build_conflict_stmt(scenario))
            results.append(
                compare(
                    conn,
                    conflict_after.replace(HINT, ""),
                    conflict_after,
                    f"{code}/CONFLICT",
                )
            )

    report = {
        "thoi_diem": datetime.now().isoformat(timespec="seconds"),
        "database": database,
        "so_kich_ban": len(results),
        "tat_ca_giong_nhau": all(item["giong_nhau"] for item in results),
        "ket_qua": results,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"{report['so_kich_ban']} kịch bản, tất cả giống nhau: "
        f"{report['tat_ca_giong_nhau']}. Ghi {OUTPUT.relative_to(ROOT)}"
    )
    if not report["tat_ca_giong_nhau"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
