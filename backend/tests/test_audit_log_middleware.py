"""Bộ kiểm thử tích hợp cho AuditLogMiddleware & Admin Audit Log API.

Kiểm chứng các thao tác quan trọng được ghi Audit Log:
1. Đúng người (user_id, user_email, user_role, ip_address - qua Bearer JWT & Cookie)
2. Đúng thao tác (action, resource_type, resource_id, status_code, status, masking payload)
3. Đúng thời điểm (created_at nằm trong khoảng thời gian thực thi, execution_time_ms >= 0)
4. Ghi nhận cả trường hợp thành công (SUCCESS) và thất bại (FAILED)
5. API quản trị tra cứu & phân quyền Admin
"""
from datetime import datetime, timedelta
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.db.session import Base, get_db
from app.middleware.audit_log import AuditLogMiddleware
from app.models.audit_log import AuditLog
from app.models.booking import Booking
from app.models.driver_license import DriverLicense
from app.models.identity_document import IdentityDocument
from app.models.payment import PaymentTransaction
from app.models.role import Role, UserRole
from app.models.store import Store
from app.models.user import User
from app.models.vehicle import Vehicle
from app.routers.admin_reviews import router as admin_reviews_router
from app.routers.audit_logs import router as audit_logs_router
from app.routers.payment import router as payment_router
from app.routers.vehicles import router as vehicles_router


def _build_test_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(AuditLogMiddleware)
    app.include_router(admin_reviews_router, prefix="/api")
    app.include_router(audit_logs_router, prefix="/api")
    app.include_router(vehicles_router, prefix="/api")
    app.include_router(payment_router, prefix="/api")
    return app


audit_test_app = _build_test_app()


class AuditLogMiddlewareTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)

        db = self.session_factory()
        # 1. Roles
        role_customer = Role(id=1, code="customer", name="Khách thuê")
        role_owner = Role(id=2, code="store_owner", name="Chủ cửa hàng")
        role_admin = Role(id=3, code="admin", name="Quản trị viên")
        db.add_all([role_customer, role_owner, role_admin])
        db.flush()

        # 2. Users
        self.customer_user = User(
            id=1, email="customer@ridehub.vn", phone="0901111111", full_name="Khách Thuê Test", status="active"
        )
        self.owner_user = User(
            id=2, email="owner@ridehub.vn", phone="0902222222", full_name="Chủ Cửa Hàng Test", status="active"
        )
        self.admin_user = User(
            id=9, email="admin@ridehub.vn", phone="0909999999", full_name="Admin Hệ Thống", status="active"
        )
        db.add_all([self.customer_user, self.owner_user, self.admin_user])
        db.flush()

        db.add_all([
            UserRole(user_id=1, role_id=1),
            UserRole(user_id=2, role_id=2),
            UserRole(user_id=9, role_id=3),
        ])

        # 3. Store & KYC pending records
        db.add(Store(id=1, owner_user_id=2, name="Store Chờ Duyệt", address="Q1", city="HCM", status="PENDING"))
        db.add(DriverLicense(id=1, user_id=1, license_number="GPLX-999", license_class="A1", status="pending"))
        db.add(IdentityDocument(id=1, user_id=1, document_type="CCCD", document_number="079200001234", status="pending"))

        # 4. Vehicle
        db.add(Vehicle(
            id=1,
            store_id=1,
            vehicle_type="MOTORBIKE",
            plate_number="59A1-12345",
            brand="Honda",
            model="Vision",
            price_per_day=180000,
            current_status="AVAILABLE",
        ))

        # 5. Booking & Successful PaymentTransaction for Refund test
        db.add(Booking(
            id=1,
            customer_id=1,
            vehicle_id=1,
            store_id=1,
            start_time=datetime.now() + timedelta(days=1),
            end_time=datetime.now() + timedelta(days=3),
            rental_amount=360000,
            total_amount=360000,
            deposit_amount=200000,
            status="BOOKED",
        ))
        db.add(PaymentTransaction(
            id=1,
            booking_id=1,
            transaction_code="TXN-AUDIT-001",
            amount=200000,
            provider="SANDBOX",
            status="SUCCESS",
        ))
        db.add(PaymentTransaction(
            id=2,
            booking_id=1,
            transaction_code="TXN-AUDIT-PENDING",
            amount=200000,
            provider="SANDBOX",
            status="PENDING",
        ))
        db.commit()
        db.close()

        def override_get_db():
            session = self.session_factory()
            try:
                yield session
            finally:
                session.close()

        audit_test_app.dependency_overrides[get_db] = override_get_db
        self.session_patcher = patch("app.middleware.audit_log.SessionLocal", self.session_factory)
        self.session_patcher.start()
        self.client = TestClient(audit_test_app)

        self.admin_token = create_access_token({"sub": "9", "email": "admin@ridehub.vn", "role": "admin"})
        self.owner_token = create_access_token({"sub": "2", "email": "owner@ridehub.vn", "role": "store_owner"})
        self.customer_token = create_access_token({"sub": "1", "email": "customer@ridehub.vn", "role": "customer"})

    def tearDown(self):
        self.client.close()
        self.session_patcher.stop()
        audit_test_app.dependency_overrides.clear()
        self.engine.dispose()

    def _get_latest_audit_log(self) -> AuditLog:
        db = self.session_factory()
        try:
            return db.query(AuditLog).order_by(AuditLog.id.desc()).first()
        finally:
            db.close()

    def test_tc01_approve_store_records_admin_who_what_when(self):
        t_before = datetime.now() - timedelta(seconds=2)
        res = self.client.patch(
            "/api/admin/reviews/stores/1",
            json={"status": "approved"},
            headers={"Authorization": f"Bearer {self.admin_token}", "User-Agent": "RideHubTest/1.0"},
        )
        t_after = datetime.now() + timedelta(seconds=2)

        self.assertEqual(res.status_code, 200)
        log = self._get_latest_audit_log()
        self.assertIsNotNone(log)
        # Đúng người
        self.assertEqual(log.user_id, 9)
        self.assertEqual(log.user_email, "admin@ridehub.vn")
        self.assertEqual(log.user_role, "admin")
        self.assertEqual(log.user_agent, "RideHubTest/1.0")
        # Đúng thao tác
        self.assertEqual(log.action, "REVIEW_APPROVE")
        self.assertEqual(log.resource_type, "stores")
        self.assertEqual(log.resource_id, "1")
        self.assertEqual(log.http_method, "PATCH")
        self.assertEqual(log.endpoint, "/api/admin/reviews/stores/1")
        self.assertEqual(log.status_code, 200)
        self.assertEqual(log.status, "SUCCESS")
        # Đúng thời điểm
        self.assertGreaterEqual(log.created_at, t_before)
        self.assertLessEqual(log.created_at, t_after)
        self.assertIsNotNone(log.execution_time_ms)
        self.assertGreaterEqual(log.execution_time_ms, 0)

    def test_tc02_reject_driver_license_records_reason_and_actor(self):
        t_before = datetime.now() - timedelta(seconds=2)
        res = self.client.patch(
            "/api/admin/reviews/driver-licenses/1",
            json={"status": "rejected", "reason": "Ảnh GPLX bị mờ"},
            headers={"Authorization": f"Bearer {self.admin_token}"},
        )
        t_after = datetime.now() + timedelta(seconds=2)

        self.assertEqual(res.status_code, 200)
        log = self._get_latest_audit_log()
        self.assertIsNotNone(log)
        self.assertEqual(log.user_id, 9)
        self.assertEqual(log.action, "REVIEW_REJECT")
        self.assertEqual(log.resource_type, "driver-licenses")
        self.assertEqual(log.resource_id, "1")
        self.assertIn("Ảnh GPLX bị mờ", log.description)
        self.assertEqual(log.status, "SUCCESS")
        self.assertGreaterEqual(log.created_at, t_before)
        self.assertLessEqual(log.created_at, t_after)

    def test_tc03_vehicle_status_change_records_store_owner(self):
        t_before = datetime.now() - timedelta(seconds=2)
        res = self.client.post(
            "/api/vehicles/1/status",
            json={"new_status": "MAINTENANCE", "changed_by": "owner@ridehub.vn", "note": "Bảo dưỡng 5000km"},
            headers={"Authorization": f"Bearer {self.owner_token}"},
        )
        t_after = datetime.now() + timedelta(seconds=2)

        self.assertEqual(res.status_code, 200)
        log = self._get_latest_audit_log()
        self.assertIsNotNone(log)
        # Đúng người (Store Owner)
        self.assertEqual(log.user_id, 2)
        self.assertEqual(log.user_email, "owner@ridehub.vn")
        self.assertEqual(log.user_role, "store_owner")
        # Đúng thao tác
        self.assertEqual(log.action, "VEHICLE_STATUS_CHANGE")
        self.assertEqual(log.resource_type, "vehicle")
        self.assertEqual(log.resource_id, "1")
        self.assertEqual(log.status_code, 200)
        self.assertEqual(log.status, "SUCCESS")
        self.assertEqual(log.request_payload.get("new_status"), "MAINTENANCE")
        # Đúng thời điểm
        self.assertGreaterEqual(log.created_at, t_before)
        self.assertLessEqual(log.created_at, t_after)

    def test_tc04_payment_refund_records_audit_log(self):
        t_before = datetime.now() - timedelta(seconds=2)
        res = self.client.post(
            "/api/payments/refund",
            json={"transaction_code": "TXN-AUDIT-001", "amount": 200000, "reason": "Khách hủy đơn hợp lệ"},
            headers={"Authorization": f"Bearer {self.admin_token}"},
        )
        t_after = datetime.now() + timedelta(seconds=2)

        self.assertEqual(res.status_code, 200)
        log = self._get_latest_audit_log()
        self.assertIsNotNone(log)
        self.assertEqual(log.user_id, 9)
        self.assertEqual(log.user_email, "admin@ridehub.vn")
        self.assertEqual(log.action, "PAYMENT_REFUND")
        self.assertEqual(log.resource_type, "payment")
        self.assertEqual(log.resource_id, "TXN-AUDIT-001")
        self.assertEqual(log.status_code, 200)
        self.assertEqual(log.status, "SUCCESS")
        self.assertGreaterEqual(log.created_at, t_before)
        self.assertLessEqual(log.created_at, t_after)

    def test_tc05_failed_operation_still_logged_with_failed_status(self):
        res = self.client.post(
            "/api/payments/refund",
            json={"transaction_code": "TXN-AUDIT-PENDING", "amount": 200000, "reason": "Test giao dịch chưa thanh toán"},
            headers={"Authorization": f"Bearer {self.admin_token}"},
        )
        self.assertEqual(res.status_code, 400)
        log = self._get_latest_audit_log()
        self.assertIsNotNone(log)
        self.assertEqual(log.user_id, 9)
        self.assertEqual(log.action, "PAYMENT_REFUND")
        self.assertEqual(log.status_code, 400)
        self.assertEqual(log.status, "FAILED")

    def test_tc06_cookie_auth_and_sensitive_payload_masking(self):
        self.client.cookies.set("ridehub_token", self.owner_token)
        res = self.client.post(
            "/api/vehicles/1/status",
            json={
                "new_status": "MAINTENANCE",
                "changed_by": "owner@ridehub.vn",
                "note": "Kiểm tra che mật khẩu",
                "secret_key": "my_super_secret",
            },
        )
        # Note: VehicleStatusChangeRequest ignores extra field secret_key by default in Pydantic v2,
        # middleware reads raw JSON body before Pydantic strips it.
        self.assertEqual(res.status_code, 200)
        log = self._get_latest_audit_log()
        self.assertEqual(log.user_id, 2)
        self.assertEqual(log.user_email, "owner@ridehub.vn")
        self.assertEqual(log.request_payload.get("secret_key"), "********")

    def test_tc07_get_requests_not_logged_and_admin_query_rbac(self):
        # GET thông thường không ghi log rác
        res_q = self.client.get(
            "/api/admin/reviews/queue",
            headers={"Authorization": f"Bearer {self.admin_token}"},
        )
        self.assertEqual(res_q.status_code, 200)
        self.assertIsNone(self._get_latest_audit_log())

        # Tạo 1 bản ghi audit log
        self.client.patch(
            "/api/admin/reviews/stores/1",
            json={"status": "approved"},
            headers={"Authorization": f"Bearer {self.admin_token}"},
        )

        # Customer không được xem audit logs
        res_cust = self.client.get(
            "/api/admin/audit-logs",
            headers={"Authorization": f"Bearer {self.customer_token}"},
        )
        self.assertEqual(res_cust.status_code, 403)

        # Admin tra cứu thành công
        res_admin = self.client.get(
            "/api/admin/audit-logs",
            headers={"Authorization": f"Bearer {self.admin_token}"},
        )
        self.assertEqual(res_admin.status_code, 200)
        data = res_admin.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["items"][0]["action"], "REVIEW_APPROVE")
        self.assertEqual(data["items"][0]["user_email"], "admin@ridehub.vn")


if __name__ == "__main__":
    unittest.main()
