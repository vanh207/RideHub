-- =============================================================================
-- RIDEHUB DATABASE SEED SCRIPT: FAQ CHATBOT DATA (TF1B346)
-- Sprint: Sprint 2 (17/11 - 23/11/2026)
-- Mục tiêu: Tạo bảng faqs và nạp ít nhất 20 câu hỏi thường gặp (24 câu hỏi thực tế)
-- 4 Nhóm chính: Giá thuê (pricing), Điều kiện thuê (rental_conditions),
--              Hủy đơn (cancellation), Hoàn tiền (refund)
-- =============================================================================

CREATE TABLE IF NOT EXISTS faqs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    category VARCHAR(50) NOT NULL,
    category_name VARCHAR(100) NOT NULL,
    question VARCHAR(500) NOT NULL,
    answer TEXT NOT NULL,
    display_order INT DEFAULT 0 NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    view_count INT DEFAULT 0 NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX ix_faqs_category (category),
    INDEX ix_faqs_is_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Xóa dữ liệu cũ nếu muốn làm mới (tuỳ chọn)
-- DELETE FROM faqs WHERE category IN ('pricing', 'rental_conditions', 'cancellation', 'refund');

INSERT INTO faqs (category, category_name, question, answer, display_order, is_active, view_count) VALUES
-- =============================================================================
-- NHÓM 1: GIÁ THUÊ & PHỤ PHÍ (pricing) - 6 câu
-- =============================================================================
(
    'pricing',
    'Giá thuê & Phụ phí',
    'Giá thuê xe trên RideHub đã bao gồm thuế VAT và bảo hiểm chưa?',
    'Dạ giá niêm yết trên ứng dụng và website RideHub đã bao gồm gói Bảo hiểm vật chất xe cơ bản và thuế VAT 10%. Quý khách có thể tùy chọn nâng cấp gói Bảo hiểm toàn diện (giảm mức khấu trừ tai nạn về 0đ) khi tiến hành đặt xe trên hệ thống.',
    1,
    TRUE,
    145
),
(
    'pricing',
    'Giá thuê & Phụ phí',
    'Cách tính thời gian thuê 1 ngày trên RideHub như thế nào?',
    'Dạ một ngày thuê được tính trọn vẹn 24 giờ kể từ thời điểm quý khách nhận bàn giao xe thực tế. Ví dụ: Nếu quý khách nhận xe lúc 09:00 sáng thứ Bảy, thời điểm trả xe đúng hạn sẽ là 09:00 sáng Chủ Nhật mà không bị tính thêm bất kỳ phụ phí nào.',
    2,
    TRUE,
    192
),
(
    'pricing',
    'Giá thuê & Phụ phí',
    'Phụ phí quá giờ (trả xe trễ hạn) được tính như thế nào?',
    'Chính sách trả trễ của RideHub được tính rất linh hoạt: Trả trễ dưới 30 phút: Miễn phí hỗ trợ. Trả trễ từ 30 phút đến dưới 5 giờ: Tính 50.000đ/giờ đối với xe máy điện và 100.000đ/giờ đối với ô tô tự lái. Trả trễ từ 5 giờ trở lên: Hệ thống sẽ tự động tính thành 1 ngày thuê tiêu chuẩn tiếp theo.',
    3,
    TRUE,
    210
),
(
    'pricing',
    'Giá thuê & Phụ phí',
    'Hạn mức số km di chuyển mỗi ngày là bao nhiêu và phí vượt km tính ra sao?',
    'Mỗi ngày thuê tiêu chuẩn trên RideHub có định mức di chuyển là 200 km/ngày và được cộng dồn theo tổng số ngày thuê của hợp đồng (ví dụ: thuê 3 ngày hạn mức tổng là 600 km). Nếu vượt quá định mức, phụ phí vượt km là 3.500đ/km đối với ô tô và 1.000đ/km đối với xe máy.',
    4,
    TRUE,
    188
),
(
    'pricing',
    'Giá thuê & Phụ phí',
    'Chi phí giao xe tận nơi (Sân bay, Khách sạn, Nhà riêng) được tính thế nào?',
    'RideHub hỗ trợ giao xe tận nơi cực kỳ tiện lợi: Miễn phí giao nhận trong bán kính 5 km từ cửa hàng. Từ km thứ 6 trở đi: tính 10.000đ/km đối với xe máy và 15.000đ/km đối với ô tô. Phí giao nhận tại Ga Sân bay áp dụng mức giá trọn gói ưu đãi chỉ từ 50.000đ - 100.000đ/lượt.',
    5,
    TRUE,
    130
),
(
    'pricing',
    'Giá thuê & Phụ phí',
    'Thuê xe điện VinFast trên RideHub có mất tiền sạc pin không?',
    'Khi nhận bàn giao xe điện, pin luôn được nạp sẵn từ 80% đến 100%. Quý khách có thể sạc pin miễn phí hoặc theo đơn giá ưu đãi tại toàn bộ hệ thống trạm sạc VinFast / V-GREEN trên toàn quốc. Khi hoàn trả xe, quý khách chỉ cần đảm bảo dung lượng pin còn lại trên 20%.',
    6,
    TRUE,
    275
),

