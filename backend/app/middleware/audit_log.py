"""Middleware ghi nhận Nhật ký kiểm toán (Audit Log) cho RideHub.

Đáp ứng đầy đủ yêu cầu:
1. Ai (Who):
   - user_id, user_email, user_role (trích xuất từ JWT token qua Authorization Header / Cookie)
   - ip_address (hỗ trợ proxy / X-Forwarded-For)
   - user_agent
2. Làm gì (What):
   - Nhận diện các thao tác nhạy cảm:
     * Duyệt hồ sơ (Admin / Staff Reviews): Duyệt / từ chối Store, CCCD/CMND, Giấy phép lái xe
     * Đổi trạng thái (Status Changes): Trạng thái xe (AVAILABLE, RENTED, MAINTENANCE,...), đơn đặt xe, biên bản bàn giao
     * Hoàn tiền (Refunds): Hoàn tiền cọc, hoàn tiền thanh toán
   - Trích xuất: action, resource_type, resource_id, request_payload (đã che thông tin nhạy cảm), description
3. Lúc nào (When):
   - Thời điểm thực thi (created_at), thời gian xử lý (execution_time_ms)
4. Kết quả:
   - status_code, status (SUCCESS/FAILED), error_message (nếu có)

Thiết kế an toàn (Fail-Safe):
- Không làm gián đoạn request của người dùng nếu việc lưu audit log gặp lỗi.
- Đọc stream request body an toàn bằng cơ chế async receive cloning.
"""
from datetime import datetime
import json
import logging
import re
import time
from typing import Any, Dict, Optional, Tuple

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.security import decode_access_token
from app.db.session import SessionLocal
from app.models.audit_log import AuditLog
from app.models.user import User

logger = logging.getLogger("ridehub.audit")

# Các trường nhạy cảm cần ẩn khi ghi log request payload
SENSITIVE_FIELD_NAMES = {
    "password",
    "pass",
    "hashed_password",
    "secret",
    "secret_key",
    "token",
    "access_token",
    "refresh_token",
    "jwt",
    "api_key",
    "checksum_key",
    "cvv",
    "card_number",
    "bank_account",
    "customer_cccd",
    "customer_license",
    "customer_phone",
    "customer_signature",
    "staff_signature",
    "signature",
}


def _mask_sensitive_data(data: Any, max_str_len: int = 255) -> Any:
    """Đệ quy ẩn các thông tin nhạy cảm trong dữ liệu payload và cắt ngắn chuỗi quá dài."""
    if isinstance(data, dict):
        masked = {}
        for key, value in data.items():
            if str(key).lower() in SENSITIVE_FIELD_NAMES:
                masked[key] = "********"
            else:
                masked[key] = _mask_sensitive_data(value, max_str_len)
        return masked
    elif isinstance(data, list):
        return [_mask_sensitive_data(item, max_str_len) for item in data]
    elif isinstance(data, str) and len(data) > max_str_len:
        return f"{data[:max_str_len]}...[truncated, total_len={len(data)}]"
    return data


