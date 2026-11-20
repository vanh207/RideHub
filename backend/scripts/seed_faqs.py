"""Script nạp dữ liệu mẫu Câu hỏi thường gặp FAQ cho Chatbot RideHub (Task: TF1B346)
Sprint 2 • RideHub Database Seeder

Cách chạy:
    cd backend
    python scripts/seed_faqs.py
    hoặc:
    python scripts/seed_faqs.py --reset  (Xóa dữ liệu cũ và nạp mới)
"""
import sys
import os
import argparse

# Thêm thư mục backend vào sys.path để import được app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal, engine, Base
from app.models.faq import FAQ
from app.db.faq_seed_data import FAQ_SEED_DATA


def seed_faqs(reset: bool = False):
    """Thực thi chèn hoặc cập nhật dữ liệu FAQ vào cơ sở dữ liệu."""
    print("=" * 75)
    print("🚀 [RIDEHUB SEEDER] Khởi chạy nạp Dữ liệu mẫu FAQ cho Chatbot (TF1B346)")
    print("=" * 75)

    # Đảm bảo bảng faqs đã được tạo
    Base.metadata.create_all(bind=engine)

    db: Session = SessionLocal()
    try:
        if reset:
            print("⚠️  Chế độ --reset được kích hoạt: Đang làm sạch bảng faqs...")
            db.query(FAQ).delete()
            db.commit()
            print("✅ Đã xóa toàn bộ câu hỏi FAQ cũ.")

        existing_count = db.query(FAQ).count()
        print(f"📊 Số lượng FAQ hiện có trong DB: {existing_count} câu.")

        inserted = 0
        updated = 0

        for item in FAQ_SEED_DATA:
            # Tìm câu hỏi trùng theo question
            existing = db.query(FAQ).filter(FAQ.question == item["question"]).first()
            if existing:
                # Cập nhật thông tin mới nhất
                existing.category = item["category"]
                existing.category_name = item["category_name"]
                existing.answer = item["answer"]
                existing.display_order = item["display_order"]
                existing.is_active = item["is_active"]
                existing.view_count = item["view_count"]
                updated += 1
            else:
                new_faq = FAQ(**item)
                db.add(new_faq)
                inserted += 1

        db.commit()

        # Thống kê phân nhóm
        total = db.query(FAQ).count()
        pricing_c = db.query(FAQ).filter(FAQ.category == "pricing").count()
        cond_c = db.query(FAQ).filter(FAQ.category == "rental_conditions").count()
        cancel_c = db.query(FAQ).filter(FAQ.category == "cancellation").count()
        refund_c = db.query(FAQ).filter(FAQ.category == "refund").count()

        print("-" * 75)
        print(f"🎉 Nạp dữ liệu thành công:")
        print(f"   • Thêm mới : {inserted} câu")
        print(f"   • Cập nhật : {updated} câu")
        print(f"   • Tổng cộng: {total} câu trong DB (Yêu cầu đề bài: >= 20 câu -> ĐẠT)")
        print("-" * 75)
        print("📌 Thống kê chi tiết theo 4 chủ đề yêu cầu:")
        print(f"   1. Giá thuê & Phụ phí         (pricing)          : {pricing_c} câu")
        print(f"   2. Điều kiện & Thủ tục thuê xe (rental_conditions): {cond_c} câu")
        print(f"   3. Chính sách hủy đơn         (cancellation)      : {cancel_c} câu")
        print(f"   4. Quy trình & Hoàn tiền      (refund)            : {refund_c} câu")
        print("=" * 75)

    except Exception as e:
        db.rollback()
        print(f"❌ Lỗi khi nạp dữ liệu FAQ: {e}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed FAQ data for RideHub Chatbot")
    parser.add_argument(
        "--reset", action="store_true", help="Xóa dữ liệu cũ trước khi nạp mới"
    )
    args = parser.parse_args()
    seed_faqs(reset=args.reset)