-- =============================================================================
-- NHÓM 2: ĐIỀU KIỆN & THỦ TỤC THUÊ XE (rental_conditions) - 6 câu
-- =============================================================================
(
    'rental_conditions',
    'Điều kiện & Thủ tục thuê xe',
    'Tôi cần chuẩn bị những giấy tờ gì để thuê xe tự lái trên RideHub?',
    'Quý khách chỉ cần chuẩn bị: (1) CCCD gắn chip hoặc Hộ chiếu (Passport) còn hạn; (2) Giấy phép lái xe (GPLX) hợp lệ: Hạng B1/B2 trở lên đối với ô tô hoặc Hạng A1/A2 đối với xe máy; (3) Hoàn tất xác thực eKYC gương mặt online trên ứng dụng trong 3 phút là đủ điều kiện nhận xe.',
    7,
    TRUE,
    340
),
(
    'rental_conditions',
    'Điều kiện & Thủ tục thuê xe',
    'Độ tuổi tối thiểu và kinh nghiệm lái xe để thuê ô tô tự lái là bao nhiêu?',
    'Đối với xe máy điện, khách hàng chỉ cần từ đủ 18 tuổi trở lên. Đối với ô tô tự lái, người thuê xe cần từ đủ 20 tuổi trở lên và sở hữu GPLX còn hiệu lực với thời gian cấp tối thiểu từ 01 năm trở lên nhằm đảm bảo an toàn tối đa cho chuyến đi.',
    8,
    TRUE,
    165
),
(
    'rental_conditions',
    'Điều kiện & Thủ tục thuê xe',
    'Mức tiền đặt cọc (thế chấp) giữ xe là bao nhiêu và thanh toán qua đâu?',
    'Mức tiền đặt cọc giữ xe tiêu chuẩn: Xe máy: từ 1.000.000đ - 2.000.000đ (hoặc để lại xe máy cá nhân kèm cà vẹt gốc); Ô tô tự lái 4 - 7 chỗ phổ thông: 5.000.000đ/xe. Quý khách thanh toán cọc chuyển khoản nhanh 24/7 qua cổng VietQR / PayOS trực tiếp ngay trên app.',
    9,
    TRUE,
    420
),
(
    'rental_conditions',
    'Điều kiện & Thủ tục thuê xe',
    'Bằng lái xe nước ngoài hoặc Bằng lái quốc tế (IDP) có thuê được xe không?',
    'RideHub hoàn toàn chấp nhận Giấy phép lái xe quốc tế (IDP - International Driving Permit) theo Công ước Vienna 1968 đi kèm với Hộ chiếu và Bằng lái xe gốc quốc gia còn hạn. Hệ thống AI eKYC của RideHub hỗ trợ quét nhận diện và đối chiếu giấy tờ của hơn 150 quốc gia.',
    10,
    TRUE,
    155
),
(
    'rental_conditions',
    'Điều kiện & Thủ tục thuê xe',
    'Quy trình xác thực định danh online eKYC diễn ra như thế nào?',
    'Sau khi chọn xe, quý khách chụp ảnh rõ nét 2 mặt CCCD/GPLX và quay video nhận diện gương mặt trực tiếp (Face Liveness). Hệ thống AI tự động trích xuất thông tin, đối khớp khuôn mặt và tự động kích hoạt tài khoản trong vòng 3 - 5 phút mà không cần phải đến quầy làm thủ tục giấy tờ.',
    11,
    TRUE,
    298
),
(
    'rental_conditions',
    'Điều kiện & Thủ tục thuê xe',
    'Tôi có thể nhờ người khác lái thay hoặc thuê hộ xe cho bạn bè được không?',
    'Người đứng tên hợp đồng thuê phải là người lái chính và đã qua xác thực eKYC. Trường hợp có thêm người lái phụ, quý khách chỉ cần khai báo bổ sung GPLX của người lái phụ vào Biên bản giao nhận điện tử khi nhận xe để đảm bảo quyền lợi bảo hiểm khi lưu thông.',
    12,
    TRUE,
    112
),

