"""API eKYC của khách và API xem ảnh bảo mật cho admin."""
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_admin, get_current_user
from app.core.kyc_errors import KycBusinessError, KycErrorCode
from app.core.auth_rate_limit import AuthRateLimiter
from app.db.session import get_db
from app.models.user import User
from app.schemas.kyc import (
    KycConsentRequest,
    KycImageKind,
    KycMeResponse,
    KycSessionCreateResponse,
    KycSubmitResponse,
    KycUploadResponse,
)
from app.services import kyc_service

router = APIRouter(prefix="/kyc", tags=["eKYC"])
admin_router = APIRouter(prefix="/admin/kyc", tags=["Admin eKYC"])

kyc_rate_limiter = AuthRateLimiter(
    max_attempts=settings.KYC_DAILY_ATTEMPT_LIMIT,
    window_seconds=86400,
)


def enforce_kyc_rate_limit(user: User = Depends(get_current_user)) -> None:
    """Giới hạn số lần thử eKYC theo từng người dùng trong ngày."""
    try:
        kyc_rate_limiter.check(f"kyc:{user.id}")
    except HTTPException as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=(
                "Bạn đã vượt quá số lần thử xác thực danh tính trong ngày. "
                "Vui lòng thử lại sau."
            ),
            headers=exc.headers,
        ) from exc


@router.post("/sessions", response_model=KycSessionCreateResponse, status_code=201)
def create_kyc_session(
    payload: KycConsentRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _: None = Depends(enforce_kyc_rate_limit),
) -> KycSessionCreateResponse:
    client_ip = request.client.host if request.client else None
    session = kyc_service.create_session(db, user.id, payload, client_ip)
    return kyc_service.new_session_response(session)


@router.post(
    "/sessions/{session_id}/images/{kind}",
    response_model=KycUploadResponse,
    status_code=201,
)
def upload_kyc_image(
    session_id: int,
    kind: KycImageKind,
    file: UploadFile = File(...),
    challenge: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _: None = Depends(enforce_kyc_rate_limit),
) -> KycUploadResponse:
    content = file.file.read(settings.KYC_MAX_UPLOAD_BYTES + 1)
    if len(content) > settings.KYC_MAX_UPLOAD_BYTES:
        raise KycBusinessError(KycErrorCode.KYC_IMAGE_TOO_LARGE)
    extension = Path(file.filename or "").suffix.lower()
    return kyc_service.save_upload(
        db,
        user.id,
        session_id,
        kind,
        content,
        extension,
        challenge=challenge,
    )


@router.post("/sessions/{session_id}/submit", response_model=KycSubmitResponse, status_code=201)
def submit_kyc_session(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _: None = Depends(enforce_kyc_rate_limit),
) -> KycSubmitResponse:
    return kyc_service.submit_session(db, user.id, session_id)


@router.get("/me", response_model=KycMeResponse)
def get_my_kyc_status(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> KycMeResponse:
    return kyc_service.get_me(db, user.id)


@admin_router.get("/{session_id}/images/{kind}")
def get_kyc_image_for_admin(
    session_id: int,
    kind: KycImageKind,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> Response:
    content, media_type = kyc_service.load_admin_image(db, session_id, kind)
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
