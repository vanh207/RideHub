"""Kiểm thử API Cấu hình Chính sách (/api/admin/policies) và Bộ lọc Nhật ký Audit (/api/admin/audit-logs)."""
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
from app.models.role import Role, UserRole
from app.models.system_policy import SystemPolicy
from app.models.user import User
from app.routers.audit_logs import router as audit_logs_router
from app.routers.policies import router as policies_router


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(AuditLogMiddleware)
    app.include_router(policies_router, prefix="/api")
    app.include_router(audit_logs_router, prefix="/api")
    return app


test_app = _build_app()


class AdminPoliciesAndAuditFilterTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)

        db = self.session_factory()
        r_cust = Role(id=1, code="customer", name="Khách thuê")
        r_admin = Role(id=2, code="admin", name="Quản trị viên")
        db.add_all([r_cust, r_admin])
        db.flush()

        db.add_all([
            User(id=1, email="customer@ridehub.vn", phone="0901111111", full_name="Khách", status="active"),
            User(id=9, email="admin@ridehub.vn", phone="0909999999", full_name="Admin", status="active"),
        ])
        db.flush()
        db.add_all([UserRole(user_id=1, role_id=1), UserRole(user_id=9, role_id=2)])
        db.commit()
        db.close()

        def override_get_db():
            session = self.session_factory()
            try:
                yield session
            finally:
                session.close()

        test_app.dependency_overrides[get_db] = override_get_db
        self.patcher = patch("app.middleware.audit_log.SessionLocal", self.session_factory)
        self.patcher.start()
        self.client = TestClient(test_app)

        self.admin_token = create_access_token({"sub": "9", "email": "admin@ridehub.vn", "role": "admin"})
        self.cust_token = create_access_token({"sub": "1", "email": "customer@ridehub.vn", "role": "customer"})

    def tearDown(self):
        self.client.close()
        self.patcher.stop()
        test_app.dependency_overrides.clear()
        self.engine.dispose()

    def test_policies_rbac_and_crud_with_audit_log(self):
        # Customer bị chặn 403
        res_cust = self.client.get(
            "/api/admin/policies",
            headers={"Authorization": f"Bearer {self.cust_token}"},
        )
        self.assertEqual(res_cust.status_code, 403)

        # Admin lấy danh sách chính sách mặc định
        res_list = self.client.get(
            "/api/admin/policies",
            headers={"Authorization": f"Bearer {self.admin_token}"},
        )
        self.assertEqual(res_list.status_code, 200)
        items = res_list.json()["data"]
        self.assertGreaterEqual(len(items), 9)

        # Admin cập nhật tỷ lệ cọc & giới hạn đăng nhập
        res_upd = self.client.put(
            "/api/admin/policies",
            json={
                "updates": [
                    {"policy_key": "booking_deposit_rate_percent", "value": "35"},
                    {"policy_key": "login_rate_limit_max_attempts", "value": "8"},
                ]
            },
            headers={"Authorization": f"Bearer {self.admin_token}"},
        )
        self.assertEqual(res_upd.status_code, 200)
        updated_map = {x["policy_key"]: x["value"] for x in res_upd.json()["data"]}
        self.assertEqual(updated_map["booking_deposit_rate_percent"], "35")
        self.assertEqual(updated_map["login_rate_limit_max_attempts"], "8")

        # Kiểm tra AuditLog đã tự động ghi lại thao tác POLICY_UPDATE
        res_logs = self.client.get(
            "/api/admin/audit-logs?action=POLICY_UPDATE",
            headers={"Authorization": f"Bearer {self.admin_token}"},
        )
        self.assertEqual(res_logs.status_code, 200)
        logs = res_logs.json()["items"]
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["user_email"], "admin@ridehub.vn")
        self.assertEqual(logs[0]["status"], "SUCCESS")

    def test_audit_log_filter_by_time_and_actor(self):
        now = datetime.now()
        db = self.session_factory()
        db.add_all([
            AuditLog(
                user_id=9,
                user_email="admin@ridehub.vn",
                user_role="admin",
                action="REVIEW_APPROVE",
                resource_type="stores",
                resource_id="1",
                http_method="PATCH",
                endpoint="/api/admin/reviews/stores/1",
                status_code=200,
                status="SUCCESS",
                created_at=now - timedelta(days=10),
            ),
            AuditLog(
                user_id=2,
                user_email="owner@ridehub.vn",
                user_role="store_owner",
                action="VEHICLE_STATUS_CHANGE",
                resource_type="vehicle",
                resource_id="5",
                http_method="POST",
                endpoint="/api/vehicles/5/status",
                status_code=200,
                status="SUCCESS",
                created_at=now - timedelta(hours=2),
            ),
        ])
        db.commit()
        db.close()

        # Lọc theo người thao tác (owner@ridehub.vn) + thời gian (trong 24h qua)
        from_iso = (now - timedelta(days=1)).isoformat()
        res = self.client.get(
            f"/api/admin/audit-logs?search=owner@ridehub.vn&from_date={from_iso}",
            headers={"Authorization": f"Bearer {self.admin_token}"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["items"][0]["action"], "VEHICLE_STATUS_CHANGE")
        self.assertEqual(data["items"][0]["user_email"], "owner@ridehub.vn")


if __name__ == "__main__":
    unittest.main()