-- =============================================================================
-- NHÓM 3: CHÍNH SÁCH HỦY ĐƠN (cancellation) - 6 câu
-- =============================================================================
(
    'cancellation',
    'Chính sách hủy đơn',
    'Tôi có thể hủy đơn đặt xe không và biểu phí phạt hủy được quy định ra sao?',
    'Quý khách có thể chủ động hủy đơn trực tiếp trên ứng dụng: Hủy trước 24 giờ so với giờ nhận xe: Miễn phí 100% (hoàn lại toàn bộ cọc). Hủy trong vòng 12 - 24 giờ trước giờ nhận: Phí phạt hủy là 30% tiền cọc. Hủy dưới 12 giờ trước giờ nhận: Phí phạt hủy là 50% tiền cọc để bù đắp chi phí chuẩn bị và giữ lịch xe của cửa hàng.',
    13,
    TRUE,
    380
),
(
    'cancellation',
    'Chính sách hủy đơn',
    'Nếu chuyến bay bị delay hoặc đổi giờ hạ cánh thì cửa hàng xử lý thế nào?',
    'Khi chuyến bay bị hoãn (delay) hoặc thay đổi giờ bay, quý khách chỉ cần gửi mã chuyến bay hoặc ảnh chụp thông báo hoãn cho CSKH / Chatbot. Cửa hàng sẽ tự động dời giờ bàn giao xe miễn phí tối đa 5 tiếng và bảo lưu xe nguyên vẹn cho quý khách.',
    14,
    TRUE,
    245
),
(
    'cancellation',
    'Chính sách hủy đơn',
    'Làm thế nào để thao tác hủy đơn đặt xe trên ứng dụng RideHub?',
    'Quý khách vào mục ''Đơn đặt xe của tôi'' trên ứng dụng -> Chọn đơn hàng cần hủy -> Nhấn nút ''Yêu cầu hủy đơn'' -> Chọn lý do hủy (Đổi kế hoạch, chuyến bay hoãn, sự cố cá nhân...) -> Xác nhận. Hệ thống sẽ tự động tính số tiền hoàn trả và gửi thông báo xác nhận ngay lập tức.',
    15,
    TRUE,
    175
),
(
    'cancellation',
    'Chính sách hủy đơn',
    'Nếu cửa hàng không có đúng dòng xe đã cam kết giao thì giải quyết thế nào?',
    'Nếu xảy ra trường hợp bất khả kháng cửa hàng không có đúng dòng xe đã đặt, RideHub cam kết: (1) Nâng hạng xe miễn phí lên dòng xe cao hơn nếu còn xe; hoặc (2) Hoàn trả 100% tiền đặt cọc ngay lập tức kèm voucher bồi hoàn giảm giá 20% cho chuyến đi tiếp theo của quý khách.',
    16,
    TRUE,
    140
),
(
    'cancellation',
    'Chính sách hủy đơn',
    'Tôi có được trả xe sớm hơn hợp đồng không và có được hoàn tiền các ngày còn lại?',
    'Quý khách hoàn toàn có thể trả xe sớm hơn hạn hợp đồng. Tiền thuê của các ngày đã sử dụng sẽ tính theo giá tiêu chuẩn, số ngày thuê còn lại chưa sử dụng sẽ được hoàn trả 70% giá trị ngày thuê sau khi hoàn tất thủ tục bàn giao và kiểm tra xe.',
    17,
    TRUE,
    128
),
(
    'cancellation',
    'Chính sách hủy đơn',
    'Các trường hợp bất khả kháng (bão lũ, thiên tai, lệnh cấm đường) có được miễn phí hủy đơn?',
    'Trong các trường hợp thiên tai, bão lũ có công điện cảnh báo của cơ quan chức năng hoặc khu vực cấm đường do thời tiết, RideHub hỗ trợ hủy đơn hoàn tiền 100% hoặc bảo lưu toàn bộ giá trị đặt cọc trong thời hạn 06 tháng theo nguyện vọng của quý khách.',
    18,
    TRUE,
    195
),

