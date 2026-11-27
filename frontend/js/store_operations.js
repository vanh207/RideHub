/* ==========================================================================
   RideHub - Giao diện Vận hành Cửa hàng: Đổi trạng thái, Lịch xe, Cảnh báo
   Đặc tả yêu cầu: FR-17 -> FR-21, FR-60 (SRS v2.2)
   ========================================================================== */
(function () {
  'use strict';

  // 1. DỮ LIỆU KHO XE & TRẠNG THÁI MẪU
  const DEFAULT_FLEET = [
    {
      id: 'v1', name: 'VinFast Feliz S', category: 'motorcycle',
      transmission: 'Xe tay ga', fuel: 'Điện', price: 160000,
      status: 'Sẵn sàng', alertText: 'Trống lịch 3 ngày tới', conflict: false
    },
    {
      id: 'v2', name: 'VinFast VF 5', category: 'car',
      transmission: 'Số tự động', fuel: 'Điện', price: 750000,
      status: 'Đang thuê', alertText: 'Trả xe lúc 18:00 hôm nay', conflict: false
    },
    {
      id: 'v3', name: 'Dat Bike Weaver++', category: 'motorcycle',
      transmission: 'Xe côn tay', fuel: 'Điện', price: 220000,
      status: 'Đang vệ sinh', alertText: '⚠️ Xung đột: Khách xin dời ngày trùng ca bảo dưỡng', conflict: true
    },
    {
      id: 'v4', name: 'Mazda 3 Sedan', category: 'car',
      transmission: 'Số tự động', fuel: 'Xăng', price: 850000,
      status: 'Bảo dưỡng', alertText: '🔧 Tới hạn bảo dưỡng • Đang ẩn khỏi tìm kiếm', conflict: false
    }
  ];

  const STATUS_CYCLE = ['Sẵn sàng', 'Đang thuê', 'Đang vệ sinh', 'Bảo dưỡng'];
  const STATUS_BADGE_MAP = {
    'Sẵn sàng': 'status-badge--available',
    'Đang thuê': 'status-badge--transit',
    'Đang vệ sinh': 'status-badge--cleaning',
    'Bảo dưỡng': 'status-badge--maintenance'
  };

  const FLEET_STORAGE_KEY = 'ridehub_store_fleet_v2';

  // Tự động tải từ kho xe thực tế (do trang vehicle_management.html quản lý)
  function getRealFleetList() {
    try {
      const raw = localStorage.getItem(FLEET_STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed) && parsed.length > 0) {
          return parsed.map((v) => ({
            id: v.id,
            name: `${v.brand || ''} ${v.name || v.model || ''}`.trim(),
            category: v.type === 'car' ? 'car' : 'motorcycle',
            transmission: v.transmission || 'Tự động',
            fuel: v.fuel || (v.type === 'moto' ? 'Điện' : 'Xăng/Điện'),
            price: Number(v.price || 0),
            status: v.status || 'Sẵn sàng',
            alertText: v.status === 'Bảo dưỡng' ? '🔧 Đang bảo dưỡng' : (v.status === 'Đang thuê' ? 'Đang trong lịch thuê' : 'Trống lịch'),
            conflict: false
          }));
        }
      }
    } catch (e) {
      console.warn('Lỗi đọc kho xe thật:', e);
    }
    return JSON.parse(JSON.stringify(DEFAULT_FLEET));
  }

  let fleetList = getRealFleetList();

  // 2. DỮ LIỆU ĐƠN THUÊ MẪU
  const mockOrders = [
    {
      id: 'RH-8842', vehicle: 'VinFast Feliz S', customer: 'Nguyễn Văn An', phone: '0901234567',
      schedule: '14/11/2026 08:00 → 16/11/2026 08:00 (2 ngày)',
      delivery: 'Giao xe tận nơi • 120 Nguyễn Huệ, Q.1', status: 'approved'
    },
    {
      id: 'RH-8845', vehicle: 'VinFast VF 5', customer: 'Trần Thanh Bình', phone: '0901000002',
      schedule: '15/11/2026 09:00 → 17/11/2026 18:00 (2.5 ngày)',
      delivery: 'Nhận tại bãi xe • GreenRide Q.1', status: 'pending'
    },
    {
      id: 'RH-8835', vehicle: 'Dat Bike Weaver++', customer: 'Lê Kim Chi', phone: '0901000003',
      schedule: '13/11/2026 10:00 → 14/11/2026 10:00 (1 ngày)',
      delivery: 'Giao xe tận nơi • 45 Lê Lợi, Q.1', status: 'approved',
      hasConflict: true, conflictReason: 'Khách xin dời sang 14/11 trùng ca bảo dưỡng/vệ sinh pin!'
    },
    {
      id: 'RH-8820', vehicle: 'VinFast Klara S', customer: 'Hoàng Minh Trí', phone: '0901000004',
      schedule: '14/11/2026 09:00 → 15/11/2026 09:00 (1 ngày)',
      delivery: 'Nhận tại cửa hàng • GreenRide Q.1', status: 'approved'
    }
  ];

  function getRealOrders() {
    try {
      const raw = localStorage.getItem('ridehub_store_orders_v1');
      if (raw) {
        const list = JSON.parse(raw);
        if (Array.isArray(list) && list.length > 0) return list;
      }
    } catch (_) {}
    return mockOrders;
  }

  // 3. TOAST THÔNG BÁO
  function showRideHubToast(msg, isWarning = false) {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = 'toast-item';
    if (isWarning) { toast.style.background = '#991b1b'; toast.style.border = '1px solid #f87171'; }
    toast.innerHTML = `<span>${isWarning ? '⚠️' : '✓'}</span><span>${msg}</span>`;
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transition = 'all 0.25s ease';
      setTimeout(() => toast.remove(), 260);
    }, 2800);
  }

  // 4. RENDER CHỈ SỐ THỐNG KÊ (KPIs)
  function renderStats() {
    const totalVeh = fleetList.length;
    const cleaningMaint = fleetList.filter(v => v.status === 'Đang vệ sinh' || v.status === 'Bảo dưỡng').length;
    const conflicts = fleetList.filter(v => v.conflict).length;
    const elTot = document.getElementById('statTotalVeh');
    const elCl = document.getElementById('statCleaningMaint');
    const elCf = document.getElementById('statConflictCount');
    if (elTot) elTot.textContent = totalVeh;
    if (elCl) elCl.textContent = cleaningMaint;
    if (elCf) elCf.textContent = conflicts;
  }

  // 5. RENDER BẢNG KHO XE & ĐỔI TRẠNG THÁI
  function renderFleetTable() {
    const tbody = document.getElementById('fleetTableBody');
    if (!tbody) return;
    tbody.innerHTML = fleetList.map((v, idx) => {
      const isCar = v.category === 'car';
      const badgeClass = STATUS_BADGE_MAP[v.status] || 'status-badge--available';
      const hasPulse = v.status === 'Sẵn sàng' || v.status === 'Đang vệ sinh';
      return `
        <tr>
          <td>
            <strong>${v.name}</strong>
            ${v.conflict ? '<span class="alert-tag alert-tag--danger" style="margin-left:6px;">Xung đột</span>' : ''}
          </td>
          <td>${isCar ? 'Ô tô' : 'Xe máy'} • ${v.transmission} • ${v.fuel}</td>
          <td><strong>${Number(v.price).toLocaleString('vi-VN')}đ</strong></td>
          <td>
            <label class="status-badge ${badgeClass}" title="Bấm để chọn trạng thái xe">
              <span class="status-dot ${hasPulse ? 'status-dot-pulse' : ''}"></span>
              <select class="status-select" data-vehicle-idx="${idx}">
                ${STATUS_CYCLE.map(opt => `<option value="${opt}" ${opt === v.status ? 'selected' : ''}>${opt}</option>`).join('')}
              </select>
              <span style="font-size:10px;margin-left:-4px;pointer-events:none;">▾</span>
            </label>
          </td>
          <td>
            <span style="${v.conflict ? 'color:#be123c;font-weight:700;' : v.status === 'Bảo dưỡng' ? 'color:#b45309;font-weight:600;' : 'color:var(--text-secondary);'}">
              ${v.alertText}
            </span>
          </td>
          <td>
            <button type="button" class="btn btn-soft" style="min-height:26px;padding:1px 8px;font-size:11.5px;" data-quick-toggle-idx="${idx}">
              Đổi nhanh
            </button>
          </td>
        </tr>
      `;
    }).join('');

    tbody.querySelectorAll('[data-vehicle-idx]').forEach(sel => {
      sel.addEventListener('change', () => {
        updateVehicleStatus(Number(sel.dataset.vehicleIdx), sel.value);
      });
    });

    tbody.querySelectorAll('[data-quick-toggle-idx]').forEach(btn => {
      btn.addEventListener('click', () => {
        const idx = Number(btn.dataset.quickToggleIdx);
        const curIdx = STATUS_CYCLE.indexOf(fleetList[idx].status);
        updateVehicleStatus(idx, STATUS_CYCLE[(curIdx + 1) % STATUS_CYCLE.length]);
      });
    });
  }

  function updateVehicleStatus(idx, newStatus) {
    const cur = fleetList[idx];
    if (!cur) return;
    cur.status = newStatus;
        // Đồng bộ trạng thái mới ngược về kho xe thật (FLEET_STORAGE_KEY)
    try {
      const raw = localStorage.getItem(FLEET_STORAGE_KEY);
      if (raw) {
        const list = JSON.parse(raw);
        const target = list.find((item) => item.id === cur.id);
        if (target) {
          target.status = newStatus;
          localStorage.setItem(FLEET_STORAGE_KEY, JSON.stringify(list));
        }
      }
    } catch (_) {}
    if (newStatus === 'Bảo dưỡng') {
      cur.alertText = '🔧 Đang bảo dưỡng • Đã ẩn khỏi tìm kiếm (FR-60)';
      showRideHubToast(`Xe "${cur.name}" chuyển sang BẢO DƯỠNG (đã ẩn xe khỏi tìm kiếm)`, true);
    } else if (newStatus === 'Đang vệ sinh') {
      cur.alertText = '⏱️ Đang vệ sinh pin & ngoại quan (trước 15:00)';
      showRideHubToast(`Xe "${cur.name}" chuyển sang ĐANG VỆ SINH`);
    } else if (newStatus === 'Đang thuê') {
      cur.alertText = '🚗 Đang bàn giao cho khách thuê';
      showRideHubToast(`Xe "${cur.name}" chuyển sang ĐANG THUÊ`);
    } else {
      cur.alertText = 'Trống lịch, sẵn sàng nhận đơn mới';
      showRideHubToast(`Xe "${cur.name}" đã SẴN SÀNG đón khách`);
    }
    renderStats();
    renderFleetTable();
  }

  // 6. LOGIC LỊCH XE THEO NGÀY & TUẦN
  let calYear = 2026;
  let calMonth = 10; // Tháng 11 (0-indexed)
  let calSelectedKey = '2026-11-14';
  let currentViewMode = 'month';

  function pad2(n) { return String(n).padStart(2, '0'); }

  function getCalendarEventsMap() {
    const map = {};
    const addEv = (dateKey, ev) => {
      if (!map[dateKey]) map[dateKey] = [];
      map[dateKey].push(ev);
    };
    getRealOrders().forEach(o => {
      const matches = (o.schedule || '').match(/(\d{2})\/(\d{2})\/(\d{4})/g) || [];
      if (matches[0]) {
        const [d, m, y] = matches[0].split('/');
        addEv(`${y}-${m}-${d}`, {
          type: 'pickup', label: `Giao: ${o.vehicle.split('(')[0].trim()}`,
          title: `#${o.id} • Giao xe ${o.vehicle}`, detail: `Khách: ${o.customer} (${o.phone}) • ${o.delivery}`,
          time: '08:00 - 10:00', status: o.status === 'approved' ? 'Đã duyệt' : 'Chờ duyệt',
          conflict: o.hasConflict || false
        });
      }
      if (matches[1]) {
        const [d, m, y] = matches[1].split('/');
        addEv(`${y}-${m}-${d}`, {
          type: 'return', label: `Trả: ${o.vehicle.split('(')[0].trim()}`,
          title: `#${o.id} • Nhận lại ${o.vehicle}`, detail: `Khách: ${o.customer} • Kiểm tra & đối soát`,
          time: '18:00 - 20:00', status: o.status === 'approved' ? 'Đã lên lịch' : 'Chờ duyệt'
        });
      }
    });
    addEv('2026-11-12', {
      type: 'maint', label: 'Vệ sinh: Dat Bike', title: 'Vệ sinh & sạc pin • Dat Bike Weaver++',
      detail: 'Hoàn tất kiểm tra sạc pin trước 15:00 (FR-60)', time: '13:00 - 15:00', status: 'Đang thực hiện'
    });
    addEv('2026-11-14', {
      type: 'conflict', label: '⚠️ Xung đột lịch: Dat Bike', title: 'CẢNH BÁO XUNG ĐỘT LỊCH (FR-21)',
      detail: 'Đơn #RH-8835 xin dời ngày trùng ca bảo dưỡng/vệ sinh pin và đơn giao xe khác!',
      time: '10:00 - 12:00', status: 'Xung đột lịch'
    });
    addEv('2026-11-18', {
      type: 'maint', label: 'Bảo dưỡng: Mazda 3', title: 'Bảo dưỡng định kỳ • Mazda 3 Sedan',
      detail: 'Kiểm tra phanh, thay nhớt & vệ sinh nội thất định kỳ', time: '09:00 - 17:00', status: 'Tới hạn bảo dưỡng'
    });
    return map;
  }

  // 7. RENDER LỊCH THÁNG
  function renderMonthView() {
    const grid = document.getElementById('calGrid');
    const titleEl = document.getElementById('calMonthTitle');
    if (!grid || !titleEl) return;
    titleEl.textContent = `Tháng ${calMonth + 1} / ${calYear}`;
    const evMap = getCalendarEventsMap();
    const firstDay = new Date(calYear, calMonth, 1).getDay();
    const offset = (firstDay + 6) % 7;
    const daysInMonth = new Date(calYear, calMonth + 1, 0).getDate();
    const todayKey = '2026-11-14';
    let html = '';
    for (let i = 0; i < offset; i++) html += '<div class="rh-cal-cell is-empty"></div>';
    for (let day = 1; day <= daysInMonth; day++) {
      const key = `${calYear}-${pad2(calMonth + 1)}-${pad2(day)}`;
      const evs = evMap[key] || [];
      const hasConflict = evs.some(e => e.type === 'conflict' || e.conflict);
      const pills = evs.slice(0, 2).map(ev => `<span class="rh-cal-pill rh-cal-pill--${ev.type}">${ev.label}</span>`).join('');
      const more = evs.length > 2 ? `<span style="font-size:9.5px;color:var(--text-muted);font-weight:700;">+${evs.length - 2} lịch khác</span>` : '';
      html += `
        <button type="button" class="rh-cal-cell ${key === calSelectedKey ? 'is-selected' : ''} ${key === todayKey ? 'is-today' : ''}" data-cal-date="${key}" style="${hasConflict ? 'border-color:#f43f5e;' : ''}">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <span class="rh-cal-day">${day}</span>
            ${hasConflict ? '<span style="font-size:10.5px;">⚠️</span>' : ''}
          </div>
          <div class="rh-cal-dots">${pills}${more}</div>
        </button>
      `;
    }
    grid.innerHTML = html;
    grid.querySelectorAll('[data-cal-date]').forEach(cell => {
      cell.addEventListener('click', () => {
        calSelectedKey = cell.dataset.calDate;
        renderMonthView();
      });
    });
    renderSelectedDayEvents(evMap);
  }

  // 8. RENDER LỊCH TUẦN
  function renderWeekView() {
    const weekGrid = document.getElementById('weekGrid');
    const titleEl = document.getElementById('calMonthTitle');
    if (!weekGrid || !titleEl) return;
    const selDate = new Date(calSelectedKey);
    const dayOfWeek = selDate.getDay();
    const monDate = new Date(selDate);
    monDate.setDate(selDate.getDate() - ((dayOfWeek + 6) % 7));
    const sunDate = new Date(monDate);
    sunDate.setDate(monDate.getDate() + 6);
    titleEl.textContent = `Tuần: ${pad2(monDate.getDate())}/${pad2(monDate.getMonth() + 1)} → ${pad2(sunDate.getDate())}/${pad2(sunDate.getMonth() + 1)}/${sunDate.getFullYear()}`;
    const evMap = getCalendarEventsMap();
    const weekdaysName = ['Thứ 2', 'Thứ 3', 'Thứ 4', 'Thứ 5', 'Thứ 6', 'Thứ 7', 'Chủ nhật'];
    const todayKey = '2026-11-14';
    let html = '';
    for (let i = 0; i < 7; i++) {
      const d = new Date(monDate);
      d.setDate(monDate.getDate() + i);
      const key = `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
      const evs = evMap[key] || [];
      const evsHtml = evs.length ? evs.map(ev => `
        <div class="week-ev-card ${ev.type}">
          <strong style="color:var(--text-primary);font-size:10.5px;">${ev.label}</strong>
          <span style="font-size:9.5px;color:var(--text-muted);">${ev.time}</span>
        </div>
      `).join('') : '<span style="font-size:10.5px;color:var(--text-muted);text-align:center;margin-top:20px;">Trống lịch</span>';
      html += `
        <div class="week-day-col ${key === calSelectedKey ? 'is-active' : ''} ${key === todayKey ? 'is-today' : ''}" data-week-date="${key}">
          <div class="week-day-header">
            <div class="week-day-title">${weekdaysName[i]}</div>
            <div class="week-day-num">${pad2(d.getDate())}</div>
          </div>
          <div style="display:flex;flex-direction:column;gap:5px;flex:1;">${evsHtml}</div>
        </div>
      `;
    }
    weekGrid.innerHTML = html;
    weekGrid.querySelectorAll('[data-week-date]').forEach(col => {
      col.addEventListener('click', () => {
        calSelectedKey = col.dataset.weekDate;
        renderWeekView();
      });
    });
    renderSelectedDayEvents(evMap);
  }

  // 9. RENDER CHI TIẾT SỰ KIỆN TRONG NGÀY
  function renderSelectedDayEvents(evMap) {
    const listEl = document.getElementById('calDayEventsList');
    const titleEl = document.getElementById('calSelectedDateTitle');
    const badgeEl = document.getElementById('calDayCountBadge');
    if (!listEl || !titleEl) return;
    const [y, m, d] = calSelectedKey.split('-');
    titleEl.textContent = `Lịch ngày ${d}/${m}/${y}`;
    const evs = evMap[calSelectedKey] || [];
    if (badgeEl) badgeEl.textContent = `${evs.length} lịch`;
    if (!evs.length) {
      listEl.innerHTML = '<div style="text-align:center;padding:28px 12px;color:var(--text-muted);font-size:12.5px;background:var(--bg-surface-soft);border-radius:12px;">Không có ca giao nhận hay bảo dưỡng nào.</div>';
      return;
    }
    listEl.innerHTML = evs.map(ev => {
      const isConflict = ev.type === 'conflict' || ev.conflict;
      return `
        <div class="event-detail-card ${isConflict ? 'has-conflict' : ''}">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:6px;">
            <strong style="font-size:12.5px;color:${isConflict ? '#9f1239' : 'var(--text-primary)'};">${ev.title}</strong>
            <span class="rh-cal-pill rh-cal-pill--${ev.type}">${ev.status}</span>
          </div>
          <div style="font-size:12px;color:var(--text-secondary);line-height:1.4;">${ev.detail}</div>
          <div style="display:flex;justify-content:space-between;font-size:11px;color:var(--text-muted);margin-top:2px;">
            <span>⏰ Khung giờ: <strong>${ev.time}</strong></span>
            ${isConflict ? '<span style="color:#be123c;font-weight:700;">⚠️ Cần xử lý</span>' : ''}
          </div>
        </div>
      `;
    }).join('');
  }

  // 10. GẮN SỰ KIỆN ĐIỀU HƯỚNG
  function initEvents() {
    const prevBtn = document.getElementById('calPrevBtn');
    const nextBtn = document.getElementById('calNextBtn');
    const todayBtn = document.getElementById('calTodayBtn');
    const viewMonthBtn = document.getElementById('viewMonthBtn');
    const viewWeekBtn = document.getElementById('viewWeekBtn');
    const monthViewWrapper = document.getElementById('monthViewWrapper');
    const weekViewWrapper = document.getElementById('weekViewWrapper');

    function refresh() {
      if (currentViewMode === 'month') renderMonthView();
      else renderWeekView();
    }

    prevBtn?.addEventListener('click', () => {
      if (currentViewMode === 'month') {
        calMonth -= 1;
        if (calMonth < 0) { calMonth = 11; calYear -= 1; }
      } else {
        const cur = new Date(calSelectedKey);
        cur.setDate(cur.getDate() - 7);
        calSelectedKey = `${cur.getFullYear()}-${pad2(cur.getMonth() + 1)}-${pad2(cur.getDate())}`;
      }
      refresh();
    });

    nextBtn?.addEventListener('click', () => {
      if (currentViewMode === 'month') {
        calMonth += 1;
        if (calMonth > 11) { calMonth = 0; calYear += 1; }
      } else {
        const cur = new Date(calSelectedKey);
        cur.setDate(cur.getDate() + 7);
        calSelectedKey = `${cur.getFullYear()}-${pad2(cur.getMonth() + 1)}-${pad2(cur.getDate())}`;
      }
      refresh();
    });

    todayBtn?.addEventListener('click', () => {
      calYear = 2026; calMonth = 10; calSelectedKey = '2026-11-14';
      refresh();
    });

    viewMonthBtn?.addEventListener('click', () => {
      currentViewMode = 'month';
      viewMonthBtn.className = 'btn btn-primary';
      viewWeekBtn.className = 'btn btn-soft';
      monthViewWrapper.removeAttribute('hidden');
      weekViewWrapper.setAttribute('hidden', '');
      renderMonthView();
    });

    viewWeekBtn?.addEventListener('click', () => {
      currentViewMode = 'week';
      viewWeekBtn.className = 'btn btn-primary';
      viewMonthBtn.className = 'btn btn-soft';
      weekViewWrapper.removeAttribute('hidden');
      monthViewWrapper.setAttribute('hidden', '');
      renderWeekView();
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    initEvents();
    renderStats();
    renderFleetTable();
    renderMonthView();
  });
})();