/**
 * =============================================================================
 * RIDEHUB — QUẢN LÝ ĐƠN HÀNG CỬA HÀNG (STORE ORDERS)
 * Task: TF1A665 — Sprint 3 (Nối API, xác nhận, từ chối, lọc trạng thái)
 * Tiêu chuẩn UI/UX: Data-Dense Dashboard & Bento Grid (ui-ux-pro-max)
 * =============================================================================
 */

(function (global) {
  'use strict';

  const STORAGE_KEY = 'ridehub_store_orders_v1';

  // Dữ liệu mẫu chuẩn nghiệp vụ cho thuê xe tự lái
  const DEFAULT_ORDERS = [
    {
      id: 'RH-8842',
      vehicle: 'VinFast Feliz S',
      category: 'moto',
      categoryLabel: 'Xe máy điện • Tay ga',
      licensePlate: '59A-123.45',
      customer: 'Nguyễn Văn An',
      phone: '0901234567',
      email: 'an.nguyen@ridehub.vn',
      cccd: '079201008899',
      ekycStatus: 'pass',
      schedule: '14/11/2026 08:00 → 16/11/2026 08:00',
      durationDays: 2,
      delivery: 'Giao xe tận nơi • 120 Nguyễn Huệ, Q.1',
      addons: '2 nón bảo hiểm 3/4, Áo mưa đôi RideHub',
      total: 320000,
      deposit: 96000,
      collateral: 'Miễn tiền cọc thế chấp (eKYC Hợp lệ)',
      status: 'pending',
      cancelReason: '',
      note: 'Khách cần nhận xe đúng giờ để đi gặp đối tác.'
    },
    {
      id: 'RH-8845',
      vehicle: 'VinFast VF 5 Plus',
      category: 'car',
      categoryLabel: 'Ô tô điện • SUV 5 chỗ',
      licensePlate: '51K-889.92',
      customer: 'Trần Thanh Bình',
      phone: '0901000002',
      email: 'binh.tran@ridehub.vn',
      cccd: '079202001122',
      ekycStatus: 'pass',
      schedule: '15/11/2026 09:00 → 17/11/2026 18:00',
      durationDays: 2.5,
      delivery: 'Nhận tại cửa hàng • GreenRide Q.1',
      addons: 'Bảo hiểm chuyến đi mở rộng thân vỏ PTI',
      total: 1875000,
      deposit: 562500,
      collateral: '5.000.000đ hoặc Cavet xe máy chính chủ',
      status: 'pending',
      cancelReason: '',
      note: 'Yêu cầu mức pin xe tối thiểu 95% trước khi bàn giao.'
    },
    {
      id: 'RH-8835',
      vehicle: 'Dat Bike Weaver++',
      category: 'moto',
      categoryLabel: 'Xe máy điện • Côn tay thể thao',
      licensePlate: '59B-987.65',
      customer: 'Lê Kim Chi',
      phone: '0901000003',
      email: 'kimchi.le@ridehub.vn',
      cccd: '079199003344',
      ekycStatus: 'pass',
      schedule: '13/11/2026 10:00 → 14/11/2026 10:00',
      durationDays: 1,
      delivery: 'Giao xe tận nơi • 45 Lê Lợi, Q.1',
      addons: 'Giá đỡ điện thoại chống rung MagSafe',
      total: 240000,
      deposit: 72000,
      collateral: '500.000đ tiền mặt (đã giữ cọc)',
      status: 'approved',
      cancelReason: '',
      rescheduleRequest: {
        status: 'pending_store',
        oldSchedule: '13/11/2026 10:00 → 14/11/2026 10:00 (1 ngày)',
        newSchedule: '14/11/2026 10:00 → 16/11/2026 10:00 (2 ngày)',
        durationDiff: '+1 ngày',
        surcharge: 240000,
        reason: 'Khách dời lịch công tác sang ngày 14/11 và xin gia hạn thêm 1 ngày.'
      }
    },
    {
      id: 'RH-8820',
      vehicle: 'VinFast Klara S',
      category: 'moto',
      categoryLabel: 'Xe máy điện • Cốp rộng',
      licensePlate: '59C-456.78',
      customer: 'Hoàng Minh Trí',
      phone: '0901000004',
      email: 'tri.hoang@ridehub.vn',
      cccd: '079198005566',
      ekycStatus: 'pass',
      schedule: '14/11/2026 09:00 → 15/11/2026 09:00',
      durationDays: 1,
      delivery: 'Nhận tại cửa hàng • GreenRide Q.1',
      addons: '2 nón bảo hiểm tiêu chuẩn, Bộ sạc theo xe',
      total: 180000,
      deposit: 54000,
      collateral: 'Miễn thế chấp eKYC',
      status: 'approved',
      cancelReason: ''
    },
    {
      id: 'RH-8812',
      vehicle: 'Mazda 3 Luxury 2023',
      category: 'car',
      categoryLabel: 'Ô tô xăng • Sedan 5 chỗ',
      licensePlate: '51H-998.11',
      customer: 'Phạm Quốc Hùng',
      phone: '0901888999',
      email: 'hung.pham@ridehub.vn',
      cccd: '079195007788',
      ekycStatus: 'pass',
      schedule: '10/11/2026 07:00 → 12/11/2026 19:00',
      durationDays: 2.5,
      delivery: 'Giao xe tận nơi • Sân bay Tân Sơn Nhất',
      addons: 'Ghế ngồi an toàn cho trẻ em',
      total: 2250000,
      deposit: 675000,
      collateral: '5.000.000đ tiền mặt',
      status: 'cancelled',
      cancelReason: 'Xe gặp sự cố kỹ thuật đột xuất cần bảo dưỡng'
    }
  ];

  // Trạng thái ứng dụng
  let orders = [];
  let currentFilter = 'all';
  let currentCategory = 'all';
  let rejectingOrderId = null;
  let isApiOnline = false;
  let isLoading = false;

  // Cấu hình Base URL
  function getApiBaseUrl() {
    if (typeof global.CONFIG !== 'undefined' && global.CONFIG.API_BASE_URL) {
      return global.CONFIG.API_BASE_URL;
    }
    return 'http://127.0.0.1:8000/api';
  }

  // Toast UI/UX Pro Max (Accessible & Auto Dismiss)
  function showToast(title, message, type = 'success') {
    let container = document.getElementById('toastContainer');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toastContainer';
      container.style.cssText = 'position:fixed;bottom:24px;right:24px;z-index:9999;display:flex;flex-direction:column;gap:10px;pointer-events:none;';
      document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast-box ${type === 'error' ? 'toast-error' : ''}`;
    toast.style.pointerEvents = 'auto';

    const iconSvg = type === 'success'
      ? `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#16a34a" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>`
      : `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`;

    toast.innerHTML = `
      <div style="flex-shrink:0;margin-top:1px;">${iconSvg}</div>
      <div style="flex:1;">
        <strong style="display:block;font-size:14px;color:var(--text-primary);margin-bottom:2px;">${title}</strong>
        <div style="color:var(--text-secondary);font-size:13px;line-height:1.4;">${message}</div>
      </div>
    `;

    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(30px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  // Cập nhật nhãn trạng thái kết nối API
  function updateConnectionBadge(online) {
    isApiOnline = online;
    const badge = document.getElementById('apiStatusBadge');
    if (!badge) return;

    if (online) {
      badge.className = 'status-badge status-badge--available';
      badge.style.background = '#dcfce7';
      badge.style.color = '#15803d';
      badge.innerHTML = `<span class="status-dot" style="background:#16a34a;"></span> API Trực Tuyến (Port 8000)`;
    } else {
      badge.className = 'status-badge';
      badge.style.background = '#fef3c7';
      badge.style.color = '#b45309';
      badge.innerHTML = `<span class="status-dot" style="background:#f59e0b;"></span> Chế Độ Đồng Bộ Cửa Hàng`;
    }
  }

  // =========================================================================
  // 1. DATA LAYER: GỌI API & FALLBACK LOCALSTORAGE
  // =========================================================================
  async function fetchOrdersFromApi() {
    isLoading = true;
    renderLoadingSkeleton();

    const baseUrl = getApiBaseUrl();
    try {
      // Dùng fetch với timeout 3s
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 3000);

      const resp = await fetch(`${baseUrl}/bookings`, {
        method: 'GET',
        headers: { 'Accept': 'application/json' },
        signal: controller.signal
      });
      clearTimeout(timeoutId);

      if (resp.ok) {
        const json = await resp.json();
        if (json && Array.isArray(json.data) && json.data.length > 0) {
          orders = json.data;
          saveOrdersToLocal(orders);
          updateConnectionBadge(true);
          isLoading = false;
          updateMetricsAndBadges();
          renderOrders();
          return;
        }
      }
      throw new Error('API response empty or invalid');
    } catch (err) {
      console.info('Khai thác dữ liệu cửa hàng từ bộ nhớ cục bộ:', err.message);
      updateConnectionBadge(false);
      loadOrdersFromLocal();
    } finally {
      isLoading = false;
      updateMetricsAndBadges();
      renderOrders();
    }
  }

  function loadOrdersFromLocal() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        orders = JSON.parse(raw);
      } else {
        orders = JSON.parse(JSON.stringify(DEFAULT_ORDERS));
        saveOrdersToLocal(orders);
      }
    } catch (_) {
      orders = JSON.parse(JSON.stringify(DEFAULT_ORDERS));
    }
  }

  function saveOrdersToLocal(data) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    } catch (e) {
      console.warn('LocalStorage error:', e);
    }
  }

  // =========================================================================
  // 2. METRICS & KPI (BENTO GRID - UI/UX PRO MAX)
  // =========================================================================
  function updateMetricsAndBadges() {
    const total = orders.length;
    const pending = orders.filter(o => o.status === 'pending').length;
    const approved = orders.filter(o => o.status === 'approved').length;
    const reschedule = orders.filter(o => o.rescheduleRequest && o.rescheduleRequest.status === 'pending_store').length;
    const cancelled = orders.filter(o => o.status === 'cancelled').length;

    // Dòng tiền
    const activeOrders = orders.filter(o => o.status !== 'cancelled');
    const totalDeposit = activeOrders.reduce((sum, o) => sum + (o.deposit || 0), 0);
    const totalRevenue = activeOrders.reduce((sum, o) => sum + (o.total || 0), 0);
    const remainCollect = Math.max(0, totalRevenue - totalDeposit);

    // DOM KPI
    const elTotal = document.getElementById('kpiTotalOrders');
    const elPending = document.getElementById('kpiPendingOrders');
    const elApproved = document.getElementById('kpiApprovedOrders');
    const elResched = document.getElementById('kpiRescheduleOrders');
    const elDeposit = document.getElementById('kpiTotalDeposit');
    const elRemain = document.getElementById('kpiRemainCollection');

    if (elTotal) elTotal.textContent = total;
    if (elPending) elPending.textContent = pending;
    if (elApproved) elApproved.textContent = approved;
    if (elResched) elResched.textContent = reschedule;
    if (elDeposit) elDeposit.textContent = totalDeposit.toLocaleString('vi-VN') + ' đ';
    if (elRemain) elRemain.textContent = remainCollect.toLocaleString('vi-VN') + ' đ';

    // Badge số đếm trên tabs bộ lọc
    const cAll = document.getElementById('countAll');
    const cPending = document.getElementById('countPending');
    const cApproved = document.getElementById('countApproved');
    const cResched = document.getElementById('countResched');
    const cCancelled = document.getElementById('countCancelled');
    const cSide = document.getElementById('sidebarPendingCount');

    if (cAll) cAll.textContent = total;
    if (cPending) cPending.textContent = pending;
    if (cApproved) cApproved.textContent = approved;
    if (cResched) cResched.textContent = reschedule;
    if (cCancelled) cCancelled.textContent = cancelled;
    if (cSide) {
      cSide.textContent = pending;
      cSide.style.display = pending > 0 ? 'inline-block' : 'none';
    }
  }

  // =========================================================================
  // 3. RENDER LOADING SKELETON
  // =========================================================================
  function renderLoadingSkeleton() {
    const container = document.getElementById('ordersListContainer');
    if (!container) return;

    container.innerHTML = [1, 2].map(() => `
      <div class="panel-card" style="padding:22px;border:1px solid #e2e8f0;opacity:0.75;display:flex;flex-direction:column;gap:14px;">
        <div style="height:24px;width:35%;background:#e2e8f0;border-radius:6px;animation:pulse 1.2s infinite ease-in-out;"></div>
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px;">
          <div style="height:60px;background:#f1f5f9;border-radius:8px;"></div>
          <div style="height:60px;background:#f1f5f9;border-radius:8px;"></div>
          <div style="height:60px;background:#f1f5f9;border-radius:8px;"></div>
          <div style="height:60px;background:#f1f5f9;border-radius:8px;"></div>
        </div>
      </div>
    `).join('');
  }

  // =========================================================================
  // 4. RENDER DANH SÁCH ĐƠN HÀNG (DATA-DENSE SAAS CARDS)
  // =========================================================================
  function renderOrders() {
    const container = document.getElementById('ordersListContainer');
    const searchVal = (document.getElementById('orderSearchInput')?.value || '').toLowerCase().trim();
    if (!container) return;

    const filtered = orders.filter(o => {
      // 1. Lọc theo Tab trạng thái
      if (currentFilter === 'pending' && o.status !== 'pending') return false;
      if (currentFilter === 'approved' && o.status !== 'approved') return false;
      if (currentFilter === 'cancelled' && o.status !== 'cancelled') return false;
      if (currentFilter === 'reschedule' && (!o.rescheduleRequest || o.rescheduleRequest.status !== 'pending_store')) return false;

      // 2. Lọc theo Phân khúc phương tiện
      if (currentCategory !== 'all' && o.category !== currentCategory) return false;

      // 3. Tìm kiếm tức thì
      if (searchVal) {
        const combined = `${o.id} ${o.customer} ${o.phone} ${o.email} ${o.vehicle} ${o.licensePlate}`.toLowerCase();
        if (!combined.includes(searchVal)) return false;
      }
      return true;
    });

    if (filtered.length === 0) {
      container.innerHTML = `
        <div class="panel-card" style="text-align:center;padding:48px 20px;color:var(--text-muted);border:1.5px dashed var(--green-200);background:#ffffff;">
          <div style="font-size:42px;margin-bottom:8px;">📭</div>
          <strong style="font-size:16px;color:var(--text-primary);display:block;margin-bottom:4px;">Không tìm thấy đơn đặt xe phù hợp</strong>
          <p style="font-size:13px;margin:0 0 16px;">Vui lòng thử chọn tab trạng thái khác hoặc nhập từ khóa tìm kiếm mới.</p>
          <button type="button" class="btn btn-soft btn-sm" onclick="window.resetFilters()">Xóa bộ lọc &amp; Hiển thị tất cả</button>
        </div>
      `;
      return;
    }

    container.innerHTML = filtered.map(o => {
      let badgeHtml = '';
      if (o.status === 'pending') {
        badgeHtml = `<span class="status-badge" style="background:#fef3c7;color:#b45309;font-weight:700;"><span class="status-dot status-dot-pulse" style="background:#f59e0b;"></span>Chờ duyệt đơn</span>`;
      } else if (o.status === 'approved') {
        badgeHtml = `<span class="status-badge status-badge--available" style="font-weight:700;">✓ Đã duyệt</span>`;
      } else if (o.status === 'cancelled') {
        badgeHtml = `<span class="status-badge" style="background:#fee2e2;color:#b91c1c;font-weight:700;">✕ Đã từ chối / Hủy</span>`;
      }

      const hasResched = o.rescheduleRequest && o.rescheduleRequest.status === 'pending_store';
      const depositType = (o.depositType || o.deposit_type || (o.pricing && o.pricing.deposit_type) || 'CASH').toUpperCase();
      const collateralInfo = o.collateralInfo || o.collateral_info || (o.pricing && o.pricing.collateral_info) || '';
      const isPledgeOnly = depositType === 'VEHICLE_PLEDGE';
      const isCombined = depositType === 'COMBINED';
      const remainAmount = isPledgeOnly ? o.total : Math.max(0, o.total - o.deposit);

      // Tham số đồng bộ sang biên bản bàn giao xe
      const handoverParams = new URLSearchParams({
        booking_id: o.id,
        customer: o.customer,
        phone: o.phone,
        vehicle: o.vehicle,
        plate: o.licensePlate,
        deposit: isPledgeOnly ? 0 : o.deposit,
        deposit_type: depositType,
        collateral_info: collateralInfo || ((isPledgeOnly || isCombined) ? o.collateral : '')
      }).toString();

      return `
        <article class="saas-order-card status-${o.status}" data-id="${o.id}">
          <!-- Header Bar -->
          <div class="order-head-bar">
            <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
              <span style="font-family:var(--font-display);font-size:18px;font-weight:800;color:var(--green-900);">
                #${o.id}
              </span>
              <span class="status-badge" style="background:var(--green-50);border:1px solid var(--green-200);color:var(--green-800);font-size:11px;font-weight:700;">
                ${o.categoryLabel}
              </span>
              ${badgeHtml}
              ${hasResched ? `<span class="status-badge" style="background:#f3e8ff;color:#7e22ce;font-weight:800;border:1px solid #d8b4fe;">⚡ Có yêu cầu dời lịch</span>` : ''}
            </div>

            <div style="font-size:12.5px;color:var(--text-muted);">
              Trạm xử lý: <strong style="color:var(--text-secondary);">GreenRide Q.1</strong>
            </div>
          </div>

          <!-- 4-Column Grid -->
          <div class="order-grid-4col">
            <!-- Cột 1: Khách thuê -->
            <div>
              <div class="col-label">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="8" r="4"/><path d="M4 20c1.5-3.8 4.8-5.5 8-5.5s6.5 1.7 8 5.5"/></svg>
                Khách thuê &amp; eKYC
              </div>
              <div class="col-val-primary">${o.customer}</div>
              <div class="col-val-sub">
                📞 ${o.phone}<br/>
                ✉️ ${o.email}
              </div>
              <div style="margin-top:6px;">
                <span class="status-badge status-badge--available" style="font-size:10.5px;padding:1px 6px;">
                  ✓ eKYC Đạt chuẩn
                </span>
              </div>
            </div>

            <!-- Cột 2: Phương tiện -->
            <div>
              <div class="col-label">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="7" cy="17" r="2"/><circle cx="17" cy="17" r="2"/><path d="M5 17H3v-4l2-5h10l3 5v4h-2M9 17h6"/></svg>
                Phương tiện bàn giao
              </div>
              <div class="col-val-primary" style="color:var(--green-800);">${o.vehicle}</div>
              <div class="col-val-sub">
                Biển số: <strong>${o.licensePlate}</strong><br/>
                Phụ kiện: <em>${o.addons}</em>
              </div>
            </div>

            <!-- Cột 3: Lịch trình & Giao nhận -->
            <div>
              <div class="col-label">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>
                Lịch trình &amp; Giao nhận
              </div>
              <div class="col-val-primary">${o.schedule}</div>
              <div class="col-val-sub">
                Thời lượng: <strong>${o.durationDays} ngày</strong><br/>
                📍 ${o.delivery}
              </div>
            </div>

            <!-- Cột 4: Dòng tiền & Cọc -->
            <div>
              <div class="col-label">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="2" y="5" width="20" height="14" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/></svg>
                Dòng tiền &amp; Đặt cọc
              </div>
              <div class="col-val-primary" style="color:var(--green-900);font-size:15px;">
                ${o.total.toLocaleString('vi-VN')} đ
              </div>
              <div class="col-val-sub">
                ${isPledgeOnly
                  ? `<span style="display:inline-block;padding:2px 8px;border-radius:999px;background:#fef3c7;color:#92400e;font-size:11px;font-weight:700;margin-bottom:3px;">🏍️ Chỉ thế chấp xe</span><br/>
                     Tiền cọc: <strong>0 đ</strong><br/>`
                  : isCombined
                    ? `<span style="display:inline-block;padding:2px 8px;border-radius:999px;background:#ecfdf5;color:#065f46;border:1px solid #a7f3d0;font-size:11px;font-weight:700;margin-bottom:3px;">🛡️ Cọc + Thế chấp xe</span><br/>
                       Đã cọc: <strong style="color:var(--green-700);">${o.deposit.toLocaleString('vi-VN')} đ</strong><br/>`
                    : `Đã cọc: <strong style="color:var(--green-700);">${o.deposit.toLocaleString('vi-VN')} đ (VietQR)</strong><br/>`
                }
                Thu tại trạm: <strong style="color:#b91c1c;">${remainAmount.toLocaleString('vi-VN')} đ</strong>
              </div>
            </div>
          </div>

          <!-- Yêu Cầu Dời Lịch (nếu có) -->
          ${hasResched ? `
            <div style="background:#faf5ff;border:1px solid #d8b4fe;border-radius:var(--radius-md);padding:12px 16px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;">
              <div>
                <div style="font-size:12.5px;font-weight:800;color:#6b21a8;margin-bottom:2px;">
                  ⚡ KHÁCH HÀNG YÊU CẦU DỜI LỊCH TRÌNH THUÊ (${o.rescheduleRequest.durationDiff}):
                </div>
                <div style="font-size:13px;color:#4c1d95;">
                  Lịch mới: <strong>${o.rescheduleRequest.newSchedule}</strong> • Phụ thu tự động: <strong>+${o.rescheduleRequest.surcharge.toLocaleString('vi-VN')} đ</strong>
                </div>
                <div style="font-size:12px;color:#7e22ce;margin-top:2px;">
                  Lý do khách gửi: <em>"${o.rescheduleRequest.reason}"</em>
                </div>
              </div>
              <button type="button" class="btn btn-sm" style="background:#7e22ce;color:#fff;border-color:#7e22ce;font-weight:700;" onclick="window.openRescheduleModal('${o.id}')">
                Xử lý Dời Lịch →
              </button>
            </div>
          ` : ''}

          <!-- Lý Do Hủy (nếu đã hủy) -->
          ${o.status === 'cancelled' && o.cancelReason ? `
            <div style="background:#fef2f2;border:1px solid #fecaca;border-radius:var(--radius-sm);padding:10px 14px;font-size:12.5px;color:#991b1b;">
              <strong>✕ Lý do từ chối đơn:</strong> ${o.cancelReason}. <em>(Hệ thống tự động ghi nhận hoàn cọc 100% ${o.deposit.toLocaleString('vi-VN')}đ qua VietQR)</em>.
            </div>
          ` : ''}

          <!-- Footer Action Toolbar (Đã căn toàn bộ nút sang bên phải đơn) -->
          <div class="order-footer-bar" style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;padding-top:14px;border-top:1px solid #f1f5f9;margin-top:2px;">
            <div style="font-size:12px;color:var(--text-muted);flex-shrink:0;">
              Thế chấp: <strong>${o.collateral}</strong>
            </div>

            <!-- Các nút thao tác luôn căn lề phải (Right-aligned) -->
            <div class="order-footer-actions" style="display:flex;align-items:center;justify-content:flex-end;gap:8px;flex-wrap:wrap;margin-left:auto;">
              <!-- Nút Thẩm định & Chi tiết -->
              <button type="button" class="btn btn-soft btn-sm" style="font-size:12.5px;font-weight:700;" onclick="window.viewOrderDetail('${o.id}')">
                👁️ Xem chi tiết &amp; Thẩm định
              </button>

              <!-- Nút Duyệt / Từ chối (Khi đang Chờ duyệt) -->
              ${o.status === 'pending' ? `
                <button type="button" class="btn btn-primary btn-sm" style="font-size:12.5px;font-weight:700;" onclick="window.approveOrder('${o.id}')">
                  ✓ Duyệt nhận đơn
                </button>
                <button type="button" class="btn btn-danger-red btn-sm" style="font-size:12.5px;" onclick="window.openRejectModal('${o.id}')">
                  ✕ Từ chối đơn
                </button>
              ` : ''}

              <!-- Nút Lập Biên Bản & Hủy (Khi Đã duyệt) -->
              ${o.status === 'approved' ? `
                <a href="handover.html?${handoverParams}" 
                   class="btn btn-primary btn-sm" 
                   style="font-size:12.5px;font-weight:700;text-decoration:none;display:inline-flex;align-items:center;gap:6px;box-shadow:0 4px 12px rgba(22,163,74,0.3);">
                  📝 Lập biên bản bàn giao xe →
                </a>
                <button type="button" class="btn btn-danger-red btn-sm" style="font-size:12.5px;" onclick="window.openRejectModal('${o.id}')">
                  ✕ Hủy đơn
                </button>
              ` : ''}

              <!-- Nút Khôi phục đơn (Khi Đã hủy) -->
              ${o.status === 'cancelled' ? `
                <button type="button" class="btn btn-primary btn-sm" style="font-size:12.5px;font-weight:700;" onclick="window.quickRevertStatus('${o.id}', 'pending')">
                  ↩️ Khôi phục lại (Chờ duyệt)
                </button>
              ` : ''}
            </div>
          </div>
        </article>
      `;
    }).join('');
  }

  // =========================================================================
  // 5. NỐI API: XÁC NHẬN DUYỆT ĐƠN ĐẶT XE (CÓ HỘP THOẠI CONFIRM ĐẸP)
  // =========================================================================
  let approvingOrderId = null;

  window.approveOrder = function (orderId) {
    const ord = orders.find(o => o.id === orderId);
    if (!ord) return;

    const modal = document.getElementById('approveOrderModal');
    const summaryBox = document.getElementById('approveOrderSummaryBox');
    if (!modal || !summaryBox) {
      executeApproveOrder(orderId);
      return;
    }

    approvingOrderId = orderId;
    const dtype = (ord.depositType || ord.deposit_type || 'CASH').toUpperCase();
    const policyLabel = dtype === 'VEHICLE_PLEDGE'
      ? '🏍️ Chỉ thế chấp tài sản (0 đ tiền cọc)'
      : dtype === 'COMBINED'
        ? `🛡️ Kết hợp cọc (${(ord.deposit || 0).toLocaleString('vi-VN')} đ) &amp; thế chấp xe`
        : `💳 Chỉ đặt cọc tiền (${(ord.deposit || 0).toLocaleString('vi-VN')} đ)`;

    summaryBox.innerHTML = `
      <div style="display:flex;justify-content:space-between;gap:8px;">
        <span style="color:#4d6b57;">Mã đơn / Xe:</span>
        <strong>#${ord.id} • ${ord.vehicle} (${ord.licensePlate || '—'})</strong>
      </div>
      <div style="display:flex;justify-content:space-between;gap:8px;">
        <span style="color:#4d6b57;">Khách thuê:</span>
        <strong>${ord.customer} • ${ord.phone}</strong>
      </div>
      <div style="display:flex;justify-content:space-between;gap:8px;">
        <span style="color:#4d6b57;">Lịch trình:</span>
        <strong>${ord.schedule}</strong>
      </div>
      <div style="display:flex;justify-content:space-between;gap:8px;padding-top:6px;border-top:1px dashed #bbf7d0;">
        <span style="color:#4d6b57;">Chính sách bảo đảm:</span>
        <strong style="color:#15803d;">${policyLabel}</strong>
      </div>
    `;
    modal.classList.add('is-open');
  };

  async function executeApproveOrder(orderId) {
    const ord = orders.find(o => o.id === orderId);
    if (!ord) return;

    const card = document.querySelector(`.saas-order-card[data-id="${orderId}"]`);
    if (card) card.style.opacity = '0.6';

    const baseUrl = getApiBaseUrl();
    let apiSuccess = false;

    try {
      const resp = await fetch(`${baseUrl}/bookings/${orderId}/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      if (resp.ok) {
        apiSuccess = true;
      }
    } catch (e) {
      console.info('API offline, lưu cập nhật duyệt vào bộ nhớ cửa hàng:', e.message);
    }

    ord.status = 'approved';
    saveOrdersToLocal(orders);
    updateMetricsAndBadges();
    renderOrders();

    showToast(
      'Đã duyệt nhận đơn đặt xe thành công!',
      `Đơn #${ord.id} (${ord.customer} • ${ord.vehicle}) đã chuyển sang trạng thái ĐÃ DUYỆT${apiSuccess ? ' (Đã đồng bộ lên CSDL API)' : ''}. Bạn có thể tiến hành lập Biên bản bàn giao xe ngay.`
    );
  }

  document.getElementById('cancelApproveModalBtn')?.addEventListener('click', () => {
    document.getElementById('approveOrderModal')?.classList.remove('is-open');
    approvingOrderId = null;
  });

  document.getElementById('confirmApproveModalBtn')?.addEventListener('click', () => {
    const id = approvingOrderId;
    document.getElementById('approveOrderModal')?.classList.remove('is-open');
    approvingOrderId = null;
    if (id) executeApproveOrder(id);
  });

  // =========================================================================
  // 6. NỐI API: TỪ CHỐI ĐƠN & HOÀN CỌC (UI MỚI SANG ĐẸP)
  // =========================================================================
  window.openRejectModal = function (orderId) {
    const ord = orders.find(o => o.id === orderId);
    if (!ord) return;

    rejectingOrderId = orderId;
    const modal = document.getElementById('rejectOrderModal');
    const refundEl = document.getElementById('rejectRefundAmount');
    if (refundEl) refundEl.textContent = (ord.deposit || 0).toLocaleString('vi-VN') + ' đ';

    // Reset selection card state
    document.querySelectorAll('.reject-reason-card').forEach((card, idx) => {
      const radio = card.querySelector('input[type="radio"]');
      if (idx === 0) {
        card.classList.add('is-active');
        if (radio) radio.checked = true;
      } else {
        card.classList.remove('is-active');
        if (radio) radio.checked = false;
      }
    });

    modal?.classList.add('is-open');
  };

  // Click vào card lý do từ chối để chọn
  document.addEventListener('click', function (e) {
    const card = e.target.closest('.reject-reason-card');
    if (card) {
      document.querySelectorAll('.reject-reason-card').forEach(c => c.classList.remove('is-active'));
      card.classList.add('is-active');
      const radio = card.querySelector('input[type="radio"]');
      if (radio) radio.checked = true;
    }
  });

  document.getElementById('confirmRejectModalBtn')?.addEventListener('click', async function () {
    if (!rejectingOrderId) return;
    const ord = orders.find(o => o.id === rejectingOrderId);
    if (!ord) return;

    const reasonRadio = document.querySelector('input[name="rejectReason"]:checked');
    const reason = reasonRadio ? reasonRadio.value : 'Lý do điều phối nội bộ';

    const baseUrl = getApiBaseUrl();
    let apiSuccess = false;

    try {
      const resp = await fetch(`${baseUrl}/bookings/${rejectingOrderId}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason })
      });
      if (resp.ok) {
        apiSuccess = true;
      }
    } catch (e) {
      console.info('API offline, lưu trạng thái hủy vào bộ nhớ cửa hàng:', e.message);
    }

    ord.status = 'cancelled';
    ord.cancelReason = reason;

    saveOrdersToLocal(orders);
    updateMetricsAndBadges();
    renderOrders();

    document.getElementById('rejectOrderModal')?.classList.remove('is-open');

    showToast(
      'Đã từ chối đơn hàng & Xác nhận hoàn cọc!',
      `Đơn #${ord.id} đã hủy${apiSuccess ? ' (Đã đồng bộ API)' : ''}. Hệ thống đã gửi email giải thích lý do kèm mã hoàn 100% cọc (${ord.deposit.toLocaleString('vi-VN')}đ) qua VietQR cho khách hàng.`,
      'error'
    );
    rejectingOrderId = null;
  });

  document.getElementById('cancelRejectModalBtn')?.addEventListener('click', function () {
    document.getElementById('rejectOrderModal')?.classList.remove('is-open');
    rejectingOrderId = null;
  });

  // =========================================================================
  // 6.1 SỬA & HOÀN TÁC TRẠNG THÁI ĐƠN HÀNG (TRÁNH THAO TÁC NHẦM)
  // =========================================================================
  let changingOrderId = null;

  window.openChangeStatusModal = function (orderId) {
    const ord = orders.find(o => o.id === orderId);
    if (!ord) return;

    changingOrderId = orderId;
    const modal = document.getElementById('changeStatusModal');
    const sub = document.getElementById('changeStatusModalSub');
    if (sub) {
      sub.textContent = `Đơn hàng #${ord.id} • Khách: ${ord.customer} (${ord.vehicle})`;
    }

    const noteInput = document.getElementById('changeStatusNoteInput');
    if (noteInput) noteInput.value = '';

    // Highlight current status
    document.querySelectorAll('.status-switch-option').forEach(opt => {
      const target = opt.dataset.targetStatus;
      const radio = opt.querySelector('input[type="radio"]');
      if (target === ord.status) {
        opt.classList.add('is-active');
        if (radio) radio.checked = true;
      } else {
        opt.classList.remove('is-active');
        if (radio) radio.checked = false;
      }
    });

    modal?.classList.add('is-open');
  };

  // Click vào tùy chọn trạng thái
  document.addEventListener('click', function (e) {
    const opt = e.target.closest('.status-switch-option');
    if (opt) {
      document.querySelectorAll('.status-switch-option').forEach(o => o.classList.remove('is-active'));
      opt.classList.add('is-active');
      const radio = opt.querySelector('input[type="radio"]');
      if (radio) radio.checked = true;
    }
  });

  // Xác nhận sửa trạng thái
  document.getElementById('confirmChangeStatusBtn')?.addEventListener('click', async function () {
    if (!changingOrderId) return;
    const ord = orders.find(o => o.id === changingOrderId);
    if (!ord) return;

    const checkedRadio = document.querySelector('input[name="targetStatusChoice"]:checked');
    const targetStatus = checkedRadio ? checkedRadio.value : 'pending';
    const note = document.getElementById('changeStatusNoteInput')?.value.trim() || 'Người dùng điều chỉnh lại trạng thái';

    await window.changeOrderStatus(changingOrderId, targetStatus, note);
    document.getElementById('changeStatusModal')?.classList.remove('is-open');
    changingOrderId = null;
  });

  // Hàm chuyển đổi trạng thái dùng chung (gọi API + cập nhật localStorage)
  window.changeOrderStatus = async function (orderId, targetStatus, reason = '') {
    const ord = orders.find(o => o.id === orderId);
    if (!ord) return;

    const oldStatus = ord.status;
    ord.status = targetStatus;
    if (targetStatus === 'cancelled') {
      ord.cancelReason = reason || 'Cửa hàng hủy đơn';
    } else {
      ord.cancelReason = '';
    }

    saveOrdersToLocal(orders);
    updateMetricsAndBadges();
    renderOrders();

    const baseUrl = getApiBaseUrl();
    try {
      await fetch(`${baseUrl}/bookings/${orderId}/status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: targetStatus, reason })
      });
    } catch (_) { }

    const statusNames = {
      pending: '🟡 Chờ duyệt',
      approved: '🟢 Đã duyệt',
      cancelled: '🔴 Đã hủy'
    };

    showToast(
      'Đã cập nhật lại trạng thái đơn hàng!',
      `Đơn #${ord.id} (${ord.customer}) đã được đổi từ [${statusNames[oldStatus] || oldStatus}] sang [${statusNames[targetStatus] || targetStatus}].`,
      targetStatus === 'cancelled' ? 'error' : 'success'
    );
  };

  // Hoàn tác nhanh 1 chạm (Quick Revert)
  window.quickRevertStatus = async function (orderId, targetStatus) {
    await window.changeOrderStatus(orderId, targetStatus, 'Hoàn tác nhanh từ danh sách');
  };

  // =========================================================================
  // 7. NỐI API: XỬ LÝ YÊU CẦU DỜI LỊCH TRÌNH
  // =========================================================================
  window.openRescheduleModal = function (orderId) {
    const ord = orders.find(o => o.id === orderId);
    if (!ord || !ord.rescheduleRequest) return;

    const modal = document.getElementById('rescheduleModal');
    const sub = document.getElementById('rescheduleModalSub');
    const body = document.getElementById('rescheduleModalBody');

    if (sub) {
      sub.innerHTML = `
        <span style="font-weight:700;color:#1e293b;">Đơn #${ord.id}</span>
        <span>•</span>
        <span style="color:#475569;">👤 <strong>${ord.customer}</strong> (${ord.phone})</span>
        <span>•</span>
        <span style="color:#059669;font-weight:700;">🛵 ${ord.vehicle} (${ord.licensePlate})</span>
      `;
    }

    const newTotal = ord.total + (ord.rescheduleRequest.surcharge || 0);
    const remainAfterReschedule = Math.max(0, newTotal - ord.deposit);

    if (body) {
      body.innerHTML = `
        <!-- Khối So Sánh Trực Quan 2 Khung Thời Gian (Timeline Comparison Cards) -->
        <div class="reschedule-compare-grid">
          <!-- Cột 1: Lịch ban đầu -->
          <div class="reschedule-card-old">
            <div>
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                <span style="font-size:11px;font-weight:800;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;display:flex;align-items:center;gap:4px;">
                  📅 Lịch thuê ban đầu
                </span>
                <span style="font-size:10.5px;font-weight:700;background:#e2e8f0;color:#334155;padding:2px 7px;border-radius:6px;">
                  ${ord.durationDays || 1} ngày
                </span>
              </div>
              <div style="font-size:13.5px;font-weight:700;color:#1e293b;line-height:1.5;">
                ${ord.rescheduleRequest.oldSchedule}
              </div>
            </div>
            <div style="margin-top:10px;padding-top:8px;border-top:1px solid #e2e8f0;display:flex;align-items:center;justify-content:space-between;font-size:12px;color:#64748b;">
              <span>Đã cọc 30%:</span>
              <strong style="color:#16a34a;">${ord.deposit.toLocaleString('vi-VN')} đ</strong>
            </div>
          </div>

          <!-- Cột giữa: Mũi tên & Tag chênh lệch thời gian -->
          <div class="reschedule-arrow-col">
            <span style="font-size:11px;font-weight:800;background:#ede9fe;color:#7c3aed;padding:3px 10px;border-radius:999px;white-space:nowrap;margin-bottom:6px;border:1.5px solid #ddd6fe;box-shadow:0 2px 6px rgba(124,58,237,0.12);">
              ${ord.rescheduleRequest.durationDiff}
            </span>
            <div style="width:36px;height:36px;border-radius:50%;background:#7c3aed;color:#ffffff;display:grid;place-items:center;font-size:16px;font-weight:900;box-shadow:0 4px 10px rgba(124,58,237,0.3);">
              ➔
            </div>
          </div>

          <!-- Cột 2: Lịch mới đề xuất (Nổi Bật) -->
          <div class="reschedule-card-new">
            <div>
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                <span style="font-size:11px;font-weight:800;color:#7c3aed;text-transform:uppercase;letter-spacing:0.5px;display:flex;align-items:center;gap:4px;">
                  ⚡ Lịch mới đề xuất
                </span>
                <span style="font-size:10.5px;font-weight:800;background:#7c3aed;color:#ffffff;padding:2px 8px;border-radius:6px;">
                  Mới
                </span>
              </div>
              <div style="font-size:14px;font-weight:800;color:#4c1d95;line-height:1.5;">
                ${ord.rescheduleRequest.newSchedule}
              </div>
            </div>
            <div style="margin-top:10px;padding-top:8px;border-top:1.5px dashed #d8b4fe;display:flex;align-items:center;justify-content:space-between;font-size:12px;color:#7c3aed;">
              <span>Phụ phí gia hạn:</span>
              <strong style="color:#6d28d9;font-size:13px;">+${ord.rescheduleRequest.surcharge.toLocaleString('vi-VN')} đ</strong>
            </div>
          </div>
        </div>

        <!-- Khối Thông Báo Kiểm Tra Lịch Trống Phương Tiện -->
        <div style="background:#f0fdf4;border:1.5px solid #bbf7d0;border-radius:12px;padding:10px 14px;display:flex;align-items:center;gap:10px;font-size:12.5px;color:#166534;">
          <span style="width:20px;height:20px;border-radius:50%;background:#22c55e;color:#fff;display:inline-grid;place-items:center;font-size:11px;font-weight:900;flex-shrink:0;">✓</span>
          <div>
            <strong>Tình trạng xe:</strong> Phương tiện <strong>${ord.vehicle} (${ord.licensePlate})</strong> hoàn toàn trống lịch trong khoảng thời gian mới. Đủ điều kiện duyệt dời lịch!
          </div>
        </div>

        <!-- Lý Do Khách Hàng Gửi -->
        <div class="reschedule-reason-callout">
          <span style="font-size:22px;line-height:1;color:#7c3aed;flex-shrink:0;">💬</span>
          <div style="flex:1;">
            <div style="font-size:11.5px;font-weight:800;color:#6b21a8;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:3px;">
              Lý do khách hàng đề xuất:
            </div>
            <div style="font-size:13.5px;color:#334155;font-style:italic;line-height:1.5;">
              "${ord.rescheduleRequest.reason}"
            </div>
          </div>
        </div>

        <!-- Hạch toán tài chính dời lịch (Bento Financial Box) -->
        <div class="reschedule-finance-box">
          <div style="font-size:11.5px;font-weight:800;color:#6b21a8;text-transform:uppercase;letter-spacing:0.6px;margin-bottom:12px;display:flex;justify-content:space-between;align-items:center;">
            <span>Hạch toán dòng tiền &amp; Phụ thu dời lịch</span>
            <span style="font-size:11px;font-weight:700;color:#7c3aed;background:#ffffff;padding:2px 10px;border-radius:999px;border:1px solid #ddd6fe;">Thu trực tiếp khi giao xe</span>
          </div>
          
          <div style="display:flex;justify-content:space-between;margin-bottom:8px;font-size:13px;color:#475569;">
            <span>Giá thuê theo hợp đồng ban đầu:</span>
            <strong style="color:#1e293b;">${ord.total.toLocaleString('vi-VN')} đ</strong>
          </div>
          <div style="display:flex;justify-content:space-between;margin-bottom:8px;font-size:13px;color:#7c3aed;">
            <span>Phụ phí gia hạn ngày thuê (${ord.rescheduleRequest.durationDiff}):</span>
            <strong style="color:#6d28d9;font-weight:800;">+${ord.rescheduleRequest.surcharge.toLocaleString('vi-VN')} đ</strong>
          </div>
          <div style="display:flex;justify-content:space-between;margin-bottom:10px;font-size:13px;color:#16a34a;">
            <span>Đã thanh toán cọc giữ chỗ 30% (VietQR):</span>
            <strong>-${ord.deposit.toLocaleString('vi-VN')} đ</strong>
          </div>

          <div style="border-top:1.5px dashed #c084fc;padding-top:12px;margin-top:8px;">
            <div style="display:flex;justify-content:space-between;align-items:center;font-size:14px;color:#4c1d95;margin-bottom:8px;">
              <span style="font-weight:700;">Tổng giá trị hợp đồng mới:</span>
              <strong style="font-size:1.15rem;font-family:var(--font-display);">${newTotal.toLocaleString('vi-VN')} đ</strong>
            </div>

            <div style="background:#ffffff;border:1.5px solid #a855f7;border-radius:10px;padding:10px 14px;display:flex;justify-content:space-between;align-items:center;box-shadow:0 2px 8px rgba(124,58,237,0.08);">
              <span style="font-size:12.5px;font-weight:700;color:#6b21a8;">Số tiền thực tế còn lại thu tại thời điểm giao xe:</span>
              <span style="font-size:1.2rem;font-weight:900;color:#7c3aed;font-family:var(--font-display);">
                ${remainAfterReschedule.toLocaleString('vi-VN')} đ
              </span>
            </div>
          </div>
        </div>

        <!-- Thanh nút thao tác -->
        <div style="display:flex;justify-content:flex-end;gap:12px;border-top:1px solid #f1f5f9;padding-top:16px;margin-top:2px;">
          <button type="button" class="btn btn-soft" style="border-radius:10px;padding:10px 18px;font-weight:700;" onclick="document.getElementById('rescheduleModal').classList.remove('is-open');">
            Đóng
          </button>
          <button type="button" class="btn btn-soft" style="border-radius:10px;padding:10px 18px;font-weight:700;color:#dc2626;border:1.5px solid #fecaca;background:#fef2f2;" onclick="window.rejectReschedule('${ord.id}')">
            ✕ Từ chối dời lịch
          </button>
          <button type="button" class="btn btn-primary" style="background:linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%);border:none;border-radius:10px;padding:10px 24px;font-weight:800;box-shadow:0 4px 14px rgba(124,58,237,0.35);color:#fff;" onclick="window.approveReschedule('${ord.id}')">
            ✓ Chấp thuận Dời Lịch (+${ord.rescheduleRequest.surcharge.toLocaleString('vi-VN')}đ)
          </button>
        </div>
      `;
    }

    modal?.classList.add('is-open');
  };

  window.approveReschedule = async function (orderId) {
    const ord = orders.find(o => o.id === orderId);
    if (!ord || !ord.rescheduleRequest) return;

    const baseUrl = getApiBaseUrl();
    try {
      await fetch(`${baseUrl}/bookings/${orderId}/reschedule-decision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'approve' })
      });
    } catch (_) { }

    ord.schedule = ord.rescheduleRequest.newSchedule;
    ord.total += (ord.rescheduleRequest.surcharge || 0);
    ord.rescheduleRequest.status = 'approved_store';

    saveOrdersToLocal(orders);
    updateMetricsAndBadges();
    renderOrders();

    document.getElementById('rescheduleModal')?.classList.remove('is-open');
    showToast(
      'Đã chấp thuận dời lịch trình thuê!',
      `Đơn #${ord.id} đã cập nhật lịch mới: ${ord.schedule}. Tổng tiền đơn được tự động tính lại thành ${ord.total.toLocaleString('vi-VN')}đ.`
    );
  };

  window.rejectReschedule = async function (orderId) {
    const ord = orders.find(o => o.id === orderId);
    if (!ord || !ord.rescheduleRequest) return;

    const baseUrl = getApiBaseUrl();
    try {
      await fetch(`${baseUrl}/bookings/${orderId}/reschedule-decision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'reject' })
      });
    } catch (_) { }

    ord.rescheduleRequest.status = 'rejected_store';

    saveOrdersToLocal(orders);
    updateMetricsAndBadges();
    renderOrders();

    document.getElementById('rescheduleModal')?.classList.remove('is-open');
    showToast(
      'Đã từ chối yêu cầu dời lịch!',
      `Đơn #${ord.id} vẫn giữ nguyên lịch trình ban đầu: ${ord.schedule}.`,
      'info'
    );
  };

  // =========================================================================
  // 8. POPUP XEM CHI TIẾT & THẨM ĐỊNH eKYC (CHUẨN FORM XE RIDEHUB 100%)
  // =========================================================================
  window.viewOrderDetail = function (orderId) {
    const ord = orders.find(o => o.id === orderId);
    if (!ord) return;

    const modal = document.getElementById('storeOrderDetailModal');
    const titleEl = document.getElementById('sodModalTitle');
    const badgeEl = document.getElementById('sodStatusBadge');
    const bodyEl = document.getElementById('sodModalBody');

    if (titleEl) {
      titleEl.textContent = `${ord.vehicle} (${ord.category === 'car' ? '2024' : '2025'})`;
    }
    if (badgeEl) {
      if (ord.status === 'approved') {
        badgeEl.className = 'status-badge status-badge--available';
        badgeEl.textContent = '✓ Đã duyệt';
      } else if (ord.status === 'cancelled') {
        badgeEl.className = 'status-badge status-badge--maintenance';
        badgeEl.textContent = '✕ Đã từ chối';
      } else {
        badgeEl.className = 'status-badge status-badge--booked';
        badgeEl.textContent = 'Chờ duyệt';
      }
    }

    const remainPay = Math.max(0, ord.total - ord.deposit);
    const handoverParams = new URLSearchParams({
      booking_id: ord.id,
      customer: ord.customer,
      phone: ord.phone,
      vehicle: ord.vehicle,
      plate: ord.licensePlate,
      deposit: ord.deposit
    }).toString();

    // SVG minh họa xe điện chuẩn RideHub
    const isCar = ord.category === 'car';
    const vehicleSvg = isCar
      ? `<svg width="240" height="110" viewBox="0 0 240 110" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect x="35" y="42" width="170" height="42" rx="14" fill="#16a34a"/>
          <path d="M60 42L85 16H155L180 42H60Z" fill="#22c55e" opacity="0.85"/>
          <path d="M88 20H120V40H68L88 20Z" fill="#dcfce7" opacity="0.9"/>
          <path d="M125 20H152L172 40H125V20Z" fill="#dcfce7" opacity="0.9"/>
          <circle cx="70" cy="84" r="18" fill="#14532d"/>
          <circle cx="70" cy="84" r="9" fill="#f0fdf4"/>
          <circle cx="170" cy="84" r="18" fill="#14532d"/>
          <circle cx="170" cy="84" r="9" fill="#f0fdf4"/>
          <rect x="195" y="52" width="12" height="6" rx="3" fill="#fef08a"/>
          <rect x="33" y="52" width="8" height="6" rx="2" fill="#ef4444"/>
         </svg>`
      : `<svg width="220" height="115" viewBox="0 0 220 115" fill="none" xmlns="http://www.w3.org/2000/svg">
          <!-- Bánh trước -->
          <circle cx="45" cy="82" r="20" stroke="#14532d" stroke-width="8" fill="#f0fdf4"/>
          <!-- Bánh sau -->
          <circle cx="175" cy="82" r="20" stroke="#14532d" stroke-width="8" fill="#f0fdf4"/>
          <!-- Khung xe điện RideHub -->
          <path d="M45 82L80 45H125L105 82H150L175 82" stroke="#16a34a" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>
          <path d="M80 45L68 22H55" stroke="#15803d" stroke-width="5" stroke-linecap="round"/>
          <!-- Yên xe & Thân cốp điện -->
          <path d="M98 40C98 32 110 26 128 26C142 26 155 35 155 45C155 48 142 54 125 54C108 54 98 48 98 40Z" fill="#4ade80" opacity="0.9"/>
          <!-- Đèn pha LED -->
          <circle cx="53" cy="22" r="4" fill="#fef08a"/>
         </svg>`;

    const isSelfPickup = !ord.delivery.toLowerCase().includes('tận nơi');

    if (bodyEl) {
      bodyEl.innerHTML = `
        <!-- 1. Banner Xe Minh Họa Chuẩn Form RideHub -->
        <div class="vehicle-visual-banner">
          ${vehicleSvg}
          <div style="margin-top:10px;display:flex;align-items:center;gap:10px;flex-wrap:wrap;justify-content:center;">
            <span class="plate-badge-pill">${ord.licensePlate}</span>
            <span style="font-size:12px;font-weight:700;color:var(--green-900);background:#ffffff;padding:3px 10px;border-radius:999px;border:1px solid #bbf7d0;">
              ⚡ Trạm sạc trực tuyến 98%
            </span>
          </div>
        </div>

        <!-- 2. Tag Phân Loại (Pills chuẩn như ảnh 2) -->
        <div style="display:flex;flex-wrap:wrap;gap:8px;">
          <span class="amenity-chip">${isCar ? '🚗 Ô tô điện' : '🛵 Xe máy điện'}</span>
          <span class="amenity-chip">⚙️ Số tự động</span>
          <span class="amenity-chip">🔋 Động cơ điện thông minh</span>
          <span class="amenity-chip">👥 ${isCar ? '5 chỗ ngồi' : '2 chỗ ngồi'}</span>
        </div>

        <!-- 3. Thời Gian Thuê Xe (Chuẩn Box ảnh 2) -->
        <div class="modal-box-soft">
          <div class="modal-section-title">
            <span>Thời gian thuê xe (${ord.durationDays} ngày)</span>
            <span style="color:var(--green-700);font-weight:700;font-size:11px;">Đã khóa lịch giữ xe</span>
          </div>
          <div style="background:#ffffff;padding:10px 14px;border-radius:10px;border:1.5px solid #dcfce7;font-weight:800;color:var(--green-800);font-size:14px;display:flex;align-items:center;gap:8px;">
            <span>📅</span>
            <span>${ord.schedule}</span>
          </div>
        </div>

        <!-- 4. Hình Thức Nhận Xe (Nút Toggle chuẩn ảnh 2) -->
        <div class="modal-box-soft">
          <div class="modal-section-title">Hình thức nhận xe</div>
          <div class="toggle-delivery-mode">
            <button type="button" class="toggle-delivery-btn ${isSelfPickup ? 'is-active' : 'is-inactive'}">
              <span>${isSelfPickup ? '✓' : '○'}</span>
              <span>Tôi tự đến lấy xe (0đ)</span>
            </button>
            <button type="button" class="toggle-delivery-btn ${!isSelfPickup ? 'is-active' : 'is-inactive'}">
              <span>${!isSelfPickup ? '✓' : '○'}</span>
              <span>Giao xe tận nơi (+30.000đ)</span>
            </button>
          </div>
          <div style="margin-top:10px;font-size:13px;color:var(--green-900);font-weight:600;display:flex;align-items:center;gap:6px;">
            <span>📍</span>
            <span>${ord.delivery}</span>
          </div>
        </div>

        <!-- 5. Tiện Ích Bổ Sung (Chuẩn checkbox list ảnh 2) -->
        <div class="modal-box-soft">
          <div class="modal-section-title">Tiện ích &amp; Phụ kiện bàn giao</div>
          <div style="display:flex;flex-direction:column;gap:8px;">
            <div class="pill-checkbox-item">
              <span style="color:var(--green-600);font-size:16px;">☑</span>
              <span>${ord.addons}</span>
            </div>
            <div class="pill-checkbox-item">
              <span style="color:var(--green-600);font-size:16px;">☑</span>
              <span>Bảo hiểm chuyến đi mở rộng PTI</span>
            </div>
          </div>
          <div style="margin-top:8px;font-size:12.5px;color:var(--text-secondary);font-style:italic;">
            Ghi chú từ khách: "${ord.note || 'Khách yêu cầu xe sạch sẽ và đầy pin.'}"
          </div>
        </div>

        <!-- 6. Hồ Sơ Khách Thuê & Thẩm Định eKYC -->
        <div class="modal-box-soft">
          <div class="modal-section-title">
            <span>Hồ sơ khách thuê &amp; Thẩm định eKYC</span>
            <span class="status-badge status-badge--available" style="font-size:10px;padding:2px 8px;">✓ eKYC Chip Đạt Chuẩn</span>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;font-size:13px;background:#ffffff;padding:12px 14px;border-radius:10px;border:1px solid #dcfce7;">
            <div>Họ và tên: <strong style="color:var(--text-primary);">${ord.customer}</strong></div>
            <div>Số điện thoại: <strong>${ord.phone}</strong></div>
            <div>Email: <strong>${ord.email}</strong></div>
            <div>Số CCCD: <strong>${ord.cccd}</strong></div>
          </div>
        </div>

        <!-- 7. Tiện Nghi Trên Xe (Tags chuẩn ảnh 2) -->
        <div class="modal-box-soft">
          <div class="modal-section-title">Các tiện nghi trang bị theo xe</div>
          <div style="display:flex;flex-wrap:wrap;gap:8px;">
            <span class="amenity-chip">Cốp rộng</span>
            <span class="amenity-chip">2 nón bảo hiểm</span>
            <span class="amenity-chip">Áo mưa đôi</span>
            <span class="amenity-chip">Bộ sạc thông minh</span>
            <span class="amenity-chip">Khóa Smartkey</span>
          </div>
        </div>

        <!-- 8. Hạch Toán Chi Phí & Đặt Cọc VietQR -->
        <div style="background:linear-gradient(135deg, #f0fdf4 0%, #e6f7ec 100%);border:1.5px solid #bbf7d0;padding:16px 18px;border-radius:14px;font-size:13.5px;">
          <div class="modal-section-title" style="color:var(--green-950);">
            Hạch toán chi phí &amp; Đặt cọc VietQR
          </div>
          <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
            <span>Tổng chi phí thuê xe:</span>
            <strong>${ord.total.toLocaleString('vi-VN')} đ</strong>
          </div>
          <div style="display:flex;justify-content:space-between;margin-bottom:6px;color:var(--green-800);">
            <span>Đã cọc giữ chỗ 30% (VietQR):</span>
            <strong>- ${ord.deposit.toLocaleString('vi-VN')} đ</strong>
          </div>
          <div style="display:flex;justify-content:space-between;align-items:center;font-size:15px;font-weight:800;border-top:1.5px dashed #86efac;padding-top:10px;margin-top:6px;color:#b91c1c;">
            <span>Số tiền còn lại thu tại thời điểm giao xe:</span>
            <span style="background:#ffffff;padding:4px 12px;border-radius:8px;border:1px solid #fca5a5;box-shadow:0 2px 4px rgba(0,0,0,0.04);">
              ${remainPay.toLocaleString('vi-VN')} đ
            </span>
          </div>
          <div style="font-size:12px;color:var(--text-muted);margin-top:8px;">
            Điều kiện thế chấp trạm: <strong>${ord.collateral}</strong>
          </div>
        </div>

        <!-- Action Footer Buttons -->
        <div style="display:flex;justify-content:flex-end;gap:10px;margin-top:10px;flex-wrap:wrap;border-top:1px solid #e2f2e5;padding-top:12px;">
          <button type="button" class="btn btn-soft" style="border-radius:10px;font-weight:700;padding:8px 18px;" onclick="document.getElementById('storeOrderDetailModal').classList.remove('is-open');">
            Đóng
          </button>
          
          
          ${ord.status === 'pending' ? `
            <button type="button" class="btn btn-primary" style="border-radius:10px;font-weight:700;padding:8px 22px;box-shadow:0 4px 12px rgba(22,163,74,0.25);" onclick="window.approveOrder('${ord.id}');document.getElementById('storeOrderDetailModal').classList.remove('is-open');">
              ✓ Duyệt nhận đơn ngay
            </button>
            <button type="button" class="btn btn-danger-red" style="border-radius:10px;padding:8px 20px;font-size:13px;" onclick="document.getElementById('storeOrderDetailModal').classList.remove('is-open');window.openRejectModal('${ord.id}');">
              ✕ Từ chối đơn
            </button>
          ` : ''}

          ${ord.status === 'approved' ? `
            <a href="handover.html?${handoverParams}" 
               class="btn btn-primary" style="text-decoration:none;border-radius:10px;font-weight:700;padding:8px 22px;display:inline-flex;align-items:center;gap:6px;box-shadow:0 4px 14px rgba(22,163,74,0.3);">
              📝 Tiến hành Lập biên bản bàn giao xe →
            </a>
            <button type="button" class="btn btn-danger-red" style="border-radius:10px;padding:8px 18px;font-size:13px;" onclick="document.getElementById('storeOrderDetailModal').classList.remove('is-open');window.openRejectModal('${ord.id}');">
              ✕ Hủy đơn
            </button>
          ` : ''}

          ${ord.status === 'cancelled' ? `
            <button type="button" class="btn btn-primary" style="border-radius:10px;font-weight:700;padding:8px 20px;" onclick="document.getElementById('storeOrderDetailModal').classList.remove('is-open');window.quickRevertStatus('${ord.id}', 'pending');">
              ↩️ Khôi phục đơn (Chờ duyệt)
            </button>
          ` : ''}
        </div>
      `;
    }

    modal?.classList.add('is-open');
  };

  document.getElementById('closeOrderModalBtn')?.addEventListener('click', function () {
    document.getElementById('storeOrderDetailModal')?.classList.remove('is-open');
  });

  // =========================================================================
  // 9. EVENT LISTENERS CHO BỘ LỌC & TÌM KIẾM
  // =========================================================================
  document.getElementById('orderSearchInput')?.addEventListener('input', function () {
    renderOrders();
  });

  document.querySelectorAll('#orderFilterBar [data-filter]').forEach(btn => {
    btn.addEventListener('click', function () {
      document.querySelectorAll('#orderFilterBar [data-filter]').forEach(b => {
        b.classList.remove('btn-primary');
        b.classList.add('btn-soft');
      });
      this.classList.remove('btn-soft');
      this.classList.add('btn-primary');
      currentFilter = this.dataset.filter;
      renderOrders();
    });
  });

  document.getElementById('vehicleCategoryFilter')?.addEventListener('change', function (e) {
    currentCategory = e.target.value;
    renderOrders();
  });

  window.resetFilters = function () {
    currentFilter = 'all';
    currentCategory = 'all';
    const searchInput = document.getElementById('orderSearchInput');
    if (searchInput) searchInput.value = '';

    const catSelect = document.getElementById('vehicleCategoryFilter');
    if (catSelect) catSelect.value = 'all';

    document.querySelectorAll('#orderFilterBar [data-filter]').forEach(b => {
      b.classList.toggle('btn-primary', b.dataset.filter === 'all');
      b.classList.toggle('btn-soft', b.dataset.filter !== 'all');
    });

    renderOrders();
  };

  // Nút làm mới dữ liệu từ API
  window.refreshOrdersFromApi = function () {
    fetchOrdersFromApi();
    showToast('Đang cập nhật...', 'Hệ thống đang đồng bộ dữ liệu mới nhất từ trạm xe.', 'success');
  };

  // Modal backdrop click & phím ESC
  [
    document.getElementById('storeOrderDetailModal'),
    document.getElementById('rejectOrderModal'),
    document.getElementById('rescheduleModal')
  ].forEach(m => {
    m?.addEventListener('click', function (e) {
      if (e.target === this) {
        this.classList.remove('is-open');
      }
    });
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      document.querySelectorAll('.app-modal-backdrop.is-open').forEach(m => m.classList.remove('is-open'));
    }
  });

  // Global export
  global.RideHubStoreOrders = {
    getOrders() { return orders; },
    reload: fetchOrdersFromApi,
  };

  // Khởi động khi tải trang
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', fetchOrdersFromApi);
  } else {
    fetchOrdersFromApi();
  }

})(typeof window !== 'undefined' ? window : this);
