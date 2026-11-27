(function () {
  "use strict";

  const form = document.getElementById("bookingForm");
  const draftSection = document.getElementById("checkoutDraftSection");
  const draftVehicleBadge = document.getElementById("draftVehicleBadge");
  const dismissDraftBtn = document.getElementById("dismissDraftBtn");
  const bookingCollateralWrap = document.getElementById("bookingCollateralWrap");
  const bookingCollateralInput = document.getElementById("bookingCollateralInfo");
  const vehicleSelect = document.getElementById("vehicleId");
  const startInput = document.getElementById("startTime");
  const endInput = document.getElementById("endTime");
  const submitButton = document.getElementById("submitBooking");
  const message = document.getElementById("message");
  const query = new URLSearchParams(window.location.search);
  let draft = {};

  if (!form) return;

  try {
    const rawDraft = localStorage.getItem("ridehub_checkout_draft");
    draft = rawDraft ? JSON.parse(rawDraft) : {};
  } catch (_) {
    draft = {};
  }

  function syncDraftUI() {
    const hasDraft = Boolean(draft && (draft.vehicle || draft.vehicleId || query.get("vehicle_id")));
    if (draftSection) draftSection.hidden = !hasDraft;
    if (draftVehicleBadge && draft.vehicle) {
      draftVehicleBadge.textContent = draft.vehicle;
    }
    const dtype = (draft.depositType === "VEHICLE_PLEDGE" || draft.depositType === "COMBINED")
      ? draft.depositType
      : "CASH";
    document.querySelectorAll('input[name="bookingDepositType"]').forEach((r) => {
      r.checked = r.value === dtype;
    });
    if (bookingCollateralWrap) bookingCollateralWrap.hidden = dtype === "CASH";
    if (bookingCollateralInput && draft.collateralInfo) {
      bookingCollateralInput.value = draft.collateralInfo;
    }
    if (submitButton) {
      submitButton.textContent = dtype === "VEHICLE_PLEDGE"
        ? "Gửi đơn thế chấp xe"
        : "Tạo đơn & Thanh toán cọc";
    }
  }

  document.querySelectorAll('input[name="bookingDepositType"]').forEach((r) => {
    r.addEventListener("change", () => {
      if (bookingCollateralWrap) bookingCollateralWrap.hidden = r.value === "CASH";
      if (submitButton) {
        submitButton.textContent = r.value === "VEHICLE_PLEDGE"
          ? "Gửi đơn thế chấp xe"
          : "Tạo đơn & Thanh toán cọc";
      }
    });
  });

  if (dismissDraftBtn) {
    dismissDraftBtn.addEventListener("click", () => {
      try { localStorage.removeItem("ridehub_checkout_draft"); } catch (_) {}
      draft = {};
      if (draftSection) draftSection.hidden = true;
    });
  }

  syncDraftUI();

  function localDateTime(value) {
    const pad = (part) => String(part).padStart(2, "0");
    return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(
      value.getDate(),
    )}T${pad(value.getHours())}:${pad(value.getMinutes())}`;
  }

  function setDefaultTimes() {
    const start = new Date();
    start.setDate(start.getDate() + 1);
    start.setHours(9, 0, 0, 0);
    const end = new Date(start);
    end.setDate(end.getDate() + 1);
    startInput.value = draft.startTime || localDateTime(start);
    endInput.value = draft.endTime || localDateTime(end);
  }

  function getApiBase() {
    const configured =
      window.CONFIG && typeof window.CONFIG.API_BASE_URL === "string"
        ? window.CONFIG.API_BASE_URL
        : "";
    if (configured) return configured.replace(/\/$/, "");
    return window.location.port === "8000"
      ? `${window.location.origin}/api`
      : "http://127.0.0.1:8000/api";
  }

  function getToken() {
    try {
      const localToken =
        localStorage.getItem("ridehub_auth_token") ||
        localStorage.getItem("ridehub_token") ||
        localStorage.getItem("token");
      if (localToken) return localToken;
      const cookie = document.cookie
        .split(";")
        .map((part) => part.trim())
        .find((part) =>
          /^(ridehub_token|access_token|token|ridehub_auth_token)=/.test(part),
        );
      return cookie
        ? decodeURIComponent(cookie.slice(cookie.indexOf("=") + 1))
        : "";
    } catch (_) {
      return "";
    }
  }

  async function fetchWithTimeout(url, options = {}) {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), 15000);
    try {
      return await fetch(url, { ...options, signal: controller.signal });
    } catch (error) {
      if (error.name === "AbortError") {
        throw new Error("Backend phản hồi quá lâu. Vui lòng thử lại.");
      }
      throw error;
    } finally {
      window.clearTimeout(timeoutId);
    }
  }

  function errorMessage(data, fallback) {
    const detail = data && (data.detail || data.message);
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail.map((item) => item.msg || "Dữ liệu không hợp lệ").join("\n");
    }
    return fallback;
  }

  async function loadAvailableVehicles() {
    vehicleSelect.disabled = true;
    submitButton.disabled = true;
    message.textContent = "Đang lấy danh sách xe từ backend…";

    const startTime = startInput.value;
    const endTime = endInput.value;
    const params = new URLSearchParams({ page: "1", page_size: "50" });
    if (startTime && endTime) {
      params.set("start_time", startTime);
      params.set("end_time", endTime);
    }

    try {
      const [searchResponse, activeResponse] = await Promise.all([
        fetchWithTimeout(
          `${getApiBase()}/vehicles/search?${params.toString()}`,
          { headers: { Accept: "application/json" }, credentials: "include" },
        ),
        fetchWithTimeout(`${getApiBase()}/vehicles?status=AVAILABLE`, {
          headers: { Accept: "application/json" },
          credentials: "include",
        }),
      ]);
      const [searchData, activeVehicles] = await Promise.all([
        searchResponse.json().catch(() => null),
        activeResponse.json().catch(() => null),
      ]);
      if (!searchResponse.ok) {
        throw new Error(
          errorMessage(searchData, `Backend trả lỗi ${searchResponse.status}.`),
        );
      }
      if (!activeResponse.ok) {
        throw new Error(
          errorMessage(
            activeVehicles,
            `Backend trả lỗi ${activeResponse.status}.`,
          ),
        );
      }
      if (!searchData || !Array.isArray(searchData.items)) {
        throw new Error("Backend trả về danh sách xe không hợp lệ.");
      }
      if (!Array.isArray(activeVehicles)) {
        throw new Error("Backend trả về trạng thái xe không hợp lệ.");
      }
      const activeIds = new Set(
        activeVehicles
          .filter(
            (vehicle) =>
              vehicle.is_active &&
              String(vehicle.current_status).toUpperCase() === "AVAILABLE",
          )
          .map((vehicle) => Number(vehicle.id)),
      );
      const availableItems = searchData.items.filter((vehicle) =>
        activeIds.has(Number(vehicle.id)),
      );

      vehicleSelect.replaceChildren();
      const placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.textContent = availableItems.length
        ? "Chọn xe"
        : "Không có xe khả dụng trong khoảng thời gian này";
      vehicleSelect.appendChild(placeholder);

      availableItems.forEach((vehicle) => {
        const option = document.createElement("option");
        option.value = String(vehicle.id);
        option.textContent = `${vehicle.brand} ${vehicle.model} — ${Number(
          vehicle.price_per_day,
        ).toLocaleString("vi-VN")}đ/ngày`;
        vehicleSelect.appendChild(option);
      });

      const requestedId = Number(query.get("vehicle_id"));
      const draftId = Number(draft.backendVehicleId || draft.vehicleId);
      const requestedName = String(draft.vehicle || "")
        .trim()
        .toLocaleLowerCase("vi");
      const matchingVehicle = availableItems.find((vehicle) => {
        const name = `${vehicle.brand} ${vehicle.model}`.trim().toLocaleLowerCase("vi");
        return requestedName && (name === requestedName || requestedName.includes(name));
      });
      const preferredId =
        Number.isSafeInteger(requestedId) && requestedId > 0
          ? requestedId
          : Number.isSafeInteger(draftId) && draftId > 0
            ? draftId
            : matchingVehicle && matchingVehicle.id;
      if (
        preferredId &&
        Array.from(vehicleSelect.options).some(
          (option) => option.value === String(preferredId),
        )
      ) {
        vehicleSelect.value = String(preferredId);
      } else if (availableItems.length === 1) {
        vehicleSelect.value = String(availableItems[0].id);
      }

      vehicleSelect.disabled = availableItems.length === 0;
      submitButton.disabled = availableItems.length === 0;
      message.textContent = availableItems.length
        ? `Tìm thấy ${availableItems.length} xe khả dụng. Giá và tiền cọc sẽ được tính lại ở backend.`
        : "Cần có xe đang hoạt động thuộc cửa hàng đã duyệt trong cơ sở dữ liệu. Kiểm tra MySQL và dữ liệu xe rồi thử lại.";
    } catch (error) {
      vehicleSelect.replaceChildren();
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "Không tải được danh sách xe";
      vehicleSelect.appendChild(option);
      message.textContent = `${error.message}\nKiểm tra backend tại http://127.0.0.1:8000/api/health.`;
    }
  }

  async function createBooking(event) {
    event.preventDefault();
    if (!getToken()) {
      message.textContent =
        "Bạn cần đăng nhập trước khi tạo đơn. Đăng nhập xong hãy mở lại trang này.";
      return;
    }

    const vehicleId = Number(vehicleSelect.value);
    if (!Number.isSafeInteger(vehicleId) || vehicleId <= 0) {
      message.textContent = "Hãy chọn một xe hợp lệ từ danh sách backend.";
      return;
    }
    if (!startInput.value || !endInput.value || endInput.value <= startInput.value) {
      message.textContent = "Thời gian nhận/trả xe không hợp lệ.";
      return;
    }

    const selectedRadio = document.querySelector('input[name="bookingDepositType"]:checked');
    const depositType = selectedRadio ? selectedRadio.value : "CASH";
    const needsPledge = depositType === "VEHICLE_PLEDGE" || depositType === "COMBINED";
    const collateralInfo = bookingCollateralInput ? bookingCollateralInput.value.trim() : "";
    if (needsPledge && !collateralInfo) {
      message.textContent = "Vui lòng nhập thông tin xe và giấy tờ thế chấp.";
      if (bookingCollateralInput) bookingCollateralInput.focus();
      return;
    }

    submitButton.disabled = true;
    submitButton.textContent = "Đang tạo đơn…";
    message.textContent = "";
    try {
      const token = getToken();
      const response = await fetchWithTimeout(
        `${getApiBase()}/bookings`,
        {
          method: "POST",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          credentials: "include",
          body: JSON.stringify({
            vehicle_id: vehicleId,
            start_time: startInput.value,
            end_time: endInput.value,
            deposit_type: depositType,
            collateral_info: needsPledge ? collateralInfo : null,
          }),
        },
      );
      const data = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(errorMessage(data, `Backend trả lỗi ${response.status}.`));
      }
      const bookingId = Number(data && data.id);
      if (!Number.isSafeInteger(bookingId) || bookingId <= 0) {
        throw new Error("Backend không trả về booking_id hợp lệ.");
      }
      try {
        localStorage.removeItem("ridehub_checkout_draft");
      } catch (_) {}

      if (depositType === "VEHICLE_PLEDGE") {
        if (window.showRideHubToast) {
          window.showRideHubToast("Đã gửi đơn thế chấp xe tới cửa hàng chờ duyệt!");
        }
        if (draftSection) draftSection.hidden = true;
        if (typeof window.reloadMyBookings === "function") {
          window.reloadMyBookings();
        }
        return;
      }

      window.location.assign(
        `payment-qr.html?booking_id=${encodeURIComponent(bookingId)}`,
      );
    } catch (error) {
      message.textContent = error.message;
      submitButton.disabled = false;
      submitButton.textContent = depositType === "VEHICLE_PLEDGE"
        ? "Gửi đơn thế chấp xe"
        : "Tạo đơn & Thanh toán cọc";
    }
  }

  setDefaultTimes();
  form.addEventListener("submit", createBooking);
  startInput.addEventListener("change", loadAvailableVehicles);
  endInput.addEventListener("change", loadAvailableVehicles);
  if (window.envConfigPromise) {
    window.envConfigPromise.then(loadAvailableVehicles).catch(loadAvailableVehicles);
  } else {
    loadAvailableVehicles();
  }
})();
