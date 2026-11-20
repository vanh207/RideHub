"""Xuất SQL thật do ORM sinh ra cho các kịch bản TF199BD."""
from __future__ import annotations

from pathlib import Path

from scenarios import (
    CONFLICT_SCENARIOS,
    SEARCH_SCENARIOS,
    build_conflict_stmt,
    build_count_stmt,
    build_select_stmt,
    compile_mysql,
)

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "docs/perf/TF199BD-sql-that.md"


def main() -> None:
    lines = [
        "# TF199BD - SQL thật do ORM sinh ra",
        "",
        "SQL dưới đây được biên dịch từ chính các statement trong `app.crud.vehicle` ",
        "bằng `literal_binds=True` và dialect MySQL. Đây là câu lệnh dùng để đo, ",
        "không phải SQL viết tay để tối ưu.",
        "",
    ]

    for code, scenario in SEARCH_SCENARIOS.items():
        lines.extend(
            [
                f"## {code} - {scenario.description}",
                "",
                f"- Thời gian: `{scenario.start_time}` -> `{scenario.end_time}`",
                f"- Khu vực: `{scenario.area}`; loại xe: `{scenario.vehicle_type}`; "
                f"giá: `{scenario.min_price}` -> `{scenario.max_price}`",
                f"- Sắp xếp: `{scenario.sort}`; trang: `{scenario.page}`; "
                f"kích thước trang: `{scenario.page_size}`",
                "",
                "### COUNT",
                "",
                "```sql",
                compile_mysql(build_count_stmt(scenario)) + ";",
                "```",
                "",
                "### SELECT",
                "",
                "```sql",
                compile_mysql(build_select_stmt(scenario)) + ";",
                "```",
                "",
            ]
        )

    for code, scenario in CONFLICT_SCENARIOS.items():
        lines.extend(
            [
                f"## {code} - {scenario.description}",
                "",
                f"- Xe: `{scenario.vehicle_id}`; thời gian: `{scenario.start_time}` "
                f"-> `{scenario.end_time}`",
                "",
                "### SELECT",
                "",
                "```sql",
                compile_mysql(build_conflict_stmt(scenario)) + ";",
                "```",
                "",
            ]
        )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Đã ghi {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
