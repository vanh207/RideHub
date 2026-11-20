import unittest

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401
from app.db.session import Base
from app.models.feedback import Complaint, Review


class FeedbackModelTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.session = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def test_feedback_tables_are_registered(self):
        self.assertTrue({
            "reviews",
            "complaints",
            "complaint_evidence",
            "complaint_status_histories",
        }.issubset(Base.metadata.tables))

    def test_review_rating_must_be_between_one_and_five(self):
        self.session.add(Review(booking_id=1, reviewer_id=1, rating=6))

        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_booking_can_have_only_one_review_per_reviewer(self):
        self.session.add(Review(booking_id=1, reviewer_id=1, rating=5))
        self.session.commit()
        self.session.add(Review(booking_id=1, reviewer_id=1, rating=4))

        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_complaint_status_must_be_supported(self):
        self.session.add(Complaint(
            booking_id=1,
            reporter_id=1,
            category="VEHICLE",
            subject="Test complaint",
            description="Test description",
            status="UNKNOWN",
        ))

        with self.assertRaises(IntegrityError):
            self.session.commit()


if __name__ == "__main__":
    unittest.main()
