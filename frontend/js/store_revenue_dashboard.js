/* ==========================================================================
   RideHub / GreenRide — Dashboard Cửa Hàng & Báo Cáo Doanh Thu (JavaScript)
   Xử lý biểu đồ doanh thu theo Ngày/Tháng, thẻ KPI, bộ lọc, bảng đối soát
   và Tự động kết nối Backend FastAPI (/api/stores/{store_id}/revenue/report)
   ========================================================================== */

(function (global) {
  'use strict';

  // Cấu hình URL Backend FastAPI (tương thích port 8000 hoặc Live Server)
  const API_BASE_URL = window.CONFIG?.API_BASE_URL || 'http://127.0.0.1:8000/api';

  // =========================================================================
  // DỮ LIỆU MẪU (MOCK DATA FALLBACK KHI CHƯA KẾT NỐI SERVER)
  // =========================================================================

  // 1. Doanh thu theo ngày (Tháng 11/2026)
  const DAILY_REVENUE_DATA = [
    { label: '01/11', day: 1, car: 1200000, scooter: 750000, trips: 3 },
    { label: '02/11', day: 2, car: 1800000, scooter: 920000, trips: 4 },
    { label: '03/11', day: 3, car: 1500000, scooter: 840000, trips: 3 },
    { label: '04/11', day: 4, car: 900000, scooter: 600000, trips: 2 },
    { label: '05/11', day: 5, car: 2100000, scooter: 1100000, trips: 5 },
    { label: '06/11', day: 6, car: 1650000, scooter: 890000, trips: 4 },
    { label: '07/11', day: 7, car: 2400000, scooter: 1350000, trips: 5 },
    { label: '08/11', day: 8, car: 2700000, scooter: 1500000, trips: 6 },
    { label: '09/11', day: 9, car: 1950000, scooter: 1050000, trips: 4 },
    { label: '10/11', day: 10, car: 1400000, scooter: 800000, trips: 3 },
    { label: '11/11', day: 11, car: 1850000, scooter: 980000, trips: 4 },
    { label: '12/11', day: 12, car: 2200000, scooter: 1150000, trips: 5 },
    { label: '13/11', day: 13, car: 2600000, scooter: 1400000, trips: 6 },
    { label: '14/11', day: 14, car: 3100000, scooter: 1650000, trips: 7 },
    { label: '15/11', day: 15, car: 2250000, scooter: 1400000, trips: 5 } // Hôm nay
  ];

  // 2. Doanh thu theo 12 tháng (Năm 2026)
  const MONTHLY_REVENUE_DATA = [
    { label: 'T1', month: 1, car: 18500000, scooter: 12000000, trips: 42 },
    { label: 'T2', month: 2, car: 22000000, scooter: 14500000, trips: 48 }, // Tết Nguyên đán
    { label: 'T3', month: 3, car: 19800000, scooter: 13200000, trips: 45 },
    { label: 'T4', month: 4, car: 25400000, scooter: 16800000, trips: 56 }, // Lễ 30/4
    { label: 'T5', month: 5, car: 23100000, scooter: 15400000, trips: 52 },
    { label: 'T6', month: 6, car: 28900000, scooter: 18600000, trips: 63 }, // Mùa hè
    { label: 'T7', month: 7, car: 31500000, scooter: 19800000, trips: 68 },
    { label: 'T8', month: 8, car: 27600000, scooter: 17200000, trips: 59 },
    { label: 'T9', month: 9, car: 24500000, scooter: 15800000, trips: 54 },
    { label: 'T10', month: 10, car: 26800000, scooter: 17000000, trips: 58 },
    { label: 'T11', month: 11, car: 28217000, scooter: 20433000, trips: 58 }, // Tháng hiện tại
    { label: 'T12', month: 12, car: 34000000, scooter: 22000000, trips: 75 }  // Dự phóng Tết dương
  ];

  // 3. Top 5 xe sinh lời nhất
  const TOP_VEHICLES = [
    { name: 'VinFast VF 5 Plus', plate: '29A-899.23', days: 18, revenue: 16500000, rate: 90, type: 'Ô tô' },
    { name: 'VinFast Feliz S', plate: '59-K1 888.88', days: 24, revenue: 9800000, rate: 95, type: 'Xe máy' },
    { name: 'Dat Bike Weaver++', plate: '59-T2 678.90', days: 20, revenue: 8650000, rate: 86, type: 'Xe máy' },
    { name: 'VinFast Klara S', plate: '59-P1 345.67', days: 18, revenue: 7200000, rate: 78, type: 'Xe máy' },
    { name: 'VinFast Evo 200', plate: '59-V3 112.34', days: 19, revenue: 6500000, rate: 82, type: 'Xe máy' }
  ];

  // 4. Danh sách giao dịch đối soát chi tiết
  const TRANSACTIONS = [
    {
      id: 'RH-8830',
      date: '15/11/2026 14:20',
      vehicle: 'VinFast VF 5 Plus',
      customer: 'Trần Minh Quang',
      total: 1850000,
      platformFee: 185000,
      net: 1665000,
      deposit: '500.000đ (Đã hoàn)',
      status: 'settled',
      statusText: 'Đã giải ngân VietQR'
    },
    {
      id: 'RH-8828',
      date: '15/11/2026 11:45',
      vehicle: 'VinFast Feliz S',
      customer: 'Nguyễn Thu Trang',
      total: 320000,
      platformFee: 32000,
      net: 288000,
      deposit: 'Miễn cọc eKYC',
      status: 'settled',
      statusText: 'Đã giải ngân VietQR'
    },
    {
      id: 'RH-8825',
      date: '14/11/2026 17:30',
      vehicle: 'Dat Bike Weaver++',
      customer: 'Lê Kim Chi',
      total: 480000,
      platformFee: 48000,
      net: 432000,
      deposit: '300.000đ (Đang giữ)',
      status: 'holding_deposit',
      statusText: 'Đang giữ cọc'
    },
    {
      id: 'RH-8822',
      date: '14/11/2026 10:15',
      vehicle: 'VinFast Klara S',
      customer: 'Hoàng Minh Trí',
      total: 240000,
      platformFee: 24000,
      net: 216000,
      deposit: 'Miễn cọc eKYC',
      status: 'settled',
      statusText: 'Đã giải ngân VietQR'
    },
    {
      id: 'RH-8819',
      date: '13/11/2026 18:00',
      vehicle: 'VinFast VF 8 Plus',
      customer: 'Phạm Đức Duy',
      total: 2400000,
      platformFee: 240000,
      net: 2160000,
      deposit: '2.000.000đ (Đã hoàn)',
      status: 'pending_settle',
      statusText: 'Chờ giải ngân'
    },
    {
      id: 'RH-8815',
      date: '13/11/2026 09:10',
      vehicle: 'VinFast Feliz S',
      customer: 'Đặng Tuấn Kiệt',
      total: 320000,
      platformFee: 32000,
      net: 288000,
      deposit: 'Miễn cọc eKYC',
      status: 'settled',
      statusText: 'Đã giải ngân VietQR'
    },
    {
      id: 'RH-8810',
      date: '12/11/2026 16:40',
      vehicle: 'Dat Bike Weaver++',
      customer: 'Võ Thanh Tùng',
      total: 240000,
      platformFee: 24000,
      net: 216000,
      deposit: '300.000đ (Đã hoàn)',
      status: 'settled',
      statusText: 'Đã giải ngân VietQR'
    },
    {
      id: 'RH-8805',
      date: '12/11/2026 12:00',
      vehicle: 'VinFast VF 5 Plus',
      customer: 'Bùi Gia Huy',
      total: 1250000,
      platformFee: 125000,
      net: 1125000,
      deposit: '500.000đ (Đã hoàn)',
      status: 'pending_settle',
      statusText: 'Chờ giải ngân'
    }
  ];

  // Trạng thái hiện tại của Dashboard
  let currentViewMode = 'daily'; // 'daily' hoặc 'monthly'
  let currentCategoryFilter = 'all'; // 'all', 'scooter', 'car'
  let currentSearchQuery = '';
  let currentPayoutFilter = 'all';

  // Khởi tạo các thành phần giao diện
  function initDashboard() {
    initCountUpAnimation();
    renderRevenueChart();
    renderTopVehiclesTable();
    renderTransactionsTable();
    bindEventListeners();
  }

  // =========================================================================
  // 1. HIỆU ỨNG ĐẾM SỐ (COUNT-UP ANIMATION)
  // =========================================================================
  function initCountUpAnimation() {
    document.querySelectorAll('[data-countup]').forEach((el) => {
      animateCountUp(el);
    });
  }

  function animateCountUp(el) {
    const target = parseFloat(el.dataset.countup || '0');
    const suffix = el.dataset.suffix || '';
    const dur = 1200;
    const start = performance.now();

    const step = (now) => {
      const p = Math.min((now - start) / dur, 1);
      const ease = 1 - Math.pow(1 - p, 3);
      const cur = target * ease;

      if (target >= 1000) {
        el.textContent = Math.round(cur).toLocaleString('vi-VN') + suffix;
      } else if (Number.isInteger(target)) {
        el.textContent = Math.round(cur) + suffix;
      } else {
        el.textContent = cur.toFixed(1) + suffix;
      }

      if (p < 1) {
        requestAnimationFrame(step);
      }
    };
    requestAnimationFrame(step);
  }

  // =========================================================================
  // 2. VẼ BIỂU ĐỒ DOANH THU TƯƠNG TÁC (INTERACTIVE SVG REVENUE CHART)
  // =========================================================================
  function renderRevenueChart() {
    const svg = document.getElementById('revenueChartSvg');
    if (!svg) return;

    const data = currentViewMode === 'daily' ? DAILY_REVENUE_DATA : MONTHLY_REVENUE_DATA;
    const filter = currentCategoryFilter;

    // Cập nhật tiêu đề biểu đồ
    const titleEl = document.getElementById('chartTitle');
    const subtitleEl = document.getElementById('chartSubtitle');
    if (titleEl) {
      titleEl.textContent = currentViewMode === 'daily'
        ? 'Biểu đồ doanh thu theo Ngày — Tháng 11/2026'
        : 'Biểu đồ doanh thu 12 Tháng — Năm 2026';
    }
    if (subtitleEl) {
      subtitleEl.textContent = currentViewMode === 'daily'
        ? 'Rê chuột hoặc chạm vào từng cột/điểm để xem chi tiết doanh thu xe máy, ô tô điện và số cuốc hoàn tất.'
        : 'Phân tích xu hướng tăng trưởng doanh thu theo từng tháng trong năm 2026.';
    }

    // Kích thước canvas SVG
    const width = 960;
    const height = 340;
    const padding = { top: 35, right: 30, bottom: 45, left: 65 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    // Tìm giá trị max để scale trục Y
    let maxVal = 0;
    data.forEach((d) => {
      let val = 0;
      if (filter === 'all') val = d.car + d.scooter;
      else if (filter === 'car') val = d.car;
      else if (filter === 'scooter') val = d.scooter;
      if (val > maxVal) maxVal = val;
    });

    // Làm tròn maxVal lên mốc đẹp
    maxVal = maxVal > 0 ? Math.ceil(maxVal / 1000000) * 1000000 : 5000000;
    if (currentViewMode === 'monthly') {
      maxVal = Math.max(maxVal, 60000000);
    } else {
      maxVal = Math.max(maxVal, 5000000);
    }

    let svgHtml = '';

    // Lưới ngang & Nhãn trục Y (4 mốc)
    const ySteps = 4;
    for (let i = 0; i <= ySteps; i++) {
      const yVal = (maxVal / ySteps) * i;
      const yPos = padding.top + chartHeight - (chartHeight / ySteps) * i;
      
      // Đường lưới ngang
      svgHtml += `
        <line x1="${padding.left}" y1="${yPos}" x2="${width - padding.right}" y2="${yPos}" 
          stroke="${i === 0 ? '#cbd5e1' : '#e2e8f0'}" stroke-width="${i === 0 ? 1.5 : 1}" stroke-dasharray="${i === 0 ? '0' : '4 4'}" />
      `;

      // Nhãn trục Y
      let labelText = '';
      if (yVal >= 1000000) {
        labelText = (yVal / 1000000).toFixed(yVal % 1000000 === 0 ? 0 : 1) + ' Tr';
      } else if (yVal === 0) {
        labelText = '0đ';
      } else {
        labelText = (yVal / 1000) + 'k';
      }

      svgHtml += `
        <text x="${padding.left - 10}" y="${yPos + 4}" fill="#64748b" font-size="11" font-weight="700" text-anchor="end" font-family="Plus Jakarta Sans">
          ${labelText}
        </text>
      `;
    }

    // Tính toán tọa độ các cột và điểm đường xu hướng
    const stepX = chartWidth / data.length;
    const barWidth = Math.max(14, Math.min(36, stepX * 0.58));
    const trendPoints = [];

    data.forEach((item, index) => {
      const centerX = padding.left + index * stepX + stepX / 2;
      const barX = centerX - barWidth / 2;

      let carVal = filter === 'scooter' ? 0 : item.car;
      let scooterVal = filter === 'car' ? 0 : item.scooter;
      let totalVal = carVal + scooterVal;

      const carHeight = (carVal / maxVal) * chartHeight;
      const scooterHeight = (scooterVal / maxVal) * chartHeight;
      const totalHeight = carHeight + scooterHeight;

      const scooterY = padding.top + chartHeight - scooterHeight;
      const carY = scooterY - carHeight;
      const totalY = padding.top + chartHeight - totalHeight;

      trendPoints.push({ x: centerX, y: totalY, data: item, total: totalVal });

      // Nhãn trục X
      svgHtml += `
        <text x="${centerX}" y="${height - padding.bottom + 22}" fill="#475569" font-size="11.5" font-weight="700" text-anchor="middle" font-family="Plus Jakarta Sans">
          ${item.label}
        </text>
      `;

      // Cột Bar Chart (gồm phần ô tô và phần xe máy)
      svgHtml += `
        <g class="chart-bar-group" 
           data-tip-label="${item.label}" 
           data-tip-car="${carVal.toLocaleString('vi-VN')}đ" 
           data-tip-scooter="${scooterVal.toLocaleString('vi-VN')}đ" 
           data-tip-total="${totalVal.toLocaleString('vi-VN')}đ" 
           data-tip-trips="${item.trips}">
          <!-- Nền bắt hover rộng toàn cột -->
          <rect x="${centerX - stepX / 2}" y="${padding.top}" width="${stepX}" height="${chartHeight}" fill="transparent" />
          
          <!-- Cột Xe máy điện (Bên dưới) -->
          ${scooterHeight > 0 ? `
            <rect x="${barX}" y="${scooterY}" width="${barWidth}" height="${scooterHeight}" 
              rx="${carHeight > 0 ? 0 : 4}" fill="#4ade80" />
          ` : ''}

          <!-- Cột Ô tô điện (Chồng lên trên) -->
          ${carHeight > 0 ? `
            <rect x="${barX}" y="${carY}" width="${barWidth}" height="${carHeight}" 
              rx="4" fill="#16a34a" />
          ` : ''}
        </g>
      `;
    });

    // Vẽ đường cong Spline xu hướng (Trend Line)
    if (trendPoints.length > 1) {
      let pathD = `M ${trendPoints[0].x} ${trendPoints[0].y}`;
      for (let i = 0; i < trendPoints.length - 1; i++) {
        const p0 = trendPoints[i];
        const p1 = trendPoints[i + 1];
        const cx1 = (p0.x + p1.x) / 2;
        const cy1 = p0.y;
        const cx2 = (p0.x + p1.x) / 2;
        const cy2 = p1.y;
        pathD += ` C ${cx1} ${cy1}, ${cx2} ${cy2}, ${p1.x} ${p1.y}`;
      }

      svgHtml += `
        <path d="${pathD}" fill="none" stroke="#f59e0b" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />
      `;

      // Các điểm node tròn trên đường xu hướng
      trendPoints.forEach((pt) => {
        svgHtml += `
          <circle class="chart-point" cx="${pt.x}" cy="${pt.y}" r="4" fill="#ffffff" stroke="#f59e0b" stroke-width="2.5" 
            data-tip-label="${pt.data.label}" 
            data-tip-car="${pt.data.car.toLocaleString('vi-VN')}đ" 
            data-tip-scooter="${pt.data.scooter.toLocaleString('vi-VN')}đ" 
            data-tip-total="${pt.total.toLocaleString('vi-VN')}đ" 
            data-tip-trips="${pt.data.trips}" />
        `;
      });
    }

    svg.innerHTML = svgHtml;
    attachChartTooltipEvents();
  }

  // =========================================================================
  // 3. XỬ LÝ TOOLTIP BIỂU ĐỒ (FLOATING HOVER TOOLTIP)
  // =========================================================================
  function attachChartTooltipEvents() {
    const tooltip = document.getElementById('revenueChartTooltip');
    if (!tooltip) return;

    const interactiveEls = document.querySelectorAll('.chart-bar-group, .chart-point');

    interactiveEls.forEach((el) => {
      el.addEventListener('mouseenter', () => {
        const label = el.dataset.tipLabel;
        const car = el.dataset.tipCar;
        const scooter = el.dataset.tipScooter;
        const total = el.dataset.tipTotal;
        const trips = el.dataset.tipTrips;

        tooltip.innerHTML = `
          <div style="font-weight:800;border-bottom:1px solid rgba(255,255,255,0.2);padding-bottom:4px;margin-bottom:4px;">
            ${currentViewMode === 'daily' ? 'Ngày ' : 'Tháng '}${label}
          </div>
          <div>🚗 Ô tô: <strong>${car}</strong></div>
          <div>🛵 Xe máy: <strong>${scooter}</strong></div>
          <div style="margin-top:2px;color:#86efac;">💰 Tổng thu: <strong>${total}</strong></div>
          <div style="font-size:11px;color:#cbd5e1;">📋 Hoàn tất: <strong>${trips} cuốc</strong></div>
        `;
        tooltip.style.opacity = '1';
      });

      el.addEventListener('mousemove', (e) => {
        tooltip.style.left = (e.clientX + 14) + 'px';
        tooltip.style.top = (e.clientY - 20) + 'px';
      });

      el.addEventListener('mouseleave', () => {
        tooltip.style.opacity = '0';
      });
    });
  }

  // =========================================================================
  // 4. RENDER BẢNG TOP XE SINH LỜI
  // =========================================================================
  function renderTopVehiclesTable() {
    const tbody = document.getElementById('topVehiclesTableBody');
    if (!tbody) return;

    let html = '';
    TOP_VEHICLES.forEach((v, index) => {
      html += `
        <tr>
          <td>
            <div style="display:flex;align-items:center;gap:8px;">
              <span style="width:20px;height:20px;border-radius:50%;background:${index === 0 ? '#16a34a' : 'var(--bg-surface-soft)'};color:${index === 0 ? '#fff' : 'var(--text-secondary)'};font-weight:800;font-size:11px;display:grid;place-items:center;">
                ${index + 1}
              </span>
              <div>
                <strong style="color:var(--text-primary);display:block;">${v.name}</strong>
                <span style="font-size:11.5px;color:var(--text-muted);">${v.plate} • ${v.type}</span>
              </div>
            </div>
          </td>
          <td><strong>${v.days}</strong> ngày</td>
          <td><strong style="color:var(--green-700);">${v.revenue.toLocaleString('vi-VN')}đ</strong></td>
          <td>
            <span class="status-badge status-badge--available" style="font-size:11px;">
              ${v.rate}%
            </span>
          </td>
        </tr>
      `;
    });
    tbody.innerHTML = html;
  }

  // =========================================================================
  // 5. RENDER BẢNG GIAO DỊCH ĐỐI SOÁT PAYOS VIETQR
  // =========================================================================
  function renderTransactionsTable() {
    const tbody = document.getElementById('transactionTableBody');
    const countEl = document.getElementById('tableRecordCount');
    if (!tbody) return;

    let filtered = TRANSACTIONS.filter((t) => {
      // Lọc trạng thái
      if (currentPayoutFilter !== 'all' && t.status !== currentPayoutFilter) {
        return false;
      }
      // Lọc tìm kiếm
      if (currentSearchQuery) {
        const q = currentSearchQuery.toLowerCase();
        return (
          t.id.toLowerCase().includes(q) ||
          t.vehicle.toLowerCase().includes(q) ||
          t.customer.toLowerCase().includes(q)
        );
      }
      return true;
    });

    if (countEl) {
      countEl.innerHTML = `Hiển thị <strong>${filtered.length}</strong> trên tổng số <strong>${TRANSACTIONS.length}</strong> giao dịch`;
    }

    if (filtered.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="10" style="text-align:center;padding:28px;color:var(--text-muted);">
            Không tìm thấy giao dịch đối soát nào phù hợp với bộ lọc.
          </td>
        </tr>
      `;
      return;
    }

    let html = '';
    filtered.forEach((t) => {
      let badgeClass = 'status-badge--settled';
      if (t.status === 'pending_settle') badgeClass = 'status-badge--pending';
      if (t.status === 'holding_deposit') badgeClass = 'status-badge--holding';

      html += `
        <tr>
          <td><strong style="color:var(--green-800);">${t.id}</strong></td>
          <td style="color:var(--text-secondary);font-size:12px;">${t.date}</td>
          <td><strong>${t.vehicle}</strong></td>
          <td>${t.customer}</td>
          <td>${t.total.toLocaleString('vi-VN')}đ</td>
          <td style="color:#dc2626;">-${t.platformFee.toLocaleString('vi-VN')}đ</td>
          <td><strong style="color:var(--green-700);">${t.net.toLocaleString('vi-VN')}đ</strong></td>
          <td style="color:var(--text-muted);font-size:12px;">${t.deposit}</td>
          <td>
            <span class="status-badge ${badgeClass}">${t.statusText}</span>
          </td>
          <td>
            <button class="btn btn-soft btn-sm" type="button" onclick="showReceiptToast('${t.id}')">
              Biên lai
            </button>
          </td>
        </tr>
      `;
    });

    tbody.innerHTML = html;
  }

  // =========================================================================
  // 6. GẮN CÁC SỰ KIỆN TƯƠNG TÁC
  // =========================================================================
  function bindEventListeners() {
    // 1. Chuyển đổi chế độ xem: Theo Ngày vs Theo Tháng
    const dailyBtn = document.getElementById('viewDailyBtn');
    const monthlyBtn = document.getElementById('viewMonthlyBtn');

    if (dailyBtn && monthlyBtn) {
      dailyBtn.addEventListener('click', () => {
        currentViewMode = 'daily';
        dailyBtn.classList.add('is-active');
        monthlyBtn.classList.remove('is-active');
        renderRevenueChart();
        loadRevenueDataFromBackend(1, 'day');
      });

      monthlyBtn.addEventListener('click', () => {
        currentViewMode = 'monthly';
        monthlyBtn.classList.add('is-active');
        dailyBtn.classList.remove('is-active');
        renderRevenueChart();
        loadRevenueDataFromBackend(1, 'month');
      });
    }

    // 2. Lọc theo khoảng thời gian nhanh
    const quickFilters = document.querySelectorAll('#dateQuickFilters .btn');
    quickFilters.forEach((btn) => {
      btn.addEventListener('click', () => {
        quickFilters.forEach((b) => b.classList.remove('is-active'));
        btn.classList.add('is-active');
        const range = btn.dataset.range;
        if (range === 'this_year') {
          currentViewMode = 'monthly';
          if (monthlyBtn) monthlyBtn.classList.add('is-active');
          if (dailyBtn) dailyBtn.classList.remove('is-active');
          loadRevenueDataFromBackend(1, 'month');
        } else {
          currentViewMode = 'daily';
          if (dailyBtn) dailyBtn.classList.add('is-active');
          if (monthlyBtn) monthlyBtn.classList.remove('is-active');
          loadRevenueDataFromBackend(1, 'day');
        }
        renderRevenueChart();
      });
    });

    // 3. Lọc theo loại phương tiện (Ô tô vs Xe máy)
    const catFilter = document.getElementById('vehicleCategoryFilter');
    if (catFilter) {
      catFilter.addEventListener('change', (e) => {
        currentCategoryFilter = e.target.value;
        renderRevenueChart();
      });
    }

    // 4. Tìm kiếm trong bảng giao dịch
    const searchInput = document.getElementById('transactionSearchInput');
    if (searchInput) {
      searchInput.addEventListener('input', (e) => {
        currentSearchQuery = e.target.value.trim();
        renderTransactionsTable();
      });
    }

    // 5. Lọc trạng thái PayOS trong bảng
    const statusSelect = document.getElementById('payoutStatusFilter');
    if (statusSelect) {
      statusSelect.addEventListener('change', (e) => {
        currentPayoutFilter = e.target.value;
        renderTransactionsTable();
      });
    }

    // 6. Mở và đóng Modal Rút tiền PayOS
    const openPayoutBtn = document.getElementById('openPayoutModalBtn');
    const closePayoutBtn = document.getElementById('closePayoutModalBtn');
    const payoutModal = document.getElementById('payoutModal');
    const withdrawAllBtn = document.getElementById('withdrawAllBtn');
    const payoutInput = document.getElementById('payoutAmountInput');
    const confirmPayoutBtn = document.getElementById('confirmPayoutBtn');

    if (openPayoutBtn && payoutModal) {
      openPayoutBtn.addEventListener('click', () => {
        payoutModal.classList.add('is-open');
      });
    }

    if (closePayoutBtn && payoutModal) {
      closePayoutBtn.addEventListener('click', () => {
        payoutModal.classList.remove('is-open');
      });
    }

    if (withdrawAllBtn && payoutInput) {
      withdrawAllBtn.addEventListener('click', () => {
        payoutInput.value = '43785000';
      });
    }

    if (confirmPayoutBtn && payoutModal) {
      confirmPayoutBtn.addEventListener('click', () => {
        const val = parseInt(payoutInput.value || '0', 10);
        if (val < 100000) {
          alert('Số tiền rút tối thiểu là 100.000 VNĐ.');
          return;
        }
        payoutModal.classList.remove('is-open');
      });
    }

    // 7. Xuất file báo cáo CSV
    const exportBtn = document.getElementById('exportReportBtn');
    if (exportBtn) {
      exportBtn.addEventListener('click', exportRevenueReportCSV);
    }
  }

  // =========================================================================
  // 7. HÀM XUẤT BÁO CÁO CSV (UTF-8 BOM HỖ TRỢ TIẾNG VIỆT TRÊN EXCEL)
  // =========================================================================
  function exportRevenueReportCSV() {
    let csv = '\uFEFFMã đơn,Thời gian,Phương tiện,Khách thuê,Tổng tiền thuê,Phí sàn 10%,Thực nhận,Tiền cọc,Trạng thái\n';
    
    TRANSACTIONS.forEach((t) => {
      csv += `"${t.id}","${t.date}","${t.vehicle}","${t.customer}","${t.total}","${t.platformFee}","${t.net}","${t.deposit}","${t.statusText}"\n`;
    });

    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `Bao_Cao_Doanh_Thu_GreenRide_Q1_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

  }

  // =========================================================================
  // 8. KẾT NỐI API BACKEND FASTAPI (TỰ ĐỘNG ĐỒNG BỘ DỮ LIỆU THẬT)
  // =========================================================================
  async function loadRevenueDataFromBackend(storeId = 1, period = 'day') {
    try {
      const token = localStorage.getItem('ridehub_token') || localStorage.getItem('access_token');
      const headers = { 'Content-Type': 'application/json' };
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const response = await fetch(`${API_BASE_URL}/stores/${storeId}/revenue/report?period=${period}&limit_top_vehicles=5`, {
        method: 'GET',
        headers: headers
      });

      if (!response.ok) {
        console.warn('Backend chưa phản hồi hoặc chưa đăng nhập, sử dụng dữ liệu mẫu.');
        return false;
      }

      const resData = await response.json();
      console.log('✅ Đã nhận dữ liệu doanh thu từ Backend:', resData);

      // 1. Cập nhật thẻ KPI
      if (resData.summary) {
        const gross = Number(resData.summary.total_revenue || 0);
        const net = Math.round(gross * 0.9);
        const fee = Math.round(gross * 0.1);

        const grossEl = document.getElementById('statGrossRevenue');
        if (grossEl) grossEl.textContent = gross.toLocaleString('vi-VN') + 'đ';

        const netRevEl = document.getElementById('statNetRevenue');
        if (netRevEl) netRevEl.textContent = net.toLocaleString('vi-VN') + 'đ';

        const feeEl = document.getElementById('statPlatformFee');
        if (feeEl) feeEl.textContent = fee.toLocaleString('vi-VN') + 'đ';

        const ordersEl = document.getElementById('statCompletedTrips');
        if (ordersEl) ordersEl.textContent = (resData.summary.completed_orders || 0) + ' cuốc';

        const avgEl = document.getElementById('statAov');
        if (avgEl) avgEl.textContent = Number(resData.summary.avg_order_value || 0).toLocaleString('vi-VN') + 'đ';
      }

      // 2. Map dữ liệu timeline vào biểu đồ SVG
      if (resData.timeline && resData.timeline.length > 0) {
        const mappedData = resData.timeline.map((item) => {
          let label = item.time_bucket;
          if (label.includes('-')) {
            const parts = label.split('-');
            if (parts.length === 3) label = `${parts[2]}/${parts[1]}`;
            else if (parts.length === 2) label = `T${parseInt(parts[1], 10)}`;
          }
          const total = Number(item.rental_revenue || 0) + Number(item.delivery_revenue || 0);
          return {
            label: label,
            car: Math.round(total * 0.6),
            scooter: Math.round(total * 0.4),
            trips: item.completed_orders || 0
          };
        });

        if (period === 'day') {
          DAILY_REVENUE_DATA.splice(0, DAILY_REVENUE_DATA.length, ...mappedData);
        } else {
          MONTHLY_REVENUE_DATA.splice(0, MONTHLY_REVENUE_DATA.length, ...mappedData);
        }
        renderRevenueChart();
      }

      // 3. Map Top xe vào bảng
      if (resData.top_vehicles && resData.top_vehicles.length > 0) {
        const mappedVehicles = resData.top_vehicles.map((v) => ({
          name: `${v.brand} ${v.model}`,
          plate: v.plate_number,
          days: v.rental_count,
          revenue: Number(v.total_revenue || 0),
          rate: Math.min(100, Math.round((v.rental_count / 20) * 100)),
          type: v.vehicle_type === 'car' ? 'Ô tô' : 'Xe máy'
        }));
        TOP_VEHICLES.splice(0, TOP_VEHICLES.length, ...mappedVehicles);
        renderTopVehiclesTable();
      }

      return true;

    } catch (error) {
      console.warn('Lỗi kết nối API Backend:', error);
      return false;
    }
  }

  // =========================================================================
  // 9. TIỆN ÍCH TOAST THÔNG BÁO
  // =========================================================================
  function showToast(message) {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.innerHTML = `<span>🔔</span> <span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transition = 'opacity 0.25s ease';
      setTimeout(() => toast.remove(), 250);
    }, 3200);
  }

  global.showReceiptToast = function (orderId) {
  };

  // Tự động khởi chạy khi DOM sẵn sàng
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      initDashboard();
      loadRevenueDataFromBackend(1, currentViewMode);
    });
  } else {
    initDashboard();
    loadRevenueDataFromBackend(1, currentViewMode);
  }

})(window);