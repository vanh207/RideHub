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
    const deposit = Math.round(total * 0.3);
    byId('detailPriceBreakdown').textContent = `${data.formatCurrency(vehicle.price)} × ${days} ngày + Giao nhận ${data.formatCurrency(deliveryFee)} + Tiện ích ${data.formatCurrency(addons)}`;
    byId('detailTotalPrice').textContent = data.formatCurrency(total);
    byId('detailDeposit').textContent = `Cọc 30%: ${data.formatCurrency(deposit)} • Còn lại ${data.formatCurrency(total - deposit)}`;
  }

  function openOwnerModal() {
    byId('ownerModalAvatar').textContent = owner.initials;
    byId('ownerModalName').textContent = owner.name;
    byId('ownerModalStats').textContent = `★ ${owner.rating} • ${owner.trips} • ${owner.response}`;
    byId('ownerModalAddr').textContent = owner.addr;
    const fleet = data.getOwnerFleet(owner);
    byId('ownerFleetList').innerHTML = fleet.length
      ? fleet.map((item) => `
          <a class="detail-owner-fleet-item" href="vehicle-detail.html?id=${encodeURIComponent(item.id)}">
            <div>
              <div class="detail-owner-fleet-name">${item.name}</div>
              <div class="detail-owner-fleet-specs">${item.transmission} • ${item.fuel} • ${item.seats}</div>
            </div>
            <div class="detail-owner-fleet-price">${data.formatCurrency(item.price)}/ngày</div>
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

  function proceedBooking() {
    const specs = Array.from(document.querySelectorAll('#detailChips .meta-chip')).map((chip) => chip.textContent.trim()).join(' • ');
    const isDelivery = byId('btnDelivery').classList.contains('btn-primary');
    const deliveryMode = isDelivery ? 'Giao xe tận nơi' : 'Tôi tự đến lấy xe';
    const deliveryAddress = isDelivery
      ? (byId('deliveryAddressInput').value.trim() || 'Địa chỉ giao tận nơi (Quận 1)')
      : byId('pickupAddressNote').textContent.replace('Nhận tại:', '').trim();
    const addons = Array.from(document.querySelectorAll('.addon-chk:checked')).map((checkbox) => checkbox.parentElement.textContent.trim());
    const totalText = byId('detailTotalPrice').textContent;
    const totalNum = Number(totalText.replace(/\D/g, '')) || 0;
    const depositNum = Math.round(totalNum * 0.3);

    const draft = {
      orderCode: 'RH-' + Math.floor(100000 + Math.random() * 899999),
      vehicleId: vehicle.id,
      vehicle: vehicle.name,
      specs,
      schedule: byId('detailScheduleInput').value,
      deliveryMode,
      deliveryAddress,
      deliveryFee,
      addons,
      breakdown: byId('detailPriceBreakdown').textContent,
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
