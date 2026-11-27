"""Kiểm tra máy trạng thái phiên KYC cho mọi cặp trạng thái."""
from types import SimpleNamespace

import pytest

from app.core import kyc_status as st
from app.core.kyc_errors import KycBusinessError, KycErrorCode


@pytest.mark.parametrize("current", sorted(st.ALL_STATUSES))
@pytest.mark.parametrize("target", sorted(st.ALL_STATUSES))
def test_can_transition_follows_single_transition_table(current: str, target: str) -> None:
    expected = target in st.ALLOWED_TRANSITIONS[current]
    assert st.can_transition(current, target) is expected


def test_same_status_is_not_a_transition() -> None:
    for status in st.ALL_STATUSES:
        assert st.can_transition(status, status) is False


def test_unknown_status_cannot_transition() -> None:
    assert st.can_transition("KHONG_CO", st.CONSENTED) is False
    assert st.normalize_status(None) == ""
    assert st.normalize_status(" submitted ") == st.SUBMITTED


def test_apply_transition_mutates_session() -> None:
    session = SimpleNamespace(status=st.CREATED)
    assert st.apply_transition(session, "consented") == st.CONSENTED
    assert session.status == st.CONSENTED


def test_apply_transition_rejects_invalid_pair() -> None:
    session = SimpleNamespace(status=st.CREATED)
    with pytest.raises(KycBusinessError) as exc:
        st.apply_transition(session, st.SUBMITTED)
    assert exc.value.code == KycErrorCode.KYC_INVALID_TRANSITION
    assert session.status == st.CREATED


def test_terminal_statuses() -> None:
    assert st.is_terminal(st.APPROVED) is True
    assert st.is_terminal(st.REJECTED) is True
    assert st.is_terminal(st.EXPIRED) is True
    assert st.is_terminal(st.SUBMITTED) is False