-- =============================================================================
-- NHÓM 4: QUY TRÌNH & THỜI GIAN HOÀN TIỀN (refund) - 6 câu
-- =============================================================================
(
    'refund',
    'Quy trình & Thời gian hoàn tiền',
    'Sau khi hoàn tất trả xe, tiền đặt cọc sẽ được hoàn lại bằng hình thức nào?',
    'Tiền cọc sẽ được hoàn trả tự động bằng phương thức chuyển khoản ngân hàng qua cổng thanh toán VietQR / PayOS trực tiếp về số tài khoản ngân hàng hoặc ví điện tử mà quý khách đã sử dụng để đặt cọc ban đầu.',
    19,
    TRUE,
    510
),
(
    'refund',
    'Quy trình & Thời gian hoàn tiền',
    'Thời gian nhận lại tiền cọc sau khi ký biên bản trả xe là bao lâu?',
    'Ngay sau khi nhân viên cửa hàng và quý khách hoàn tất kiểm tra tình trạng xe, ký Biên bản Check-in điện tử: Số tiền cọc sau khi quyết toán các phụ phí (xăng/sạc, quá giờ, vệ sinh...) sẽ được hệ thống kích hoạt lệnh hoàn trả tự động trong vòng 15 đến 30 phút và tiền về tài khoản trong ngày.',
    20,
    TRUE,
    620
),
(
    'refund',
    'Quy trình & Thời gian hoàn tiền',
    'Khoản tiền giữ cọc phạt nguội giao thông là gì và khi nào được hoàn trả?',
    'Để bảo đảm tuân thủ xử phạt nguội theo camera giao thông (dữ liệu thường cập nhật sau 7 - 15 ngày), cửa hàng có thể giữ lại từ 1.000.000đ - 2.000.000đ cọc phạt nguội. Sau đúng 15 ngày kể từ ngày trả xe, nếu không có vi phạm từ CSGT, hệ thống tự động hoàn trả 100% số tiền này về tài khoản ngân hàng của quý khách.',
    21,
    TRUE,
    435
),
(
    'refund',
    'Quy trình & Thời gian hoàn tiền',
    'Tôi có thể tra cứu và theo dõi tiến độ hoàn tiền ở đâu trên RideHub?',
    'Quý khách truy cập mục ''Lịch sử giao dịch'' hoặc xem trực tiếp tại trang ''Chi tiết đơn hàng''. Tiến độ hoàn tiền được hiển thị minh bạch theo thời gian thực: ''Đã tạo lệnh hoàn'' -> ''Đang chuyển tiền qua PayOS'' -> ''Hoàn tiền thành công'' kèm mã tham chiếu ngân hàng (FT reference).',
    22,
    TRUE,
    280
),
(
    'refund',
    'Quy trình & Thời gian hoàn tiền',
    'Nếu quá thời gian cam kết mà tài khoản chưa nhận được tiền hoàn cọc thì làm thế nào?',
    'Quý khách có thể bấm nút ''Khiếu nại cọc'' ngay trên khung Chatbot hoặc gọi Hotline CSKH 1900-7433. Hệ thống sẽ tự động chuyển tiếp cuộc gọi / tin nhắn đến Trưởng ca vận hành (Agent Escalation) để kiểm tra tra soát với ngân hàng và ưu tiên chuyển khoản thủ công cho quý khách trong 10 phút.',
    23,
    TRUE,
    315
),
(
    'refund',
    'Quy trình & Thời gian hoàn tiền',
    'Trường hợp xe bị trầy xước phát sinh lúc trả xe, chi phí bồi thường được trừ vào cọc ra sao?',
    'Khi trả xe, hai bên cùng đối chiếu vết xước phát sinh mới so với ảnh chụp hiện trạng lúc giao trên Biên bản điện tử. Chi phí bồi thường được tính minh bạch theo Bảng đơn giá niêm yết linh kiện chính hãng của RideHub. Toàn bộ số tiền cọc còn lại sau khi khấu trừ chi phí sẽ được chuyển khoản hoàn trả ngay lập tức.',
    24,
    TRUE,
    265
);
