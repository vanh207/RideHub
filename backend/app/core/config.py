"""Đọc cấu hình từ file .env (hoặc biến môi trường).

Muốn thêm cấu hình mới: thêm 1 dòng vào class Settings + thêm vào .env.example.
"""
import secrets
from decimal import Decimal
from typing import Optional
from urllib.parse import quote_plus
from pydantic import Field, field_validator, model_validator
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
    PAYOS_RETURN_URL: str = "http://127.0.0.1:8000/frontend/payment-result.html"
    PAYOS_CANCEL_URL: str = "http://127.0.0.1:8000/frontend/payment-result.html"
    PAYOS_BANK_NAME: str = ""
    PAYOS_ACCOUNT_NUMBER: str = ""
    PAYOS_ACCOUNT_NAME: str = ""

    # ---- Cấu hình Email (SMTP hoặc Mock) ----
    EMAIL_BACKEND: str = "mock"
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "no-reply@ridehub.vn"
    SMTP_FROM_NAME: str = "RideHub Notification"
    SMTP_TLS: bool = True

    # ---- JWT & Giới hạn tần suất đăng nhập ----
    JWT_SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(48))
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    LOGIN_RATE_LIMIT_MAX_ATTEMPTS: int = 5
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 60

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

    # ---- Hủy đơn & hoàn tiền ----
    BOOKING_CANCEL_FREE_HOURS: int = 24
    BOOKING_CANCEL_PARTIAL_HOURS: int = 6
    BOOKING_CANCEL_PARTIAL_RATE: Decimal = Decimal("0.5")
    BOOKING_CANCEL_STORE_FAULT_RATE: Decimal = Decimal("1.0")

    # ---- Job tự hủy đơn hết hạn giữ chỗ ----
    BOOKING_EXPIRY_JOB_ENABLED: bool = True
    BOOKING_EXPIRY_JOB_INTERVAL_SECONDS: int = 60
    BOOKING_EXPIRY_JOB_BATCH_SIZE: int = 100

    # ---- Cấu hình Chatbot AI & Kho tri thức (Knowledge Base) ----
    AI_PROVIDER: str = "auto"  # "auto" | "gemini" | "openai" | "mock"
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    AI_MODEL_NAME: str = ""  # Để trống sẽ tự chọn theo provider (vd: gemini-2.5-flash / gpt-4o-mini)
    CHATBOT_RATE_LIMIT_PER_MINUTE: int = 20  # Tối đa 20 tin nhắn/phút mỗi session/IP
    CHATBOT_RATE_LIMIT_PER_DAY: int = 100    # Tối đa 100 tin nhắn/ngày mỗi session/IP
    CHATBOT_MAX_CONTEXT_MESSAGES: int = 10   # Số tin nhắn lịch sử gần nhất nạp vào prompt AI

    # ---- eKYC / xác thực danh tính (TASK_BONUS_FACECHECK) ----
    # Bật luồng eKYC ở dev; KYC_REQUIRED_FOR_BOOKING mặc định TẮT để không vỡ demo/test cũ.
    KYC_ENABLED: bool = True
    KYC_REQUIRED_FOR_BOOKING: bool = False

    KYC_FACE_PROVIDER: str = "manual"  # manual | mock | vendor
    KYC_MOCK_SCORE: float = 0.82       # Điểm cố định cho MockProvider, chưa hiệu chỉnh.
    KYC_MATCH_THRESHOLD: Optional[float] = None  # Chưa đặt: cần hiệu chỉnh trước khi dùng.
    KYC_VENDOR_BASE_URL: str = ""
    KYC_VENDOR_API_KEY: str = ""
    KYC_VENDOR_TIMEOUT_SECONDS: int = 10

    KYC_CONSENT_VERSION: str = "2026-11-v1"
    KYC_PRIVACY_CONTACT_EMAIL: str = "[ĐIỀN email nhóm]"
    KYC_LEGAL_REVIEWER: str = "[ĐIỀN tên nhóm trưởng/giảng viên]"

    KYC_SESSION_TTL_MINUTES: int = 15
    KYC_DAILY_ATTEMPT_LIMIT: int = 5
    KYC_MAX_UPLOAD_BYTES: int = 5 * 1024 * 1024
    KYC_MIN_IMAGE_WIDTH: int = 640
    KYC_MIN_IMAGE_HEIGHT: int = 480
    KYC_MAX_IMAGE_PIXELS: int = 20_000_000  # Chống decompression bomb.
    KYC_ID_ASPECT_MIN: float = 1.20
    KYC_ID_ASPECT_MAX: float = 2.00
    KYC_SELFIE_ASPECT_MIN: float = 0.50
    KYC_SELFIE_ASPECT_MAX: float = 2.00
    KYC_BLUR_CHECK_ENABLED: bool = True
    KYC_QR_CHECK_ENABLED: bool = True

    KYC_FACE_RETENTION_DAYS: int = 30
    KYC_ID_RETENTION_DAYS: int = 180
    KYC_PRIVATE_UPLOAD_DIR: str = "private_uploads/kyc"
    KYC_CLEANUP_JOB_ENABLED: bool = True
    KYC_CLEANUP_JOB_INTERVAL_SECONDS: int = 3600
    KYC_CLEANUP_BATCH_SIZE: int = 100

    @field_validator("KYC_FACE_PROVIDER", mode="before")
    @classmethod
    def normalize_kyc_provider(cls, value: object) -> str:
        return str(value or "manual").strip().lower()

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

    @model_validator(mode="after")
    def validate_kyc_settings(self) -> "Settings":
        if self.KYC_FACE_PROVIDER not in {"manual", "mock", "vendor"}:
            raise ValueError(
                "KYC_FACE_PROVIDER chỉ nhận manual, mock hoặc vendor. "
                f"Giá trị hiện tại: {self.KYC_FACE_PROVIDER}"
            )
        if self.KYC_FACE_PROVIDER == "vendor" and (
            not self.KYC_VENDOR_BASE_URL.strip() or not self.KYC_VENDOR_API_KEY.strip()
        ):
            raise ValueError(
                "Đã chọn KYC_FACE_PROVIDER=vendor nhưng thiếu KYC_VENDOR_BASE_URL "
                "hoặc KYC_VENDOR_API_KEY. Vui lòng cấu hình lại hoặc đổi về manual."
            )
        positive_fields = {
            "KYC_SESSION_TTL_MINUTES": self.KYC_SESSION_TTL_MINUTES,
            "KYC_DAILY_ATTEMPT_LIMIT": self.KYC_DAILY_ATTEMPT_LIMIT,
            "KYC_MAX_UPLOAD_BYTES": self.KYC_MAX_UPLOAD_BYTES,
            "KYC_MIN_IMAGE_WIDTH": self.KYC_MIN_IMAGE_WIDTH,
            "KYC_MIN_IMAGE_HEIGHT": self.KYC_MIN_IMAGE_HEIGHT,
            "KYC_MAX_IMAGE_PIXELS": self.KYC_MAX_IMAGE_PIXELS,
            "KYC_FACE_RETENTION_DAYS": self.KYC_FACE_RETENTION_DAYS,
            "KYC_ID_RETENTION_DAYS": self.KYC_ID_RETENTION_DAYS,
        }
        for name, value in positive_fields.items():
            if value <= 0:
                raise ValueError(f"{name} phải lớn hơn 0.")
        if not self.KYC_CONSENT_VERSION.strip():
            raise ValueError("KYC_CONSENT_VERSION không được để trống.")
        if self.KYC_MATCH_THRESHOLD is not None and not 0 <= self.KYC_MATCH_THRESHOLD <= 1:
            raise ValueError("KYC_MATCH_THRESHOLD phải nằm trong đoạn [0, 1] hoặc để trống.")
        return self

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
