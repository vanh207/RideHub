"""Schema API eKYC: chỉ chứa dữ liệu cần thiết, không chứa ảnh/base64."""
from datetime import date, datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class KycImageKind(str, Enum):
    FRONT = "front"
    BACK = "back"
    SELFIE = "selfie"


class KycConsentRequest(BaseModel):
    consent_text: str = Field(min_length=1)
    consent_version: str = Field(min_length=1)
    document_number: str = Field(min_length=6, max_length=50)
    full_name: str = Field(min_length=1, max_length=150)
    date_of_birth: date
    issued_date: Optional[date] = None
    expiry_date: date
    gender: Optional[str] = Field(default=None, max_length=20)
    address: Optional[str] = Field(default=None, max_length=300)


class KycConsentResponse(BaseModel):
    consented: bool
    consent_version: str
    consented_at: datetime


class KycSessionCreateResponse(BaseModel):
    session_id: int
    status: str
    challenge: str
    expires_at: datetime


class KycUploadResponse(BaseModel):
    session_id: int
    status: str
    kind: KycImageKind
    flags: list[str]
    qr_consistent: Optional[bool] = None


class KycSubmitResponse(BaseModel):
    session_id: int
    status: str
    identity_document_id: int
    match_score: Optional[float] = None
    liveness_result: Optional[str] = None
    flags: list[str]


class KycMeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    document_number_masked: Optional[str] = None
    reject_reason: Optional[str] = None
    identity_document_id: Optional[int] = None
    match_score: Optional[float] = None
    liveness_result: Optional[str] = None
    flags: list[str]
    expires_at: Optional[datetime] = None


class KycErrorResponse(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
