"""Chốt an toàn DB và tạo engine cho các script đo hiệu năng TF199BD."""
from __future__ import annotations

import os
from urllib.parse import urlparse

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.pool import NullPool

ALLOWED_DB_MARKERS = ("perf", "test")


def get_perf_url(env_var: str = "PERF_DATABASE_URL") -> str:
    """Đọc URL từ env và từ chối nếu tên DB không chứa perf/test."""
    value = os.environ.get(env_var)
    if not value:
        raise RuntimeError(f"Chưa đặt {env_var}; tuyệt đối không tự nối vào DB làm việc.")
    parsed = make_url(value)
    database = (parsed.database or "").lower()
    if not any(marker in database for marker in ALLOWED_DB_MARKERS):
        raise RuntimeError(
            f"Từ chối chạy: database='{database}' không chứa 'perf' hoặc 'test'."
        )
    return value


def make_perf_engine(url: str | None = None) -> Engine:
    """Tạo engine NullPool; mỗi lần đo dùng một connection riêng."""
    return create_engine(url or get_perf_url(), poolclass=NullPool, pool_pre_ping=True)


def assert_safe_database(engine: Engine) -> str:
    """Kiểm tra lại DB hiện tại ngay trên connection/server trước khi ghi dữ liệu."""
    with engine.connect() as conn:
        database = conn.execute(text("SELECT DATABASE()")).scalar() or ""
    database = str(database).lower()
    if not any(marker in database for marker in ALLOWED_DB_MARKERS):
        raise RuntimeError(
            f"Từ chối chạy: DB hiện tại='{database}' không chứa 'perf' hoặc 'test'."
        )
    return database


def db_name_from_url(url: str) -> str:
    """Trả về tên DB để ghi nhật ký, không trả về host/user/password."""
    return urlparse(url).path.lstrip("/") or "(none)"
