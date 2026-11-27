"""Kiểm tra kho ảnh riêng: tên ngẫu nhiên, quyền, chặn path traversal."""
import os
from pathlib import Path

import pytest

from app.core.kyc_errors import KycBusinessError, KycErrorCode
from app.services.kyc_file_store import LocalKycFileStore


def test_local_store_saves_random_name_and_can_delete(tmp_path: Path) -> None:
    store = LocalKycFileStore(root=tmp_path)
    first = store.save("front", b"noi-dung-gia", ".jpg")
    second = store.save("front", b"noi-dung-gia", ".jpg")

    assert first != second
    assert first.startswith("front/")
    assert store.exists(first) is True
    assert store.read(first) == b"noi-dung-gia"
    assert (tmp_path / first).exists() is True
    assert (os.stat(tmp_path / first).st_mode & 0o777) == 0o600

    assert store.delete(first) is True
    assert store.exists(first) is False
    assert store.delete(first) is False


def test_local_store_rejects_traversal_and_unknown_kind(tmp_path: Path) -> None:
    store = LocalKycFileStore(root=tmp_path)
    with pytest.raises(KycBusinessError) as exc:
        store.read("../secret.jpg")
    assert exc.value.code == KycErrorCode.KYC_FORBIDDEN

    with pytest.raises(KycBusinessError) as exc:
        store.save("avatar", b"x", ".jpg")
    assert exc.value.code == KycErrorCode.KYC_FORBIDDEN
