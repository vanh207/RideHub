import sys
import os
from decimal import Decimal
from datetime import datetime

# Đảm bảo import được các module trong app khi chạy trực tiếp file
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal, engine, Base
from app.models.store import Store
from app.models.vehicle import Vehicle, VehicleImage, VehicleStatusHistory
from app.models.delivery import DeliveryFeeZone, DeliveryPoint


# ==============================================================================
# 1. DANH SÁCH 20 PHƯƠNG TIỆN MẪU (10 XE MÁY & 10 Ô TÔ ĐA DẠNG PHÂN KHÚC)
# ==============================================================================
SAMPLE_VEHICLES = [
    # ---------------- 10 XE MÁY ----------------
    {
        "vehicle_type": "MOTORBIKE",
        "plate_number": "59B1-102.34",
        "brand": "Honda",
        "model": "Vision 110cc Smartkey",
        "year_of_manufacture": 2023,
        "engine_capacity": 110,
        "transmission_type": "Tay ga",
        "seats": 2,
        "body_type": "Xe ga",
        "fuel_type": "Xăng",
        "price_per_day": Decimal("130000"),
        "price_per_hour": Decimal("20000"),
        "description": "Xe tay ga đô thị nhỏ gọn, tiết kiệm xăng, trang bị khóa thông minh Smartkey an toàn.",
        "image_url": "https://images.unsplash.com/photo-1558981403-c5f9899a28bc?w=800&auto=format&fit=crop",
    },
    {
        "vehicle_type": "MOTORBIKE",
        "plate_number": "59B1-567.89",
        "brand": "Honda",
        "model": "Air Blade 160 ABS",
        "year_of_manufacture": 2023,
        "engine_capacity": 160,
        "transmission_type": "Tay ga",
        "seats": 2,
        "body_type": "Xe ga",
        "fuel_type": "Xăng",
        "price_per_day": Decimal("180000"),
        "price_per_hour": Decimal("25000"),
        "description": "Động cơ eSP+ 160cc mạnh mẽ, phanh ABS chống bó cứng, cốp xe rộng rãi phù hợp đi phố và phượt.",
        "image_url": "https://images.unsplash.com/photo-1568772585407-9361f9bf3a87?w=800&auto=format&fit=crop",
    },
    {
        "vehicle_type": "MOTORBIKE",
        "plate_number": "59B1-999.88",
        "brand": "Honda",
        "model": "SH 150i ABS Thể Thao",
        "year_of_manufacture": 2024,
        "engine_capacity": 150,
        "transmission_type": "Tay ga",
        "seats": 2,
        "body_type": "Xe ga cao cấp",
        "fuel_type": "Xăng",
        "price_per_day": Decimal("320000"),
        "price_per_hour": Decimal("45000"),
        "description": "Dòng xe tay ga cao cấp thời thượng, phanh ABS 2 kênh, kết nối bluetooth điện thoại.",
        "image_url": "https://images.unsplash.com/photo-1599819811279-d5ad9cccf838?w=800&auto=format&fit=crop",
    },
    {
        "vehicle_type": "MOTORBIKE",
        "plate_number": "59B1-223.45",
        "brand": "Honda",
        "model": "Wave Alpha 110",
        "year_of_manufacture": 2022,
        "engine_capacity": 110,
        "transmission_type": "Số sàn",
        "seats": 2,
        "body_type": "Xe số",
        "fuel_type": "Xăng",
        "price_per_day": Decimal("90000"),
        "price_per_hour": Decimal("15000"),
        "description": "Xe số quốc dân bền bỉ, tiết kiệm nhiên liệu tối đa, chi phí thuê siêu tiết kiệm cho sinh viên.",
        "image_url": "https://images.unsplash.com/photo-1609630875171-b1321377ee65?w=800&auto=format&fit=crop",
    },
    {
        "vehicle_type": "MOTORBIKE",
        "plate_number": "59B1-778.90",
        "brand": "Yamaha",
        "model": "Exciter 155 VVA GP",
        "year_of_manufacture": 2023,
        "engine_capacity": 155,
        "transmission_type": "Côn tay",
        "seats": 2,
        "body_type": "Xe côn tay",
        "fuel_type": "Xăng",
        "price_per_day": Decimal("200000"),
        "price_per_hour": Decimal("30000"),
        "description": "Xe côn tay thể thao với van biến thiên VVA bốc khỏe, thích hợp đi tour xa, đường đèo dốc.",
        "image_url": "https://images.unsplash.com/photo-1558981420-87aa9dad1c89?w=800&auto=format&fit=crop",
    },
    {
        "vehicle_type": "MOTORBIKE",
        "plate_number": "59B1-334.56",
        "brand": "Yamaha",
        "model": "Grande Hybrid BlueCore 125",
        "year_of_manufacture": 2023,
        "engine_capacity": 125,
        "transmission_type": "Tay ga",
        "seats": 2,
        "body_type": "Xe ga",
        "fuel_type": "Xăng lai điện",
        "price_per_day": Decimal("160000"),
        "price_per_hour": Decimal("25000"),
        "description": "Kiểu dáng thanh lịch châu Âu, trợ lực Hybrid khởi động mượt mà, cốp cực đại 27 lít.",
        "image_url": "https://images.unsplash.com/photo-1558980664-3a031cf67ea8?w=800&auto=format&fit=crop",
    },
    {
        "vehicle_type": "MOTORBIKE",
        "plate_number": "59B1-445.67",
        "brand": "VinFast",
        "model": "Feliz S Pin LFP",
        "year_of_manufacture": 2023,
        "engine_capacity": 0,
        "transmission_type": "Tự động",
        "seats": 2,
        "body_type": "Xe máy điện",
        "fuel_type": "Điện",
        "price_per_day": Decimal("140000"),
        "price_per_hour": Decimal("20000"),
        "description": "Xe máy điện công nghệ pin LFP đi được 198km/sạc, thân thiện môi trường, chống nước IP67.",
        "image_url": "https://images.unsplash.com/photo-1591637333184-19aa84b3e01f?w=800&auto=format&fit=crop",
    },
    {
        "vehicle_type": "MOTORBIKE",
        "plate_number": "59B1-881.23",
        "brand": "VinFast",
        "model": "Klara S 2023",
        "year_of_manufacture": 2023,
        "engine_capacity": 0,
        "transmission_type": "Tự động",
        "seats": 2,
        "body_type": "Xe máy điện",
        "fuel_type": "Điện",
        "price_per_day": Decimal("170000"),
        "price_per_hour": Decimal("25000"),
        "description": "Xe điện thời trang cao cấp kiểu Ý, vận hành êm ái, định vị GPS qua app thông minh.",
        "image_url": "https://images.unsplash.com/photo-1558981806-ec527fa84c39?w=800&auto=format&fit=crop",
    },
    {
        "vehicle_type": "MOTORBIKE",
        "plate_number": "59B1-667.12",
        "brand": "Dat Bike",
        "model": "Weaver++ Côn điện",
        "year_of_manufacture": 2023,
        "engine_capacity": 0,
        "transmission_type": "Tự động",
        "seats": 2,
        "body_type": "Xe máy điện",
        "fuel_type": "Điện",
        "price_per_day": Decimal("220000"),
        "price_per_hour": Decimal("35000"),
        "description": "Xe máy điện hiệu năng cao made in Vietnam, tăng tốc 0-50km/h chỉ trong 3 giây, sạc nhanh 3 giờ.",
        "image_url": "https://images.unsplash.com/photo-1558980664-769d59546b3d?w=800&auto=format&fit=crop",
    },
    {
        "vehicle_type": "MOTORBIKE",
        "plate_number": "59B1-554.32",
        "brand": "Honda",
        "model": "Winner X 150 ABS",
        "year_of_manufacture": 2023,
        "engine_capacity": 150,
        "transmission_type": "Côn tay",
        "seats": 2,
        "body_type": "Xe côn tay",
        "fuel_type": "Xăng",
        "price_per_day": Decimal("190000"),
        "price_per_hour": Decimal("28000"),
        "description": "Thiết kế khí động học sắc sảo, côn số nhẹ nhàng, phanh ABS bánh trước chống trượt.",
        "image_url": "https://images.unsplash.com/photo-1568772585407-9361f9bf3a87?w=800&auto=format&fit=crop",
    },

    # ---------------- 10 Ô TÔ ----------------
    {
        "vehicle_type": "CAR",
        "plate_number": "51K-123.45",
        "brand": "VinFast",
        "model": "VF5 Plus 2023",
        "year_of_manufacture": 2023,
        "engine_capacity": 0,
        "transmission_type": "Tự động",
        "seats": 5,
        "body_type": "A-SUV",
        "fuel_type": "Điện",
        "price_per_day": Decimal("650000"),
        "price_per_hour": Decimal("80000"),
        "description": "SUV điện 5 chỗ đô thị năng động, hỗ trợ ADAS thông minh, chi phí vận hành siêu rẻ.",
        "image_url": "https://images.unsplash.com/photo-1533473359331-0135ef1b58bf?w=800&auto=format&fit=crop",
    },
    {
        "vehicle_type": "CAR",
        "plate_number": "51K-234.56",
        "brand": "VinFast",
        "model": "VF3 Mini SUV",
        "year_of_manufacture": 2024,
        "engine_capacity": 0,
        "transmission_type": "Tự động",
        "seats": 4,
        "body_type": "Mini SUV",
        "fuel_type": "Điện",
        "price_per_day": Decimal("450000"),
        "price_per_hour": Decimal("60000"),
        "description": "Mẫu SUV điện cỡ nhỏ cá tính, dễ dàng luồn lách mọi ngõ phố, phong cách hiện đại.",
        "image_url": "https://images.unsplash.com/photo-1549399542-7e3f8b79c341?w=800&auto=format&fit=crop",
    },
    {
        "vehicle_type": "CAR",
        "plate_number": "51K-345.67",
        "brand": "VinFast",
        "model": "VF8 Eco AWD",
        "year_of_manufacture": 2023,
        "engine_capacity": 0,
        "transmission_type": "Tự động",
        "seats": 5,
        "body_type": "D-SUV",
        "fuel_type": "Điện",
        "price_per_day": Decimal("1200000"),
        "price_per_hour": Decimal("150000"),
        "description": "SUV điện cỡ D sang trọng, dẫn động 4 bánh toàn thời gian 402 mã lực, gói tự hành thông minh.",
        "image_url": "https://images.unsplash.com/photo-1617788138017-80ad40651399?w=800&auto=format&fit=crop",
    },
    {
        "vehicle_type": "CAR",
        "plate_number": "51H-567.89",
        "brand": "Toyota",
        "model": "Vios 1.5G CVT",
        "year_of_manufacture": 2023,
        "engine_capacity": 1500,
        "transmission_type": "Tự động",
        "seats": 5,
        "body_type": "Sedan",
        "fuel_type": "Xăng",
        "price_per_day": Decimal("700000"),
        "price_per_hour": Decimal("90000"),
        "description": "Mẫu sedan gia đình bền bỉ số 1, điều hòa mát sâu, khoang hành khách rộng rãi và êm ái.",
        "image_url": "https://images.unsplash.com/photo-1621007947382-bb3c3994e3fb?w=800&auto=format&fit=crop",
    },
    {
        "vehicle_type": "CAR",
        "plate_number": "51H-678.90",
        "brand": "Hyundai",
        "model": "Accent 1.4 AT Đặc biệt",
        "year_of_manufacture": 2023,
        "engine_capacity": 1400,
        "transmission_type": "Tự động",
        "seats": 5,
        "body_type": "Sedan",
        "fuel_type": "Xăng",
        "price_per_day": Decimal("650000"),
        "price_per_hour": Decimal("85000"),
        "description": "Ngoại hình trẻ trung, có cửa sổ trời, cruise control, màn hình cảm ứng kết nối Apple CarPlay.",
        "image_url": "https://images.unsplash.com/photo-1616422285623-13ff0162193c?w=800&auto=format&fit=crop",
    },
    {
        "vehicle_type": "CAR",
        "plate_number": "51H-789.01",
        "brand": "Mazda",
        "model": "Mazda 3 Premium 1.5L",
        "year_of_manufacture": 2023,
        "engine_capacity": 1500,
        "transmission_type": "Tự động",
        "seats": 5,
        "body_type": "Sedan",
        "fuel_type": "Xăng",
        "price_per_day": Decimal("850000"),
        "price_per_hour": Decimal("110000"),
        "description": "Thiết kế KODO đẳng cấp như xe sang, âm thanh loa sống động, cảm giác lái thể thao và đầm chắc.",
        "image_url": "https://images.unsplash.com/photo-1542282088-72c9c27ed0cd?w=800&auto=format&fit=crop",
    },
    {
        "vehicle_type": "CAR",
        "plate_number": "51H-890.12",
        "brand": "Kia",
        "model": "Seltos 1.4 Turbo Premium",
        "year_of_manufacture": 2023,
        "engine_capacity": 1400,
        "transmission_type": "Tự động",
        "seats": 5,
        "body_type": "B-SUV",
        "fuel_type": "Xăng",
        "price_per_day": Decimal("900000"),
        "price_per_hour": Decimal("115000"),
        "description": "SUV 5 chỗ gầm cao đa dụng, động cơ tăng áp bốc, làm mát ghế lái tiện nghi cho ngày nắng nóng.",
        "image_url": "https://images.unsplash.com/photo-1583121274602-3e2820c69888?w=800&auto=format&fit=crop",
    },
    {
        "vehicle_type": "CAR",
        "plate_number": "51H-901.23",
        "brand": "Mitsubishi",
        "model": "Xpander Cross 2023",
        "year_of_manufacture": 2023,
        "engine_capacity": 1500,
        "transmission_type": "Tự động",
        "seats": 7,
        "body_type": "MPV 7 chỗ",
        "fuel_type": "Xăng",
        "price_per_day": Decimal("950000"),
        "price_per_hour": Decimal("120000"),
        "description": "Xe 7 chỗ rộng rãi lý tưởng cho gia đình du lịch cuối tuần, gầm cao 225mm vượt mọi địa hình ngập nước.",
        "image_url": "https://images.unsplash.com/photo-1511919884226-fd3cad34687c?w=800&auto=format&fit=crop",
    },
    {
        "vehicle_type": "CAR",
        "plate_number": "51H-012.34",
        "brand": "Toyota",
        "model": "Fortuner Legender 2.4 AT 4x2",
        "year_of_manufacture": 2023,
        "engine_capacity": 2400,
        "transmission_type": "Tự động",
        "seats": 7,
        "body_type": "SUV 7 chỗ",
        "fuel_type": "Dầu (Diesel)",
        "price_per_day": Decimal("1350000"),
        "price_per_hour": Decimal("180000"),
        "description": "Dòng SUV 7 chỗ khung gầm rời khỏe khoắn, máy dầu tiết kiệm, chinh phục mọi cung đường xa.",
        "image_url": "https://images.unsplash.com/photo-1519641471654-76ce0107ad1b?w=800&auto=format&fit=crop",
    },
    {
        "vehicle_type": "CAR",
        "plate_number": "51C-456.78",
        "brand": "Ford",
        "model": "Ranger Wildtrak 2.0L Bi-Turbo 4x4",
        "year_of_manufacture": 2023,
        "engine_capacity": 2000,
        "transmission_type": "Tự động",
        "seats": 5,
        "body_type": "Bán tải",
        "fuel_type": "Dầu (Diesel)",
        "price_per_day": Decimal("1100000"),
        "price_per_hour": Decimal("140000"),
        "description": "Vua bán tải 2 cầu vi sai cơ học, thùng sau rộng chở nhiều hành lý, thiết kế cơ bắp đậm chất Mỹ.",
        "image_url": "https://images.unsplash.com/photo-1559416523-140ddc3d238c?w=800&auto=format&fit=crop",
    },
]


