(function () {
  'use strict';

  const data = window.RideHubData;
  if (!data) return;

  const ITEMS_PER_PAGE = 9;
  const state = {
    page: 1,
    type: 'all',
    city: 'TP. Hồ Chí Minh',
    priceMax: 2000000,
    fuelEco: false,
    transAuto: false,
    transManual: false,
    sort: 'featured',
    schedule: '',
    days: 3
  };

  let picker = null;

  function byId(id) {
    return document.getElementById(id);
  }

  function toast(message, isError) {
    if (window.showRideHubToast) window.showRideHubToast(message, isError);
  }

  function matchesCity(vehicle, city) {
    if (!city) return true;
    if (city.indexOf('Hồ Chí Minh') !== -1) {
      return /HCM|Hồ Chí Minh/i.test(vehicle.address);
    }
    return vehicle.address.toLowerCase().indexOf(city.toLowerCase()) !== -1;
  }

  function readFilters() {
    state.city = byId('cityFilter').value;
    state.type = document.querySelector('input[name="vType"]:checked')?.value || 'all';
    state.priceMax = Number(byId('priceFilter').value);
    state.fuelEco = byId('chkFuelEco').checked;
    state.transAuto = byId('chkTransAuto').checked;
    state.transManual = byId('chkTransManual').checked;
    state.sort = byId('sortResults').value;
  }

  function sortVehicles(list) {
    const result = list.slice();
    if (state.sort === 'price-asc') return result.sort((a, b) => a.price - b.price);
    if (state.sort === 'price-desc') return result.sort((a, b) => b.price - a.price);
    if (state.sort === 'rating') return result.sort((a, b) => Number(b.rating) - Number(a.rating));
    return result;
  }

  function getFilteredVehicles() {
    const filtered = data.VEHICLES.filter((vehicle) => {
      if (state.type !== 'all' && vehicle.type !== state.type) return false;
      if (!matchesCity(vehicle, state.city)) return false;
      if (vehicle.price > state.priceMax) return false;
      if (state.fuelEco && vehicle.fuel.indexOf('Điện') === -1) return false;
      if (state.transAuto || state.transManual) {
        const isAuto = vehicle.transmission.indexOf('tự động') !== -1;
        const isManual = vehicle.transmission.indexOf('Xe số') !== -1 || vehicle.transmission.indexOf('côn tay') !== -1;
        if (!((state.transAuto && isAuto) || (state.transManual && isManual))) return false;
      }
      return true;
    });
    return sortVehicles(filtered);
  }

  function navigateToDetail(vehicleId) {
    const params = new URLSearchParams({ id: vehicleId });
    if (state.schedule) params.set('schedule', state.schedule);
    window.location.href = 'vehicle-detail.html?' + params.toString();
  }

  function renderCard(vehicle) {
    const favorite = data.isFavorite(vehicle);
    return `
      <article class="vehicle-card spotlight-card search-vehicle-card" tabindex="0" role="link" data-vehicle-id="${vehicle.id}" aria-label="Xem chi tiết ${vehicle.name}">
        <div class="vehicle-card-media">
          ${data.getVehicleSvg(vehicle)}
          <button type="button" class="fav-heart-btn ${favorite ? 'is-liked' : ''}" data-favorite-id="${vehicle.id}" aria-label="Thêm vào xe yêu thích">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M12 21s-7-4.5-9-9a5.5 5.5 0 0 1 9-5.5A5.5 5.5 0 0 1 21 12c-2 4.5-9 9-9 9z"/></svg>
          </button>
        </div>
        <div class="badge-row">
          <span class="status-badge status-badge--available">
            <span class="status-dot status-dot-pulse"></span>
            <span>Sẵn sàng</span>
          </span>
          <div class="vehicle-stats-row">
            <span class="vehicle-rating">★ ${vehicle.rating}</span>
            <span class="vehicle-trips">${vehicle.trips}</span>
          </div>
        </div>
        <h3 class="vehicle-card-title">${vehicle.name}</h3>
        <div class="vehicle-meta-chips">
          <span class="meta-chip">${vehicle.transmission}</span>
          <span class="meta-chip">${vehicle.fuel}</span>
          <span class="meta-chip">${vehicle.seats}</span>
        </div>
        <div class="vehicle-address">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 21s-6-5.5-6-11a6 6 0 1 1 12 0c0 5.5-6 11-6 11z"/><circle cx="12" cy="10" r="2.2"/></svg>
          <span>${vehicle.address}</span>
        </div>
        <div class="vehicle-card-price-row">
          <div class="vehicle-card-price">
            <strong>${data.formatCurrency(vehicle.price)}</strong><span>/ngày</span>
          </div>
          <a class="vehicle-card-detail-link" href="vehicle-detail.html?id=${encodeURIComponent(vehicle.id)}">Chi tiết →</a>
        </div>
      </article>
    `;
  }

  function bindCard(card) {
    card.addEventListener('click', (event) => {
      if (event.target.closest('.fav-heart-btn, a')) return;
      navigateToDetail(card.dataset.vehicleId);
    });
    card.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      if (event.target.closest('.fav-heart-btn, a')) return;
      event.preventDefault();
      navigateToDetail(card.dataset.vehicleId);
    });
  }

  function bindFavorite(button) {
    button.addEventListener('click', (event) => {
      event.stopPropagation();
      const vehicle = data.getVehicleById(button.dataset.favoriteId);
      if (!vehicle) return;
      const added = data.toggleFavorite(vehicle);
      button.classList.toggle('is-liked', added);
      toast(added ? `Đã thêm ${vehicle.name} vào Xe yêu thích!` : `Đã bỏ thích ${vehicle.name}`);
    });
  }

  function renderPagination(totalPages, totalItems) {
    const numbers = byId('paginationNumbers');
    const prevButton = byId('prevPageBtn');
    const nextButton = byId('nextPageBtn');
    const info = byId('paginationInfo');
    const pagination = byId('vehiclesPagination');

    if (pagination) pagination.hidden = totalItems === 0;
    if (info) info.textContent = `Trang ${state.page} / ${totalPages} (${totalItems} xe)`;

    if (prevButton) {
      prevButton.disabled = state.page <= 1;
      prevButton.onclick = () => {
        if (state.page <= 1) return;
        state.page -= 1;
        renderVehicles();
        window.scrollTo({ top: 380, behavior: 'smooth' });
      };
    }

    if (nextButton) {
      nextButton.disabled = state.page >= totalPages;
      nextButton.onclick = () => {
        if (state.page >= totalPages) return;
        state.page += 1;
        renderVehicles();
        window.scrollTo({ top: 380, behavior: 'smooth' });
      };
    }

    if (numbers) {
      let html = '';
      for (let page = 1; page <= totalPages; page++) {
        const active = page === state.page;
        html += `<button type="button" class="btn ${active ? 'btn-primary' : 'btn-soft'}" data-go-page="${page}">${page}</button>`;
      }
      numbers.innerHTML = html;
      numbers.querySelectorAll('[data-go-page]').forEach((button) => {
        button.addEventListener('click', () => {
          state.page = Number(button.dataset.goPage);
          renderVehicles();
          window.scrollTo({ top: 380, behavior: 'smooth' });
        });
      });
    }
  }

  function renderVehicles() {
    const grid = byId('vehiclesGrid');
    const emptyState = byId('emptyState');
    const filtered = getFilteredVehicles();
    const totalPages = Math.ceil(filtered.length / ITEMS_PER_PAGE) || 1;
    if (state.page > totalPages) state.page = totalPages;
    if (state.page < 1) state.page = 1;

    const startIndex = (state.page - 1) * ITEMS_PER_PAGE;
    const pageItems = filtered.slice(startIndex, startIndex + ITEMS_PER_PAGE);

    grid.innerHTML = pageItems.map(renderCard).join('');
    grid.querySelectorAll('.search-vehicle-card').forEach(bindCard);
    grid.querySelectorAll('[data-favorite-id]').forEach(bindFavorite);
    grid.hidden = filtered.length === 0;

    if (emptyState) emptyState.hidden = filtered.length !== 0;

    const count = byId('resultsCount');
    if (count) count.textContent = `${filtered.length} phương tiện`;

    renderPagination(totalPages, filtered.length);
  }

  function updateSchedule(payload) {
    state.schedule = payload.rangeText;
    state.days = payload.days;
    const input = byId('filterScheduleInput');
    const duration = byId('filterDurationText');
    const summary = byId('resultsDateSummary');
    if (input) input.value = payload.rangeText;
    if (duration) duration.textContent = payload.durationText;
    if (summary) summary.textContent = payload.rangeText;
  }

  function resetFilters() {
    byId('cityFilter').value = 'TP. Hồ Chí Minh';
    byId('priceFilter').value = '2000000';
    byId('priceCapLabel').textContent = '2.000.000đ';
    byId('chkFuelEco').checked = false;
    byId('chkTransAuto').checked = false;
    byId('chkTransManual').checked = false;
    byId('sortResults').value = 'featured';
    const allType = document.querySelector('input[name="vType"][value="all"]');
    if (allType) allType.checked = true;
    state.page = 1;
    readFilters();
    renderVehicles();
    toast('Đã đặt lại bộ lọc.');
  }

  function initGuestBanner() {
    const user = window.AuthRBAC ? window.AuthRBAC.getCurrentUser() : null;
    const banner = byId('guestInviteBanner');
    if (!banner || user || localStorage.getItem('rh_hide_guest_banner') === '1') return;
    banner.hidden = false;
    byId('dismissGuestBanner')?.addEventListener('click', () => {
      banner.hidden = true;
      localStorage.setItem('rh_hide_guest_banner', '1');
    });
  }

  function init() {
    initGuestBanner();

    const initialParams = new URLSearchParams(window.location.search);
    const initialType = initialParams.get('type');
    if (initialType === 'moto' || initialType === 'car') {
      const radio = document.querySelector(`input[name="vType"][value="${initialType}"]`);
      if (radio) radio.checked = true;
    }

    picker = window.RideHubDateTimePicker.mount({
      triggerIds: ['openFilterDateTimeBtn'],
      onChange: updateSchedule
    });

    const initialSchedule = initialParams.get('schedule');
    if (initialSchedule) picker.syncFromText(initialSchedule);

    byId('filterScheduleInput')?.addEventListener('input', (event) => {
      state.schedule = event.target.value;
      const summary = byId('resultsDateSummary');
      if (summary) summary.textContent = event.target.value;
      if (picker) picker.syncFromText(event.target.value);
    });

    byId('priceFilter')?.addEventListener('input', (event) => {
      const value = Number(event.target.value);
      state.priceMax = value;
      byId('priceCapLabel').textContent = data.formatCurrency(value);
    });

    document.querySelectorAll('input[name="vType"]').forEach((radio) => {
      radio.addEventListener('change', () => {
        state.type = radio.value;
        state.page = 1;
        renderVehicles();
      });
    });

    byId('sortResults')?.addEventListener('change', (event) => {
      state.sort = event.target.value;
      state.page = 1;
      renderVehicles();
    });

    byId('applyFilterBtn')?.addEventListener('click', () => {
      const loader = byId('filterLoader');
      const grid = byId('vehiclesGrid');
      readFilters();
      state.page = 1;
      loader.hidden = false;
      grid.style.opacity = '0.4';
      setTimeout(() => {
        loader.hidden = true;
        grid.style.opacity = '1';
        renderVehicles();
        toast(`Tìm thấy ${getFilteredVehicles().length} phương tiện khả dụng!`);
      }, 500);
    });

    byId('resetFiltersBtn')?.addEventListener('click', resetFilters);

    readFilters();
    renderVehicles();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
