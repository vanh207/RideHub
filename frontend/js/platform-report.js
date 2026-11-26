/**
 * platform-report.js — TF1A397
 * Báo cáo toàn nền tảng RideHub: doanh thu, số đơn, hoàn tiền, bất thường.
 * Gọi GET /api/reports/platform?from_date=…&to_date=…  (admin/operator JWT).
 */
(function () {
  'use strict';

  /* ── DOM refs ─────────────────────────────────────────────────────────── */
  const accessMessage     = document.getElementById('accessMessage');
  const accessMessageText = document.getElementById('accessMessageText');
  const quickLoginBtn     = document.getElementById('quickLoginAdminBtn');
  const viewDemoBtn       = document.getElementById('viewDemoDataBtn');
  const reportContent     = document.getElementById('reportContent');
  const loadingState      = document.getElementById('loadingState');
  const errorState        = document.getElementById('errorState');
  const errorMessage      = document.getElementById('errorMessage');
  const retryButton       = document.getElementById('retryButton');
  const reportData        = document.getElementById('reportData');
  const refreshButton     = document.getElementById('refreshButton');
  const fromDateInput     = document.getElementById('fromDate');
  const toDateInput       = document.getElementById('toDate');
  const applyFilter       = document.getElementById('applyFilter');
  const periodLabel       = document.getElementById('periodLabel');
  const lastUpdated       = document.getElementById('lastUpdated');
  const toast             = document.getElementById('toast');
  const quickBtns         = document.querySelectorAll('.btn-quick');

  /* ── KPI elements ─────────────────────────────────────────────────────── */
  const kpi = {
    netAmount        : document.getElementById('kpiNetAmount'),
    grossAmount      : document.getElementById('kpiGrossAmount'),
    txnCount         : document.getElementById('kpiTxnCount'),
    refundAmount     : document.getElementById('kpiRefundAmount'),
    refundCount      : document.getElementById('kpiRefundCount'),
    pendingRefund    : document.getElementById('kpiPendingRefund'),
    pendingRefundCount: document.getElementById('kpiPendingRefundCount'),
    extraFee         : document.getElementById('kpiExtraFee'),
    extraFeeCount    : document.getElementById('kpiExtraFeeCount'),
    bookingTotal     : document.getElementById('kpiBookingTotal'),
    bookingPending   : document.getElementById('kpiBookingPending'),
    bookingBooked    : document.getElementById('kpiBookingBooked'),
    bookingCompleted : document.getElementById('kpiBookingCompleted'),
    bookingCancelled : document.getElementById('kpiBookingCancelled'),
    userTotal        : document.getElementById('kpiUserTotal'),
    userNew          : document.getElementById('kpiUserNew'),
    userActive       : document.getElementById('kpiUserActive'),
    vehicleActive    : document.getElementById('kpiVehicleActive'),
    vehicleTotal     : document.getElementById('kpiVehicleTotal'),
  };

  let toastTimer = null;

  /* ── Helpers ──────────────────────────────────────────────────────────── */
  function getApiBase() {
    const cfg = window.CONFIG && window.CONFIG.API_BASE_URL;
    return (cfg || 'http://127.0.0.1:8000/api').replace(/\/+$/, '');
  }

  function getToken() {
    try {
      const keys = ['ridehub_auth_token', 'ridehub_token', 'token', 'access_token'];
      for (const k of keys) {
        const v = localStorage.getItem(k);
        if (v) return v;
      }
      const m = document.cookie.match(/(?:^|;\s*)(?:ridehub_token|access_token|token)=([^;]+)/);
      return m ? decodeURIComponent(m[1]) : '';
    } catch (_) { return ''; }
  }

  /** VNĐ formatter */
  function fmt(value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return '—';
    return n.toLocaleString('vi-VN') + ' ₫';
  }

  /** integer formatter */
  function fmtInt(value) {
    const n = Number(value);
    return Number.isFinite(n) ? n.toLocaleString('vi-VN') : '—';
  }

  /** yyyy-MM-dd from Date */
  function dateStr(d) {
    return d.toISOString().slice(0, 10);
  }

  /** Show toast */
  function showToast(msg, duration = 3000) {
    clearTimeout(toastTimer);
    toast.textContent = msg;
    toast.hidden = false;
    toastTimer = setTimeout(() => { toast.hidden = true; }, duration);
  }

  /** Badge HTML for transaction status */
  function statusBadge(status) {
    const map = {
      SUCCESS : ['badge-success',  'Thành công'],
      PAID    : ['badge-success',  'Đã thanh toán'],
      PENDING : ['badge-pending',  'Chờ xử lý'],
      FAILED  : ['badge-failed',   'Thất bại'],
      REFUNDED: ['badge-refunded', 'Đã hoàn tiền'],
      CANCELLED:['badge-failed',   'Đã hủy'],
    };
    const [cls, label] = map[status] || ['badge-default', status];
    return `<span class="badge ${cls}">${label}</span>`;
  }

  /* ── Date range helpers ───────────────────────────────────────────────── */
  function setDateRange(days) {
    const to   = new Date();
    const from = new Date();
    from.setDate(to.getDate() - (days - 1));
    fromDateInput.value = dateStr(from);
    toDateInput.value   = dateStr(to);
    quickBtns.forEach(b => b.classList.toggle('is-active', Number(b.dataset.days) === days));
  }

  function getCurrentRange() {
    const today = dateStr(new Date());
    const from  = fromDateInput.value || today;
    const to    = toDateInput.value   || today;
    return { from, to };
  }

  /* ── Auth check ───────────────────────────────────────────────────────── */
  function showAccess(msg) {
    accessMessageText.textContent = msg;
    accessMessage.hidden = false;
    reportContent.hidden = true;
  }

  /* ── Demo data (offline fallback) ────────────────────────────────────── */
  function getDemoData() {
    return {
      period   : { from_date: '2026-10-27', to_date: '2026-11-25' },
      currency : 'VND',
      payments : {
        transaction_count    : 142,
        transactions_by_status: { SUCCESS: 118, PENDING: 14, FAILED: 7, REFUNDED: 3 },
        captured_count       : 118,
        captured_amount      : 59000000,
        completed_refund_amount: 1500000,
        net_collected_amount : 57500000,
      },
      refunds  : {
        refund_count     : 8,
        refunds_by_status: { SUCCESS: 3, PENDING: 5 },
        pending_count    : 5,
        pending_amount   : 2500000,
        completed_count  : 3,
        completed_amount : 1500000,
      },
      bookings : {
        booking_count    : 135,
        bookings_by_status: { PENDING: 12, BOOKED: 48, COMPLETED: 68, CANCELLED: 7 },
      },
      extra_fee_count  : 9,
      extra_fee_amount : 450000,
      platform : {
        user_count       : 328,
        active_user_count: 304,
        new_user_count   : 42,
        users_by_status  : { active: 304, suspended: 24 },
        vehicle_count    : 87,
        active_vehicle_count: 79,
        vehicles_by_status : { available: 79, maintenance: 8 },
      },
      anomalies: {
        amount_mismatch_count          : 2,
        late_payment_count             : 4,
        pending_refund_count           : 5,
        invalid_signature_webhook_count: 1,
        failed_webhook_count           : 3,
      },
    };
  }

  /* ── Render report ────────────────────────────────────────────────────── */
  function renderReport(data) {
    const p = data.payments;
    const r = data.refunds;
    const b = data.bookings;
    const pl = data.platform;
    const a = data.anomalies;
    const bs = b.bookings_by_status || {};

    /* KPI — Thanh toán */
    kpi.netAmount.textContent         = fmt(p.net_collected_amount);
    kpi.grossAmount.textContent       = fmt(p.captured_amount);
    kpi.txnCount.textContent          = `${fmtInt(p.captured_count)} giao dịch thành công`;
    kpi.refundAmount.textContent      = fmt(r.completed_amount);
    kpi.refundCount.textContent       = `${fmtInt(r.completed_count)} lần hoàn`;
    kpi.pendingRefund.textContent     = fmt(r.pending_amount);
    kpi.pendingRefundCount.textContent= `${fmtInt(r.pending_count)} yêu cầu chờ`;
    kpi.extraFee.textContent          = fmt(data.extra_fee_amount);
    kpi.extraFeeCount.textContent     = `${fmtInt(data.extra_fee_count)} lần phát sinh`;

    /* KPI — Đơn */
    kpi.bookingTotal.textContent     = fmtInt(b.booking_count);
    kpi.bookingPending.textContent   = fmtInt(bs.PENDING || 0);
    kpi.bookingBooked.textContent    = fmtInt(bs.BOOKED  || 0);
    kpi.bookingCompleted.textContent = fmtInt(bs.COMPLETED || 0);
    kpi.bookingCancelled.textContent = fmtInt(bs.CANCELLED || 0);

    /* KPI — Người dùng & xe */
    kpi.userTotal.textContent        = fmtInt(pl.user_count);
    kpi.userNew.textContent          = `${fmtInt(pl.new_user_count)} người dùng mới kỳ này`;
    kpi.userActive.textContent       = fmtInt(pl.active_user_count);
    kpi.vehicleActive.textContent    = fmtInt(pl.active_vehicle_count);
    kpi.vehicleTotal.textContent     = `/ ${fmtInt(pl.vehicle_count)} tổng xe`;

    /* Bảng phân tích giao dịch */
    const tbody = document.getElementById('txnBreakdownRows');
    const txnTotal = p.transaction_count || 1;
    const statusRows = Object.entries(p.transactions_by_status || {});
    if (statusRows.length === 0) {
      tbody.innerHTML = '<tr><td colspan="3" class="table-empty">Không có dữ liệu giao dịch.</td></tr>';
    } else {
      tbody.innerHTML = statusRows.map(([status, count]) => {
        const pct = txnTotal > 0 ? ((count / txnTotal) * 100).toFixed(1) : '0.0';
        return `
          <tr>
            <td>${statusBadge(status)}</td>
            <td class="text-right"><strong>${fmtInt(count)}</strong></td>
            <td class="text-right">${pct}%</td>
          </tr>`;
      }).join('');
    }

    /* Cảnh báo bất thường */
    const anomalyGrid = document.getElementById('anomalyGrid');
    const anomalyItems = [
      { label: 'Số tiền không khớp',         value: a.amount_mismatch_count,           critical: a.amount_mismatch_count > 0 },
      { label: 'Thanh toán trễ hạn',          value: a.late_payment_count,              critical: a.late_payment_count > 5 },
      { label: 'Hoàn tiền chờ duyệt',         value: a.pending_refund_count,            critical: a.pending_refund_count > 10 },
      { label: 'Webhook chữ ký sai',           value: a.invalid_signature_webhook_count, critical: a.invalid_signature_webhook_count > 0 },
      { label: 'Webhook thất bại',             value: a.failed_webhook_count,            critical: a.failed_webhook_count > 5 },
    ];
    anomalyGrid.innerHTML = anomalyItems.map(({ label, value, critical }) => {
      const cls = value === 0 ? 'is-ok' : (critical ? 'is-critical' : '');
      const valCls = value === 0 ? '' : (critical ? 'is-critical' : 'is-warn');
      return `
        <div class="anomaly-card ${cls}">
          <div class="anomaly-label">${label}</div>
          <div class="anomaly-value ${valCls}">${fmtInt(value)}</div>
        </div>`;
    }).join('');

    /* Kỳ báo cáo & thời gian cập nhật */
    const { from_date, to_date } = data.period;
    periodLabel.textContent = `Kỳ báo cáo: ${from_date} → ${to_date}`;
    lastUpdated.textContent = `Cập nhật lúc: ${new Date().toLocaleString('vi-VN')}`;
  }

  /* ── Fetch data ───────────────────────────────────────────────────────── */
  async function loadReport() {
    const { from, to } = getCurrentRange();

    // Show loading
    loadingState.hidden = false;
    errorState.hidden   = true;
    reportData.hidden   = true;

    const token = getToken();
    if (!token) {
      showAccess('Bạn cần đăng nhập tài khoản Admin hoặc Operator để xem báo cáo toàn nền tảng.');
      loadingState.hidden = true;
      return;
    }

    reportContent.hidden = false;
    accessMessage.hidden = true;

    try {
      const url = `${getApiBase()}/reports/platform?from_date=${from}&to_date=${to}`;
      const res = await fetch(url, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (res.status === 401 || res.status === 403) {
        loadingState.hidden = true;
        showAccess('Phiên đăng nhập đã hết hạn hoặc tài khoản không đủ quyền Admin/Operator.');
        return;
      }

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Lỗi API (HTTP ${res.status})`);
      }

      const data = await res.json();
      loadingState.hidden = true;
      reportData.hidden   = false;
      renderReport(data);

    } catch (err) {
      loadingState.hidden = true;
      errorMessage.textContent = `Không thể tải báo cáo: ${err.message || 'Lỗi kết nối backend.'}`;
      errorState.hidden = false;
    }
  }

  /* ── Demo mode ────────────────────────────────────────────────────────── */
  function loadDemoReport() {
    reportContent.hidden = false;
    accessMessage.hidden = true;
    loadingState.hidden  = false;
    errorState.hidden    = true;
    reportData.hidden    = true;

    setTimeout(() => {
      loadingState.hidden = false;
      const demo = getDemoData();
      loadingState.hidden = true;
      reportData.hidden   = false;
      renderReport(demo);
      showToast('Đang hiển thị dữ liệu mẫu (Demo). Đăng nhập Admin để xem dữ liệu thực.');
    }, 600);
  }

  /* ── Event listeners ──────────────────────────────────────────────────── */
  refreshButton.addEventListener('click', () => {
    showToast('Đang làm mới báo cáo…');
    loadReport();
  });

  retryButton.addEventListener('click', loadReport);

  applyFilter.addEventListener('click', loadReport);

  quickBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      setDateRange(Number(btn.dataset.days));
      loadReport();
    });
  });

  quickLoginBtn.addEventListener('click', () => {
    showToast('Chức năng đăng nhập nhanh Demo — dùng token admin mẫu.');
    // Nếu có token demo, set vào localStorage
    const demoToken = window.CONFIG && window.CONFIG.DEMO_ADMIN_TOKEN;
    if (demoToken) {
      localStorage.setItem('ridehub_auth_token', demoToken);
      loadReport();
    } else {
      loadDemoReport();
    }
  });

  viewDemoBtn.addEventListener('click', loadDemoReport);

  /* ── Init ─────────────────────────────────────────────────────────────── */
  (function init() {
    // Set default: 30 ngày gần nhất
    setDateRange(30);

    const token = getToken();
    if (!token) {
      showAccess('Bạn cần đăng nhập tài khoản Admin hoặc Operator để xem báo cáo toàn nền tảng.');
    } else {
      reportContent.hidden = false;
      accessMessage.hidden = true;
      loadReport();
    }
  })();

})();
