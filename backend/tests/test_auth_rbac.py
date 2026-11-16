"""Test Suite: Kiểm thử Xác thực (Authentication) & Phân quyền truy cập (RBAC).

Dự án: RideHub - Nền tảng cho thuê xe máy và ô tô tự lái
Mục tiêu kiểm thử:
  1. Đăng nhập đúng (Valid Login): Admin, Store Owner, Store Staff, Customer.
  2. Đăng nhập sai (Invalid Login): Sai mật khẩu, sai email, tài khoản bị vô hiệu hóa, sai định dạng.
  3. Thiếu token hoặc token không hợp lệ: Không gửi token, token rác, token hết hạn, sai loại token.
  4. Truy cập trái quyền theo từng vai trò (RBAC): Kiểm tra ma trận quyền Admin, Store Owner, Store Staff, Customer.

Cách chạy:
  cd backend
  python tests/test_auth_rbac.py
"""
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

# Bổ sung thư mục gốc backend vào sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.session import Base, get_db
from app.models.user import User
from app.core.security import hash_password, create_access_token, create_refresh_token, _create_token

# =============================================================================
# KHỞI TẠO TEST DATABASE (SQLite In-Memory độc lập, cách ly hoàn toàn)
# =============================================================================
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)

# Tạo toàn bộ schema bảng
Base.metadata.create_all(bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Override dependency get_db của FastAPI app
app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

# =============================================================================
# DỮ LIỆU MẪU KIỂM THỬ (SEED DATA FOR TESTS)
# =============================================================================
TEST_USERS = [
    {
        "id": 1,
        "firebase_uid": "fb_uid_admin_01",
        "email": "admin@ridehub.vn",
        "phone": "0901000001",
        "full_name": "Nguyễn Quản Trị (Admin)",
        "password": "AdminPassword@123",
        "role": "admin",
        "status": "active",
    },
    {
        "id": 2,
        "firebase_uid": "fb_uid_owner_01",
        "email": "owner@ridehub.vn",
        "phone": "0902000001",
        "full_name": "Trần Chủ Xe (Store Owner)",
        "password": "OwnerPassword@123",
        "role": "store_owner",
        "status": "active",
    },
    {
        "id": 3,
        "firebase_uid": "fb_uid_staff_01",
        "email": "staff@ridehub.vn",
        "phone": "0903000001",
        "full_name": "Lê Nhân Viên (Store Staff)",
        "password": "StaffPassword@123",
        "role": "store_staff",
        "status": "active",
    },
    {
        "id": 4,
        "firebase_uid": "fb_uid_customer_01",
        "email": "customer@gmail.com",
        "phone": "0987654321",
        "full_name": "Phạm Khách Hàng (Customer)",
        "password": "CustomerPassword@123",
        "role": "customer",
        "status": "active",
    },
    {
        "id": 5,
        "firebase_uid": "fb_uid_disabled_01",
        "email": "banned@gmail.com",
        "phone": "0987654329",
        "full_name": "Tài Khoản Bị Khóa",
        "password": "BannedPassword@123",
        "role": "customer",
        "status": "inactive",  # Tài khoản bị vô hiệu hóa
    },
]


def seed_test_database():
    """Khởi tạo tài khoản kiểm thử vào CSDL."""
    db = TestingSessionLocal()
    db.query(User).delete()
    for u in TEST_USERS:
        user_record = User(
            id=u["id"],
            firebase_uid=u["firebase_uid"],
            email=u["email"],
            phone=u["phone"],
            full_name=u["full_name"],
            hashed_password=hash_password(u["password"]),
            role=u["role"],
            status=u["status"],
        )
        db.add(user_record)
    db.commit()
    db.close()


# =============================================================================
# RUNNER & TEST EXECUTION LOG
# =============================================================================
test_results: List[Dict[str, Any]] = []


def record_result(
    tc_id: str,
    category: str,
    name: str,
    endpoint: str,
    method: str,
    expected_status: int,
    actual_status: int,
    details: str,
    duration_ms: float,
):
    passed = expected_status == actual_status
    test_results.append(
        {
            "id": tc_id,
            "category": category,
            "name": name,
            "endpoint": f"{method} {endpoint}",
            "expected_status": expected_status,
            "actual_status": actual_status,
            "passed": passed,
            "details": details,
            "duration_ms": duration_ms,
        }
    )
    status_tag = "[PASS]" if passed else "[FAIL]"
    print(f"  {status_tag} {tc_id:<12} | {name:<45} | Expected: {expected_status} | Actual: {actual_status} ({duration_ms:.1f}ms)")


def run_all_tests():
    print("=" * 80)
    print(" RIDEHUB - KIỂM THỬ XÁC THỰC (AUTHENTICATION) & PHÂN QUYỀN (RBAC)")
    print(f" Thời gian thực thi: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    seed_test_database()

    # Lưu token đăng nhập của các vai trò để dùng cho nhóm RBAC
    tokens: Dict[str, str] = {}

    # -------------------------------------------------------------------------
    # NHÓM 1: ĐĂNG NHẬP ĐÚNG (VALID LOGIN)
    # -------------------------------------------------------------------------
    print("\n--- NHÓM 1: KIỂM THỬ ĐĂNG NHẬP ĐÚNG (VALID LOGIN) ---")

    roles_to_test = [
        ("TC_AUTH_001", "customer@gmail.com", "CustomerPassword@123", "customer", "Đăng nhập Customer hợp lệ"),
        ("TC_AUTH_002", "admin@ridehub.vn", "AdminPassword@123", "admin", "Đăng nhập Admin hợp lệ"),
        ("TC_AUTH_003", "owner@ridehub.vn", "OwnerPassword@123", "store_owner", "Đăng nhập Store Owner hợp lệ"),
        ("TC_AUTH_004", "staff@ridehub.vn", "StaffPassword@123", "store_staff", "Đăng nhập Store Staff hợp lệ"),
    ]

    for tc_id, email, password, expected_role, tc_name in roles_to_test:
        t0 = time.perf_counter()
        res = client.post("/auth/login", json={"email": email, "password": password})
        duration = (time.perf_counter() - t0) * 1000

        data = res.json().get("data", {}) if res.status_code == 200 else {}
        access_token = data.get("access_token", "")
        tokens[expected_role] = access_token

        role_match = data.get("role") == expected_role
        has_token = bool(access_token)
        passed_condition = res.status_code == 200 and role_match and has_token

        detail = f"Token nhận được: {access_token[:15]}... | Role: {data.get('role')}"
        record_result(
            tc_id=tc_id,
            category="Đăng nhập đúng",
            name=tc_name,
            endpoint="/auth/login",
            method="POST",
            expected_status=200,
            actual_status=res.status_code if passed_condition else 500,
            details=detail,
            duration_ms=duration,
        )

    # -------------------------------------------------------------------------
    # NHÓM 2: ĐĂNG NHẬP SAI (INVALID LOGIN)
    # -------------------------------------------------------------------------
    print("\n--- NHÓM 2: KIỂM THỬ ĐĂNG NHẬP SAI (INVALID LOGIN) ---")

    # TC_AUTH_005: Sai mật khẩu
    t0 = time.perf_counter()
    res = client.post("/auth/login", json={"email": "customer@gmail.com", "password": "WrongPassword@999"})
    duration = (time.perf_counter() - t0) * 1000
    record_result(
        "TC_AUTH_005",
        "Đăng nhập sai",
        "Đăng nhập sai mật khẩu",
        "/auth/login",
        "POST",
        401,
        res.status_code,
        res.json().get("detail", str(res.json())),
        duration,
    )

    # TC_AUTH_006: Email không tồn tại
    t0 = time.perf_counter()
    res = client.post("/auth/login", json={"email": "notfound@ridehub.vn", "password": "AnyPassword@123"})
    duration = (time.perf_counter() - t0) * 1000
    record_result(
        "TC_AUTH_006",
        "Đăng nhập sai",
        "Đăng nhập Email không tồn tại",
        "/auth/login",
        "POST",
        401,
        res.status_code,
        res.json().get("detail", str(res.json())),
        duration,
    )

    # TC_AUTH_007: Tài khoản bị vô hiệu hóa (status = 'inactive')
    t0 = time.perf_counter()
    res = client.post("/auth/login", json={"email": "banned@gmail.com", "password": "BannedPassword@123"})
    duration = (time.perf_counter() - t0) * 1000
    record_result(
        "TC_AUTH_007",
        "Đăng nhập sai",
        "Đăng nhập tài khoản bị vô hiệu hóa (status=inactive)",
        "/auth/login",
        "POST",
        403,
        res.status_code,
        res.json().get("detail", str(res.json())),
        duration,
    )

    # TC_AUTH_008: Email sai định dạng
    t0 = time.perf_counter()
    res = client.post("/auth/login", json={"email": "dinh_dang_email_sai_khong_co_a_cong", "password": "123"})
    duration = (time.perf_counter() - t0) * 1000
    record_result(
        "TC_AUTH_008",
        "Đăng nhập sai",
        "Đăng nhập email sai định dạng RFC",
        "/auth/login",
        "POST",
        422,
        res.status_code,
        "Pydantic Validation Error (Invalid email format)",
        duration,
    )

    # TC_AUTH_009: Thiếu trường bắt buộc (thiếu password)
    t0 = time.perf_counter()
    res = client.post("/auth/login", json={"email": "customer@gmail.com"})
    duration = (time.perf_counter() - t0) * 1000
    record_result(
        "TC_AUTH_009",
        "Đăng nhập sai",
        "Đăng nhập thiếu trường bắt buộc (thiếu password)",
        "/auth/login",
        "POST",
        422,
        res.status_code,
        "Pydantic Validation Error (Field required: password)",
        duration,
    )

    # -------------------------------------------------------------------------
    # NHÓM 3: THIẾU TOKEN HOẶC TOKEN KHÔNG HỢP LỆ (TOKEN AUTHENTICATION)
    # -------------------------------------------------------------------------
    print("\n--- NHÓM 3: KIỂM THỬ THIẾU HOẶC SAI TOKEN (TOKEN AUTHENTICATION) ---")

    # TC_AUTH_010: Gọi endpoint bảo vệ nhưng KHÔNG gửi header Authorization
    t0 = time.perf_counter()
    res = client.get("/auth/me")
    duration = (time.perf_counter() - t0) * 1000
    record_result(
        "TC_AUTH_010",
        "Thiếu/Sai Token",
        "Gọi API bảo vệ không có Authorization Header",
        "/auth/me",
        "GET",
        403,
        res.status_code,
        res.json().get("detail", str(res.json())),
        duration,
    )

    # TC_AUTH_011: Gửi Token rác / chuỗi hash tùy tiện không hợp lệ
    t0 = time.perf_counter()
    res = client.get("/auth/me", headers={"Authorization": "Bearer token_rac_khong_hop_le_123456"})
    duration = (time.perf_counter() - t0) * 1000
    record_result(
        "TC_AUTH_011",
        "Thiếu/Sai Token",
        "Gửi Token rác / chữ ký giả mạo",
        "/auth/me",
        "GET",
        401,
        res.status_code,
        res.json().get("detail", str(res.json())),
        duration,
    )

    # TC_AUTH_012: Gửi Token đã hết hạn (Expired Token)
    expired_token = _create_token({"sub": "4", "email": "customer@gmail.com", "role": "customer"}, -10, "access")
    t0 = time.perf_counter()
    res = client.get("/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    duration = (time.perf_counter() - t0) * 1000
    record_result(
        "TC_AUTH_012",
        "Thiếu/Sai Token",
        "Gửi Token đã hết hạn (Expired JWT)",
        "/auth/me",
        "GET",
        401,
        res.status_code,
        res.json().get("detail", str(res.json())),
        duration,
    )

    # TC_AUTH_013: Gửi Refresh Token vào endpoint yêu cầu Access Token (Sai loại Token)
    refresh_token = create_refresh_token({"sub": "4", "email": "customer@gmail.com", "role": "customer"})
    t0 = time.perf_counter()
    res = client.get("/auth/me", headers={"Authorization": f"Bearer {refresh_token}"})
    duration = (time.perf_counter() - t0) * 1000
    record_result(
        "TC_AUTH_013",
        "Thiếu/Sai Token",
        "Gửi Refresh Token vào endpoint yêu cầu Access Token",
        "/auth/me",
        "GET",
        401,
        res.status_code,
        res.json().get("detail", str(res.json())),
        duration,
    )

    # TC_AUTH_014: Token hợp lệ nhưng user_id không tồn tại trong DB (User đã bị xóa)
    ghost_token = create_access_token({"sub": "9999", "email": "ghost@ridehub.vn", "role": "customer"})
    t0 = time.perf_counter()
    res = client.get("/auth/me", headers={"Authorization": f"Bearer {ghost_token}"})
    duration = (time.perf_counter() - t0) * 1000
    record_result(
        "TC_AUTH_014",
        "Thiếu/Sai Token",
        "Token chứa User ID không tồn tại trong DB",
        "/auth/me",
        "GET",
        401,
        res.status_code,
        res.json().get("detail", str(res.json())),
        duration,
    )

    # -------------------------------------------------------------------------
    # NHÓM 4: TRUY CẬP TRÁI QUYỀN THEO TỪNG VAI TRÒ (RBAC MATRIX)
    # -------------------------------------------------------------------------
    print("\n--- NHÓM 4: KIỂM THỬ TRUY CẬP TRÁI QUYỀN THEO VAI TRÒ (RBAC) ---")

    admin_token = tokens["admin"]
    owner_token = tokens["store_owner"]
    staff_token = tokens["store_staff"]
    cust_token = tokens["customer"]

    rbac_scenarios = [
        # --- Endpoint Admin Dashboard (Yêu cầu role: admin) ---
        ("TC_RBAC_015", "admin", admin_token, "/auth/admin-dashboard", 200, "Admin truy cập Dashboard Quản trị"),
        ("TC_RBAC_016", "customer", cust_token, "/auth/admin-dashboard", 403, "Customer cố truy cập Dashboard Quản trị (Trái quyền)"),
        ("TC_RBAC_017", "store_owner", owner_token, "/auth/admin-dashboard", 403, "Store Owner cố truy cập Dashboard Quản trị (Trái quyền)"),
        ("TC_RBAC_018", "store_staff", staff_token, "/auth/admin-dashboard", 403, "Store Staff cố truy cập Dashboard Quản trị (Trái quyền)"),

        # --- Endpoint Store Management (Yêu cầu role: store_owner hoặc admin) ---
        ("TC_RBAC_019", "store_owner", owner_token, "/auth/store-management", 200, "Store Owner truy cập Quản lý Cửa hàng"),
        ("TC_RBAC_020", "admin", admin_token, "/auth/store-management", 200, "Admin truy cập Quản lý Cửa hàng (Đặc quyền cao)"),
        ("TC_RBAC_021", "customer", cust_token, "/auth/store-management", 403, "Customer cố truy cập Quản lý Cửa hàng (Trái quyền)"),
        ("TC_RBAC_022", "store_staff", staff_token, "/auth/store-management", 403, "Store Staff cố truy cập Quản lý Cửa hàng (Trái quyền)"),

        # --- Endpoint Staff Handover (Yêu cầu role: store_staff, store_owner hoặc admin) ---
        ("TC_RBAC_023", "store_staff", staff_token, "/auth/staff-handover", 200, "Store Staff truy cập Bàn giao xe"),
        ("TC_RBAC_024", "store_owner", owner_token, "/auth/staff-handover", 200, "Store Owner truy cập Bàn giao xe (Được phép)"),
        ("TC_RBAC_025", "customer", cust_token, "/auth/staff-handover", 403, "Customer cố truy cập Bàn giao xe (Trái quyền)"),

        # --- Endpoint Customer Orders (Yêu cầu role: customer hoặc admin) ---
        ("TC_RBAC_026", "customer", cust_token, "/auth/customer-orders", 200, "Customer truy cập Đơn đặt xe cá nhân"),
        ("TC_RBAC_027", "store_staff", staff_token, "/auth/customer-orders", 403, "Store Staff truy cập Đơn khách hàng (Trái quyền)"),
    ]

    for tc_id, role_name, token, endpoint, expected_code, tc_name in rbac_scenarios:
        t0 = time.perf_counter()
        res = client.get(endpoint, headers={"Authorization": f"Bearer {token}"})
        duration = (time.perf_counter() - t0) * 1000
        detail = res.json().get("detail") if res.status_code != 200 else res.json().get("message")
        record_result(
            tc_id=tc_id,
            category="Phân quyền RBAC",
            name=tc_name,
            endpoint=endpoint,
            method="GET",
            expected_status=expected_code,
            actual_status=res.status_code,
            details=str(detail),
            duration_ms=duration,
        )

    # TC_RBAC_028: Token hợp lệ nhưng tài khoản bị khóa trong DB sau khi token được cấp
    # Kịch bản: Admin khóa tài khoản Customer đang hoạt động
    db = TestingSessionLocal()
    cust_db = db.query(User).filter(User.id == 4).first()
    cust_db.status = "inactive"
    db.commit()
    db.close()

    t0 = time.perf_counter()
    res = client.get("/auth/me", headers={"Authorization": f"Bearer {cust_token}"})
    duration = (time.perf_counter() - t0) * 1000
    record_result(
        "TC_RBAC_028",
        "Phân quyền RBAC",
        "Token còn hạn nhưng tài khoản đã bị khóa trong DB",
        "/auth/me",
        "GET",
        403,
        res.status_code,
        res.json().get("detail", str(res.json())),
        duration,
    )

    # -------------------------------------------------------------------------
    # TỔNG KẾT KẾT QUẢ KIỂM THỬ
    # -------------------------------------------------------------------------
    total_tests = len(test_results)
    passed_tests = sum(1 for t in test_results if t["passed"])
    failed_tests = total_tests - passed_tests
    success_rate = (passed_tests / total_tests) * 100

    print("\n" + "=" * 80)
    print(" KẾT QUẢ TỔNG HỢP KIỂM THỬ BẢO MẬT & PHÂN QUYỀN RIDEHUB")
    print("=" * 80)
    print(f" Tổng số Test Cases đã chạy : {total_tests}")
    print(f" Số Test Cases ĐẠT (PASS)   : {passed_tests} ({success_rate:.1f}%)")
    print(f" Số Test Cases HỎNG (FAIL)  : {failed_tests}")
    print("=" * 80)

    if failed_tests == 0:
        print(" >>> CHÚC MỪNG: 100% CÁC TEST CASES ĐÃ ĐẠT CHUẨN THIẾT KẾ AN TOÀN! <<<")
    else:
        print(" >>> CẢNH BÁO: CÓ TEST CASE KHÔNG ĐẠT. XEM CHI TIẾT BÊN TRÊN. <<<")

    return test_results


if __name__ == "__main__":
    results = run_all_tests()

