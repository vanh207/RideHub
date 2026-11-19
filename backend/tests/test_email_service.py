"""Unit test cho EmailService (MockEmailSender & SMTPEmailSender).
"""
import unittest
from app.services.email_service import EmailService, MockEmailSender

class TestEmailService(unittest.TestCase):
    def setUp(self):
        self.mock_sender = MockEmailSender()
        self.email_service = EmailService(sender=self.mock_sender)

    def test_send_booking_confirmation(self):
        success = self.email_service.send_booking_confirmation(
            to_email="test@ridehub.vn",
            customer_name="Nguyễn Văn A",
            booking_id="RH-12345",
            vehicle_name="VinFast VF5 Plus",
            start_time="15/11/2026",
            end_time="17/11/2026",
            total_amount=1500000.0,
            deposit_amount=500000.0
        )
        self.assertTrue(success)
        self.assertEqual(len(self.mock_sender.sent_history), 1)
        sent = self.mock_sender.get_last_sent()
        self.assertEqual(sent.to_email, "test@ridehub.vn")
        self.assertIn("RH-12345", sent.subject)

    def test_send_deposit_refund_notification(self):
        success = self.email_service.send_deposit_refund_notification(
            to_email="test@ridehub.vn",
            customer_name="Nguyễn Văn A",
            booking_id="RH-12345",
            refund_amount=500000.0,
        )
        self.assertTrue(success)
        self.assertEqual(len(self.mock_sender.sent_history), 1)
        sent = self.mock_sender.get_last_sent()
        self.assertIn("hoàn tiền cọc", sent.subject.lower())

    def test_send_handover_protocol_notification(self):
        success = self.email_service.send_handover_protocol_notification(
            to_email="test@ridehub.vn",
            customer_name="Nguyễn Văn A",
            protocol_code="BB-20261113-1001",
            booking_id="RH-12345",
            vehicle_name="VinFast VF5 Plus",
            license_plate="51K-889.92",
            protocol_type="CHECK_OUT",
            odo_reading=12000,
            fuel_level="FULL",
        )
        self.assertTrue(success)
        self.assertEqual(len(self.mock_sender.sent_history), 1)

    def test_send_raw_uses_injected_sender(self):
        success = self.email_service.send_raw(
            to_email="test@ridehub.vn",
            subject="Test",
            html_content="<p>Test email</p>",
        )
        self.assertTrue(success)
        self.assertEqual(self.mock_sender.get_last_sent().subject, "Test")

if __name__ == "__main__":
    unittest.main()
