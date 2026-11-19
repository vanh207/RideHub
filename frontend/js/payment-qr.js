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
      : `http://127.0.0.1:8000/api`;
  const ui = {
    amount: document.getElementById("amountDisplay"),
    amountCopy: document.getElementById("amountCopyDisplay"),
    bankName: document.getElementById("bankName"),
    accountName: document.getElementById("accountName"),
    accountNumber: document.getElementById("accountNumber"),
    bookingId: document.getElementById("bookingIdDisplay"),
    cancelButton: document.getElementById("cancelPaymentButton"),
    colLeft: document.getElementById("colLeft"),
    colRight: document.getElementById("colRight"),
    countdown: document.getElementById("timerDisplay"),
    downloadQr: document.getElementById("downloadQr"),
    error: document.getElementById("pageError"),
    errorText: document.getElementById("pageErrorText"),
    expiredScreen: document.getElementById("expiredScreen"),
    expiredTitle: document.querySelector(".expired-title"),
    expiredMessage: document.getElementById("expiredMessage"),
    fill: document.getElementById("progressFill"),
    laser: document.getElementById("laser"),
    paymentCard: document.getElementById("paymentCard"),
    qr: document.getElementById("qrImg"),
    qrExpiredOverlay: document.getElementById("qrExpiredOverlay"),
    receiptAmount: document.getElementById("receiptAmount"),
    receiptBank: document.getElementById("receiptBank"),
    receiptBookingId: document.getElementById("receiptBookingId"),
    receiptTransaction: document.getElementById("receiptTransaction"),
    retryButton: document.getElementById("retryButton"),
    spinner: document.getElementById("spinner"),
    statusBadge: document.getElementById("statusBadge"),
    statusBar: document.getElementById("statusBar"),
    statusText: document.getElementById("statusText"),
    successBookingId: document.getElementById("successBookingId"),
    successScreen: document.getElementById("successScreen"),
    successSub: document.querySelector(".success-sub"),
    toast: document.getElementById("toast"),
    transferDescription: document.getElementById("transferDescription"),
  };
  const state = {
    active: true,
    deadline: null,
    holdDuration: 1,
    amount: null,
    transactionCode: "",
    timer: null,
    pollTimeout: null,
    requestController: null,
    polling: false,
    terminal: false,
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

  function apiErrorMessage(data, fallback) {
    const detail = data && (data.detail || data.message);
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail.map((item) => item.msg || "Dữ liệu không hợp lệ").join(", ");
    }
    return fallback;
  }

  async function apiRequest(path, options) {
    const controller = new AbortController();
    state.requestController = controller;
    const timeout = window.setTimeout(() => controller.abort(), 8000);
    const headers = { Accept: "application/json" };
    const token = getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
    if (options && options.body !== undefined) {
      headers["Content-Type"] = "application/json";
    }

    try {
      const response = await fetch(`${apiBase}${path}`, {
        method: (options && options.method) || "GET",
        headers,
        credentials: "include",
        body:
          options && options.body !== undefined
            ? JSON.stringify(options.body)
            : undefined,
        signal: controller.signal,
      });
      const data = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(
          apiErrorMessage(data, `Máy chủ trả lỗi (${response.status}).`),
        );
      }
      if (!data || typeof data !== "object") {
        throw new Error("Phản hồi từ máy chủ không hợp lệ.");
      }
      return data;
    } catch (error) {
      if (error.name === "AbortError") {
        throw new Error("Yêu cầu quá thời gian chờ. Vui lòng thử lại.");
      }
      if (error instanceof TypeError) {
        throw new Error("Không kết nối được máy chủ. Kiểm tra mạng và thử lại.");
      }
      throw error;
    } finally {
      window.clearTimeout(timeout);
      if (state.requestController === controller) state.requestController = null;
    }
  }

  function showError(message, retryable) {
    ui.errorText.textContent = message;
    ui.error.hidden = false;
    ui.retryButton.hidden = !retryable;
  }

  function clearError() {
    ui.error.hidden = true;
    ui.errorText.textContent = "";
  }

  function formatAmount(value) {
    return new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 }).format(
      value,
    );
  }

  function formatTime(seconds) {
    const minutes = Math.floor(seconds / 60);
    const remaining = seconds % 60;
    return `${String(minutes).padStart(2, "0")}:${String(remaining).padStart(2, "0")}`;
  }

  function setBadge(label, className) {
    const dot = ui.statusBadge.querySelector(".badge-dot");
    ui.statusBadge.className = `badge ${className}`;
    ui.statusBadge.textContent = label;
    if (dot) ui.statusBadge.prepend(dot);
  }

  function setDeadline(remainingSeconds, totalSeconds) {
    const seconds = Number(remainingSeconds);
    if (!Number.isFinite(seconds) || seconds < 0) {
      throw new Error("Backend không trả về thời hạn giữ chỗ hợp lệ.");
    }
    state.holdDuration = Math.max(1, Number(totalSeconds) || state.holdDuration);
    state.deadline = Date.now() + seconds * 1000;
    updateCountdown();
    if (state.timer) window.clearInterval(state.timer);
    if (seconds > 0) {
      state.timer = window.setInterval(updateCountdown, 250);
    }
  }

  function updateCountdown() {
    if (state.deadline === null) return;
    const remaining = Math.max(
      0,
      Math.ceil((state.deadline - Date.now()) / 1000),
    );
    ui.countdown.textContent = formatTime(remaining);
    ui.countdown.classList.toggle("urgent", remaining <= 60);
    ui.fill.style.width = `${Math.min(
      100,
      (remaining / state.holdDuration) * 100,
    )}%`;
    if (remaining === 0) {
      window.clearInterval(state.timer);
      state.timer = null;
      if (state.pollTimeout) window.clearTimeout(state.pollTimeout);
      state.pollTimeout = window.setTimeout(() => {
        state.pollTimeout = null;
        pollPaymentStatus();
      }, 0);
    }
  }

  function setQrImage(value) {
    if (!value) return;
    let url;
    try {
      url = new URL(value);
    } catch (_) {
      throw new Error("Backend không trả về đường dẫn mã QR hợp lệ.");
    }
    if (url.protocol !== "https:" || url.hostname !== "api.qrserver.com") {
      throw new Error("Đường dẫn mã QR từ máy chủ không được chấp nhận.");
    }
    ui.qr.src = url.href;
    ui.downloadQr.href = url.href;
    ui.downloadQr.download = `RideHub-booking-${bookingId}.png`;
  }

  function renderDetails(data) {
    if (Number.isFinite(Number(data.amount)) && Number(data.amount) > 0) {
      state.amount = Number(data.amount);
      const formatted = formatAmount(state.amount);
      ui.amount.textContent = formatted;
      ui.amountCopy.textContent = formatted;
      ui.receiptAmount.textContent = formatted;
    }
    if (data.transaction_code) {
      state.transactionCode = String(data.transaction_code);
      ui.receiptTransaction.textContent = state.transactionCode;
    }
    const bankName = data.bin ? `BIN ${data.bin}` : "";
    const bankValues = {
      bankName,
      accountNumber: data.account_number || "",
      accountName: data.account_name || "",
    };
    Object.entries(bankValues).forEach(([key, value]) => {
      const element = ui[key];
      const row = document.getElementById(`${key}Row`);
      element.textContent = value || "—";
      if (row) row.hidden = !value;
    });
    ui.bookingId.textContent = String(bookingId);
    ui.receiptBookingId.textContent = String(bookingId);
    ui.successBookingId.textContent = String(bookingId);
    const description = data.description || `Coc xe don ${bookingId}`;
    ui.transferDescription.textContent = description;
    document.getElementById("descriptionRow").hidden = !description;
    document.getElementById("amountRow").hidden = !state.amount;
    const qrUrl = data.qr_code_url;
    if (qrUrl) setQrImage(qrUrl);

    const hasRemainingSeconds =
      data.remaining_seconds !== undefined &&
      data.remaining_seconds !== null &&
      Number.isFinite(Number(data.remaining_seconds));
    if (hasRemainingSeconds) {
      setDeadline(data.remaining_seconds, data.hold_duration_seconds);
    } else if (data.hold_expires_at) {
      const expiry = Date.parse(data.hold_expires_at);
      if (!Number.isFinite(expiry)) {
        throw new Error("Thời hạn giữ chỗ trong phản hồi không hợp lệ.");
      }
      setDeadline(
        Math.max(0, Math.ceil((expiry - Date.now()) / 1000)),
        data.hold_duration_seconds,
      );
    } else {
      throw new Error("Backend thiếu dữ liệu thời hạn giữ chỗ.");
    }
  }

  function stopActivity() {
    state.terminal = true;
    if (state.timer) window.clearInterval(state.timer);
    if (state.pollTimeout) window.clearTimeout(state.pollTimeout);
    state.timer = null;
    state.pollTimeout = null;
    ui.spinner.style.display = "none";
    ui.laser.style.display = "none";
    ui.cancelButton.disabled = true;
  }

  function showSuccess() {
    stopActivity();
    ui.colLeft.style.display = "none";
    ui.colRight.style.display = "none";
    ui.successScreen.classList.add("visible");
    ui.successSub.textContent = `Đơn hàng #${bookingId} đã được xác nhận`;
    setBadge("Thanh toán thành công", "badge-success");
    ui.statusText.textContent = "Thanh toán đã được xác nhận bởi máy chủ.";
    ui.receiptBank.textContent = ui.bankName.textContent === "—" ? "PayOS" : ui.bankName.textContent;
    const time = document.getElementById("txTime");
    if (time) time.textContent = new Date().toLocaleString("vi-VN");
  }

  function showTerminalFailure(status) {
    stopActivity();
    ui.colLeft.style.display = "none";
    ui.colRight.style.display = "none";
    ui.expiredScreen.classList.add("visible");
    ui.qrExpiredOverlay.classList.add("visible");
    const labels = {
      CANCELLED: ["Giao dịch đã bị hủy", "Đơn giữ chỗ đã được hủy."],
      EXPIRED: ["Giao dịch đã hết hạn", "Thời gian giữ chỗ đã hết. Vui lòng tạo đơn đặt xe mới."],
      FAILED: ["Thanh toán thất bại", "Giao dịch không được hệ thống thanh toán xác nhận."],
      LATE_PAYMENT: ["Thanh toán đến muộn", "Khoản thanh toán đến sau khi giữ chỗ hết hạn và cần được xử lý."],
      REFUNDED: ["Giao dịch đã hoàn tiền", "Khoản thanh toán này đã được hoàn tiền."],
      AMOUNT_MISMATCH: ["Số tiền không khớp", "Khoản thanh toán cần được kiểm tra và xử lý thủ công."],
    };
    const message = labels[status] || labels.EXPIRED;
    ui.expiredTitle.textContent = message[0];
    ui.expiredMessage.textContent = message[1];
    setBadge(message[0], "badge-danger");
    ui.statusText.textContent = message[1];
    ui.countdown.textContent = "00:00";
    ui.fill.style.width = "0%";
  }

  function renderStatus(data) {
    if (!data || Number(data.booking_id) !== bookingId) {
      throw new Error("Phản hồi trạng thái không khớp booking đang mở.");
    }
    renderDetails(data);
    const status = String(data.payment_status || "").toUpperCase();
    if (status === "SUCCESS") {
      showSuccess();
      return;
    }
    if (
      [
        "CANCELLED",
        "EXPIRED",
        "FAILED",
        "LATE_PAYMENT",
        "REFUNDED",
        "AMOUNT_MISMATCH",
      ].includes(
        status,
      )
    ) {
      showTerminalFailure(status);
      return;
    }
    if (status === "NOT_STARTED") {
      setBadge("Đang tạo giao dịch", "badge-warning");
      return;
    }
    setBadge("Đang chờ thanh toán", "badge-warning");
    ui.statusText.textContent =
      "Hệ thống đang tự động kiểm tra trạng thái thanh toán.";
    ui.spinner.style.display = "";
    if (data.qr_code_url) ui.laser.style.display = "block";
  }

  async function createPayment() {
    const created = await apiRequest("/payments/deposit/payos", {
      method: "POST",
      body: { booking_id: bookingId },
    });
    if (
      Number(created.booking_id) !== bookingId ||
      !Number.isFinite(Number(created.amount)) ||
      Number(created.amount) <= 0 ||
      !created.qr_code_url
    ) {
      throw new Error("Backend trả thiếu dữ liệu giao dịch hoặc mã QR.");
    }
    renderDetails(created);
    setBadge("Đang chờ thanh toán", "badge-warning");
    return created;
  }

  async function pollPaymentStatus() {
    if (!state.active || state.terminal || state.polling) return;
    state.polling = true;
    try {
      const data = await apiRequest(
        `/payments/booking/${bookingId}/status`,
      );
      renderStatus(data);
      clearError();
    } catch (error) {
      showError(error.message, true);
    } finally {
      state.polling = false;
      if (state.active && !state.terminal) {
        state.pollTimeout = window.setTimeout(pollPaymentStatus, 5000);
      }
    }
  }

  async function loadPayment() {
    if (!Number.isSafeInteger(bookingId) || bookingId <= 0) {
      showError("Thiếu booking_id hợp lệ trong đường dẫn thanh toán.", false);
      ui.paymentCard.setAttribute("aria-busy", "false");
      return;
    }
    if (!getToken()) {
      showError("Vui lòng đăng nhập để xem và thanh toán đơn đặt xe này.", false);
      ui.paymentCard.setAttribute("aria-busy", "false");
      return;
    }

    clearError();
    ui.paymentCard.setAttribute("aria-busy", "true");
    try {
      const current = await apiRequest(
        `/payments/booking/${bookingId}/status`,
      );
      if (current.payment_status === "NOT_STARTED") {
        await createPayment();
        const fresh = await apiRequest(
          `/payments/booking/${bookingId}/status`,
        );
        renderStatus(fresh);
      } else {
        renderStatus(current);
      }
      ui.paymentCard.setAttribute("aria-busy", "false");
      if (!state.terminal) {
        state.pollTimeout = window.setTimeout(pollPaymentStatus, 5000);
      }
    } catch (error) {
      ui.paymentCard.setAttribute("aria-busy", "false");
      showError(error.message, true);
    }
  }

  async function cancelPayment() {
    if (state.terminal || !Number.isSafeInteger(bookingId)) return;
    if (!window.confirm("Bạn có chắc muốn hủy giao dịch và giải phóng đơn giữ chỗ?")) {
      return;
    }
    ui.cancelButton.disabled = true;
    try {
      await apiRequest(`/payments/booking/${bookingId}/cancel`, {
        method: "POST",
      });
      const data = await apiRequest(`/payments/booking/${bookingId}/status`);
      renderStatus(data);
      clearError();
    } catch (error) {
      ui.cancelButton.disabled = false;
      showError(error.message, true);
    }
  }

  async function copyField(event) {
    const button = event.currentTarget;
    const field = button.dataset.copyField;
    const element = field === "amountRaw" ? null : document.getElementById(field);
    const value =
      field === "amountRaw"
        ? state.amount
          ? String(Math.round(state.amount))
          : ""
        : element
          ? element.textContent.trim()
          : "";
    if (!value || value === "—") return;
    const original = button.textContent;
    try {
      await navigator.clipboard.writeText(value);
    } catch (_) {
      const textarea = document.createElement("textarea");
      textarea.value = value;
      textarea.setAttribute("readonly", "");
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      textarea.remove();
    }
    button.textContent = "✅ Đã copy";
    button.classList.add("copied");
    window.setTimeout(() => {
      button.textContent = original;
      button.classList.remove("copied");
    }, 1800);
  }

  ui.retryButton.addEventListener("click", loadPayment);
  ui.cancelButton.addEventListener("click", cancelPayment);
  document
    .querySelectorAll("[data-copy-field]")
    .forEach((button) => button.addEventListener("click", copyField));
  window.addEventListener("pagehide", () => {
    state.active = false;
    if (state.timer) window.clearInterval(state.timer);
    if (state.pollTimeout) window.clearTimeout(state.pollTimeout);
    if (state.requestController) state.requestController.abort();
  });

  loadPayment();
})();