# ==============================================================================
# 2. KHU VỰC TÍNH PHÍ GIAO NHẬN (DELIVERY FEE ZONES)
# ==============================================================================
SAMPLE_ZONES = [
    {"area": "Khu vực Trung tâm Quận 1 & Quận 3", "delivery_fee": Decimal("0.00")},
    {"area": "Khu vực Bình Thạnh & Phú Nhuận", "delivery_fee": Decimal("30000.00")},
    {"area": "Khu vực Sân bay Tân Sơn Nhất & Tân Bình", "delivery_fee": Decimal("40000.00")},
    {"area": "Khu vực Quận 7 & Khu Đô Thị Sala (TP Thủ Đức)", "delivery_fee": Decimal("50000.00")},
    {"area": "Khu vực Bến xe Miền Đông Mới & TP Dĩ An", "delivery_fee": Decimal("80000.00")},
]


# ==============================================================================
# 3. CÁC ĐIỂM GIAO NHẬN MẪU (DELIVERY POINTS)
# ==============================================================================
SAMPLE_POINTS = [
    {
        "zone_area": "Khu vực Sân bay Tân Sơn Nhất & Tân Bình",
        "name": "Sân bay Quốc tế Tân Sơn Nhất (Ga T1)",
        "address": "Cột số 12, Ga Quốc nội T1, Đường Trường Sơn, Phường 2, Tân Bình",
        "area": "Tân Bình",
        "delivery_fee": Decimal("40000.00"),
    },
    {
        "zone_area": "Khu vực Sân bay Tân Sơn Nhất & Tân Bình",
        "name": "Sân bay Quốc tế Tân Sơn Nhất (Ga T2 Quốc tế)",
        "address": "Cột số 9, Ga Quốc tế T2, Đường Trường Sơn, Phường 2, Tân Bình",
        "area": "Tân Bình",
        "delivery_fee": Decimal("40000.00"),
    },
    {
        "zone_area": "Khu vực Trung tâm Quận 1 & Quận 3",
        "name": "Ga Sài Gòn (Đường Nguyễn Thông)",
        "address": "Số 01 Nguyễn Thông, Phường 9, Quận 3, TP. Hồ Chí Minh",
        "area": "Quận 3",
        "delivery_fee": Decimal("0.00"),
    },
    {
        "zone_area": "Khu vực Trung tâm Quận 1 & Quận 3",
        "name": "Chợ Bến Thành (Cửa Tây)",
        "address": "Đường Phan Chu Trinh, Phường Bến Thành, Quận 1, TP. Hồ Chí Minh",
        "area": "Quận 1",
        "delivery_fee": Decimal("0.00"),
    },
    {
        "zone_area": "Khu vực Bình Thạnh & Phú Nhuận",
        "name": "Tòa nhà Landmark 81 (Sảnh chính)",
        "address": "720A Điện Biên Phủ, Phường 22, Quận Bình Thạnh, TP. Hồ Chí Minh",
        "area": "Bình Thạnh",
        "delivery_fee": Decimal("30000.00"),
    },
    {
        "zone_area": "Khu vực Bình Thạnh & Phú Nhuận",
        "name": "Công viên Gia Định (Cổng Hoàng Minh Giám)",
        "address": "Đường Hoàng Minh Giám, Phường 3, Quận Gò Vấp / Phú Nhuận",
        "area": "Phú Nhuận",
        "delivery_fee": Decimal("30000.00"),
    },
    {
        "zone_area": "Khu vực Quận 7 & Khu Đô Thị Sala (TP Thủ Đức)",
        "name": "Khu Đô Thị Sala (Sảnh Sarimi)",
        "address": "Đại lộ Mai Chí Thọ, Phường An Lợi Đông, TP. Thủ Đức",
        "area": "TP. Thủ Đức",
        "delivery_fee": Decimal("50000.00"),
    },
    {
        "zone_area": "Khu vực Quận 7 & Khu Đô Thị Sala (TP Thủ Đức)",
        "name": "Trung tâm Triển lãm SECC Quận 7",
        "address": "799 Đại lộ Nguyễn Văn Linh, Phường Tân Phú, Quận 7",
        "area": "Quận 7",
        "delivery_fee": Decimal("50000.00"),
    },
    {
        "zone_area": "Khu vực Bến xe Miền Đông Mới & TP Dĩ An",
        "name": "Bến xe Miền Đông Mới (Bãi trả khách)",
        "address": "501 Hoàng Hữu Nam, Phường Long Bình, TP. Thủ Đức",
        "area": "TP. Thủ Đức",
        "delivery_fee": Decimal("80000.00"),
    },
]


