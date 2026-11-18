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
            booking_code="RH-12345",
            vehicle_name="VinFast VF5 Plus",
            start_date="15/11/2026",
            end_date="17/11/2026",
            total_amount=1500000.0,
            deposit_amount=500000.0
        )
        self.assertTrue(success)
        self.assertEqual(len(self.mock_sender.sent_emails), 1)
        sent = self.mock_sender.sent_emails[0]
        self.assertEqual(sent["to"], "test@ridehub.vn")
        self.assertIn("RH-12345", sent["subject"])

    def test_send_booking_cancellation(self):
        success = self.email_service.send_booking_cancellation(
            to_email="test@ridehub.vn",
            customer_name="Nguyễn Văn A",
            booking_code="RH-12345",
            reason="Hết xe cùng phân khúc",
            refund_amount=500000.0
        )
        self.assertTrue(success)
        self.assertEqual(len(self.mock_sender.sent_emails), 1)
        sent = self.mock_sender.sent_emails[0]
        self.assertIn("Hủy", sent["subject"])

    def test_send_handover_report(self):
        success = self.email_service.send_handover_report(
            to_email="test@ridehub.vn",
            customer_name="Nguyễn Văn A",
            protocol_code="BB-20261113-1001",
            vehicle_name="VinFast VF5 Plus",
            license_plate="51K-889.92",
            protocol_type="CHECK_OUT"
        )
        self.assertTrue(success)
        self.assertEqual(len(self.mock_sender.sent_emails), 1)

    def test_send_settlement_receipt(self):
        success = self.email_service.send_settlement_receipt(
            to_email="test@ridehub.vn",
            customer_name="Nguyễn Văn A",
            protocol_code="BB-20261113-1001",
            refund_amount=4500000.0,
            surcharge_total=500000.0
        )
        self.assertTrue(success)

if __name__ == "__main__":
    unittest.main()
