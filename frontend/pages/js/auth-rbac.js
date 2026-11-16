/* ==========================================================================
   RideHub Authentication & Role-Based Access Control (auth-rbac.js)
   3 Roles: customer (Khách thuê), store_owner (Chủ cửa hàng), admin (Quản trị hệ thống)
   ========================================================================== */

(function (global) {
  'use strict';

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
    customer: {
      label: 'Khách thuê',
      badgeClass: 'status-badge--available',
      home: 'vehicles.html',
      allowedPages: ['index.html', 'vehicles.html', 'booking.html', 'trips.html', 'profile.html', 'auth.html', 'chat.html']
    },
    store_owner: {
      label: 'Chủ cửa hàng',
      badgeClass: 'status-badge--transit',
      home: 'store-portal.html',
      allowedPages: ['index.html', 'store-portal.html', 'profile.html', 'auth.html', 'chat.html']
    },
    admin: {
      label: 'Quản trị hệ thống',
      badgeClass: 'status-badge--maintenance',
      home: 'admin-ops.html',
      allowedPages: ['index.html', 'admin-ops.html', 'profile.html', 'auth.html', 'chat.html']
    }
  };

  const DEFAULT_ACCOUNTS = [
    { phone: '0901234567', email: 'an.nguyen@ridehub.vn', pass: '123456', name: 'Nguyễn Văn An', role: 'customer' },
    { phone: '0902222222', email: 'greenride@ridehub.vn', pass: '123456', name: 'Chủ xe GreenRide Q1', role: 'store_owner' },
    { phone: '0909999999', email: 'admin@ridehub.vn', pass: '123456', name: 'Admin Hệ thống', role: 'admin' }
  ];

  const AuthRBAC = {
    getAccounts() {
      let list = null;
      try {
        const raw = localStorage.getItem(STORAGE_ACCOUNTS);
        if (raw) list = JSON.parse(raw);
      } catch (_) {}
      if (!Array.isArray(list)) {
        localStorage.setItem(STORAGE_ACCOUNTS, JSON.stringify(DEFAULT_ACCOUNTS));
        return [...DEFAULT_ACCOUNTS];
      }
      // Filter out deleted roles (store_staff, operator)
      list = list.filter((a) => a.role !== 'store_staff' && a.role !== 'operator');
      // Ensure default role accounts always have up-to-date email & phone
      let changed = false;
      DEFAULT_ACCOUNTS.forEach((def) => {
        const idx = list.findIndex((a) => a.phone === def.phone || a.role === def.role);
        if (idx === -1) {
          list.push(def);
          changed = true;
        } else if (!list[idx].email) {
          list[idx] = { ...def, ...list[idx], email: def.email };
          changed = true;
        }
      });
      if (changed) localStorage.setItem(STORAGE_ACCOUNTS, JSON.stringify(list));
      return list;
    },

    saveAccounts(list) {
      localStorage.setItem(STORAGE_ACCOUNTS, JSON.stringify(list));
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
      localStorage.removeItem(STORAGE_USER);
      this.applyUI();
      if (global.showRideHubToast) global.showRideHubToast('Đã đăng xuất tài khoản.');
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

    getNotifications(role) {
      const map = this._loadNotifMap();
      return Array.isArray(map[role]) ? map[role] : [];
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
      const map = this._loadNotifMap();
      const list = map[role];
      if (!Array.isArray(list)) return;
      const item = list.find((n) => n.id === id);
      if (item && !item.read) {
        item.read = true;
        localStorage.setItem(STORAGE_NOTIFS, JSON.stringify(map));
      }
    },

    markAllNotificationsRead(role) {
      const map = this._loadNotifMap();
      const list = map[role];
      if (!Array.isArray(list)) return;
      list.forEach((n) => { n.read = true; });
      localStorage.setItem(STORAGE_NOTIFS, JSON.stringify(map));
      this._renderNotifPanel(role);
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

      listEl.querySelectorAll('.notif-item').forEach((btn) => {
        btn.addEventListener('click', () => {
          const id = btn.dataset.notifId;
          const link = btn.dataset.notifLink;
          this.markNotificationRead(role, id);
          this._renderNotifPanel(role, this._notifFilter);
          if (link && link !== this.getCurrentPageName()) {
            window.location.href = link;
          } else {
            document.getElementById('rbacNotifDropdown')?.classList.remove('is-open');
            document.getElementById('rbacNotifBtn')?.setAttribute('aria-expanded', 'false');
          }
        });
      });
    },

    applyUI() {
      const user = this.getCurrentUser();
      const roleInfo = user ? ROLES[user.role] : null;
      const currentPage = this.getCurrentPageName();

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
                  <div style="font-size:13px;font-weight:800;color:var(--text-primary);">${user.name}</div>
                  <div style="font-size:11px;color:var(--text-muted);">${user.email || user.phone} • ${roleInfo.label}</div>
                </div>
                <a href="profile.html" class="user-menu-item" role="menuitem">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="8" r="4"/><path d="M4 20c1.5-3.8 4.8-5.5 8-5.5s6.5 1.7 8 5.5"/></svg>
                  <span>Hồ sơ</span>
                </a>
                <a href="chat.html" class="user-menu-item" role="menuitem">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>
                  <span>Tin nhắn &amp; Hỗ trợ</span>
                </a>
                ${user.role === 'customer' || user.role === 'admin' ? `
                <a href="trips.html" class="user-menu-item" role="menuitem">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>
                  <span>Chuyến đi</span>
                </a>` : ''}
                <a href="profile.html#change-password" class="user-menu-item" role="menuitem">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="5" y="11" width="14" height="10" rx="3"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>
                  <span>Đổi mật khẩu</span>
                </a>
                <div style="padding:6px 12px 4px;font-size:10px;font-weight:800;color:var(--text-muted);text-transform:uppercase;border-top:1px solid var(--green-100);margin-top:4px;">Chuyển nhanh vai trò (Demo)</div>
                <div style="display:flex;flex-direction:column;gap:2px;padding:2px 6px 6px;">
                  <button type="button" data-nav-switch-role="store_owner" class="user-menu-item" style="font-size:12px;padding:5px 8px;border-radius:6px;${user.role==='store_owner'?'background:var(--green-100);font-weight:700;color:var(--green-800);':''}">🏪 Chủ cửa hàng (GreenRide Q1)</button>
                  <button type="button" data-nav-switch-role="customer" class="user-menu-item" style="font-size:12px;padding:5px 8px;border-radius:6px;${user.role==='customer'?'background:var(--green-100);font-weight:700;color:var(--green-800);':''}">👤 Khách thuê (Nguyễn Văn An)</button>
                  <button type="button" data-nav-switch-role="admin" class="user-menu-item" style="font-size:12px;padding:5px 8px;border-radius:6px;${user.role==='admin'?'background:var(--green-100);font-weight:700;color:var(--green-800);':''}">👑 Admin hệ thống</button>
                </div>
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

          dropdown?.querySelectorAll('[data-nav-switch-role]').forEach((btn) => {
            btn.addEventListener('click', (e) => {
              e.stopPropagation();
              const targetRole = btn.dataset.navSwitchRole;
              this.loginAsRole(targetRole);
              const targetHome = ROLES[targetRole]?.home || 'index.html';
              if (currentPage === 'store-portal.html' && (targetRole === 'store_owner' || targetRole === 'admin')) {
                window.location.reload();
              } else if (currentPage === 'admin-ops.html' && targetRole === 'admin') {
                window.location.reload();
              } else {
                window.location.href = targetHome;
              }
            });
          });

          document.getElementById('rbacLogoutBtn')?.addEventListener('click', () => {
            this.logout();
            if (currentPage !== 'index.html' && currentPage !== 'auth.html') {
              window.location.href = 'auth.html';
            }
          });
        } else {
          userPill.innerHTML = `<a href="auth.html" class="btn btn-soft" style="min-height:38px;padding:6px 14px;font-size:13px;">Đăng nhập</a>`;
        }
      }

      // 2. Filter Navbar & Mobile Drawer links based on role
      const allowed = roleInfo ? roleInfo.allowedPages : ['index.html', 'vehicles.html', 'booking.html', 'auth.html'];
      document.querySelectorAll('.nav-links a, .mobile-drawer a').forEach((link) => {
        const href = link.getAttribute('href');
        if (!href || href.startsWith('#')) return;
        const page = href.split('#')[0];
        const ok = allowed.includes(page);
        link.style.display = ok ? '' : 'none';
      });

      // 3. Enforce Page Guard (403 Forbidden if unauthorized)
      const existingGuard = document.getElementById('rbacGuardOverlay');
      if (existingGuard) existingGuard.remove();

      if (!allowed.includes(currentPage)) {
        const guard = document.createElement('div');
        guard.id = 'rbacGuardOverlay';
        guard.style.cssText = 'position:fixed;inset:0;z-index:180;background:rgba(248,252,249,0.96);backdrop-filter:blur(10px);display:flex;align-items:center;justify-content:center;padding:24px;';

        let quickActionHtml = '';
        if (currentPage === 'store-portal.html') {
          quickActionHtml = `
            <div style="margin:16px 0;padding:12px;border-radius:12px;background:#f0fdf4;border:1px solid #86efac;text-align:left;">
              <div style="font-size:12px;font-weight:800;color:#166534;margin-bottom:8px;">ĐĂNG NHẬP NHANH VÀO CỬA HÀNG (1-CLICK):</div>
              <div style="display:flex;flex-direction:column;gap:6px;">
                <button type="button" id="guardQuickStoreOwnerBtn" class="btn btn-primary btn-premium" style="justify-content:center;padding:10px 14px;font-size:13px;width:100%;">
                  🏪 Đăng nhập vai trò Chủ cửa hàng (GreenRide Q1)
                </button>
              </div>
              <div style="font-size:11px;color:#15803d;margin-top:6px;text-align:center;">Email: <strong>greenride@ridehub.vn</strong> • Mật khẩu: <strong>123456</strong></div>
            </div>
          `;
        } else if (currentPage === 'admin-ops.html') {
          quickActionHtml = `
            <div style="margin:16px 0;padding:12px;border-radius:12px;background:#f0fdf4;border:1px solid #86efac;text-align:left;">
              <div style="font-size:12px;font-weight:800;color:#166534;margin-bottom:8px;">ĐĂNG NHẬP NHANH QUẢN TRỊ (1-CLICK):</div>
              <div style="display:flex;flex-direction:column;gap:6px;">
                <button type="button" id="guardQuickAdminBtn" class="btn btn-primary btn-premium" style="justify-content:center;padding:10px 14px;font-size:13px;width:100%;">
                  👑 Đăng nhập Admin hệ thống
                </button>
              </div>
              <div style="font-size:11px;color:#15803d;margin-top:6px;text-align:center;">Email: <strong>admin@ridehub.vn</strong> • Mật khẩu: <strong>123456</strong></div>
            </div>
          `;
        }

        guard.innerHTML = `
          <div class="panel-card" style="max-width:480px;text-align:center;">
            <span class="eyebrow" style="background:#fee2e2;color:#b91c1c;">403 • Phân quyền truy cập</span>
            <h2 style="margin:8px 0;font-family:var(--font-display);">Quyền truy cập bị giới hạn</h2>
            <p style="color:var(--text-secondary);font-size:14px;margin:0 0 12px;">
              ${user ? `Bạn đang đăng nhập với tài khoản: <strong>${user.name} (${roleInfo.label})</strong>.` : 'Trang này yêu cầu quyền truy cập phù hợp.'}
            </p>
            ${quickActionHtml}
            <div style="display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin-top:10px;">
              <a href="auth.html" class="btn btn-soft" style="font-size:12px;">Mở trang đăng nhập (auth.html)</a>
              <a href="${roleInfo ? roleInfo.home : 'index.html'}" class="btn btn-soft" style="font-size:12px;">Về trang chủ</a>
            </div>
          </div>
        `;
        document.body.appendChild(guard);

        document.getElementById('guardQuickStoreOwnerBtn')?.addEventListener('click', () => {
          this.loginAsRole('store_owner');
          window.location.reload();
        });
        document.getElementById('guardQuickAdminBtn')?.addEventListener('click', () => {
          this.loginAsRole('admin');
          window.location.reload();
        });
      }

      // 4. Enforce Tab-Level Restrictions (BR-24 for store_staff, Admin tabs for operator)
      if (roleInfo && roleInfo.restrictedTabs) {
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

  global.AuthRBAC = AuthRBAC;
  document.addEventListener('DOMContentLoaded', () => AuthRBAC.applyUI());
})(window);

