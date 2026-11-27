"""Test cổng eKYC cho luồng đặt xe."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.core.config import settings
from app.core.kyc_errors import KycBusinessError
from app.crud.booking import ensure_customer_verified
from app.db.session import Base
from app.models.identity_document import IdentityDocument
from app.models.kyc_session import KycSession
from app.models.user import User


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    db = session_factory()
    db.add(User(id=8201, phone="0900000001", status="active"))
    db.commit()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def test_gate_skips_when_disabled(db_session, monkeypatch):
    monkeypatch.setattr(settings, "KYC_ENABLED", False)
    monkeypatch.setattr(settings, "KYC_REQUIRED_FOR_BOOKING", True)

    ensure_customer_verified(db_session, 8201)


def test_gate_skips_non_customer(db_session, monkeypatch):
    monkeypatch.setattr(settings, "KYC_ENABLED", True)
    monkeypatch.setattr(settings, "KYC_REQUIRED_FOR_BOOKING", True)
    monkeypatch.setattr(User, "role", property(lambda self: "admin"))

    ensure_customer_verified(db_session, 8201)


def test_gate_rejects_pending_session(db_session, monkeypatch):
    monkeypatch.setattr(settings, "KYC_ENABLED", True)
    monkeypatch.setattr(settings, "KYC_REQUIRED_FOR_BOOKING", True)
    now = datetime.now()
    db_session.add(
        KycSession(
            user_id=8201,
            status="SUBMITTED",
            expires_at=now + timedelta(minutes=15),
        )
    )
    db_session.commit()

    with pytest.raises(KycBusinessError) as raised:
        ensure_customer_verified(db_session, 8201)

    assert raised.value.code.value == "KYC_NOT_APPROVED"
    assert raised.value.details == {"status": "SUBMITTED"}


def test_gate_allows_approved_session(db_session, monkeypatch):
    monkeypatch.setattr(settings, "KYC_ENABLED", True)
    monkeypatch.setattr(settings, "KYC_REQUIRED_FOR_BOOKING", True)
    db_session.add(KycSession(user_id=8201, status="APPROVED"))
    db_session.commit()

    ensure_customer_verified(db_session, 8201)


def test_gate_allows_approved_identity_document(db_session, monkeypatch):
    monkeypatch.setattr(settings, "KYC_ENABLED", True)
    monkeypatch.setattr(settings, "KYC_REQUIRED_FOR_BOOKING", True)
    db_session.add(
        IdentityDocument(
            user_id=8201,
            document_type="CCCD",
            document_number="001230000001",
            status="approved",
        )
    )
    db_session.commit()

    ensure_customer_verified(db_session, 8201)
