"""Lấy sự thật về index và DDL từ DB perf (không giả định theo model)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sqlalchemy import text

from db_guard import assert_safe_database, get_perf_url, make_perf_engine

TABLES = [
    "bookings",
    "vehicle_reservations",
    "vehicle_schedules",
    "vehicles",
    "stores",
    "delivery_points",
]
ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "docs/perf/TF199BD-index-hien-co.md"


def main() -> None:
    url = get_perf_url()
    engine = make_perf_engine(url)
    database = assert_safe_database(engine)
    lines = [
        "# TF199BD - Index hiện có trên DB perf",
        "",
        f"- Thời điểm lấy: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- Database: `{database}`",
        "",
    ]

    with engine.connect() as conn:
        version = conn.execute(text("SELECT VERSION()")).scalar()
        time_zone = conn.execute(text("SELECT @@session.time_zone")).scalar()
        lines.extend(
            [
                f"- MySQL `VERSION()`: `{version}`",
                f"- `@@session.time_zone`: `{time_zone}`",
                "",
                "> `EXPLAIN ANALYZE` yêu cầu MySQL 8.0.18+. Phiên bản này "
                + ("đáp ứng." if str(version).startswith("8.") else "không đáp ứng."),
                "",
            ]
        )
        for table in TABLES:
            lines.extend([f"## `{table}`", "", "### SHOW INDEX", ""])
            rows = conn.execute(text(f"SHOW INDEX FROM `{table}`")).mappings().all()
            lines.extend(
                [
                    "| Key_name | Seq_in_index | Column_name | Non_unique | Index_type |",
                    "|---|---:|---|---:|---|",
                ]
            )
            for row in rows:
                lines.append(
                    f"| `{row['Key_name']}` | {row['Seq_in_index']} | "
                    f"`{row['Column_name']}` | {row['Non_unique']} | "
                    f"{row['Index_type']} |"
                )
            lines.extend(["", "### SHOW CREATE TABLE", "", "```sql"])
            ddl_row = conn.execute(text(f"SHOW CREATE TABLE `{table}`")).mappings().first()
            ddl = next(iter(ddl_row.values()))
            lines.extend([str(ddl), "```", ""])

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Đã ghi {OUTPUT.relative_to(ROOT)} cho DB {database}")


if __name__ == "__main__":
    main()
