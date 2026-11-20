"""Dữ liệu mẫu 24 câu hỏi thường gặp (FAQ) cho Chatbot & Module Tra cứu RideHub.
Task: TF1B346 | Sprint 2
Bao gồm 4 nhóm chủ đề nghiệp vụ cốt lõi:
1. Giá thuê & Phụ phí (pricing): 6 câu
2. Điều kiện & Thủ tục thuê xe (rental_conditions): 6 câu
3. Chính sách hủy đơn (cancellation): 6 câu
4. Quy trình & Thời gian hoàn tiền (refund): 6 câu
"""

FAQ_SEED_DATA = [
    # -------------------------------------------------------------------------
    # 1. GIÁ THUÊ & PHỤ PHÍ (pricing) - 6 câu
    # -------------------------------------------------------------------------
    {
        "category": "pricing",
        "category_name": "Giá thuê & Phụ phí",
        "question": "Giá thuê xe trên RideHub đã bao gồm thuế VAT và bảo hiểm chưa?",
        "answer": (
            "Dạ giá niêm yết trên ứng dụng và website RideHub đã bao gồm gói Bảo hiểm vật chất xe cơ bản "
            "và thuế VAT 10%. Quý khách có thể tùy chọn nâng cấp gói Bảo hiểm toàn diện (giảm mức khấu trừ "
            "tai nạn về 0đ) khi tiến hành đặt xe trên hệ thống."
        ),
        "display_order": 1,
        "is_active": True,
        "view_count": 145,
    },
    {
        "category": "pricing",
        "category_name": "Giá thuê & Phụ phí",
        "question": "Cách tính thời gian thuê 1 ngày trên RideHub như thế nào?",
        "answer": (
            "Dạ một ngày thuê được tính trọn vẹn 24 giờ kể từ thời điểm quý khách nhận bàn giao xe thực tế. "
            "Ví dụ: Nếu quý khách nhận xe lúc 09:00 sáng thứ Bảy, thời điểm trả xe đúng hạn sẽ là 09:00 sáng "
            "Chủ Nhật mà không bị tính thêm bất kỳ phụ phí nào."
        ),
        "display_order": 2,
        "is_active": True,
        "view_count": 192,
    },
    {
        "category": "pricing",
        "category_name": "Giá thuê & Phụ phí",
        "question": "Phụ phí quá giờ (trả xe trễ hạn) được tính như thế nào?",
        "answer": (
            "Chính sách trả trễ của RideHub được tính rất linh hoạt: Trả trễ dưới 30 phút: Miễn phí hỗ trợ. "
            "Trả trễ từ 30 phút đến dưới 5 giờ: Tính 50.000đ/giờ đối với xe máy điện và 100.000đ/giờ đối với "
            "ô tô tự lái. Trả trễ từ 5 giờ trở lên: Hệ thống sẽ tự động tính thành 1 ngày thuê tiêu chuẩn tiếp theo."
        ),
        "display_order": 3,
        "is_active": True,
        "view_count": 210,
    },
    {
        "category": "pricing",
        "category_name": "Giá thuê & Phụ phí",
        "question": "Hạn mức số km di chuyển mỗi ngày là bao nhiêu và phí vượt km tính ra sao?",
        "answer": (
            "Mỗi ngày thuê tiêu chuẩn trên RideHub có định mức di chuyển là 200 km/ngày và được cộng dồn theo "
            "tổng số ngày thuê của hợp đồng (ví dụ: thuê 3 ngày hạn mức tổng là 600 km). Nếu vượt quá định mức, "
            "phụ phí vượt km là 3.500đ/km đối với ô tô và 1.000đ/km đối với xe máy."
        ),
        "display_order": 4,
        "is_active": True,
        "view_count": 188,
    },
    {
        "category": "pricing",
        "category_name": "Giá thuê & Phụ phí",
        "question": "Chi phí giao xe tận nơi (Sân bay, Khách sạn, Nhà riêng) được tính thế nào?",
        "answer": (
            "RideHub hỗ trợ giao xe tận nơi cực kỳ tiện lợi: Miễn phí giao nhận trong bán kính 5 km từ cửa hàng. "
            "Từ km thứ 6 trở đi: tính 10.000đ/km đối với xe máy và 15.000đ/km đối với ô tô. Phí giao nhận tại Ga "
            "Sân bay áp dụng mức giá trọn gói ưu đãi chỉ từ 50.000đ - 100.000đ/lượt."
        ),
        "display_order": 5,
        "is_active": True,
        "view_count": 130,
    },
    {
        "category": "pricing",
        "category_name": "Giá thuê & Phụ phí",
        "question": "Thuê xe điện VinFast trên RideHub có mất tiền sạc pin không?",
        "answer": (
            "Khi nhận bàn giao xe điện, pin luôn được nạp sẵn từ 80% đến 100%. Quý khách có thể sạc pin miễn phí "
            "hoặc theo đơn giá ưu đãi tại toàn bộ hệ thống trạm sạc VinFast / V-GREEN trên toàn quốc. Khi hoàn trả xe, "
            "quý khách chỉ cần đảm bảo dung lượng pin còn lại trên 20%."
        ),
        "display_order": 6,
        "is_active": True,
        "view_count": 275,
    },

    # -------------------------------------------------------------------------
    # 2. ĐIỀU KIỆN & THỦ TỤC THUÊ XE (rental_conditions) - 6 câu
    # -------------------------------------------------------------------------
    {
        "category": "rental_conditions",
        "category_name": "Điều kiện & Thủ tục thuê xe",
        "question": "Tôi cần chuẩn bị những giấy tờ gì để thuê xe tự lái trên RideHub?",
        "answer": (
            "Quý khách chỉ cần chuẩn bị: (1) CCCD gắn chip hoặc Hộ chiếu (Passport) còn hạn; "
            "(2) Giấy phép lái xe (GPLX) hợp lệ: Hạng B1/B2 trở lên đối với ô tô hoặc Hạng A1/A2 đối với xe máy; "
            "(3) Hoàn tất xác thực eKYC gương mặt online trên ứng dụng trong 3 phút là đủ điều kiện nhận xe."
        ),
        "display_order": 7,
        "is_active": True,
        "view_count": 340,
    },
    {
        "category": "rental_conditions",
        "category_name": "Điều kiện & Thủ tục thuê xe",
        "question": "Độ tuổi tối thiểu và kinh nghiệm lái xe để thuê ô tô tự lái là bao nhiêu?",
        "answer": (
            "Đối với xe máy điện, khách hàng chỉ cần từ đủ 18 tuổi trở lên. Đối với ô tô tự lái, người thuê xe "
            "cần từ đủ 20 tuổi trở lên và sở hữu GPLX còn hiệu lực với thời gian cấp tối thiểu từ 01 năm trở lên "
            "nhằm đảm bảo an toàn tối đa cho chuyến đi."
        ),
        "display_order": 8,
        "is_active": True,
        "view_count": 165,
    },
    {
        "category": "rental_conditions",
        "category_name": "Điều kiện & Thủ tục thuê xe",
        "question": "Mức tiền đặt cọc (thế chấp) giữ xe là bao nhiêu và thanh toán qua đâu?",
        "answer": (
            "Mức tiền đặt cọc giữ xe tiêu chuẩn: Xe máy: từ 1.000.000đ - 2.000.000đ (hoặc để lại xe máy cá nhân "
            "kèm cà vẹt gốc); Ô tô tự lái 4 - 7 chỗ phổ thông: 5.000.000đ/xe. Quý khách thanh toán cọc chuyển khoản "
            "nhanh 24/7 qua cổng VietQR / PayOS trực tiếp ngay trên app."
        ),
        "display_order": 9,
        "is_active": True,
        "view_count": 420,
    },
    {
        "category": "rental_conditions",
        "category_name": "Điều kiện & Thủ tục thuê xe",
        "question": "Bằng lái xe nước ngoài hoặc Bằng lái quốc tế (IDP) có thuê được xe không?",
        "answer": (
            "RideHub hoàn toàn chấp nhận Giấy phép lái xe quốc tế (IDP - International Driving Permit) theo Công ước "
            "Vienna 1968 đi kèm với Hộ chiếu và Bằng lái xe gốc quốc gia còn hạn. Hệ thống AI eKYC của RideHub hỗ trợ "
            "quét nhận diện và đối chiếu giấy tờ của hơn 150 quốc gia."
        ),
        "display_order": 10,
        "is_active": True,
        "view_count": 155,
    },
    {
        "category": "rental_conditions",
        "category_name": "Điều kiện & Thủ tục thuê xe",
        "question": "Quy trình xác thực định danh online eKYC diễn ra như thế nào?",
        "answer": (
            "Sau khi chọn xe, quý khách chụp ảnh rõ nét 2 mặt CCCD/GPLX và quay video nhận diện gương mặt trực tiếp "
            "(Face Liveness). Hệ thống AI tự động trích xuất thông tin, đối khớp khuôn mặt và tự động kích hoạt tài khoản "
            "trong vòng 3 - 5 phút mà không cần phải đến quầy làm thủ tục giấy tờ."
        ),
        "display_order": 11,
        "is_active": True,
        "view_count": 298,
    },
    {
        "category": "rental_conditions",
        "category_name": "Điều kiện & Thủ tục thuê xe",
        "question": "Tôi có thể nhờ người khác lái thay hoặc thuê hộ xe cho bạn bè được không?",
        "answer": (
            "Người đứng tên hợp đồng thuê phải là người lái chính và đã qua xác thực eKYC. Trường hợp có thêm người lái "
            "phụ, quý khách chỉ cần khai báo bổ sung GPLX của người lái phụ vào Biên bản giao nhận điện tử khi nhận xe "
            "để đảm bảo quyền lợi bảo hiểm khi lưu thông."
        ),
        "display_order": 12,
        "is_active": True,
        "view_count": 112,
    },

    # -------------------------------------------------------------------------
    # 3. CHÍNH SÁCH HỦY ĐƠN (cancellation) - 6 câu
    # -------------------------------------------------------------------------
    {
        "category": "cancellation",
        "category_name": "Chính sách hủy đơn",
        "question": "Tôi có thể hủy đơn đặt xe không và biểu phí phạt hủy được quy định ra sao?",
        "answer": (
            "Quý khách có thể chủ động hủy đơn trực tiếp trên ứng dụng: Hủy trước 24 giờ so với giờ nhận xe: Miễn phí "
            "100% (hoàn lại toàn bộ cọc). Hủy trong vòng 12 - 24 giờ trước giờ nhận: Phí phạt hủy là 30% tiền cọc. "
            "Hủy dưới 12 giờ trước giờ nhận: Phí phạt hủy là 50% tiền cọc để bù đắp chi phí chuẩn bị và giữ lịch xe của cửa hàng."
        ),
        "display_order": 13,
        "is_active": True,
        "view_count": 380,
    },
    {
        "category": "cancellation",
        "category_name": "Chính sách hủy đơn",
        "question": "Nếu chuyến bay bị delay hoặc đổi giờ hạ cánh thì cửa hàng xử lý thế nào?",
        "answer": (
            "Khi chuyến bay bị hoãn (delay) hoặc thay đổi giờ bay, quý khách chỉ cần gửi mã chuyến bay hoặc ảnh chụp "
            "thông báo hoãn cho CSKH / Chatbot. Cửa hàng sẽ tự động dời giờ bàn giao xe miễn phí tối đa 5 tiếng và bảo lưu "
            "xe nguyên vẹn cho quý khách."
        ),
        "display_order": 14,
        "is_active": True,
        "view_count": 245,
    },
    {
        "category": "cancellation",
        "category_name": "Chính sách hủy đơn",
        "question": "Làm thế nào để thao tác hủy đơn đặt xe trên ứng dụng RideHub?",
        "answer": (
            "Quý khách vào mục 'Đơn đặt xe của tôi' trên ứng dụng -> Chọn đơn hàng cần hủy -> Nhấn nút 'Yêu cầu hủy đơn' "
            "-> Chọn lý do hủy (Đổi kế hoạch, chuyến bay hoãn, sự cố cá nhân...) -> Xác nhận. Hệ thống sẽ tự động tính "
            "số tiền hoàn trả và gửi thông báo xác nhận ngay lập tức."
        ),
        "display_order": 15,
        "is_active": True,
        "view_count": 175,
    },
    {
        "category": "cancellation",
        "category_name": "Chính sách hủy đơn",
        "question": "Nếu cửa hàng không có đúng dòng xe đã cam kết giao thì giải quyết thế nào?",
        "answer": (
            "Nếu xảy ra trường hợp bất khả kháng cửa hàng không có đúng dòng xe đã đặt, RideHub cam kết: (1) Nâng hạng "
            "xe miễn phí lên dòng xe cao hơn nếu còn xe; hoặc (2) Hoàn trả 100% tiền đặt cọc ngay lập tức kèm voucher "
            "bồi hoàn giảm giá 20% cho chuyến đi tiếp theo của quý khách."
        ),
        "display_order": 16,
        "is_active": True,
        "view_count": 140,
    },
    {
        "category": "cancellation",
        "category_name": "Chính sách hủy đơn",
        "question": "Tôi có được trả xe sớm hơn hợp đồng không và có được hoàn tiền các ngày còn lại?",
        "answer": (
            "Quý khách hoàn toàn có thể trả xe sớm hơn hạn hợp đồng. Tiền thuê của các ngày đã sử dụng sẽ tính theo giá "
            "tiêu chuẩn, số ngày thuê còn lại chưa sử dụng sẽ được hoàn trả 70% giá trị ngày thuê sau khi hoàn tất thủ "
            "tục bàn giao và kiểm tra xe."
        ),
        "display_order": 17,
        "is_active": True,
        "view_count": 128,
    },
    {
        "category": "cancellation",
        "category_name": "Chính sách hủy đơn",
        "question": "Các trường hợp bất khả kháng (bão lũ, thiên tai, lệnh cấm đường) có được miễn phí hủy đơn?",
        "answer": (
            "Trong các trường hợp thiên tai, bão lũ có công điện cảnh báo của cơ quan chức năng hoặc khu vực cấm đường "
            "do thời tiết, RideHub hỗ trợ hủy đơn hoàn tiền 100% hoặc bảo lưu toàn bộ giá trị đặt cọc trong thời hạn "
            "06 tháng theo nguyện vọng của quý khách."
        ),
        "display_order": 18,
        "is_active": True,
        "view_count": 195,
    },

    # -------------------------------------------------------------------------
    # 4. QUY TRÌNH & THỜI GIAN HOÀN TIỀN (refund) - 6 câu
    # -------------------------------------------------------------------------
    {
        "category": "refund",
        "category_name": "Quy trình & Thời gian hoàn tiền",
        "question": "Sau khi hoàn tất trả xe, tiền đặt cọc sẽ được hoàn lại bằng hình thức nào?",
        "answer": (
            "Tiền cọc sẽ được hoàn trả tự động bằng phương thức chuyển khoản ngân hàng qua cổng thanh toán "
            "VietQR / PayOS trực tiếp về số tài khoản ngân hàng hoặc ví điện tử mà quý khách đã sử dụng để đặt cọc ban đầu."
        ),
        "display_order": 19,
        "is_active": True,
        "view_count": 510,
    },
    {
        "category": "refund",
        "category_name": "Quy trình & Thời gian hoàn tiền",
        "question": "Thời gian nhận lại tiền cọc sau khi ký biên bản trả xe là bao lâu?",
        "answer": (
            "Ngay sau khi nhân viên cửa hàng và quý khách hoàn tất kiểm tra tình trạng xe, ký Biên bản Check-in điện tử: "
            "Số tiền cọc sau khi quyết toán các phụ phí (xăng/sạc, quá giờ, vệ sinh...) sẽ được hệ thống kích hoạt lệnh "
            "hoàn trả tự động trong vòng 15 đến 30 phút và tiền về tài khoản trong ngày."
        ),
        "display_order": 20,
        "is_active": True,
        "view_count": 620,
    },
    {
        "category": "refund",
        "category_name": "Quy trình & Thời gian hoàn tiền",
        "question": "Khoản tiền giữ cọc phạt nguội giao thông là gì và khi nào được hoàn trả?",
        "answer": (
            "Để bảo đảm tuân thủ xử phạt nguội theo camera giao thông (dữ liệu thường cập nhật sau 7 - 15 ngày), cửa hàng "
            "có thể giữ lại từ 1.000.000đ - 2.000.000đ cọc phạt nguội. Sau đúng 15 ngày kể từ ngày trả xe, nếu không có vi "
            "phạm từ CSGT, hệ thống tự động hoàn trả 100% số tiền này về tài khoản ngân hàng của quý khách."
        ),
        "display_order": 21,
        "is_active": True,
        "view_count": 435,
    },
    {
        "category": "refund",
        "category_name": "Quy trình & Thời gian hoàn tiền",
        "question": "Tôi có thể tra cứu và theo dõi tiến độ hoàn tiền ở đâu trên RideHub?",
        "answer": (
            "Quý khách truy cập mục 'Lịch sử giao dịch' hoặc xem trực tiếp tại trang 'Chi tiết đơn hàng'. Tiến độ hoàn tiền "
            "được hiển thị minh bạch theo thời gian thực: 'Đã tạo lệnh hoàn' -> 'Đang chuyển tiền qua PayOS' -> 'Hoàn tiền "
            "thành công' kèm mã tham chiếu ngân hàng (FT reference)."
        ),
        "display_order": 22,
        "is_active": True,
        "view_count": 280,
    },
    {
        "category": "refund",
        "category_name": "Quy trình & Thời gian hoàn tiền",
        "question": "Nếu quá thời gian cam kết mà tài khoản chưa nhận được tiền hoàn cọc thì làm thế nào?",
        "answer": (
            "Quý khách có thể bấm nút 'Khiếu nại cọc' ngay trên khung Chatbot hoặc gọi Hotline CSKH 1900-7433. Hệ thống sẽ "
            "tự động chuyển tiếp cuộc gọi / tin nhắn đến Trưởng ca vận hành (Agent Escalation) để kiểm tra tra soát với "
            "ngân hàng và ưu tiên chuyển khoản thủ công cho quý khách trong 10 phút."
        ),
        "display_order": 23,
        "is_active": True,
        "view_count": 315,
    },
    {
        "category": "refund",
        "category_name": "Quy trình & Thời gian hoàn tiền",
        "question": "Trường hợp xe bị trầy xước phát sinh lúc trả xe, chi phí bồi thường được trừ vào cọc ra sao?",
        "answer": (
            "Khi trả xe, hai bên cùng đối chiếu vết xước phát sinh mới so với ảnh chụp hiện trạng lúc giao trên Biên bản "
            "điện tử. Chi phí bồi thường được tính minh bạch theo Bảng đơn giá niêm yết linh kiện chính hãng của RideHub. "
            "Toàn bộ số tiền cọc còn lại sau khi khấu trừ chi phí sẽ được chuyển khoản hoàn trả ngay lập tức."
        ),
        "display_order": 24,
        "is_active": True,
        "view_count": 265,
    },
]
