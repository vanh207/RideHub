from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, Optional


LICENSE_CLASSES_BY_VEHICLE = {
    "MOTORBIKE": frozenset({"A1", "A2", "A3", "A4"}),
    "CAR": frozenset({"B1", "B2", "C", "D1", "D2", "D", "E"}),
}

MINIMUM_AGE_BY_LICENSE = {
    "A1": 18,
    "A2": 18,
    "A3": 18,
    "A4": 18,
    "B1": 18,
    "B2": 18,
    "C": 21,
    "D1": 24,
    "D2": 27,
    "D": 27,
    "E": 27,
}


@dataclass(frozen=True)
class EligibilityResult:
    eligible: bool
    reasons: tuple[str, ...]

    def first_reason(self) -> Optional[str]:
        return self.reasons[0] if self.reasons else None


def calculate_age(date_of_birth: date, at_date: date) -> int:
    if date_of_birth is None:
        raise ValueError("date_of_birth không được để trống")
    return at_date.year - date_of_birth.year - (
        (at_date.month, at_date.day) < (date_of_birth.month, date_of_birth.day)
    )


def normalize_vehicle_type(vehicle_type: str) -> str:
    normalized = (vehicle_type or "").strip().upper()
    aliases = {
        "XE_MAY": "MOTORBIKE",
        "MOTOR": "MOTORBIKE",
        "BIKE": "MOTORBIKE",
        "OTO": "CAR",
        "AUTO": "CAR",
    }
    return aliases.get(normalized, normalized)


def get_compatible_license_classes(vehicle_type: str) -> frozenset[str]:
    normalized = normalize_vehicle_type(vehicle_type)
    return LICENSE_CLASSES_BY_VEHICLE.get(normalized, frozenset())


def is_driver_license_expired(
    expiry_date: Optional[date],
    on_date: date,
) -> bool:
    return expiry_date is None or expiry_date < on_date


def check_customer_can_rent(
    customer,
    vehicle,
    rental_start: Optional[datetime | date] = None,
) -> EligibilityResult:
    """Kiểm tra tuổi, hạng GPLX và hạn GPLX trước khi đặt xe."""
    normalized_type = normalize_vehicle_type(
        getattr(vehicle, "vehicle_type", "")
    )
    compatible_classes = get_compatible_license_classes(normalized_type)
    if not compatible_classes:
        return EligibilityResult(False, ("Loại xe không được hỗ trợ.",))

    if isinstance(rental_start, datetime):
        check_date = rental_start.date()
    elif isinstance(rental_start, date):
        check_date = rental_start
    else:
        check_date = date.today()

    date_of_birth = getattr(customer, "date_of_birth", None)
    if date_of_birth is None:
        return EligibilityResult(
            False,
            ("Khách hàng chưa cung cấp ngày sinh.",),
        )

    if calculate_age(date_of_birth, check_date) < 18:
        return EligibilityResult(
            False,
            ("Khách hàng phải đủ 18 tuổi mới được thuê xe.",),
        )

    licenses = getattr(customer, "driver_licenses", None) or []
    approved_licenses = [
        license
        for license in licenses
        if str(getattr(license, "status", "")).lower()
        in {"approved", "verified", "active"}
    ]

    if not approved_licenses:
        return EligibilityResult(
            False,
            ("Khách hàng chưa có GPLX đã được xác minh.",),
        )

    compatible_licenses = [
        license
        for license in approved_licenses
        if str(getattr(license, "license_class", "")).strip().upper()
        in compatible_classes
    ]
    if not compatible_licenses:
        return EligibilityResult(
            False,
            (
                f"Hạng GPLX không phù hợp loại xe {normalized_type}. "
                f"Cần hạng: {', '.join(sorted(compatible_classes))}.",
            ),
        )

    age = calculate_age(date_of_birth, check_date)
    valid_licenses = [
        license
        for license in compatible_licenses
        if not is_driver_license_expired(
            getattr(license, "expiry_date", None),
            check_date,
        )
        and age >= MINIMUM_AGE_BY_LICENSE.get(
            str(getattr(license, "license_class", "")).strip().upper(),
            18,
        )
    ]
    if not valid_licenses:
        return EligibilityResult(
            False,
            ("GPLX phù hợp đã hết hạn hoặc khách chưa đủ tuổi theo hạng GPLX.",),
        )

    return EligibilityResult(True, ())


def validate_booking_eligibility(
    customer,
    vehicle,
    rental_start: Optional[datetime | date] = None,
) -> EligibilityResult:
    return check_customer_can_rent(customer, vehicle, rental_start)
