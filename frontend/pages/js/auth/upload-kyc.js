/* ==========================================================================
   RideHub KYC Drag & Drop Uploader (js/auth/upload-kyc.js)
   ========================================================================== */

import { validateImageFile } from './validators.js';
import { icon } from './icons.js';

export function mountKYCUploader(cardEl, { title, key, onChange } = {}) {
  if (!cardEl) return null;

  let fileState = { ok: false, url: '', zoom: 1, rotate: 0, isBlurry: false };

  cardEl.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
      <strong style="font-size:14px;">${title}</strong>
      <span class="kyc-sharp-badge" style="font-size:11px;font-weight:700;color:var(--text-muted);">Chưa tải</span>
    </div>
    <div class="kyc-dropzone" tabindex="0" role="button" aria-label="Tải lên ${title}">
      <input type="file" accept="image/jpeg,image/png" hidden />
      <div class="kyc-empty-state">
        <div style="color:var(--green-600);margin-bottom:8px;">${icon('upload', 'rh-icon rh-icon--lg')}</div>
        <div style="font-weight:700;font-size:13px;color:var(--green-800);">Kéo thả hoặc nhấn để chọn ảnh</div>
        <div style="font-size:11px;color:var(--text-muted);margin-top:4px;">JPG, PNG • Tối đa 5MB • Rõ nét</div>
      </div>
      <div class="kyc-preview-wrap" hidden>
        <img class="kyc-preview-img" alt="Xem trước ${title}" />
      </div>
    </div>
    <div class="kyc-toolbar" hidden>
      <button type="button" class="kyc-tool-btn" data-act="zoom">${icon('zoom-in')} Phóng to</button>
      <button type="button" class="kyc-tool-btn" data-act="rotate">${icon('rotate')} Xoay 90°</button>
      <button type="button" class="kyc-tool-btn" data-act="replace">Thay ảnh</button>
    </div>
    <div class="field-error-msg kyc-err" aria-live="polite"></div>
  `;

  const zone = cardEl.querySelector('.kyc-dropzone');
  const input = cardEl.querySelector('input[type="file"]');
  const emptyEl = cardEl.querySelector('.kyc-empty-state');
  const previewWrap = cardEl.querySelector('.kyc-preview-wrap');
  const previewImg = cardEl.querySelector('.kyc-preview-img');
  const toolbar = cardEl.querySelector('.kyc-toolbar');
  const badge = cardEl.querySelector('.kyc-sharp-badge');
  const errEl = cardEl.querySelector('.kyc-err');

  const applyTransform = () => {
    previewImg.style.transform = `scale(${fileState.zoom}) rotate(${fileState.rotate}deg)`;
  };

  const processFile = async (file) => {
    const res = await validateImageFile(file);
    if (!res.ok) {
      errEl.textContent = res.error;
      zone.classList.remove('field-shake');
      void zone.offsetWidth;
      zone.classList.add('field-shake');
      return;
    }
    errEl.textContent = '';
    fileState = { ok: true, url: res.url, zoom: 1, rotate: 0, isBlurry: res.isBlurry, key };
    previewImg.src = res.url;
    previewImg.classList.add('dropped-thumb');
    emptyEl.hidden = true;
    previewWrap.hidden = false;
    toolbar.hidden = false;
    applyTransform();

    if (res.isBlurry) {
      badge.textContent = 'Hơi mờ — nên chụp lại';
      badge.style.color = '#d97706';
    } else {
      badge.textContent = `Rõ nét (${res.width}x${res.height})`;
      badge.style.color = 'var(--green-700)';
    }
    if (onChange) onChange(fileState);
  };

  zone.addEventListener('click', (e) => {
    if (e.target.closest('.kyc-tool-btn')) return;
    if (emptyEl.hidden === false) input.click();
  });

  zone.addEventListener('keydown', (e) => {
    if ((e.key === 'Enter' || e.key === ' ') && !emptyEl.hidden) {
      e.preventDefault();
      input.click();
    }
  });

  input.addEventListener('change', () => {
    if (input.files?.[0]) processFile(input.files[0]);
  });

  ['dragenter', 'dragover'].forEach((ev) => {
    zone.addEventListener(ev, (e) => { e.preventDefault(); zone.classList.add('is-dragover'); });
  });
  ['dragleave', 'drop'].forEach((ev) => {
    zone.addEventListener(ev, (e) => { e.preventDefault(); zone.classList.remove('is-dragover'); });
  });
  zone.addEventListener('drop', (e) => {
    const f = e.dataTransfer?.files?.[0];
    if (f) processFile(f);
  });

  toolbar.querySelector('[data-act="zoom"]').addEventListener('click', () => {
    fileState.zoom = fileState.zoom >= 1.8 ? 1 : Number((fileState.zoom + 0.4).toFixed(1));
    applyTransform();
  });
  toolbar.querySelector('[data-act="rotate"]').addEventListener('click', () => {
    fileState.rotate = (fileState.rotate + 90) % 360;
    applyTransform();
  });
  toolbar.querySelector('[data-act="replace"]').addEventListener('click', () => input.click());

  return {
    getState: () => fileState,
    setMockUploaded: (label = 'Ảnh đã lưu từ hồ sơ trước') => {
      fileState = { ok: true, url: '', zoom: 1, rotate: 0, isBlurry: false, key };
      emptyEl.hidden = true;
      previewWrap.hidden = false;
      previewWrap.innerHTML = `<div style="padding:14px;font-size:13px;font-weight:700;color:var(--green-700);">${label}</div>`;
      toolbar.hidden = false;
      badge.textContent = 'Đạt chuẩn';
      badge.style.color = 'var(--green-700)';
    }
  };
}

