/* ==========================================================================
   RideHub Route Guard & Action Visibility (js/auth/auth-guard.js)
   ========================================================================== */

import { getCurrentUser, getSession, setReturnUrl, initSessionMonitor } from './session.js';
import { can, ROLE_LABELS } from './permissions.js';

export function requireAuth({
  allowedRoles = null,
  loginUrl = '../xac-thuc/dang-nhap.html',
  forbiddenUrl = '../xac-thuc/403.html',
  requireApprovedStore = false
} = {}) {
  const sess = getSession();
  const user = getCurrentUser();

  if (!sess || sess.expired || !user) {
    setReturnUrl(window.location.href);
    window.location.href = loginUrl + (sess?.expired ? '?expired=1' : '');
    return null;
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    window.location.href = forbiddenUrl;
    return null;
  }

  if (requireApprovedStore && user.role === 'store_owner' && user.storeStatus !== 'approved') {
    window.location.href = '../xac-thuc/cho-duyet-cua-hang.html';
    return null;
  }

  // Apply granular [data-can] hiding
  document.querySelectorAll('[data-can]').forEach((el) => {
    const action = el.getAttribute('data-can');
    if (!can(action, user)) {
      el.hidden = true;
    }
  });

  // Render active user pill if header slot exists
  const slot = document.getElementById('authUserBadge');
  if (slot) {
    slot.textContent = `${user.name} (${ROLE_LABELS[user.role] || user.role})`;
  }

  // Monitor session expiration
  initSessionMonitor(() => {
    showExpiredModal(loginUrl);
  });

  return user;
}

function showExpiredModal(loginUrl) {
  setReturnUrl(window.location.href);
  const modal = document.createElement('div');
  modal.className = 'modal-backdrop is-open';
  modal.innerHTML = `
    <div class="modal-dialog" style="max-width:420px;text-align:center;">
      <h3 style="margin:0 0 8px;">Phiên đăng nhập đã hết hạn</h3>
      <p style="color:var(--text-secondary);font-size:14px;margin:0 0 18px;">
        Vui lòng đăng nhập lại để tiếp tục thao tác tại trang này.
      </p>
      <a href="${loginUrl}" class="btn btn-primary btn-premium">Đăng nhập lại</a>
    </div>
  `;
  document.body.appendChild(modal);
}

