"""Test API eKYC Lát 2: luồng khách, bảo mật ảnh và đồng bộ admin duyệt."""
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.kyc_errors import KycBusinessError, kyc_business_error_handler
from app.core.config import settings
from app.core.dependencies import get_current_admin, get_current_user
from app.db.session import Base, get_db
from app.models.identity_document import IdentityDocument
from app.models.kyc_session import KycSession
from app.routers import kyc
from app.routers.admin_reviews import _sync_kyc_session_after_review
from app.services import kyc_service
from app.services.kyc_file_store import LocalKycFileStore

CONSENT = {
    "consent_text": "Tôi đồng ý xử lý dữ liệu sinh trắc học để xác thực danh tính.",
    "consent_version": "2026-11-v1",
    "document_number": "001230000001",
    "full_name": "Nguyễn Văn A",
    "date_of_birth": "1990-01-01",
    "issued_date": "2020-01-01",
    "expiry_date": "2030-01-01",
    "gender": "nam",
    "address": "Đà Nẵng",
}


def image_bytes(width: int, height: int) -> bytes:
    output = BytesIO()
    Image.new("RGB", (width, height), "white").save(output, format="JPEG")
    return output.getvalue()


@pytest.fixture()
def kyc_env(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "KYC_QR_CHECK_ENABLED", False)
    monkeypatch.setattr(settings, "KYC_FACE_PROVIDER", "mock")
    monkeypatch.setattr(settings, "KYC_MOCK_SCORE", 0.9)
    monkeypatch.setattr(settings, "KYC_MATCH_THRESHOLD", None)
    monkeypatch.setattr(
        kyc_service, "kyc_file_store", LocalKycFileStore(root=tmp_path / "private-kyc")
    )
    kyc.kyc_rate_limiter.reset()

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)

    app = FastAPI()
    app.add_exception_handler(KycBusinessError, kyc_business_error_handler)
    app.include_router(kyc.router, prefix="/api")
    app.include_router(kyc.admin_router, prefix="/api")

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    customer = SimpleNamespace(id=1, role="customer")
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: customer
    app.dependency_overrides[get_current_admin] = lambda: SimpleNamespace(id=99, role="admin")

    with TestClient(app) as client:
        yield client, testing_session, app, customer

    app.dependency_overrides.clear()
    engine.dispose()


def finish_kyc_flow(client) -> dict:
    created = client.post("/api/kyc/sessions", json=CONSENT)
    assert created.status_code == 201
    session_data = created.json()
    session_id = session_data["session_id"]

    front = client.post(
        f"/api/kyc/sessions/{session_id}/images/front",
        files={"file": ("front.jpg", image_bytes(800, 500), "image/jpeg")},
    )
    assert front.status_code == 201
    assert front.json()["status"] == "ID_UPLOADED"

    back = client.post(
        f"/api/kyc/sessions/{session_id}/images/back",
        files={"file": ("back.jpg", image_bytes(800, 500), "image/jpeg")},
    )
    assert back.status_code == 201

    selfie = client.post(
        f"/api/kyc/sessions/{session_id}/images/selfie",
        data={"challenge": session_data["challenge"]},
        files={"file": ("selfie.jpg", image_bytes(700, 900), "image/jpeg")},
    )
    assert selfie.status_code == 201
    assert selfie.json()["status"] == "FACE_UPLOADED"

    submitted = client.post(
        f"/api/kyc/sessions/{session_id}/submit",
        json={"score": 0.99},
    )
    assert submitted.status_code == 201
    return submitted.json()


def test_full_public_flow_keeps_images_private(kyc_env) -> None:
    client, _, _, _ = kyc_env
    result = finish_kyc_flow(client)

    assert result["status"] == "SUBMITTED"
    assert result["match_score"] == 0.9
    assert result["identity_document_id"] > 0

    me = client.get("/api/kyc/me")
    assert me.status_code == 200
    body = me.json()
    assert body["status"] == "SUBMITTED"
    assert body["document_number_masked"] == "********0001"
    assert CONSENT["document_number"] not in me.text
    assert "front/" not in me.text
    assert "selfie/" not in me.text

    image = client.get(f"/api/admin/kyc/{result['session_id']}/images/selfie")
    assert image.status_code == 200
    assert image.headers["cache-control"] == "no-store"
    assert image.headers["x-content-type-options"] == "nosniff"
    assert image.content.startswith(b"\xff\xd8")


def test_duplicate_document_number_is_generic(kyc_env) -> None:
    client, _, app, _ = kyc_env
    finish_kyc_flow(client)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=2, role="customer")

    duplicate = client.post("/api/kyc/sessions", json=CONSENT)
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "KYC_DUPLICATE_ID"
    assert CONSENT["document_number"] not in duplicate.text


def test_wrong_liveness_challenge_is_rejected(kyc_env) -> None:
    client, _, _, _ = kyc_env
    created = client.post("/api/kyc/sessions", json=CONSENT)
    session_id = created.json()["session_id"]

    bad = client.post(
        f"/api/kyc/sessions/{session_id}/images/selfie",
        data={"challenge": "sai"},
        files={"file": ("selfie.jpg", image_bytes(700, 900), "image/jpeg")},
    )
    assert bad.status_code == 400
    assert bad.json()["code"] == "KYC_CHALLENGE_INVALID"


def test_admin_decision_closes_linked_kyc_session(kyc_env) -> None:
    _, testing_session, _, _ = kyc_env
    db = testing_session()
    try:
        document = IdentityDocument(
            user_id=1,
            document_type="CCCD",
            document_number="001230000009",
            status="pending",
        )
        session = KycSession(
            user_id=1,
            status="SUBMITTED",
            document_number=document.document_number,
            flags=[],
        )
        db.add_all([document, session])
        db.commit()
        db.refresh(document)
        db.refresh(session)

        session.identity_document_id = document.id
        db.commit()

        _sync_kyc_session_after_review(db, document.id, "approved")
        assert session.status == "APPROVED"
        assert "admin_review" in session.flags
    finally:
        db.close()
