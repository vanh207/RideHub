"""Đọc cấu hình từ file .env (hoặc biến môi trường).

Muốn thêm cấu hình mới: thêm 1 dòng vào class Settings + thêm vào .env.example.
"""
from urllib.parse import quote_plus
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    
    APP_NAME: str = "RideHub API"

    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "app_db"

    # Chuỗi các origin cách nhau bằng dấu phẩy, hoặc "*"
    CORS_ORIGINS: str = "*"
    # Cổng thanh toán Sandbox (Mock Payment Gateway - TF19E3D)
    PAYMENT_GATEWAY_SECRET: str = "ridehub_mock_secret_key_2026_tf19e3d"
    PAYMENT_MOCK_BASE_URL: str = "https://sandbox.ridehub.vn"

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
    JWT_SECRET_KEY: str = "CHANGE_ME_replace_with_a_strong_random_key"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ---- Firebase Admin SDK ----
    FIREBASE_CREDENTIALS_PATH: str = "serviceAccountKey.json"

    @property
    def database_url(self) -> str:
        # mysql+pymysql://user:password@host:port/database
        # quote_plus: để mật khẩu có ký tự đặc biệt (@, #, /...) không làm hỏng URL
        return (
            f"mysql+pymysql://{self.DB_USER}:{quote_plus(self.DB_PASSWORD)}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
