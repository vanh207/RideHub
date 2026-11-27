(function () {
  'use strict';

  const data = window.RideHubData;
  if (!data) return;

  const params = new URLSearchParams(window.location.search);
  const vehicleId = params.get('id');
  const scheduleParam = params.get('schedule');
  const vehicle = data.getVehicleById(vehicleId);

  let picker = null;
  let owner = null;
  let deliveryFee = 0;
  let currentDays = 3;
  let selectedDepositType = 'CASH'; // 'CASH' | 'VEHICLE_PLEDGE'

  function byId(id) {
    return document.getElementById(id);
  }

  function toast(message, isError) {
    if (window.showRideHubToast) window.showRideHubToast(message, isError);
  }

  function getDescription(currentVehicle) {
    if (currentVehicle.type === 'car') {
      return 'Xe ô tô bảo dưỡng định kỳ chính hãng, nội thất sạch sẽ, vận hành êm ái phù hợp đi phố và đường dài.';
    }
    return 'Xe chạy êm, tiết kiệm năng lượng, đã kiểm tra phanh và lốp trước mỗi chuyến đi.';
  }

  function getAmenities(currentVehicle) {
    if (currentVehicle.type === 'car') {
      return '<span class="meta-chip">Bluetooth</span><span class="meta-chip">Camera lùi</span><span class="meta-chip">GPS</span><span class="meta-chip">Cổng USB</span>';
    }
    return '<span class="meta-chip">Cốp rộng</span><span class="meta-chip">2 nón bảo hiểm</span><span class="meta-chip">Áo mưa</span><span class="meta-chip">Khóa Smartkey</span>';
  }

  function getCollateral(currentVehicle) {
    if (currentVehicle.type === 'car') {
      return '3.000.000đ tiền mặt hoặc xe máy kèm cà vẹt gốc (miễn nếu eKYC Đạt).';
    }
    return '500.000đ tiền cọc giữ xe (hoặc miễn thế chấp khi eKYC Đạt).';
  }

  function showNotFound() {
    byId('detailNotFound').hidden = false;
    byId('detailContent').hidden = true;
  }

  function renderVehicle() {
    owner = data.getOwnerForVehicle(vehicle);
    document.title = `${vehicle.name} — RideHub`;
    byId('detailBreadcrumbName').textContent = vehicle.name;
    byId('detailTitle').textContent = vehicle.name;
    byId('detailImageBox').innerHTML = data.getVehicleSvg(vehicle);
    byId('detailChips').innerHTML = `
      <span class="meta-chip">${vehicle.category}</span>
      <span class="meta-chip">${vehicle.transmission}</span>
      <span class="meta-chip">${vehicle.fuel}</span>
      <span class="meta-chip">${vehicle.seats}</span>
    `;
    byId('detailAddress').textContent = vehicle.address;
    byId('detailRating').textContent = `★ ${vehicle.rating}`;
    byId('detailTrips').textContent = vehicle.trips;
    byId('detailBasePrice').textContent = data.formatCurrency(vehicle.price);
    byId('detailDesc').textContent = getDescription(vehicle);
    byId('detailAmenities').innerHTML = getAmenities(vehicle);
    byId('detailCollateral').textContent = getCollateral(vehicle);
    byId('detailOwnerAvatar').textContent = owner.initials;
    byId('detailOwnerInfo').textContent = owner.name;
    byId('detailOwnerStat').innerHTML = `<span class="vehicle-rating">★ ${owner.rating}</span><span class="vehicle-trips">${owner.trips}</span>`;
    byId('pickupAddressNote').textContent = `Nhận tại: ${vehicle.address}`;
    byId('detailContent').hidden = false;
    byId('detailNotFound').hidden = true;
  }

  function updateSchedule(payload) {
    currentDays = payload.days;
    byId('detailScheduleInput').value = payload.rangeText;
    byId('detailDurationText').textContent = payload.durationText;
    recalcTotal();
  }

  function recalcTotal() {
    const days = Math.max(1, currentDays);
    let addons = 0;
    document.querySelectorAll('.addon-chk:checked').forEach((checkbox) => {
      const price = Number(checkbox.dataset.price || 0);
      addons += checkbox.dataset.perday === '1' ? price * days : price;
    });
    const total = vehicle.price * days + deliveryFee + addons;
    const deposit = selectedDepositType === 'VEHICLE_PLEDGE' ? 0 : Math.round(total * 0.3);
    byId('detailPriceBreakdown').textContent = `${data.formatCurrency(vehicle.price)} × ${days} ngày + Giao nhận ${data.formatCurrency(deliveryFee)} + Tiện ích ${data.formatCurrency(addons)}`;
    byId('detailTotalPrice').textContent = data.formatCurrency(total);
    if (selectedDepositType === 'VEHICLE_PLEDGE') {
      byId('detailDeposit').textContent = `Thế chấp xe tại trạm (0đ cọc online) • Thanh toán ${data.formatCurrency(total)} khi nhận xe`;
    } else {
      byId('detailDeposit').textContent = `Cọc 30%: ${data.formatCurrency(deposit)} • Còn lại ${data.formatCurrency(total - deposit)}`;
    }
  }

  function setDepositType(type) {
    selectedDepositType = type === 'VEHICLE_PLEDGE' ? 'VEHICLE_PLEDGE' : 'CASH';
    document.querySelectorAll('#depositOptionGroup .deposit-option-card').forEach((card) => {
      const active = card.dataset.depositType === selectedDepositType;
      card.style.borderColor = active ? '#16a34a' : '#d5e7dc';
      card.style.background = active ? '#f0fdf4' : '#ffffff';
      const radio = card.querySelector('input[type="radio"]');
      if (radio) radio.checked = active;
    });
    const wrap = byId('collateralVehicleWrap');
    if (wrap) wrap.hidden = selectedDepositType !== 'VEHICLE_PLEDGE';
    recalcTotal();
  }

  function openOwnerModal() {
    byId('ownerModalAvatar').textContent = owner.initials;
    byId('ownerModalName').textContent = owner.name;
    byId('ownerModalStats').textContent = `★ ${owner.rating} • ${owner.trips} • ${owner.response}`;
    byId('ownerModalAddr').textContent = owner.addr;

    const chatBtn = byId('ownerChatLinkBtn');
    if (chatBtn) {
      chatBtn.href = `chat.html?owner=${encodeURIComponent(owner.name)}&initials=${encodeURIComponent(owner.initials)}&addr=${encodeURIComponent(owner.addr)}`;
    }

    const fleet = data.getOwnerFleet(owner);
    byId('ownerFleetList').innerHTML = fleet.length
      ? fleet.map((item) => `
          <a href="vehicle-detail.html?id=${encodeURIComponent(item.id)}" class="panel-card" style="padding:14px;display:flex;flex-direction:column;gap:10px;border:1px solid var(--green-100);box-shadow:0 4px 14px rgba(15,23,42,0.04);text-decoration:none;color:inherit;box-sizing:border-box;">
            <div style="border-radius:12px;overflow:hidden;position:relative;background:#f0fdf4;">
              ${data.getVehicleSvg(item)}
              <span class="status-badge status-badge--available" style="position:absolute;top:8px;left:8px;font-size:11px;">Sẵn sàng</span>
            </div>
            <div style="flex:1;">
              <div style="font-weight:800;font-size:15px;color:var(--text-primary);margin-bottom:4px;">${item.name}</div>
              <div style="font-size:12.5px;color:var(--text-secondary);">${item.transmission} • ${item.fuel} • ${item.seats}</div>
            </div>
            <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;padding-top:10px;border-top:1px solid var(--green-100);">
              <span style="font-size:12px;color:var(--text-muted);">★ ${item.rating || '4.8'} • ${item.trips || '100+ chuyến'}</span>
              <strong style="color:var(--green-700);font-size:14.5px;white-space:nowrap;">${data.formatCurrency(item.price)}/ngày</strong>
            </div>
          </a>
        `).join('')
      : '<div class="detail-owner-fleet-specs">Chủ xe chưa có phương tiện khác.</div>';

    byId('ownerProfileModal').classList.add('is-open');
  }

  function setDelivery(mode) {
    const selfButton = byId('btnSelfPickup');
    const deliveryButton = byId('btnDelivery');
    const isDelivery = mode === 'delivery';
    deliveryFee = isDelivery ? 30000 : 0;
    selfButton.className = isDelivery ? 'btn btn-soft detail-delivery-btn' : 'btn btn-primary detail-delivery-btn';
    deliveryButton.className = isDelivery ? 'btn btn-primary detail-delivery-btn' : 'btn btn-soft detail-delivery-btn';
    byId('pickupAddressNote').hidden = isDelivery;
    byId('deliveryAddressWrap').hidden = !isDelivery;
    recalcTotal();
  }

  function getRentalStart() {
    const state = picker.getState();
    const pad = (value) => String(value).padStart(2, '0');
    return `${state.year}-${pad(state.month + 1)}-${pad(state.startDay)}T${state.pickupHour}:00`;
  }

  function toDateTime(year, month, day, time) {
    const pad = (value) => String(value).padStart(2, '0');
    const [hour, minute] = time.split(':').map(Number);
    const date = new Date(year, month, day, hour, minute, 0, 0);
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:00`;
  }

  async function proceedBooking() {
    const button = byId('proceedBookingBtn');
    const vehTotal = byId('detailTotalPrice')?.textContent?.trim() || '';
    if (window.AuthRBAC && typeof window.AuthRBAC.confirmAction === 'function') {
      const ok = await window.AuthRBAC.confirmAction({
        title: 'Xác nhận thuê xe',
        message: `Bạn có chắc chắn muốn đặt thuê <strong>${vehicle.name}</strong>${vehTotal ? ` (tổng dự kiến <strong>${vehTotal}</strong>)` : ''} không?`,
        confirmText: 'Xác nhận thuê xe',
        cancelText: 'Xem lại',
      });
      if (!ok) return;
    }
    const eligibilityMessage = byId('bookingEligibilityMessage');
    button.disabled = true;
    window.RideHubBookingEligibility.clearMessage(eligibilityMessage);
    try {
      const vehicleType = vehicle.type === 'car' ? 'CAR' : 'MOTORBIKE';
      const result = await window.RideHubBookingEligibility.check(vehicleType, getRentalStart());
      if (!result.eligible) {
        window.RideHubBookingEligibility.showReasons(eligibilityMessage, result.reasons);
        return;
      }
    } catch (error) {
      console.error('[RideHub] Không thể kiểm tra điều kiện thuê:', error);
      window.RideHubBookingEligibility.showError(
        eligibilityMessage,
        `Không thể kiểm tra điều kiện thuê: ${error.message}`
      );
      return;
    } finally {
      button.disabled = false;
    }

    const scheduleState = picker.getState();
    if (!scheduleState.endDay) {
      toast('Vui lòng chọn ngày trả xe trước khi tiếp tục.', true);
      return;
    }

    const specs = Array.from(document.querySelectorAll('#detailChips .meta-chip')).map((chip) => chip.textContent.trim()).join(' • ');
    const isDelivery = byId('btnDelivery').classList.contains('btn-primary');
    const deliveryMode = isDelivery ? 'Giao xe tận nơi' : 'Tôi tự đến lấy xe';
    const deliveryAddress = isDelivery
      ? (byId('deliveryAddressInput').value.trim() || 'Địa chỉ giao tận nơi (Quận 1)')
      : byId('pickupAddressNote').textContent.replace('Nhận tại:', '').trim();
    const addons = Array.from(document.querySelectorAll('.addon-chk:checked')).map((checkbox) => checkbox.parentElement.textContent.trim());
    const totalText = byId('detailTotalPrice').textContent;
    const totalNum = Number(totalText.replace(/\D/g, '')) || 0;
    const isPledge = selectedDepositType === 'VEHICLE_PLEDGE';
    let collateralInfo = '';
    if (isPledge) {
      const colType = byId('collateralVehicleType')?.value || 'Xe máy';
      const colName = (byId('collateralVehicleName')?.value || '').trim();
      const colDocs = (byId('collateralDocs')?.value || 'Cà vẹt gốc + CCCD').trim();
      if (!colName) {
        toast('Vui lòng nhập tên xe và biển số xe thế chấp trước khi tiếp tục.', true);
        byId('collateralVehicleName')?.focus();
        return;
      }
      collateralInfo = `${colType}: ${colName} (${colDocs})`;
    }
    const depositNum = isPledge ? 0 : Math.round(totalNum * 0.3);

    const draft = {
      orderCode: 'RH-' + Math.floor(100000 + Math.random() * 899999),
      vehicleId: vehicle.id,
      vehicle: vehicle.name,
      specs,
      schedule: byId('detailScheduleInput').value,
      startTime: toDateTime(scheduleState.year, scheduleState.month, scheduleState.startDay, scheduleState.pickupHour),
      endTime: toDateTime(scheduleState.year, scheduleState.month, scheduleState.endDay, scheduleState.returnHour),
      deliveryMode,
      deliveryAddress,
      deliveryFee,
      addons,
      breakdown: byId('detailPriceBreakdown').textContent,
      depositType: selectedDepositType,
      collateralInfo,
      totalNum,
      depositNum,
      remainNum: totalNum - depositNum,
      totalText
    };
    localStorage.setItem('ridehub_checkout_draft', JSON.stringify(draft));
    window.location.href = 'booking.html';
  }

  function bindEvents() {
    byId('detailOwnerCard').addEventListener('click', openOwnerModal);
    byId('detailOwnerCard').addEventListener('keydown', (event) => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault();
      openOwnerModal();
    });

    byId('btnSelfPickup').addEventListener('click', () => setDelivery('self'));
    byId('btnDelivery').addEventListener('click', () => setDelivery('delivery'));
    document.querySelectorAll('input[name="depositType"]').forEach((radio) => {
      radio.addEventListener('change', (e) => setDepositType(e.target.value));
    });
    document.querySelectorAll('.addon-chk').forEach((checkbox) => checkbox.addEventListener('change', recalcTotal));
    byId('proceedBookingBtn').addEventListener('click', proceedBooking);

    byId('detailScheduleInput').addEventListener('input', (event) => {
      if (picker) picker.syncFromText(event.target.value);
    });
  }

  function init() {
    if (!vehicle) {
      showNotFound();
      return;
    }

    renderVehicle();
    bindEvents();

    picker = window.RideHubDateTimePicker.mount({
      triggerIds: ['openDetailDateTimeBtn'],
      onChange: updateSchedule
    });

    if (scheduleParam && picker.syncFromText(scheduleParam)) {
      toast('Đã áp dụng khung thời gian từ trang tìm kiếm.');
    }

    recalcTotal();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
