# TÀI LIỆU THIẾT KẾ & ĐẶC TẢ NGHIỆP VỤ RIDEHUB
## BIÊN BẢN GIAO/NHẬN XE · HỆ THỐNG FAQ · KỊCH BẢN CHATBOT AI
*Tuân thủ bộ tiêu chuẩn thiết kế UI/UX Pro Max (`ui-ux-pro-max`)*

---

## I. TỔNG QUAN
Hệ sinh thái **RideHub** là nền tảng trực tuyến kết nối khách hàng với các chủ phương tiện và đơn vị cho thuê xe tự lái (ô tô và xe máy). Ba cấu phần then chốt nhằm số hóa và tối ưu trải nghiệm khách hàng bao gồm:
1. **Biên bản Giao / Nhận xe điện tử (Digital Handover Protocol):** Chứng từ số hóa lưu vết trạng thái xe, ODO, vạch nhiên liệu, tổn hại thân vỏ và chữ ký số để xóa bỏ tranh chấp tài sản.
2. **Hệ thống Câu hỏi thường gặp (FAQ Hub):** Bộ giải đáp 10 tình huống thực tế xuyên suốt 5 chặng hành trình khách hàng.
3. **Kịch bản Trợ lý Chatbot AI (RideHub Assistant):** Luồng hội thoại tự nhiên, gợi ý xe, xử lý tình huống khẩn cấp và quy tắc leo thang sang nhân viên người thật khi có khiếu nại.

---

