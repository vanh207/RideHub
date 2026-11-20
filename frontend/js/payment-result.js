(function () {
  "use strict";

  const query = new URLSearchParams(window.location.search);
  const rawBookingId = query.get("booking_id");
  const bookingId =
    rawBookingId && /^[1-9]\d*$/.test(rawBookingId)
      ? Number(rawBookingId)
      : NaN;
  const configuredApiBase =
    window.CONFIG && typeof window.CONFIG.API_BASE_URL === "string"
      ? window.CONFIG.API_BASE_URL
      : "";
  const apiBase = configuredApiBase
    ? configuredApiBase.replace(/\/$/, "")
    : window.location.port === "8000"
      ? `${window.location.origin}/api`
      : "http://127.0.0.1:8000/api";
  const ui = {
    amount: document.getElementById("paymentAmount"),
    backOrder: document.getElementById("backOrderButton"),
    bookingRef: document.getElementById("bookingRef"),
    checkAgain: document.getElementById("checkAgainButton"),
    details: document.getElementById("transactionDetails"),
    failure: document.getElementById("resultAlert"),
    holdExpiresAt: document.getElementById("holdExpiresAt"),
    login: document.getElementById("loginButton"),
    paidAt: document.getElementById("paidAt"),
    retryPayment: document.getElementById("retryPaymentButton"),
    resultCard: document.getElementById("resultCard"),
    stateIcon: document.getElementById("stateIcon"),
    status: document.getElementById("paymentStatus"),
    statusMessage: document.getElementById("statusMessage"),
    statusTitle: document.getElementById("statusTitle"),
    transactionCode: document.getElementById("transactionCode"),
  };
  const state = { active: true, loading: false, timer: null };
  const terminalStatuses = new Set([
    "SUCCESS",
    "CANCELLED",
    "EXPIRED",
    "FAILED",
    "LATE_PAYMENT",
    "REFUNDED",
    "AMOUNT_MISMATCH",
  ]);
  const statusLabels = {
    SUCCESS: "Thanh toán thành công",
    CANCELLED: "Đã hủy",
    EXPIRED: "Hết hạn giữ chỗ",
    FAILED: "Thanh toán thất bại",
    LATE_PAYMENT: "Thanh toán đến muộn",
    REFUNDED: "Đã hoàn tiền",
    AMOUNT_MISMATCH: "Số tiền không khớp",
    PENDING: "Đang chờ thanh toán",
    NOT_STARTED: "Chưa khởi tạo giao dịch",
  };

  function getToken() {
    try {
      const cookie = document.cookie
        .split(";")
        .map((part) => part.trim())
        .find((part) =>
          /^(ridehub_token|access_token|token|ridehub_auth_token)=/.test(part),
        );
      if (cookie) return decodeURIComponent(cookie.slice(cookie.indexOf("=") + 1));
      return (
        localStorage.getItem("ridehub_auth_token") ||
        localStorage.getItem("ridehub_token") ||
        ""
      );
    } catch (_) {
      return "";
    }
  }

  async function apiRequest() {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 8000);
    const headers = { Accept: "application/json" };
    const token = getToken();
    if (token) headers.Authorization = `Bearer ${token}`;

    try {
      const response = await fetch(
        `${apiBase}/payments/booking/${bookingId}/status`,
        {
          headers,
          credentials: "include",
          signal: controller.signal,
        },
      );
      const data = await response.json().catch(() => null);
      if (!response.ok) {
        const error = new Error("Không thể xác minh trạng thái đơn.");
        error.status = response.status;
        throw error;
      }
      if (!data || typeof data !== "object") {
        throw new Error("Phản hồi trạng thái từ máy chủ không hợp lệ.");
      }
      return data;
    } catch (error) {
      if (error.name === "AbortError" || error instanceof TypeError) {
        throw new Error("Không kết nối được máy chủ. Hãy kiểm tra mạng và thử lại.");
      }
      throw error;
    } finally {
      window.clearTimeout(timeout);
    }
  }

  function setView(title, message, tone, icon) {
    ui.resultCard.className = `result-card ${tone || ""}`.trim();
    ui.stateIcon.textContent = icon || "…";
    ui.statusTitle.textContent = title;
    ui.statusMessage.textContent = message;
  }

  function formatDate(value) {
    if (!value) return "—";
    const date = new Date(value);
    return Number.isNaN(date.getTime())
      ? "—"
      : new Intl.DateTimeFormat("vi-VN", {
          dateStyle: "medium",
          timeStyle: "short",
        }).format(date);
  }

  function formatAmount(value) {
    const amount = Number(value);
    return Number.isFinite(amount) && amount > 0
      ? `${new Intl.NumberFormat("vi-VN", {
          maximumFractionDigits: 0,
        }).format(amount)} VNĐ`
      : "—";
  }

  function setOrderLinks(data) {
    const orderUrl = new URL("payment-qr.html", window.location.href);
    orderUrl.searchParams.set("booking_id", String(bookingId));
    orderUrl.searchParams.set("return_to_order", "1");
    ui.backOrder.href = orderUrl.href;
    ui.backOrder.hidden = false;

    const canRetry =
      data.payment_status === "FAILED" &&
      Number(data.remaining_seconds) > 0 &&
      ["PENDING", "PENDING_PAYMENT"].includes(
        String(data.booking_status || "").toUpperCase(),
      );
    if (canRetry) {
      const retryUrl = new URL("payment-qr.html", window.location.href);
      retryUrl.searchParams.set("booking_id", String(bookingId));
      retryUrl.searchParams.set("retry", "1");
      ui.retryPayment.href = retryUrl.href;
      ui.retryPayment.hidden = false;
    }
  }

  function renderDetails(data, status) {
    ui.bookingRef.textContent = `Mã đơn đặt xe: #${bookingId}`;
    ui.bookingRef.hidden = false;
    ui.details.hidden = false;
    ui.status.textContent = statusLabels[status] || status;
    ui.amount.textContent = formatAmount(data.amount);
    ui.transactionCode.textContent = data.transaction_code || "—";
    ui.paidAt.textContent = formatDate(data.paid_at);
    ui.holdExpiresAt.textContent = formatDate(data.hold_expires_at);
    setOrderLinks(data);
  }

  function renderStatus(data) {
    if (Number(data.booking_id) !== bookingId) {
      throw new Error("Trạng thái trả về không khớp với đơn đang mở.");
    }
    const status = String(data.payment_status || "").toUpperCase();
    renderDetails(data, status);

    if (status === "SUCCESS") {
      const booked = String(data.booking_status || "").toUpperCase() === "BOOKED";
      setView(
        "Thanh toán thành công",
        booked
          ? `Máy chủ đã xác nhận thanh toán và đơn đặt xe #${bookingId} đã được xác nhận.`
          : `Máy chủ đã xác nhận thanh toán cho đơn đặt xe #${bookingId}.`,
        "success",
        "✓",
      );
      return terminalStatuses.has(status);
    }

    if (status === "EXPIRED") {
      setView(
        "Đã hết hạn giữ chỗ",
        "Thời gian giữ chỗ đã kết thúc nên đơn không còn giữ xe. Vui lòng đặt xe lại để chọn một khoảng thời gian còn khả dụng.",
        "warning",
        "⌛",
      );
      return true;
    }

    if (status === "CANCELLED") {
      setView(
        "Giao dịch đã bị hủy",
        "Giao dịch đã được hủy và xe không còn được giữ cho đơn này. Bạn có thể xem lại đơn hoặc bắt đầu một lượt đặt xe mới.",
        "failure",
        "×",
      );
      return true;
    }

    if (status === "FAILED") {
      setView(
        "Thanh toán thất bại",
        data.failure_reason ||
          "Cổng thanh toán không xác nhận giao dịch. Nếu thời hạn giữ chỗ còn, bạn có thể thử thanh toán lại.",
        "failure",
        "×",
      );
      return true;
    }

    if (status === "LATE_PAYMENT") {
      setView(
        "Thanh toán được ghi nhận sau khi giữ chỗ hết hạn",
        "Đơn chưa được xác nhận tự động. Vui lòng liên hệ RideHub để được hướng dẫn xử lý khoản thanh toán.",
        "warning",
        "!",
      );
      return true;
    }

    if (status === "AMOUNT_MISMATCH") {
      setView(
        "Số tiền thanh toán cần được kiểm tra",
        "Số tiền nhận được không khớp với giao dịch. Đơn chưa được xác nhận; vui lòng liên hệ RideHub để được hỗ trợ.",
        "warning",
        "!",
      );
      return true;
    }

    if (status === "REFUNDED") {
      setView(
        "Giao dịch đã được hoàn tiền",
        "Khoản thanh toán đã được hoàn. Đơn đặt xe này không còn ở trạng thái thanh toán thành công.",
        "warning",
        "↩",
      );
      return true;
    }

    setView(
      "Đang chờ xác nhận thanh toán",
      "RideHub đang đối chiếu giao dịch với PayOS. Trang sẽ tự động cập nhật khi có kết quả.",
      "",
      "…",
    );
    return false;
  }

  function showError(error) {
    ui.resultCard.setAttribute("aria-busy", "false");
    ui.details.hidden = true;
    ui.checkAgain.hidden = false;
    ui.failure.hidden = false;

    if (error.status === 401 || !getToken()) {
      setView(
        "Vui lòng đăng nhập",
        "Bạn cần đăng nhập để xác minh trạng thái và quyền truy cập đơn đặt xe.",
        "warning",
        "!",
      );
      ui.login.hidden = false;
      ui.failure.textContent =
        "Sau khi đăng nhập, hãy mở lại đường dẫn kết quả có booking_id.";
      ui.checkAgain.hidden = true;
      return;
    }
    if (error.status === 404) {
      setView(
        "Không tìm thấy đơn đặt xe",
        "Đơn không tồn tại hoặc tài khoản hiện tại không có quyền xem đơn này.",
        "failure",
        "×",
      );
      ui.failure.textContent = "";
      ui.checkAgain.hidden = true;
      return;
    }
    setView(
      "Chưa thể xác minh kết quả",
      "Máy chủ tạm thời không thể kiểm tra thanh toán. Trạng thái đơn chưa được suy đoán; hãy thử kiểm tra lại.",
      "warning",
      "!",
    );
    ui.failure.textContent = error.message;
  }

  async function loadStatus() {
    if (!state.active || state.loading) return;
    if (!Number.isSafeInteger(bookingId) || bookingId <= 0) {
      setView(
        "Đường dẫn thiếu mã đơn",
        "Không tìm thấy booking_id hợp lệ. Hãy mở lại trang từ luồng đặt xe hoặc thanh toán.",
        "failure",
        "×",
      );
      ui.resultCard.setAttribute("aria-busy", "false");
      return;
    }
    if (!getToken()) {
      showError({ status: 401 });
      return;
    }

    state.loading = true;
    ui.resultCard.setAttribute("aria-busy", "true");
    ui.failure.hidden = true;
    ui.checkAgain.hidden = true;
    try {
      const data = await apiRequest();
      const terminal = renderStatus(data);
      ui.resultCard.setAttribute("aria-busy", "false");
      if (!terminal && state.active) {
        state.timer = window.setTimeout(loadStatus, 5000);
      }
    } catch (error) {
      showError(error);
    } finally {
      state.loading = false;
    }
  }

  ui.checkAgain.addEventListener("click", loadStatus);
  window.addEventListener("pagehide", () => {
    state.active = false;
    if (state.timer) window.clearTimeout(state.timer);
  });

  loadStatus();
})();
