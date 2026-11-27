CHƯA ĐƯỢC REVIEW PHÁP LÝ

# Chính sách xử lý dữ liệu eKYC — TASK_BONUS_FACECHECK

Tài liệu này là bản nháp kỹ thuật, chưa có hiệu lực cho người dùng cuối.

## 1. Phạm vi dữ liệu

RideHub xử lý các nhóm dữ liệu sau khi khách đồng ý xác thực danh tính:

- Thông tin khai báo trên CCCD: số giấy tờ, họ tên, ngày sinh, ngày cấp, ngày hết hạn, giới tính, địa chỉ.
- Ảnh mặt trước, mặt sau CCCD và ảnh khuôn mặt kèm thử thách của phiên.
- Kết quả kiểm tra máy: cờ QR, cờ chất lượng ảnh, điểm so khớp do provider trả về, kết quả liveness.

Máy không tự động phê duyệt hay từ chối hồ sơ. Admin là người đưa ra quyết định cuối cùng.

## 2. Căn cứ xử lý và đồng ý

- Phiên bản đồng ý hiện tại: `2026-11-v1`.
- Frontend phải hiển thị nội dung đồng ý trước khi tạo phiên eKYC.
- Backend lưu phiên bản đồng ý, thời điểm đồng ý và IP của client.
- Người dùng có thể yêu cầu xóa dữ liệu theo mục 5.

## 3. Lưu trữ và truy cập

- Ảnh được lưu trong thư mục riêng `KYC_PRIVATE_UPLOAD_DIR`, tên do hệ thống sinh, không trả URL công khai.
- API xem ảnh chỉ dành cho admin/operator có quyền, trả header `Cache-Control: no-store` và `X-Content-Type-Options: nosniff`.
- Mọi thao tác tạo phiên, nộp hồ sơ và xem ảnh đều được ghi audit log; log không chứa ảnh, base64 hay số CCCD đầy đủ.
- Số CCCD chỉ trả về dạng che một phần qua `GET /api/kyc/me`.

## 4. Thời gian lưu trữ

- Ảnh khuôn mặt: xóa sau `KYC_FACE_RETENTION_DAYS` = 30 ngày kể từ thời điểm phiên hết hạn.
- Ảnh CCCD và hồ sơ định danh: xóa sau `KYC_ID_RETENTION_DAYS` = 180 ngày kể từ ngày tạo.
- Job nền `kyc_cleanup_job` chạy mỗi `KYC_CLEANUP_JOB_INTERVAL_SECONDS` giây, xử lý theo batch `KYC_CLEANUP_BATCH_SIZE`.
- Mỗi lượt xóa ghi audit với mã `KYC_CLEANUP_FACE` hoặc `KYC_CLEANUP_DELETE`.
- Nếu xóa file thất bại, hệ thống ghi cảnh báo để vận hành xử lý thủ công.

Các mốc 30/180 ngày là giả định kỹ thuật, chưa được pháp chế phê duyệt.

## 5. Quyền của người dùng

Người dùng có thể yêu cầu truy cập, chỉnh sửa hoặc xóa dữ liệu eKYC qua:

- Email liên hệ: `KYC_PRIVACY_CONTACT_EMAIL` = `vietanh282007@gmail.com`.
- Người review nội bộ: `KYC_LEGAL_REVIEWER` = `Đỗ Việt Anh`.

Yêu cầu xóa phải được đối chiếu với hợp đồng thuê xe còn hiệu lực trước khi thực hiện.

## 6. Giới hạn kỹ thuật đã biết

- Đọc QR CCCD là tính năng thử nghiệm, chưa kiểm chứng với thẻ thật; mặc định có thể trả cờ `qr_unavailable`.
- Provider mặc định là `manual`, không trả điểm số; giao diện không hiển thị phần trăm chính xác.
- Bộ giới hạn số lần thử eKYC hiện lưu trong bộ nhớ tiến trình, chưa an toàn cho nhiều tiến trình.
- Chưa tích hợp nhà cung cấp nhận dạng khuôn mặt thương mại.
