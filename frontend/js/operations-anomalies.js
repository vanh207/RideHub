(function () {
  'use strict';

  const rowsElement = document.getElementById('anomalyRows');
  const queueContent = document.getElementById('queueContent');
  const accessMessage = document.getElementById('accessMessage');
  const accessMessageText = document.getElementById('accessMessageText');
  const loginLink = document.getElementById('loginLink');
  const queueStatus = document.getElementById('queueStatus');
  const emptyState = document.getElementById('emptyState');
  const refreshButton = document.getElementById('refreshButton');
  const refundDialog = document.getElementById('refundDialog');
  const confirmRefundButton = document.getElementById('confirmRefundButton');
  const refundNote = document.getElementById('refundNote');
  const refundDialogSummary = document.getElementById('refundDialogSummary');

  let anomalies = [];
  let selectedAnomaly = null;
  let toastTimer = null;

  function getToken() {
    try {
      const keys = ['ridehub_auth_token', 'ridehub_token', 'token'];
      for (const key of keys) {
        const token = localStorage.getItem(key);
        if (token) return token;
      }
      const match = document.cookie.match(/(?:^|;\s*)(?:ridehub_token|access_token|token)=([^;]+)/);
      return match ? decodeURIComponent(match[1]) : '';
    } catch (_) {
      return '';
    }
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, (character) => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;'
    })[character]);
  }

  function formatMoney(value) {
    const amount = Number(value);
    return Number.isFinite(amount) ? `${amount.toLocaleString('vi-VN')} ₫` : '—';
  }

  function formatDate(value) {
    if (!value) return 'Không rõ thời gian';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? 'Không rõ thời gian' : date.toLocaleString('vi-VN');
  }

  function getApiBaseUrl() {
    const configured = window.CONFIG && window.CONFIG.API_BASE_URL;
    return (configured || 'http://127.0.0.1:8000/api').replace(/\/+$/, '');
  }

  async function apiRequest(path, options) {
    const token = getToken();
    const headers = { Accept: 'application/json' };
    if (options && options.body) headers['Content-Type'] = 'application/json';
    if (token) headers.Authorization = `Bearer ${token}`;

    let response;
    try {
      response = await fetch(`${getApiBaseUrl()}${path}`, {
        ...options,
        headers: { ...headers, ...(options && options.headers ? options.headers : {}) },
        cache: 'no-store'
      });
    } catch (_) {
      const error = new Error('Không thể kết nối máy chủ. Vui lòng kiểm tra Backend và thử lại.');
      error.status = 0;
      throw error;
    }

    let payload = {};
    try {
      payload = await response.json();
    } catch (_) {
      payload = {};
    }
    if (!response.ok) {
      const detail = payload.detail || payload.message;
      const message = typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map((item) => item.msg || 'Dữ liệu không hợp lệ').join('; ')
          : `Máy chủ trả về lỗi ${response.status}.`;
      const error = new Error(message);
      error.status = response.status;
      throw error;
    }
    return payload;
  }

  function showAccessMessage(message, needsLogin) {
    queueContent.hidden = true;
    accessMessage.hidden = false;
    accessMessageText.textContent = message;
    loginLink.hidden = !needsLogin;
    loginLink.href = './auth.html?next=' + encodeURIComponent(window.location.pathname);
  }

  function showToast(message, isError) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.classList.toggle('toast--error', Boolean(isError));
    toast.hidden = false;
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => { toast.hidden = true; }, 4500);
  }

  function anomalyLabel(type) {
    const labels = {
      AMOUNT_MISMATCH: 'Sai lệch số tiền',
      LATE_PAYMENT: 'Thanh toán đến muộn',
      PENDING_REFUND: 'Yêu cầu hoàn tiền đang chờ'
    };
    return labels[type] || type || 'Cần đối soát';
  }

  function refundState(anomaly) {
    if (anomaly.refund_status === 'SUCCESS' || anomaly.refund_status === 'REFUNDED') {
      return { label: 'Đã hoàn tiền', className: 'badge--complete', filter: 'completed' };
    }
    if (anomaly.can_refund) {
      return { label: 'Chờ xác nhận hoàn tiền', className: 'badge--pending', filter: 'pending' };
    }
    return { label: 'Cần kiểm tra', className: 'badge--review', filter: 'review' };
  }

  function renderStats() {
    document.getElementById('statTotal').textContent = anomalies.length;
    document.getElementById('statPending').textContent = anomalies.filter((item) => item.can_refund).length;
    document.getElementById('statCompleted').textContent = anomalies.filter((item) => {
      return item.refund_status === 'SUCCESS' || item.refund_status === 'REFUNDED';
    }).length;
    document.getElementById('statReview').textContent = anomalies.filter((item) => {
      return refundState(item).filter === 'review';
    }).length;
  }

  function renderRows() {
    const term = document.getElementById('searchInput').value.trim().toLocaleLowerCase('vi');
    const status = document.getElementById('statusFilter').value;
    const filtered = anomalies.filter((item) => {
      const searchable = [
        item.transaction_code,
        item.booking_id,
        item.customer_name,
        item.vehicle_name,
        item.vehicle_plate,
        item.reason,
        anomalyLabel(item.anomaly_type)
      ].join(' ').toLocaleLowerCase('vi');
      return (!term || searchable.includes(term)) && (status === 'all' || refundState(item).filter === status);
    });

    rowsElement.innerHTML = filtered.map((item) => {
      const state = refundState(item);
      const detail = [
        `Mã đơn: #${item.booking_id}`,
        item.provider_txn_id ? `Mã từ cổng: ${item.provider_txn_id}` : '',
        item.vehicle_plate ? `Biển số: ${item.vehicle_plate}` : '',
        item.refund_id ? `Mã hoàn tiền: #${item.refund_id}` : '',
        `Trạng thái giao dịch: ${item.transaction_status || '—'}`
      ].filter(Boolean).join(' • ');
      const action = item.can_refund
        ? `<button type="button" class="button button--danger refund-action" data-refund-id="${Number(item.refund_id)}">Xác nhận hoàn tiền</button>`
        : '<span class="secondary-cell">Không khả dụng</span>';

      return `
        <tr>
          <td>
            <span class="primary-cell">${escapeHtml(item.transaction_code || `Giao dịch #${item.id}`)}</span>
            <span class="secondary-cell">Đơn #${escapeHtml(item.booking_id)}</span>
          </td>
          <td>
            <span class="primary-cell">${escapeHtml(item.customer_name || 'Không rõ khách hàng')}</span>
            <span class="secondary-cell">${escapeHtml(item.vehicle_name || 'Không rõ phương tiện')}${item.vehicle_plate ? ` • ${escapeHtml(item.vehicle_plate)}` : ''}</span>
          </td>
          <td class="amount">${formatMoney(item.amount)}</td>
          <td>
            <span class="primary-cell">${escapeHtml(anomalyLabel(item.anomaly_type))}</span>
            <span class="secondary-cell">${escapeHtml(formatDate(item.occurred_at))}</span>
            <div class="reason">${escapeHtml(item.reason || 'Chưa có mô tả chi tiết.')}</div>
            <details class="details">
              <summary>Chi tiết giao dịch</summary>
              <div class="detail-text">${escapeHtml(detail)}</div>
            </details>
          </td>
          <td><span class="badge ${state.className}">${state.label}</span></td>
          <td>${action}</td>
        </tr>
      `;
    }).join('');
    emptyState.hidden = filtered.length !== 0;
    renderStats();
  }

  async function loadQueue(showSuccessToast) {
    if (!getToken()) {
      showAccessMessage('Bạn cần đăng nhập bằng tài khoản Admin hoặc Điều hành để xem hàng chờ.', true);
      return;
    }
    refreshButton.disabled = true;
    queueStatus.textContent = 'Đang tải hàng chờ giao dịch…';
    try {
      const payload = await apiRequest('/payments/operations/anomalies?limit=500');
      anomalies = Array.isArray(payload) ? payload : [];
      queueContent.hidden = false;
      accessMessage.hidden = true;
      document.getElementById('lastUpdated').textContent = `Cập nhật lúc ${formatDate(new Date().toISOString())}`;
      queueStatus.textContent = anomalies.length ? `${anomalies.length} giao dịch trong hàng chờ.` : '';
      renderRows();
      if (showSuccessToast) showToast('Đã cập nhật hàng chờ.', false);
    } catch (error) {
      if (error.status === 401) {
        showAccessMessage('Phiên đăng nhập không hợp lệ hoặc đã hết hạn. Vui lòng đăng nhập lại.', true);
      } else if (error.status === 403) {
        showAccessMessage('Tài khoản của bạn không có quyền truy cập hàng chờ giao dịch vận hành.', false);
      } else {
        queueContent.hidden = false;
        queueStatus.textContent = error.message;
        showToast(error.message, true);
      }
    } finally {
      refreshButton.disabled = false;
    }
  }

  function openRefundDialog(anomaly) {
    selectedAnomaly = anomaly;
    refundNote.value = '';
    refundDialogSummary.textContent =
      `Giao dịch ${anomaly.transaction_code} • Đơn #${anomaly.booking_id} • ${formatMoney(anomaly.amount)}. ` +
      'Thao tác sẽ gửi yêu cầu hoàn tiền tới Backend/cổng thanh toán.';
    refundDialog.showModal();
  }

  async function confirmRefund() {
    if (!selectedAnomaly || !selectedAnomaly.can_refund || confirmRefundButton.disabled) return;
    const anomaly = selectedAnomaly;
    confirmRefundButton.disabled = true;
    confirmRefundButton.textContent = 'Đang xử lý…';
    try {
      await apiRequest(`/payments/operations/refunds/${Number(anomaly.refund_id)}/confirm`, {
        method: 'POST',
        body: JSON.stringify({ reason: refundNote.value.trim() || null })
      });
      refundDialog.close();
      showToast(`Đã xác nhận hoàn tiền cho giao dịch ${anomaly.transaction_code}.`, false);
      await loadQueue(false);
    } catch (error) {
      if (error.status === 401) {
        refundDialog.close();
        showAccessMessage('Phiên đăng nhập không hợp lệ hoặc đã hết hạn. Vui lòng đăng nhập lại.', true);
      } else if (error.status === 403) {
        refundDialog.close();
        showAccessMessage('Tài khoản của bạn không có quyền xác nhận hoàn tiền.', false);
      } else {
        showToast(error.message, true);
        if (error.status === 409) await loadQueue(false);
      }
    } finally {
      confirmRefundButton.disabled = false;
      confirmRefundButton.textContent = 'Xác nhận hoàn tiền';
      selectedAnomaly = null;
    }
  }

  rowsElement.addEventListener('click', (event) => {
    const button = event.target.closest('[data-refund-id]');
    if (!button) return;
    const anomaly = anomalies.find((item) => Number(item.refund_id) === Number(button.dataset.refundId));
    if (anomaly) openRefundDialog(anomaly);
  });
  document.getElementById('searchInput').addEventListener('input', renderRows);
  document.getElementById('statusFilter').addEventListener('change', renderRows);
  refreshButton.addEventListener('click', () => loadQueue(true));
  document.getElementById('cancelRefundButton').addEventListener('click', () => refundDialog.close());
  confirmRefundButton.addEventListener('click', confirmRefund);

  Promise.resolve(window.envConfigPromise)
    .catch(() => undefined)
    .then(() => loadQueue(false));
})();
