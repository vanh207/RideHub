"""Tự động kiểm tra và bổ sung các cột còn thiếu trong MySQL khi khởi động server.

Khắc phục triệt để lỗi:
- pymysql.err.OperationalError: (1054, "Unknown column 'stores.description' in 'field list'")
- Thiếu các cột mới trong bảng stores hoặc users do create_all() không tự sửa bảng đã có sẵn.
"""
import logging
from sqlalchemy import text
from app.db.session import engine

logger = logging.getLogger("ridehub.migration")

# Danh mục các cột cần đảm bảo tồn tại cho các bảng hiện hữu
REQUIRED_COLUMNS = {
    "users": [
        ("hashed_password", "VARCHAR(255) NULL"),
    ],
    "stores": [
        ("description", "TEXT NULL"),
        ("phone", "VARCHAR(20) NULL"),
        ("email", "VARCHAR(255) NULL"),
        ("district", "VARCHAR(100) NULL"),
        ("ward", "VARCHAR(100) NULL"),
        ("address_detail", "TEXT NULL"),
        ("business_license_file", "VARCHAR(255) NULL"),
        ("logo_file", "VARCHAR(255) NULL"),
    ],
    "payment_transactions": [
        ("bank_name", "VARCHAR(100) NULL"),
        ("bank_bin", "VARCHAR(20) NULL"),
        ("account_number", "VARCHAR(50) NULL"),
        ("account_name", "VARCHAR(255) NULL"),
        ("beneficiary_source", "VARCHAR(100) NULL"),
    ],
}


def auto_migrate_missing_columns() -> None:
    """Tự động phát hiện và thêm các cột còn thiếu vào MySQL nếu bảng đã tồn tại từ trước."""
    try:
        with engine.begin() as conn:
            for table_name, columns in REQUIRED_COLUMNS.items():
                # 1. Kiểm tra bảng có tồn tại trong database không
                check_table = conn.execute(
                    text(f"SHOW TABLES LIKE '{table_name}'")
                ).fetchone()
                if not check_table:
                    continue

                # 2. Lấy danh sách các cột hiện có
                col_result = conn.execute(text(f"SHOW COLUMNS FROM `{table_name}`"))
                existing_cols = {row[0].lower() for row in col_result.fetchall()}

                # 3. Thêm các cột còn thiếu
                for col_name, col_def in columns:
                    if col_name.lower() not in existing_cols:
                        conn.execute(
                            text(f"ALTER TABLE `{table_name}` ADD COLUMN `{col_name}` {col_def}")
                        )
                        logger.info(
                            "[DB Auto-Migration] Added column %s.%s",
                            table_name,
                            col_name,
                        )

    except Exception as exc:
        logger.warning("[DB Auto-Migration] Column migration failed: %s", exc)
