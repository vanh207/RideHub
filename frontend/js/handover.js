// =============================================================================
// handover.js — Biên bản Giao/Nhận xe | RideHub
// Task: TF1B2C3 | Sprint 2 | Hạn: 19/11/2026
// =============================================================================

'use strict';

// ─────────────────────────────────────────────────────────────────────────────
// CONFIG — Tất cả hằng số tiền/đơn giá đặt tập trung ở đây
// ─────────────────────────────────────────────────────────────────────────────
const HO_CONFIG = {
  MAX_PHOTOS: 20,
  MAX_FILE_SIZE_MB: 5,
  ALLOWED_TYPES: ['image/jpeg', 'image/png', 'image/webp'],
  FUEL_PRICE_PER_LEVEL: 80_000,   // VNĐ / mức xăng (1/4 bình)
  CLEANING_FEE: 150_000,           // VNĐ — phí vệ sinh xe bẩn
  OVERTIME_RATE_PER_HOUR: 50_000, // VNĐ / giờ quá giờ
  DRAFT_KEY: 'rh_handover_draft_v1',
  API_BASE_URL: (typeof CONFIG !== 'undefined' && CONFIG.API_BASE_URL) ? CONFIG.API_BASE_URL : 'http://127.0.0.1:8000/api',
};

function getAuthToken() {
  try {
    const keys = ['ridehub_auth_token', 'ridehub_token', 'access_token', 'token'];
    for (const k of keys) {
      const v = localStorage.getItem(k);
      if (v) return v;
    }
    const match = document.cookie.match(/(?:^|;\s*)(?:ridehub_token|access_token|token)=([^;]+)/);
    if (match && match[1]) return decodeURIComponent(match[1]);
  } catch (_) {}
  return '';
}

const FUEL_LEVELS = ['E', '1/4', '2/4', '3/4', 'FULL'];
const FUEL_SEGS = 4; // số đoạn trên thanh xăng (0 → 4 đoạn)
const FUEL_IDX = { 'E': 0, '1/4': 1, '2/4': 2, '3/4': 3, 'FULL': 4 };

// ─────────────────────────────────────────────────────────────────────────────
// MOCK DATA — Đánh dấu rõ: chỉ dùng trong demo, thay bằng API call khi có backend
// ─────────────────────────────────────────────────────────────────────────────
const MOCK_CONTRACT = {
  contractId: 'HD-2026-08842',
  licensePlate: '51G-888.42',
  brand: 'VinFast',
  model: 'VF 5 Plus',
  year: 2024,
  color: 'Trắng Ngọc',
  chassisNo: '...X842',      // rút gọn
  engineNo: '...A991',       // rút gọn
  registrationExp: '15/06/2027',
  insuranceExp: '20/03/2027',
  kmPerDayLimit: 200,
  overKmFee: 3_500,          // VNĐ/km
  deposit: 5_000_000,        // VNĐ
  baseDeposit: 5_000_000,    // Tiền cọc gốc theo hợp đồng (để khôi phục nếu đổi lại CASH/COMBINED)
  depositType: 'CASH',       // 'CASH' | 'VEHICLE_PLEDGE' | 'COMBINED'
  collateralInfo: '',        // Thông tin xe thế chấp
  collateralHeld: false,     // Đã nhận giữ xe thế chấp tại trạm
  collateralOutHandler: '',  // Nhân viên tiếp nhận thế chấp
  collateralOutTime: '',     // Thời gian tiếp nhận
  collateralOutCustConfirmed: false, // Khách xác nhận giao tài sản
  collateralReturned: false, // Đã trả lại xe thế chấp lúc check-in
  collateralInHandler: '',   // Nhân viên bàn giao trả tài sản
  collateralInTime: '',      // Thời gian bàn giao trả
  collateralInCustConfirmed: false, // Khách xác nhận đã nhận lại tài sản
  rentDays: 2,
  pricePerDay: 937_500,
  customerName: 'Trần Thanh Bình',
  customerPhone: '0901000002',
  customerCCCD: '079200012345',
  customerLicense: 'B2 — 0790123456',
  staffName: 'Kim Cương',
  staffId: 'NV-021',
  stationName: 'GreenRide Q.1',
  pickupAddr: 'Nhận tại cửa hàng • GreenRide Q.1',
  returnAddr: 'Nhận tại cửa hàng • GreenRide Q.1',
};

// ─────────────────────────────────────────────────────────────────────────────
// STATE — single source of truth
// ─────────────────────────────────────────────────────────────────────────────
let state = {
  activeTab: 'checkout',   // 'checkout' | 'checkin'
  contract: { ...MOCK_CONTRACT },

  checkout: {
    datetime: '',
    odo: '',
    fuel: 'FULL',
    photos: [],         // [{id, file, url, label, note, required}]
    checklist: [],      // populated from CHECKLIST_ITEMS
    damages: [],        // [{id, x, y, type, severity, note, age:'old'}]
    signedDocPhotos: [], // [{id, file, url, name}]
    customerName: MOCK_CONTRACT.customerName,
    staffName: MOCK_CONTRACT.staffName,
    note: '',
  },
  checkin: {
    datetime: '',
    odo: '',
    fuel: 'FULL',
    photos: [],
    checklist: [],
    damages: [],        // age:'new' for new damages found on return
    signedDocPhotos: [], // [{id, file, url, name}]
    customerName: MOCK_CONTRACT.customerName,
    staffName: MOCK_CONTRACT.staffName,
    note: '',
    overtimeHours: 0,
    cleaningFee: false,
    customFee: 0,
    customFeeNote: '',
  },
};

// ─────────────────────────────────────────────────────────────────────────────
// CHECKLIST items template
// ─────────────────────────────────────────────────────────────────────────────
const CHECKLIST_ITEMS = [
  { id: 'giay-dkx', name: 'Giấy đăng ký xe (cà vẹt)' },
  { id: 'dang-kiem', name: 'Giấy đăng kiểm xe' },
  { id: 'bao-hiem', name: 'Giấy bảo hiểm xe' },
  { id: 'chia-khoa', name: 'Chìa khóa xe (bộ chính)' },
  { id: 'chia-khoa-dp', name: 'Chìa khóa dự phòng' },
  { id: 'lop-dp', name: 'Lốp dự phòng' },
  { id: 'kich', name: 'Bộ kích & cờ-lê lốp' },
  { id: 'camera', name: 'Camera hành trình' },
  { id: 'sac-cap', name: 'Sạc / cáp điện (nếu xe điện)' },
  { id: 'bom-xe', name: 'Bơm hơi điện' },
  { id: 'hop-cuu-thuong', name: 'Hộp cứu thương' },
  { id: 'tham-lot', name: 'Thảm lót sàn (bộ 4)' },
];

// ─────────────────────────────────────────────────────────────────────────────
// Required photo slots for checkout
// ─────────────────────────────────────────────────────────────────────────────
const REQUIRED_PHOTO_SLOTS = [
  { id: 'req-front',    label: 'Đầu xe' },
  { id: 'req-rear',     label: 'Đuôi xe' },
  { id: 'req-left',     label: 'Bên trái' },
  { id: 'req-right',    label: 'Bên phải' },
  { id: 'req-odo',      label: 'Đồng hồ ODO' },
];

// ─────────────────────────────────────────────────────────────────────────────
// UTILS
// ─────────────────────────────────────────────────────────────────────────────
function formatVnd(n) {
  return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(n || 0);
}
function formatNum(n) {
  return new Intl.NumberFormat('vi-VN').format(n || 0);
}
function uid() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
}
function qs(sel, ctx = document) { return ctx.querySelector(sel); }
function qsa(sel, ctx = document) { return [...ctx.querySelectorAll(sel)]; }

function showToast(msg, type = 'info', duration = 3200) {
  const t = qs('#hoToast');
  if (!t) return;
  t.textContent = msg;
  t.className = `ho-toast ${type}`;
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.add('hidden'), duration);
}

function setText(el, txt) { if (el) el.textContent = txt ?? '—'; }

function clamp(val, min, max) { return Math.max(min, Math.min(max, val)); }

