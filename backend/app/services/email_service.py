"""Lớp gửi email dùng chung (SMTP hoặc Mock) cho thông báo đơn thuê xe.
Dành cho ticket: [BE] Lớp gửi email thông báo

Hỗ trợ:
- Chế độ Mock: In nội dung email ra console & lưu vào danh sách phục vụ kiểm thử không cần cấu hình tài khoản.
- Chế độ SMTP: Gửi email thực tế qua giao thức SMTP (Gmail, Sendgrid, Mailgun...) hỗ trợ TLS/SSL và bảo mật thông tin.
- Mẫu email HTML thông báo đơn xe, biên bản bàn giao, thanh toán, hoàn tiền cọc chuẩn nhận diện thương hiệu RideHub.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
import email.utils
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
import smtplib
from typing import Any, Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger("ridehub.email")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)


@dataclass
class EmailPayload:
    """Đối tượng chứa dữ liệu một email cần gửi."""
    to_email: str
    subject: str
    html_content: str
    text_content: Optional[str] = None
    from_email: Optional[str] = None
    from_name: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)


class BaseEmailSender(ABC):
    """Giao diện trừu tượng (Interface) cho các bộ gửi email."""

    @abstractmethod
    def send(self, payload: EmailPayload) -> bool:
        """Gửi email và trả về True nếu thành công, False nếu thất bại."""
        pass


class MockEmailSender(BaseEmailSender):
    """Bộ gửi email giả lập (Mock).
    Dùng cho môi trường Development / Unit Test, không cần internet hoặc tài khoản SMTP.
    """

    def __init__(self):
        self.sent_history: List[EmailPayload] = []

    def send(self, payload: EmailPayload) -> bool:
        self.sent_history.append(payload)
        
        # In trực quan ra console cho lập trình viên theo dõi
        print("\n" + "=" * 70)
        print("📨 [MOCK EMAIL DISPATCHED] (Chế độ giả lập - Không tốn phí)")
        print(f"⏰ Thời gian: {payload.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"👤 Người gửi: {payload.from_name or settings.SMTP_FROM_NAME} <{payload.from_email or settings.SMTP_FROM_EMAIL}>")
        print(f"🎯 Người nhận: {payload.to_email}")
        print(f"📌 Tiêu đề:   {payload.subject}")
        print("-" * 70)
        # In tóm tắt nội dung văn bản thuần
        text_preview = payload.text_content or "HTML Content Included"
        print(f"📝 Tóm tắt nội dung:\n{text_preview[:400]}...")
        print("=" * 70 + "\n")

        logger.info(f"[MockEmail] Đã ghi nhận gửi email thành công tới: {payload.to_email} | Tiêu đề: {payload.subject}")
        return True

    def get_last_sent(self) -> Optional[EmailPayload]:
        """Lấy email vừa gửi gần nhất (phục vụ viết unit test)."""
        return self.sent_history[-1] if self.sent_history else None

    def clear_history(self) -> None:
        """Xóa lịch sử gửi email mock."""
        self.sent_history.clear()


class SMTPEmailSender(BaseEmailSender):
    """Bộ gửi email thực tế qua giao thức SMTP (Gmail, Sendgrid, SMTP Server nội bộ)."""

    def __init__(
        self,
        host: str = settings.SMTP_HOST,
        port: int = settings.SMTP_PORT,
        user: str = settings.SMTP_USER,
        password: str = settings.SMTP_PASSWORD,
        use_tls: bool = settings.SMTP_TLS,
        from_email: str = settings.SMTP_FROM_EMAIL,
        from_name: str = settings.SMTP_FROM_NAME,
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.use_tls = use_tls
        self.from_email = from_email
        self.from_name = from_name

    def send(self, payload: EmailPayload) -> bool:
        sender_email = payload.from_email or self.from_email
        sender_name = payload.from_name or self.from_name

        # Tạo MIME Multipart message (hỗ trợ cả plain text và html)
        msg = MIMEMultipart("alternative")
        msg["Subject"] = payload.subject
        msg["From"] = email.utils.formataddr((sender_name, sender_email))
        msg["To"] = payload.to_email
        msg["Date"] = email.utils.formatdate(localtime=True)

        # Đính kèm phần văn bản thuần (fallback)
        if payload.text_content:
            msg.attach(MIMEText(payload.text_content, "plain", "utf-8"))
        else:
            msg.attach(MIMEText("Vui lòng mở ứng dụng email hỗ trợ HTML để xem thông báo này.", "plain", "utf-8"))

        # Đính kèm phần HTML
        msg.attach(MIMEText(payload.html_content, "html", "utf-8"))

        try:
            with smtplib.SMTP(self.host, self.port, timeout=15) as server:
                server.ehlo()
                if self.use_tls:
                    server.starttls()
                    server.ehlo()
                if self.user and self.password:
                    server.login(self.user, self.password)
                server.send_message(msg)

            logger.info(f"[SMTPEmail] Gửi email thành công tới {payload.to_email} qua {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"[SMTPEmail] Lỗi khi gửi email tới {payload.to_email}: {str(e)}", exc_info=True)
            return False


class EmailService:
    """Lớp quản lý dịch vụ email dùng chung cho toàn hệ thống RideHub.
    Cung cấp các hàm gửi thông báo đơn hàng, biên bản giao nhận, cọc và hoàn tiền.
    """

    def __init__(self, backend_type: Optional[str] = None):
        # Xác định backend: nếu không chỉ định, lấy từ settings.EMAIL_BACKEND
        selected_backend = (backend_type or settings.EMAIL_BACKEND).strip().lower()

        # Kiểm tra tự động: nếu chọn "smtp" mà chưa có cấu hình SMTP_USER thì tự chuyển sang "mock" để tránh crash
        if selected_backend == "smtp" and not settings.SMTP_USER:
            logger.warning("[EmailService] EMAIL_BACKEND='smtp' nhưng chưa điền SMTP_USER trong .env. Tự động chuyển sang chế độ 'mock'.")
            selected_backend = "mock"

        if selected_backend == "smtp":
            self.sender: BaseEmailSender = SMTPEmailSender()
            self.backend_name = "SMTP"
        else:
            self.sender: BaseEmailSender = MockEmailSender()
            self.backend_name = "Mock"

        logger.info(f"[EmailService] Đã khởi tạo dịch vụ gửi email với chế độ: {self.backend_name}")

    def send_raw(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
    ) -> bool:
        """Gửi email tùy biến bất kỳ."""
        payload = EmailPayload(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
        )
        return self.sender.send(payload)

    # --------------------------------------------------------------------------
    # MẪU THIẾT KẾ EMAIL CHUẨN HTML CHO THÔNG BÁO ĐƠN HÀNG (RIDEHUB BRANDED)
    # --------------------------------------------------------------------------
    @staticmethod
    def _render_base_template(title: str, preheader: str, body_html: str, call_to_action: Optional[Dict[str, str]] = None) -> str:
        """Tạo layout HTML email responsive, sang trọng theo nhận diện thương hiệu RideHub."""
        cta_button_html = ""
        if call_to_action and call_to_action.get("url") and call_to_action.get("text"):
            cta_button_html = f"""
            <div style="text-align: center; margin: 30px 0;">
                <a href="{call_to_action['url']}" style="background-color: #1d4ed8; color: #ffffff; padding: 12px 28px; text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 15px; display: inline-block;">
                    {call_to_action['text']}
                </a>
            </div>
            """

        return f"""
        <!DOCTYPE html>
        <html lang="vi">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f1f5f9; margin: 0; padding: 20px; color: #0f172a; }}
                .email-card {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.06); border: 1px solid #e2e8f0; }}
                .email-header {{ background: linear-gradient(135deg, #0f172a 0%, #1e293b 60%, #1e3a8a 100%); color: #ffffff; padding: 24px; text-align: center; }}
                .email-body {{ padding: 24px; }}
                .email-footer {{ background: #f8fafc; padding: 16px; text-align: center; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0; }}
                .data-table {{ width: 100%; border-collapse: collapse; margin: 16px 0; }}
                .data-table td {{ padding: 10px 12px; border-bottom: 1px solid #f1f5f9; font-size: 14px; }}
                .data-table td.label {{ color: #64748b; font-weight: 500; width: 40%; }}
                .data-table td.value {{ color: #0f172a; font-weight: 600; text-align: right; }}
                .badge {{ display: inline-block; padding: 4px 10px; border-radius: 9999px; font-size: 12px; font-weight: 600; }}
                .badge-success {{ background: #dcfce7; color: #166534; }}
                .badge-primary {{ background: #e0e7ff; color: #3730a3; }}
                .badge-warning {{ background: #fef3c7; color: #92400e; }}
            </style>
        </head>
        <body>
            <span style="display:none;font-size:0px;color:#fff;line-height:0px;max-height:0px;max-width:0px;opacity:0;overflow:hidden;">
                {preheader}
            </span>
            <div class="email-card">
                <div class="email-header">
                    <div style="font-size: 20px; font-weight: 800; letter-spacing: -0.5px;">🚗 RIDEHUB VIỆT NAM</div>
                    <div style="font-size: 13px; color: #cbd5e1; margin-top: 4px;">Nền tảng cho thuê ô tô & xe máy tự lái</div>
                </div>
                <div class="email-body">
                    <h2 style="margin-top: 0; color: #0f172a; font-size: 18px; border-bottom: 2px solid #f1f5f9; padding-bottom: 10px;">
                        {title}
                    </h2>
                    {body_html}
                    {cta_button_html}
                </div>
                <div class="email-footer">
                    <p style="margin: 0 0 6px 0;">Cần hỗ trợ? Gọi hotline 24/7: <strong style="color: #1d4ed8;">1900-7433</strong> hoặc gửi về <a href="mailto:support@ridehub.vn" style="color: #1d4ed8;">support@ridehub.vn</a></p>
                    <p style="margin: 0;">© {datetime.now().year} RideHub Inc. Trạm xe Sân bay Đà Nẵng & Hệ sinh thái xe toàn quốc.</p>
                </div>
            </div>
        </body>
        </html>
        """

    # --------------------------------------------------------------------------
    # 1. THÔNG BÁO XÁC NHẬN ĐẶT ĐƠN XE THÀNH CÔNG
    # --------------------------------------------------------------------------
    def send_booking_confirmation(
        self,
        to_email: str,
        customer_name: str,
        booking_id: Any,
        vehicle_name: str,
        start_time: str,
        end_time: str,
        total_amount: float,
        deposit_amount: float,
        pickup_location: str = "Trạm trung tâm RideHub",
    ) -> bool:
        """Gửi email thông báo đơn đặt giữ xe thành công kèm mã đơn & tiền cọc."""
        subject = f"[RideHub] Xác nhận đặt xe thành công - Đơn #{booking_id}"
        preheader = f"Chúc mừng {customer_name}! Đơn thuê xe #{booking_id} của bạn đã được xác nhận."

        body_html = f"""
        <p>Xin chào <strong>{customer_name}</strong>,</p>
        <p>Đơn đặt xe tự lái của bạn trên nền tảng <strong>RideHub</strong> đã được ghi nhận và khóa lịch thành công. Dưới đây là thông tin chi tiết:</p>
        
        <table class="data-table">
            <tr>
                <td class="label">Mã đơn đặt xe</td>
                <td class="value"><span class="badge badge-primary">#{booking_id}</span></td>
            </tr>
            <tr>
                <td class="label">Phương tiện thuê</td>
                <td class="value">{vehicle_name}</td>
            </tr>
            <tr>
                <td class="label">Thời gian nhận xe</td>
                <td class="value">{start_time}</td>
            </tr>
            <tr>
                <td class="label">Thời gian trả xe</td>
                <td class="value">{end_time}</td>
            </tr>
            <tr>
                <td class="label">Địa điểm giao nhận</td>
                <td class="value">{pickup_location}</td>
            </tr>
            <tr>
                <td class="label">Tiền cọc giữ chỗ</td>
                <td class="value" style="color: #16a34a;">{deposit_amount:,.0f} VNĐ</td>
            </tr>
            <tr>
                <td class="label">Tổng giá trị đơn</td>
                <td class="value" style="color: #1d4ed8; font-size: 16px;">{total_amount:,.0f} VNĐ</td>
            </tr>
        </table>

        <div style="background-color: #f8fafc; border-left: 4px solid #1d4ed8; padding: 12px; margin-top: 16px; font-size: 13.5px; color: #475569;">
            📌 <strong>Lưu ý khi nhận xe:</strong> Quý khách vui lòng mang theo bản gốc <strong>CCCD gắn chip</strong> và <strong>GPLX tương ứng</strong> để nhân viên đối chiếu và ký Biên bản bàn giao điện tử.
        </div>
        """

        text_content = (
            f"Xin chào {customer_name},\n\n"
            f"Đơn đặt xe #{booking_id} của bạn đã thành công!\n"
            f"- Phương tiện: {vehicle_name}\n"
            f"- Nhận xe: {start_time}\n"
            f"- Trả xe: {end_time}\n"
            f"- Địa điểm: {pickup_location}\n"
            f"- Tiền cọc giữ chỗ: {deposit_amount:,.0f} VNĐ\n"
            f"- Tổng tiền: {total_amount:,.0f} VNĐ\n\n"
            f"Hotline hỗ trợ: 1900-7433 | RideHub"
        )

        html = self._render_base_template(
            title="Xác Nhận Đặt Giữ Xe Thành Công",
            preheader=preheader,
            body_html=body_html,
            call_to_action={"url": "http://localhost:8000", "text": "Xem Chi Tiết Đơn Hàng"}
        )

        return self.send_raw(to_email, subject, html, text_content)

    # --------------------------------------------------------------------------
    # 2. THÔNG BÁO BIÊN BẢN GIAO / NHẬN XE ĐIỆN TỬ
    # --------------------------------------------------------------------------
    def send_handover_protocol_notification(
        self,
        to_email: str,
        customer_name: str,
        protocol_code: str,
        booking_id: Any,
        vehicle_name: str,
        license_plate: str,
        protocol_type: str,  # "CHECK_OUT" hoặc "CHECK_IN"
        odo_reading: int,
        fuel_level: str,
        signed_at: Optional[str] = None,
    ) -> bool:
        """Gửi email xác nhận biên bản điện tử đã được ký số khi giao xe hoặc nhận trả xe."""
        is_checkout = (protocol_type == "CHECK_OUT")
        action_name = "Bàn Giao Xe Xuất Phát" if is_checkout else "Hoàn Trả Xe & Tất Toán"
        badge_class = "badge-primary" if is_checkout else "badge-success"

        subject = f"[RideHub] Biên bản {action_name.lower()} số {protocol_code}"
        preheader = f"Biên bản điện tử #{protocol_code} cho xe {license_plate} đã được ký số thành công."

        signed_time = signed_at or datetime.now().strftime("%H:%M - %d/%m/%Y")

        body_html = f"""
        <p>Xin chào <strong>{customer_name}</strong>,</p>
        <p>Biên bản điện tử số <strong>{protocol_code}</strong> đối với đơn thuê <strong>#{booking_id}</strong> đã được hai bên ký xác nhận số hóa thành công.</p>
        
        <table class="data-table">
            <tr>
                <td class="label">Mã biên bản</td>
                <td class="value"><span class="badge {badge_class}">{protocol_code}</span></td>
            </tr>
            <tr>
                <td class="label">Trạng thái luồng</td>
                <td class="value"><strong>{action_name}</strong></td>
            </tr>
            <tr>
                <td class="label">Phương tiện & Biển số</td>
                <td class="value">{vehicle_name} ({license_plate})</td>
            </tr>
            <tr>
                <td class="label">Số km đồng hồ (ODO)</td>
                <td class="value"><strong>{odo_reading:,} km</strong></td>
            </tr>
            <tr>
                <td class="label">Mức nhiên liệu / Pin</td>
                <td class="value"><strong>{fuel_level}</strong></td>
            </tr>
            <tr>
                <td class="label">Thời điểm ký số</td>
                <td class="value">{signed_time}</td>
            </tr>
        </table>

        <p style="font-size: 13.5px; color: #475569;">
            Biên bản này có giá trị pháp lý làm căn cứ giải quyết mọi phát sinh về hiện trạng phương tiện, số km và nhiên liệu. Quý khách có thể tải bản sao điện tử bất kỳ lúc nào.
        </p>
        """

        text_content = (
            f"Xin chào {customer_name},\n\n"
            f"Biên bản {action_name} #{protocol_code} đã hoàn tất.\n"
            f"- Xe: {vehicle_name} ({license_plate})\n"
            f"- Số ODO: {odo_reading:,} km\n"
            f"- Mức nhiên liệu: {fuel_level}\n"
            f"- Thời gian ký: {signed_time}\n\n"
            f"RideHub trân trọng cảm ơn Quý khách!"
        )

        html = self._render_base_template(
            title=f"Biên Bản Điện Tử - {action_name}",
            preheader=preheader,
            body_html=body_html,
            call_to_action={"url": "http://localhost:8000/pages/items.html", "text": "Tra Cứu Biên Bản"}
        )

        return self.send_raw(to_email, subject, html, text_content)

    # --------------------------------------------------------------------------
    # 3. THÔNG BÁO HOÀN TIỀN CỌC / QUYẾT TOÁN TẤT TOÁN
    # --------------------------------------------------------------------------
    def send_deposit_refund_notification(
        self,
        to_email: str,
        customer_name: str,
        booking_id: Any,
        refund_amount: float,
        hold_fine_deposit: float = 0,
        bank_name: str = "Tài khoản thanh toán ban đầu",
    ) -> bool:
        """Gửi email thông báo hoàn trả tiền cọc sau chuyến đi."""
        subject = f"[RideHub] Thông báo hoàn tiền cọc đơn thuê #{booking_id}"
        preheader = f"RideHub đã thực hiện lệnh hoàn tiền cọc {refund_amount:,.0f} VNĐ cho bạn."

        body_html = f"""
        <p>Xin chào <strong>{customer_name}</strong>,</p>
        <p>RideHub xin thông báo lệnh hoàn trả tiền cọc thế chấp cho đơn thuê <strong>#{booking_id}</strong> đã được xử lý thành công.</p>
        
        <table class="data-table">
            <tr>
                <td class="label">Mã đơn đặt xe</td>
                <td class="value">#{booking_id}</td>
            </tr>
            <tr>
                <td class="label">Số tiền hoàn trả ngay</td>
                <td class="value" style="color: #16a34a; font-size: 16px;"><strong>{refund_amount:,.0f} VNĐ</strong></td>
            </tr>
            <tr>
                <td class="label">Cọc giữ phạt nguội (nếu có)</td>
                <td class="value" style="color: #d97706;">{hold_fine_deposit:,.0f} VNĐ</td>
            </tr>
            <tr>
                <td class="label">Phương thức nhận</td>
                <td class="value">{bank_name}</td>
            </tr>
            <tr>
                <td class="label">Thời gian đối soát</td>
                <td class="value">{datetime.now().strftime('%d/%m/%Y')}</td>
            </tr>
        </table>

        <div style="background-color: #fffbeb; border-left: 4px solid #f59e0b; padding: 12px; margin-top: 14px; font-size: 13px; color: #92400e;">
            ℹ️ <strong>Lưu ý về khoản cọc phạt nguội:</strong> Theo quy chế vận hành, khoản giữ hộ phạt nguội ({hold_fine_deposit:,.0f} VNĐ) sẽ được hoàn trả tự động sau 15 - 20 ngày sau khi Cục CSGT xác nhận xe không phát sinh lỗi vi phạm trong thời gian thuê.
        </div>
        """

        text_content = (
            f"Xin chào {customer_name},\n\n"
            f"RideHub đã thực hiện hoàn trả tiền cọc đơn #{booking_id}:\n"
            f"- Tiền hoàn trả ngay: {refund_amount:,.0f} VNĐ\n"
            f"- Tiền giữ phạt nguội: {hold_fine_deposit:,.0f} VNĐ\n\n"
            f"Cảm ơn bạn đã đồng hành cùng RideHub!"
        )

        html = self._render_base_template(
            title="Xác Nhận Hoàn Trả Tiền Cọc",
            preheader=preheader,
            body_html=body_html,
        )

        return self.send_raw(to_email, subject, html, text_content)


# Khởi tạo một singleton instance dùng chung toàn ứng dụng backend
email_service = EmailService()

