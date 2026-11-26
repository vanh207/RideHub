# TF196F6 — Kết quả kiểm tra giao diện mobile

- Ngày kiểm: 2026-11-26.
- Phạm vi: tìm kiếm xe, chi tiết xe, đặt/giữ chỗ, chuyến của khách, thanh toán QR và kết quả thanh toán.
- Đối chiếu: bản gốc `origin/develop` tại `967e360` so với bản đã sửa trên nhánh `feature/tf196f6-sua-loi-giao-dien-mobile`.
- Không sửa backend, không đổi nghiệp vụ, endpoint, định dạng dữ liệu hay module ngoài phạm vi.

## Cách kiểm tra

- Script: `scripts/check_mobile.mjs` — Chrome headless qua CDP, không dùng thư viện ngoài.
- Lệnh chạy bản hiện tại:

```bash
VEHICLE_ID=1990414 BOOKING_ID=19540401 node scripts/check_mobile.mjs
```

- Lệnh chạy bản gốc:

```bash
MOBILE_BASE_URL=http://127.0.0.1:5502 \
RESULT_PATH=docs/mobile/TF196F6-headless-results-baseline.json \
SCREENSHOT_DIR=docs/mobile/screenshots-baseline \
VEHICLE_ID=1990414 BOOKING_ID=19540401 node scripts/check_mobile.mjs
```

- Kích thước: `360x740`, `390x844`, `414x896`, `768x1024`, `1280x800`, `844x390` (landscape).
- Mỗi lần chạy sinh 36 ảnh (6 kích thước x 6 trang) trước và sau; kết quả được tóm tắt trong báo cáo này, ảnh/JSON chi tiết sinh lại bằng script để tránh đẩy artifact lớn lên repo.
- Script đo `document.documentElement.scrollWidth`, phần tử vượt viewport, phần tử tương tác nhỏ hơn `44x44px`, phần tử có `scrollWidth > clientWidth`, và lỗi console/network.
- Script vô hiệu hóa animation/reveal trong lần đo để không đọc nhầm trạng thái đang mờ dần.

## Kết quả tổng hợp

| Chỉ số | Trước | Sau | Ghi chú |
|---|---:|---:|---|
| Tràn ngang tài liệu | 0 | 0 | `html/body` đã có `overflow-x: hidden`, nên chỉ số này không phản ánh đúng lỗi bố cục; dùng thêm phần tử vượt viewport. |
| Phần tử vượt viewport | 4 | 4 | Chỉ là blob nền/aurora có `pointer-events: none`, không chặn thao tác. |
| Vùng chạm `<44x44px` (36 lần đo) | 725 | 310 | Các kích thước mobile `360/390/414` còn **0**; phần còn lại nằm ở `768/1280/844`, ngoài yêu cầu mobile. |
| Vùng chạm `<44x44px` ở `360x740` | 120 | 0 | Hết lỗi ở toàn bộ 6 trang mobile. |
| Lỗi JS (`TypeError/ReferenceError`) | 0 | 0 | Lỗi biến `selectedTime` cũ nằm trong luồng click, được sửa và kiểm tra tĩnh. |
| Lỗi console/network | 157 | 156 | Lỗi có sẵn: probe `/.env`, `/frontend/.env`, chat lịch sử `404`; không phát sinh lỗi mới. |

### Chi tiết theo trang ở `360x740`

| Trang | Vùng chạm nhỏ trước | Vùng chạm nhỏ sau | Cắt/chặn text trước | Cắt/chặn text sau |
|---|---:|---:|---:|---:|
| `vehicles.html` | 44 | 0 | 12 | 12 |
| `vehicle-detail.html` | 21 | 0 | 1 | 1 |
| `booking.html` | 22 | 0 | 1 | 3 |
| `trips.html` | 33 | 0 | 4 | 4 |
| `payment-qr.html` | 0 | 0 | 1 | 1 |
| `payment-result.html` | 0 | 0 | 0 | 0 |

`Cắt/chặn text` là chỉ số thô `scrollWidth > clientWidth`: phần tăng ở `booking.html` là 2 phần tử `step-circle/step-node` Border-box lệch 1px, các còn lại là khối có `overflow: hidden` chứa aurora/blob trang trí. Không có chỉnh sửa nào làm mất nội dung văn bản.

## Lỗi đã sửa

