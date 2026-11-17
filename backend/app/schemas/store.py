import re
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, ValidationError, field_validator
from datetime import datetime

from app.core.store_errors import StoreAPIError


class StoreRegistrationForm(BaseModel):
    """Validated form fields for POST /api/stores/register."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    phone: str = Field(..., max_length=20)
    email: EmailStr = Field(..., max_length=255)
    province: str = Field(..., min_length=1, max_length=100)
    district: str = Field(..., min_length=1, max_length=100)
    ward: str = Field(..., min_length=1, max_length=100)
    address_detail: str = Field(..., min_length=1, max_length=500)
    business_license_number: str = Field(..., min_length=10, max_length=13)

    @field_validator("phone")
    @classmethod
    def validate_vietnamese_phone(cls, value: str) -> str:
        normalized = re.sub(r"[\s().-]", "", value)
        if normalized.startswith("+84"):
            normalized = "0" + normalized[3:]
        elif normalized.startswith("84") and len(normalized) == 11:
            normalized = "0" + normalized[2:]
        if not re.fullmatch(r"0(?:3|5|7|8|9)\d{8}", normalized):
            raise ValueError("Số điện thoại Việt Nam không hợp lệ.")
        return normalized

    @field_validator("business_license_number")
    @classmethod
    def validate_business_license_number(cls, value: str) -> str:
        if not re.fullmatch(r"\d{10}(?:\d{3})?", value):
            raise ValueError("Mã số doanh nghiệp phải gồm 10 hoặc 13 chữ số.")
        return value


def parse_store_registration_form(values: dict) -> StoreRegistrationForm:
    """Convert Pydantic field errors into the API's Vietnamese field-error shape."""
    try:
        return StoreRegistrationForm.model_validate(values)
    except ValidationError as exc:
        errors = {}
        for error in exc.errors():
            field = str(error["loc"][0])
            error_type = error["type"]
            if error_type == "missing":
                message = "Trường này là bắt buộc."
            elif field == "name":
                message = "Tên cửa hàng phải từ 3 đến 100 ký tự."
            elif field == "description":
                message = "Mô tả không được vượt quá 1000 ký tự."
            elif field == "phone":
                message = "Số điện thoại Việt Nam không hợp lệ."
            elif field == "email":
                message = "Địa chỉ email không hợp lệ hoặc vượt quá 255 ký tự."
            elif field == "business_license_number":
                message = "Mã số doanh nghiệp phải gồm 10 hoặc 13 chữ số."
            else:
                message = "Trường này không hợp lệ hoặc vượt quá độ dài cho phép."
            errors.setdefault(field, []).append(message)
        raise StoreAPIError(
            status_code=400,
            message="Dữ liệu đăng ký cửa hàng không hợp lệ.",
            errors=errors,
        ) from exc


class StoreBase(BaseModel):
    name: str
    address: str
    city: str
    business_license: Optional[str] = None
    bank_account_info: Optional[str] = None

class StoreCreate(StoreBase):
    owner_user_id: int

class StoreResponse(StoreBase):
    id: int
    owner_user_id: int
    status: str
    reject_reason: Optional[str] = None
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True