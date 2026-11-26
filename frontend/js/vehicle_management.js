
(function () {
  'use strict';

  const FLEET_KEY = 'ridehub_store_fleet_v2';
  const SYSTEM_CANCEL_POLICY = 'Trước 24h: hoàn 100% cọc • Trong 2–24h: hoàn 70% cọc • Dưới 2h: không hoàn cọc.';

  const DEFAULT_FLEET = [
    {
      id: 'v1', name: 'VinFast Feliz S', category: 'motorcycle',
      transmission: 'Xe tay ga', fuel: 'Điện', price: 160000,
      status: 'Sẵn sàng', alertText: 'Trống lịch 3 ngày tới',
      desc: 'Xe máy điện pin LFP đi được 198km/lần sạc, cốp 25L rộng rãi.',
      collateral: '500.000đ tiền cọc giữ xe (hoặc miễn thế chấp khi eKYC Đạt).',
      terms: 'Sử dụng đúng mục đích, không chở hàng cấm, tuân thủ luật giao thông.',
      surcharge: 'Vượt giới hạn 150km/ngày: 2.000đ/km • Trả trễ: 30.000đ/giờ • Vệ sinh: 30.000đ.',
      cancelMode: 'system', cancelPolicy: SYSTEM_CANCEL_POLICY, photos: []
    },
    {
      id: 'v2', name: 'VinFast VF 5', category: 'car',
      transmission: 'Số tự động', fuel: 'Điện', price: 750000,
      status: 'Đang thuê', alertText: 'Trả xe lúc 18:00 hôm nay',
      desc: 'Ô tô điện 4–5 chỗ nhỏ gọn, camera lùi, màn hình giải trí 8 inch.',
      collateral: '5.000.000đ tiền cọc hoặc xe máy chính chủ kèm cà vẹt gốc.',
      terms: 'Không hút thuốc trong xe, giữ gìn nội thất sạch sẽ, tuân thủ tốc độ.',
      surcharge: 'Vượt giới hạn 250km/ngày: 4.000đ/km • Trả trễ: 100.000đ/giờ.',
      cancelMode: 'system', cancelPolicy: SYSTEM_CANCEL_POLICY, photos: []
    },
    {
      id: 'v3', name: 'Dat Bike Weaver++', category: 'motorcycle',
      transmission: 'Xe côn tay', fuel: 'Điện', price: 220000,
      status: 'Đang vệ sinh', alertText: 'Sắp hết giờ vệ sinh xe',
      desc: 'Xe điện công suất mạnh mẽ, hỗ trợ sạc nhanh, phù hợp dạo phố.',
      collateral: '500.000đ tiền cọc giữ xe (hoặc miễn thế chấp khi eKYC Đạt).',
      terms: 'Không tự ý tháo pin hoặc can thiệp phần cứng xe.',
      surcharge: 'Trả trễ: 40.000đ/giờ • Vệ sinh: 40.000đ.',
      cancelMode: 'store', cancelPolicy: 'Hủy trước 48h: hoàn 100% cọc • Trong 48h: hoàn 50% cọc.', photos: []
    },
    {
      id: 'v4', name: 'Mazda 3 Sedan', category: 'car',
      transmission: 'Số tự động', fuel: 'Xăng', price: 850000,
      status: 'Bảo dưỡng', alertText: 'Đang ẩn khỏi tìm kiếm',
      desc: 'Sedan hạng C sang trọng, điều hòa 2 vùng, cruise control, cốp rộng.',
      collateral: '5.000.000đ tiền cọc giữ xe khi nhận xe.',
      terms: 'Đổ đúng xăng A95, không giao xe cho người khác điều khiển.',
      surcharge: 'Vượt 250km/ngày: 4.000đ/km • Trả trễ: 100.000đ/giờ.',
      cancelMode: 'system', cancelPolicy: SYSTEM_CANCEL_POLICY, photos: []
    }
  ];

  const STATUS_CYCLE = ['Sẵn sàng', 'Đang thuê', 'Đang vệ sinh', 'Bảo dưỡng'];
  const STATUS_BADGE_MAP = {
    'Sẵn sàng': 'status-badge--available',
    'Đang thuê': 'status-badge--transit',
    'Đang vệ sinh': 'status-badge--cleaning',
    'Bảo dưỡng': 'status-badge--maintenance'
  };

  function showToast(msg) {
    const box = document.getElementById('toastContainer');
    if (!box) return alert(msg);
    const t = document.createElement('div');
    t.style.cssText = 'background:#132a1c;color:#fff;padding:10px 16px;border-radius:10px;font-size:13px;margin-bottom:8px;box-shadow:0 4px 12px rgba(0,0,0,0.15);';
    t.textContent = msg;
    box.appendChild(t);
    setTimeout(() => t.remove(), 2500);
  }

  function getFleet() {
    try {
      const raw = localStorage.getItem(FLEET_KEY);
      if (raw) return JSON.parse(raw);
    } catch (_) {}
    localStorage.setItem(FLEET_KEY, JSON.stringify(DEFAULT_FLEET));
    return [...DEFAULT_FLEET];
  }

  let fleetList = getFleet();
  let editingVehicleIdx = null;
  let uploadedPhotoUrls = [];
  let sortAsc = true;

  const tbody = document.getElementById('fleetTableBody');
  const addModal = document.getElementById('addVehicleModal');
  const detailModal = document.getElementById('vehicleDetailModal');

  // 1. RENDER BẢNG PHƯƠNG TIỆN
  function renderFleet() {
    if (!tbody) return;
    tbody.innerHTML = fleetList.map((v, idx) => {
      const st = v.status || 'Sẵn sàng';
      const catLabel = v.category === 'car' ? 'Ô tô' : 'Xe máy';
      return `
        <tr>
          <td>
            <div style="display:flex;align-items:center;gap:10px;">
              <span style="font-size:18px;">${v.category === 'car' ? '🚗' : '🏍️'}</span>
              <div>
                <strong style="color:var(--text-primary);display:block;">${v.name}</strong>
                <span style="font-size:11px;color:var(--text-muted);">${v.photos?.length || 0} ảnh • ${v.id}</span>
              </div>
            </div>
          </td>
          <td>${catLabel} • ${v.transmission} • ${v.fuel}</td>
          <td><strong style="color:var(--green-700);">${Number(v.price).toLocaleString('vi-VN')}đ</strong></td>
          <td>
            <label class="status-badge ${STATUS_BADGE_MAP[st] || 'status-badge--available'}" style="cursor:pointer;display:inline-flex;align-items:center;gap:6px;">
              <select data-pick-status="${idx}" style="background:transparent;border:0;color:inherit;font-weight:700;font-size:12px;cursor:pointer;outline:none;">
                ${STATUS_CYCLE.map(opt => `<option value="${opt}" ${opt === st ? 'selected' : ''}>${opt}</option>`).join('')}
              </select>
            </label>
          </td>
          <td style="${st === 'Đang vệ sinh' ? 'color:#c2410c;font-weight:700;' : ''}">${v.alertText || 'Sẵn sàng'}</td>
          <td>
            <div style="display:flex;gap:6px;">
              <button class="btn btn-soft" style="min-height:28px;padding:2px 8px;font-size:12px;" type="button" data-view-veh="${idx}">Chi tiết</button>
              <button class="btn btn-soft" style="min-height:28px;padding:2px 8px;font-size:12px;" type="button" data-edit-veh="${idx}">Sửa</button>
              <button class="btn btn-soft" style="min-height:28px;padding:2px 8px;font-size:12px;color:#e11d48;" type="button" data-del-veh="${idx}">Xóa</button>
            </div>
          </td>
        </tr>
      `;
    }).join('');

    tbody.querySelectorAll('[data-pick-status]').forEach(sel => {
      sel.addEventListener('change', (e) => {
        const idx = Number(sel.dataset.pickStatus);
        fleetList[idx].status = e.target.value;
        localStorage.setItem(FLEET_KEY, JSON.stringify(fleetList));
        renderFleet();
        showToast(`Xe ${fleetList[idx].name} đã chuyển sang "${e.target.value}"`);
      });
    });

    tbody.querySelectorAll('[data-view-veh]').forEach(btn => {
      btn.addEventListener('click', () => openVehicleDetail(Number(btn.dataset.viewVeh)));
    });

    tbody.querySelectorAll('[data-edit-veh]').forEach(btn => {
      btn.addEventListener('click', () => openEditVehicleModal(Number(btn.dataset.editVeh)));
    });

    tbody.querySelectorAll('[data-del-veh]').forEach(btn => {
      btn.addEventListener('click', () => {
        const idx = Number(btn.dataset.delVeh);
        const cur = fleetList[idx];
        if (confirm(`Bạn có chắc muốn xóa xe "${cur.name}" khỏi kho?`)) {
          fleetList.splice(idx, 1);
          localStorage.setItem(FLEET_KEY, JSON.stringify(fleetList));
          renderFleet();
          showToast(`Đã xóa xe "${cur.name}" khỏi kho.`);
        }
      });
    });
  }

  // Sắp xếp theo giá
  document.getElementById('sortFleetTableBtn')?.addEventListener('click', () => {
    sortAsc = !sortAsc;
    fleetList.sort((a, b) => sortAsc ? a.price - b.price : b.price - a.price);
    renderFleet();
    showToast(sortAsc ? 'Đã sắp xếp giá: Thấp → Cao' : 'Đã sắp xếp giá: Cao → Thấp');
  });

  // 2. CHỌN HỘP SỐ THEO LOẠI XE
  const MOTORCYCLE_TRANSMISSIONS = ['Xe tay ga', 'Xe số', 'Xe côn tay', 'Xe điện'];
  const CAR_TRANSMISSIONS = ['Số tự động', 'Số sàn'];

  function updateTransmissionOptions(category, selectedVal) {
    const sel = document.getElementById('addVehTransmission');
    const lbl = document.getElementById('addVehTransmissionLabel');
    const motoLabel = document.getElementById('vehCatMotorcycleLabel');
    const carLabel = document.getElementById('vehCatCarLabel');
    if (!sel) return;

    if (category === 'car') {
      if (lbl) lbl.textContent = 'Loại hộp số ô tô';
      sel.innerHTML = CAR_TRANSMISSIONS.map(t => `<option value="${t}" ${t === selectedVal ? 'selected' : ''}>${t}</option>`).join('');
      if (motoLabel) { motoLabel.style.borderColor = '#e2e8f0'; motoLabel.style.background = '#fff'; motoLabel.style.color = 'var(--text-secondary)'; }
      if (carLabel) { carLabel.style.borderColor = 'var(--green-600)'; carLabel.style.background = 'var(--green-50)'; carLabel.style.color = 'var(--green-800)'; }
    } else {
      if (lbl) lbl.textContent = 'Loại xe máy';
      sel.innerHTML = MOTORCYCLE_TRANSMISSIONS.map(t => `<option value="${t}" ${t === selectedVal ? 'selected' : ''}>${t}</option>`).join('');
      if (motoLabel) { motoLabel.style.borderColor = 'var(--green-600)'; motoLabel.style.background = 'var(--green-50)'; motoLabel.style.color = 'var(--green-800)'; }
      if (carLabel) { carLabel.style.borderColor = '#e2e8f0'; carLabel.style.background = '#fff'; carLabel.style.color = 'var(--text-secondary)'; }
    }
  }

  document.querySelectorAll('input[name="addVehCategory"]').forEach(r => {
    r.addEventListener('change', () => updateTransmissionOptions(r.value));
  });

  // 3. XỬ LÝ TẢI ẢNH (Kéo thả + Preview)
  function renderPhotoPreviews() {
    const preview = document.getElementById('addVehPhotoPreview');
    const counter = document.getElementById('addVehPhotoCount');
    if (counter) counter.textContent = `${uploadedPhotoUrls.length} / 8 ảnh`;
    if (!preview) return;
    preview.innerHTML = uploadedPhotoUrls.map((src, idx) => `
      <div class="fleet-photo-item">
        <img src="${src}" alt="Ảnh xe ${idx + 1}" />
        <span class="fleet-photo-badge">${idx === 0 ? 'Ảnh bìa' : '#' + (idx + 1)}</span>
        <button type="button" class="fleet-photo-remove" data-remove-photo="${idx}">×</button>
      </div>
    `).join('');

    preview.querySelectorAll('[data-remove-photo]').forEach(btn => {
      btn.addEventListener('click', () => {
        uploadedPhotoUrls.splice(Number(btn.dataset.removePhoto), 1);
        renderPhotoPreviews();
      });
    });
  }

  function handlePhotoFiles(fileList) {
    const remaining = Math.max(0, 8 - uploadedPhotoUrls.length);
    const files = Array.from(fileList || []).filter(f => f.type.startsWith('image/')).slice(0, remaining);
    files.forEach(file => {
      const reader = new FileReader();
      reader.onload = () => {
        if (typeof reader.result === 'string' && uploadedPhotoUrls.length < 8) {
          uploadedPhotoUrls.push(reader.result);
          renderPhotoPreviews();
        }
      };
      reader.readAsDataURL(file);
    });
  }

  const dropzone = document.getElementById('addVehDropzone');
  const photoInput = document.getElementById('addVehPhotos');
  photoInput?.addEventListener('change', (e) => {
    handlePhotoFiles(e.target.files);
    e.target.value = '';
  });
  dropzone?.addEventListener('dragover', (e) => { e.preventDefault(); dropzone.style.borderColor = 'var(--green-600)'; });
  dropzone?.addEventListener('dragleave', () => { dropzone.style.borderColor = 'var(--green-400)'; });
  dropzone?.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.style.borderColor = 'var(--green-400)';
    handlePhotoFiles(e.dataTransfer?.files);
  });

  // 4. MỞ MODAL THÊM XE
  function prepareAddVehicleModal() {
    editingVehicleIdx = null;
    document.getElementById('addVehModalTitle').textContent = 'Thêm xe mới vào kho';
    const catRadio = document.querySelector('input[name="addVehCategory"][value="motorcycle"]');
    if (catRadio) catRadio.checked = true;
    updateTransmissionOptions('motorcycle', 'Xe tay ga');
    document.getElementById('addVehName').value = 'Honda Vision (2025)';
    document.getElementById('addVehPrice').value = 150000;
    const statusSelect = document.getElementById('addVehStatus');
    if (statusSelect) statusSelect.value = 'Sẵn sàng';
    uploadedPhotoUrls = [];
    renderPhotoPreviews();
    addModal.classList.add('is-open');
  }

  // 5. MỞ MODAL SỬA XE
  function openEditVehicleModal(idx) {
    const v = fleetList[idx];
    if (!v) return;
    editingVehicleIdx = idx;
    const cat = v.category || 'motorcycle';
    const catRadio = document.querySelector(`input[name="addVehCategory"][value="${cat}"]`);
    if (catRadio) catRadio.checked = true;
    updateTransmissionOptions(cat, v.transmission);

    document.getElementById('addVehModalTitle').textContent = `Chỉnh sửa xe: ${v.name}`;
    document.getElementById('addVehName').value = v.name || '';
    document.getElementById('addVehTransmission').value = v.transmission || (cat === 'car' ? 'Số tự động' : 'Xe tay ga');
    document.getElementById('addVehFuel').value = v.fuel || 'Điện';
    document.getElementById('addVehPrice').value = v.price || 150000;
    const statusSelect = document.getElementById('addVehStatus');
    if (statusSelect) statusSelect.value = v.status || 'Sẵn sàng';
    document.getElementById('addVehDesc').value = v.desc || '';
    document.getElementById('addVehCollateral').value = v.collateral || '';
    document.getElementById('addVehTerms').value = v.terms || '';
    document.getElementById('addVehSurcharge').value = v.surcharge || '';

    const mode = v.cancelMode === 'store' ? 'store' : 'system';
    const radio = document.querySelector(`input[name="cancelPolicyMode"][value="${mode}"]`);
    if (radio) radio.checked = true;
    document.getElementById('addVehSystemCancelPreview').hidden = mode === 'store';
    document.getElementById('addVehCustomCancelBox').hidden = mode !== 'store';
    if (mode === 'store') document.getElementById('addVehCustomCancel').value = v.cancelPolicy || '';

    uploadedPhotoUrls = Array.isArray(v.photos) ? [...v.photos] : [];
    renderPhotoPreviews();
    addModal.classList.add('is-open');
  }

  // 6. XEM CHI TIẾT XE
  function openVehicleDetail(idx) {
    const v = fleetList[idx];
    if (!v) return;
    const catLabel = v.category === 'car' ? 'Ô tô' : 'Xe máy';
    document.getElementById('vdStatusBadge').textContent = v.status;
    document.getElementById('vdTitle').textContent = v.name;
    document.getElementById('vdMeta').textContent = `${catLabel} • Giá: ${Number(v.price).toLocaleString('vi-VN')}đ/ngày`;
    const gallery = document.getElementById('vdGallery');
    if (v.photos && v.photos.length) {
      gallery.innerHTML = v.photos.map((src, i) => `<img src="${src}" alt="Ảnh ${i + 1}" style="width:100%;height:80px;object-fit:cover;border-radius:8px;" />`).join('');
    } else {
      gallery.innerHTML = '<span style="color:var(--text-muted);font-size:12px;">Chưa có ảnh tải lên</span>';
    }
    document.getElementById('vdSpecsRow').innerHTML = `
      <span class="status-badge status-badge--available">${catLabel}</span>
      <span class="status-badge status-badge--transit">${v.transmission}</span>
      <span class="status-badge">${v.fuel}</span>
    `;
    document.getElementById('vdDesc').textContent = v.desc || 'Chưa có mô tả.';
    document.getElementById('vdCollateral').textContent = v.collateral || 'Theo quy định cửa hàng.';
    document.getElementById('vdCancel').textContent = v.cancelPolicy || SYSTEM_CANCEL_POLICY;
    detailModal.classList.add('is-open');
  }

  // 7. LƯU THÊM MỚI HOẶC CẬP NHẬT XE
  document.getElementById('addVehicleForm')?.addEventListener('submit', (e) => {
    e.preventDefault();
    const mode = document.querySelector('input[name="cancelPolicyMode"]:checked')?.value || 'system';
    const customPolicy = document.getElementById('addVehCustomCancel').value.trim();
    const category = document.querySelector('input[name="addVehCategory"]:checked')?.value || 'motorcycle';

    const payload = {
      category,
      name: document.getElementById('addVehName').value.trim(),
      status: document.getElementById('addVehStatus')?.value || 'Sẵn sàng',
      transmission: document.getElementById('addVehTransmission').value,
      fuel: document.getElementById('addVehFuel').value,
      price: Number(document.getElementById('addVehPrice').value) || 150000,
      desc: document.getElementById('addVehDesc').value.trim(),
      collateral: document.getElementById('addVehCollateral').value.trim(),
      terms: document.getElementById('addVehTerms').value.trim(),
      surcharge: document.getElementById('addVehSurcharge').value.trim(),
      cancelMode: mode,
      cancelPolicy: mode === 'store' ? (customPolicy || SYSTEM_CANCEL_POLICY) : SYSTEM_CANCEL_POLICY,
      photos: [...uploadedPhotoUrls]
    };

    if (editingVehicleIdx !== null && fleetList[editingVehicleIdx]) {
      fleetList[editingVehicleIdx] = { ...fleetList[editingVehicleIdx], ...payload };
      showToast(`Đã cập nhật thông tin xe ${payload.name}!`);
    } else {
      fleetList.unshift({
        id: 'v_' + Date.now(),
        status: 'Sẵn sàng',
        alertText: 'Mới thêm vào kho',
        ...payload
      });
      showToast(`Đã thêm xe ${payload.name} (${payload.photos.length} ảnh) vào kho!`);
    }

    editingVehicleIdx = null;
    localStorage.setItem(FLEET_KEY, JSON.stringify(fleetList));
    renderFleet();
    addModal.classList.remove('is-open');
  });

  // Đóng mở modal
  document.getElementById('openAddVehicleBtn')?.addEventListener('click', prepareAddVehicleModal);
  document.getElementById('closeAddVehModalBtn')?.addEventListener('click', () => addModal.classList.remove('is-open'));
  document.getElementById('closeDetailModalBtn')?.addEventListener('click', () => detailModal.classList.remove('is-open'));

  // Đổi chế độ chính sách hủy
  document.querySelectorAll('input[name="cancelPolicyMode"]').forEach(radio => {
    radio.addEventListener('change', () => {
      const isStore = radio.value === 'store';
      document.getElementById('addVehSystemCancelPreview').hidden = isStore;
      document.getElementById('addVehCustomCancelBox').hidden = !isStore;
    });
  });

  // Khởi chạy hiển thị bảng lần đầu
  renderFleet();
})();