| Mức | Lỗi | Vị trí sửa | Trạng thái |
|---|---|---|---|
| Cao | `frontend/js/pages/vehicle-detail.js` dùng `selectedTime` và `toDateTime()` không tồn tại; bấm “Tiếp tục đặt xe” gây `ReferenceError`. Thêm helper `toDateTime()` và lấy lịch từ `picker.getState()`. | `frontend/js/pages/vehicle-detail.js:137`, `:167`, `:190` | Đã sửa |
| Cao | Chưa chọn ngày trả vẫn có thể đi tiếp luồng đặt xe. Thêm kiểm tra `endDay` với thông báo tiếng Việt. | `frontend/js/pages/vehicle-detail.js:167` | Đã sửa |
| Trung bình | Nhiều nút/link/header/footer/bộ lọc nhỏ hơn `44x44px` ở mobile. Ghi đè trong CSS riêng từng trang, không sửa file dùng chung. | `frontend/css/pages/search.css:314`, `frontend/css/pages/vehicle-detail.css:428`, `frontend/css/pages/booking.css:1`, `frontend/css/pages/trips.css:1` | Đã sửa |
| Trung bình | Nút inline trong HTML có `min-height: 26/30/34/36/38px` vượt CSS. Đổi trực tiếp sang `44px`. | `frontend/vehicles.html:158`, `:161`, `:172`, `:173`, `:359`, `:1199`, `:1345`; `frontend/booking.html:171`, `:295`; `frontend/trips.html:71`–`:73`, `:172`, `:249`, `:327`, `:376`, `:467`, `:492`, `:871`, `:872`, `:877`, `:1104` | Đã sửa |
| Trung bình | Trang tìm kiếm: nút “Ẩn”, thanh trượt giá, tim yêu thích có vùng chạm nhỏ. Đổi selector cho đúng `#dismissGuestBanner`, tăng chiều cao range và tim. | `frontend/css/pages/search.css:345`, `:353`, `:357` | Đã sửa |
| Trung bình | Trang chi tiết: breadcrumb, liên hệ, footer, nút modal có vùng chạm nhỏ; giá đội xe `white-space: nowrap` dễ cưỡng dòng. | `frontend/css/pages/vehicle-detail.css:445`, `:456`, `:467` | Đã sửa |
| Trung bình | Trang đặt xe: `step-node` hẹp, `<5 phút`, nút đóng modal và footer nhỏ. Thêm CSS riêng `booking.css` và nạp sau `animations.css`. | `frontend/booking.html:11`, `frontend/css/pages/booking.css:1` | Đã sửa |
| Trung bình | Trang chuyến đi: nút demo, nút thẻ chuyến, nút modal, footer nhỏ; grid `minmax(320px,1fr)` có thể tràn ở viewport hẹp hơn `360px`. Thêm CSS riêng `trips.css`, ép 1 cột ở `<=360px`. | `frontend/trips.html:13`, `frontend/css/pages/trips.css:1`, `:53` | Đã sửa |
| Thấp | Thanh toán: thiếu safe-area trên thiết bị tai thỏ; toast cố định có thể bị che. Thêm `viewport-fit=cover` và `env(safe-area-inset-*)`. | `frontend/payment-qr.html:6`, `:59`, `:797`, `:818`, `:850`; `frontend/payment-result.html:5`, `:13` | Đã sửa |
| Thấp | Các trang chính thiếu `viewport-fit=cover`. | `frontend/vehicles.html:5`, `frontend/vehicle-detail.html:5`, `frontend/booking.html:5`, `frontend/trips.html:5` | Đã sửa |

## File dùng chung

Không chỉnh sửa `frontend/css/styles.css`, `frontend/css/variables.css`, `frontend/css/animations.css`, `frontend/css/components/chat-widget.css`, `frontend/js/layout.js`, `frontend/js/auth-rbac.js`, `frontend/js/utils.js`.

Một số rule mobile dùng `!important` trong CSS riêng của trang để thắng `inline style` do `auth-rbac.js` và HTML sinh ra; phạm vi bị giới hạn bởi file CSS chỉ được nạp ở trang tương ứng.

## Lỗi chưa kiểm / không thuộc phạm vi

- Chưa kiểm trên máy thật; phép đo hiện tại là Chrome headless. Checklist tự kiểm: bấm thử từng nút ở `390x844`, mở modal lịch/chọn ngày, bấm “Tiếp tục đặt xe”, mở drawer menu, xoay ngang thiết bị.
- Lỗi console có sẵn, không sửa do nằm ngoài module: `/.env` và `/frontend/.env` trả `404`; `/api/chat/conversations/{id}/messages` trả `404` do session chat mẫu cũ. Không có exception JavaScript mới sau khi sửa.
- Không kiểm/chỉnh module auth, admin, store, handover, profile, chatbot.

## Minh chứng

- Bảng số liệu trước/sau nằm ở phần “Kết quả tổng hợp”.
- Script đo: `scripts/check_mobile.mjs`.
- Chạy script với `RESULT_PATH`/`SCREENSHOT_DIR` tùy chọn sẽ sinh lại `TF196F6-headless-results.json` và các ảnh `docs/mobile/screenshots/` để đối chiếu.