## II. BẢNG BIÊN BẢN GIAO/NHẬN XE ĐIỆN TỬ
Đã hiện thực hóa tại: [`frontend/pages/handover.html`](file:///c:/Users/Admin/OneDrive/Desktop/RideHub/frontend/pages/handover.html)

### 1. Phân loại luồng biên bản
- **Check-out (Giao xe xuất phát):** 
  - Ghi nhận ODO ban đầu, mức nhiên liệu xuất bãi (Full), 06 điểm kiểm tra an toàn, chụp ảnh 4 mặt xe và đánh dấu các vết xước có sẵn.
  - Khách thuê và Nhân viên cùng ký số xác nhận.
- **Check-in (Nhận xe hoàn trả):**
  - Ghi nhận ODO hoàn trả, tự động tính chênh lệch quãng đường (phụ phí nếu vượt 350km/ngày: 3.000đ/km).
  - Đối chiếu vạch xăng/pin và các vết xước mới phát sinh trên sơ đồ xe.
  - Tự động tính toán bảng quyết toán cọc: Hoàn trả ngay cọc tài sản (80%) và giữ cọc bảo đảm phạt nguội giao thông (20%, hoàn sau 15-20 ngày).

### 2. Sơ đồ tương tác ngoại thất (Interactive Damage Hotspots)
- Tích hợp sơ đồ vector trực quan 4 mặt xe: Đầu xe, Đuôi xe, Sườn trái, Sườn phải, Kính chắn gió, Nóc xe.
- Mỗi điểm kiểm tra (Hotspot) có thể nhấp chọn để chuyển đổi trạng thái: *Bình thường (Trắng/Xanh)* ↔ *Có vết trầy xước/móp méo (Đỏ)*.
- Tự động cập nhật bảng tóm tắt chi tiết các vị trí lỗi và tính chi phí bồi thường (300.000đ/vết xước dặm sơn mới).

### 3. Chữ ký số Canvas HTML5
- Sử dụng thẻ `<canvas>` độ nét cao (2x DPI scale) hỗ trợ thao tác mượt mà bằng chuột trên Desktop và ngón tay/bút stylus trên Smartphone & Tablet.
- Hỗ trợ nút ký lại nhanh và trích xuất chữ ký dạng Base64 PNG.

---

## III. HỆ THỐNG FAQ 5 CHẶNG HÀNH TRÌNH
Đã hiện thực hóa tại: [`frontend/pages/faq.html`](file:///c:/Users/Admin/OneDrive/Desktop/RideHub/frontend/pages/faq.html)

- **Chặng 1: Hồ sơ, Bằng lái & eKYC:** Hướng dẫn CCCD gắn chip + GPLX A1/A2/B1/B2, thời gian duyệt eKYC 3-5 phút, chính sách bằng lái quốc tế IDP cho du khách.
- **Chặng 2: Đặt cọc & Thanh toán:** Minh bạch tiền cọc giữ chỗ (30-50%) và cọc tài sản (1-3 triệu xe máy, 5-15 triệu ô tô); cơ chế hoàn tiền tức thì sau khi trả xe và chính sách giữ cọc phạt nguội 15-20 ngày.
- **Chặng 3: Giao nhận xe & Biên bản điện tử:** Giao xe tận nơi trong bán kính 5km miễn phí; quy trình chụp ảnh 6 góc bảo vệ quyền lợi người thuê.
- **Chặng 4: Vận hành & Cứu hộ khẩn cấp 24/7:** Định mức km (350-400km/ngày); quy trình dừng khẩn cấp, bật đèn hazard và gọi cứu hộ 1900-7433 miễn phí khi hỏng hóc kỹ thuật.
- **Chặng 5: Hủy chuyến & Phụ phí vi phạm:** Hủy trước 48h hoàn 100% cọc; phí vệ sinh xe bẩn và phụ phí hút thuốc (500.000đ).

---

## IV. KỊCH BẢN HỘI THOẠI & TIN NHẮN CHATBOT AI
Đã hiện thực hóa tại: [`frontend/pages/chatbot.html`](file:///c:/Users/Admin/OneDrive/Desktop/RideHub/frontend/pages/chatbot.html)

### 1. Nhân vật & Giọng điệu (AI Persona)
- Tên trợ lý: **RideHub Assistant**.
- Giọng điệu: Nhiệt tình, thân thiện, lịch thiệp, câu văn ngắn gọn, cung cấp các nút bấm tác vụ nhanh (Quick Reply Chips).

### 2. Bộ 5 kịch bản đàm thoại chuẩn
1. **Tìm xe & Báo giá tự động:** Trích xuất yêu cầu khách hàng (số chỗ, địa điểm, ngân sách), phản hồi kèm Thẻ xe (Car Cards) trực quan có giá, thông số và nút "Đặt ngay".
2. **Tư vấn eKYC:** Hướng dẫn 3 bước chụp ảnh giấy tờ không lóa đèn, không mất góc để AI duyệt trong 3 phút.
3. **Tra cứu đơn thuê & Ký biên bản:** Tra cứu trạng thái đơn `#BK-88421`, thông tin nhân viên giao xe và link mở biên bản điện tử trực tiếp.
4. **Hỗ trợ khẩn cấp trên đèo dốc:** Nhận diện sự cố xịt lốp/hỏng phanh/chết máy -> kích hoạt cảnh báo đỏ, hướng dẫn dừng an toàn, nút gửi tọa độ GPS và hotline kết nối trực tiếp đội cơ động.
5. **Khiếu nại cọc & Leo thang nhân viên (Human Escalation):** Nhận diện từ khóa bức xúc ("lừa đảo", "chưa hoàn cọc", "gặp nhân viên") -> Xin lỗi chân thành, giải thích nguyên nhân và chuyển giao quyền điều khiển phiên chat cho Chuyên viên Chăm sóc Khách hàng (Mai Linh) kèm tóm tắt hồ sơ.

---

## V. CÁCH KIỂM TRA & TRẢI NGHIỆM TRÊN TRÌNH DUYỆT
1. Mở file [`frontend/index.html`](file:///c:/Users/Admin/OneDrive/Desktop/RideHub/frontend/index.html) bằng bất kỳ trình duyệt nào (hoặc Live Server).
2. Thanh menu trên Header cung cấp liên kết trực tiếp:
   - **Trang chủ** (`index.html`)
   - **Biên bản Giao/Nhận xe** (`pages/handover.html`)
   - **FAQ Trợ giúp** (`pages/faq.html`)
   - **Trợ lý AI Chatbot** (`pages/chatbot.html`)

