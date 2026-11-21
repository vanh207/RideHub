"""Đo EXPLAIN, EXPLAIN ANALYZE, Handler_read và latency cho bộ kịch bản TF199BD."""
from __future__ import annotations

import argparse
import json
import statistics
import time
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
ANALYZE_TABLES = [
    "bookings",
    "vehicle_reservations",
    "vehicle_schedules",
    "vehicles",
    "stores",
    "delivery_points",
]
HANDLER_PREFIX = "Handler_read"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("baseline", "after"), required=True)
    parser.add_argument("--repeats", type=int, default=30)
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def handler_status(conn) -> dict[str, int]:
    rows = conn.execute(text("SHOW SESSION STATUS LIKE 'Handler_read%'")).mappings().all()
    return {str(r["Variable_name"]): int(r["Value"]) for r in rows}


def handler_delta(before: dict[str, int], after: dict[str, int]) -> dict[str, int]:
    keys = sorted(set(before) | set(after))
    return {key: after.get(key, 0) - before.get(key, 0) for key in keys}


def for_driver(sql: str) -> str:
    """escape '%' để PyMySQL không hiểu nhầm LIKE '%area%' là placeholder."""
    return sql.replace("%", "%%")


def plain_explain(conn, sql: str) -> list[dict[str, str]]:
    rows = conn.exec_driver_sql("EXPLAIN " + for_driver(sql)).mappings().all()
    return [{str(k): ("" if v is None else str(v)) for k, v in row.items()} for row in rows]


def explain_analyze(conn, sql: str) -> str:
    rows = conn.exec_driver_sql("EXPLAIN ANALYZE " + for_driver(sql)).fetchall()
    return "\n".join(str(row[0]) for row in rows)


def measure_sql(conn, sql: str, repeats: int, warmup: int) -> dict:
    """Đo latency sau khi làm nóng cache và đọc delta Handler_read trên cùng session."""
    for _ in range(warmup):
        conn.exec_driver_sql(for_driver(sql)).fetchall()

    before = handler_status(conn)
    samples = []
    fetched_rows = 0
    first_value = None
    for _ in range(repeats):
        started = time.perf_counter()
        result = conn.exec_driver_sql(for_driver(sql)).fetchall()
        samples.append((time.perf_counter() - started) * 1000)
        if result:
            fetched_rows = len(result)
            first_value = str(result[0][0])
    after = handler_status(conn)

    ordered = sorted(samples)
    return {
        "repeat_count": repeats,
        "warmup_count": warmup,
        "median_ms": round(statistics.median(ordered), 3),
        "p95_ms": round(ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))], 3),
        "min_ms": round(ordered[0], 3),
        "max_ms": round(ordered[-1], 3),
        "fetched_rows_last_run": fetched_rows,
        "first_column_last_run": first_value,
        "handler_read_delta": handler_delta(before, after),
    }


def measure_statement(conn, sql: str, repeats: int, warmup: int) -> dict:
    return {
        "sql": sql,
        "explain": plain_explain(conn, sql),
        "explain_analyze": explain_analyze(conn, sql),
        "timing": measure_sql(conn, sql, repeats, warmup),
    }


def main() -> None:
    args = parse_args()
    if args.repeats < 1 or args.warmup < 0:
        raise SystemExit("--repeats phải >= 1 và --warmup phải >= 0")

    url = get_perf_url()
    engine = make_perf_engine(url)
    database = assert_safe_database(engine)

    with engine.begin() as conn:
        for table in ANALYZE_TABLES:
            conn.execute(text(f"ANALYZE TABLE `{table}`"))

    result = {
        "phase": args.phase,
        "measured_at": datetime.now().isoformat(timespec="seconds"),
        "database": database,
        "mysql_version": None,
        "dataset_counts": {},
        "repeats": args.repeats,
        "warmup": args.warmup,
        "scenarios": {},
    }

    with engine.connect() as conn:
        result["mysql_version"] = str(conn.execute(text("SELECT VERSION()")).scalar())
        for table in ANALYZE_TABLES:
            result["dataset_counts"][table] = int(
                conn.execute(text(f"SELECT COUNT(*) FROM `{table}`")).scalar()
            )

        for code, scenario in SEARCH_SCENARIOS.items():
            entry = {
                "description": scenario.description,
                "parameters": {
                    "start_time": str(scenario.start_time),
                    "end_time": str(scenario.end_time),
                    "area": scenario.area,
                    "vehicle_type": scenario.vehicle_type,
                    "min_price": scenario.min_price,
                    "max_price": scenario.max_price,
                    "sort": scenario.sort,
                    "page": scenario.page,
                    "page_size": scenario.page_size,
                    "now": str(scenario.now),
                },
            }
            entry["count"] = measure_statement(
                conn,
                compile_mysql(build_count_stmt(scenario)),
                args.repeats,
                args.warmup,
            )
            entry["select"] = measure_statement(
                conn,
                compile_mysql(build_select_stmt(scenario)),
                args.repeats,
                args.warmup,
            )
            entry["api_total_median_ms"] = round(
                entry["count"]["timing"]["median_ms"]
                + entry["select"]["timing"]["median_ms"],
                3,
            )
            result["scenarios"][code] = entry
            print(f"{code}: count={entry['count']['timing']['median_ms']}ms "
                  f"select={entry['select']['timing']['median_ms']}ms")

        for code, scenario in CONFLICT_SCENARIOS.items():
            entry = {
                "description": scenario.description,
                "parameters": {
                    "vehicle_id": scenario.vehicle_id,
                    "start_time": str(scenario.start_time),
                    "end_time": str(scenario.end_time),
                    "now": str(scenario.now),
                },
            }
            entry["conflict"] = measure_statement(
                conn,
                compile_mysql(build_conflict_stmt(scenario)),
                args.repeats,
                args.warmup,
            )
            result["scenarios"][code] = entry
            print(f"{code}: conflict={entry['conflict']['timing']['median_ms']}ms")

    output = args.output or ROOT / f"docs/perf/TF199BD-{args.phase}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Đã ghi {output.relative_to(ROOT) if output.is_relative_to(ROOT) else output}")


if __name__ == "__main__":
    main()
