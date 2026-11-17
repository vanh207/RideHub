from fastapi import UploadFile
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.core.store_errors import StoreAPIError
from app.middleware.store_upload import validate_upload
from app.models.store import Store
from app.schemas.store import parse_store_registration_form
from app.services.store_registration import register_store


async def register_store_controller(
    *,
    db: Session,
    owner_id: int,
    fields: dict,
    business_license_file: UploadFile | None,
    logo_file: UploadFile | None,
) -> Store:
    form = parse_store_registration_form(fields)
    license_upload = await validate_upload(
        business_license_file,
        field_name="business_license_file",
        allowed_types=("application/pdf", "image/jpeg", "image/png"),
        max_bytes=5 * 1024 * 1024,
        required=True,
    )
    logo_upload = await validate_upload(
        logo_file,
        field_name="logo",
        allowed_types=("image/jpeg", "image/png"),
        max_bytes=2 * 1024 * 1024,
        required=False,
    )
    if license_upload is None:
        raise StoreAPIError(400, "Vui lòng tải lên giấy phép kinh doanh.")
    return await run_in_threadpool(
        register_store,
        db,
        owner_id,
        form,
        license_upload,
        logo_upload,
    )
