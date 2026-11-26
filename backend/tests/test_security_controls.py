"""Kiểm thử các lớp bảo mật cốt lõi của RideHub:
1. Không hardcode secret trong mã nguồn & cấu hình .gitignore
2. Cấu hình CORS an toàn (cho phép localhost/127.0.0.1, chặn domain lạ, không trả '*' khi allow_credentials=True)
3. Giới hạn tần suất đăng nhập (Rate Limiting chống Brute-force trả HTTP 429)
"""
from pathlib import Path
import re
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth_rate_limit import auth_rate_limiter
from app.core.config import Settings, settings
from app.core.security import hash_password
from app.db.session import Base, get_db
from app.main import app
from app.models.user import User


class SecurityControlsTests(unittest.TestCase):
    def setUp(self):
        auth_rate_limiter.reset()
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)

        db = self.session_factory()
        db.add(User(
            id=1,
            email="customer@ridehub.vn",
            phone="0901234567",
            full_name="Customer Test",
            hashed_password=hash_password("password123"),
            status="active",
        ))
        db.commit()
        db.close()

        def override_get_db():
            session = self.session_factory()
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        auth_rate_limiter.reset()
        app.dependency_overrides.clear()
        self.engine.dispose()

    # 1. KIỂM TRA SECRET KHÔNG NẰM TRONG CODE
    def test_no_hardcoded_api_keys_in_frontend_config_and_gitignore(self):
        repo_root = Path(__file__).resolve().parents[2]
        fe_config = (repo_root / "frontend" / "js" / "config.js").read_text(encoding="utf-8")
        self.assertIsNone(
            re.search(r"AIza[0-9A-Za-z_-]{20,}", fe_config),
            "Phát hiện Firebase API Key hardcode trong frontend/js/config.js",
        )

        gitignore_text = (repo_root / "backend" / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(".env", gitignore_text)
        self.assertIn("serviceAccountKey.json", gitignore_text)

        # Kiểm tra validator tự thay thế placeholder secret bằng chuỗi ngẫu nhiên mạnh
        generated = Settings.replace_placeholder_secrets("CHANGE_ME_replace_with_a_strong_random_key")
        self.assertNotEqual(generated, "CHANGE_ME_replace_with_a_strong_random_key")
        self.assertGreaterEqual(len(generated), 40)

    # 2. KIỂM TRA CẤU HÌNH CORS
    def test_cors_allows_dev_origins_and_blocks_untrusted_origin(self):
        # Không trả về wildcard "*" khi allow_credentials=True
        self.assertNotIn("*", settings.cors_origin_list)

        # Origin hợp lệ (Live Server 5501)
        res_ok = self.client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:5501",
                "Access-Control-Request-Method": "GET",
            },
        )
        self.assertEqual(res_ok.status_code, 200)
        self.assertEqual(res_ok.headers.get("access-control-allow-origin"), "http://localhost:5501")
        self.assertEqual(res_ok.headers.get("access-control-allow-credentials"), "true")

        # Origin lạ không đáng tin cậy
        res_evil = self.client.options(
            "/api/health",
            headers={
                "Origin": "https://evil-attacker.com",
                "Access-Control-Request-Method": "POST",
            },
        )
        self.assertIsNone(res_evil.headers.get("access-control-allow-origin"))

    # 3. KIỂM TRA GIỚI HẠN TẦN SUẤT ĐĂNG NHẬP (RATE LIMITING)
    def test_login_rate_limiting_blocks_brute_force_with_429(self):
        max_attempts = settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS

        # Gửi các lần sai mật khẩu trong ngưỡng cho phép
        for i in range(max_attempts):
            res = self.client.post(
                "/api/auth/login",
                json={"email": "customer@ridehub.vn", "password": f"wrong_pass_{i}"},
                headers={"X-Forwarded-For": "203.0.113.10"},
            )
            self.assertEqual(res.status_code, 401, f"Lần {i + 1} phải trả 401 chứ không bị chặn sớm")

        # Lần vượt ngưỡng -> bị chặn với HTTP 429 & header Retry-After
        res_blocked = self.client.post(
            "/api/auth/login",
            json={"email": "customer@ridehub.vn", "password": "password123"},
            headers={"X-Forwarded-For": "203.0.113.10"},
        )
        self.assertEqual(res_blocked.status_code, 429)
        self.assertIn("Retry-After", res_blocked.headers)

        # IP khác vẫn đăng nhập bình thường
        res_other_ip = self.client.post(
            "/api/auth/login",
            json={"email": "customer@ridehub.vn", "password": "password123"},
            headers={"X-Forwarded-For": "203.0.113.99"},
        )
        self.assertEqual(res_other_ip.status_code, 200)


if __name__ == "__main__":
    unittest.main()
