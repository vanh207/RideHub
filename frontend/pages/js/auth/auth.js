/* ==========================================================================
   RideHub Auth Core, Demo Panel, Login Gate & Auth Chatbot (js/auth/auth.js)
   ========================================================================== */

import { DEMO_MODE, getUsers, saveUsers, hashMock, appendAuditLog, getDemoGroups } from './auth-mock.js';
import { createSession, clearSession, getCurrentUser, setReturnUrl, popReturnUrl, getGuestSessionId } from './session.js';
import { getRoleHome, ROLE_LABELS } from './permissions.js';
import { normalizeVNPhone } from './validators.js';
import { icon } from './icons.js';

export function loginWithPassword(identifier, password, { remember = false, allowedRoles = null } = {}) {
  const users = getUsers();
  const key = identifier.trim();
  const normPhone = normalizeVNPhone(key);
  const user = users.find((u) => u.username === key || u.email === key || (normPhone && u.phone === normPhone));

  if (!user) {
    appendAuditLog(key, 'Đăng nhập thất bại (Tài khoản không tồn tại)', 'failed');
    return { ok: false, code: 'NOT_FOUND', message: 'Số điện thoại hoặc tên đăng nhập chưa được đăng ký.' };
  }
  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return { ok: false, code: 'WRONG_PORTAL', message: 'Tài khoản này không thuộc cổng đăng nhập hiện tại.' };
  }
  if (user.status === 'locked') {
    appendAuditLog(user.username, 'Đăng nhập bị từ chối (Tài khoản bị khóa)', 'failed');
    return { ok: false, code: 'LOCKED', message: `Tài khoản đã bị khóa${user.lockReason ? ': ' + user.lockReason : '.'}` };
  }
  if (user.passHash !== hashMock(password)) {
    appendAuditLog(user.username, 'Đăng nhập thất bại (Sai mật khẩu)', 'failed');
    return { ok: false, code: 'BAD_PASS', message: 'Mật khẩu chưa chính xác.' };
  }

  createSession(user.id, remember);
  appendAuditLog(user.username, `Đăng nhập thành công (${ROLE_LABELS[user.role]})`, 'success');
  return { ok: true, user };
}

export function loginByPhoneOTP(phone, { remember = false, allowedRoles = ['customer', 'store_owner'] } = {}) {
  const norm = normalizeVNPhone(phone);
  const user = getUsers().find((u) => u.phone === norm);
  if (!user) return { ok: false, message: 'Số điện thoại chưa đăng ký tài khoản.' };
  if (allowedRoles && !allowedRoles.includes(user.role)) return { ok: false, message: 'Vai trò không hỗ trợ đăng nhập OTP tại đây.' };
  if (user.status === 'locked') return { ok: false, message: 'Tài khoản hiện đang bị khóa.' };
  createSession(user.id, remember);
  appendAuditLog(user.username, 'Đăng nhập bằng OTP thành công', 'success');
  return { ok: true, user };
}

export function registerCustomerAccount({ phone, name, dob, email, password }) {
  const users = getUsers();
  const norm = normalizeVNPhone(phone);
  if (users.some((u) => u.phone === norm)) {
    return { ok: false, message: 'Số điện thoại này đã có tài khoản. Vui lòng đăng nhập.' };
  }
  const newUser = {
    id: 'cus-' + Date.now(),
    phone: norm,
    username: norm,
    email: email || '',
    name: name.trim(),
    dob,
    address: '',
    role: 'customer',
    status: 'active',
    passHash: hashMock(password),
    kycStatus: 'not_submitted',
    licenseClass: '',
    licenseExpiry: '',
    cccdNumber: '',
    kycReason: ''
  };
  users.push(newUser);
  saveUsers(users);
  createSession(newUser.id, false);
  appendAuditLog(norm, 'Đăng ký tài khoản Khách thuê mới', 'success');
  return { ok: true, user: newUser };
}

export function registerStoreOwnerAccount(payload) {
  const users = getUsers();
  const norm = normalizeVNPhone(payload.phone);
  if (users.some((u) => u.phone === norm)) {
    return { ok: false, message: 'Số điện thoại đã được sử dụng.' };
  }
  const newOwner = {
    id: 'own-' + Date.now(),
    phone: norm,
    username: norm,
    email: payload.email,
    name: payload.name,
    storeName: payload.storeName,
    storeId: 'store-' + Date.now(),
    role: 'store_owner',
    status: 'active',
    passHash: hashMock(payload.password),
    storeStatus: 'pending',
    storeReason: '',
    taxCode: payload.taxCode,
    bankName: payload.bankName,
    bankAcc: payload.bankAcc,
    pickupPoints: payload.pickupPoints || []
  };
  users.push(newOwner);
  saveUsers(users);
  createSession(newOwner.id, false);
  appendAuditLog(norm, `Đăng ký gian hàng "${payload.storeName}" (Chờ duyệt)`, 'success');
  return { ok: true, user: newOwner };
}

