import logging
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.store_errors import StoreAPIError
from app.middleware.store_upload import (
    ValidatedUpload,
    delete_private_upload,
    save_private_upload,
)
from app.models.store import Store
from app.models.user import User
from app.schemas.store import StoreRegistrationForm

logger = logging.getLogger("ridehub.stores")

_UNIQUE_CONFLICTS = (
    ("uq_stores_business_license_number", "business_license_number", "Mã số doanh nghiệp/thuế đã được đăng ký."),
    ("uq_stores_email", "email", "Email cửa hàng đã được đăng ký."),
    ("uq_stores_name", "name", "Tên cửa hàng đã được đăng ký."),
)


def _duplicate_error(error: IntegrityError) -> StoreAPIError:
    message = str(error.orig).lower()
    for constraint, field, localized_message in _UNIQUE_CONFLICTS:
        if constraint.lower() in message or field.lower() in message:
            return StoreAPIError(
                status_code=409,
                message=localized_message,
                errors={field: [localized_message]},
            )
    return StoreAPIError(
        status_code=409,
        message="Thông tin đăng ký cửa hàng đã tồn tại.",
        errors={"store": ["Vui lòng kiểm tra tên, email và mã số doanh nghiệp."]},
    )


def register_store(
    db: Session,
    owner_id: int,
    form: StoreRegistrationForm,
    business_license: ValidatedUpload,
    logo: ValidatedUpload | None,
) -> Store:
    saved_files: list[str] = []
    committed = False

    def cleanup_saved_files() -> None:
        for path in saved_files:
            try:
                delete_private_upload(path)
            except OSError:
                logger.exception("Không thể dọn tệp đăng ký cửa hàng %s", path)

    try:
        # Lock the owner row so concurrent submissions cannot create two active stores.
        owner_exists = (
            db.query(User.id)
            .filter(User.id == owner_id)
            .with_for_update()
            .scalar()
        )
        if owner_exists is None:
            raise StoreAPIError(401, "Không tìm thấy người dùng đã đăng nhập.")

        has_active_store = (
            db.query(Store.id)
            .filter(
                Store.owner_id == owner_id,
                func.upper(Store.status).in_(("PENDING", "APPROVED")),
            )
            .first()
        )
        if has_active_store:
            raise StoreAPIError(
                status_code=409,
                message="Bạn đã có cửa hàng đang chờ duyệt hoặc đã được duyệt.",
                errors={"owner_id": ["Mỗi tài khoản chỉ được có một cửa hàng PENDING hoặc APPROVED."]},
            )

        duplicates = (
            (Store.business_license_number == form.business_license_number, "business_license_number", "Mã số doanh nghiệp/thuế đã được đăng ký."),
            (func.lower(Store.email) == str(form.email).lower(), "email", "Email cửa hàng đã được đăng ký."),
            (func.lower(Store.name) == form.name.lower(), "name", "Tên cửa hàng đã được đăng ký."),
        )
        for condition, field, message in duplicates:
            if db.query(Store.id).filter(condition).first():
                raise StoreAPIError(409, message, errors={field: [message]})

        license_path = save_private_upload(business_license, "business_licenses")
        saved_files.append(license_path)
        logo_path = None
        if logo is not None:
            logo_path = save_private_upload(logo, "store_logos")
            saved_files.append(logo_path)

        full_address = ", ".join(
            (form.address_detail, form.ward, form.district, form.province)
        )
        store = Store(
            owner_id=owner_id,
            name=form.name,
            description=form.description,
            phone=form.phone,
            email=str(form.email).lower(),
            address=full_address,
            city=form.province,
            district=form.district,
            ward=form.ward,
            address_detail=form.address_detail,
            business_license_number=form.business_license_number,
            business_license_file=license_path,
            logo_file=logo_path,
            status="PENDING",
        )
        db.add(store)
        db.commit()
        committed = True
        db.refresh(store)
        return store
    except StoreAPIError:
        db.rollback()
        if not committed:
            cleanup_saved_files()
        raise
    except IntegrityError as exc:
        db.rollback()
        if committed:
            logger.exception("Không thể tải lại cửa hàng vừa đăng ký cho user_id=%s", owner_id)
            raise StoreAPIError(
                status_code=500,
                message="Cửa hàng đã được lưu nhưng không thể tải lại dữ liệu.",
            ) from exc
        cleanup_saved_files()
        raise _duplicate_error(exc) from exc
    except Exception as exc:
        db.rollback()
        if not committed:
            cleanup_saved_files()
        logger.exception("Lỗi khi đăng ký cửa hàng cho user_id=%s", owner_id)
        raise StoreAPIError(
            status_code=500,
            message="Không thể đăng ký cửa hàng lúc này. Vui lòng thử lại sau.",
        ) from exc
