import unittest
from datetime import date
from types import SimpleNamespace

from app.routers.bookings import (
    BookingEligibilityRequest,
    check_booking_eligibility,
)


class BookingEligibilityApiTest(unittest.TestCase):
    def test_vehicle_type_request_returns_ineligibility_reasons(self):
        customer = SimpleNamespace(date_of_birth=None, driver_licenses=[])
        request = BookingEligibilityRequest(
            vehicle_type="MOTORBIKE",
            rental_start="2026-11-20T12:00:00",
        )

        result = check_booking_eligibility(request, db=None, current_user=customer)

        self.assertFalse(result.eligible)
        self.assertIn("ngày sinh", result.reasons[0])

    def test_vehicle_id_request_still_looks_up_vehicle(self):
        vehicle = SimpleNamespace(vehicle_type="MOTORBIKE")
        query = SimpleNamespace(
            filter=lambda *_: SimpleNamespace(first=lambda: vehicle)
        )
        db = SimpleNamespace(query=lambda *_: query)
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
        request = BookingEligibilityRequest(vehicle_id=1)

        result = check_booking_eligibility(request, db=db, current_user=customer)

        self.assertTrue(result.eligible)


if __name__ == "__main__":
    unittest.main()