export function resetPasswordByPhone(phone, newPassword) {
  const users = getUsers();
  const norm = normalizeVNPhone(phone);
  const idx = users.findIndex((u) => u.phone === norm);
  if (idx === -1) return { ok: false, message: 'Không tìm thấy tài khoản với số điện thoại này.' };
  users[idx].passHash = hashMock(newPassword);
  users[idx].mustChangePass = false;
  saveUsers(users);
  appendAuditLog(users[idx].username, 'Khôi phục mật khẩu qua OTP', 'success');
  return { ok: true };
}

export function logoutWithTransition(redirectUrl = '../../index.html') {
  const user = getCurrentUser();
  if (user) appendAuditLog(user.username, 'Đăng xuất tài khoản', 'success');
  const road = document.querySelector('.auth-road-stage');
  if (road) road.classList.add('is-accelerating');
  clearSession();
  setTimeout(() => { window.location.href = redirectUrl; }, 420);
}

export function redirectAfterLogin(user) {
  const target = popReturnUrl(getRoleHome(user));
  window.location.href = target;
}

/* Floating Demo Panel (DEMO_MODE = true) */
export function mountDemoPanel(onPickAccount) {
  if (!DEMO_MODE) return;
  const fab = document.createElement('button');
  fab.type = 'button';
  fab.className = 'demo-drawer-fab';
  fab.innerHTML = `${icon('key')} <span>Tài khoản thử (Demo)</span>`;

  const panel = document.createElement('div');
  panel.className = 'demo-drawer-panel';
  panel.setAttribute('aria-label', 'Danh sách tài khoản thử');

  const groups = getDemoGroups();
  panel.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
      <strong style="font-size:13px;color:var(--green-800);">Bấm để điền nhanh (Pass: Ridehub@123)</strong>
      <button type="button" class="btn btn-soft demo-close-btn" style="min-height:28px;padding:2px 10px;font-size:11px;">Đóng</button>
    </div>
    ${groups.map((g) => `
      <div style="font-size:11px;font-weight:800;color:var(--text-muted);margin:8px 0 4px;text-transform:uppercase;">${g.group}</div>
      ${g.items.map((u) => `
        <button type="button" class="demo-acc-item" data-username="${u.username}">
          <div>
            <strong>${u.username}</strong>
            <div style="color:var(--text-muted);font-size:11px;">${u.name}</div>
          </div>
          <span class="status-badge status-badge--available" style="font-size:10px;padding:2px 8px;">${u.kycStatus || u.storeStatus || u.status}</span>
        </button>
      `).join('')}
    `).join('')}
  `;

  document.body.append(fab, panel);
  fab.addEventListener('click', () => panel.classList.toggle('is-open'));
  panel.querySelector('.demo-close-btn').addEventListener('click', () => panel.classList.remove('is-open'));
  panel.querySelectorAll('.demo-acc-item').forEach((btn) => {
    btn.addEventListener('click', () => {
      const uname = btn.dataset.username;
      panel.classList.remove('is-open');
      if (onPickAccount) onPickAccount(uname, 'Ridehub@123');
    });
  });
}

/* Guest Login Gate Modal */
export function showLoginGateModal(actionLabel = 'tiếp tục thao tác này', loginPath = 'pages/xac-thuc/dang-nhap.html', registerPath = 'pages/xac-thuc/dang-ky-khach.html') {
  setReturnUrl(window.location.href);
  const existing = document.getElementById('loginGateModal');
  if (existing) existing.remove();

  const modal = document.createElement('div');
  modal.id = 'loginGateModal';
  modal.className = 'modal-backdrop is-open';
  modal.innerHTML = `
    <div class="modal-dialog" style="max-width:440px;text-align:center;">
      <div style="width:52px;height:52px;margin:0 auto 12px;border-radius:16px;background:var(--green-100);color:var(--green-700);display:grid;place-items:center;">
        ${icon('lock', 'rh-icon rh-icon--lg')}
      </div>
      <h3 style="margin:0 0 8px;">Đăng nhập để ${actionLabel}</h3>
      <p style="color:var(--text-secondary);font-size:14px;margin:0 0 18px;">
        Hệ thống sẽ giữ nguyên xe, thời gian và điểm nhận bạn đã chọn sau khi đăng nhập.
      </p>
      <div style="display:flex;flex-direction:column;gap:8px;">
        <a href="${loginPath}" class="btn btn-primary btn-premium btn-shine">Đăng nhập</a>
        <a href="${registerPath}" class="btn btn-soft btn-premium">Tạo tài khoản mới</a>
        <button type="button" class="btn btn-outline gate-dismiss-btn">Tiếp tục xem xe</button>
      </div>
    </div>
  `;
  document.body.appendChild(modal);
  modal.querySelector('.gate-dismiss-btn').addEventListener('click', () => modal.remove());
  modal.addEventListener('click', (e) => { if (e.target === modal) modal.remove(); });
}

/* Auth Chatbot AI Widget */
export function mountAuthChatbot(loginHref = 'dang-nhap.html') {
  const guestId = getGuestSessionId();
  const histKey = `rh_chat_hist_${guestId}`;

  const fab = document.createElement('button');
  fab.type = 'button';
  fab.className = 'chat-fab';
  fab.setAttribute('aria-label', 'Mở trợ lý AI RideHub');
  fab.innerHTML = `<span class="chat-fab-ring"></span>${icon('chat', 'rh-icon rh-icon--lg')}`;

  const win = document.createElement('div');
  win.className = 'chat-window';
  win.setAttribute('role', 'dialog');
  win.setAttribute('aria-label', 'Trợ lý AI RideHub');
  win.innerHTML = `
    <div style="padding:12px 16px;background:var(--green-600);color:#ffffff;display:flex;justify-content:space-between;align-items:center;">
      <strong>Trợ lý AI RideHub</strong>
      <button type="button" class="chat-close-x" style="border:0;background:transparent;color:#ffffff;font-weight:800;">Đóng</button>
    </div>
    <div class="chat-messages" id="authChatMsgs">
      <div class="chat-msg chat-msg--bot">Xin chào! Tôi có thể giải đáp về đăng ký, xác thực giấy tờ eKYC và điều kiện thuê xe.</div>
      <div style="display:flex;gap:6px;flex-wrap:wrap;">
        <button type="button" class="chat-quick-pill" data-q="Cách đăng ký">Cách đăng ký</button>
        <button type="button" class="chat-quick-pill" data-q="Vì sao cần xác thực giấy tờ">Vì sao cần xác thực giấy tờ</button>
        <button type="button" class="chat-quick-pill" data-q="Điều kiện thuê xe">Điều kiện thuê xe</button>
        <button type="button" class="chat-quick-pill" data-q="Tra cứu đơn của tôi">Tra cứu đơn của tôi</button>
      </div>
    </div>
    <div style="padding:10px;display:flex;gap:8px;border-top:1px solid var(--green-100);">
      <input id="authChatIn" type="text" placeholder="Hỏi trợ lý..." style="flex:1;padding:8px 12px;border-radius:99px;border:1px solid var(--green-200);outline:none;font-size:13px;" />
      <button id="authChatSend" class="btn btn-primary" style="min-height:36px;padding:6px 14px;" type="button">Gửi</button>
    </div>
  `;

  document.body.append(fab, win);
  const msgs = win.querySelector('#authChatMsgs');

  const answers = {
    'Cách đăng ký': 'Bạn chỉ cần 4 bước: Nhập SĐT (+84) → Xác thực OTP 6 số → Tạo mật khẩu → Hoàn tất trong 1 phút.',
    'Vì sao cần xác thực giấy tờ': 'Xác thực CCCD và GPLX giúp bảo vệ quyền lợi hai bên, kiểm tra hạng bằng hợp lệ (BR-25) và duyệt đơn tự động nhanh hơn.',
    'Điều kiện thuê xe': 'Bạn cần đủ 18 tuổi trở lên, có CCCD và GPLX còn hạn (A1/A2 cho xe máy ≥50cc, B1/B2 cho ô tô).'
  };

  const replyTo = (q) => {
    const u = document.createElement('div');
    u.className = 'chat-msg chat-msg--user';
    u.textContent = q;
    msgs.appendChild(u);

    const bot = document.createElement('div');
    bot.className = 'chat-msg chat-msg--bot';
    const user = getCurrentUser();
    if (q.toLowerCase().includes('đơn') && !user) {
      bot.innerHTML = `Vui lòng đăng nhập để tra cứu đơn hàng cá nhân. <div style="margin-top:8px;"><a href="${loginHref}" class="btn btn-primary" style="min-height:30px;padding:4px 12px;font-size:12px;">Đăng nhập ngay</a></div>`;
    } else {
      bot.textContent = answers[q] || 'Bạn có thể hoàn tất hồ sơ eKYC trong mục Tài khoản để đặt xe ngay trong 30 giây.';
    }
    msgs.appendChild(bot);
    msgs.scrollTop = msgs.scrollHeight;
    sessionStorage.setItem(histKey, msgs.innerHTML);
  };

  fab.addEventListener('click', () => win.classList.toggle('is-open'));
  win.querySelector('.chat-close-x').addEventListener('click', () => win.classList.remove('is-open'));
  win.querySelectorAll('.chat-quick-pill').forEach((p) => p.addEventListener('click', () => replyTo(p.dataset.q)));
  win.querySelector('#authChatSend').addEventListener('click', () => {
    const inp = win.querySelector('#authChatIn');
    if (inp.value.trim()) { replyTo(inp.value.trim()); inp.value = ''; }
  });
}

