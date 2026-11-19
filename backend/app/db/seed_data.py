"""Khởi tạo dữ liệu mẫu (Seed Data) cho hệ thống RideHub.

Tự động chạy mỗi khi khởi động server:
Đảm bảo luôn có 3 tài khoản đại diện chuẩn:
1. Khách thuê:      customer@ridehub.vn / 123456 (Role: customer)
2. Chủ cửa hàng:    owner@ridehub.vn    / 123456 (Role: store_owner, kèm cửa hàng đã duyệt)
3. Admin hệ thống:  admin@ridehub.vn    / 123456 (Role: admin)
"""
import logging
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.auto_migration import auto_migrate_missing_columns
from app.db.session import SessionLocal
from app.models.role import Role, UserRole
from app.models.store import Store
from app.models.user import User

logger = logging.getLogger("ridehub.seed")

DEFAULT_PASSWORD = "password123"  # Mật khẩu chung dễ nhớ cho môi trường dev

# Danh sách 3 tài khoản đại diện mẫu
SEED_ACCOUNTS = [
    {
        "role_code": "customer",
        "role_name": "Khách thuê",
        "email": "customer@ridehub.vn",
        "phone": "0901234567",
        "full_name": "Nguyễn Văn An (Khách thuê)",
        "password": DEFAULT_PASSWORD,
        "firebase_uid": "seed_customer_uid_01",
    },
    {
        "role_code": "store_owner",
        "role_name": "Chủ cửa hàng",
        "email": "owner@ridehub.vn",
        "phone": "0902222222",
        "full_name": "Lê Hoàng Nam (Chủ cửa hàng)",
        "password": DEFAULT_PASSWORD,
        "firebase_uid": "seed_store_owner_uid_02",
        "store_info": {
            "name": "GreenRide - Chi nhánh Quận 1",
            "description": "Cửa hàng cho thuê xe điện & xe máy uy tín tại trung tâm TP.HCM",
            "phone": "0902222222",
            "email": "greenride@ridehub.vn",
            "address": "120 Lê Lợi, Phường Bến Thành",
            "city": "TP. Hồ Chí Minh",
            "district": "Quận 1",
            "ward": "Phường Bến Thành",
            "status": "APPROVED",
        },
    },
    {
        "role_code": "admin",
        "role_name": "Quản trị viên",
        "email": "admin@ridehub.vn",
        "phone": "0909999999",
        "full_name": "Quản Trị Viên Hệ Thống",
        "password": DEFAULT_PASSWORD,
        "firebase_uid": "seed_admin_uid_03",
    },
]


def _ensure_role(db: Session, code: str, name: str) -> Role:
    """Tạo hoặc lấy vai trò theo code."""
    role_code_clean = code.strip().lower()
    role = db.query(Role).filter(func.lower(Role.code) == role_code_clean).first()
    if not role:
        role = Role(
            code=role_code_clean,
            name=name,
            description=f"Vai trò {name} trong hệ thống RideHub",
        )
        db.add(role)
        db.commit()
        db.refresh(role)
    return role


def _assign_role(db: Session, user_id: int, role_id: int) -> None:
    """Đảm bảo tài khoản được liên kết vai trò trong bảng user_roles."""
    existing = db.query(UserRole).filter(
        UserRole.user_id == user_id,
        UserRole.role_id == role_id,
    ).first()
    if not existing:
        ur = UserRole(user_id=user_id, role_id=role_id)
        db.add(ur)
        db.commit()


def seed_default_accounts() -> None:
    """Hàm khởi tạo dữ liệu mẫu, đảm bảo 3 tài khoản luôn tồn tại và sẵn sàng đăng nhập."""
    # Tự động bổ sung các cột còn thiếu trong DB trước khi thao tác
    auto_migrate_missing_columns()

    db: Session = SessionLocal()
    try:
        # 1. Đảm bảo các Roles cơ bản tồn tại
        roles_dict = {
            "customer": _ensure_role(db, "customer", "Khách thuê"),
            "store_owner": _ensure_role(db, "store_owner", "Chủ cửa hàng"),
            "admin": _ensure_role(db, "admin", "Quản trị viên"),
            "store_staff": _ensure_role(db, "store_staff", "Nhân viên cửa hàng"),
            "operator": _ensure_role(db, "operator", "Điều hành"),
        }

        created_or_updated = []

        # 2. Lần lượt tạo hoặc cập nhật 3 tài khoản đại diện
        for acc in SEED_ACCOUNTS:
            role_code = acc["role_code"]
            email = acc["email"]
            phone = acc["phone"]
            full_name = acc["full_name"]
            password = acc["password"]
            firebase_uid = acc["firebase_uid"]
            role_obj = roles_dict[role_code]

            # Kiểm tra xem user đã tồn tại theo email hoặc phone chưa
            user = db.query(User).filter(
                (User.email == email) | (User.phone == phone)
            ).first()

            if not user:
                # Tạo mới
                user = User(
                    email=email,
                    phone=phone,
                    full_name=full_name,
                    hashed_password=hash_password(password),
                    status="active",
                    firebase_uid=firebase_uid,
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                status_action = "TẠO MỚI"
            else:
                # Đã có -> Đảm bảo mật khẩu và trạng thái hoạt động
                user.hashed_password = hash_password(password)
                user.status = "active"
                if not user.firebase_uid:
                    user.firebase_uid = firebase_uid
                db.commit()
                status_action = "ĐÃ ĐỒNG BỘ"

            # Gán vai trò
            _assign_role(db, user.id, role_obj.id)

            # Nếu là Chủ cửa hàng, đảm bảo có ít nhất 1 cửa hàng APPROVED
            if "store_info" in acc:
                try:
                    store_info = acc["store_info"]
                    store = db.query(Store).filter(Store.owner_user_id == user.id).first()
                    if not store:
                        store = Store(
                            owner_user_id=user.id,
                            name=store_info["name"],
                            description=store_info.get("description"),
                            phone=store_info.get("phone"),
                            email=store_info.get("email"),
                            address=store_info["address"],
                            city=store_info["city"],
                            district=store_info.get("district"),
                            ward=store_info.get("ward"),
                            status=store_info["status"],
                            approved_at=datetime.now(),
                        )
                        db.add(store)
                        db.commit()
                except Exception as store_err:
                    db.rollback()
                    logger.warning(f"[SEED DATA] Bỏ qua tạo cửa hàng mẫu (vẫn giữ tài khoản user): {store_err}")

            created_or_updated.append((role_code, email, password, full_name, status_action))

        # 3. In thông báo rõ ràng ra console để lập trình viên tiện sử dụng
        print("\n" + "=" * 76)
        print(" [SEED DATA] 3 TÀI KHOẢN MẪU KHỞI TẠO SẴN SÀNG CHO MÔI TRƯỜNG DEV")
        print("=" * 76)
        print(f" 1. KHÁCH THUÊ:    customer@ridehub.vn | Mật khẩu: {DEFAULT_PASSWORD} | Role: customer")
        print(f" 2. CHỦ CỬA HÀNG:  owner@ridehub.vn    | Mật khẩu: {DEFAULT_PASSWORD} | Role: store_owner")
        print(f" 3. QUẢN TRỊ VIÊN: admin@ridehub.vn    | Mật khẩu: {DEFAULT_PASSWORD} | Role: admin")
        print("=" * 76 + "\n")

    except Exception as e:
        logger.error(f"[SEED DATA] Lỗi khi tạo dữ liệu mẫu: {e}", exc_info=True)
    finally:
        db.close()
