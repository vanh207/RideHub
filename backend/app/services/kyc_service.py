"""Nghiệp vụ eKYC: tạo phiên, kiểm tra ảnh, nộp hồ sơ và trạng thái của tôi."""
from datetime import date, datetime, timedelta
from secrets import compare_digest, token_urlsafe
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.core.kyc_errors import KycBusinessError, KycErrorCode
from app.core.kyc_status import (
    APPROVED,
    CONSENTED,
    CREATED,
    EXPIRED,
    FACE_UPLOADED,
    ID_UPLOADED,
    NOT_STARTED,
    REJECTED,
    SUBMITTED,
    apply_transition,
    can_transition,
)
from app.models.identity_document import IdentityDocument
from app.models.kyc_session import KycSession
from app.schemas.kyc import (
    KycConsentRequest,
    KycImageKind,
    KycMeResponse,
    KycSessionCreateResponse,
    KycSubmitResponse,
    KycUploadResponse,
)
from app.services.booking_eligibility import calculate_age
from app.services.kyc_file_store import KycFileStore, kyc_file_store
from app.services.kyc_image import inspect_and_normalize_image
from app.services.kyc_provider import FaceVerificationProvider, create_kyc_provider

_ACTIVE_SESSION_STATUSES = {CREATED, CONSENTED, ID_UPLOADED, FACE_UPLOADED, SUBMITTED}


def _dedupe_flags(flags: list[str]) -> list[str]:
    return sorted({flag for flag in flags if flag})


