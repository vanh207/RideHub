from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.booking_status import COMPLETED, normalize_status
from app.models.booking import Booking
from app.models.feedback import Complaint, ComplaintEvidence, Review
from app.models.store import Store
from app.models.user import User


class BookingFeedbackError(Exception):
    pass


class BookingFeedbackNotFoundError(BookingFeedbackError):
    pass


class BookingFeedbackPermissionError(BookingFeedbackError):
    pass


class BookingFeedbackStateError(BookingFeedbackError):
    pass


class BookingFeedbackConflictError(BookingFeedbackError):
    pass


class BookingFeedbackValidationError(BookingFeedbackError):
    pass


def _get_completed_booking(db: Session, booking_id: int, customer: User) -> Booking:
    booking = (
        db.query(Booking)
        .filter(Booking.id == booking_id)
        .with_for_update()
        .first()
    )
    if booking is None:
        raise BookingFeedbackNotFoundError("Không tìm thấy đơn thuê.")
    if booking.customer_id != customer.id:
        raise BookingFeedbackPermissionError("Chỉ khách thuê của đơn mới được gửi đánh giá hoặc khiếu nại.")
    if normalize_status(booking.status) != COMPLETED:
        raise BookingFeedbackStateError("Chỉ có thể đánh giá hoặc khiếu nại sau khi đơn thuê đã hoàn tất.")
    return booking


def create_booking_review(
    db: Session,
    *,
    booking_id: int,
    customer: User,
    rating: int,
    comment: str | None = None,
) -> Review:
    booking = _get_completed_booking(db, booking_id, customer)
    if not 1 <= rating <= 5:
        raise BookingFeedbackValidationError("Điểm đánh giá phải từ 1 đến 5.")

    existing = db.scalar(
        select(Review).where(
            Review.booking_id == booking.id,
            Review.reviewer_id == customer.id,
        )
    )
    if existing is not None:
        raise BookingFeedbackConflictError("Đơn thuê này đã có đánh giá.")

    review = Review(
        booking_id=booking.id,
        reviewer_id=customer.id,
        rating=rating,
        comment=comment.strip() if comment and comment.strip() else None,
    )
    db.add(review)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise BookingFeedbackConflictError("Đơn thuê này đã có đánh giá.") from exc
    db.refresh(review)
    return review


def create_booking_complaint(
    db: Session,
    *,
    booking_id: int,
    customer: User,
    category: str,
    subject: str,
    description: str,
    against_user_id: int | None = None,
    evidence_urls: list[str] | None = None,
) -> Complaint:
    booking = _get_completed_booking(db, booking_id, customer)

    if against_user_id is not None:
        against = db.query(User).filter(User.id == against_user_id).first()
        if against is None:
            raise BookingFeedbackValidationError("Người bị khiếu nại không tồn tại.")
        if against.id == customer.id:
            raise BookingFeedbackValidationError("Không thể khiếu nại chính khách thuê.")

    if evidence_urls:
        for url in evidence_urls:
            if not isinstance(url, str) or not url.strip():
                raise BookingFeedbackValidationError("URL bằng chứng không hợp lệ.")

    complaint = Complaint(
        booking_id=booking.id,
        reporter_id=customer.id,
        against_user_id=against_user_id,
        category=category.strip(),
        subject=subject.strip(),
        description=description.strip(),
        status="OPEN",
        priority="NORMAL",
    )
    db.add(complaint)
    db.flush()

    for image_url in evidence_urls or []:
        db.add(ComplaintEvidence(
            complaint_id=complaint.id,
            uploaded_by=customer.id,
            image_url=image_url.strip(),
        ))

    db.commit()
    db.refresh(complaint)
    return complaint
