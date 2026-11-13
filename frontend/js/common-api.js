/* ==========================================================================
   RIDEHUB — HÀM GỌI API DÙNG CHUNG (COMMON-API.JS)
   Module API Client tập trung cho toàn bộ hệ thống RideHub:
   - Cấu hình Base URL, Headers, Auth Token injection
   - Các phương thức HTTP chuẩn: GET, POST, PUT, PATCH, DELETE
   - Interceptors: Xử lý lỗi toàn cục, 401 Unauthorized, 403 Forbidden, 500
   - Chế độ Mock Fallback thông minh: Tương thích 100% với LocalStorage DB
   - Các domain service: Auth, Vehicles, Bookings, Notifications, Store, Admin
   ========================================================================== */

(function (global) {
  'use strict';

  // Config mặc định
  const DEFAULT_CONFIG = {
    baseUrl: 'https://api.ridehub.vn/v1',
    timeoutMs: 8000,
    mockMode: true, // Mặc định bật Mock fallback để ứng dụng chạy độc lập
    storageUserKey: 'ridehub_current_user',
    storageTokenKey: 'ridehub_auth_token',
    storageAccountsKey: 'ridehub_accounts_db',
    storageNotifsKey: 'ridehub_notifications_v1',
    storageBookingsKey: 'ridehub_bookings_db',
    storageFavoritesKey: 'ridehub_favorite_vehicles'
  };

  // Mock Accounts ban đầu theo chuẩn 5 vai trò SRS v2.2
  const SEED_ACCOUNTS = [
    { id: 'usr-1', phone: '0901234567', email: 'an.nguyen@ridehub.vn', pass: '123456', name: 'Nguyễn Văn An', role: 'customer', kycStatus: 'approved' },
    { id: 'usr-2', phone: '0902222222', email: 'greenride@ridehub.vn', pass: '123456', name: 'Lê Hoàng Nam (GreenRide)', role: 'store_owner', storeName: 'GreenRide Q1' },
    { id: 'usr-3', phone: '0903333333', email: 'khoi.nv@ridehub.vn', pass: '123456', name: 'Trần Minh Khôi (NV)', role: 'store_staff', storeName: 'GreenRide Q1' },
    { id: 'usr-4', phone: '0904444444', email: 'linh.ops@ridehub.vn', pass: '123456', name: 'Vận hành viên Linh', role: 'operator', opsTeam: 'Khu vực Miền Nam' },
    { id: 'usr-5', phone: '0909999999', email: 'admin@ridehub.vn', pass: '123456', name: 'Admin Quản Trị Hệ Thống', role: 'admin' }
  ];

  // Danh mục xe mẫu
  const SEED_VEHICLES = [
    { id: 'vh-1', name: 'VinFast Klara S (2024)', type: 'moto', category: 'Xe máy điện', city: 'TP. Hồ Chí Minh', price: 160000, rating: 4.9, trips: 142, status: 'available', store: 'GreenRide Q1', address: '120 Lê Lợi, Q.1' },
    { id: 'vh-2', name: 'Honda Vision 110cc', type: 'moto', category: 'Xe tay ga', city: 'TP. Hồ Chí Minh', price: 180000, rating: 4.8, trips: 280, status: 'available', store: 'GreenRide Q1', address: '120 Lê Lợi, Q.1' },
    { id: 'vh-3', name: 'Honda Air Blade 160cc', type: 'moto', category: 'Xe tay ga', city: 'TP. Hồ Chí Minh', price: 240000, rating: 4.9, trips: 195, status: 'available', store: 'SaigonMoto Q3', address: '45 Võ Văn Tần, Q.3' },
    { id: 'vh-4', name: 'VinFast VF5 Plus', type: 'car', category: 'SUV Điện đô thị', city: 'TP. Hồ Chí Minh', price: 750000, rating: 4.95, trips: 88, status: 'available', store: 'EcoDrive', address: '88 Nguyễn Hữu Cảnh, Bình Thạnh' },
    { id: 'vh-5', name: 'VinFast VF3', type: 'car', category: 'Mini Electric Car', city: 'Hà Nội', price: 500000, rating: 4.85, trips: 64, status: 'available', store: 'GreenRide HN', address: '12 Cầu Giấy, Hà Nội' },
    { id: 'vh-6', name: 'Mazda 3 Luxury 2023', type: 'car', category: 'Sedan C', city: 'Đà Nẵng', price: 900000, rating: 4.9, trips: 110, status: 'available', store: 'DanangRent', address: '22 Bạch Đằng, Đà Nẵng' }
  ];

  class CommonApiClient {
    constructor(config = {}) {
      this.config = { ...DEFAULT_CONFIG, ...config };
      this._initStorage();
    }

    _initStorage() {
      try {
        if (!localStorage.getItem(this.config.storageAccountsKey)) {
          localStorage.setItem(this.config.storageAccountsKey, JSON.stringify(SEED_ACCOUNTS));
        }
        if (!localStorage.getItem(this.config.storageBookingsKey)) {
          localStorage.setItem(this.config.storageBookingsKey, JSON.stringify([]));
        }
      } catch (e) {
        console.warn('[RideHubAPI] LocalStorage not available:', e);
      }
    }

    // Cấu hình linh hoạt thời điểm runtime
    configure(newConfig) {
      this.config = { ...this.config, ...newConfig };
      return this;
    }

    // Token Auth
    getToken() {
      try {
        return localStorage.getItem(this.config.storageTokenKey) || '';
      } catch (_) {
        return '';
      }
    }

    setToken(token) {
      try {
        if (token) localStorage.setItem(this.config.storageTokenKey, token);
        else localStorage.removeItem(this.config.storageTokenKey);
      } catch (_) {}
    }

    clearToken() {
      this.setToken('');
    }

    // Thông báo toast thống nhất
    notify(message, type = 'info') {
      if (typeof global.showRideHubToast === 'function') {
        global.showRideHubToast(message);
      } else {
        console.log(`[RideHubAPI ${type.toUpperCase()}]: ${message}`);
      }
    }

    /* ------------------------------------------------------------------------
       CORE HTTP REQUEST WRAPPER
       ------------------------------------------------------------------------ */
    async request(endpoint, options = {}) {
      const {
        method = 'GET',
        headers = {},
        body = null,
        params = null,
        timeout = this.config.timeoutMs,
        useMock = this.config.mockMode,
        skipAuth = false
      } = options;

      // Xây dựng URL & query params
      let url = endpoint.startsWith('http') ? endpoint : `${this.config.baseUrl.replace(/\/$/, '')}/${endpoint.replace(/^\//, '')}`;
      if (params && Object.keys(params).length > 0) {
        const query = new URLSearchParams();
        Object.entries(params).forEach(([k, v]) => {
          if (v !== undefined && v !== null && v !== '') query.append(k, v);
        });
        const qStr = query.toString();
        if (qStr) url += (url.includes('?') ? '&' : '?') + qStr;
      }

      // Xây dựng headers
      const reqHeaders = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        ...headers
      };

      if (!skipAuth) {
        const token = this.getToken();
        if (token) reqHeaders['Authorization'] = `Bearer ${token}`;
      }

      // Tạo controller hỗ trợ timeout
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeout);

      // Nếu không bật chế độ mock, gửi request HTTP thực tế
      if (!useMock) {
        try {
          const response = await fetch(url, {
            method,
            headers: reqHeaders,
            body: body ? JSON.stringify(body) : undefined,
            signal: controller.signal
          });
          clearTimeout(timer);

          // Xử lý status code đặc thù
          if (response.status === 401) {
            this.notify('Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại.', 'error');
            this.auth.logout();
            return { ok: false, status: 401, message: 'Unauthorized' };
          }

          if (response.status === 403) {
            this.notify('Bạn không có quyền truy cập tài nguyên này (403 Forbidden).', 'error');
            return { ok: false, status: 403, message: 'Forbidden' };
          }

          const data = await response.json().catch(() => ({}));
          if (!response.ok) {
            return { ok: false, status: response.status, message: data.message || `Lỗi máy chủ (${response.status})`, data };
          }

          return { ok: true, status: response.status, data };
        } catch (error) {
          clearTimeout(timer);
          if (error.name === 'AbortError') {
            this.notify('Yêu cầu hết thời gian chờ (Timeout).', 'error');
            return { ok: false, status: 408, message: 'Request Timeout' };
          }
          console.warn('[RideHubAPI] Fetch thất bại, chuyển sang Mock fallback:', error.message);
          // Rơi xuống mock router
        }
      } else {
        clearTimeout(timer);
      }

      // Giả lập trễ mạng tự nhiên 120ms
      await new Promise(r => setTimeout(r, 120));
      return this._mockRouter(method, endpoint, body, params);
    }

    // Các hàm helper tiện dụng
    get(endpoint, params = null, options = {}) {
      return this.request(endpoint, { ...options, method: 'GET', params });
    }

    post(endpoint, body = null, options = {}) {
      return this.request(endpoint, { ...options, method: 'POST', body });
    }

    put(endpoint, body = null, options = {}) {
      return this.request(endpoint, { ...options, method: 'PUT', body });
    }

    patch(endpoint, body = null, options = {}) {
      return this.request(endpoint, { ...options, method: 'PATCH', body });
    }

    delete(endpoint, options = {}) {
      return this.request(endpoint, { ...options, method: 'DELETE' });
    }

    /* ------------------------------------------------------------------------
       MOCK ROUTER & LOCAL STORAGE FALLBACK
       ------------------------------------------------------------------------ */
    _mockRouter(method, endpoint, body, params) {
      const ep = endpoint.replace(/^\//, '');

      // 1. Auth mock endpoints
      if (ep === 'auth/login' && method === 'POST') {
        const { identifier, password } = body || {};
        const key = (identifier || '').trim().toLowerCase();
        const accounts = this._getAccounts();
        const user = accounts.find(a => ((a.email && a.email.toLowerCase() === key) || a.phone === key) && a.pass === password);
        if (!user) {
          return { ok: false, status: 400, message: 'Sai email/số điện thoại hoặc mật khẩu!' };
        }
        const token = 'mock_jwt_token_' + btoa(user.phone + ':' + Date.now());
        this.setToken(token);
        this._setCurrentUser(user);
        return { ok: true, status: 200, data: { user, token } };
      }

      if (ep === 'auth/register' && method === 'POST') {
        const { name, phone, email, password, role } = body || {};
        const accounts = this._getAccounts();
        const mail = (email || '').trim().toLowerCase();
        if (mail && accounts.some(a => a.email && a.email.toLowerCase() === mail)) {
          return { ok: false, status: 400, message: 'Email đã được sử dụng!' };
        }
        if (accounts.some(a => a.phone === phone?.trim())) {
          return { ok: false, status: 400, message: 'Số điện thoại đã được sử dụng!' };
        }
        const newUser = {
          id: 'usr_' + Date.now(),
          name: name?.trim() || 'Người dùng mới',
          phone: phone?.trim(),
          email: mail,
          pass: password,
          role: role || 'customer',
          kycStatus: 'pending'
        };
        accounts.push(newUser);
        localStorage.setItem(this.config.storageAccountsKey, JSON.stringify(accounts));
        this._setCurrentUser(newUser);
        return { ok: true, status: 201, data: { user: newUser } };
      }

      // 2. Vehicles mock endpoints
      if (ep.startsWith('vehicles') && method === 'GET') {
        let list = [...SEED_VEHICLES];
        if (params?.type && params.type !== 'all') {
          list = list.filter(v => v.type === params.type);
        }
        if (params?.city && params.city !== 'all') {
          list = list.filter(v => v.city === params.city);
        }
        if (params?.search) {
          const q = params.search.toLowerCase();
          list = list.filter(v => v.name.toLowerCase().includes(q) || v.category.toLowerCase().includes(q));
        }
        return { ok: true, status: 200, data: { vehicles: list, total: list.length } };
      }

      // 3. Bookings mock endpoints
      if (ep === 'bookings' && method === 'POST') {
        const bookings = this._getBookings();
        const user = this._getCurrentUser() || { name: 'Khách', phone: '0901234567' };
        const newBooking = {
          id: 'RH-' + Math.floor(1000 + Math.random() * 9000),
          createdAt: new Date().toISOString(),
          customerName: user.name,
          customerPhone: user.phone,
          status: 'pending_deposit',
          ...body
        };
        bookings.unshift(newBooking);
        localStorage.setItem(this.config.storageBookingsKey, JSON.stringify(bookings));
        return { ok: true, status: 201, data: newBooking };
      }

      if (ep === 'bookings' && method === 'GET') {
        const bookings = this._getBookings();
        return { ok: true, status: 200, data: bookings };
      }

      // Fallback mặc định
      return { ok: true, status: 200, data: { message: 'Mock response OK', endpoint, method } };
    }

    _getAccounts() {
      try {
        const raw = localStorage.getItem(this.config.storageAccountsKey);
        return raw ? JSON.parse(raw) : [...SEED_ACCOUNTS];
      } catch (_) {
        return [...SEED_ACCOUNTS];
      }
    }

    _getCurrentUser() {
      try {
        const raw = localStorage.getItem(this.config.storageUserKey);
        return raw ? JSON.parse(raw) : null;
      } catch (_) {
        return null;
      }
    }

    _setCurrentUser(user) {
      try {
        if (user) localStorage.setItem(this.config.storageUserKey, JSON.stringify(user));
        else localStorage.removeItem(this.config.storageUserKey);
      } catch (_) {}
    }

    _getBookings() {
      try {
        const raw = localStorage.getItem(this.config.storageBookingsKey);
        return raw ? JSON.parse(raw) : [];
      } catch (_) {
        return [];
      }
    }

    /* ------------------------------------------------------------------------
       DOMAIN SERVICES
       ------------------------------------------------------------------------ */

    // 1. DỊCH VỤ XÁC THỰC & TÀI KHOẢN (AUTH)
    get auth() {
      const self = this;
      return {
        async login(identifier, password) {
          const res = await self.post('auth/login', { identifier, password });
          if (res.ok && res.data?.user) {
            self._setCurrentUser(res.data.user);
            self.notify(`Chào mừng ${res.data.user.name}!`, 'success');
          }
          return res;
        },

        async loginAsRole(role) {
          const accounts = self._getAccounts();
          const acc = accounts.find(a => a.role === role);
          if (!acc) return { ok: false, message: `Không tìm thấy tài khoản vai trò ${role}` };
          self._setCurrentUser(acc);
          self.notify(`Đã chuyển sang vai trò: ${acc.name} (${role})`, 'success');
          return { ok: true, user: acc };
        },

        async register(userData) {
          const res = await self.post('auth/register', userData);
          if (res.ok) self.notify('Đăng ký tài khoản thành công!', 'success');
          return res;
        },

        getCurrentUser() {
          return self._getCurrentUser();
        },

        logout() {
          self.clearToken();
          self._setCurrentUser(null);
          self.notify('Đã đăng xuất tài khoản.', 'info');
        },

        async updateProfile(patch) {
          const cur = self._getCurrentUser();
          if (!cur) return { ok: false, message: 'Bạn chưa đăng nhập!' };
          const updated = { ...cur, ...patch };
          const accounts = self._getAccounts();
          const idx = accounts.findIndex(a => a.phone === cur.phone || a.id === cur.id);
          if (idx !== -1) {
            accounts[idx] = updated;
            localStorage.setItem(self.config.storageAccountsKey, JSON.stringify(accounts));
          }
          self._setCurrentUser(updated);
          self.notify('Cập nhật hồ sơ thành công!', 'success');
          return { ok: true, user: updated };
        },

        async changePassword(oldPass, newPass) {
          const cur = self._getCurrentUser();
          if (!cur) return { ok: false, message: 'Bạn chưa đăng nhập!' };
          if (cur.pass !== oldPass) return { ok: false, message: 'Mật khẩu cũ không chính xác!' };
          return this.updateProfile({ pass: newPass });
        }
      };
    }

    // 2. DỊCH VỤ PHƯƠNG TIỆN (VEHICLES)
    get vehicles() {
      const self = this;
      return {
        async getAll(filters = {}) {
          return self.get('vehicles', filters);
        },

        async getById(id) {
          const res = await self.get(`vehicles/${id}`);
          if (res.ok) return res;
          // Fallback mock
          const found = SEED_VEHICLES.find(v => v.id === id);
          return found ? { ok: true, data: found } : { ok: false, message: 'Không tìm thấy xe!' };
        },

        getFavorites() {
          try {
            const raw = localStorage.getItem(self.config.storageFavoritesKey);
            return raw ? JSON.parse(raw) : [];
          } catch (_) {
            return [];
          }
        },

        toggleFavorite(vehicle) {
          let list = this.getFavorites();
          const exists = list.some(v => v.id === vehicle.id || v.name === vehicle.name);
          if (exists) {
            list = list.filter(v => v.id !== vehicle.id && v.name !== vehicle.name);
            self.notify(`Đã bỏ lưu ${vehicle.name}`, 'info');
          } else {
            list.push(vehicle);
            self.notify(`Đã thêm ${vehicle.name} vào danh sách yêu thích!`, 'success');
          }
          localStorage.setItem(self.config.storageFavoritesKey, JSON.stringify(list));
          return list;
        }
      };
    }

    // 3. DỊCH VỤ ĐƠN THUÊ (BOOKINGS)
    get bookings() {
      const self = this;
      return {
        async create(bookingData) {
          return self.post('bookings', bookingData);
        },

        async getMyBookings() {
          return self.get('bookings');
        },

        async cancel(bookingId, reason = '') {
          const bookings = self._getBookings();
          const target = bookings.find(b => b.id === bookingId);
          if (target) {
            target.status = 'cancelled';
            target.cancelReason = reason;
            localStorage.setItem(self.config.storageBookingsKey, JSON.stringify(bookings));
            self.notify(`Đơn #${bookingId} đã được hủy thành công.`, 'info');
            return { ok: true, data: target };
          }
          return { ok: false, message: 'Không tìm thấy mã đơn!' };
        }
      };
    }

    // 4. DỊCH VỤ THÔNG BÁO (NOTIFICATIONS)
    get notifications() {
      const self = this;
      return {
        _getMap() {
          try {
            const raw = localStorage.getItem(self.config.storageNotifsKey);
            return raw ? JSON.parse(raw) : {};
          } catch (_) {
            return {};
          }
        },

        getByRole(role) {
          const map = this._getMap();
          return Array.isArray(map[role]) ? map[role] : [];
        },

        markRead(role, notifId) {
          const map = this._getMap();
          if (Array.isArray(map[role])) {
            const item = map[role].find(n => n.id === notifId);
            if (item) {
              item.read = true;
              localStorage.setItem(self.config.storageNotifsKey, JSON.stringify(map));
            }
          }
        },

        markAllRead(role) {
          const map = this._getMap();
          if (Array.isArray(map[role])) {
            map[role].forEach(n => { n.read = true; });
            localStorage.setItem(self.config.storageNotifsKey, JSON.stringify(map));
          }
        }
      };
    }
  }

  // Export Singleton instance & Class
  const instance = new CommonApiClient();
  global.RideHubAPI = instance;
  global.RideHubApiClient = CommonApiClient;

})(typeof window !== 'undefined' ? window : this);

