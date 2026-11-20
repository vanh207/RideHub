import unittest
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.dependencies import get_current_admin, get_current_user
from app.db.session import Base, get_db
from app.models.driver_license import DriverLicense
from app.models.identity_document import IdentityDocument
from app.models.store import Store
from app.models.user import User
from app.routers.admin_reviews import router as admin_reviews_router


admin_review_test_app = FastAPI()
admin_review_test_app.include_router(admin_reviews_router, prefix="/api")


class AdminReviewTests(unittest.TestCase):
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
            email="customer@example.com",
            phone="0900000001",
            full_name="Customer Example",
            status="active",
        ))
        db.add(User(
            id=9,
            email="admin@example.com",
            phone="0900000009",
            full_name="Admin Example",
            status="active",
        ))
        db.add(Store(
            id=1,
            owner_user_id=1,
            name="Pending Store",
            status="PENDING",
        ))
        db.add(Store(
            id=2,
            owner_user_id=1,
            name="Approved Store",
            status="APPROVED",
        ))
        db.add(IdentityDocument(
            id=1,
            user_id=1,
            document_type="CCCD",
            document_number="012345678901",
            status="pending",
        ))
        db.add(DriverLicense(
            id=1,
            user_id=1,
            license_number="GPLX-123",
            license_class="A1",
            status="pending",
        ))
        db.commit()
        db.close()

        def override_get_db():
            session = self.session_factory()
            try:
                yield session
            finally:
                session.close()

        admin_review_test_app.dependency_overrides[get_db] = override_get_db
        admin_review_test_app.dependency_overrides[get_current_admin] = lambda: SimpleNamespace(id=9)
        self.client = TestClient(admin_review_test_app)

    def tearDown(self):
        self.client.close()
        admin_review_test_app.dependency_overrides.clear()
        self.engine.dispose()

    def test_queue_returns_pending_stores_and_customer_documents(self):
        response = self.client.get("/api/admin/reviews/queue")

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual([item["name"] for item in data["stores"]], ["Pending Store"])
        self.assertEqual(
            {item["resource_type"] for item in data["customers"]},
            {"identity_document", "driver_license"},
        )
        self.assertTrue(data["stores"][0]["business_license_url"].endswith("/1/business-license"))

    def test_customer_cannot_access_admin_queue(self):
        admin_review_test_app.dependency_overrides.pop(get_current_admin)
        admin_review_test_app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            id=1,
            role="customer",
        )

        response = self.client.get("/api/admin/reviews/queue")

        self.assertEqual(response.status_code, 403)

    def test_reject_requires_reason_and_records_reviewer(self):
        response = self.client.patch(
            "/api/admin/reviews/identity-documents/1",
            json={"status": "rejected", "reason": "   "},
        )
        self.assertEqual(response.status_code, 422)

        response = self.client.patch(
            "/api/admin/reviews/identity-documents/1",
            json={"status": "rejected", "reason": "Ảnh CCCD bị mờ"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["reject_reason"], "Ảnh CCCD bị mờ")

        db = self.session_factory()
        document = db.query(IdentityDocument).filter_by(id=1).one()
        self.assertEqual(document.status, "rejected")
        self.assertEqual(document.verified_by, 9)
        self.assertIsNotNone(document.verified_at)
        db.close()

    def test_approval_is_recorded_and_processed_item_cannot_be_reviewed_twice(self):
        response = self.client.patch(
            "/api/admin/reviews/stores/1",
            json={"status": "approved"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["status"], "APPROVED")

        second_response = self.client.patch(
            "/api/admin/reviews/stores/1",
            json={"status": "rejected", "reason": "Thiếu giấy tờ"},
        )
        self.assertEqual(second_response.status_code, 409)

        db = self.session_factory()
        store = db.query(Store).filter_by(id=1).one()
        self.assertEqual(store.approved_by, 9)
        self.assertIsNotNone(store.approved_at)
        db.close()


if __name__ == "__main__":
    unittest.main()
