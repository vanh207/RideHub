/* ==========================================================================
   RIDEHUB — LAYOUT CHUNG & MENU THEO VAI TRÒ (LAYOUT.JS)
   Module dựng và quản lý Layout dùng chung cho toàn bộ website:
   - Header thông minh (Logo, Navbar, Role Menu, Quick Switcher, Avatar, Notif)
   - Menu điều hướng phân quyền theo 5 vai trò SRS v2.2 + Khách vãng lai
   - Tự động phát hiện và xử lý đường dẫn tương đối (root path ../../)
   - Drawer di động (Mobile Drawer) mượt mà kèm hiệu ứng
   - Tích hợp liền mạch với RideHubAPI và AuthRBAC
   ========================================================================== */

(function (global) {
  'use strict';

  // 1. CẤU HÌNH VAI TRÒ & DANH MỤC MENU (SRS v2.2)
  const ROLE_CONFIG = {
    guest: {
      key: 'guest',
      label: 'Khách vãng lai',
      badgeClass: 'role-tag-guest',
      home: 'index.html',
      menu: [
        { id: 'home', label: 'Trang chủ', href: 'index.html' },
        { id: 'vehicles', label: 'Tìm & Thuê xe', href: 'vehicles.html' },
        { id: 'guide', label: 'Hướng dẫn thuê xe', href: 'index.html#storySection' },
        { id: 'partner', label: 'Dành cho Cửa hàng', href: 'auth.html' }
      ]
    },
    customer: {
      key: 'customer',
      label: 'Khách thuê',
      badgeClass: 'role-tag-customer',
      home: 'vehicles.html',
      menu: [
        { id: 'home', label: 'Trang chủ', href: 'index.html' },
        { id: 'vehicles', label: 'Tìm & Thuê xe', href: 'vehicles.html' },
        { id: 'trips', label: 'Chuyến đi của tôi', href: 'trips.html' },
        { id: 'booking', label: 'Đơn đặt xe', href: 'booking.html' },
        { id: 'guide', label: 'Hướng dẫn', href: 'index.html#storySection' }
      ]
    },
    store_owner: {
      key: 'store_owner',
      label: 'Chủ cửa hàng',
      badgeClass: 'role-tag-store_owner',
      home: 'store-portal.html',
      menu: [
        { id: 'portal', label: 'Tổng quan bãi xe', href: 'store-portal.html' },
        { id: 'vehicles', label: 'Quản lý xe', href: 'store-portal.html#tabVehicles' },
        { id: 'orders', label: 'Duyệt đơn thuê', href: 'store-portal.html#tabOrders' },
        { id: 'revenue', label: 'Doanh thu & Báo cáo', href: 'store-portal.html#tabRevenue' },
        { id: 'fleet', label: 'Kho xe RideHub', href: 'vehicles.html' }
      ]
    },
    admin: {
      key: 'admin',
      label: 'Quản trị hệ thống',
      badgeClass: 'role-tag-admin',
      home: 'admin-ops.html',
      menu: [
        { id: 'admin', label: 'Vận hành & Admin', href: 'admin-ops.html' },
        { id: 'portal', label: 'Cổng Cửa hàng', href: 'store-portal.html' },
        { id: 'vehicles', label: 'Tìm & Thuê xe', href: 'vehicles.html' },
        { id: 'trips', label: 'Chuyến đi', href: 'trips.html' },
        { id: 'profile', label: 'Hồ sơ', href: 'profile.html' }
      ]
    }
  };

  // Icon SVG dùng trong layout
  const ICONS = {
    bell: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>',
    chevronDown: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>',
    user: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="8" r="4"/><path d="M4 20c1.5-3.8 4.8-5.5 8-5.5s6.5 1.7 8 5.5"/></svg>',
    trip: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
    key: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="5" y="11" width="14" height="10" rx="3"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>',
    logout: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/></svg>',
    hamburger: '<svg width="22" height="22" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><line x1="4" y1="7" x2="20" y2="7"></line><line x1="4" y1="12" x2="20" y2="12"></line><line x1="4" y1="17" x2="20" y2="17"></line></svg>',
    phone: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/></svg>',
    mail: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>',
    mapPin: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>',
    arrowUp: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="19" x2="12" y2="5"></line><polyline points="5 12 12 5 19 12"></polyline></svg>',
    globe: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>',
    message: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>',
    share: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>'
  };

  class RideHubLayoutManager {
    constructor() {
      this.currentRole = 'guest';
      this.currentUser = null;
      this.rootPrefix = this._computeRootPrefix();
      this.activeNavId = '';
      this._notifFilter = 'all';
    }

    // Tự tính tiền tố thư mục gốc (./ hoặc ../../) dựa vào độ sâu URL
    _computeRootPrefix() {
      const path = window.location.pathname.replace(/\\/g, '/');
      const parts = path.split('/').filter(Boolean);
      const fileName = parts[parts.length - 1] || '';
      const isSubDir = parts.includes('pages');
      if (isSubDir) {
        const pagesIndex = parts.indexOf('pages');
        const depth = parts.length - 1 - pagesIndex;
        return '../'.repeat(depth);
      }
      return './';
    }

    _resolvePath(relPath) {
      if (!relPath) return '#';
      if (relPath.startsWith('http') || relPath.startsWith('//') || relPath.startsWith('#')) return relPath;
      return this.rootPrefix + relPath.replace(/^\//, '');
    }

    _getCurrentPage() {
      const parts = window.location.pathname.split('/');
      return parts.pop() || 'index.html';
    }

    // Lấy thông tin user hiện tại (đồng bộ cả RideHubAPI và localStorage)
    _syncUser() {
      let user = null;
      if (global.RideHubAPI && typeof global.RideHubAPI.auth?.getCurrentUser === 'function') {
        user = global.RideHubAPI.auth.getCurrentUser();
      }
      if (!user) {
        try {
          const raw = localStorage.getItem('ridehub_current_user');
          if (raw) user = JSON.parse(raw);
        } catch (_) {}
      }
      this.currentUser = user;
      this.currentRole = user ? (user.role || 'customer') : 'guest';
      return user;
    }

    /* ------------------------------------------------------------------------
       KHỞI TẠO VÀ RENDER LAYOUT
       ------------------------------------------------------------------------ */
    init(options = {}) {
      this.options = options;
      if (options.rootPrefix) this.rootPrefix = options.rootPrefix;
      if (options.activeNavId) this.activeNavId = options.activeNavId;

      this._syncUser();
      this._renderNavbar(options.mountId || 'mainNavbar');
      this._renderDrawer();
      if (options.renderFooter !== false) {
        this._renderFooter(options.footerMountId || 'mainFooter');
      }
      this._ensureToastContainer();
      this._bindEvents();

      console.log(`[RideHubLayout] Đã khởi tạo giao diện cho vai trò: ${this.currentRole.toUpperCase()}`);
    }

    // Đổi vai trò tức thì (cho demo & testing)
    setRole(role) {
      if (!ROLE_CONFIG[role]) return;
      if (role === 'guest') {
        if (global.RideHubAPI) global.RideHubAPI.auth.logout();
        else localStorage.removeItem('ridehub_current_user');
      } else {
        if (global.RideHubAPI) {
          global.RideHubAPI.auth.loginAsRole(role);
        } else if (global.AuthRBAC) {
          global.AuthRBAC.loginAsRole(role);
        } else {
          const mockUser = {
            name: role === 'customer' ? 'Nguyễn Văn An' : role === 'store_owner' ? 'Chủ xe GreenRide' : 'Admin Hệ thống',
            role: role,
            email: `${role}@ridehub.vn`
          };
          localStorage.setItem('ridehub_current_user', JSON.stringify(mockUser));
        }
      }

      this._syncUser();
      this._renderNavbar(this.options?.mountId || 'mainNavbar');
      this._renderDrawer();

      // Phát event để trang hiện tại lắng nghe phản ứng
      window.dispatchEvent(new CustomEvent('ridehub:role-changed', { detail: { role, user: this.currentUser } }));
    }

    /* ------------------------------------------------------------------------
       RENDER SMART NAVBAR
       ------------------------------------------------------------------------ */
    _renderNavbar(mountId) {
      let nav = document.getElementById(mountId);
      if (!nav) {
        // Tự tạo nếu chưa có
        nav = document.createElement('header');
        nav.id = mountId;
        nav.className = 'navbar is-scrolled';
        document.body.prepend(nav);
      }

      const roleInfo = ROLE_CONFIG[this.currentRole] || ROLE_CONFIG.guest;
      const user = this.currentUser;
      const currentPage = this._getCurrentPage();

      // Tạo HTML menu links theo vai trò
      const linksHtml = roleInfo.menu.map(item => {
        const fullHref = this._resolvePath(item.href);
        const isActive = this.activeNavId === item.id || currentPage === item.href.split('#')[0];
        return `<a href="${fullHref}" class="nav-link ${isActive ? 'is-active' : ''}" data-nav-id="${item.id}">${item.label}</a>`;
      }).join('');

      // Avatar & user actions
      let userActionHtml = '';
      if (user) {
        const initials = (user.name || 'U').trim().split(/\s+/).slice(-1)[0].slice(0, 1).toUpperCase();
        userActionHtml = `
          <!-- Notification Bell -->
          <div class="notif-wrap" id="rhNotifWrap">
            <button id="rhNotifBtn" class="notif-bell-btn" type="button" aria-label="Thông báo" aria-expanded="false">
              ${ICONS.bell}
              <span id="rhNotifBadge" class="notif-badge" hidden>0</span>
            </button>
            <div id="rhNotifDropdown" class="notif-dropdown">
              <div class="notif-header">
                <div class="notif-header-title">
                  <span>Thông báo</span>
                  <span class="notif-role-pill ${roleInfo.badgeClass}">${roleInfo.label}</span>
                </div>
                <button id="rhNotifReadAll" class="notif-readall-btn" type="button">Đọc tất cả</button>
              </div>
              <div class="notif-tabs">
                <button type="button" class="notif-tab is-active" data-filter="all">Tất cả</button>
                <button type="button" class="notif-tab" data-filter="unread">Chưa đọc</button>
              </div>
              <div id="rhNotifList" class="notif-list"></div>
            </div>
          </div>

          <!-- User Avatar Dropdown -->
          <div class="user-menu-wrap" id="rhUserWrap">
            <button id="rhAvatarBtn" class="user-avatar-trigger" type="button" aria-expanded="false">
              <span class="user-avatar-circle">${initials}</span>
              <span>${user.name}</span>
              ${ICONS.chevronDown}
            </button>
            <div id="rhAvatarDropdown" class="user-avatar-dropdown">
              <div class="user-menu-header">
                <div class="user-menu-name">${user.name}</div>
                <div class="user-menu-sub">${user.email || user.phone} • <strong>${roleInfo.label}</strong></div>
              </div>
              <a href="${this._resolvePath('profile.html')}" class="user-menu-item">
                ${ICONS.user}
                <span>Hồ sơ cá nhân</span>
              </a>
              ${(this.currentRole === 'customer' || this.currentRole === 'admin') ? `
              <a href="${this._resolvePath('trips.html')}" class="user-menu-item">
                ${ICONS.trip}
                <span>Chuyến đi của tôi</span>
              </a>` : ''}
              <a href="${this._resolvePath('profile.html#change-password')}" class="user-menu-item">
                ${ICONS.key}
                <span>Đổi mật khẩu</span>
              </a>
              <button id="rhLogoutBtn" class="user-menu-item user-menu-item--danger" type="button">
                ${ICONS.logout}
                <span>Đăng xuất</span>
              </button>
            </div>
          </div>
        `;
      } else {
        userActionHtml = `
          <a href="${this._resolvePath('auth.html')}" class="btn btn-soft btn-sm">Đăng nhập</a>
          <a href="${this._resolvePath('pages/xac-thuc/dang-ky-khach.html')}" class="btn btn-primary btn-sm">Đăng ký</a>
        `;
      }

      // Quick Role Switcher để thử nghiệm nhanh giữa 4 vai trò
      const roleSwitcherHtml = `
        <div class="role-quick-switcher" title="Chuyển đổi giao diện nhanh giữa các vai trò">
          <span>Vai trò:</span>
          <select id="rhRoleSelect">
            <option value="guest" ${this.currentRole === 'guest' ? 'selected' : ''}>Khách vãng lai</option>
            <option value="customer" ${this.currentRole === 'customer' ? 'selected' : ''}>Khách thuê (Customer)</option>
            <option value="store_owner" ${this.currentRole === 'store_owner' ? 'selected' : ''}>Chủ cửa hàng (Store Owner)</option>
            <option value="admin" ${this.currentRole === 'admin' ? 'selected' : ''}>Quản trị (Admin)</option>
          </select>
        </div>
      `;

      nav.innerHTML = `
        <div class="container navbar-inner">
          <a href="${this._resolvePath(roleInfo.home)}" class="brand-logo">
            <img src="${this._resolvePath('assets/logo-rh.png')}" alt="RideHub Logo" onerror="this.style.display='none'" />
            <span>RideHub</span>
          </a>

          <nav class="nav-links" aria-label="Điều hướng theo vai trò">
            ${linksHtml}
          </nav>

          <div class="nav-actions">
            ${roleSwitcherHtml}
            ${userActionHtml}
            <button id="rhHamburgerBtn" class="hamburger-btn" aria-label="Mở menu" type="button">
              ${ICONS.hamburger}
            </button>
          </div>
        </div>
      `;

      if (user) {
        this._renderNotifItems(this.currentRole, this._notifFilter);
      }
    }

    /* ------------------------------------------------------------------------
       RENDER MOBILE DRAWER
       ------------------------------------------------------------------------ */
    _renderDrawer() {
      let drawer = document.getElementById('rhMobileDrawer');
      let backdrop = document.getElementById('rhDrawerBackdrop');

      if (!drawer) {
        drawer = document.createElement('aside');
        drawer.id = 'rhMobileDrawer';
        drawer.className = 'mobile-drawer';
        document.body.appendChild(drawer);
      }

      if (!backdrop) {
        backdrop = document.createElement('div');
        backdrop.id = 'rhDrawerBackdrop';
        backdrop.className = 'drawer-backdrop';
        document.body.appendChild(backdrop);
      }

      const roleInfo = ROLE_CONFIG[this.currentRole] || ROLE_CONFIG.guest;
      const user = this.currentUser;

      const linksHtml = roleInfo.menu.map(item => {
        const fullHref = this._resolvePath(item.href);
        return `<a href="${fullHref}">${item.label}</a>`;
      }).join('');

      drawer.innerHTML = `
        <div class="mobile-drawer-header">
          <div style="font-size:15px;font-weight:800;color:var(--text-primary);">${user ? user.name : 'Khách vãng lai'}</div>
          <div style="font-size:12px;color:var(--text-muted);">${roleInfo.label}</div>
        </div>
        ${linksHtml}
        <div style="margin-top:auto;padding-top:16px;border-top:1px solid var(--green-100);">
          ${user ? `
            <a href="${this._resolvePath('profile.html')}" style="background:transparent;">Hồ sơ cá nhân</a>
            <button id="rhDrawerLogoutBtn" class="btn btn-outline btn-sm" style="width:100%;margin-top:10px;" type="button">Đăng xuất</button>
          ` : `
            <a href="${this._resolvePath('auth.html')}" class="btn btn-primary btn-sm" style="width:100%;">Đăng nhập</a>
          `}
        </div>
      `;
    }

    /* ------------------------------------------------------------------------
       RENDER THÔNG BÁO THEO VAI TRÒ
       ------------------------------------------------------------------------ */
    _renderNotifItems(role, filter = 'all') {
      const listEl = document.getElementById('rhNotifList');
      const badgeEl = document.getElementById('rhNotifBadge');
      if (!listEl) return;

      let items = [];
      if (global.RideHubAPI) {
        items = global.RideHubAPI.notifications.getByRole(role);
      }
      if (!items.length) {
        // Mock thông báo mặc định nếu chưa có trong DB
        items = [
          { id: '1', title: 'Chào mừng bạn đến với RideHub', body: 'Trải nghiệm thuê xe xanh phản hồi 60fps.', time: 'Vừa xong', read: false },
          { id: '2', title: 'Cập nhật bảo mật', body: 'Hãy hoàn thiện thông tin giấy tờ GPLX và CCCD.', time: '1 giờ trước', read: true }
        ];
      }

      const unreadCount = items.filter(n => !n.read).length;
      if (badgeEl) {
        if (unreadCount > 0) {
          badgeEl.textContent = unreadCount > 9 ? '9+' : unreadCount;
          badgeEl.hidden = false;
        } else {
          badgeEl.hidden = true;
        }
      }

      const filtered = filter === 'unread' ? items.filter(n => !n.read) : items;
      if (!filtered.length) {
        listEl.innerHTML = `<div class="notif-empty">${filter === 'unread' ? 'Không có thông báo chưa đọc.' : 'Chưa có thông báo.'}</div>`;
        return;
      }

      listEl.innerHTML = filtered.map(n => `
        <div class="notif-item ${n.read ? '' : 'is-unread'}" data-notif-id="${n.id}">
          <div class="notif-icon">${ICONS.bell}</div>
          <div class="notif-content">
            <div class="notif-title">${n.title}</div>
            <div class="notif-body">${n.body}</div>
            <div class="notif-time">${n.time || 'Hôm nay'}</div>
          </div>
          ${n.read ? '' : '<span class="notif-dot"></span>'}
        </div>
      `).join('');

      // Gắn sự kiện click item để đánh dấu đã đọc
      listEl.querySelectorAll('.notif-item').forEach(el => {
        el.addEventListener('click', () => {
          const id = el.dataset.notifId;
          if (global.RideHubAPI) {
            global.RideHubAPI.notifications.markRead(role, id);
          }
          this._renderNotifItems(role, this._notifFilter);
        });
      });
    }

    /* ------------------------------------------------------------------------
       RENDER SITE FOOTER (THEO TIÊU CHUẨN UI/UX PRO MAX)
       ------------------------------------------------------------------------ */
    _renderFooter(mountId = 'mainFooter') {
      let footer = document.getElementById(mountId);
      if (!footer) {
        footer = document.createElement('footer');
        footer.id = mountId;
        footer.className = 'site-footer';
        footer.setAttribute('role', 'contentinfo');
        document.body.appendChild(footer);
      } else {
        footer.className = 'site-footer';
        footer.setAttribute('role', 'contentinfo');
      }

      footer.innerHTML = `
        <!-- Hiệu ứng đường lăn bánh và xe điện tương tác ở đỉnh Footer -->
        <div class="footer-road-edge" aria-hidden="true">
          <div id="footerCruisingVehicle" class="footer-road-vehicle" title="Bấm còi xe RideHub">
            <svg viewBox="0 0 110 64" width="56" height="24">
              <path d="M22 36 C28 22, 46 20, 60 25 L76 17 L85 20 L75 36 Z" fill="#4ade80"/>
              <g transform="translate(27,45)"><circle r="8" fill="#0d2316"/><circle r="3.5" fill="#dcfce7"/></g>
              <g transform="translate(81,45)"><circle r="8" fill="#0d2316"/><circle r="3.5" fill="#dcfce7"/></g>
            </svg>
          </div>
        </div>

        <div class="container footer-main-grid">
          <!-- Cột 1: Thông tin thương hiệu, cam kết an toàn & mạng xã hội -->
          <div class="footer-col">
            <a href="${this._resolvePath('index.html')}" class="footer-brand-logo">
              <img src="${this._resolvePath('assets/logo-rh.png')}" alt="RideHub" style="height:32px;width:auto;" onerror="this.style.display='none'" />
              <span>RideHub</span>
            </a>
            <p class="footer-brand-desc">
              Nền tảng thuê xe thông minh &amp; di chuyển xanh 60fps. Đặt xe trong 30 giây, giao nhận tận nơi trong 15 phút, miễn thế chấp qua xác thực eKYC.
            </p>

            <div class="footer-trust-badges">
              <span class="trust-badge-pill">✓ Chuẩn ISO 27001</span>
              <span class="trust-badge-pill">✓ Bộ Công Thương</span>
              <span class="trust-badge-pill">✓ Bảo Hiểm PVI 100%</span>
            </div>

            <div class="footer-social-list" aria-label="Kênh kết nối cộng đồng RideHub">
              <a href="#footerSocial" class="footer-social-btn" aria-label="Trang thông tin cộng đồng">
                ${ICONS.globe}
              </a>
              <a href="#footerChat" class="footer-social-btn" aria-label="Kênh trao đổi trực tuyến">
                ${ICONS.message}
              </a>
              <a href="#footerShare" class="footer-social-btn" aria-label="Chia sẻ ứng dụng">
                ${ICONS.share}
              </a>
            </div>
          </div>

          <!-- Cột 2: Danh mục dịch vụ thuê xe -->
          <nav class="footer-col" aria-label="Dịch vụ thuê xe">
            <h4 class="footer-col-title">Dịch vụ thuê xe</h4>
            <ul class="footer-links">
              <li><a href="${this._resolvePath('vehicles.html?type=moto')}" class="footer-link">Thuê xe máy điện</a></li>
              <li><a href="${this._resolvePath('vehicles.html?type=moto')}" class="footer-link">Xe máy tay ga</a></li>
              <li><a href="${this._resolvePath('vehicles.html?type=car')}" class="footer-link">Thuê ô tô tự lái</a></li>
              <li><a href="${this._resolvePath('vehicles.html')}" class="footer-link">Gói thuê theo tháng</a></li>
              <li><a href="${this._resolvePath('index.html#storySection')}" class="footer-link">Bảng giá minh bạch</a></li>
            </ul>
          </nav>

          <!-- Cột 3: Dành cho đối tác -->
          <nav class="footer-col" aria-label="Dành cho đối tác">
            <h4 class="footer-col-title">Dành cho Đối tác</h4>
            <ul class="footer-links">
              <li><a href="${this._resolvePath('pages/xac-thuc/dang-ky-cua-hang.html')}" class="footer-link">Đăng ký Cửa hàng</a></li>
              <li><a href="${this._resolvePath('store-portal.html')}" class="footer-link">Cổng Cửa hàng (Portal)</a></li>
              <li><a href="${this._resolvePath('admin-ops.html')}" class="footer-link">Cổng Vận hành &amp; Admin</a></li>
              <li><a href="${this._resolvePath('index.html#storySection')}" class="footer-link">Quy chuẩn bàn giao xe</a></li>
              <li><a href="${this._resolvePath('auth.html')}" class="footer-link">Chính sách hợp tác</a></li>
            </ul>
          </nav>

          <!-- Cột 4: Hỗ trợ & Chính sách -->
          <nav class="footer-col" aria-label="Hỗ trợ và chính sách">
            <h4 class="footer-col-title">Hỗ trợ &amp; Pháp lý</h4>
            <ul class="footer-links">
              <li><a href="${this._resolvePath('index.html#storySection')}" class="footer-link">Hỏi đáp thường gặp (FAQ)</a></li>
              <li><a href="${this._resolvePath('pages/khach/xac-thuc-giay-to.html')}" class="footer-link">Thẩm định eKYC &amp; GPLX</a></li>
              <li><a href="${this._resolvePath('index.html#storySection')}" class="footer-link">Chính sách hủy &amp; cọc</a></li>
              <li><a href="${this._resolvePath('profile.html')}" class="footer-link">Quy chế hoạt động</a></li>
              <li><a href="${this._resolvePath('profile.html')}" class="footer-link">Chính sách bảo mật</a></li>
            </ul>
          </nav>

          <!-- Cột 5: Liên hệ 24/7 & Hộp thư nhận ưu đãi -->
          <div class="footer-col">
            <h4 class="footer-col-title">Liên hệ 24/7</h4>
            <div class="footer-contact-item">
              ${ICONS.phone}
              <div>Hotline CSKH: <strong>1900 6868</strong> (24/7)</div>
            </div>
            <div class="footer-contact-item">
              ${ICONS.mail}
              <div>Hộp thư hỗ trợ: <strong>support@ridehub.vn</strong></div>
            </div>
            <div class="footer-contact-item">
              ${ICONS.mapPin}
              <div>Trụ sở: 120 Nguyễn Huệ, Quận 1, TP.HCM</div>
            </div>

            <!-- Form đăng ký ưu đãi -->
            <div class="footer-newsletter-box">
              <div class="footer-newsletter-title">Nhận ưu đãi chuyến đi đầu</div>
              <div class="footer-newsletter-desc">Đăng ký để nhận voucher giảm 20% và ưu đãi xe mới.</div>
              <form class="footer-newsletter-form" id="rhNewsletterForm">
                <input type="email" class="footer-newsletter-input" placeholder="Nhập email của bạn..." required aria-label="Email nhận voucher" />
                <button type="submit" class="footer-newsletter-btn">Gửi</button>
              </form>
            </div>
          </div>
        </div>

        <!-- Thanh bản quyền chân trang -->
        <div class="footer-bottom-bar">
          <div class="container footer-bottom-inner">
            <div>
              © 2026 <strong>RideHub Technology JSC</strong>. Toàn bộ bản quyền được bảo hộ.
            </div>

            <div class="footer-legal-links">
              <span class="footer-status-pill">
                <span class="status-dot-pulse"></span>
                <span>Hệ thống trực tuyến 99.98%</span>
              </span>
              <a href="#privacy">Quyền riêng tư</a>
              <a href="#terms">Điều khoản sử dụng</a>
              <a href="#sitemap">Sitemap</a>
            </div>

            <button type="button" class="back-to-top-btn" id="rhBackToTopBtn" aria-label="Cuộn lên đầu trang">
              ${ICONS.arrowUp}
              <span>Lên đầu trang</span>
            </button>
          </div>
        </div>
      `;

      // Gắn sự kiện xe bấm còi
      document.getElementById('footerCruisingVehicle')?.addEventListener('click', () => {
        if (typeof global.showRideHubToast === 'function') {
          global.showRideHubToast('🚗 Bíp bíp! Xe RideHub đã sẵn sàng cho chuyến đi xanh của bạn!', 'success');
        }
      });

      // Gắn sự kiện cuộn lên đầu trang
      document.getElementById('rhBackToTopBtn')?.addEventListener('click', () => {
        window.scrollTo({ top: 0, behavior: 'smooth' });
      });

      // Gắn sự kiện đăng ký nhận tin
      document.getElementById('rhNewsletterForm')?.addEventListener('submit', (e) => {
        e.preventDefault();
        const input = e.target.querySelector('input');
        if (input && input.value) {
          if (typeof global.showRideHubToast === 'function') {
            global.showRideHubToast(`🎉 Cảm ơn bạn! Voucher 20% đã gửi tới: ${input.value}`, 'success');
          }
          input.value = '';
        }
      });
    }

    _ensureToastContainer() {
      if (!document.getElementById('toastContainer')) {
        const toast = document.createElement('div');
        toast.id = 'toastContainer';
        toast.className = 'toast-container';
        document.body.appendChild(toast);
      }

      // Đảm bảo hàm showRideHubToast luôn hoạt động
      if (typeof global.showRideHubToast !== 'function') {
        global.showRideHubToast = function (message, type = 'info') {
          const container = document.getElementById('toastContainer');
          if (!container) return;
          const t = document.createElement('div');
          t.className = `toast toast-${type}`;
          t.textContent = message;
          container.appendChild(t);
          setTimeout(() => {
            t.style.opacity = '0';
            t.style.transform = 'translateY(10px)';
            setTimeout(() => t.remove(), 300);
          }, 3200);
        };
      }
    }

    /* ------------------------------------------------------------------------
       GẮN SỰ KIỆN TƯƠNG TÁC (DROPDOWNS, OUTSIDE CLICK, HAMBURGER)
       ------------------------------------------------------------------------ */
    _bindEvents() {
      // 1. Role switcher dropdown
      const roleSelect = document.getElementById('rhRoleSelect');
      if (roleSelect) {
        roleSelect.addEventListener('change', (e) => {
          this.setRole(e.target.value);
        });
      }

      // 2. Avatar dropdown toggle
      const avatarBtn = document.getElementById('rhAvatarBtn');
      const avatarDrop = document.getElementById('rhAvatarDropdown');
      const notifBtn = document.getElementById('rhNotifBtn');
      const notifDrop = document.getElementById('rhNotifDropdown');

      avatarBtn?.addEventListener('click', (e) => {
        e.stopPropagation();
        notifDrop?.classList.remove('is-open');
        notifBtn?.setAttribute('aria-expanded', 'false');
        const open = avatarDrop.classList.toggle('is-open');
        avatarBtn.setAttribute('aria-expanded', String(open));
      });

      // 3. Notif dropdown toggle
      notifBtn?.addEventListener('click', (e) => {
        e.stopPropagation();
        avatarDrop?.classList.remove('is-open');
        avatarBtn?.setAttribute('aria-expanded', 'false');
        const open = notifDrop.classList.toggle('is-open');
        notifBtn.setAttribute('aria-expanded', String(open));
      });

      // 4. Outside click
      document.addEventListener('click', (e) => {
        if (avatarDrop && !avatarDrop.contains(e.target) && !avatarBtn?.contains(e.target)) {
          avatarDrop.classList.remove('is-open');
          avatarBtn?.setAttribute('aria-expanded', 'false');
        }
        if (notifDrop && !notifDrop.contains(e.target) && !notifBtn?.contains(e.target)) {
          notifDrop.classList.remove('is-open');
          notifBtn?.setAttribute('aria-expanded', 'false');
        }
      });

      // 5. Notif Tabs (Tất cả / Chưa đọc)
      document.querySelectorAll('#rhNotifDropdown .notif-tab').forEach(tab => {
        tab.addEventListener('click', (e) => {
          e.stopPropagation();
          document.querySelectorAll('#rhNotifDropdown .notif-tab').forEach(t => t.classList.remove('is-active'));
          tab.classList.add('is-active');
          this._notifFilter = tab.dataset.filter;
          this._renderNotifItems(this.currentRole, this._notifFilter);
        });
      });

      // 6. Đọc tất cả thông báo
      document.getElementById('rhNotifReadAll')?.addEventListener('click', (e) => {
        e.stopPropagation();
        if (global.RideHubAPI) {
          global.RideHubAPI.notifications.markAllRead(this.currentRole);
        }
        this._renderNotifItems(this.currentRole, this._notifFilter);
      });

      // 7. Đăng xuất
      const handleLogout = () => {
        this.setRole('guest');
        if (typeof global.showRideHubToast === 'function') {
          global.showRideHubToast('Đã đăng xuất tài khoản.');
        }
      };
      document.getElementById('rhLogoutBtn')?.addEventListener('click', handleLogout);
      document.getElementById('rhDrawerLogoutBtn')?.addEventListener('click', handleLogout);

      // 8. Mobile Drawer toggle
      const drawer = document.getElementById('rhMobileDrawer');
      const backdrop = document.getElementById('rhDrawerBackdrop');
      const hamburger = document.getElementById('rhHamburgerBtn');

      const toggleDrawer = (open) => {
        const isOpen = open !== undefined ? open : !drawer?.classList.contains('is-open');
        drawer?.classList.toggle('is-open', isOpen);
        backdrop?.classList.toggle('is-open', isOpen);
        hamburger?.classList.toggle('is-open', isOpen);
      };

      hamburger?.addEventListener('click', () => toggleDrawer());
      backdrop?.addEventListener('click', () => toggleDrawer(false));
    }
  }

  // Khởi tạo Singleton
  const layoutManager = new RideHubLayoutManager();
  global.RideHubLayout = layoutManager;

  // Tự động nạp khi trang tải xong nếu có #mainNavbar, #ridehubHeader hoặc #mainFooter
  document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('mainNavbar') || document.getElementById('ridehubHeader') || document.getElementById('mainFooter')) {
      layoutManager.init({
        mountId: document.getElementById('mainNavbar') ? 'mainNavbar' : 'ridehubHeader',
        footerMountId: 'mainFooter'
      });
    }
  });

})(typeof window !== 'undefined' ? window : this);

