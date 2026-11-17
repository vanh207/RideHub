from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.controllers.store_controller import register_store_controller
from app.core.dependencies import get_current_user
from app.core.store_rate_limit import limit_store_registration
from app.core.store_errors import StoreAPIError
from app.db.session import get_db
from app.middleware.store_upload import resolve_private_upload
from app.models.store import Store
from app.models.user import User

router = APIRouter(prefix="/stores", tags=["Stores"])


@router.post("/register", status_code=201)
async def register_store_endpoint(
    request: Request,
    name: str | None = Form(None),
    description: str | None = Form(None),
    phone: str | None = Form(None),
    email: str | None = Form(None),
    province: str | None = Form(None),
    district: str | None = Form(None),
    ward: str | None = Form(None),
    address_detail: str | None = Form(None),
    business_license_number: str | None = Form(None),
    business_license_file: UploadFile | None = File(None),
    logo: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(limit_store_registration),
):
    content_type = request.headers.get("content-type", "").lower()
    if not content_type.startswith("multipart/form-data"):
        raise StoreAPIError(415, "Yêu cầu phải sử dụng multipart/form-data.")

    store = await register_store_controller(
        db=db,
        owner_id=current_user.id,
        fields={
            "name": name,
            "description": description,
            "phone": phone,
            "email": email,
            "province": province,
            "district": district,
            "ward": ward,
            "address_detail": address_detail,
            "business_license_number": business_license_number,
        },
        business_license_file=business_license_file,
        logo_file=logo,
    )
    return {
        "success": True,
        "message": "Đăng ký cửa hàng thành công, vui lòng chờ duyệt",
        "data": {
            "id": store.id,
            "name": store.name,
            "status": store.status,
            "created_at": store.created_at.isoformat(),
        },
    }


@router.get("/{store_id}/business-license")
def get_business_license(
    store_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    store = db.query(Store).filter(Store.id == store_id).first()
    if store is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy cửa hàng.")
    if current_user.role != "admin" and store.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Bạn không có quyền xem giấy phép của cửa hàng này.")

    file_path = resolve_private_upload(store.business_license_file)
    if file_path is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp giấy phép kinh doanh.")
    allowed_extensions = {".pdf": "application/pdf", ".jpg": "image/jpeg", ".png": "image/png"}
    media_type = allowed_extensions.get(Path(file_path).suffix.lower())
    if media_type is None:
        raise HTTPException(status_code=415, detail="Định dạng giấy phép được lưu không hợp lệ.")
    return FileResponse(
        file_path,
        media_type=media_type,
        filename=f"business-license-{store.id}{Path(file_path).suffix.lower()}",
    )
