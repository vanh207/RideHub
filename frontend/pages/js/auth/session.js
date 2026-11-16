/* ==========================================================================
   RideHub Session Manager & Masking Helpers (js/auth/session.js)
   ========================================================================== */

import { getUsers } from './auth-mock.js';

const SESSION_KEY = 'rh_active_session_v2';
const GUEST_KEY = 'rh_guest_session_id';
const RETURN_URL_KEY = 'rh_return_url';
const DEFAULT_TTL_MS = 30 * 60 * 1000; // 30 minutes
const REMEMBER_TTL_MS = 30 * 24 * 60 * 60 * 1000; // 30 days

export function getGuestSessionId() {
  let id = localStorage.getItem(GUEST_KEY);
  if (!id) {
    id = 'guest_' + Math.random().toString(36).slice(2, 10);
    localStorage.setItem(GUEST_KEY, id);
  }
  return id;
}

export function createSession(userId, remember = false) {
  const ttl = remember ? REMEMBER_TTL_MS : DEFAULT_TTL_MS;
  const session = {
    userId,
    token: 'rh_tok_' + Math.random().toString(36).slice(2) + Date.now().toString(36),
    remember,
    expiresAt: Date.now() + ttl
  };
  localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  return session;
}

export function getSession() {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const sess = JSON.parse(raw);
    if (Date.now() > sess.expiresAt) {
      return { ...sess, expired: true };
    }
    return sess;
  } catch (_) {
    return null;
  }
}

export function getCurrentUser() {
  const sess = getSession();
  if (!sess || sess.expired) return null;
  return getUsers().find((u) => u.id === sess.userId) || null;
}

export function clearSession() {
  localStorage.removeItem(SESSION_KEY);
}

export function renewSession() {
  const sess = getSession();
  if (!sess || sess.expired) return;
  const ttl = sess.remember ? REMEMBER_TTL_MS : DEFAULT_TTL_MS;
  sess.expiresAt = Date.now() + ttl;
  localStorage.setItem(SESSION_KEY, JSON.stringify(sess));
}

export function setReturnUrl(url) {
  if (url) sessionStorage.setItem(RETURN_URL_KEY, url);
}

export function popReturnUrl(fallback) {
  const url = sessionStorage.getItem(RETURN_URL_KEY);
  sessionStorage.removeItem(RETURN_URL_KEY);
  return url || fallback;
}

/* Masking Helpers (Privacy Display) */
export function maskPhone(phone = '') {
  if (phone.length < 7) return phone;
  return phone.slice(0, 3) + '****' + phone.slice(-3);
}

export function maskCCCD(cccd = '') {
  if (!cccd) return 'Chưa cập nhật';
  if (cccd.length < 6) return '***';
  return cccd.slice(0, 3) + '******' + cccd.slice(-3);
}

export function maskBankAcc(acc = '') {
  if (!acc) return '';
  return '******' + acc.slice(-4);
}

/* Activity Auto-Renew & 2-Minute Expiry Warning Modal */
export function initSessionMonitor(onExpired) {
  const sess = getSession();
  if (!sess || sess.expired) return;

  ['click', 'keydown'].forEach((ev) => {
    window.addEventListener(ev, () => renewSession(), { passive: true });
  });

  setInterval(() => {
    const current = getSession();
    if (!current) return;
    const remaining = current.expiresAt - Date.now();
    if (remaining <= 0) {
      clearSession();
      if (onExpired) onExpired();
    } else if (remaining <= 2 * 60 * 1000 && !document.getElementById('sessionWarnModal')) {
      showSessionWarningModal(Math.ceil(remaining / 1000));
    }
  }, 15000);
}

function showSessionWarningModal(secLeft) {
  const modal = document.createElement('div');
  modal.id = 'sessionWarnModal';
  modal.className = 'modal-backdrop is-open';
  modal.innerHTML = `
    <div class="modal-dialog" style="max-width:420px;text-align:center;">
      <h3 style="margin:0 0 8px;">Phiên đăng nhập sắp hết hạn</h3>
      <p style="color:var(--text-secondary);font-size:14px;margin:0 0 16px;">
        Phiên làm việc của bạn sẽ hết hạn sau <strong id="sessWarnSec">${secLeft}</strong> giây để bảo mật tài khoản.
      </p>
      <div style="display:flex;gap:10px;justify-content:center;">
        <button id="sessExtendBtn" class="btn btn-primary btn-premium" type="button">Tiếp tục phiên</button>
      </div>
    </div>
  `;
  document.body.appendChild(modal);
  document.getElementById('sessExtendBtn').addEventListener('click', () => {
    renewSession();
    modal.remove();
  });
}

