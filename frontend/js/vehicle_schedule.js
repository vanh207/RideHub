(function () {
  'use strict';

  // Trạng thái ngày/tháng đang chọn
  let calYear = 2026;
  let calMonth = 10; // Tháng 11 (0-indexed: 0 = Tháng 1, 10 = Tháng 11)
  let calSelectedKey = '2026-11-14'; // Ngày mặc định được chọn
  let currentMode = 'month'; // 'month' hoặc 'week'

  function pad2(n) {
    return String(n).padStart(2, '0');
  }

  function parseLocalDateKey(key) {
    const [y, m, d] = String(key).split('-').map(Number);
    return new Date(y, m - 1, d);
  }

  // 1. DỮ LIỆU ĐƠN THUÊ GIẢ LẬP (Trích xuất từ DEFAULT_ORDERS của store-portal.html)
  const mockOrders = [
    {
      id: 'RH-8842',
      vehicle: 'VinFast Feliz S (Xe máy điện)',
      customer: 'Nguyễn Văn An',
      phone: '0901234567',
      schedule: '14/11/2026 08:00 → 16/11/2026 08:00 (2 ngày)',
      delivery: 'Giao xe tận nơi • 120 Nguyễn Huệ, Q.1',
      status: 'approved'
    },
    {
      id: 'RH-8845',
      vehicle: 'VinFast VF 5 (Ô tô điện)',
      customer: 'Trần Thanh Bình',
      phone: '0901000002',
      schedule: '15/11/2026 09:00 → 17/11/2026 18:00 (2.5 ngày)',
      delivery: 'Nhận tại bãi xe • GreenRide Q.1',
      status: 'pending'
    },
    {
      id: 'RH-8835',
      vehicle: 'Dat Bike Weaver++ (Xe máy điện)',
      customer: 'Lê Kim Chi',
      phone: '0901000003',
      schedule: '13/11/2026 10:00 → 14/11/2026 10:00 (1 ngày)',
      delivery: 'Giao xe tận nơi • 45 Lê Lợi, Q.1',
      status: 'approved'
    },
    {
      id: 'RH-8820',
      vehicle: 'VinFast Klara S (Xe máy điện)',
      customer: 'Hoàng Minh Trí',
      phone: '0901000004',
      schedule: '14/11/2026 09:00 → 15/11/2026 09:00 (1 ngày)',
      delivery: 'Nhận tại cửa hàng • GreenRide Q.1',
      status: 'approved'
    }
  ];

    function getRealOrders() {
    // 1. Thử lấy từ Quản lý đơn hàng (store-orders.html)
    try {
      const raw = localStorage.getItem('ridehub_store_orders_v1');
      if (raw) {
        const list = JSON.parse(raw);
        if (Array.isArray(list) && list.length > 0) return list;
      }
    } catch (_) {}

    // 2. Thử lấy từ Đặt xe hệ thống
    try {
      const raw2 = localStorage.getItem('ridehub_bookings_db');
      if (raw2) {
        const list2 = JSON.parse(raw2);
        if (Array.isArray(list2) && list2.length > 0) return list2;
      }
    } catch (_) {}

    return mockOrders;
  }

  // 2. BẢN ĐỒ TỔNG HỢP SỰ KIỆN THEO NGÀY (Giao xe, Trả xe, Bảo dưỡng)
  function getCalendarEventsMap() {
    const map = {};
    const addEv = (dateKey, ev) => {
      if (!map[dateKey]) map[dateKey] = [];
      map[dateKey].push(ev);
    };

    // Bóc tách ngày giao & trả từ chuỗi schedule (dd/mm/yyyy)
    const activeOrders = getRealOrders();
    activeOrders.forEach((o) => {
      const matches = (o.schedule || '').match(/(\d{2})\/(\d{2})\/(\d{4})/g) || [];
      if (matches[0]) {
        const [d, m, y] = matches[0].split('/');
        addEv(`${y}-${m}-${d}`, {
          type: 'pickup',
          label: `Giao: ${o.vehicle.split('(')[0].trim()}`,
          title: `#${o.id} • Giao xe ${o.vehicle}`,
          detail: `Khách: ${o.customer} (${o.phone}) • ${o.delivery}`,
          time: '08:00 - 10:00',
          status: o.status === 'approved' ? 'Đã duyệt' : 'Chờ duyệt'
        });
      }
      if (matches[1]) {
        const [d, m, y] = matches[1].split('/');
        addEv(`${y}-${m}-${d}`, {
          type: 'return',
          label: `Trả: ${o.vehicle.split('(')[0].trim()}`,
          title: `#${o.id} • Nhận lại ${o.vehicle}`,
          detail: `Khách: ${o.customer} • Kiểm tra & hoàn tất đơn`,
          time: '18:00 - 20:00',
          status: o.status === 'approved' ? 'Đã lên lịch' : 'Chờ duyệt'
        });
      }
    });

    // Lịch bảo dưỡng & vệ sinh xe định kỳ (trích từ store-portal.html)
    addEv('2026-11-12', {
      type: 'maint',
      label: 'Vệ sinh: Dat Bike',
      title: 'Vệ sinh & kiểm tra pin • Dat Bike Weaver++',
      detail: 'Hoàn tất vệ sinh sạc pin trước 15:00 (FR-60)',
      time: '13:00 - 15:00',
      status: 'Đang thực hiện'
    });
    addEv('2026-11-18', {
      type: 'maint',
      label: 'Bảo dưỡng: Mazda 3',
      title: 'Bảo dưỡng định kỳ • Mazda 3 Sedan',
      detail: 'Kiểm tra phanh, thay nhớt & vệ sinh nội thất',
      time: '09:00 - 17:00',
      status: 'Bảo dưỡng'
    });

    return map;
  }

  // 3. RENDER LỊCH THÁNG (MONTH VIEW)
  function renderMonthView() {
    const grid = document.getElementById('calGrid');
    const titleEl = document.getElementById('calMonthTitle');
    const subTitleEl = document.getElementById('calSubTitle');
    if (!grid || !titleEl) return;

    titleEl.textContent = `Tháng ${calMonth + 1} / ${calYear}`;
    if (subTitleEl) subTitleEl.textContent = 'Theo dõi lịch giao xe, nhận lại xe và bảo dưỡng theo ngày';

    const evMap = getCalendarEventsMap();
    const firstDay = new Date(calYear, calMonth, 1).getDay(); // 0 = Chủ nhật, 1 = T2
    const offset = (firstDay + 6) % 7; // Mon = 0 .. Sun = 6
    const daysInMonth = new Date(calYear, calMonth + 1, 0).getDate();
    const todayKey = '2026-11-12';

    let html = '';
    for (let i = 0; i < offset; i++) {
      html += '<div class="rh-cal-cell is-empty"></div>';
    }

    for (let day = 1; day <= daysInMonth; day++) {
      const key = `${calYear}-${pad2(calMonth + 1)}-${pad2(day)}`;
      const evs = evMap[key] || [];
      const pills = evs
        .slice(0, 2)
        .map((ev) => `<span class="rh-cal-pill rh-cal-pill--${ev.type}">${ev.label}</span>`)
        .join('');
      const more =
        evs.length > 2
          ? `<span class="rh-cal-more">+${evs.length - 2}</span>`
          : '';

      html += `
        <button type="button" class="rh-cal-cell ${key === calSelectedKey ? 'is-selected' : ''} ${key === todayKey ? 'is-today' : ''}" data-cal-date="${key}">
          <span class="rh-cal-day">${day}</span>
          <div class="rh-cal-dots">${pills}${more}</div>
        </button>
      `;
    }

    grid.innerHTML = html;
    grid.querySelectorAll('[data-cal-date]').forEach((cell) => {
      cell.addEventListener('click', () => {
        calSelectedKey = cell.dataset.calDate;
        renderMonthView();
      });
    });

    renderSelectedDayEvents(evMap);
  }

  // 4. RENDER LỊCH TUẦN (WEEK VIEW GRID - 7 NGÀY)
  function renderWeekView() {
    const weekGrid = document.getElementById('weekGrid');
    const titleEl = document.getElementById('calMonthTitle');
    const subTitleEl = document.getElementById('calSubTitle');
    if (!weekGrid || !titleEl) return;

    const selDate = parseLocalDateKey(calSelectedKey);
    const dayOfWeek = selDate.getDay();
    const diffToMon = (dayOfWeek + 6) % 7;
    const monDate = new Date(selDate);
    monDate.setDate(selDate.getDate() - diffToMon);

    const sunDate = new Date(monDate);
    sunDate.setDate(monDate.getDate() + 6);

    titleEl.textContent = `Tuần: ${pad2(monDate.getDate())}/${pad2(monDate.getMonth() + 1)} → ${pad2(sunDate.getDate())}/${pad2(sunDate.getMonth() + 1)}/${sunDate.getFullYear()}`;
    if (subTitleEl) subTitleEl.textContent = 'Theo dõi phân bổ lịch xe theo các ngày trong tuần';

    const evMap = getCalendarEventsMap();
    const weekdaysName = ['Thứ 2', 'Thứ 3', 'Thứ 4', 'Thứ 5', 'Thứ 6', 'Thứ 7', 'Chủ nhật'];
    const todayKey = '2026-11-12';

    let html = '';
    for (let i = 0; i < 7; i++) {
      const d = new Date(monDate);
      d.setDate(monDate.getDate() + i);
      const key = `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
      const evs = evMap[key] || [];
      const evsHtml = evs.length
        ? evs
            .map(
              (ev) => `
            <div class="week-ev-card ${ev.type}">
              <strong style="color:var(--text-primary);">${ev.label}</strong>
              <span style="font-size:10px;color:var(--text-muted);">${ev.time}</span>
            </div>
          `
            )
            .join('')
        : '<span style="font-size:11px;color:var(--text-muted);text-align:center;margin-top:24px;">Trống lịch</span>';

      html += `
        <div class="week-day-col ${key === calSelectedKey ? 'is-active' : ''} ${key === todayKey ? 'is-today' : ''}" data-week-date="${key}">
          <div class="week-day-header">
            <div class="week-day-title">${weekdaysName[i]}</div>
            <div class="week-day-num">${pad2(d.getDate())}</div>
          </div>
          <div style="display:flex;flex-direction:column;gap:6px;flex:1;">
            ${evsHtml}
          </div>
        </div>
      `;
    }

    weekGrid.innerHTML = html;
    weekGrid.querySelectorAll('[data-week-date]').forEach((col) => {
      col.addEventListener('click', () => {
        calSelectedKey = col.dataset.weekDate;
        renderWeekView();
      });
    });

    renderSelectedDayEvents(evMap);
  }

  // 5. RENDER CHI TIẾT CÁC LỊCH XE TRONG NGÀY (CỘT PHẢI)
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
      listEl.innerHTML =
        '<div style="text-align:center;padding:32px 14px;color:var(--text-muted);font-size:13px;background:var(--bg-surface-soft);border-radius:14px;">Không có lịch giao nhận hay bảo dưỡng nào trong ngày này.</div>';
      return;
    }

    listEl.innerHTML = evs
      .map(
        (ev) => `
        <div class="event-detail-card">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px;">
            <strong style="font-size:13.5px;color:var(--text-primary);min-width:0;overflow-wrap:anywhere;">${ev.title}</strong>
            <span class="rh-cal-pill rh-cal-pill--${ev.type}" style="flex-shrink:0;">${ev.status}</span>
          </div>
          <div style="font-size:12.5px;color:var(--text-secondary);line-height:1.45;">${ev.detail}</div>
          <div style="font-size:11.5px;color:var(--text-muted);font-weight:600;">⏰ Thời gian dự kiến: ${ev.time}</div>
        </div>
      `
      )
      .join('');
  }

  // 6. GẮN SỰ KIỆN ĐIỀU HƯỚNG & CHUYỂN CHẾ ĐỘ XEM
  function initCalendarEvents() {
    const prevBtn = document.getElementById('calPrevBtn');
    const nextBtn = document.getElementById('calNextBtn');
    const todayBtn = document.getElementById('calTodayBtn');
    const viewMonthBtn = document.getElementById('viewMonthBtn');
    const viewWeekBtn = document.getElementById('viewWeekBtn');
    const monthViewWrapper = document.getElementById('monthViewWrapper');
    const weekViewWrapper = document.getElementById('weekViewWrapper');

    function refreshView() {
      if (currentMode === 'month') {
        renderMonthView();
      } else {
        renderWeekView();
      }
    }

    // Nút lùi tháng / tuần
    prevBtn?.addEventListener('click', () => {
      if (currentMode === 'month') {
        calMonth -= 1;
        if (calMonth < 0) {
          calMonth = 11;
          calYear -= 1;
        }
      } else {
        const cur = parseLocalDateKey(calSelectedKey);
        cur.setDate(cur.getDate() - 7);
        calSelectedKey = `${cur.getFullYear()}-${pad2(cur.getMonth() + 1)}-${pad2(cur.getDate())}`;
      }
      refreshView();
    });

    // Nút tiến tháng / tuần
    nextBtn?.addEventListener('click', () => {
      if (currentMode === 'month') {
        calMonth += 1;
        if (calMonth > 11) {
          calMonth = 0;
          calYear += 1;
        }
      } else {
        const cur = parseLocalDateKey(calSelectedKey);
        cur.setDate(cur.getDate() + 7);
        calSelectedKey = `${cur.getFullYear()}-${pad2(cur.getMonth() + 1)}-${pad2(cur.getDate())}`;
      }
      refreshView();
    });

    // Nút về ngày hiện tại
    todayBtn?.addEventListener('click', () => {
      calYear = 2026;
      calMonth = 10;
      calSelectedKey = '2026-11-14';
      refreshView();
    });

    // Chuyển sang chế độ Tháng
    viewMonthBtn?.addEventListener('click', () => {
      currentMode = 'month';
      viewMonthBtn.className = 'btn btn-primary';
      viewWeekBtn.className = 'btn btn-soft';
      monthViewWrapper.removeAttribute('hidden');
      weekViewWrapper.setAttribute('hidden', '');
      renderMonthView();
    });

    // Chuyển sang chế độ Tuần
    viewWeekBtn?.addEventListener('click', () => {
      currentMode = 'week';
      viewWeekBtn.className = 'btn btn-primary';
      viewMonthBtn.className = 'btn btn-soft';
      weekViewWrapper.removeAttribute('hidden');
      monthViewWrapper.setAttribute('hidden', '');
      renderWeekView();
    });
  }

  // Khởi động khi tải xong trang
  document.addEventListener('DOMContentLoaded', () => {
    initCalendarEvents();
    renderMonthView();
  });
})();