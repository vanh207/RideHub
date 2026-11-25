# TF1A2FA - Đối soát giao dịch và báo cáo toàn nền tảng

## Hiện trạng đã rà soát

- RideHub đã có tạo link PayOS, webhook có xác thực chữ ký/idempotency, truy vấn trạng thái từng PayOS order, hàng chờ giao dịch bất thường và xử lý refund.
- `payment_booking_reconciliation` cập nhật trạng thái booking sau khi thanh toán thành công; đây không phải đối soát sao kê gateway với giao dịch local.
- PayOS integration có tra cứu một order nhưng không lấy danh sách sao kê tài khoản. Vì vậy API đối soát nhận các dòng sao kê đã xuất từ gateway/vận hành cung cấp, không giả lập việc truy cập được toàn bộ sao kê PayOS.
- Trước thay đổi, chưa có API báo cáo toàn nền tảng. Dashboard đăng nhập là placeholder; các thống kê hiện hữu chỉ phục vụ audit hoặc lịch xe.

## API mới

### `POST /api/payments/operations/reconciliation`

Chỉ `admin` hoặc `operator`; yêu cầu Bearer token. Đây là API **read-only**, không cập nhật payment, refund, booking, reservation hay lịch xe.

Query:

| Tham số | Bắt buộc | Ý nghĩa |
|---|---:|---|
| `from_date` | Có | Ngày bắt đầu, gồm cả ngày |
| `to_date` | Có | Ngày kết thúc, gồm cả ngày |
| `status` | Không | `MATCHED`, `MISMATCHED`, `MISSING_GATEWAY`, `MISSING_LOCAL` |
| `q` | Không | Tìm transaction code, provider transaction ID hoặc booking ID local |

Khoảng ngày tối đa 367 ngày. Body nhận tối đa 2.000 dòng; mỗi dòng cần `transaction_code` hoặc `provider_txn_id`, `amount` VND, `status` và `occurred_at`. `PAID` được chuẩn hóa thành `SUCCESS`; `PROCESSING` thành `PENDING`.

Request mẫu:

```json
{
  "provider": "PAYOS",
  "gateway_transactions": [
    {
      "transaction_code": "PAYOS_26112512345601",
      "provider_txn_id": "GATEWAY-REF-001",
      "amount": "500000.00",
      "status": "PAID",
      "occurred_at": "2026-11-25T12:34:56"
    }
  ]
}
```

Với PayOS, `transaction_code` nội bộ được tạo theo dạng `PAYOS_<orderCode>`. Không gửi chữ ký, API key, checksum key hoặc toàn bộ payload webhook vào API này.

Response mẫu rút gọn:

```json
{
  "provider": "PAYOS",
  "from_date": "2026-11-25",
  "to_date": "2026-11-25",
  "summary": {
    "total_count": 4,
    "matched_count": 1,
    "mismatched_count": 1,
    "missing_gateway_count": 1,
    "missing_local_count": 1,
    "local_amount_total": "1500000.00",
    "gateway_amount_total": "1550000.00",
    "difference_amount_total": "50000.00",
    "anomaly_count": 1,
    "pending_refund_count": 1,
    "pending_refund_amount": "200000.00",
    "completed_refund_amount": "0.00"
  },
  "transactions": [
    {
      "reconciliation_status": "MISMATCHED",
      "transaction_code": "PAYOS_26112512345601",
      "gateway_transaction_code": "PAYOS_26112512345601",
      "booking_id": 101,
      "local_amount": "500000.00",
      "gateway_amount": "550000.00",
      "difference_amount": "50000.00",
      "local_status": "SUCCESS",
      "gateway_status": "PAID",
      "refund_status": null,
      "anomaly_types": []
    }
  ]
}
```

`difference_amount` là gateway trừ local. Các refund local liên quan được đính kèm theo giao dịch (trạng thái, tổng tiền pending/đã hoàn); model hiện chưa lưu mã giao dịch hoàn riêng từ provider nên API không tuyên bố đối chiếu độc lập từng refund với gateway.

### `GET /api/reports/platform`

Chỉ `admin` hoặc `operator`; yêu cầu Bearer token.

Query `from_date` và `to_date` là tùy chọn. Mặc định là 30 ngày gần nhất tính đến hôm nay; nếu chỉ truyền một ngày thì ngày còn lại được suy ra. Khoảng báo cáo tối đa 367 ngày.

Response gồm:

- Payment count và count theo trạng thái; tiền đã thu (SUCCESS/REFUNDED/LATE_PAYMENT), refund đã hoàn và tiền thu ròng.
- Refund count/status, số tiền đang chờ và đã hoàn.
- Booking count theo trạng thái; số lượng/tổng phụ phí CHECK_IN.
- Tổng số user/vehicle, user mới theo kỳ, user active và phân bố trạng thái xe/người dùng.
- Số AMOUNT_MISMATCH, LATE_PAYMENT, pending refund, webhook signature invalid và webhook failure.

Các khoản tiền trả `Decimal` hai chữ số thập phân, đơn vị `VND`. Tập kết quả rỗng trả count `0`, tổng tiền `"0.00"` và map trạng thái rỗng thay vì `null`.

## Kiểm thử

Test mới: `backend/tests/test_platform_reconciliation.py`. Bao gồm matched/mismatched/missing hai phía, lọc ngày/trạng thái/tìm kiếm, refund sidecar, body sai/trùng, dữ liệu rỗng, báo cáo tiền/trạng thái/fee/user/vehicle/anomaly, và quyền `401`/`403`. Đối soát lặp lại cho kết quả như nhau và không thay đổi số liệu báo cáo.

Kết quả chạy thực tế:

- Bộ test thanh toán/đối soát/báo cáo liên quan: **73 passed**.
- Toàn bộ Backend: **196 passed, 23 skipped, 1 failed**. Lỗi còn lại là `tests/test_chatbot_ai.py::test_02_knowledge_base_rag_context_building`, test mong context chứa tiêu đề `"Chính sách tiền cọc & Hoàn tiền"` nhưng kết quả chỉ có nội dung câu trả lời. Lỗi này không đi qua các API/service được thay đổi ở task này.
- Test dùng SQLite in-memory và dữ liệu mô phỏng; chưa kết nối MySQL hoặc gọi PayOS thật.

Chạy kiểm thử liên quan trên Windows:

```powershell
cd .\backend
.\.venv\Scripts\python.exe -m pytest tests\test_platform_reconciliation.py tests\test_payment_operations.py tests\test_payment_flow.py tests\test_payos.py tests\test_booking_settlement.py -q
```

Đối soát đang dùng SQLite in-memory trong test/API TestClient; chưa kết nối MySQL hoặc gọi PayOS thật. Để dùng trong môi trường thật, yêu cầu người vận hành xuất sao kê phù hợp, chuẩn hóa thành body trên và xác minh số liệu với chứng từ gateway trước khi xử lý bất thường/refund.
