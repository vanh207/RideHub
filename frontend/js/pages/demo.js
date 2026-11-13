document.addEventListener('DOMContentLoaded', () => {
      const output = document.getElementById('apiOutput');
      const log = (title, data) => {
        const time = new Date().toLocaleTimeString();
        output.textContent = `[${time}] ${title}\n` + JSON.stringify(data, null, 2);
      };

      // 1. Quản lý nút chuyển vai trò trong trang Demo
      const updateRoleButtons = (role) => {
        document.querySelectorAll('#demoRoleBtns .role-btn').forEach(btn => {
          btn.classList.toggle('active', btn.dataset.role === role);
        });

        const descs = {
          guest: 'Đang xem với vai trò: Khách vãng lai. Menu hiển thị: Trang chủ, Tìm & Thuê xe, Hướng dẫn, Cổng đối tác và nút Đăng nhập / Đăng ký.',
          customer: 'Đang xem với vai trò: Khách thuê. Menu hiển thị: Trang chủ, Tìm & Thuê xe, Chuyến đi, Đơn đặt xe, Hướng dẫn, Avatar và Thông báo cá nhân.',
          store_owner: 'Đang xem với vai trò: Chủ cửa hàng. Menu hiển thị: Cổng Cửa hàng, Quản lý xe, Duyệt đơn thuê, Doanh thu, Kho xe RideHub.',
          admin: 'Đang xem với vai trò: Quản trị hệ thống. Quyền truy cập toàn bộ hệ thống vận hành, cổng đối tác, cấu hình RBAC.'
        };
        document.getElementById('currentRoleDesc').innerHTML = descs[role] || '';
      };

      // Đặt mặc định vai trò hiện tại
      updateRoleButtons(RideHubLayout.currentRole);

      document.querySelectorAll('#demoRoleBtns .role-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          const role = btn.dataset.role;
          RideHubLayout.setRole(role);
          updateRoleButtons(role);
        });
      });

      // Lắng nghe sự kiện đổi role từ select box trên Header
      window.addEventListener('ridehub:role-changed', (e) => {
        updateRoleButtons(e.detail.role);
      });

      // 2. Kiểm thử các hàm gọi API dùng chung
      document.getElementById('btnApiVehicles')?.addEventListener('click', async () => {
        output.textContent = 'Đang gọi API RideHubAPI.vehicles.getAll()...';
        const res = await RideHubAPI.vehicles.getAll({ type: 'all' });
        log('GET /api/v1/vehicles — Danh sách xe khả dụng', res);
      });

      document.getElementById('btnApiLogin')?.addEventListener('click', async () => {
        output.textContent = 'Đang gọi API RideHubAPI.auth.login()...';
        const res = await RideHubAPI.auth.login('an.nguyen@ridehub.vn', '123456');
        log('POST /api/v1/auth/login — Đăng nhập tài khoản khách', res);
        RideHubLayout.init();
        updateRoleButtons(RideHubLayout.currentRole);
      });

      document.getElementById('btnApiBooking')?.addEventListener('click', async () => {
        output.textContent = 'Đang gọi API RideHubAPI.bookings.create()...';
        const res = await RideHubAPI.bookings.create({
          vehicleId: 'vh-1',
          vehicleName: 'VinFast Klara S (2024)',
          days: 3,
          dailyPrice: 160000,
          totalPrice: 480000,
          depositPrice: 144000,
          deliveryAddress: '120 Lê Lợi, Q.1, TP.HCM'
        });
        log('POST /api/v1/bookings — Tạo đơn thuê mới', res);
      });

      document.getElementById('btnApiNotifs')?.addEventListener('click', () => {
        const notifs = RideHubAPI.notifications.getByRole(RideHubLayout.currentRole);
        log(`GET /api/v1/notifications (${RideHubLayout.currentRole})`, notifs);
      });

      document.getElementById('btnApiFavorites')?.addEventListener('click', () => {
        const favs = RideHubAPI.vehicles.getFavorites();
        log('GET Favorites — Danh sách xe yêu thích từ LocalStorage', favs);
      });

      document.getElementById('btnClearLog')?.addEventListener('click', () => {
        output.textContent = '// Nhật ký đã được xóa.';
      });
    });