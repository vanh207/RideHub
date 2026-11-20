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
              <div class="table-empty-icon">📂</div>
              <div style="font-weight: 600; font-size: 14px;">${message}</div>
            </td>
          </tr>
        `;
      }
    }
  };

  // Tự động khởi chạy Modal Engine khi DOM sẵn sàng
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => RideHubUI.Modal.init());
  } else {
    RideHubUI.Modal.init();
  }

  // Tương thích ngược với showRideHubToast
  global.showRideHubToast = (msg, type = 'success') => RideHubUI.Toast.show(msg, type);

  // Xuất ra global scope
  global.RideHubUI = RideHubUI;

})(typeof window !== 'undefined' ? window : this);
