"""Đọc QR CCCD theo cách chịu lỗi và chỉ trả mã băm, không trả nội dung thô.

Thư viện qrcode/pyzbar chỉ được nạp lười khi có sẵn; thiếu thư viện hoặc thiếu
thư viện hệ thống zbar thì trả về cờ `qr_unavailable` để admin duyệt thủ công.
"""
import hashlib
import re
import unicodedata
from datetime import date, datetime
from typing import Any, Optional

from PIL import Image


def _normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[\s\-_./\\]+", "", text).strip().lower()


def _normalize_date(value: Any) -> str:
    text = str(value or "").strip()
    for pattern in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            continue
    return _normalize_text(text)


def extract_qr_payload(image: Image.Image) -> Optional[str]:
    """Trích chuỗi QR; trả None nếu không có bộ đọc hoặc không đọc được."""
    try:
        from pyzbar.pyzbar import decode
    except Exception:
        return None
    try:
        results = decode(image)
    except Exception:
        return None
    for result in results:
        payload = bytes(result.data or b"").decode("utf-8", errors="ignore").strip()
        if payload:
            return payload
    return None


def hash_payload(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def parse_qr_fields(payload: Optional[str]) -> dict[str, str]:
    """Tách các trường thường gặp, ngăn nhau bằng '|' hoặc xuống dòng."""
    if not payload:
        return {}
    parts = [part.strip() for part in re.split(r"[|\r\n]+", payload) if part.strip()]
    if len(parts) < 4:
        return {}
    fields: dict[str, str] = {}
    for token in parts:
        normalized = _normalize_text(token)
        if re.fullmatch(r"\d{9,12}", normalized) and "document_number" not in fields:
            fields["document_number"] = token
        elif re.fullmatch(r"\d{2}[-/]\d{2}[-/]\d{4}|\d{4}-\d{2}-\d{2}", token.strip()):
            iso = _normalize_date(token)
            if "date_of_birth" not in fields:
                fields["date_of_birth"] = token.strip()
            elif "issued_date" not in fields and iso != _normalize_date(fields["date_of_birth"]):
                fields["issued_date"] = token.strip()
        elif len(normalized) >= 6 and any(char.isalpha() for char in normalized):
            if "full_name" not in fields:
                fields["full_name"] = token
            else:
                fields.setdefault("address", token)
    return fields


def compare_qr_with_consent(payload: Optional[str], consent: Any) -> tuple[Optional[bool], list[str]]:
    """So khớp mềm: cần ít nhất 2 trùng khớp mới coi là nhất quán."""
    fields = parse_qr_fields(payload)
    if not fields:
        return None, ["qr_unparsable"]

    matches = 0
    checks = (
        ("document_number", _normalize_text),
        ("full_name", _normalize_text),
        ("date_of_birth", _normalize_date),
        ("issued_date", _normalize_date),
        ("address", _normalize_text),
    )
    for field_name, normalizer in checks:
        expected = getattr(consent, field_name, None)
        actual = fields.get(field_name)
        if expected and actual and normalizer(expected) == normalizer(actual):
            matches += 1

    if matches >= 2:
        return True, []
    return False, ["qr_mismatch"]
