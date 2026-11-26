/* ==========================================================================
   RideHub Authentication & Role-Based Access Control (auth-rbac.js)
   3 Roles: customer (Khách thuê), store_owner (Chủ cửa hàng), admin (Quản trị hệ thống)
   ========================================================================== */

(function (global) {
  'use strict';

  // Bật kiểm tra phân quyền giao diện HTML/JS theo vai trò (customer / store_owner / admin)
  const DISABLE_FRONTEND_RBAC = false;

  const STORAGE_USER = 'ridehub_current_user';
  const STORAGE_ACCOUNTS = 'ridehub_accounts_db';
  const STORAGE_NOTIFS = 'ridehub_notifications_v1';

  const DEFAULT_NOTIFS_BY_ROLE = {
    customer: [
      { id: 'c1', type: 'payment', title: 'Đơn thuê đã được cửa hàng duyệt', body: 'Cửa hàng GreenRide Q1 đã duyệt đơn #RH-8842 (Honda Vision 2024). Vui lòng hoàn tất cọc 30%.', time: '5 phút trước', link: 'booking.html', read: false },
      { id: 'c2', type: 'alert', title: 'Sắp đến giờ nhận xe', body: 'Chuyến đi #RH-8835 (VinFast VF5 Plus) còn 1 ngày 04 giờ nữa bắt đầu.', time: '1 giờ trước', link: 'trips.html', read: false },
      { id: 'c3', type: 'system', title: 'Xác thực GPLX hợp lệ', body: 'Hồ sơ Giấy phép lái xe của bạn đã được đồng bộ, sẵn sàng thuê xe không cần thế chấp.', time: 'Hôm qua', link: 'profile.html', read: true }
    ],
    store_owner: [
      { id: 'so1', type: 'booking', title: 'Đơn thuê mới chờ duyệt', body: 'Khách Nguyễn Văn An vừa gửi yêu cầu thuê Honda Vision 2024 (2 ngày) • Giao tận nơi.', time: '3 phút trước', link: 'store-portal.html', read: false },
      { id: 'so2', type: 'payment', title: 'Khách đã thanh toán cọc 30%', body: 'Đơn #RH-8842 đã ghi nhận cọc 108.000đ qua VietQR. Chuẩn bị bàn giao xe.', time: '28 phút trước', link: 'store-portal.html', read: false },
      { id: 'so3', type: 'system', title: 'Báo cáo doanh thu tuần', body: 'Doanh thu cửa hàng tuần này đạt 14.850.000đ (+18% so với tuần trước).', time: 'Hôm qua', link: 'store-portal.html', read: true }
    ],
    admin: [
      { id: 'ad1', type: 'system', title: 'Phê duyệt đối tác mới', body: 'Có 2 hồ sơ chủ cửa hàng đang chờ Admin phê duyệt kích hoạt trên hệ thống.', time: '8 phút trước', link: 'admin-ops.html', read: false },
      { id: 'ad2', type: 'payment', title: 'Đối soát giao dịch đặt cọc', body: 'Hệ thống ghi nhận 28 giao dịch VietQR thành công trong 24h qua.', time: '1 giờ trước', link: 'admin-ops.html', read: false },
      { id: 'ad3', type: 'alert', title: 'Nhật ký kiểm toán hệ thống', body: 'Đã hoàn tất kiểm tra đối soát giao dịch và giải quyết các khiếu nại phát sinh.', time: 'Hôm qua', link: 'admin-ops.html', read: true }
    ]
  };

  const ROLES = {
    guest: {
      label: 'Khách vãng lai',
      badgeClass: 'status-badge--available',
      home: 'index.html',
      menu: [
        { label: 'Trang chủ', href: 'index.html' },
        { label: 'Tìm & Thuê xe', href: 'vehicles.html' },
        { label: 'Hướng dẫn thuê xe', href: 'index.html#storySection' }
      ],
      allowedPages: [
        'index.html', 'vehicles.html', 'vehicle-detail.html', 'booking.html',
        'payment-qr.html', 'payment-result.html', 'auth.html', 'privacy-policy.html'
      ]
    },
    customer: {
      label: 'Khách thuê',
      badgeClass: 'status-badge--available',
      home: 'vehicles.html',
      menu: [
        { label: 'Trang chủ', href: 'index.html' },
        { label: 'Tìm & Thuê xe', href: 'vehicles.html' },
        { label: 'Chuyến đi', href: 'trips.html' },
        { label: 'Đơn đặt xe', href: 'booking.html' },
        { label: 'Hướng dẫn thuê xe', href: 'index.html#storySection' }
      ],
      allowedPages: [
        'index.html', 'vehicles.html', 'vehicle-detail.html', 'booking.html',
        'payment-qr.html', 'payment-result.html', 'trips.html',
        'profile.html', 'auth.html', 'chat.html', 'privacy-policy.html'
      ]
    },
    store_owner: {
      label: 'Chủ cửa hàng',
      badgeClass: 'status-badge--transit',
      home: 'pages/store-orders.html',
      menu: [
        { label: 'Trang chủ', href: 'index.html' },
        { label: 'Đơn thuê', href: 'pages/store-orders.html' },
        { label: 'Quản lý xe', href: 'pages/vehicle_management.html' },
        { label: 'Lịch xe', href: 'pages/vehicle_schedule.html' },
        { label: 'Bàn giao xe', href: 'pages/handover.html' },
        { label: 'Giao nhận', href: 'pages/delivery.html' }
      ],
      allowedPages: [
        'index.html', 'store-portal.html', 'store-orders.html', 'store_operations.html',
        'vehicle_management.html', 'vehicle_schedule.html', 'handover.html', 'delivery.html',
        'profile.html', 'auth.html', 'chat.html', 'privacy-policy.html'
      ]
    },
    admin: {
      label: 'Quản trị hệ thống',
      badgeClass: 'status-badge--maintenance',
      home: 'pages/admin-policies-audit.html',
      menu: [
        { label: 'Trang chủ', href: 'index.html' },
        { label: 'Hàng chờ bất thường', href: 'pages/operations-anomalies.html' },
        { label: 'Chính sách & Audit', href: 'pages/admin-policies-audit.html' }
      ],
      allowedPages: [
        'index.html', 'admin-ops.html', 'operations-anomalies.html',
        'admin-policies-audit.html', 'test-cases.html',
        'profile.html', 'auth.html', 'chat.html', 'privacy-policy.html'
      ]
    }
  };

  const DEFAULT_ACCOUNTS = [];

  const AuthRBAC = {
    getAccounts() {
      let list = [];
      try {
        const raw = localStorage.getItem(STORAGE_ACCOUNTS);
        if (raw) list = JSON.parse(raw);
      } catch (_) {}
      return Array.isArray(list) ? list : [];
    },

    saveAccounts(list) {
      localStorage.setItem(STORAGE_ACCOUNTS, JSON.stringify(list));
    },

    setCurrentUser(user) {
      if (user) {
        localStorage.setItem(STORAGE_USER, JSON.stringify(user));
      } else {
        localStorage.removeItem(STORAGE_USER);
      }
    },

    getCurrentUser() {
      try {
        const raw = localStorage.getItem(STORAGE_USER);
        if (!raw) return null;
        let u = JSON.parse(raw);
        if (u && (u.role === 'store_staff' || u.role === 'operator')) {
          u.role = u.role === 'store_staff' ? 'store_owner' : 'admin';
          u.name = u.role === 'store_owner' ? 'Chủ xe GreenRide Q1' : 'Admin Hệ thống';
          u.email = u.role === 'store_owner' ? 'greenride@ridehub.vn' : 'admin@ridehub.vn';
          localStorage.setItem(STORAGE_USER, JSON.stringify(u));
        }
        return u;
      } catch (_) {
        return null;
      }
    },

    login(identifier, pass) {
      const key = identifier.trim().toLowerCase();
      const acc = this.getAccounts().find((a) =>
        ((a.email && a.email.toLowerCase() === key) || a.phone === key) && a.pass === pass
      );
      if (!acc) return { ok: false, message: 'Sai email hoặc mật khẩu!' };
      localStorage.setItem(STORAGE_USER, JSON.stringify(acc));
      return { ok: true, user: acc };
    },

    loginAsRole(role) {
      const acc = this.getAccounts().find((a) => a.role === role);
      if (!acc) return;
      localStorage.setItem(STORAGE_USER, JSON.stringify(acc));
      this.applyUI();
      if (global.showRideHubToast) {
        global.showRideHubToast(`Đã chuyển sang vai trò: ${ROLES[role].label}`);
      }
    },

    register({ phone, email, name, pass, role, ...extra }) {
      const list = this.getAccounts();
      const mail = (email || '').trim().toLowerCase();
      if (mail && list.some((a) => a.email && a.email.toLowerCase() === mail)) {
        return { ok: false, message: 'Email này đã được đăng ký!' };
      }
      if (list.some((a) => a.phone === phone.trim())) {
        return { ok: false, message: 'Số điện thoại này đã được đăng ký!' };
      }
      const newUser = { phone: phone.trim(), email: mail, name: name.trim(), pass, role: role || 'customer', ...extra };
      list.push(newUser);
      this.saveAccounts(list);
      localStorage.setItem(STORAGE_USER, JSON.stringify(newUser));
      return { ok: true, user: newUser };
    },

    hasEmail(email) {
      const mail = (email || '').trim().toLowerCase();
      return this.getAccounts().some((a) => a.email && a.email.toLowerCase() === mail);
    },

    resetPasswordByEmail(email, newPass) {
      const list = this.getAccounts();
      const mail = (email || '').trim().toLowerCase();
      const idx = list.findIndex((a) => a.email && a.email.toLowerCase() === mail);
      if (idx === -1) return { ok: false, message: 'Email này chưa được đăng ký tài khoản!' };
      list[idx].pass = newPass;
      this.saveAccounts(list);
      return { ok: true };
    },

    updateProfile(patch) {
      const cur = this.getCurrentUser();
      if (!cur) return { ok: false, message: 'Bạn chưa đăng nhập.' };
      const list = this.getAccounts();
      const idx = list.findIndex((a) => a.phone === cur.phone && a.email === cur.email);
      const updated = { ...cur, ...patch };
      if (idx !== -1) {
        list[idx] = updated;
        this.saveAccounts(list);
      }
      localStorage.setItem(STORAGE_USER, JSON.stringify(updated));
      this.applyUI();
      return { ok: true, user: updated };
    },

    changePassword(oldPass, newPass) {
      const cur = this.getCurrentUser();
      if (!cur) return { ok: false, message: 'Bạn chưa đăng nhập.' };
      if (cur.pass !== oldPass) return { ok: false, message: 'Mật khẩu hiện tại chưa đúng!' };
      return this.updateProfile({ pass: newPass });
    },

    logout() {
      const delCookie = (name) => {
        document.cookie = `${name}=; path=/; expires=Thu, 01 Jan 1970 00:00:01 GMT; SameSite=Lax`;
      };
      delCookie('ridehub_token');
      delCookie('access_token');
      delCookie('token');
      delCookie('ridehub_auth_token');
      delCookie('ridehub_refresh_token');

      localStorage.removeItem(STORAGE_USER);
      localStorage.removeItem('ridehub_token');
      localStorage.removeItem('token');
      localStorage.removeItem('ridehub_auth_token');
      localStorage.removeItem('ridehub_refresh_token');
      this.applyUI();
      if (global.showRideHubToast) global.showRideHubToast('Đã đăng xuất tài khoản.');
    },

    confirmAction({
      title = 'Xác nhận thao tác',
      message = 'Bạn có chắc chắn muốn thực hiện thao tác này?',
      confirmText = 'Xác nhận',
      cancelText = 'Hủy',
      danger = false,
    } = {}) {
      return new Promise((resolve) => {
        document.getElementById('rhConfirmDialogModal')?.remove();
        const backdrop = document.createElement('div');
        backdrop.id = 'rhConfirmDialogModal';
        backdrop.style.cssText =
          'position:fixed;inset:0;z-index:9998;background:rgba(15,23,42,0.52);backdrop-filter:blur(4px);display:flex;align-items:center;justify-content:center;padding:16px;';
        backdrop.innerHTML = `
          <div role="dialog" aria-modal="true" style="width:min(420px,100%);background:#ffffff;border-radius:18px;padding:22px 24px;box-shadow:0 20px 50px rgba(15,23,42,0.22);border:1px solid #e2e8f0;">
            <h3 style="margin:0 0 8px;font-family:var(--font-display,Outfit,sans-serif);font-size:1.15rem;color:#0f172a;">${title}</h3>
            <p style="margin:0 0 18px;font-size:14px;line-height:1.55;color:#475569;">${message}</p>
            <div style="display:flex;justify-content:flex-end;gap:10px;">
              <button type="button" id="rhConfirmCancelBtn" class="btn btn-soft" style="min-height:38px;padding:6px 16px;font-size:13px;">${cancelText}</button>
              <button type="button" id="rhConfirmOkBtn" class="btn ${danger ? '' : 'btn-primary'}" style="min-height:38px;padding:6px 16px;font-size:13px;${danger ? 'background:#dc2626;color:#ffffff;border:none;' : ''}">${confirmText}</button>
            </div>
          </div>
        `;
        const cleanup = (result) => {
          document.removeEventListener('keydown', onKey);
          backdrop.remove();
          resolve(result);
        };
        const onKey = (e) => {
          if (e.key === 'Escape') cleanup(false);
        };
        document.addEventListener('keydown', onKey);
        backdrop.addEventListener('click', (e) => {
          if (e.target === backdrop) cleanup(false);
        });
        backdrop.querySelector('#rhConfirmCancelBtn').addEventListener('click', () => cleanup(false));
        backdrop.querySelector('#rhConfirmOkBtn').addEventListener('click', () => cleanup(true));
        document.body.appendChild(backdrop);
        backdrop.querySelector('#rhConfirmOkBtn').focus();
      });
    },

    getToken() {
      try {
        const fromCookie = (document.cookie.match(/(^| )ridehub_token=([^;]+)/) || [])[2]
                        || (document.cookie.match(/(^| )access_token=([^;]+)/) || [])[2]
                        || (document.cookie.match(/(^| )token=([^;]+)/) || [])[2];
        if (fromCookie) return decodeURIComponent(fromCookie);
        return localStorage.getItem('ridehub_token') || localStorage.getItem('token') || '';
      } catch (_) {
        return '';
      }
    },

    getCurrentPageName() {
      const path = window.location.pathname.split('/').pop();
      return path || 'index.html';
    },

    _loadNotifMap() {
      let map = {};
      try {
        const raw = localStorage.getItem(STORAGE_NOTIFS);
        if (raw) map = JSON.parse(raw) || {};
      } catch (_) {}
      let changed = false;
      Object.keys(DEFAULT_NOTIFS_BY_ROLE).forEach((r) => {
        if (!Array.isArray(map[r])) {
          map[r] = DEFAULT_NOTIFS_BY_ROLE[r].map((n) => ({ ...n }));
          changed = true;
        }
      });
      if (changed) localStorage.setItem(STORAGE_NOTIFS, JSON.stringify(map));
      return map;
    },

    _getApiBase() {
      if (global.CONFIG && global.CONFIG.API_BASE_URL) {
        return String(global.CONFIG.API_BASE_URL).replace(/\/+$/, '');
      }
      return 'http://127.0.0.1:8000/api';
    },

    _apiHeaders(hasBody = false) {
      const token = this.getToken();
      return {
        Accept: 'application/json',
        ...(hasBody ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      };
    },

    getNotifications(role) {
      if (this._apiNotifCache && Array.isArray(this._apiNotifCache[role])) {
        return this._apiNotifCache[role];
      }
      const map = this._loadNotifMap();
      return Array.isArray(map[role]) ? map[role] : [];
    },

    async fetchNotificationsFromApi(role) {
      if (!role || role === 'guest') return;
      if (!this._apiNotifCache) this._apiNotifCache = {};
      if (this._notifFetchingRole === role) return;
      this._notifFetchingRole = role;
      try {
        const res = await fetch(`${this._getApiBase()}/notifications`, {
          headers: this._apiHeaders(false),
          credentials: 'include',
        });
        if (!res.ok) return;
        const data = await res.json();
        if (data && Array.isArray(data.items)) {
          this._apiNotifCache[role] = data.items;
          const cur = this.getCurrentUser();
          if (cur && cur.role === role) {
            this._renderNotifListOnly(role, this._notifFilter || 'all');
          }
        }
      } catch (_) {
        // Fallback to localStorage cache when backend is unreachable
      } finally {
        this._notifFetchingRole = null;
      }
    },

    pushNotification({ role, roles, title, body, link = '', type = 'booking' }) {
      const targets = Array.isArray(roles) ? roles : [role || 'customer'];
      const map = this._loadNotifMap();
      targets.forEach((r) => {
        if (!Array.isArray(map[r])) map[r] = [];
        map[r].unshift({
          id: 'n_' + Date.now() + '_' + Math.random().toString(36).slice(2, 6),
          type,
          title,
          body,
          time: 'Vừa xong',
          link,
          read: false
        });
      });
      localStorage.setItem(STORAGE_NOTIFS, JSON.stringify(map));
      const cur = this.getCurrentUser();
      if (cur && targets.includes(cur.role)) {
        this._renderNotifPanel(cur.role);
      }
    },

    markNotificationRead(role, id) {
      if (this._apiNotifCache && Array.isArray(this._apiNotifCache[role])) {
        const cached = this._apiNotifCache[role].find((n) => String(n.id) === String(id));
        if (cached) cached.read = true;
      }
      const map = this._loadNotifMap();
      const list = map[role];
      if (Array.isArray(list)) {
        const item = list.find((n) => String(n.id) === String(id));
        if (item && !item.read) {
          item.read = true;
          localStorage.setItem(STORAGE_NOTIFS, JSON.stringify(map));
        }
      }
      if (/^\d+$/.test(String(id))) {
        fetch(`${this._getApiBase()}/notifications/${id}/read`, {
          method: 'PATCH',
          headers: this._apiHeaders(false),
          credentials: 'include',
        }).catch(() => {});
      }
    },

    markAllNotificationsRead(role) {
      if (this._apiNotifCache && Array.isArray(this._apiNotifCache[role])) {
        this._apiNotifCache[role].forEach((n) => { n.read = true; });
      }
      const map = this._loadNotifMap();
      const list = map[role];
      if (Array.isArray(list)) {
        list.forEach((n) => { n.read = true; });
        localStorage.setItem(STORAGE_NOTIFS, JSON.stringify(map));
      }
      fetch(`${this._getApiBase()}/notifications/read-all`, {
        method: 'PATCH',
        headers: this._apiHeaders(false),
        credentials: 'include',
      }).catch(() => {});
      this._renderNotifListOnly(role, this._notifFilter || 'all');
    },

    _getNotifIconSvg(type) {
      if (type === 'payment') {
        return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="2" y="5" width="20" height="14" rx="3"/><path d="M2 10h20"/></svg>';
      }
      if (type === 'alert') {
        return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16h.01"/></svg>';
      }
      if (type === 'system') {
        return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 2l7 4v6c0 5-3.5 8.5-7 10-3.5-1.5-7-5-7-10V6l7-4z"/></svg>';
      }
      return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/></svg>';
    },

    _renderNotifPanel(role, filter = this._notifFilter || 'all') {
      this._renderNotifListOnly(role, filter);
      this.fetchNotificationsFromApi(role);
    },

    _renderNotifListOnly(role, filter = this._notifFilter || 'all') {
      this._notifFilter = filter;
      const listEl = document.getElementById('rbacNotifList');
      const badgeEl = document.getElementById('rbacNotifBadge');
      if (!listEl) return;

      const allItems = this.getNotifications(role);
      const unreadCount = allItems.filter((n) => !n.read).length;

      if (badgeEl) {
        if (unreadCount > 0) {
          badgeEl.textContent = unreadCount > 9 ? '9+' : String(unreadCount);
          badgeEl.hidden = false;
        } else {
          badgeEl.hidden = true;
        }
      }

      document.querySelectorAll('.notif-tab[data-notif-filter]').forEach((tab) => {
        tab.classList.toggle('is-active', tab.dataset.notifFilter === filter);
      });

      const items = filter === 'unread' ? allItems.filter((n) => !n.read) : allItems;
      if (!items.length) {
        listEl.innerHTML = `<div class="notif-empty">${filter === 'unread' ? 'Không có thông báo chưa đọc.' : 'Chưa có thông báo nào.'}</div>`;
        return;
      }

      listEl.innerHTML = items.map((n) => `
        <button type="button" class="notif-item ${n.read ? '' : 'is-unread'}" data-notif-id="${n.id}" data-notif-link="${n.link || ''}">
          <span class="notif-icon notif-icon--${n.type || 'booking'}">${this._getNotifIconSvg(n.type)}</span>
          <span class="notif-content">
            <div class="notif-title">${n.title}</div>
            <div class="notif-body">${n.body}</div>
            <div class="notif-time">${n.time}</div>
          </span>
          ${n.read ? '' : '<span class="notif-dot" aria-label="Chưa đọc"></span>'}
        </button>
      `).join('');

      const inPagesDir = window.location.pathname.includes('/pages/');
      const resolveNotifLink = (href) => {
        if (!href || href.startsWith('#') || href.startsWith('http')) return href;
        if (inPagesDir) return href.startsWith('pages/') ? href.slice(6) : `../${href}`;
        return href;
      };

      listEl.querySelectorAll('.notif-item').forEach((btn) => {
        btn.addEventListener('click', () => {
          const id = btn.dataset.notifId;
          const link = btn.dataset.notifLink;
          this.markNotificationRead(role, id);
          this._renderNotifListOnly(role, this._notifFilter);
          if (link && link !== this.getCurrentPageName()) {
            window.location.href = resolveNotifLink(link);
          } else {
            document.getElementById('rbacNotifDropdown')?.classList.remove('is-open');
            document.getElementById('rbacNotifBtn')?.setAttribute('aria-expanded', 'false');
          }
        });
      });
    },

    applyUI() {
      const currentPage = this.getCurrentPageName();
      const isAuthPage = currentPage === 'auth.html' || window.location.pathname.includes('auth.html');

      // Trên trang Đăng nhập / Đăng ký: Xóa bỏ và không hiển thị bất kỳ Avatar / Notif nào
      if (isAuthPage) {
        document.querySelectorAll('#rbacUserPill, #rhUserWrap, #rhNotifWrap, #rbacNotifWrap, .user-menu-wrap, .notif-wrap, .user-avatar-trigger').forEach(el => el.remove());
        return;
      }

      const user = this.getCurrentUser();
      const roleInfo = user ? ROLES[user.role] : null;

      // 1. Update Navbar User Pill
      const navActions = document.querySelector('.nav-actions');
      if (navActions) {
        let userPill = document.getElementById('rbacUserPill');
        if (!userPill) {
          userPill = document.createElement('div');
          userPill.id = 'rbacUserPill';
          userPill.style.cssText = 'display:inline-flex;align-items:center;gap:8px;';
          navActions.prepend(userPill);
        }

        if (user && roleInfo) {
          const inPagesDir = window.location.pathname.includes('/pages/');
          const rootPfx = inPagesDir ? '../' : '';
          const initials = (user.name || 'U').trim().split(/\s+/).slice(-1)[0].slice(0, 1).toUpperCase();
          const avatarInner = user.avatarUrl
            ? `<img src="${user.avatarUrl}" alt="${user.name}" style="width:100%;height:100%;object-fit:cover;">`
            : initials;
          userPill.innerHTML = `
            <div class="notif-wrap" id="rbacNotifWrap">
              <button id="rbacNotifBtn" class="notif-bell-btn" type="button" aria-label="Thông báo" aria-expanded="false" aria-haspopup="true">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
                  <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
                </svg>
                <span id="rbacNotifBadge" class="notif-badge" hidden>0</span>
              </button>
              <div id="rbacNotifDropdown" class="notif-dropdown" role="dialog" aria-label="Thông báo theo vai trò">
                <div class="notif-header">
                  <div class="notif-header-title">
                    <span>Thông báo</span>
                    <span class="notif-role-pill">${roleInfo.label}</span>
                  </div>
                  <button id="rbacNotifReadAll" class="notif-readall-btn" type="button">Đọc tất cả</button>
                </div>
                <div class="notif-tabs">
                  <button type="button" class="notif-tab is-active" data-notif-filter="all">Tất cả</button>
                  <button type="button" class="notif-tab" data-notif-filter="unread">Chưa đọc</button>
                </div>
                <div id="rbacNotifList" class="notif-list"></div>
              </div>
            </div>
            <div class="user-menu-wrap">
              <button id="rbacAvatarBtn" class="user-avatar-trigger" type="button" aria-expanded="false" aria-haspopup="true">
                <span class="user-avatar-circle">${avatarInner}</span>
                <span>${user.name}</span>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>
              </button>
              <div id="rbacAvatarDropdown" class="user-avatar-dropdown" role="menu">
                <div style="padding:8px 12px 10px;border-bottom:1px solid var(--green-100);margin-bottom:6px;">
                  <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;">
                    <div style="font-size:13px;font-weight:800;color:var(--text-primary);">${user.name}</div>
                    ${(user.is_verified || user.verified || user.cccdStatus === 'approved' || user.role === 'admin')
                      ? '<span style="padding:2px 8px;border-radius:999px;background:#dcfce7;color:#15803d;font-size:10.5px;font-weight:700;white-space:nowrap;">Đã xác thực</span>'
                      : '<span style="padding:2px 8px;border-radius:999px;background:#fef3c7;color:#b45309;font-size:10.5px;font-weight:700;white-space:nowrap;">Chưa xác thực</span>'}
                  </div>
                  <div style="font-size:11px;color:var(--text-muted);margin-top:2px;">${user.email || user.phone} • ${roleInfo.label}</div>
                </div>
                <a href="${rootPfx}profile.html" class="user-menu-item" role="menuitem">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="8" r="4"/><path d="M4 20c1.5-3.8 4.8-5.5 8-5.5s6.5 1.7 8 5.5"/></svg>
                  <span>Hồ sơ</span>
                </a>
                <a href="${rootPfx}chat.html" class="user-menu-item" role="menuitem">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>
                  <span>Tin nhắn &amp; Hỗ trợ</span>
                </a>
                ${user.role === 'customer' ? `
                <a href="${rootPfx}trips.html" class="user-menu-item" role="menuitem">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>
                  <span>Chuyến đi</span>
                </a>` : ''}
                <a href="${rootPfx}profile.html#change-password" class="user-menu-item" role="menuitem">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="5" y="11" width="14" height="10" rx="3"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>
                  <span>Đổi mật khẩu</span>
                </a>
                <button id="rbacLogoutBtn" class="user-menu-item user-menu-item--danger" style="border-top:1px solid var(--green-100);margin-top:2px;" type="button" role="menuitem">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/></svg>
                  <span>Đăng xuất</span>
                </button>
              </div>
            </div>
          `;

          this._renderNotifPanel(user.role, 'all');

          const notifBtn = document.getElementById('rbacNotifBtn');
          const notifDropdown = document.getElementById('rbacNotifDropdown');
          const avatarBtn = document.getElementById('rbacAvatarBtn');
          const dropdown = document.getElementById('rbacAvatarDropdown');

          notifBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            dropdown?.classList.remove('is-open');
            avatarBtn?.setAttribute('aria-expanded', 'false');
            const open = notifDropdown.classList.toggle('is-open');
            notifBtn.setAttribute('aria-expanded', String(open));
          });

          document.getElementById('rbacNotifReadAll')?.addEventListener('click', (e) => {
            e.stopPropagation();
            this.markAllNotificationsRead(user.role);
          });

          notifDropdown?.querySelectorAll('.notif-tab[data-notif-filter]').forEach((tab) => {
            tab.addEventListener('click', (e) => {
              e.stopPropagation();
              this._renderNotifPanel(user.role, tab.dataset.notifFilter);
            });
          });

          avatarBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            notifDropdown?.classList.remove('is-open');
            notifBtn?.setAttribute('aria-expanded', 'false');
            const open = dropdown.classList.toggle('is-open');
            avatarBtn.setAttribute('aria-expanded', String(open));
          });

          if (!global.__rbacOutsideClickBound) {
            global.__rbacOutsideClickBound = true;
            document.addEventListener('click', (e) => {
              const avBtn = document.getElementById('rbacAvatarBtn');
              const avDrop = document.getElementById('rbacAvatarDropdown');
              const nBtn = document.getElementById('rbacNotifBtn');
              const nDrop = document.getElementById('rbacNotifDropdown');
              if (avDrop && avBtn && !avDrop.contains(e.target) && !avBtn.contains(e.target)) {
                avDrop.classList.remove('is-open');
                avBtn.setAttribute('aria-expanded', 'false');
              }
              if (nDrop && nBtn && !nDrop.contains(e.target) && !nBtn.contains(e.target)) {
                nDrop.classList.remove('is-open');
                nBtn.setAttribute('aria-expanded', 'false');
              }
            });
          }



          document.getElementById('rbacLogoutBtn')?.addEventListener('click', async () => {
            const ok = await this.confirmAction({
              title: 'Xác nhận đăng xuất',
              message: 'Bạn có chắc chắn muốn đăng xuất khỏi tài khoản hiện tại không?',
              confirmText: 'Đăng xuất',
              cancelText: 'Hủy',
              danger: true,
            });
            if (!ok) return;
            this.logout();
            const isPublicPage = currentPage === 'index.html' || currentPage === 'vehicles.html' || currentPage === 'auth.html' || currentPage === 'privacy-policy.html';
            if (!isPublicPage) {
              const authUrl = window.location.pathname.includes('/pages/') ? 'auth.html' : 'pages/auth.html';
              window.location.href = authUrl;
            }
          });
        } else {
          const authUrl = window.location.pathname.includes('/pages/') ? 'auth.html' : 'pages/auth.html';
          userPill.innerHTML = `<a href="${authUrl}" class="btn btn-soft" style="min-height:38px;padding:6px 14px;font-size:13px;">Đăng nhập</a>`;
        }
      }

      // 2. Render Header (.nav-links) & Mobile Drawer (.mobile-drawer) riêng cho từng role (4 roles: guest, customer, store_owner, admin)
      const activeRoleKey = user && ROLES[user.role] ? user.role : 'guest';
      const activeRoleCfg = ROLES[activeRoleKey];
      const inPagesDir = window.location.pathname.includes('/pages/');
      const rootPfx = inPagesDir ? '../' : '';
      const resolveRoleHref = (href) => {
        if (!href || href.startsWith('#') || href.startsWith('http')) return href;
        if (inPagesDir) {
          return href.startsWith('pages/') ? href.slice(6) : `../${href}`;
        }
        return href;
      };

      const alwaysPublicPages = ROLES.guest.allowedPages;
      const allowed = activeRoleCfg ? activeRoleCfg.allowedPages : alwaysPublicPages;

      if (!DISABLE_FRONTEND_RBAC && activeRoleCfg && Array.isArray(activeRoleCfg.menu)) {
        const navLinksContainer = document.querySelector('.nav-links');
        if (navLinksContainer) {
          navLinksContainer.innerHTML = activeRoleCfg.menu
            .map((item) => {
              const targetHref = resolveRoleHref(item.href);
              const pageName = item.href.split('#')[0].split('/').pop();
              const isActive = currentPage === pageName && !item.href.includes('#');
              return `<a href="${targetHref}" class="nav-link${isActive ? ' is-active' : ''}">${item.label}</a>`;
            })
            .join('');
        }
        const mobileDrawer = document.getElementById('mobileDrawer');
        if (mobileDrawer) {
          mobileDrawer.innerHTML = activeRoleCfg.menu
            .map((item) => `<a href="${resolveRoleHref(item.href)}">${item.label}</a>`)
            .join('');
        }
      }

      // 3. Enforce Page Guard (403 Forbidden if unauthorized) — tạm tắt khi DISABLE_FRONTEND_RBAC = true
      const existingGuard = document.getElementById('rbacGuardOverlay');
      if (existingGuard) existingGuard.remove();

      const isPublic = alwaysPublicPages.includes(currentPage);
      if (!DISABLE_FRONTEND_RBAC && !isPublic && !allowed.includes(currentPage)) {
        const guard = document.createElement('div');
        guard.id = 'rbacGuardOverlay';
        guard.style.cssText = 'position:fixed;inset:0;z-index:180;background:rgba(248,252,249,0.96);backdrop-filter:blur(10px);display:flex;align-items:center;justify-content:center;padding:24px;';

        guard.innerHTML = `
          <div class="panel-card" style="max-width:480px;text-align:center;">
            <span class="eyebrow" style="background:#fee2e2;color:#b91c1c;">403 • Phân quyền truy cập</span>
            <h2 style="margin:8px 0;font-family:var(--font-display);">Quyền truy cập bị giới hạn</h2>
            <p style="color:var(--text-secondary);font-size:14px;margin:0 0 12px;">
              ${user ? `Bạn đang đăng nhập với tài khoản: <strong>${user.name} (${roleInfo.label})</strong>.` : 'Trang này yêu cầu quyền truy cập phù hợp.'}
            </p>
            <div style="display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin-top:10px;">
              <a href="${resolveRoleHref('pages/auth.html')}" class="btn btn-soft" style="font-size:12px;">Mở trang đăng nhập (auth.html)</a>
              <a href="${resolveRoleHref(roleInfo ? roleInfo.home : 'index.html')}" class="btn btn-soft" style="font-size:12px;">Về trang chủ</a>
            </div>
          </div>
        `;
        document.body.appendChild(guard);
      }

      // 4. Enforce Tab-Level Restrictions (tạm tắt khi DISABLE_FRONTEND_RBAC = true)
      if (!DISABLE_FRONTEND_RBAC && roleInfo && roleInfo.restrictedTabs) {
        roleInfo.restrictedTabs.forEach((tabName) => {
          const tabBtn = document.querySelector(`.tab-btn[data-tab="${tabName}"]`);
          if (tabBtn) {
            tabBtn.disabled = true;
            tabBtn.style.opacity = '0.45';
            tabBtn.style.cursor = 'not-allowed';
            tabBtn.title = 'Vai trò của bạn không có quyền truy cập mục này';
            tabBtn.innerHTML = tabBtn.textContent + ' (Khóa)';
          }
        });
      }
    }
  };

  const initPageTransitionLoader = () => {
    if (global.__rhTransitionLoaderInit) return;
    global.__rhTransitionLoaderInit = true;

    const inPagesDir = window.location.pathname.includes('/pages/');
    const logoSrc = inPagesDir ? '../assets/logo-rh.png' : 'assets/logo-rh.png';

    if (!document.getElementById('rhTransitionLoaderStyle')) {
      const style = document.createElement('style');
      style.id = 'rhTransitionLoaderStyle';
      style.textContent = `
        .rh-nav-loader {
          position: fixed;
          inset: 0;
          z-index: 9999;
          background: linear-gradient(160deg, #f0fdf4, #ffffff 55%, #ecfccb);
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 20px;
          clip-path: inset(0 0 0 0);
          opacity: 1;
          transition: clip-path 0.72s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.35s ease;
        }
        .rh-nav-loader.is-revealing {
          clip-path: inset(0 0 100% 0);
          pointer-events: none;
        }
        .rh-nav-loader.is-done {
          display: none;
        }
        .rh-nav-road-track {
          position: relative;
          width: min(440px, 84vw);
          height: 64px;
          overflow: hidden;
          border-bottom: 3px solid #86efac;
        }
        .rh-nav-road-track::after {
          content: "";
          position: absolute;
          left: 0;
          right: 0;
          bottom: 4px;
          height: 2px;
          background: repeating-linear-gradient(90deg, #4ade80 0 18px, transparent 18px 34px);
          opacity: 0.55;
        }
        .rh-nav-moto {
          position: absolute;
          bottom: 6px;
          left: -80px;
          width: 72px;
          height: 46px;
          animation: rhNavMotoZoom 1.1s cubic-bezier(0.22, 1, 0.36, 1) forwards;
        }
        .rh-nav-moto .wheel-spin {
          transform-box: fill-box;
          transform-origin: center;
          animation: rhNavWheelSpin 0.45s linear infinite;
        }
        @keyframes rhNavMotoZoom {
          0% { transform: translate3d(0, 0, 0) scale(0.95); }
          75% { transform: translate3d(calc(min(440px, 84vw) * 0.72), -1px, 0) scale(1); }
          100% { transform: translate3d(calc(min(440px, 84vw) + 120px), -2px, 0) scale(1.06); }
        }
        @keyframes rhNavWheelSpin {
          to { transform: rotate(360deg); }
        }
      `;
      document.head.appendChild(style);
    }

    const createLoaderEl = (labelText) => {
      let el = document.getElementById('rhNavPageLoader');
      if (el) el.remove();
      el = document.createElement('div');
      el.id = 'rhNavPageLoader';
      el.className = 'rh-nav-loader';
      el.setAttribute('aria-hidden', 'true');
      el.innerHTML = `
        <div style="display:flex;align-items:center;gap:12px;">
          <img src="${logoSrc}" alt="RideHub" style="height:42px;width:auto;object-fit:contain;" />
          <span style="font-family:var(--font-display, Outfit, sans-serif);font-weight:800;font-size:1.5rem;color:#15803d;">RideHub</span>
        </div>
        <div class="rh-nav-road-track">
          <div class="rh-nav-moto">
            <svg viewBox="0 0 110 64" width="72" height="46">
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
          </div>
        </div>
        <span style="font-size:13px;font-weight:600;color:#64748b;">${labelText || 'Đang tải nội dung...'}</span>
      `;
      document.body.appendChild(el);
      return el;
    };

    const hasIndexLoader = Boolean(document.getElementById('pageLoader'));
    const fromTransition = sessionStorage.getItem('ridehub_page_transition') === '1';
    if (fromTransition) {
      sessionStorage.removeItem('ridehub_page_transition');
      if (!hasIndexLoader) {
        const arrivalEl = createLoaderEl('Đang tải nội dung...');
        setTimeout(() => {
          arrivalEl.classList.add('is-revealing');
          setTimeout(() => arrivalEl.classList.add('is-done'), 740);
        }, 420);
      }
    }

    document.addEventListener('click', (e) => {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const anchor = e.target.closest('a[href]');
      if (!anchor) return;
      if (anchor.hasAttribute('download') || (anchor.target && anchor.target !== '_self')) return;
      const rawHref = anchor.getAttribute('href') || '';
      if (!rawHref || rawHref.startsWith('#') || rawHref.startsWith('javascript:') || rawHref.startsWith('mailto:') || rawHref.startsWith('tel:')) return;

      let targetUrl;
      try {
        targetUrl = new URL(anchor.href, window.location.href);
      } catch (_) {
        return;
      }
      if (targetUrl.origin !== window.location.origin) return;
      if (targetUrl.pathname === window.location.pathname && targetUrl.search === window.location.search && targetUrl.hash) return;

      e.preventDefault();
      sessionStorage.setItem('ridehub_page_transition', '1');
      createLoaderEl('Đang chuyển hướng trang...');
      setTimeout(() => {
        window.location.href = targetUrl.href;
      }, 280);
    });

    window.addEventListener('pageshow', (evt) => {
      if (evt.persisted) {
        document.getElementById('rhNavPageLoader')?.remove();
      }
    });
  };

  const initGlobalChatWidget = () => {
    const currentPage = AuthRBAC.getCurrentPageName();
    if (currentPage === 'auth.html' || currentPage === 'chat.html' || window.location.pathname.includes('auth.html')) {
      return;
    }
    const inPagesDir = window.location.pathname.includes('/pages/');
    const pfx = inPagesDir ? '../' : '';
    if (!document.querySelector('link[href*="chat-widget.css"]')) {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = `${pfx}css/components/chat-widget.css`;
      document.head.appendChild(link);
    }
    if (!document.querySelector('script[src*="chat-widget.js"]')) {
      const script = document.createElement('script');
      script.src = `${pfx}js/components/chat-widget.js`;
      script.defer = true;
      document.body.appendChild(script);
    }
  };

  const initGlobalGeoMap = () => {
    const currentPage = AuthRBAC.getCurrentPageName();
    if (currentPage === 'auth.html' || window.location.pathname.includes('auth.html')) {
      return;
    }
    const inPagesDir = window.location.pathname.includes('/pages/');
    const pfx = inPagesDir ? '../' : '';
    if (!document.querySelector('script[src*="geo-map.js"]')) {
      const script = document.createElement('script');
      script.src = `${pfx}js/components/geo-map.js`;
      script.defer = true;
      document.body.appendChild(script);
    }
  };

  global.AuthRBAC = AuthRBAC;
  document.addEventListener('DOMContentLoaded', () => {
    AuthRBAC.applyUI();
    initPageTransitionLoader();
    initGlobalChatWidget();
    initGlobalGeoMap();
  });
})(window);
