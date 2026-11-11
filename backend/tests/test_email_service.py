"""Kiểm thử tự động cho EmailService (chế độ Mock & SMTP).
Chạy: python -m unittest backend/tests/test_email_service.py
"""
import unittest
from app.services.email_service import EmailService, MockEmailSender, SMTPEmailSender


class TestEmailService(unittest.TestCase):
    def setUp(self):
        # Khởi tạo EmailService chạy với backend Mock
        self.service = EmailService(backend_type="mock")

    def test_mock_sender_initialization(self):
        self.assertIsInstance(self.service.sender, MockEmailSender)
        self.assertEqual(self.service.backend_name, "Mock")

    def test_send_booking_confirmation(self):
        result = self.service.send_booking_confirmation(
            to_email="test_customer@gmail.com",
            customer_name="Nguyễn Văn Quân",
            booking_id=88421,
            vehicle_name="Mazda CX-5 2.0L Premium (2024)",
            start_time="14:00 - 10/11/2026",
            end_time="14:00 - 13/11/2026",
            total_amount=2850000,
            deposit_amount=10000000,
        )
        self.assertTrue(result)
        last_sent = self.service.sender.get_last_sent()
        self.assertIsNotNone(last_sent)
        self.assertEqual(last_sent.to_email, "test_customer@gmail.com")
        self.assertIn("88421", last_sent.subject)

    def test_send_handover_protocol_notification(self):
        result = self.service.send_handover_protocol_notification(
            to_email="test_customer@gmail.com",
            customer_name="Nguyễn Văn Quân",
            protocol_code="BB-202611-0891",
            booking_id=88421,
            vehicle_name="Mazda CX-5 2024",
            license_plate="43A-688.92",
            protocol_type="CHECK_OUT",
            odo_reading=18420,
            fuel_level="FULL",
        )
        self.assertTrue(result)
        last_sent = self.service.sender.get_last_sent()
        self.assertIn("BB-202611-0891", last_sent.subject)

    def test_send_deposit_refund_notification(self):
        result = self.service.send_deposit_refund_notification(
            to_email="test_customer@gmail.com",
            customer_name="Nguyễn Văn Quân",
            booking_id=88421,
            refund_amount=8000000,
            hold_fine_deposit=2000000,
        )
        self.assertTrue(result)
        last_sent = self.service.sender.get_last_sent()
        self.assertIn("hoàn tiền cọc", last_sent.subject.lower())


if __name__ == "__main__":
    unittest.main()