class AuditLogMiddleware(BaseHTTPMiddleware):
    """Middleware tự động bắt và lưu trữ vết kiểm toán cho các thao tác trọng yếu."""

    # Danh sách các Regex URL và phân loại nghiệp vụ tương ứng
    AUDIT_RULES = [
        # 1. THAO TÁC DUYỆT (ADMIN REVIEWS: Duyệt hồ sơ Store, CCCD, GPLX)
        {
            "pattern": re.compile(r"^/api/admin/reviews/(?P<resource_type>[^/]+)/(?P<resource_id>[^/]+)$"),
            "methods": {"PATCH", "POST", "PUT"},
            "category": "REVIEW",
            "default_action": "REVIEW_DECISION",
        },
        # Duyệt / Từ chối cửa hàng riêng biệt (nếu có)
        {
            "pattern": re.compile(r"^/api/stores/(?P<resource_id>[^/]+)/(?P<action_verb>approve|reject)$"),
            "methods": {"POST", "PATCH", "PUT"},
            "category": "REVIEW",
            "default_action": "STORE_REVIEW",
        },
        # 2. THAO TÁC ĐỔI TRẠNG THÁI (STATUS CHANGES)
        # Đổi trạng thái phương tiện
        {
            "pattern": re.compile(r"^/api/vehicles/(?P<resource_id>[^/]+)/status$"),
            "methods": {"POST", "PATCH", "PUT"},
            "category": "STATUS_CHANGE",
            "default_action": "VEHICLE_STATUS_CHANGE",
            "resource_type": "vehicle",
        },
        # Đổi trạng thái bảo trì phương tiện
        {
            "pattern": re.compile(r"^/api/vehicles/(?P<resource_id>[^/]+)/maintenance$"),
            "methods": {"POST", "PATCH", "PUT"},
            "category": "STATUS_CHANGE",
            "default_action": "VEHICLE_MAINTENANCE_CHANGE",
            "resource_type": "vehicle",
        },
        # Đổi trạng thái đơn đặt xe (Booking status)
        {
            "pattern": re.compile(r"^/api/bookings/(?P<resource_id>[^/]+)/status$"),
            "methods": {"POST", "PATCH", "PUT"},
            "category": "STATUS_CHANGE",
            "default_action": "BOOKING_STATUS_CHANGE",
            "resource_type": "booking",
        },
        {
            "pattern": re.compile(r"^/api/bookings/(?P<resource_id>[^/]+)/settle$"),
            "methods": {"POST"},
            "category": "STATUS_CHANGE",
            "default_action": "BOOKING_SETTLEMENT",
            "resource_type": "booking",
        },
        # Cửa hàng duyệt đơn / từ chối đơn đặt xe (TF1A595)
        {
            "pattern": re.compile(r"^/api/bookings/(?P<resource_id>[^/]+)/(?P<action_verb>confirm|reject)$"),
            "methods": {"POST"},
            "category": "REVIEW",
            "default_action": "STORE_ORDER_REVIEW",
            "resource_type": "booking",
        },
        {
            "pattern": re.compile(r"^/api/stores/(?P<store_id>[^/]+)/orders/(?P<resource_id>[^/]+)/(?P<action_verb>confirm|reject)$"),
            "methods": {"POST"},
            "category": "REVIEW",
            "default_action": "STORE_ORDER_REVIEW",
            "resource_type": "booking",
        },
        # Biên bản giao nhận xe — tạo, check-in, ký (Handover Protocol)
        {
            "pattern": re.compile(r"^/api/handover$"),
            "methods": {"POST"},
            "category": "STATUS_CHANGE",
            "default_action": "HANDOVER_CREATE",
            "resource_type": "handover",
        },
        {
            "pattern": re.compile(r"^/api/handover/checkin$"),
            "methods": {"POST"},
            "category": "STATUS_CHANGE",
            "default_action": "HANDOVER_CHECKIN",
            "resource_type": "handover",
        },
        {
            "pattern": re.compile(r"^/api/handover/(?P<resource_id>[^/]+)/checkin$"),
            "methods": {"PUT", "PATCH"},
            "category": "STATUS_CHANGE",
            "default_action": "HANDOVER_CHECKIN",
            "resource_type": "handover",
        },
        {
            "pattern": re.compile(r"^/api/handover/(?P<resource_id>[^/]+)/sign$"),
            "methods": {"POST"},
            "category": "STATUS_CHANGE",
            "default_action": "HANDOVER_SIGN",
            "resource_type": "handover",
        },
        {
            "pattern": re.compile(r"^/api/handover/(?P<resource_id>[^/]+)/confirm-photos$"),
            "methods": {"POST"},
            "category": "STATUS_CHANGE",
            "default_action": "HANDOVER_CONFIRM_PHOTOS",
            "resource_type": "handover",
        },
        {
            "pattern": re.compile(r"^/api/handover/(?P<resource_id>[^/]+)/media$"),
            "methods": {"POST"},
            "category": "STATUS_CHANGE",
            "default_action": "HANDOVER_MEDIA_UPLOAD",
            "resource_type": "handover",
        },
        # Quyết toán / Hoàn tất bàn giao xe (Handover settlement — legacy pattern)
        {
            "pattern": re.compile(r"^/api/handover/(?P<resource_id>[^/]+)/settlement$"),
            "methods": {"POST", "PATCH", "PUT"},
            "category": "STATUS_CHANGE",
            "default_action": "HANDOVER_SETTLEMENT",
            "resource_type": "handover",
        },
        # 3. THAO TÁC HOÀN TIỀN (REFUNDS)
        {
            "pattern": re.compile(r"^/api/payments/refund$"),
            "methods": {"POST"},
            "category": "REFUND",
            "default_action": "PAYMENT_REFUND",
            "resource_type": "payment",
        },
        {
            "pattern": re.compile(
                r"^/api/payments/operations/refunds/(?P<resource_id>\d+)/confirm$"
            ),
            "methods": {"POST"},
            "category": "REFUND",
            "default_action": "OPERATIONS_PAYMENT_REFUND",
            "resource_type": "payment_refund",
        },
        {
            "pattern": re.compile(r"^/api/payments/payos/refund$"),
            "methods": {"POST"},
            "category": "REFUND",
            "default_action": "PAYOS_REFUND",
            "resource_type": "payment",
        },
        # 4. CẤU HÌNH CHÍNH SÁCH HỆ THỐNG
        {
            "pattern": re.compile(r"^/api/admin/policies$"),
            "methods": {"PUT", "PATCH", "POST"},
            "category": "POLICY",
            "default_action": "POLICY_UPDATE",
            "resource_type": "system_policy",
        },
    ]

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        method = request.method.upper()

        # Kiểm tra xem request có thuộc diện cần ghi Audit Log hay không
        matched_rule, match_groups = self._match_audit_rule(method, path)
        if not matched_rule:
            # Nếu không phải thao tác kiểm toán, cho qua ngay lập tức mà không tốn chi phí
            return await call_next(request)

        # ----------------------------------------------------------------------
        # 1. ĐỌC & SAO CHÉP REQUEST BODY AN TOÀN (STREAM PRESERVATION)
        # ----------------------------------------------------------------------
        content_type = request.headers.get("content-type", "")
        payload_dict = None

        if "multipart/form-data" in content_type:
            # Bỏ đọc body khi upload file để tránh nghẽn stream và tiết kiệm RAM
            payload_dict = {"_info": "multipart/form-data upload omitted"}
        else:
            body_bytes = await request.body()

            # Tạo lại hàm receive để downstream handler trong FastAPI vẫn đọc được request body
            async def receive():
                return {"type": "http.request", "body": body_bytes}

            request._receive = receive

            if body_bytes:
                try:
                    raw_json = json.loads(body_bytes.decode("utf-8"))
                    payload_dict = _mask_sensitive_data(raw_json)
                except Exception:
                    # Nếu không phải JSON, không ghi payload dạng object
                    payload_dict = None

        # ----------------------------------------------------------------------
        # 2. XÁC ĐỊNH THÔNG TIN "AI" (WHO)
        # ----------------------------------------------------------------------
        user_id, user_email, user_role = self._extract_user_context(request)
        ip_address = self._extract_client_ip(request)
        user_agent = request.headers.get("user-agent", "")[:500]

        # ----------------------------------------------------------------------
        # 3. XÁC ĐỊNH THÔNG TIN "LÀM GÌ" (WHAT)
        # ----------------------------------------------------------------------
        action, resource_type, resource_id, description = self._determine_action_details(
            matched_rule=matched_rule,
            match_groups=match_groups,
            payload=payload_dict,
            user_id=user_id,
            user_role=user_role,
        )

        # ----------------------------------------------------------------------
        # 4. THỰC THI REQUEST & ĐO THỜI GIAN "LÚC NÀO" (WHEN)
        # ----------------------------------------------------------------------
        start_time = time.perf_counter()
        created_at = datetime.now()
        status_code = 500
        error_message = None

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as exc:
            error_message = str(exc)
            status_code = 500
            raise
        finally:
            execution_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
            audit_status = "SUCCESS" if status_code < 400 else "FAILED"

            # ------------------------------------------------------------------
            # 5. GHI VÀO CƠ SỞ DỮ LIỆU BẢO ĐẢM KHÔNG LÀM CRASH ỨNG DỤNG (FAIL-SAFE)
            # ------------------------------------------------------------------
            try:
                self._save_audit_log(
                    user_id=user_id,
                    user_email=user_email,
                    user_role=user_role,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    http_method=method,
                    endpoint=path,
                    description=description,
                    request_payload=payload_dict,
                    status_code=status_code,
                    status=audit_status,
                    error_message=error_message,
                    execution_time_ms=execution_time_ms,
                    created_at=created_at,
                )
            except Exception as save_err:
                logger.error(
                    f"[AuditLogMiddleware] Lỗi không thể lưu audit log: {save_err}",
                    exc_info=True,
                )

    def _match_audit_rule(self, method: str, path: str) -> Tuple[Optional[Dict[str, Any]], Dict[str, str]]:
        """Kiểm tra URL và HTTP method với danh sách các quy tắc cần kiểm toán."""
        for rule in self.AUDIT_RULES:
            if method in rule["methods"]:
                match = rule["pattern"].match(path)
                if match:
                    return rule, match.groupdict()

        # Quy tắc mở rộng: Bắt mọi endpoint POST/PATCH/PUT có chứa các từ khóa đặc biệt
        if method in {"POST", "PATCH", "PUT", "DELETE"}:
            path_lower = path.lower()
            if "/refund" in path_lower:
                return {
                    "category": "REFUND",
                    "default_action": "PAYMENT_REFUND",
                    "resource_type": "payment",
                }, {}
            if "/status" in path_lower or "/change-status" in path_lower:
                return {
                    "category": "STATUS_CHANGE",
                    "default_action": "GENERIC_STATUS_CHANGE",
                    "resource_type": "resource",
                }, {}
            if "/review" in path_lower or "/approve" in path_lower or "/reject" in path_lower:
                return {
                    "category": "REVIEW",
                    "default_action": "GENERIC_REVIEW",
                    "resource_type": "review_item",
                }, {}

        return None, {}

    def _extract_user_context(self, request: Request) -> Tuple[Optional[int], Optional[str], Optional[str]]:
        """Giải mã Token JWT từ header Authorization hoặc Cookie để tìm danh tính người dùng."""
        token = None

        # 1. Thử lấy từ header Authorization: Bearer <token>
        auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()

        # 2. Thử lấy từ Cookie
        if not token:
            token = (
                request.cookies.get("ridehub_token")
                or request.cookies.get("access_token")
                or request.cookies.get("token")
            )

        if not token:
            return None, None, "anonymous"

        # 3. Giải mã JWT payload
        payload = decode_access_token(token)
        if not payload:
            return None, None, "anonymous"

        user_id_raw = payload.get("sub")
        try:
            user_id = int(user_id_raw) if user_id_raw is not None else None
        except (ValueError, TypeError):
            user_id = None

        if not user_id:
            return None, None, "anonymous"

        # 4. Tra cứu thông tin User từ Database (để lấy Email và Role chính xác nhất)
        user_email = None
        user_role = payload.get("role") or "customer"

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user_email = user.email
                user_role = user.role
        except Exception as e:
            logger.debug(f"[AuditLog] Không thể đọc chi tiết user {user_id} từ DB: {e}")
        finally:
            db.close()

        return user_id, user_email, user_role

    def _extract_client_ip(self, request: Request) -> Optional[str]:
        """Lấy địa chỉ IP thực của client, ưu tiên các header Reverse Proxy / CDN."""
        x_forwarded_for = request.headers.get("x-forwarded-for")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()

        x_real_ip = request.headers.get("x-real-ip")
        if x_real_ip:
            return x_real_ip.strip()

        if request.client:
            return request.client.host
        return None

    def _determine_action_details(
        self,
        matched_rule: Dict[str, Any],
        match_groups: Dict[str, str],
        payload: Optional[Dict[str, Any]],
        user_id: Optional[int],
        user_role: Optional[str],
    ) -> Tuple[str, str, Optional[str], str]:
        """Tự động phân tích và tạo mô tả hành động trực quan cho con người đọc."""
        category = matched_rule.get("category", "SYSTEM")
        resource_type = match_groups.get("resource_type") or matched_rule.get("resource_type", "resource")
        resource_id = match_groups.get("resource_id")
        action = matched_rule.get("default_action", "ACTION")
        actor_label = f"Người dùng #{user_id} ({user_role})" if user_id else f"Người dùng vô danh ({user_role})"

        # A. THAO TÁC DUYỆT (REVIEWS)
        if category == "REVIEW":
            decision_status = (payload or {}).get("status", "").lower() if payload else ""
            if decision_status == "approved" or match_groups.get("action_verb") == "approve":
                action = "REVIEW_APPROVE"
                description = f"{actor_label} đã PHÊ DUYỆT hồ sơ {resource_type} #{resource_id}."
            elif decision_status == "rejected" or match_groups.get("action_verb") == "reject":
                action = "REVIEW_REJECT"
                reason = (payload or {}).get("reason", "Không có lý do")
                description = f"{actor_label} đã TỪ CHỐI hồ sơ {resource_type} #{resource_id}. Lý do: {reason}."
            else:
                action = "REVIEW_DECISION"
                description = f"{actor_label} xử lý duyệt hồ sơ {resource_type} #{resource_id}."

        # B. THAO TÁC ĐỔI TRẠNG THÁI (STATUS CHANGES)
        elif category == "STATUS_CHANGE":
            if action == "VEHICLE_STATUS_CHANGE":
                new_status = (payload or {}).get("new_status", "UNKNOWN")
                note = (payload or {}).get("note", "")
                description = (
                    f"{actor_label} đã chuyển trạng thái xe #{resource_id} sang '{new_status}'"
                    + (f" (Ghi chú: {note})" if note else ".")
                )
            elif action == "HANDOVER_SETTLEMENT":
                description = f"{actor_label} đã hoàn tất quyết toán & bàn giao xe #{resource_id}."
            elif action == "BOOKING_STATUS_CHANGE":
                new_status = (payload or {}).get("status", "UNKNOWN")
                description = f"{actor_label} đổi trạng thái đơn đặt xe #{resource_id} sang '{new_status}'."
            else:
                description = f"{actor_label} đã thay đổi trạng thái đối với {resource_type} #{resource_id}."

        # C. THAO TÁC HOÀN TIỀN (REFUNDS)
        elif category == "REFUND":
            action = "PAYMENT_REFUND"
            resource_type = "payment"
            if payload:
                resource_id = str(payload.get("transaction_code") or payload.get("booking_id") or "")
                amount = payload.get("amount")
                reason = payload.get("reason", "Yêu cầu hoàn tiền")
                amount_str = f" với số tiền {amount:,.0f}đ" if isinstance(amount, (int, float)) else ""
                description = f"{actor_label} yêu cầu hoàn tiền giao dịch '{resource_id}'{amount_str}. Lý do: {reason}."
            else:
                description = f"{actor_label} thực hiện thao tác hoàn tiền thanh toán."

        # D. CẤU HÌNH CHÍNH SÁCH HỆ THỐNG (POLICIES)
        elif category == "POLICY":
            action = "POLICY_UPDATE"
            resource_type = "system_policy"
            updates = (payload or {}).get("updates", []) if isinstance(payload, dict) else []
            keys_str = ", ".join(str(u.get("policy_key", "")) for u in updates[:5] if isinstance(u, dict))
            resource_id = keys_str[:100] if keys_str else "bulk"
            description = f"{actor_label} đã cập nhật {len(updates)} cấu hình chính sách hệ thống ({keys_str})."

        else:
            description = f"{actor_label} thực hiện hành động {action} trên {resource_type} #{resource_id}."

        return action, resource_type, resource_id, description

    def _save_audit_log(
        self,
        user_id: Optional[int],
        user_email: Optional[str],
        user_role: Optional[str],
        ip_address: Optional[str],
        user_agent: Optional[str],
        action: str,
        resource_type: str,
        resource_id: Optional[str],
        http_method: str,
        endpoint: str,
        description: str,
        request_payload: Optional[Dict[str, Any]],
        status_code: int,
        status: str,
        error_message: Optional[str],
        execution_time_ms: float,
        created_at: datetime,
    ) -> None:
        """Lưu bản ghi AuditLog độc lập vào MySQL Session."""
        db = SessionLocal()
        try:
            log_record = AuditLog(
                user_id=user_id,
                user_email=user_email,
                user_role=user_role,
                ip_address=ip_address,
                user_agent=user_agent,
                action=action,
                resource_type=resource_type,
                resource_id=str(resource_id) if resource_id is not None else None,
                http_method=http_method,
                endpoint=endpoint,
                description=description,
                request_payload=request_payload,
                status_code=status_code,
                status=status,
                error_message=error_message,
                execution_time_ms=execution_time_ms,
                created_at=created_at,
            )
            db.add(log_record)
            db.commit()
            logger.info(
                f"[AuditLog] Đã ghi log ID={log_record.id} | Action={action} | "
                f"User={user_email or user_id} | Status={status_code} ({execution_time_ms}ms)"
            )
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
