(function (global) {
  'use strict';

  function getErrorMessage(data, fallback) {
    if (data && typeof data.detail === 'string') return data.detail;
    if (data && Array.isArray(data.detail)) {
      return data.detail.map((item) => item.msg).filter(Boolean).join(' ') || fallback;
    }
    return (data && data.message) || fallback;
  }

  async function check(vehicleType, rentalStart) {
    const token = global.AuthRBAC ? global.AuthRBAC.getToken() : '';
    if (!token) {
      throw new Error('Vui lòng đăng nhập để kiểm tra điều kiện thuê xe.');
    }

    if (global.envConfigPromise) await global.envConfigPromise;
    const baseUrl = global.CONFIG && global.CONFIG.API_BASE_URL
      ? global.CONFIG.API_BASE_URL
      : 'http://127.0.0.1:8000/api';
    const response = await fetch(`${baseUrl.replace(/\/$/, '')}/bookings/check-eligibility`, {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify({ vehicle_type: vehicleType, rental_start: rentalStart || null })
    });

    const responseText = await response.text();
    let data = {};
    if (responseText) {
      try {
        data = JSON.parse(responseText);
      } catch (_) {
        throw new Error('Phản hồi kiểm tra điều kiện thuê không hợp lệ.');
      }
    }
    if (!response.ok) {
      throw new Error(getErrorMessage(data, `Máy chủ trả về lỗi ${response.status}.`));
    }
    if (typeof data.eligible !== 'boolean' || !Array.isArray(data.reasons)) {
      throw new Error('Phản hồi kiểm tra điều kiện thuê không đầy đủ.');
    }
    return data;
  }

  function clearMessage(element) {
    if (!element) return;
    element.replaceChildren();
    element.hidden = true;
  }

  function showReasons(element, reasons) {
    if (!element) return;
    element.replaceChildren();
    const title = document.createElement('strong');
    title.textContent = 'Bạn chưa đủ điều kiện thuê xe:';
    element.appendChild(title);

    const list = document.createElement('ul');
    (reasons.length ? reasons : ['Vui lòng kiểm tra lại hồ sơ thuê xe.']).forEach((reason) => {
      const item = document.createElement('li');
      item.textContent = reason;
      list.appendChild(item);
    });
    element.appendChild(list);
    element.hidden = false;
  }

  function showError(element, message) {
    if (!element) return;
    element.replaceChildren();
    element.textContent = message;
    element.hidden = false;
  }

  global.RideHubBookingEligibility = { check, clearMessage, showReasons, showError };
})(window);