def _mask_number(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return f"{'*' * max(0, len(value) - 4)}{value[-4:]}" if len(value) > 4 else "***"


def _ensure_enabled(config: Settings) -> None:
    if not config.KYC_ENABLED:
        raise KycBusinessError(KycErrorCode.KYC_DISABLED)


def _get_session(db: Session, session_id: int, user_id: Optional[int] = None) -> KycSession:
    query = db.query(KycSession).filter(KycSession.id == session_id)
    if user_id is not None:
        query = query.filter(KycSession.user_id == user_id)
    session = query.first()
    if session is None:
        raise KycBusinessError(KycErrorCode.KYC_SESSION_NOT_FOUND)
    return session


def _ensure_usable(db: Session, session: KycSession) -> None:
    now = datetime.now()
    if session.expires_at and now > session.expires_at:
        if can_transition(session.status, EXPIRED):
            apply_transition(session, EXPIRED)
            db.commit()
        raise KycBusinessError(KycErrorCode.KYC_SESSION_EXPIRED)
    if session.status in {SUBMITTED, APPROVED, REJECTED, EXPIRED}:
        raise KycBusinessError(KycErrorCode.KYC_SESSION_USED)


def create_session(
    db: Session,
    user_id: int,
    payload: KycConsentRequest,
    consent_ip: Optional[str] = None,
    config: Settings | None = None,
) -> KycSession:
    config = config or settings
    _ensure_enabled(config)
    if not payload.consent_text.strip():
        raise KycBusinessError(KycErrorCode.KYC_CONSENT_REQUIRED)
    if payload.consent_version != config.KYC_CONSENT_VERSION:
        raise KycBusinessError(KycErrorCode.KYC_CONSENT_VERSION_INVALID)
    if calculate_age(payload.date_of_birth, date.today()) < 18:
        raise KycBusinessError(KycErrorCode.KYC_AGE_BELOW_MINIMUM)
    if payload.expiry_date < date.today():
        raise KycBusinessError(KycErrorCode.KYC_ID_EXPIRED)

    existing = (
        db.query(IdentityDocument)
        .filter(IdentityDocument.document_number == payload.document_number)
        .first()
    )
    if existing and existing.user_id != user_id:
        raise KycBusinessError(KycErrorCode.KYC_DUPLICATE_ID)

    active = (
        db.query(KycSession)
        .filter(
            KycSession.user_id == user_id,
            KycSession.status.in_(_ACTIVE_SESSION_STATUSES),
        )
        .first()
    )
    if active:
        raise KycBusinessError(KycErrorCode.KYC_SESSION_ACTIVE)

    now = datetime.now()
    expires_at = now + timedelta(minutes=config.KYC_SESSION_TTL_MINUTES)
    session = KycSession(
        user_id=user_id,
        status=CONSENTED,
        challenge=token_urlsafe(18),
        challenge_expires_at=expires_at,
        expires_at=expires_at,
        attempt_count=0,
        consent_version=payload.consent_version,
        consented_at=now,
        consent_ip=consent_ip,
        document_number=payload.document_number,
        full_name=payload.full_name,
        date_of_birth=payload.date_of_birth,
        issued_date=payload.issued_date,
        expiry_date=payload.expiry_date,
        gender=payload.gender,
        address=payload.address,
        flags=[],
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def new_session_response(session: KycSession) -> KycSessionCreateResponse:
    return KycSessionCreateResponse(
        session_id=session.id,
        status=session.status,
        challenge=session.challenge or "",
        expires_at=session.expires_at,
    )


def save_upload(
    db: Session,
    user_id: int,
    session_id: int,
    kind: KycImageKind,
    content: bytes,
    extension: str,
    challenge: Optional[str] = None,
    config: Settings | None = None,
    file_store: KycFileStore | None = None,
    provider: FaceVerificationProvider | None = None,
) -> KycUploadResponse:
    config = config or settings
    store = file_store or kyc_file_store
    _ensure_enabled(config)
    session = _get_session(db, session_id, user_id)
    _ensure_usable(db, session)

    kind_value = kind.value if isinstance(kind, KycImageKind) else str(kind).lower()
    if kind_value == KycImageKind.SELFIE.value:
        valid_challenge = bool(
            session.challenge
            and challenge
            and compare_digest(str(challenge), str(session.challenge))
            and session.challenge_expires_at
            and datetime.now() <= session.challenge_expires_at
        )
        if not valid_challenge:
            raise KycBusinessError(KycErrorCode.KYC_CHALLENGE_INVALID)
        allowed = {ID_UPLOADED, FACE_UPLOADED}
    else:
        allowed = {CONSENTED, ID_UPLOADED}
    if session.status not in allowed:
        raise KycBusinessError(KycErrorCode.KYC_INVALID_TRANSITION)

    if not extension.lower() in {".jpg", ".jpeg", ".png"}:
        raise KycBusinessError(KycErrorCode.KYC_IMAGE_INVALID_FORMAT)

    inspection = inspect_and_normalize_image(content, kind, config=config, consent=session)
    path_attribute = f"{kind_value}_path"
    old_path = getattr(session, path_attribute, None)
    relative_path = store.save(kind_value, inspection.content, inspection.extension)
    setattr(session, path_attribute, relative_path)
    if old_path and old_path != relative_path:
        try:
            store.delete(old_path)
        except Exception:
            pass

    flags = list(session.flags or [])
    flags.extend(inspection.flags)
    if kind_value in {KycImageKind.FRONT.value, KycImageKind.BACK.value}:
        session.qr_payload_hash = inspection.qr_payload_hash
        session.qr_consistent = inspection.qr_consistent
        if session.status == CONSENTED:
            apply_transition(session, ID_UPLOADED)
    else:
        verifier = provider or create_kyc_provider(settings_obj=config)
        liveness = verifier.check_liveness([relative_path], challenge or "")
        session.liveness_result = liveness.result
        flags.extend(liveness.flags)
        if session.status == ID_UPLOADED:
            apply_transition(session, FACE_UPLOADED)

    session.flags = _dedupe_flags(flags)
    session.attempt_count = (session.attempt_count or 0) + 1
    db.commit()
    db.refresh(session)
    return KycUploadResponse(
        session_id=session.id,
        status=session.status,
        kind=kind,
        flags=list(session.flags or []),
        qr_consistent=session.qr_consistent,
    )


def submit_session(
    db: Session,
    user_id: int,
    session_id: int,
    config: Settings | None = None,
    file_store: KycFileStore | None = None,
    provider: FaceVerificationProvider | None = None,
) -> KycSubmitResponse:
    config = config or settings
    store = file_store or kyc_file_store
    _ensure_enabled(config)
    session = _get_session(db, session_id, user_id)
    _ensure_usable(db, session)
    if session.status != FACE_UPLOADED:
        raise KycBusinessError(KycErrorCode.KYC_INVALID_TRANSITION)

    required_paths = (session.front_path, session.back_path, session.selfie_path)
    if not all(required_paths) or not all(store.exists(path) for path in required_paths):
        raise KycBusinessError(KycErrorCode.KYC_UPLOAD_REQUIRED)

    existing = (
        db.query(IdentityDocument)
        .filter(IdentityDocument.document_number == session.document_number)
        .first()
    )
    if existing and existing.user_id != user_id:
        raise KycBusinessError(KycErrorCode.KYC_DUPLICATE_ID)

    verifier = provider or create_kyc_provider(settings_obj=config)
    comparison = verifier.compare(session.front_path, session.selfie_path)
    flags = list(session.flags or [])
    flags.extend(comparison.flags)
    if comparison.score is not None and config.KYC_MATCH_THRESHOLD is not None:
        flag = (
            "score_below_threshold"
            if comparison.score < config.KYC_MATCH_THRESHOLD
            else "score_above_threshold"
        )
        flags.append(flag)
    flags = _dedupe_flags(flags)

    if existing:
        document = existing
        document.status = "pending"
        document.reject_reason = None
        document.verified_by = None
        document.verified_at = None
    else:
        document = IdentityDocument(
            user_id=user_id,
            document_type="CCCD",
            status="pending",
        )
        db.add(document)

    document.document_number = session.document_number
    document.front_image_url = session.front_path
    document.back_image_url = session.back_path
    document.issued_date = session.issued_date
    document.expiry_date = session.expiry_date
    document.selfie_path = session.selfie_path
    document.match_score = comparison.score
    document.liveness_result = session.liveness_result
    document.kyc_flags = flags
    document.kyc_provider = getattr(verifier, "name", "manual")
    db.flush()

    apply_transition(session, SUBMITTED)
    session.identity_document_id = document.id
    session.match_score = comparison.score
    session.provider = getattr(verifier, "name", "manual")
    session.flags = flags
    session.attempt_count = (session.attempt_count or 0) + 1
    db.commit()
    db.refresh(session)
    db.refresh(document)
    return KycSubmitResponse(
        session_id=session.id,
        status=session.status,
        identity_document_id=document.id,
        match_score=session.match_score,
        liveness_result=session.liveness_result,
        flags=list(session.flags or []),
    )


def get_me(db: Session, user_id: int) -> KycMeResponse:
    latest_session = (
        db.query(KycSession)
        .filter(KycSession.user_id == user_id)
        .order_by(KycSession.id.desc())
        .first()
    )
    latest_document = (
        db.query(IdentityDocument)
        .filter(IdentityDocument.user_id == user_id)
        .order_by(IdentityDocument.id.desc())
        .first()
    )

    document_status = (latest_document.status or "").upper() if latest_document else ""
    if latest_session and latest_session.status in {APPROVED, REJECTED}:
        status = latest_session.status
    elif document_status in {APPROVED, REJECTED}:
        status = document_status
    elif latest_session:
        status = latest_session.status
    else:
        status = NOT_STARTED

    flags = list(
        getattr(latest_document, "kyc_flags", None)
        or (latest_session.flags if latest_session else [])
        or []
    )
    return KycMeResponse(
        status=status,
        document_number_masked=_mask_number(
            getattr(latest_document, "document_number", None)
            or (latest_session.document_number if latest_session else None)
        ),
        reject_reason=(
            latest_document.reject_reason if status == REJECTED and latest_document else None
        ),
        identity_document_id=latest_document.id if latest_document else None,
        match_score=(
            getattr(latest_document, "match_score", None)
            if latest_document and latest_document.match_score is not None
            else (latest_session.match_score if latest_session else None)
        ),
        liveness_result=(
            getattr(latest_document, "liveness_result", None)
            or (latest_session.liveness_result if latest_session else None)
        ),
        flags=_dedupe_flags(flags),
        expires_at=(
            latest_session.expires_at
            if latest_session and latest_session.status not in {APPROVED, REJECTED, EXPIRED}
            else None
        ),
    )


def load_admin_image(
    db: Session,
    session_id: int,
    kind: KycImageKind,
    file_store: KycFileStore | None = None,
) -> tuple[bytes, str]:
    store = file_store or kyc_file_store
    session = _get_session(db, session_id)
    kind_value = kind.value if isinstance(kind, KycImageKind) else str(kind).lower()
    relative_path = getattr(session, f"{kind_value}_path", None)
    if not relative_path or not store.exists(relative_path):
        raise KycBusinessError(KycErrorCode.KYC_UPLOAD_REQUIRED, "Không tìm thấy ảnh đã nộp.")
    content = store.read(relative_path)
    media_type = "image/png" if relative_path.lower().endswith(".png") else "image/jpeg"
    return content, media_type
