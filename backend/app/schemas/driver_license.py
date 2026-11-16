from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime

class DriverLicenseBase(BaseModel):
    license_class: str
    license_number: str
    image_url: str
    issued_date: date
    expiry_date: Optional[date] = None

class DriverLicenseCreate(DriverLicenseBase):
    user_id: int

class DriverLicenseResponse(DriverLicenseBase):
    id: int
    user_id: int
    status: str
    reject_reason: Optional[str] = None
    verified_by: Optional[int] = None
    verified_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True