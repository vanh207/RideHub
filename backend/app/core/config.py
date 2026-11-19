"""Đọc cấu hình từ file .env (hoặc biến môi trường).

Muốn thêm cấu hình mới: thêm 1 dòng vào class Settings + thêm vào .env.example.
"""
import secrets
from decimal import Decimal
from urllib.parse import quote_plus
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env", "../backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    APP_NAME: str = "RideHub API"

    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "app_db"

    # Chuỗi các origin cách nhau bằng dấu phẩy, hoặc "*"
    CORS_ORIGINS: str = "*"

    # Cổng thanh toán Sandbox (Mock Payment Gateway - TF19E3D)
    PAYMENT_GATEWAY_SECRET: str = Field(
        default_factory=lambda: secrets.token_urlsafe(48)
    )
    PAYMENT_MOCK_BASE_URL: str = "https://sandbox.ridehub.vn"

    # ---- Cổng thanh toán PayOS (Thanh toán tiền cọc - TF19EFA) ----
    PAYOS_CLIENT_ID: str = ""
    PAYOS_API_KEY: str = ""
    PAYOS_CHECKSUM_KEY: str = ""
    PAYOS_RETURN_URL: str = "http://localhost:3000/payment/success"
    PAYOS_CANCEL_URL: str = "http://localhost:3000/payment/cancel"

    # ---- Cấu hình Email (SMTP hoặc Mock) ----
    EMAIL_BACKEND: str = "mock"
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "no-reply@ridehub.vn"
    SMTP_FROM_NAME: str = "RideHub Notification"
    SMTP_TLS: bool = True

    # ---- JWT Cấu hình ----
    JWT_SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(48))
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ---- Firebase Admin SDK & Web API Key (Được đọc hoàn toàn từ .env) ----
    FIREBASE_CREDENTIALS_PATH: str = "serviceAccountKey.json"
    FIREBASE_WEB_API_KEY: str = ""
    FIREBASE_PROJECT_ID: str = ""
    FIREBASE_AUTH_DOMAIN: str = ""
    FIREBASE_STORAGE_BUCKET: str = ""

    # ---- Đặt xe & giữ chỗ (TF197DE) ----
    # FR-30: giữ chỗ mặc định 30 phút.
    BOOKING_HOLD_MINUTES: int = 30
    # BR-07: đệm 60 phút trước/sau mỗi lượt thuê.
    BOOKING_BUFFER_MINUTES: int = 60
    # BR-02: thời lượng thuê tối thiểu 4 giờ, tối đa 30 ngày.
    BOOKING_MIN_DURATION_HOURS: int = 4
    BOOKING_MAX_DURATION_DAYS: int = 30
    # BR-03: cọc 30% tiền thuê, tối thiểu 200.000đ, tối đa 1.000.000đ.
    BOOKING_DEPOSIT_RATE: Decimal = Decimal("0.30")
    BOOKING_DEPOSIT_MIN: Decimal = Decimal("200000")
    BOOKING_DEPOSIT_MAX: Decimal = Decimal("1000000")
    # SRS không nêu khoảng tối thiểu trước giờ nhận; đặt 0 phút.
    BOOKING_MIN_START_LEAD_MINUTES: int = 0
    # Thuê dưới 24 giờ thì dùng giá giờ nếu xe có cấu hình.
    BOOKING_HOURLY_MAX_HOURS: int = 24
    # Thử lại khi MySQL báo deadlock (1213) hoặc lock wait timeout (1205).
    BOOKING_LOCK_RETRY_ATTEMPTS: int = 3
    BOOKING_LOCK_RETRY_BASE_DELAY_SECONDS: float = 0.05

    @field_validator("PAYMENT_GATEWAY_SECRET", "JWT_SECRET_KEY", mode="before")
    @classmethod
    def replace_placeholder_secrets(cls, value: str) -> str:
        placeholders = {
            "",
            "change_me_replace_with_a_strong_random_key",
            "your_strong_random_jwt_secret_here",
            "your_mock_webhook_secret_here",
        }
        if not isinstance(value, str) or value.strip().lower() in placeholders:
            return secrets.token_urlsafe(48)
        return value

    @property
    def database_url(self) -> str:
        # mysql+pymysql://user:password@host:port/database
        return (
            f"mysql+pymysql://{self.DB_USER}:{quote_plus(self.DB_PASSWORD)}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        raw = [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
        if "*" in raw or not raw:
            return [
                "http://localhost:5500",
                "http://127.0.0.1:5500",
                "http://localhost:5501",
                "http://127.0.0.1:5501",
                "http://localhost:5502",
                "http://127.0.0.1:5502",
                "http://localhost:3000",
                "http://localhost:8000",
                "http://127.0.0.1:8000",
                "http://localhost:5173",
            ]
        return raw


settings = Settings()
