import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.dependencies import get_current_user
from app.core.store_errors import (
    StoreAPIError,
    store_api_error_handler,
    store_http_exception_handler,
)
from app.core.store_rate_limit import store_registration_rate_limiter
from app.db.session import Base, get_db
from app.middleware import store_upload
from app.models.store import Store
from app.models.user import User
from app.routers.stores import router as stores_router

test_app = FastAPI()
test_app.add_exception_handler(StoreAPIError, store_api_error_handler)
test_app.add_exception_handler(HTTPException, store_http_exception_handler)
test_app.include_router(stores_router, prefix="/api")

class StoreRegistrationTests(unittest.TestCase):
    def setUp(self):
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
            firebase_uid="test-firebase-user",
            email="owner@example.com",
            phone="0912345678",
            full_name="Store Owner",
            status="active",
        ))
        db.commit()
        db.close()
        self.user = SimpleNamespace(id=1, role="customer")

        self.upload_directory = tempfile.mkdtemp(prefix="ridehub-store-tests-")
        self.original_upload_root = store_upload.PRIVATE_UPLOAD_ROOT
        store_upload.PRIVATE_UPLOAD_ROOT = Path(self.upload_directory)
        store_registration_rate_limiter.reset()

        def override_get_db():
            session = self.session_factory()
            try:
                yield session
            finally:
                session.close()

        test_app.dependency_overrides[get_db] = override_get_db
        test_app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(test_app)

    def tearDown(self):
        self.client.close()
        test_app.dependency_overrides.clear()
        store_upload.PRIVATE_UPLOAD_ROOT = self.original_upload_root
        store_registration_rate_limiter.reset()
        shutil.rmtree(self.upload_directory, ignore_errors=True)
        self.engine.dispose()

    def _valid_form(self, **overrides):
        fields = {
            "name": "RideHub Motor Store",
            "description": "Cửa hàng cho thuê xe",
            "phone": "+84912345678",
            "email": "store@example.com",
            "province": "TP. Hồ Chí Minh",
            "district": "Quận 1",
            "ward": "Phường Bến Nghé",
            "address_detail": "45 Lê Duẩn",
            "business_license_number": "0123456789",
        }
        fields.update(overrides)
        return fields

    @staticmethod
    def _license_file(content=b"%PDF-1.7\nRideHub license"):
        return (
            "business_license_file",
            ("license.pdf", content, "application/octet-stream"),
        )

    def test_register_store_creates_pending_store_and_keeps_license_private(self):
        response = self.client.post(
            "/api/stores/register",
            data=self._valid_form(),
            files=[
                self._license_file(),
                ("logo", ("logo.jpg", b"\xff\xd8\xfflogo\xff\xd9", "image/jpeg")),
            ],
        )

        self.assertEqual(response.status_code, 201)
        result = response.json()
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["status"], "PENDING")
        self.assertTrue(result["data"]["created_at"])

        db = self.session_factory()
        store = db.query(Store).one()
        self.assertEqual(store.owner_id, 1)
        self.assertEqual(store.business_license_number, "0123456789")
        self.assertTrue(store.business_license_file.startswith("business_licenses/"))
        self.assertTrue((store_upload.PRIVATE_UPLOAD_ROOT / store.business_license_file).is_file())
        self.assertTrue(store.logo_file.startswith("store_logos/"))
        db.close()

        download = self.client.get(f"/api/stores/{store.id}/business-license")
        self.assertEqual(download.status_code, 200)
        self.assertTrue(download.content.startswith(b"%PDF-"))

    def test_register_store_requires_business_license_file(self):
        response = self.client.post(
            "/api/stores/register",
            data=self._valid_form(),
            files=[("logo", ("logo.jpg", b"\xff\xd8\xfflogo", "image/jpeg"))],
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("business_license_file", response.json()["errors"])

    def test_register_store_requires_authenticated_user(self):
        test_app.dependency_overrides.pop(get_current_user)
        response = self.client.post(
            "/api/stores/register",
            data=self._valid_form(),
            files=[self._license_file()],
        )

        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.json()["success"])

    def test_register_store_rejects_duplicate_business_license(self):
        db = self.session_factory()
        db.add(User(
            id=2,
            firebase_uid="second-user",
            email="second@example.com",
            phone="0987654321",
            full_name="Second Owner",
            status="active",
        ))
        db.add(Store(
            owner_user_id=2,
            name="Existing Rejected Store",
            business_license="0123456789",
            status="REJECTED",
        ))
        db.commit()
        db.close()

        response = self.client.post(
            "/api/stores/register",
            data=self._valid_form(),
            files=[self._license_file()],
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("Mã số doanh nghiệp/thuế", response.json()["message"])

    def test_register_store_rejects_duplicate_email_and_name(self):
        db = self.session_factory()
        db.add(Store(
            owner_user_id=1,
            name="Existing Email Store",
            business_license="1111111111",
            email="store@example.com",
            status="REJECTED",
        ))
        db.commit()
        db.close()
        email_response = self.client.post(
            "/api/stores/register",
            data=self._valid_form(business_license_number="2222222222"),
            files=[self._license_file()],
        )
        self.assertEqual(email_response.status_code, 409)
        self.assertIn("Email cửa hàng", email_response.json()["message"])

        db = self.session_factory()
        db.add(Store(
            owner_user_id=1,
            name="RideHub Motor Store",
            business_license="3333333333",
            email="other@example.com",
            status="REJECTED",
        ))
        db.commit()
        db.close()
        name_response = self.client.post(
            "/api/stores/register",
            data=self._valid_form(
                business_license_number="4444444444",
                email="another@example.com",
            ),
            files=[self._license_file()],
        )
        self.assertEqual(name_response.status_code, 409)
        self.assertIn("Tên cửa hàng", name_response.json()["message"])

    def test_register_store_rejects_owner_with_active_store(self):
        db = self.session_factory()
        db.add(Store(
            owner_user_id=1,
            name="Existing Store",
            business_license="1111111111",
            status="PENDING",
        ))
        db.commit()
        db.close()

        response = self.client.post(
            "/api/stores/register",
            data=self._valid_form(),
            files=[self._license_file()],
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("đang chờ duyệt hoặc đã được duyệt", response.json()["message"])

    def test_register_store_rejects_file_with_unsupported_real_mime(self):
        response = self.client.post(
            "/api/stores/register",
            data=self._valid_form(),
            files=[self._license_file(b"<html>not a PDF</html>")],
        )

        self.assertEqual(response.status_code, 415)
        self.assertIn("business_license_file", response.json()["errors"])

    def test_register_store_rejects_oversized_license(self):
        oversized_pdf = b"%PDF-1.7\n" + (b"x" * (5 * 1024 * 1024))
        response = self.client.post(
            "/api/stores/register",
            data=self._valid_form(),
            files=[self._license_file(oversized_pdf)],
        )

        self.assertEqual(response.status_code, 413)


if __name__ == "__main__":
    unittest.main()
