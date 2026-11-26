/* ==========================================================================
   RIDEHUB GOOGLE MAPS & GEOLOCATION COMPONENT (geo-map.js)
   - Nhúng Google Maps iframe vào các khu vực chọn địa điểm / giao nhận / hồ sơ
   - Hỗ trợ nút "Lấy vị trí hiện tại" qua navigator.geolocation + Reverse Geocoding
   ========================================================================== */
(function (global) {
  'use strict';

  const buildEmbedUrl = (query) => {
    const q = (query || 'TP. Hồ Chí Minh, Việt Nam').trim();
    return `https://maps.google.com/maps?q=${encodeURIComponent(q)}&t=&z=15&ie=UTF8&iwloc=&output=embed`;
  };

  const notify = (msg, type = 'success') => {
    if (typeof global.showRideHubToast === 'function') {
      global.showRideHubToast(msg, type);
    }
  };

  async function reverseGeocode(lat, lng) {
    try {
      const res = await fetch(
        `https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lng)}&accept-language=vi`
      );
      if (res.ok) {
        const data = await res.json();
        if (data && data.display_name) {
          return data.display_name;
        }
      }
    } catch (_) {}
    return `${lat.toFixed(6)}, ${lng.toFixed(6)}`;
  }

  function requestCurrentLocation(onSuccess, btnEl) {
    if (!navigator.geolocation) {
      notify('Trình duyệt của bạn không hỗ trợ định vị GPS.', 'error');
      return;
    }
    const origText = btnEl ? btnEl.textContent : '';
    if (btnEl) {
      btnEl.disabled = true;
      btnEl.textContent = 'Đang lấy vị trí...';
    }
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const lat = pos.coords.latitude;
        const lng = pos.coords.longitude;
        const address = await reverseGeocode(lat, lng);
        if (btnEl) {
          btnEl.disabled = false;
          btnEl.textContent = origText;
        }
        notify('Đã cập nhật vị trí hiện tại của bạn!');
        onSuccess({ lat, lng, address, coordsQuery: `${lat},${lng}` });
      },
      (err) => {
        if (btnEl) {
          btnEl.disabled = false;
          btnEl.textContent = origText;
        }
        const msg =
          err && err.code === 1
            ? 'Vui lòng cấp quyền truy cập vị trí trên trình duyệt.'
            : 'Không thể xác định vị trí hiện tại. Vui lòng thử lại.';
        notify(msg, 'error');
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 30000 }
    );
  }

  function createMapContainer(id, initialQuery) {
    const wrap = document.createElement('div');
    wrap.id = id;
    wrap.style.cssText =
      'margin-top:10px;border-radius:12px;overflow:hidden;border:1px solid #bbf7d0;background:#f8fafc;';
    wrap.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between;padding:6px 10px;background:#ecfdf5;border-bottom:1px solid #d1fae5;font-size:12px;color:#15803d;font-weight:700;">
        <span>Bản đồ Google Maps</span>
        <a class="rh-gmap-ext" href="https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(initialQuery || 'TP. Hồ Chí Minh')}" target="_blank" rel="noopener" style="color:#15803d;text-decoration:none;">Mở Google Maps ↗</a>
      </div>
      <iframe
        title="Bản đồ vị trí RideHub"
        src="${buildEmbedUrl(initialQuery)}"
        style="width:100%;height:200px;border:0;display:block;"
        loading="lazy"
        referrerpolicy="no-referrer-when-downgrade"
      ></iframe>
    `;
    return wrap;
  }

  function updateMapContainer(wrap, query) {
    if (!wrap) return;
    const iframe = wrap.querySelector('iframe');
    const extLink = wrap.querySelector('.rh-gmap-ext');
    if (iframe) iframe.src = buildEmbedUrl(query);
    if (extLink) {
      extLink.href = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query || 'TP. Hồ Chí Minh')}`;
    }
  }

  function attachInputWithMap(inputEl, options = {}) {
    if (!inputEl || inputEl.dataset.rhGeoAttached === '1') return null;
    inputEl.dataset.rhGeoAttached = '1';

    const btnWrap = document.createElement('div');
    btnWrap.style.cssText = 'display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:8px;';

    const geoBtn = document.createElement('button');
    geoBtn.type = 'button';
    geoBtn.className = 'btn btn-soft';
    geoBtn.style.cssText = 'min-height:34px;padding:5px 12px;font-size:12px;';
    geoBtn.textContent = 'Lấy vị trí hiện tại';

    const toggleMapBtn = document.createElement('button');
    toggleMapBtn.type = 'button';
    toggleMapBtn.className = 'btn btn-soft';
    toggleMapBtn.style.cssText = 'min-height:34px;padding:5px 12px;font-size:12px;';
    toggleMapBtn.textContent = options.defaultMapOpen ? 'Ẩn bản đồ' : 'Xem trên Google Maps';

    btnWrap.appendChild(geoBtn);
    btnWrap.appendChild(toggleMapBtn);

    const mapWrap = createMapContainer(
      `rhMap_${inputEl.id || Math.random().toString(36).slice(2, 7)}`,
      inputEl.value.trim() || options.fallbackQuery || 'TP. Hồ Chí Minh'
    );
    mapWrap.hidden = !options.defaultMapOpen;

    const anchor = options.mountAfter || inputEl;
    anchor.insertAdjacentElement('afterend', mapWrap);
    anchor.insertAdjacentElement('afterend', btnWrap);

    let debounceTimer = null;
    inputEl.addEventListener('input', () => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        const q = inputEl.value.trim();
        if (q) updateMapContainer(mapWrap, q);
      }, 450);
    });

    geoBtn.addEventListener('click', () => {
      requestCurrentLocation(({ address, coordsQuery }) => {
        inputEl.value = address;
        inputEl.dispatchEvent(new Event('input', { bubbles: true }));
        inputEl.dispatchEvent(new Event('change', { bubbles: true }));
        mapWrap.hidden = false;
        toggleMapBtn.textContent = 'Ẩn bản đồ';
        updateMapContainer(mapWrap, coordsQuery);
      }, geoBtn);
    });

    toggleMapBtn.addEventListener('click', () => {
      mapWrap.hidden = !mapWrap.hidden;
      toggleMapBtn.textContent = mapWrap.hidden ? 'Xem trên Google Maps' : 'Ẩn bản đồ';
      if (!mapWrap.hidden) {
        updateMapContainer(mapWrap, inputEl.value.trim() || options.fallbackQuery || 'TP. Hồ Chí Minh');
      }
    });

    return { mapWrap, geoBtn, toggleMapBtn };
  }

  function initBookingPickupMap() {
    const pickupNote = document.getElementById('pickupAddressNote');
    const delWrap = document.getElementById('deliveryAddressWrap');
    const delInput = document.getElementById('deliveryAddressInput');
    if (!pickupNote || !delWrap || !delInput) return;

    // Gắn bản đồ ngay bên dưới khối chọn địa điểm nhận/giao xe
    if (!document.getElementById('rhBookingLocationMap')) {
      const initialAddr =
        pickupNote.textContent.replace('Nhận tại:', '').trim() || 'Quận 1, TP. Hồ Chí Minh';
      const mapWrap = createMapContainer('rhBookingLocationMap', initialAddr);
      delWrap.insertAdjacentElement('afterend', mapWrap);

      // Nút lấy vị trí hiện tại cho giao xe tận nơi
      if (!delWrap.querySelector('.rh-geo-btn')) {
        const geoBtn = document.createElement('button');
        geoBtn.type = 'button';
        geoBtn.className = 'btn btn-soft rh-geo-btn';
        geoBtn.style.cssText = 'min-height:34px;padding:5px 12px;font-size:12px;margin-top:8px;';
        geoBtn.textContent = 'Lấy vị trí hiện tại';
        delWrap.appendChild(geoBtn);

        geoBtn.addEventListener('click', () => {
          requestCurrentLocation(({ address, coordsQuery }) => {
            delInput.value = address;
            delInput.dispatchEvent(new Event('input', { bubbles: true }));
            updateMapContainer(mapWrap, coordsQuery);
          }, geoBtn);
        });
      }

      let timer = null;
      delInput.addEventListener('input', () => {
        clearTimeout(timer);
        timer = setTimeout(() => {
          const val = delInput.value.trim();
          if (val) updateMapContainer(mapWrap, val);
        }, 450);
      });

      document.getElementById('btnSelfPickup')?.addEventListener('click', () => {
        const addr = pickupNote.textContent.replace('Nhận tại:', '').trim() || 'TP. Hồ Chí Minh';
        updateMapContainer(mapWrap, addr);
      });
      document.getElementById('btnDelivery')?.addEventListener('click', () => {
        const val = delInput.value.trim();
        if (val) updateMapContainer(mapWrap, val);
      });

      // Theo dõi thay đổi text của pickupNote khi mở modal xe khác nhau
      const obs = new MutationObserver(() => {
        if (!pickupNote.hidden) {
          const addr = pickupNote.textContent.replace('Nhận tại:', '').trim();
          if (addr) updateMapContainer(mapWrap, addr);
        }
      });
      obs.observe(pickupNote, { childList: true, characterData: true, subtree: true });
    }
  }

  function initHeroSearchLocation() {
    const heroInput = document.getElementById('heroLocationInput');
    if (!heroInput || heroInput.dataset.rhGeoAttached === '1') return;
    heroInput.dataset.rhGeoAttached = '1';

    const fieldWrap = heroInput.closest('.search-field') || heroInput.parentElement;
    if (!fieldWrap) return;

    const actionRow = document.createElement('div');
    actionRow.style.cssText = 'display:flex;gap:8px;margin-top:6px;flex-wrap:wrap;';

    const geoBtn = document.createElement('button');
    geoBtn.type = 'button';
    geoBtn.className = 'btn btn-soft';
    geoBtn.style.cssText = 'min-height:28px;padding:3px 10px;font-size:11.5px;border-radius:999px;';
    geoBtn.textContent = 'Lấy vị trí hiện tại';

    const mapBtn = document.createElement('button');
    mapBtn.type = 'button';
    mapBtn.className = 'btn btn-soft';
    mapBtn.style.cssText = 'min-height:28px;padding:3px 10px;font-size:11.5px;border-radius:999px;';
    mapBtn.textContent = 'Google Maps';

    actionRow.appendChild(geoBtn);
    actionRow.appendChild(mapBtn);
    fieldWrap.appendChild(actionRow);

    const searchCard = heroInput.closest('.hero-search-card') || fieldWrap.parentElement;
    const mapWrap = createMapContainer('rhHeroSearchMap', heroInput.value.trim() || 'TP. Hồ Chí Minh');
    mapWrap.hidden = true;
    searchCard?.insertAdjacentElement('afterend', mapWrap);

    geoBtn.addEventListener('click', () => {
      requestCurrentLocation(({ address, coordsQuery }) => {
        heroInput.value = address;
        mapWrap.hidden = false;
        updateMapContainer(mapWrap, coordsQuery);
      }, geoBtn);
    });

    mapBtn.addEventListener('click', () => {
      mapWrap.hidden = !mapWrap.hidden;
      if (!mapWrap.hidden) {
        updateMapContainer(mapWrap, heroInput.value.trim() || 'TP. Hồ Chí Minh');
      }
    });
  }

  function initProfileMaps() {
    const profAddr = document.getElementById('profAddrIn');
    if (profAddr) {
      attachInputWithMap(profAddr, { defaultMapOpen: false, fallbackQuery: 'TP. Hồ Chí Minh' });
    }
    const storeAddr = document.getElementById('storeAddressInput');
    if (storeAddr) {
      attachInputWithMap(storeAddr, { defaultMapOpen: false, fallbackQuery: 'TP. Hồ Chí Minh' });
    }
  }

  function initAll() {
    initHeroSearchLocation();
    initBookingPickupMap();
    initProfileMaps();
  }

  global.RideHubGeoMap = { initAll, attachInputWithMap, requestCurrentLocation, updateMapContainer };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll);
  } else {
    initAll();
  }
})(window);