def seed_vehicles_and_delivery():
    """Thực thi chèn dữ liệu mẫu an toàn (Idempotent - không bị trùng lặp)."""
    db: Session = SessionLocal()
    try:
        print("\n" + "=" * 70)
        print("🚀 BẮT ĐẦU SEED DỮ LIỆU: 20 PHƯƠNG TIỆN & ĐIỂM GIAO NHẬN")
        print("=" * 70)

        # 1. Tìm hoặc tạo Store hợp lệ để gán xe
        store = db.query(Store).filter(Store.status == "APPROVED").first()
        if not store:
            store = db.query(Store).first()

        if not store:
            print("⚠️ Chưa tìm thấy cửa hàng nào trong bảng `stores`. Đang tạo cửa hàng mặc định...")
            store = Store(
                owner_user_id=1,
                name="GreenRide - Trụ sở Quận 1",
                description="Hệ thống cho thuê xe tự lái và xe máy uy tín tại TP.HCM",
                phone="0902222222",
                email="store@ridehub.vn",
                address="120 Lê Lợi, Phường Bến Thành",
                city="TP. Hồ Chí Minh",
                district="Quận 1",
                ward="Phường Bến Thành",
                status="APPROVED",
                approved_at=datetime.now(),
            )
            db.add(store)
            db.commit()
            db.refresh(store)

        store_id = store.id
        print(f"👉 Gán dữ liệu cho Cửa hàng: [ID: {store_id}] {store.name}")

        # 2. Seed 20 Phương tiện & Hình ảnh
        added_vehicles_count = 0
        for item in SAMPLE_VEHICLES:
            plate = item["plate_number"]
            # Kiểm tra xe đã tồn tại theo biển số chưa
            existing_v = db.query(Vehicle).filter(
                Vehicle.store_id == store_id,
                Vehicle.plate_number == plate,
            ).first()

            if not existing_v:
                v = Vehicle(
                    store_id=store_id,
                    vehicle_type=item["vehicle_type"],
                    plate_number=plate,
                    brand=item["brand"],
                    model=item["model"],
                    year_of_manufacture=item["year_of_manufacture"],
                    engine_capacity=item["engine_capacity"],
                    transmission_type=item["transmission_type"],
                    seats=item["seats"],
                    body_type=item["body_type"],
                    fuel_type=item["fuel_type"],
                    price_per_day=item["price_per_day"],
                    price_per_hour=item["price_per_hour"],
                    current_status="AVAILABLE",
                    description=item["description"],
                    is_active=True,
                )
                db.add(v)
                db.commit()
                db.refresh(v)

                # Thêm ảnh đại diện
                img = VehicleImage(
                    vehicle_id=v.id,
                    image_url=item["image_url"],
                    is_primary=True,
                    sort_order=1,
                )
                db.add(img)

                # Ghi nhận log lịch sử khởi tạo
                history = VehicleStatusHistory(
                    vehicle_id=v.id,
                    from_status=None,
                    to_status="AVAILABLE",
                    changed_by="SYSTEM_SEED",
                    reason="Khởi tạo xe mẫu ban đầu",
                    note="Xe mới thêm vào kho sẵn sàng cho thuê",
                )
                db.add(history)
                db.commit()

                added_vehicles_count += 1
                print(f"  [+] Đã thêm xe: {v.vehicle_type:<9} | {v.plate_number:<11} | {v.brand} {v.model}")
            else:
                print(f"  [~] Xe {plate} đã tồn tại, bỏ qua.")

        print(f"\n✅ Tổng kết xe: Đã thêm mới {added_vehicles_count} xe (tổng 20 xe trong danh sách).")

        # 3. Seed Khu vực giao nhận (DeliveryFeeZone)
        zone_map = {}  # Lưu area -> id để gán cho delivery points
        print("\n📦 CẬP NHẬT CÁC KHU VỰC TÍNH PHÍ GIAO NHẬN (ZONES):")
        for z_data in SAMPLE_ZONES:
            area_name = z_data["area"]
            zone = db.query(DeliveryFeeZone).filter(
                DeliveryFeeZone.store_id == store_id,
                DeliveryFeeZone.area == area_name,
            ).first()

            if not zone:
                zone = DeliveryFeeZone(
                    store_id=store_id,
                    area=area_name,
                    delivery_fee=z_data["delivery_fee"],
                    is_active=True,
                )
                db.add(zone)
                db.commit()
                db.refresh(zone)
                print(f"  [+] Đã thêm khu vực: {zone.area} (Phí: {int(zone.delivery_fee):,} đ)")
            else:
                print(f"  [~] Khu vực '{zone.area}' đã có.")

            zone_map[area_name] = zone.id

        # 4. Seed Điểm giao nhận cụ thể (DeliveryPoint)
        print("\n📍 CẬP NHẬT CÁC ĐIỂM GIAO NHẬN MẪU (DELIVERY POINTS):")
        for p_data in SAMPLE_POINTS:
            point_name = p_data["name"]
            zone_id = zone_map.get(p_data["zone_area"])

            point = db.query(DeliveryPoint).filter(
                DeliveryPoint.store_id == store_id,
                DeliveryPoint.name == point_name,
            ).first()

            if not point:
                point = DeliveryPoint(
                    store_id=store_id,
                    delivery_fee_zone_id=zone_id,
                    name=point_name,
                    address=p_data["address"],
                    area=p_data["area"],
                    delivery_fee=p_data["delivery_fee"],
                    is_active=True,
                )
                db.add(point)
                db.commit()
                print(f"  [+] Đã thêm điểm: {point.name} ({point.address[:45]}...)")
            else:
                print(f"  [~] Điểm giao nhận '{point.name}' đã có.")

        print("\n" + "=" * 70)
        print("🎉 HOÀN THÀNH SEED DỮ LIỆU PHƯƠNG TIỆN & ĐIỂM GIAO NHẬN THÀNH CÔNG!")
        print("=" * 70 + "\n")

    except Exception as e:
        db.rollback()
        print(f"\n❌ LỖI TRONG QUÁ TRÌNH SEED: {e}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    seed_vehicles_and_delivery()