// ─────────────────────────────────────────────────────────────────────────────
// CALCULATIONS
// ─────────────────────────────────────────────────────────────────────────────
function calcDistance(odoIn, odoOut) {
  const dist = (Number(odoIn) || 0) - (Number(odoOut) || 0);
  return Math.max(0, dist);
}
function calcAllowedKm(rentDays, kmPerDay) {
  return (rentDays || 0) * (kmPerDay || 0);
}
function calcOverKm(distance, allowedKm) {
  return Math.max(0, distance - allowedKm);
}
function calcOverKmFee(overKm, feePerKm) {
  return overKm * (feePerKm || 0);
}
function calcFuelFee(fuelOut, fuelIn) {
  const diff = FUEL_IDX[fuelOut] - FUEL_IDX[fuelIn];
  if (diff <= 0) return 0;
  return diff * HO_CONFIG.FUEL_PRICE_PER_LEVEL;
}
function calcOvertimeFee(hours, rate) {
  return Math.max(0, hours || 0) * (rate || HO_CONFIG.OVERTIME_RATE_PER_HOUR);
}
function calcSettlement() {
  const co = state.checkout;
  const ci = state.checkin;
  const c = state.contract;

  const dist = calcDistance(ci.odo, co.odo);
  const allowed = calcAllowedKm(c.rentDays, c.kmPerDayLimit);
  const overKm = calcOverKm(dist, allowed);
  const overKmFee = calcOverKmFee(overKm, c.overKmFee);
  const fuelFee = calcFuelFee(co.fuel, ci.fuel);
  const overtimeFee = calcOvertimeFee(Number(ci.overtimeHours), HO_CONFIG.OVERTIME_RATE_PER_HOUR);
  const cleaningFee = ci.cleaningFee ? HO_CONFIG.CLEANING_FEE : 0;
  const customFee = Number(ci.customFee) || 0;

  // Phí hư hỏng mới: lấy từ damages[age=new] mà có severity
  const damageFee = ci.damages
    .filter(d => d.age === 'new')
    .reduce((s, d) => s + (Number(d.fee) || 0), 0);

  const totalDeductions = overKmFee + fuelFee + overtimeFee + cleaningFee + customFee + damageFee;
  const refund = c.deposit - totalDeductions;

  return {
    deposit: c.deposit,
    overKm, overKmFee, fuelFee,
    overtimeFee, cleaningFee, customFee, damageFee,
    totalDeductions,
    refund,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// RENDER — Contract Info
// ─────────────────────────────────────────────────────────────────────────────
function renderContractInfo() {
  const c = state.contract;
  const fields = {
    '#hoContractId': c.contractId,
    '#hoPlate': c.licensePlate,
    '#hoVehicle': `${c.brand} ${c.model} (${c.year}) — ${c.color}`,
    '#hoRegExp': c.registrationExp,
    '#hoInsExp': c.insuranceExp,
    '#hoKmLimit': `${formatNum(c.kmPerDayLimit)} km/ngày × ${c.rentDays} ngày = ${formatNum(calcAllowedKm(c.rentDays, c.kmPerDayLimit))} km`,
    '#coKmLimitPreview': `${formatNum(c.kmPerDayLimit)} km/ngày × ${c.rentDays} ngày = ${formatNum(calcAllowedKm(c.rentDays, c.kmPerDayLimit))} km · Phí vượt: ${formatVnd(c.overKmFee)}/km`,
    '#hoOverFee': formatVnd(c.overKmFee) + '/km',
    '#hoDeposit': c.depositType === 'VEHICLE_PLEDGE'
      ? '0 ₫ (Miễn cọc tiền)'
      : formatVnd(c.deposit),
  };
  for (const [sel, val] of Object.entries(fields)) {
    const el = qs(sel);
    if (el) setText(el, val);
  }

  const policyEl = qs('#hoPolicySelect');
  if (policyEl) policyEl.value = c.depositType || 'CASH';

  const hasPledge = c.depositType === 'VEHICLE_PLEDGE' || c.depositType === 'COMBINED';
  const coBox = qs('#coCollateralBox');
  if (coBox) {
    coBox.hidden = !hasPledge;
    const infoEl = qs('#coCollateralInfo');
    if (infoEl && infoEl.value !== (c.collateralInfo || '')) infoEl.value = c.collateralInfo || '';
    const handlerEl = qs('#coCollateralHandler');
    if (handlerEl) handlerEl.value = c.collateralOutHandler || c.staffName || '';
    const timeEl = qs('#coCollateralTime');
    if (timeEl && c.collateralOutTime) timeEl.value = c.collateralOutTime;
    const heldEl = qs('#coCollateralHeld');
    if (heldEl) heldEl.checked = Boolean(c.collateralHeld);
    const custConfEl = qs('#coCollateralCustConfirmed');
    if (custConfEl) custConfEl.checked = Boolean(c.collateralOutCustConfirmed);
    setText(qs('#coCollateralCustName'), state.checkout.customerName || c.customerName || 'Khách thuê');
    const coBadge = qs('#coCollateralStatusBadge');
    if (coBadge) {
      const heldOk = Boolean(c.collateralHeld);
      coBadge.textContent = heldOk
        ? (c.collateralOutCustConfirmed ? '✓ Đã tiếp nhận (2 bên xác nhận)' : '✓ Đang giữ tại trạm')
        : 'Chưa tiếp nhận';
      coBadge.className = `ho-collateral-badge ${heldOk ? 'is-held' : ''}`;
    }
  }

  const ciBox = qs('#ciCollateralReturnBox');
  if (ciBox) {
    ciBox.hidden = !hasPledge;
    setText(qs('#ciCollateralInfoText'), c.collateralInfo || 'Xe cá nhân + Giấy tờ gốc theo hợp đồng');
    const handlerEl = qs('#ciCollateralHandler');
    if (handlerEl) handlerEl.value = c.collateralInHandler || state.checkin.staffName || c.staffName || '';
    const timeEl = qs('#ciCollateralTime');
    if (timeEl && c.collateralInTime) timeEl.value = c.collateralInTime;
    const retEl = qs('#ciCollateralReturned');
    if (retEl) retEl.checked = Boolean(c.collateralReturned);
    const custConfEl = qs('#ciCollateralCustConfirmed');
    if (custConfEl) custConfEl.checked = Boolean(c.collateralInCustConfirmed);
    setText(qs('#ciCollateralCustName'), state.checkin.customerName || c.customerName || 'Khách thuê');
    const ciBadge = qs('#ciCollateralStatusBadge');
    if (ciBadge) {
      const retOk = Boolean(c.collateralReturned && c.collateralInCustConfirmed);
      ciBadge.textContent = retOk
        ? '✓ Đã hoàn trả khách (2 bên xác nhận)'
        : c.collateralReturned
          ? 'Đã bàn giao (Chờ khách xác nhận)'
          : 'Đang giữ tại trạm';
      ciBadge.className = `ho-collateral-badge ${retOk ? 'is-returned' : 'is-held'}`;
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// RENDER — ODO & distance
// ─────────────────────────────────────────────────────────────────────────────
function renderOdo(tabKey) {
  const co = state.checkout;
  const ci = state.checkin;
  const c = state.contract;

  if (tabKey === 'checkout') {
    // nothing to calculate yet
    return;
  }
  // checkin tab
  const dist = calcDistance(ci.odo, co.odo);
  const allowed = calcAllowedKm(c.rentDays, c.kmPerDayLimit);
  const overKm = calcOverKm(dist, allowed);
  const overKmFee = calcOverKmFee(overKm, c.overKmFee);

  setText(qs('#ciOdoDistVal'), `${formatNum(dist)} km`);
  setText(qs('#ciOdoAllowed'), `${formatNum(allowed)} km`);
  const overEl = qs('#ciOdoOver');
  setText(overEl, overKm > 0 ? `${formatNum(overKm)} km → ${formatVnd(overKmFee)}` : 'Không vượt');
  if (overEl) overEl.className = 'ho-odo-stat-val ' + (overKm > 0 ? 'over' : 'ok');

  renderSettlement();
}

// ─────────────────────────────────────────────────────────────────────────────
// RENDER — Fuel gauge
// ─────────────────────────────────────────────────────────────────────────────
function renderFuel(tabKey) {
  const level = state[tabKey].fuel;
  const idx = FUEL_IDX[level] ?? 4;
  const prefix = tabKey === 'checkout' ? 'co' : 'ci';

  // Update buttons
  qsa(`.ho-fuel-btn[data-tab="${tabKey}"]`).forEach(btn => {
    btn.classList.toggle('is-active', btn.dataset.level === level);
    btn.setAttribute('aria-pressed', btn.dataset.level === level ? 'true' : 'false');
  });

  // Update gauge segments
  qsa(`.ho-fuel-seg[data-tab="${tabKey}"]`).forEach((seg, i) => {
    const filled = i < idx;
    seg.classList.toggle('filled', filled);
    seg.classList.toggle('warn', filled && idx <= 1);
  });

  if (tabKey === 'checkout') {
    const badge = qs('#ciFuelOutBadge');
    if (badge) setText(badge, level === 'E' ? 'E (Hết)' : level);
  }

  // Fuel warning & fee (checkin only)
  if (tabKey === 'checkin') {
    const fuelFee = calcFuelFee(state.checkout.fuel, state.checkin.fuel);
    const warn = qs('#ciFuelWarning');
    if (warn) {
      warn.classList.toggle('visible', fuelFee > 0);
      setText(qs('#ciFuelWarningFee'), fuelFee > 0 ? `Phí bù xăng: ${formatVnd(fuelFee)}` : '');
    }
    renderSettlement();
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// RENDER — Photos
// ─────────────────────────────────────────────────────────────────────────────
function renderPhotos(tabKey) {
  const phase = state[tabKey];
  const prefix = tabKey === 'checkout' ? 'co' : 'ci';

  // Required slots
  REQUIRED_PHOTO_SLOTS.forEach(slot => {
    const container = qs(`#${prefix}Photo_${slot.id}`);
    if (!container) return;
    const existing = phase.photos.find(p => p.required === slot.id);
    _renderPhotoSlot(container, existing, slot.label, slot.id, tabKey);
  });

  // Extra photos grid
  const extraGrid = qs(`#${prefix}ExtraGrid`);
  if (extraGrid) {
    extraGrid.innerHTML = '';
    const extras = phase.photos.filter(p => !p.required);
    extras.forEach(photo => {
      const slot = document.createElement('div');
      slot.className = 'ho-photo-slot has-image';
      extraGrid.appendChild(slot);
      _buildPhotoThumb(slot, photo, tabKey);
      // Note input below slot
      const noteWrap = document.createElement('div');
      noteWrap.className = 'ho-photo-note';
      const noteInput = document.createElement('input');
      noteInput.type = 'text';
      noteInput.placeholder = 'Ghi chú ảnh...';
      noteInput.value = photo.note || '';
      noteInput.setAttribute('aria-label', 'Ghi chú cho ảnh');
      noteInput.addEventListener('input', () => {
        photo.note = noteInput.value;
      });
      noteWrap.appendChild(noteInput);
      extraGrid.appendChild(noteWrap);
    });
  }
}

function _renderPhotoSlot(container, photo, label, slotId, tabKey) {
  container.innerHTML = '';
  if (photo) {
    container.classList.add('has-image');
    container.classList.remove('required-empty');
    _buildPhotoThumb(container, photo, tabKey);
    const badge = document.createElement('span');
    badge.className = 'ho-photo-required-badge';
    badge.textContent = label;
    container.appendChild(badge);
  } else {
    container.classList.remove('has-image');
    // Icon + label
    const icon = document.createElement('div');
    icon.className = 'ho-photo-slot-icon';
    icon.setAttribute('aria-hidden', 'true');
    icon.innerHTML = `<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="7" width="18" height="14" rx="2"/><circle cx="12" cy="14" r="3.5"/><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>`;
    const lbl = document.createElement('div');
    lbl.className = 'ho-photo-slot-label';
    // Use textContent to avoid XSS
    lbl.textContent = label;
    container.appendChild(icon);
    container.appendChild(lbl);
    container.addEventListener('click', () => triggerPhotoUpload(tabKey, slotId), { once: true });
  }
}

function _buildPhotoThumb(container, photo, tabKey) {
  const img = document.createElement('img');
  img.className = 'thumb';
  img.src = photo.url;
  img.alt = photo.label || 'Ảnh xe';
  img.addEventListener('click', (e) => { e.stopPropagation(); openLightbox(photo.url); });
  container.appendChild(img);

  const delBtn = document.createElement('button');
  delBtn.className = 'del-btn';
  delBtn.type = 'button';
  delBtn.setAttribute('aria-label', 'Xóa ảnh');
  delBtn.textContent = '×';
  delBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    removePhoto(tabKey, photo.id);
  });
  container.appendChild(delBtn);
}

function triggerPhotoUpload(tabKey, requiredSlotId = null) {
  const phase = state[tabKey];
  if (phase.photos.length >= HO_CONFIG.MAX_PHOTOS) {
    showToast(`Tối đa ${HO_CONFIG.MAX_PHOTOS} ảnh cho mỗi biên bản.`, 'error');
    return;
  }
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = HO_CONFIG.ALLOWED_TYPES.join(',');
  input.multiple = !requiredSlotId;
  input.setAttribute('capture', 'environment'); // mobile camera
  input.addEventListener('change', () => {
    [...(input.files || [])].forEach(file => handlePhotoFile(tabKey, file, requiredSlotId));
  });
  input.click();
}

function handlePhotoFile(tabKey, file, requiredSlotId = null) {
  // Validate type
  if (!HO_CONFIG.ALLOWED_TYPES.includes(file.type)) {
    showToast(`"${file.name}" không đúng định dạng (chỉ JPG, PNG, WebP).`, 'error');
    return;
  }
  // Validate size
  if (file.size > HO_CONFIG.MAX_FILE_SIZE_MB * 1024 * 1024) {
    showToast(`"${file.name}" quá ${HO_CONFIG.MAX_FILE_SIZE_MB}MB.`, 'error');
    return;
  }
  const phase = state[tabKey];
  if (phase.photos.length >= HO_CONFIG.MAX_PHOTOS) {
    showToast(`Đã đạt tối đa ${HO_CONFIG.MAX_PHOTOS} ảnh.`, 'error');
    return;
  }

  const url = URL.createObjectURL(file);
  const photo = {
    id: uid(),
    file,
    url,
    label: file.name,
    note: '',
    required: requiredSlotId || null,
  };

  // Replace if same required slot
  if (requiredSlotId) {
    const idx = phase.photos.findIndex(p => p.required === requiredSlotId);
    if (idx >= 0) {
      URL.revokeObjectURL(phase.photos[idx].url);
      phase.photos.splice(idx, 1, photo);
    } else {
      phase.photos.push(photo);
    }
  } else {
    phase.photos.push(photo);
  }

  renderPhotos(tabKey);
}

function removePhoto(tabKey, photoId) {
  const phase = state[tabKey];
  const idx = phase.photos.findIndex(p => p.id === photoId);
  if (idx < 0) return;
  URL.revokeObjectURL(phase.photos[idx].url);
  phase.photos.splice(idx, 1);
  renderPhotos(tabKey);
}

// ─────────────────────────────────────────────────────────────────────────────
// LIGHTBOX
// ─────────────────────────────────────────────────────────────────────────────
function openLightbox(src) {
  const lb = qs('#hoLightbox');
  const img = qs('#hoLightboxImg');
  if (!lb || !img) return;
  img.src = src;
  img.alt = 'Phóng to ảnh xe';
  lb.classList.add('open');
}
function closeLightbox() {
  const lb = qs('#hoLightbox');
  if (lb) { lb.classList.remove('open'); qs('#hoLightboxImg').src = ''; }
}

// ─────────────────────────────────────────────────────────────────────────────
// RENDER — Checklist
// ─────────────────────────────────────────────────────────────────────────────
function initChecklist(tabKey) {
  state[tabKey].checklist = CHECKLIST_ITEMS.map(item => ({
    ...item,
    status: 'ok',
    note: '',
  }));
}

function renderChecklist(tabKey) {
  const prefix = tabKey === 'checkout' ? 'co' : 'ci';
  const container = qs(`#${prefix}Checklist`);
  if (!container) return;
  container.innerHTML = '';

  state[tabKey].checklist.forEach((item, idx) => {
    const row = document.createElement('div');
    row.className = 'ho-checklist-row';
    row.setAttribute('role', 'group');
    row.setAttribute('aria-label', item.name);

    // Name
    const nameEl = document.createElement('span');
    nameEl.className = 'ho-checklist-name';
    nameEl.textContent = item.name;

    // Status buttons
    const statusWrap = document.createElement('div');
    statusWrap.className = 'ho-checklist-status';
    const statuses = [
      { key: 'ok', label: 'Đủ', cls: 'ok' },
      { key: 'miss', label: 'Thiếu', cls: 'miss' },
      { key: 'broken', label: 'Hư hỏng', cls: 'broken' },
      { key: 'na', label: 'Không có', cls: 'na' },
    ];
    statuses.forEach(s => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = `ho-status-btn ${s.cls}${item.status === s.key ? ' is-active' : ''}`;
      btn.textContent = s.label;
      btn.setAttribute('aria-pressed', item.status === s.key ? 'true' : 'false');
      btn.addEventListener('click', () => {
        item.status = s.key;
        renderChecklist(tabKey);
      });
      statusWrap.appendChild(btn);
    });

    // Note input (shown if 'miss' or 'broken')
    const noteWrap = document.createElement('div');
    noteWrap.className = 'ho-checklist-note';
    if (item.status === 'miss' || item.status === 'broken') {
      const noteInput = document.createElement('input');
      noteInput.type = 'text';
      noteInput.placeholder = 'Ghi chú...';
      noteInput.value = item.note || '';
      noteInput.setAttribute('aria-label', `Ghi chú: ${item.name}`);
      noteInput.addEventListener('input', () => { item.note = noteInput.value; });
      noteWrap.appendChild(noteInput);
    }

    row.appendChild(nameEl);
    row.appendChild(statusWrap);
    row.appendChild(noteWrap);
    container.appendChild(row);
  });
}

function checklistSelectAll(tabKey) {
  state[tabKey].checklist.forEach(item => {
    item.status = 'ok';
    item.note = '';
  });
  renderChecklist(tabKey);
}

// ─────────────────────────────────────────────────────────────────────────────
// BODY DIAGRAM — Damage pins
// ─────────────────────────────────────────────────────────────────────────────
let _damageModalResolve = null;

function renderDamages(tabKey) {
  const prefix = tabKey === 'checkout' ? 'co' : 'ci';
  const container = qs(`#${prefix}BodyDiagram`);
  const listEl = qs(`#${prefix}DamageList`);
  if (!container) return;

  // Remove old pins
  qsa('.damage-pin', container).forEach(p => p.remove());

  const damages = state[tabKey].damages;

  // Draw pins
  damages.forEach(d => {
    const pin = document.createElement('button');
    pin.className = `damage-pin ${d.age}`;
    pin.type = 'button';
    pin.style.left = `${d.x}%`;
    pin.style.top = `${d.y}%`;
    pin.setAttribute('aria-label', `Vết ${d.type} — ${d.severity} — Nhấn để sửa`);
    pin.textContent = d.age === 'old' ? '●' : '✕';
    pin.addEventListener('click', (e) => {
      e.stopPropagation();
      openDamageModal(tabKey, d);
    });
    container.appendChild(pin);
  });

  // Render list
  if (listEl) {
    listEl.innerHTML = '';
    if (!damages.length) {
      const empty = document.createElement('p');
      empty.style.cssText = 'color:#6b8a76;font-size:13px;margin:0;';
      empty.textContent = 'Chưa có vết xước nào được đánh dấu.';
      listEl.appendChild(empty);
      return;
    }
    damages.forEach(d => {
      const item = document.createElement('div');
      item.className = 'ho-damage-item';

      const header = document.createElement('div');
      header.className = 'ho-damage-item-header';

      const badge = document.createElement('span');
      badge.className = `ho-damage-badge ${d.age}`;
      badge.textContent = d.age === 'old' ? 'Vết cũ (lúc giao)' : 'Vết mới (lúc trả)';

      const delBtn = document.createElement('button');
      delBtn.type = 'button';
      delBtn.className = 'ho-damage-del';
      delBtn.setAttribute('aria-label', 'Xóa vết xước');
      delBtn.textContent = 'Xóa';
      delBtn.addEventListener('click', () => {
        state[tabKey].damages = state[tabKey].damages.filter(x => x.id !== d.id);
        renderDamages(tabKey);
      });

      header.appendChild(badge);
      header.appendChild(delBtn);
      item.appendChild(header);

      const desc = document.createElement('p');
      desc.style.cssText = 'margin:4px 0 0;font-size:13px;';
      // Use textContent to avoid XSS
      desc.textContent = `${d.type} · ${d.severity}${d.note ? ' · ' + d.note : ''}${d.fee ? ' · Phí dự kiến: ' + formatVnd(d.fee) : ''}`;
      item.appendChild(desc);

      listEl.appendChild(item);
    });
  }
}

function openDamageModal(tabKey, existingDamage = null) {
  const modal = qs('#hoDamageModal');
  if (!modal) return;
  modal.classList.add('open');
  modal.setAttribute('aria-hidden', 'false');

  const title = qs('#hoDamageModalTitle');
  setText(title, existingDamage ? 'Sửa vết xước' : 'Thêm vết xước');

  // Populate form
  const typeEl = qs('#dmgType');
  const sevEl = qs('#dmgSeverity');
  const ageEl = qs('#dmgAge');
  const noteEl = qs('#dmgNote');
  const feeEl = qs('#dmgFee');
  if (existingDamage) {
    if (typeEl) typeEl.value = existingDamage.type;
    if (sevEl) sevEl.value = existingDamage.severity;
    if (ageEl) ageEl.value = existingDamage.age;
    if (noteEl) noteEl.value = existingDamage.note || '';
    if (feeEl) feeEl.value = existingDamage.fee || '';
  } else {
    if (typeEl) typeEl.value = 'xước';
    if (sevEl) sevEl.value = 'nhẹ';
    if (ageEl) ageEl.value = tabKey === 'checkout' ? 'old' : 'new';
    if (noteEl) noteEl.value = '';
    if (feeEl) feeEl.value = '';
  }

  // Confirm
  const confirmBtn = qs('#dmgConfirm');
  const newConfirm = confirmBtn.cloneNode(true);
  confirmBtn.parentNode.replaceChild(newConfirm, confirmBtn);
  newConfirm.addEventListener('click', () => {
    const data = {
      type: typeEl ? typeEl.value : 'xước',
      severity: sevEl ? sevEl.value : 'nhẹ',
      age: ageEl ? ageEl.value : (tabKey === 'checkout' ? 'old' : 'new'),
      note: noteEl ? noteEl.value : '',
      fee: feeEl ? Number(feeEl.value) || 0 : 0,
    };
    if (existingDamage) {
      Object.assign(existingDamage, data);
    }
    // existingDamage already added when clicking map; nothing to push again
    closeDamageModal();
    renderDamages(tabKey);
    if (state.activeTab === 'checkin') renderSettlement();
  });
}

function closeDamageModal() {
  const modal = qs('#hoDamageModal');
  if (modal) { modal.classList.remove('open'); modal.setAttribute('aria-hidden', 'true'); }
}

// ─────────────────────────────────────────────────────────────────────────────
// RENDER — Settlement (Check-in only)
// ─────────────────────────────────────────────────────────────────────────────
function renderSettlement() {
  const s = calcSettlement();
  const dtype = state.contract.depositType || 'CASH';
  const isPledgeOnly = dtype === 'VEHICLE_PLEDGE';
  const isCombined = dtype === 'COMBINED';
  const fields = {
    '#settlDepositLabel': isPledgeOnly
      ? 'Chính sách bảo đảm'
      : isCombined
        ? 'Tiền cọc ban đầu (+ Thế chấp xe)'
        : 'Tiền cọc ban đầu',
    '#settlDeposit': isPledgeOnly ? 'Chỉ thế chấp tài sản (0 ₫ cọc)' : formatVnd(s.deposit),
    '#settlOverKm': s.overKm > 0 ? `${formatNum(s.overKm)} km × ${formatVnd(state.contract.overKmFee)} = ${formatVnd(s.overKmFee)}` : '0 ₫ (trong hạn mức)',
    '#settlFuel': s.fuelFee > 0 ? formatVnd(s.fuelFee) : '0 ₫',
    '#settlOvertime': s.overtimeFee > 0 ? formatVnd(s.overtimeFee) : '0 ₫',
    '#settlCleaning': s.cleaningFee > 0 ? formatVnd(s.cleaningFee) : '0 ₫',
    '#settlDamage': s.damageFee > 0 ? formatVnd(s.damageFee) : '0 ₫',
    '#settlCustom': s.customFee > 0 ? formatVnd(s.customFee) : '0 ₫',
    '#settlTotal': formatVnd(s.totalDeductions),
    '#settlRefund': isPledgeOnly ? formatVnd(s.totalDeductions) : formatVnd(Math.abs(s.refund)),
  };
  for (const [sel, val] of Object.entries(fields)) {
    const el = qs(sel);
    if (el) setText(el, val);
  }
  const refundRow = qs('#settlRefundRow');
  if (refundRow) {
    if (isPledgeOnly) {
      if (s.totalDeductions > 0) {
        refundRow.className = 'ho-settlement-row charge';
        setText(qs('#settlRefundLabel'), `⚠️ Khách cần thanh toán phụ phí`);
      } else {
        refundRow.className = 'ho-settlement-row refund';
        setText(qs('#settlRefundLabel'), `✅ Không phát sinh phụ phí (Hoàn trả tài sản thế chấp)`);
      }
    } else if (s.refund >= 0) {
      refundRow.className = 'ho-settlement-row refund';
      setText(qs('#settlRefundLabel'), isCombined ? `✅ Hoàn cọc khách &amp; trả tài sản thế chấp` : `✅ Hoàn cọc khách`);
    } else {
      refundRow.className = 'ho-settlement-row charge';
      setText(qs('#settlRefundLabel'), `⚠️ Khách cần trả thêm`);
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// SIGNED PAPER PROTOCOL PHOTOS (Ảnh biên bản giấy đã ký)
// ─────────────────────────────────────────────────────────────────────────────
function renderSignedDocs(tabKey) {
  const prefix = tabKey === 'checkout' ? 'co' : 'ci';
  const grid = qs(`#${prefix}SignedDocGrid`);
  const zone = qs(`#${prefix}SignedDocZone`);
  const errEl = qs(`#${prefix}SignedDocErr`);
  if (!grid) return;

  const docs = state[tabKey].signedDocPhotos || [];
  grid.innerHTML = '';

  if (docs.length > 0) {
    zone?.classList.remove('is-error');
    if (errEl) { errEl.textContent = ''; errEl.classList.remove('visible'); }
  }

  docs.forEach((doc, idx) => {
    const item = document.createElement('div');
    item.className = 'ho-doc-item';

    const img = document.createElement('img');
    img.src = doc.url;
    img.alt = doc.name || `Ảnh biên bản trang ${idx + 1}`;
    img.addEventListener('click', () => openLightbox(doc.url, img.alt));

    const badge = document.createElement('span');
    badge.className = 'ho-doc-badge';
    badge.textContent = `Trang ${idx + 1}`;

    const del = document.createElement('button');
    del.type = 'button';
    del.className = 'del-btn';
    del.innerHTML = '&times;';
    del.setAttribute('aria-label', `Xoá ảnh biên bản trang ${idx + 1}`);
    del.addEventListener('click', (e) => {
      e.stopPropagation();
      try { if (doc.url && doc.url.startsWith('blob:')) URL.revokeObjectURL(doc.url); } catch {}
      state[tabKey].signedDocPhotos = state[tabKey].signedDocPhotos.filter(d => d.id !== doc.id);
      renderSignedDocs(tabKey);
    });

    item.appendChild(img);
    item.appendChild(badge);
    item.appendChild(del);
    grid.appendChild(item);
  });
}

function triggerSignedDocUpload(tabKey) {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = 'image/jpeg,image/png,image/webp';
  input.multiple = true;
  input.addEventListener('change', () => {
    [...(input.files || [])].forEach(f => handleSignedDocFile(tabKey, f));
  });
  input.click();
}

function handleSignedDocFile(tabKey, file) {
  if (!file) return;
  if (!HO_CONFIG.ALLOWED_TYPES.includes(file.type)) {
    showToast('Chỉ hỗ trợ ảnh JPG, PNG, WebP cho biên bản giấy.', 'error');
    return;
  }
  if (file.size > HO_CONFIG.MAX_FILE_SIZE_MB * 1024 * 1024) {
    showToast(`File "${file.name}" vượt quá ${HO_CONFIG.MAX_FILE_SIZE_MB}MB.`, 'error');
    return;
  }
  const url = URL.createObjectURL(file);
  state[tabKey].signedDocPhotos.push({ id: uid(), file, url, name: file.name });
  renderSignedDocs(tabKey);
}

// ─────────────────────────────────────────────────────────────────────────────
// TAB SWITCH
// ─────────────────────────────────────────────────────────────────────────────
function switchTab(tabKey) {
  state.activeTab = tabKey;
  qsa('[role="tab"]').forEach(btn => {
    const isActive = btn.dataset.tab === tabKey;
    btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
    btn.tabIndex = isActive ? 0 : -1;
  });
  qsa('[role="tabpanel"]').forEach(panel => {
    panel.hidden = panel.id !== `panel-${tabKey}`;
  });
  if (tabKey === 'checkin') {
    renderOdo('checkin');
    renderFuel('checkin');
    renderSettlement();
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// VALIDATE — kiểm tra và báo đỏ các trường chưa điền
// ─────────────────────────────────────────────────────────────────────────────
function clearPhaseErrors(tabKey) {
  const prefix = tabKey === 'checkout' ? 'co' : 'ci';
  const panel = qs(`#panel-${tabKey}`);
  if (panel) {
    qsa('.is-error', panel).forEach(el => el.classList.remove('is-error'));
    qsa('.required-empty', panel).forEach(el => el.classList.remove('required-empty'));
    qsa('.ho-field-error.visible', panel).forEach(el => {
      el.classList.remove('visible');
      el.textContent = '';
    });
  }
}

function validatePhase(tabKey) {
  clearPhaseErrors(tabKey);
  const phase = state[tabKey];
  const prefix = tabKey === 'checkout' ? 'co' : 'ci';
  let firstError = null;
  const errors = [];

  function markError(inputId, msg) {
    const el = qs(`#${inputId}`);
    if (el) {
      el.classList.add('is-error');
      const errEl = qs(`#${inputId}Err`);
      if (errEl) {
        errEl.textContent = msg;
        errEl.classList.add('visible');
      }
      if (!firstError) firstError = el;
    }
    errors.push(msg);
  }

  // Họ tên khách & nhân viên
  const custInput = qs(`#${prefix}CustName`);
  if (!custInput?.value.trim()) {
    markError(`${prefix}CustName`, 'Vui lòng nhập họ tên khách thuê.');
  }

  const staffInput = qs(`#${prefix}StaffName`);
  if (!staffInput?.value.trim()) {
    markError(`${prefix}StaffName`, 'Vui lòng nhập họ tên nhân viên.');
  }

  // Ngày giờ
  const dtInput = qs(`#${prefix}Dt`);
  if (!dtInput?.value && !phase.datetime) {
    markError(`${prefix}Dt`, 'Vui lòng chọn thời gian.');
  }

  // ODO
  const odoInput = qs(`#${prefix}Odo`);
  if (!odoInput?.value && odoInput?.value !== '0' && !phase.odo && phase.odo !== 0) {
    markError(`${prefix}Odo`, 'Vui lòng nhập số km ODO.');
  } else if (tabKey === 'checkin') {
    const coOdo = Number(qs('#coOdo')?.value || state.checkout.odo) || 0;
    const ciOdo = Number(odoInput?.value || phase.odo) || 0;
    if (ciOdo < coOdo) {
      markError('ciOdo', `ODO trả (${ciOdo}) phải ≥ ODO giao (${coOdo}).`);
    }
  }

  // 5 Ảnh bắt buộc
  const missingPhotos = REQUIRED_PHOTO_SLOTS.filter(slot =>
    !phase.photos.find(p => p.required === slot.id)
  );
  if (missingPhotos.length > 0) {
    const missingNames = missingPhotos.map(s => s.label).join(', ');
    errors.push(`Thiếu ảnh bắt buộc: ${missingNames}`);
    missingPhotos.forEach(slot => {
      const slotEl = qs(`#${prefix}Photo_${slot.id}`);
      if (slotEl) {
        slotEl.classList.add('required-empty');
        if (!firstError) firstError = slotEl;
      }
    });
  }

  // Ảnh biên bản giấy đã ký
  if (!phase.signedDocPhotos || phase.signedDocPhotos.length === 0) {
    const msg = 'Vui lòng chụp/tải lên ảnh biên bản giấy đã ký xác nhận.';
    errors.push(msg);
    const zone = qs(`#${prefix}SignedDocZone`);
    const errEl = qs(`#${prefix}SignedDocErr`);
    if (zone) {
      zone.classList.add('is-error');
      if (!firstError) firstError = zone;
    }
    if (errEl) {
      errEl.textContent = msg;
      errEl.classList.add('visible');
    }
  }

  return { errors, firstError };
}

// ─────────────────────────────────────────────────────────────────────────────
// DRAFT — localStorage
// ─────────────────────────────────────────────────────────────────────────────
function saveDraft() {
  try {
    const draft = {
      activeTab: state.activeTab,
      checkout: _serializePhase(state.checkout),
      checkin: _serializePhase(state.checkin),
    };
    localStorage.setItem(HO_CONFIG.DRAFT_KEY, JSON.stringify(draft));
    showToast('Đã lưu nháp.', 'success', 2000);
  } catch (e) {
    showToast('Không thể lưu nháp (localStorage đầy?)', 'error');
  }
}

function _serializePhase(phase) {
  // Skip file objects & blob URLs
  return {
    ...phase,
    photos: phase.photos.map(p => ({ id: p.id, label: p.label, note: p.note, required: p.required })),
    signedDocPhotos: [],
  };
}

function loadDraft() {
  try {
    const raw = localStorage.getItem(HO_CONFIG.DRAFT_KEY);
    if (!raw) return false;
    const draft = JSON.parse(raw);
    if (draft.checkout) {
      Object.assign(state.checkout, draft.checkout);
      state.checkout.photos = []; // can't restore blob URLs
      state.checkout.signedDocPhotos = [];
    }
    if (draft.checkin) {
      Object.assign(state.checkin, draft.checkin);
      state.checkin.photos = [];
      state.checkin.signedDocPhotos = [];
    }
    return true;
  } catch (e) {
    return false;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// SUBMIT — Nút luôn sáng xanh, bấm kiểm tra và báo đỏ nếu thiếu
// ─────────────────────────────────────────────────────────────────────────────
async function submitHandover() {
  // Kiểm tra thông tin cả 2 tab
  const coRes = validatePhase('checkout');
  const ciRes = validatePhase('checkin');

  if (coRes.errors.length > 0 || ciRes.errors.length > 0) {
    // Nếu tab đang xem có lỗi -> cuộn tới lỗi đầu tiên của tab này
    if (state.activeTab === 'checkout' && coRes.errors.length > 0) {
      coRes.firstError?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      showToast('Vui lòng điền đủ các mục được báo đỏ ở Check-out.', 'error', 4500);
    } else if (state.activeTab === 'checkin' && ciRes.errors.length > 0) {
      ciRes.firstError?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      showToast('Vui lòng điền đủ các mục được báo đỏ ở Check-in.', 'error', 4500);
    } else if (state.activeTab === 'checkout' && coRes.errors.length === 0 && ciRes.errors.length > 0) {
      // Check-out đã xong, tự động chuyển sang Check-in để báo đỏ
      switchTab('checkin');
      setTimeout(() => {
        ciRes.firstError?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 150);
      showToast('Check-out đã đủ. Vui lòng hoàn tất các mục báo đỏ ở Check-in!', 'error', 4500);
    } else if (state.activeTab === 'checkin' && ciRes.errors.length === 0 && coRes.errors.length > 0) {
      // Check-in đã xong, tự động chuyển sang Check-out để báo đỏ
      switchTab('checkout');
      setTimeout(() => {
        coRes.firstError?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 150);
      showToast('Vui lòng hoàn tất các mục còn thiếu ở tab Check-out!', 'error', 4500);
    }
    return;
  }

  const submitBtn = qs('#hoSubmitBtn');
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerHTML = `<span class="ho-spinner"></span> Đang lưu...`;
  }

  try {
    const token = getAuthToken();
    const numericBookingId = _resolveNumericBookingId();

    if (token && numericBookingId > 0) {
      await _submitToBackend(numericBookingId, token);
      showToast('✅ Biên bản & ảnh biên bản giấy đã lưu lên hệ thống!', 'success', 4000);
    } else {
      const coPayload = buildPayload('checkout');
      const ciPayload = buildPayload('checkin');
      await _mockSubmit(coPayload);
      await _mockSubmit(ciPayload);
      showToast('✅ Đã lưu biên bản (chế độ demo — đăng nhập & chọn đơn để đồng bộ DB).', 'success', 4500);
    }
    try { localStorage.removeItem(HO_CONFIG.DRAFT_KEY); } catch {}
  } catch (err) {
    showToast(err?.message || 'Lỗi khi lưu biên bản. Vui lòng thử lại.', 'error', 5000);
    console.error('[Handover] Submit error:', err);
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg> Xác nhận & Lưu biên bản`;
    }
  }
}

function _resolveNumericBookingId() {
  const params = new URLSearchParams(window.location.search);
  const raw = params.get('booking_id') || state.contract.contractId || '';
  if (/^\d+$/.test(String(raw).trim())) return Number(raw);
  return 0;
}

function _mapChecklistForApi(items) {
  return (items || []).map(c => ({
    item: c.name,
    ok: c.status === 'ok' || c.status === 'na',
    status: c.status || 'ok',
    note: c.note || null,
  }));
}

function _mapFuelForApi(fuel) {
  if (fuel === 'E') return 'EMPTY';
  if (fuel === '2/4') return '1/2';
  return fuel || 'FULL';
}

async function _uploadMediaBatch(protocolId, files, mediaType, captions, token) {
  if (!files || files.length === 0) return [];
  const fd = new FormData();
  files.forEach(f => fd.append('files', f));
  fd.append('media_type', mediaType);
  if (captions && captions.length) fd.append('captions', captions.join('|'));

  const res = await fetch(`${HO_CONFIG.API_BASE_URL}/handover/${protocolId}/media`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: fd,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Upload ảnh (${mediaType}) thất bại (${res.status})`);
  }
  return res.json();
}

async function _submitToBackend(bookingId, token) {
  const co = state.checkout;
  const ci = state.checkin;
  const c = state.contract;
  const settl = calcSettlement();
  const suffix = Date.now().toString().slice(-5);

  const headers = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
  };

  const hasPledge = c.depositType === 'VEHICLE_PLEDGE' || c.depositType === 'COMBINED';
  // 1. Tạo biên bản CHECK_OUT
  const coBody = {
    protocol_code: `BB-OUT-${bookingId}-${suffix}`,
    booking_id: bookingId,
    protocol_type: 'CHECK_OUT',
    handover_location: qs('#coPickupAddr')?.value?.trim() || c.pickupAddr || 'Cửa hàng RideHub',
    vehicle_name: `${c.brand} ${c.model}`.trim() || 'Xe thuê',
    license_plate: c.licensePlate || 'Chưa cập nhật',
    vehicle_category: 'CAR',
    customer_name: qs('#coCustName')?.value?.trim() || co.customerName,
    customer_cccd: qs('#coCustCCCD')?.value?.trim() || c.customerCCCD || '',
    customer_phone: qs('#coCustPhone')?.value?.trim() || c.customerPhone || '',
    customer_license: qs('#coCustLicense')?.value?.trim() || c.customerLicense || '',
    odo_checkout: Number(qs('#coOdo')?.value || co.odo) || 0,
    fuel_checkout: _mapFuelForApi(co.fuel),
    free_km_limit: calcAllowedKm(c.rentDays, c.kmPerDayLimit),
    checklist_data: _mapChecklistForApi(co.checklist),
    deposit_type: c.depositType || 'CASH',
    collateral_info: hasPledge ? (qs('#coCollateralInfo')?.value?.trim() || c.collateralInfo || null) : null,
    collateral_status: hasPledge ? (c.collateralHeld ? 'HELD' : 'PENDING') : null,
    collateral_handler_name: hasPledge ? (qs('#coCollateralHandler')?.value?.trim() || c.collateralOutHandler || co.staffName || null) : null,
    collateral_handled_at: hasPledge && (qs('#coCollateralTime')?.value || c.collateralOutTime) ? (qs('#coCollateralTime')?.value || c.collateralOutTime) : null,
    collateral_customer_confirmed: hasPledge ? Boolean(c.collateralOutCustConfirmed) : false,
    deposit_original: c.depositType === 'VEHICLE_PLEDGE' ? 0 : (c.deposit || 0),
    notes: co.note || null,
  };

  const coRes = await fetch(`${HO_CONFIG.API_BASE_URL}/handover/checkout`, {
    method: 'POST',
    headers,
    body: JSON.stringify(coBody),
  });
  if (!coRes.ok) {
    const err = await coRes.json().catch(() => ({}));
    throw new Error(err.detail || `Lưu Check-out thất bại (${coRes.status})`);
  }
  const coProtocol = await coRes.json();

  // Upload ảnh xe & ảnh biên bản giấy Check-out
  const coVehicleFiles = co.photos.filter(p => p.file).map(p => p.file);
  const coVehicleCaptions = co.photos.filter(p => p.file).map(p => p.label || 'Ảnh xe lúc giao');
  await _uploadMediaBatch(coProtocol.id, coVehicleFiles, 'VEHICLE_PHOTO', coVehicleCaptions, token);

  const coDocFiles = (co.signedDocPhotos || []).filter(d => d.file).map(d => d.file);
  const coDocCaptions = (co.signedDocPhotos || []).filter(d => d.file).map((_, i) => `Biên bản giao xe trang ${i + 1}`);
  await _uploadMediaBatch(coProtocol.id, coDocFiles, 'SIGNED_DOCUMENT', coDocCaptions, token);

  // 2. Tạo biên bản CHECK_IN
  const holdFine = Math.min(c.deposit || 0, Math.max(0, settl.totalDeductions));
  const refundImm = Math.max(0, (c.deposit || 0) - holdFine);
  const ciBody = {
    protocol_code: `BB-IN-${bookingId}-${suffix}`,
    booking_id: bookingId,
    odo_checkin: Number(qs('#ciOdo')?.value || ci.odo) || 0,
    fuel_checkin: _mapFuelForApi(ci.fuel),
    handover_location: qs('#coPickupAddr')?.value?.trim() || c.returnAddr || 'Cửa hàng RideHub',
    checklist_data: _mapChecklistForApi(ci.checklist),
    fee_overtime: settl.overtimeFee,
    fee_excess_km: settl.overKmFee,
    fee_fuel: settl.fuelFee,
    fee_cleaning: settl.cleaningFee,
    fee_damage: settl.damageFee + settl.customFee,
    deposit_type: c.depositType || 'CASH',
    collateral_info: hasPledge ? (c.collateralInfo || null) : null,
    collateral_status: hasPledge ? (c.collateralReturned ? 'RETURNED' : 'HELD') : null,
    collateral_handler_name: hasPledge ? (qs('#ciCollateralHandler')?.value?.trim() || c.collateralInHandler || ci.staffName || null) : null,
    collateral_handled_at: hasPledge && (qs('#ciCollateralTime')?.value || c.collateralInTime) ? (qs('#ciCollateralTime')?.value || c.collateralInTime) : null,
    collateral_customer_confirmed: hasPledge ? Boolean(c.collateralInCustConfirmed) : false,
    deposit_original: c.depositType === 'VEHICLE_PLEDGE' ? 0 : (c.deposit || 0),
    hold_fine_deposit: c.depositType === 'VEHICLE_PLEDGE' ? 0 : holdFine,
    refund_immediate: c.depositType === 'VEHICLE_PLEDGE' ? 0 : refundImm,
    notes: ci.note || null,
  };

  const ciRes = await fetch(`${HO_CONFIG.API_BASE_URL}/handover/checkin`, {
    method: 'POST',
    headers,
    body: JSON.stringify(ciBody),
  });
  if (!ciRes.ok) {
    const err = await ciRes.json().catch(() => ({}));
    throw new Error(err.detail || `Lưu Check-in thất bại (${ciRes.status})`);
  }
  const ciProtocol = await ciRes.json();

  // Upload ảnh xe & ảnh biên bản giấy Check-in
  const ciVehicleFiles = ci.photos.filter(p => p.file).map(p => p.file);
  const ciVehicleCaptions = ci.photos.filter(p => p.file).map(p => p.label || 'Ảnh xe lúc nhận');
  await _uploadMediaBatch(ciProtocol.id, ciVehicleFiles, 'VEHICLE_PHOTO', ciVehicleCaptions, token);

  const ciDocFiles = (ci.signedDocPhotos || []).filter(d => d.file).map(d => d.file);
  const ciDocCaptions = (ci.signedDocPhotos || []).filter(d => d.file).map((_, i) => `Biên bản nhận xe trang ${i + 1}`);
  await _uploadMediaBatch(ciProtocol.id, ciDocFiles, 'SIGNED_DOCUMENT', ciDocCaptions, token);
}

function buildPayload(tabKey) {
  const phase = state[tabKey];
  const formData = new FormData();
  formData.append('contractId', state.contract.contractId);
  formData.append('phase', tabKey);
  formData.append('datetime', phase.datetime);
  formData.append('odo', phase.odo);
  formData.append('fuel', phase.fuel);
  formData.append('checklist', JSON.stringify(phase.checklist));
  formData.append('damages', JSON.stringify(phase.damages));
  formData.append('note', phase.note || '');
  if (tabKey === 'checkin') {
    formData.append('overtimeHours', state.checkin.overtimeHours);
    formData.append('cleaningFee', state.checkin.cleaningFee ? '1' : '0');
    formData.append('customFee', state.checkin.customFee);
    formData.append('customFeeNote', state.checkin.customFeeNote);
    formData.append('settlement', JSON.stringify(calcSettlement()));
  }
  (phase.signedDocPhotos || []).forEach((d, i) => {
    if (d.file) formData.append(`signed_doc_${i}`, d.file, d.name);
  });
  phase.photos.forEach((p, i) => {
    if (p.file) formData.append(`photo_${i}`, p.file, p.label);
  });
  return formData;
}

/** Mock submit — xóa khi có backend */
function _mockSubmit(payload) {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      console.log('[MOCK] Handover submitted. Payload keys:', [...payload.keys()]);
      resolve({ success: true });
    }, 1200);
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// DRAG & DROP for extra photos
// ─────────────────────────────────────────────────────────────────────────────
function initDragDrop(tabKey) {
  const prefix = tabKey === 'checkout' ? 'co' : 'ci';
  const zone = qs(`#${prefix}DropZone`);
  if (!zone) return;

  zone.addEventListener('dragover', e => { e.preventDefault(); zone.style.borderColor = '#16a34a'; });
  zone.addEventListener('dragleave', () => { zone.style.borderColor = ''; });
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.style.borderColor = '';
    [...(e.dataTransfer.files || [])].forEach(f => handlePhotoFile(tabKey, f));
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// BIND UI events
// ─────────────────────────────────────────────────────────────────────────────
function bindEvents() {
  // Tab keyboard navigation
  const tabList = qs('[role="tablist"]');
  if (tabList) {
    tabList.addEventListener('keydown', e => {
      const tabs = qsa('[role="tab"]', tabList);
      const idx = tabs.indexOf(document.activeElement);
      if (e.key === 'ArrowRight' && idx < tabs.length - 1) tabs[idx + 1].focus();
      if (e.key === 'ArrowLeft' && idx > 0) tabs[idx - 1].focus();
    });
  }

  // Tab buttons
  qsa('[role="tab"]').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    btn.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') switchTab(btn.dataset.tab); });
  });

  // ODO inputs
  ['coOdo', 'ciOdo'].forEach(id => {
    const el = qs(`#${id}`);
    if (!el) return;
    el.addEventListener('input', () => {
      const tabKey = id.startsWith('co') ? 'checkout' : 'checkin';
      state[tabKey].odo = el.value;
      renderOdo(tabKey);
      el.classList.remove('is-error');
      const errEl = qs(`#${id}Err`);
      if (errEl) { errEl.classList.remove('visible'); errEl.textContent = ''; }
    });
  });

  // Datetime inputs
  ['coDt', 'ciDt'].forEach(id => {
    const el = qs(`#${id}`);
    if (!el) return;
    el.addEventListener('change', () => {
      const tabKey = id.startsWith('co') ? 'checkout' : 'checkin';
      state[tabKey].datetime = el.value;
      el.classList.remove('is-error');
      const errEl = qs(`#${id}Err`);
      if (errEl) { errEl.classList.remove('visible'); errEl.textContent = ''; }
    });
  });

  // Clear errors on typing for other fields
  ['coCustName', 'ciCustName', 'coStaffName', 'ciStaffName'].forEach(id => {
    const el = qs(`#${id}`);
    if (!el) return;
    el.addEventListener('input', () => {
      el.classList.remove('is-error');
      const errEl = qs(`#${id}Err`);
      if (errEl) { errEl.classList.remove('visible'); errEl.textContent = ''; }
    });
  });

  // Fuel buttons
  qsa('.ho-fuel-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = btn.dataset.tab;
      state[tab].fuel = btn.dataset.level;
      renderFuel(tab);
    });
  });

  // Checklist select-all
  qsa('.ho-checklist-all').forEach(btn => {
    btn.addEventListener('click', () => checklistSelectAll(btn.dataset.tab));
  });

  // Add extra photo buttons
  qsa('.ho-photo-add-btn').forEach(btn => {
    btn.addEventListener('click', () => triggerPhotoUpload(btn.dataset.tab));
  });

  // Body diagram click
  ['co', 'ci'].forEach(prefix => {
    const diag = qs(`#${prefix}BodyDiagram`);
    if (!diag) return;
    const tabKey = prefix === 'co' ? 'checkout' : 'checkin';
    diag.addEventListener('click', (e) => {
      if (e.target.classList.contains('damage-pin')) return;
      const rect = diag.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * 100;
      const y = ((e.clientY - rect.top) / rect.height) * 100;
      const newDmg = {
        id: uid(), x, y,
        type: 'xước', severity: 'nhẹ', note: '', fee: 0,
        age: tabKey === 'checkout' ? 'old' : 'new',
      };
      state[tabKey].damages.push(newDmg);
      renderDamages(tabKey);
      openDamageModal(tabKey, newDmg);
    });
  });

  // Damage modal cancel
  qs('#dmgCancel')?.addEventListener('click', () => {
    // Remove last added pin if cancelled (it was already pushed)
    const tabKey = state.activeTab;
    // We only remove if cancel was for a new (uncommitted) damage
    // For simplicity: just close modal; pin is already in state
    closeDamageModal();
  });
  qs('#hoDamageModal')?.addEventListener('click', (e) => {
    if (e.target === qs('#hoDamageModal')) closeDamageModal();
  });

  // Lightbox close
  qs('#hoLightboxClose')?.addEventListener('click', closeLightbox);
  qs('#hoLightbox')?.addEventListener('click', e => { if (e.target === qs('#hoLightbox')) closeLightbox(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') { closeLightbox(); closeDamageModal(); } });

  // Signed paper protocol upload & name sync
  ['checkout', 'checkin'].forEach(tabKey => {
    const prefix = tabKey === 'checkout' ? 'co' : 'ci';
    const docZone = qs(`#${prefix}SignedDocZone`);
    if (docZone) {
      docZone.addEventListener('click', () => triggerSignedDocUpload(tabKey));
      docZone.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          triggerSignedDocUpload(tabKey);
        }
      });
    }

    // Name sync
    const custNameInput = qs(`#${prefix}CustName`);
    if (custNameInput) {
      custNameInput.addEventListener('input', () => {
        state[tabKey].customerName = custNameInput.value;
      });
    }
    const staffNameInput = qs(`#${prefix}StaffName`);
    if (staffNameInput) {
      staffNameInput.addEventListener('input', () => {
        state[tabKey].staffName = staffNameInput.value;
      });
    }
  });

  // Check-in settlement inputs
  const ciOvertime = qs('#ciOvertimeHours');
  if (ciOvertime) ciOvertime.addEventListener('input', () => { state.checkin.overtimeHours = ciOvertime.value; renderOdo('checkin'); });
  const ciCleaning = qs('#ciCleaningFee');
  if (ciCleaning) ciCleaning.addEventListener('change', () => { state.checkin.cleaningFee = ciCleaning.checked; renderSettlement(); });
  const ciCustomFee = qs('#ciCustomFee');
  if (ciCustomFee) ciCustomFee.addEventListener('input', () => { state.checkin.customFee = Number(ciCustomFee.value) || 0; renderSettlement(); });
  const ciCustomNote = qs('#ciCustomFeeNote');
  if (ciCustomNote) ciCustomNote.addEventListener('input', () => { state.checkin.customFeeNote = ciCustomNote.value; });

  // Note textareas
  qs('#coNote')?.addEventListener('input', e => { state.checkout.note = e.target.value; });
  qs('#ciNote')?.addEventListener('input', e => { state.checkin.note = e.target.value; });

  // Collateral policy & audit trail inputs
  function _nowLocalIso() {
    const d = new Date();
    const pad = n => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  qs('#hoPolicySelect')?.addEventListener('change', e => {
    const val = e.target.value;
    state.contract.depositType = val;
    if (val === 'VEHICLE_PLEDGE') {
      state.contract.deposit = 0;
    } else {
      state.contract.deposit = state.contract.baseDeposit || 5_000_000;
    }
    renderContractInfo();
    renderSettlement();
  });

  qs('#coCollateralInfo')?.addEventListener('input', e => {
    state.contract.collateralInfo = e.target.value;
    setText(qs('#ciCollateralInfoText'), e.target.value || 'Xe cá nhân + Giấy tờ gốc theo hợp đồng');
  });
  qs('#coCollateralHandler')?.addEventListener('input', e => {
    state.contract.collateralOutHandler = e.target.value;
  });
  qs('#coCollateralTime')?.addEventListener('change', e => {
    state.contract.collateralOutTime = e.target.value;
  });
  qs('#coCollateralHeld')?.addEventListener('change', e => {
    state.contract.collateralHeld = e.target.checked;
    if (e.target.checked && !state.contract.collateralOutTime) {
      state.contract.collateralOutTime = _nowLocalIso();
    }
    if (e.target.checked && !state.contract.collateralOutHandler) {
      state.contract.collateralOutHandler = qs('#coStaffName')?.value?.trim() || state.contract.staffName || '';
    }
    renderContractInfo();
  });
  qs('#coCollateralCustConfirmed')?.addEventListener('change', e => {
    state.contract.collateralOutCustConfirmed = e.target.checked;
    renderContractInfo();
  });

  qs('#ciCollateralHandler')?.addEventListener('input', e => {
    state.contract.collateralInHandler = e.target.value;
  });
  qs('#ciCollateralTime')?.addEventListener('change', e => {
    state.contract.collateralInTime = e.target.value;
  });
  qs('#ciCollateralReturned')?.addEventListener('change', e => {
    state.contract.collateralReturned = e.target.checked;
    if (e.target.checked && !state.contract.collateralInTime) {
      state.contract.collateralInTime = _nowLocalIso();
    }
    if (e.target.checked && !state.contract.collateralInHandler) {
      state.contract.collateralInHandler = qs('#ciStaffName')?.value?.trim() || state.contract.staffName || '';
    }
    renderContractInfo();
  });
  qs('#ciCollateralCustConfirmed')?.addEventListener('change', e => {
    state.contract.collateralInCustConfirmed = e.target.checked;
    renderContractInfo();
  });

  // Draft
  qs('#hoDraftBtn')?.addEventListener('click', saveDraft);

  // Submit
  qs('#hoSubmitBtn')?.addEventListener('click', () => submitHandover());

  // Print
  qs('#hoPrintBtn')?.addEventListener('click', () => window.print());
}

// ─────────────────────────────────────────────────────────────────────────────
// BOOT
// ─────────────────────────────────────────────────────────────────────────────
function boot() {
  // Đọc query parameters truyền từ trang danh sách đơn store-orders.html (nếu có)
  try {
    const params = new URLSearchParams(window.location.search);
    const bookingId = params.get('booking_id');
    const customer = params.get('customer');
    const phone = params.get('phone');
    const vehicle = params.get('vehicle');
    const plate = params.get('plate');
    const deposit = params.get('deposit');
    const depositType = params.get('deposit_type');
    const collateralInfo = params.get('collateral_info');

    if (bookingId) state.contract.contractId = bookingId;
    if (customer) {
      state.contract.customerName = customer;
      state.checkout.customerName = customer;
      state.checkin.customerName = customer;
    }
    if (phone) state.contract.customerPhone = phone;
    if (plate) state.contract.licensePlate = plate;
    if (vehicle) {
      state.contract.brand = vehicle;
      state.contract.model = '';
    }
    if (depositType) {
      const upper = depositType.toUpperCase();
      state.contract.depositType = (upper === 'VEHICLE_PLEDGE' || upper === 'COMBINED') ? upper : 'CASH';
    }
    if (collateralInfo) {
      state.contract.collateralInfo = collateralInfo;
    }
    if (deposit !== null && deposit !== '' && Number(deposit) > 0) {
      state.contract.baseDeposit = Number(deposit);
    }
    if (state.contract.depositType === 'VEHICLE_PLEDGE') {
      state.contract.deposit = 0;
    } else if (deposit !== null && deposit !== '') {
      state.contract.deposit = Number(deposit) || state.contract.deposit;
    }
  } catch (_) {}

  // Init checklists
  initChecklist('checkout');
  initChecklist('checkin');

  // Try load draft
  const hasDraft = loadDraft();

  // Render contract info
  renderContractInfo();

  // Render both phases
  ['checkout', 'checkin'].forEach(tabKey => {
    renderPhotos(tabKey);
    renderSignedDocs(tabKey);
    renderChecklist(tabKey);
    renderDamages(tabKey);
    renderFuel(tabKey);
    initDragDrop(tabKey);
  });

  // Prefill form fields from state / mock
  _prefillFormFields();

  // Render settlement
  renderSettlement();

  // Switch to initial tab
  switchTab(state.activeTab);

  // Bind all events
  bindEvents();

  if (hasDraft) {
    showToast('Đã khôi phục nháp lưu trước.', 'info', 3000);
    // Show draft badge
    const badge = qs('#hoDraftBadge');
    if (badge) badge.style.display = 'inline-flex';
  }
}

function _prefillFormFields() {
  const c = state.contract;
  // Checkout fields
  const coFields = {
    coCustName: state.checkout.customerName,
    coStaffName: state.checkout.staffName,
    coCustPhone: c.customerPhone,
    coCustCCCD: c.customerCCCD,
    coCustLicense: c.customerLicense,
    coPickupAddr: c.pickupAddr,
  };
  for (const [id, val] of Object.entries(coFields)) {
    const el = qs(`#${id}`);
    if (el) el.value = val || '';
  }
  // Checkin prefill names
  const ciFields = {
    ciCustName: state.checkin.customerName,
    ciStaffName: state.checkin.staffName,
  };
  for (const [id, val] of Object.entries(ciFields)) {
    const el = qs(`#${id}`);
    if (el) el.value = val || '';
  }
}

// Wait for DOM
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', boot);
} else {
  boot();
}

