/**
 * ==============================================================================
 * RIDEHUB — SHARED COMPONENT ENGINE (COMPONENTS.JS)
 * Thư viện Component JavaScript dùng chung: Modals, Forms, Tables, Toasts.
 * ==============================================================================
 */

(function (global) {
  'use strict';

  const RideHubUI = {
    // --------------------------------------------------------------------------
    // 1. MODAL ENGINE
    // --------------------------------------------------------------------------
    Modal: {
      open(modalId) {
        const modal = typeof modalId === 'string' ? document.getElementById(modalId) : modalId;
        if (!modal) return;

        modal.classList.add('is-open');
        modal.classList.remove('is-hidden');
        if (modal.style.display === 'none') {
          modal.style.display = '';
        }
        document.body.style.overflow = 'hidden';

        // Dispatch custom event
        modal.dispatchEvent(new CustomEvent('modal:open', { bubbles: true }));
      },

      close(modalId) {
        const modal = typeof modalId === 'string' ? document.getElementById(modalId) : modalId;
        if (!modal) return;

        modal.classList.remove('is-open');
        // Check if there are other open modals before restoring scroll
        const remainingOpen = document.querySelectorAll('.modal-backdrop.is-open, .app-modal-backdrop.is-open');
        if (remainingOpen.length <= 1) {
          document.body.style.overflow = '';
        }

        modal.dispatchEvent(new CustomEvent('modal:close', { bubbles: true }));
      },

      toggle(modalId) {
        const modal = typeof modalId === 'string' ? document.getElementById(modalId) : modalId;
        if (!modal) return;
        if (modal.classList.contains('is-open')) {
          this.close(modal);
        } else {
          this.open(modal);
        }
      },

      init() {
        // Lắng nghe sự kiện click mở modal từ data attributes
        document.addEventListener('click', (e) => {
          const trigger = e.target.closest('[data-open-modal]');
          if (trigger) {
            e.preventDefault();
            const targetId = trigger.getAttribute('data-open-modal');
            RideHubUI.Modal.open(targetId);
            return;
          }

          // Lắng nghe nút đóng modal
          const closeBtn = e.target.closest('[data-close-modal], .modal-close-btn, .modal-close');
          if (closeBtn) {
            e.preventDefault();
            const parentModal = closeBtn.closest('.modal-backdrop, .app-modal-backdrop');
            if (parentModal) {
              RideHubUI.Modal.close(parentModal);
            }
            return;
          }

          // Bấm ra ngoài backdrop để đóng modal
          if (e.target.classList.contains('modal-backdrop') || e.target.classList.contains('app-modal-backdrop')) {
            RideHubUI.Modal.close(e.target);
          }
        });

        // Bấm phím ESC để đóng modal đang mở
        document.addEventListener('keydown', (e) => {
          if (e.key === 'Escape' || e.key === 'Esc') {
            const activeModal = document.querySelector('.modal-backdrop.is-open, .app-modal-backdrop.is-open');
            if (activeModal) {
              RideHubUI.Modal.close(activeModal);
            }
          }
        });
      }
    },

    // --------------------------------------------------------------------------
    // 2. TOAST ENGINE
    // --------------------------------------------------------------------------
    Toast: {
      getContainer() {
        let container = document.getElementById('toastContainer');
        if (!container) {
          container = document.createElement('div');
          container.id = 'toastContainer';
          container.className = 'toast-container';
          document.body.appendChild(container);
        }
        return container;
      },

      show(message, type = 'success', duration = 3500) {
        const container = this.getContainer();
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;

        let icon = '✅';
        if (type === 'error') icon = '❌';
        if (type === 'info') icon = 'ℹ️';
        if (type === 'warning') icon = '⚠️';

        toast.innerHTML = `
          <span style="font-size: 16px;">${icon}</span>
          <div style="flex: 1; font-size: 13.5px; font-weight: 600; line-height: 1.4;">${message}</div>
          <button type="button" style="background:none;border:none;cursor:pointer;color:#94a3b8;font-size:16px;padding:0 4px;" onclick="this.parentElement.remove();">&times;</button>
        `;

        container.appendChild(toast);

        setTimeout(() => {
          toast.style.opacity = '0';
          toast.style.transform = 'translateY(8px)';
          toast.style.transition = 'all 0.25s ease';
          setTimeout(() => toast.remove(), 250);
        }, duration);
      }
    },

    // --------------------------------------------------------------------------
    // 3. FORM UTILITIES
    // --------------------------------------------------------------------------
    Form: {
      serialize(formElement) {
        if (!formElement) return {};
        const formData = new FormData(formElement);
        const data = {};
        for (const [key, value] of formData.entries()) {
          data[key] = value;
        }
        return data;
      },

      setLoading(buttonElement, isLoading, loadingText = 'Đang xử lý...') {
        if (!buttonElement) return;
        if (isLoading) {
          buttonElement.dataset.originalHtml = buttonElement.innerHTML;
          buttonElement.classList.add('is-loading');
          buttonElement.disabled = true;
          if (loadingText) {
            buttonElement.innerHTML = `<span>${loadingText}</span>`;
          }
        } else {
          buttonElement.classList.remove('is-loading');
          buttonElement.disabled = false;
          if (buttonElement.dataset.originalHtml) {
            buttonElement.innerHTML = buttonElement.dataset.originalHtml;
          }
        }
      },

      showFieldError(inputElement, errorMessage) {
        if (!inputElement) return;
        inputElement.classList.add('is-invalid');
        const parent = inputElement.closest('.form-group, .float-field') || inputElement.parentElement;
        let errorSpan = parent.querySelector('.form-error, .input-error');
        if (!errorSpan) {
          errorSpan = document.createElement('div');
          errorSpan.className = 'form-error';
          parent.appendChild(errorSpan);
        }
        errorSpan.textContent = errorMessage;
      },

      clearFieldError(inputElement) {
        if (!inputElement) return;
        inputElement.classList.remove('is-invalid');
        const parent = inputElement.closest('.form-group, .float-field') || inputElement.parentElement;
        const errorSpan = parent.querySelector('.form-error, .input-error');
        if (errorSpan) errorSpan.remove();
      }
    },

    // --------------------------------------------------------------------------
    // 4. TABLE UTILITIES
    // --------------------------------------------------------------------------
    Table: {
      renderEmpty(tbodyElement, message = 'Chưa có dữ liệu hiển thị.', colSpan = 6) {
        if (!tbodyElement) return;
        tbodyElement.innerHTML = `
          <tr>
            <td colspan="${colSpan}" class="table-empty">
              <div style="font-weight: 600; font-size: 14px;">${message}</div>
            </td>
          </tr>
        `;
      }
    },

    // --------------------------------------------------------------------------
    // 5. GLOBAL PAGE & SECTION LOADING ENGINE
    // --------------------------------------------------------------------------
    Loader: {
      _el: null,
      _safetyTimer: null,

      _getLogoSrc() {
        return window.location.pathname.includes('/pages/')
          ? '../assets/logo-rh.png'
          : 'assets/logo-rh.png';
      },

      _ensureStyles() {
        if (document.getElementById('rhMotoLoaderStyle')) return;
        const style = document.createElement('style');
        style.id = 'rhMotoLoaderStyle';
        style.textContent = `
          .rh-moto-overlay {
            position: fixed;
            inset: 0;
            z-index: 9999;
            background: linear-gradient(160deg, #f0fdf4, #ffffff 55%, #ecfccb);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 20px;
            opacity: 1;
            transition: opacity 0.3s ease;
          }
          .rh-moto-overlay.is-hidden {
            display: none !important;
          }
          .rh-moto-track {
            position: relative;
            width: min(440px, 84vw);
            height: 64px;
            overflow: hidden;
            border-bottom: 3px solid #86efac;
          }
          .rh-moto-track::after {
            content: "";
            position: absolute;
            left: 0;
            right: 0;
            bottom: 4px;
            height: 2px;
            background: repeating-linear-gradient(90deg, #4ade80 0 18px, transparent 18px 34px);
            opacity: 0.55;
          }
          .rh-moto-runner {
            position: absolute;
            bottom: 6px;
            left: -80px;
            width: 72px;
            height: 46px;
            animation: rhMotoLoop 1.35s cubic-bezier(0.22, 1, 0.36, 1) infinite;
          }
          .rh-moto-runner .wheel-spin,
          .rh-inline-moto-icon .wheel-spin {
            transform-box: fill-box;
            transform-origin: center;
            animation: rhMotoWheel 0.45s linear infinite;
          }
          .rh-inline-moto-loader {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 10px;
            padding: 20px 12px;
            color: #475569;
            font-size: 13px;
            font-weight: 600;
          }
          .rh-inline-moto-track {
            position: relative;
            width: 180px;
            height: 36px;
            overflow: hidden;
            border-bottom: 2px solid #86efac;
          }
          .rh-inline-moto-track::after {
            content: "";
            position: absolute;
            left: 0;
            right: 0;
            bottom: 3px;
            height: 1.5px;
            background: repeating-linear-gradient(90deg, #4ade80 0 10px, transparent 10px 20px);
            opacity: 0.55;
          }
          .rh-inline-moto-icon {
            position: absolute;
            bottom: 4px;
            left: -52px;
            width: 46px;
            height: 29px;
            animation: rhInlineMotoLoop 1.25s cubic-bezier(0.22, 1, 0.36, 1) infinite;
          }
          @keyframes rhMotoLoop {
            0% { transform: translate3d(0, 0, 0) scale(0.95); }
            75% { transform: translate3d(calc(min(440px, 84vw) * 0.72), -1px, 0) scale(1); }
            100% { transform: translate3d(calc(min(440px, 84vw) + 120px), -2px, 0) scale(1.06); }
          }
          @keyframes rhInlineMotoLoop {
            0% { transform: translate3d(0, 0, 0); }
            100% { transform: translate3d(240px, 0, 0); }
          }
          @keyframes rhMotoWheel {
            to { transform: rotate(360deg); }
          }
        `;
        document.head.appendChild(style);
      },

      _motoSvg(w = 72, h = 46) {
        return `
          <svg viewBox="0 0 110 64" width="${w}" height="${h}" aria-hidden="true">
            <path d="M22 36 C28 22, 46 20, 60 25 L76 17 L85 20 L75 36 Z" fill="#22c55e" />
            <path d="M32 25 C40 20, 52 20, 58 25 L48 29 L30 29 Z" fill="#132a1c" />
            <g transform="translate(27,45)">
              <g class="wheel-spin">
                <circle r="11" fill="#132a1c" />
                <circle r="5" fill="#dcfce7" />
                <line x1="-5" y1="0" x2="5" y2="0" stroke="#22c55e" stroke-width="1.6" />
              </g>
            </g>
            <g transform="translate(81,45)">
              <g class="wheel-spin">
                <circle r="11" fill="#132a1c" />
                <circle r="5" fill="#dcfce7" />
                <line x1="-5" y1="0" x2="5" y2="0" stroke="#22c55e" stroke-width="1.6" />
              </g>
            </g>
          </svg>
        `;
      },

      _ensureElement() {
        this._ensureStyles();
        if (this._el && document.body.contains(this._el)) return this._el;
        let el = document.getElementById('rhPageLoader');
        if (!el) {
          el = document.createElement('div');
          el.id = 'rhPageLoader';
          el.className = 'rh-moto-overlay is-hidden';
          el.setAttribute('role', 'status');
          el.setAttribute('aria-live', 'polite');
          el.innerHTML = `
            <div style="display:flex;align-items:center;gap:12px;">
              <img src="${this._getLogoSrc()}" alt="RideHub" style="height:42px;width:auto;object-fit:contain;" />
              <span style="font-family:var(--font-display, Outfit, sans-serif);font-weight:800;font-size:1.5rem;color:#15803d;">RideHub</span>
            </div>
            <div class="rh-moto-track">
              <div class="rh-moto-runner">${this._motoSvg(72, 46)}</div>
            </div>
            <div class="rh-loader-text" id="rhPageLoaderText" style="font-size:13px;font-weight:600;color:#64748b;">Đang tải dữ liệu...</div>
          `;
          document.body.appendChild(el);
        }
        this._el = el;
        return el;
      },

      show(message = 'Đang xử lý yêu cầu...') {
        if (!document.body) return;
        const el = this._ensureElement();
        const textEl = el.querySelector('#rhPageLoaderText');
        if (textEl) textEl.textContent = message;
        el.classList.remove('is-hidden');

        clearTimeout(this._safetyTimer);
        this._safetyTimer = setTimeout(() => this.hide(), 4000);
      },

      hide() {
        clearTimeout(this._safetyTimer);
        const el = this._el || document.getElementById('rhPageLoader');
        if (el) el.classList.add('is-hidden');
      },

      showInline(container, message = 'Đang tải dữ liệu...') {
        if (!container) return;
        this._ensureStyles();
        const inlineHtml = `
          <div class="rh-inline-moto-loader">
            <div class="rh-inline-moto-track">
              <div class="rh-inline-moto-icon">${this._motoSvg(46, 29)}</div>
            </div>
            <span>${message}</span>
          </div>
        `;
        if (container.tagName === 'TBODY') {
          const cols = container.closest('table')?.querySelectorAll('thead th').length || 6;
          container.innerHTML = `<tr><td colspan="${cols}">${inlineHtml}</td></tr>`;
        } else {
          container.innerHTML = inlineHtml;
        }
      },

      init() {
        this._ensureElement();
        this.hide();
        window.addEventListener('pageshow', () => this.hide());
      }
    }
  };

  // Tự động khởi chạy Modal & Loader Engine khi DOM sẵn sàng
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      RideHubUI.Modal.init();
      RideHubUI.Loader.init();
    });
  } else {
    RideHubUI.Modal.init();
    RideHubUI.Loader.init();
  }

  // Tương thích ngược với showRideHubToast
  global.showRideHubToast = (msg, type = 'success') => RideHubUI.Toast.show(msg, type);

  // Xuất ra global scope
  global.RideHubUI = RideHubUI;

})(typeof window !== 'undefined' ? window : this);
