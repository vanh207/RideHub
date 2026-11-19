import unittest
import importlib.util
from datetime import date
from types import SimpleNamespace

service_spec = importlib.util.spec_from_file_location(
    "booking_eligibility",
    "app/services/booking_eligibility.py",
)
booking_eligibility = importlib.util.module_from_spec(service_spec)
service_spec.loader.exec_module(booking_eligibility)
check_customer_can_rent = booking_eligibility.check_customer_can_rent


class BookingEligibilityTest(unittest.TestCase):
    def test_18_year_old_with_valid_motorbike_license_can_rent(self):
        customer = SimpleNamespace(
            date_of_birth=date(2008, 5, 10),
            driver_licenses=[
                SimpleNamespace(
                    license_class="A1",
                    status="approved",
                    expiry_date=date(2030, 1, 1),
                )
            ],
        )
        vehicle = SimpleNamespace(vehicle_type="MOTORBIKE")

        result = check_customer_can_rent(customer, vehicle, date(2026, 11, 19))

        self.assertTrue(result.eligible)

    def test_car_requires_compatible_license(self):
        customer = SimpleNamespace(
            date_of_birth=date(2000, 1, 1),
            driver_licenses=[
                SimpleNamespace(
                    license_class="A1",
                    status="approved",
                    expiry_date=date(2030, 1, 1),
                )
            ],
        )
        vehicle = SimpleNamespace(vehicle_type="CAR")

        result = check_customer_can_rent(customer, vehicle, date(2026, 11, 19))

        self.assertFalse(result.eligible)
        self.assertIn("không phù hợp", result.first_reason())

    def test_expired_license_is_rejected(self):
        customer = SimpleNamespace(
            date_of_birth=date(2000, 1, 1),
            driver_licenses=[
                SimpleNamespace(
                    license_class="B2",
                    status="verified",
                    expiry_date=date(2026, 11, 18),
                )
            ],
        )
        vehicle = SimpleNamespace(vehicle_type="CAR")

        result = check_customer_can_rent(customer, vehicle, date(2026, 11, 19))

        self.assertFalse(result.eligible)
        self.assertIn("hết hạn", result.first_reason())

    def test_unverified_license_is_rejected(self):
        customer = SimpleNamespace(
            date_of_birth=date(2000, 1, 1),
            driver_licenses=[
                SimpleNamespace(
                    license_class="B2",
                    status="pending",
                    expiry_date=date(2030, 1, 1),
                )
            ],
        )
        vehicle = SimpleNamespace(vehicle_type="CAR")

        result = check_customer_can_rent(customer, vehicle, date(2026, 11, 19))

        self.assertFalse(result.eligible)
        self.assertIn("GPLX", result.first_reason())


if __name__ == "__main__":
    unittest.main()
