/* ==========================================================================
   RideHub Mock Database & Demo Accounts (js/auth/auth-mock.js)
   ========================================================================== */

export const DEMO_MODE = true;
export const DEMO_OTP = '123456';

const DB_USERS_KEY = 'rh_auth_users_v2';
const DB_LOGS_KEY = 'rh_auth_audit_logs_v2';
const DB_STAFF_KEY = 'rh_store_staff_v2';

// Simple deterministic hash simulation (never store plaintext password in localStorage)
export function hashMock(str) {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return 'rh_h$' + (h >>> 0).toString(16).padStart(8, '0');
}

const DEFAULT_PASS_HASH = hashMock('Ridehub@123');

const SEED_USERS = [
  // Khách thuê
  {
    id: 'cus-1', phone: '0901000001', username: '0901000001', email: 'an.nguyen@gmail.com',
    name: 'Nguyễn Văn An', dob: '1998-04-12', address: '120 Nguyễn Huệ, Q.1, TP.HCM',
    role: 'customer', status: 'active', passHash: DEFAULT_PASS_HASH,
    kycStatus: 'approved', licenseClass: 'B2', licenseExpiry: '2030-08-15',
    cccdNumber: '079098004112', kycReason: ''
  },
  {
    id: 'cus-2', phone: '0901000002', username: '0901000002', email: 'binh.tran@gmail.com',
    name: 'Trần Thanh Bình', dob: '2000-09-20', address: '45 Cầu Giấy, Hà Nội',
    role: 'customer', status: 'active', passHash: DEFAULT_PASS_HASH,
    kycStatus: 'pending', licenseClass: 'A1', licenseExpiry: '2029-05-01',
    cccdNumber: '001200019283', kycReason: ''
  },
  {
    id: 'cus-3', phone: '0901000003', username: '0901000003', email: 'chi.le@gmail.com',
    name: 'Lê Kim Chi', dob: '1999-11-03', address: '18 Hải Châu, Đà Nẵng',
    role: 'customer', status: 'active', passHash: DEFAULT_PASS_HASH,
    kycStatus: 'rejected', licenseClass: 'A1', licenseExpiry: '2028-02-10',
    cccdNumber: '048199002311', kycReason: 'Ảnh giấy phép lái xe bị lóa sáng, không đọc được hạng bằng.'
  },
  {
    id: 'cus-4', phone: '0901000004', username: '0901000004', email: 'dung.pham@gmail.com',
    name: 'Phạm Hoàng Dũng', dob: '1995-02-14', address: '88 Lê Lợi, Q.1, TP.HCM',
    role: 'customer', status: 'active', passHash: DEFAULT_PASS_HASH,
    kycStatus: 'expired', licenseClass: 'B1', licenseExpiry: '2026-10-01',
    cccdNumber: '079095008711', kycReason: 'Giấy phép lái xe đã hết hạn sử dụng.'
  },
  {
    id: 'cus-5', phone: '0901000005', username: '0901000005', email: 'em.vo@gmail.com',
    name: 'Võ Minh Em', dob: '2002-07-22', address: '12 Phan Xích Long, Phú Nhuận',
    role: 'customer', status: 'active', passHash: DEFAULT_PASS_HASH,
    kycStatus: 'not_submitted', licenseClass: '', licenseExpiry: '',
    cccdNumber: '', kycReason: ''
  },

  // Chủ cửa hàng
  {
    id: 'own-1', phone: '0902000001', username: '0902000001', email: 'greenride.q1@ridehub.vn',
    name: 'Lê Hoàng Nam (GreenRide Q1)', storeName: 'GreenRide Quận 1', storeId: 'store-q1',
    role: 'store_owner', status: 'active', passHash: DEFAULT_PASS_HASH,
    storeStatus: 'approved', storeReason: '', taxCode: '0316889900', bankName: 'Vietcombank', bankAcc: '1029384756'
  },
  {
    id: 'own-2', phone: '0902000002', username: '0902000002', email: 'ecodrive.hn@ridehub.vn',
    name: 'Nguyễn Thu Thảo (EcoDrive HN)', storeName: 'EcoDrive Hà Nội', storeId: 'store-hn',
    role: 'store_owner', status: 'active', passHash: DEFAULT_PASS_HASH,
    storeStatus: 'pending', storeReason: '', taxCode: '0108923411', bankName: 'Techcombank', bankAcc: '19033445566'
  },
  {
    id: 'own-3', phone: '0902000003', username: '0902000003', email: 'saigonmoto@ridehub.vn',
    name: 'Đỗ Quốc Tuấn (SaigonMoto)', storeName: 'SaigonMoto Q3', storeId: 'store-q3',
    role: 'store_owner', status: 'active', passHash: DEFAULT_PASS_HASH,
    storeStatus: 'rejected', storeReason: 'Thiếu ảnh mặt sau CCCD người đại diện pháp luật và sai mã số thuế.',
    taxCode: '0310001122', bankName: 'ACB', bankAcc: '8822110044'
  },

  // Nhân viên cửa hàng
  {
    id: 'stf-1', phone: '0903000001', username: 'nv.hanoi01', email: 'nv.hanoi01@ridehub.vn',
    name: 'Hoàng Minh Trí', storeName: 'GreenRide Quận 1', storeId: 'store-q1',
    role: 'store_staff', status: 'active', passHash: DEFAULT_PASS_HASH, mustChangePass: false,
    staffPerms: { manage_vehicles: true, confirm_booking: true, handover_out: true, handover_in: true, view_schedule: true, view_report: true }
  },
  {
    id: 'stf-2', phone: '0903000002', username: 'nv.hanoi02', email: 'nv.hanoi02@ridehub.vn',
    name: 'Bùi Ngọc Ánh', storeName: 'GreenRide Quận 1', storeId: 'store-q1',
    role: 'store_staff', status: 'active', passHash: DEFAULT_PASS_HASH, mustChangePass: true,
    staffPerms: { manage_vehicles: false, confirm_booking: false, handover_out: true, handover_in: true, view_schedule: true, view_report: false }
  },
  {
    id: 'stf-3', phone: '0903000003', username: 'nv.khoa', email: 'nv.khoa@ridehub.vn',
    name: 'Tài Khoản Bị Khóa', storeName: 'GreenRide Quận 1', storeId: 'store-q1',
    role: 'store_staff', status: 'locked', lockReason: 'Vi phạm quy trình bàn giao xe', passHash: DEFAULT_PASS_HASH,
    staffPerms: { manage_vehicles: false, confirm_booking: false, handover_out: false, handover_in: false, view_schedule: false, view_report: false }
  },

  // Vận hành viên & Admin
  {
    id: 'ops-1', phone: '0904000001', username: 'van.hanh@ridehub.vn', email: 'van.hanh@ridehub.vn',
    name: 'Nguyễn Linh (Vận hành viên)', role: 'operator', status: 'active', passHash: DEFAULT_PASS_HASH,
    lastLogin: '12/11/2026 08:45 • Chrome / Windows'
  },
  {
    id: 'adm-1', phone: '0909000001', username: 'admin@ridehub.vn', email: 'admin@ridehub.vn',
    name: 'Trần Quản Trị (Admin)', role: 'admin', status: 'active', passHash: DEFAULT_PASS_HASH,
    lastLogin: '12/11/2026 09:10 • Edge / Windows'
  }
];

const SEED_LOGS = [
  { id: 'log-1', time: '12/11/2026 09:10', actor: 'admin@ridehub.vn', action: 'Đăng nhập 2 lớp thành công', ip: '113.161.72.18', device: 'Edge / Windows 11', status: 'success' },
  { id: 'log-2', time: '12/11/2026 08:52', actor: 'van.hanh@ridehub.vn', action: 'Duyệt Đạt hồ sơ khách 0901000001', ip: '14.169.44.9', device: 'Chrome / Windows 11', status: 'success' },
  { id: 'log-3', time: '12/11/2026 08:30', actor: 'nv.khoa', action: 'Đăng nhập thất bại (Tài khoản bị khóa)', ip: '27.72.99.104', device: 'Safari / iOS', status: 'failed' },
  { id: 'log-4', time: '11/11/2026 17:40', actor: '0902000001', action: 'Khóa tài khoản nhân viên nv.khoa', ip: '171.244.10.5', device: 'Chrome / macOS', status: 'warning' }
];

export function getUsers() {
  try {
    const raw = localStorage.getItem(DB_USERS_KEY);
    if (raw) return JSON.parse(raw);
  } catch (_) {}
  localStorage.setItem(DB_USERS_KEY, JSON.stringify(SEED_USERS));
  return [...SEED_USERS];
}

export function saveUsers(users) {
  localStorage.setItem(DB_USERS_KEY, JSON.stringify(users));
}

export function updateUserById(id, patch) {
  const users = getUsers();
  const idx = users.findIndex((u) => u.id === id);
  if (idx === -1) return null;
  users[idx] = { ...users[idx], ...patch };
  saveUsers(users);
  return users[idx];
}

export function getAuditLogs() {
  try {
    const raw = localStorage.getItem(DB_LOGS_KEY);
    if (raw) return JSON.parse(raw);
  } catch (_) {}
  localStorage.setItem(DB_LOGS_KEY, JSON.stringify(SEED_LOGS));
  return [...SEED_LOGS];
}

export function appendAuditLog(actor, action, status = 'success') {
  const logs = getAuditLogs();
  const now = new Date();
  const time = now.toLocaleDateString('vi-VN') + ' ' + now.toTimeString().slice(0, 5);
  logs.unshift({
    id: 'log-' + Date.now(),
    time,
    actor,
    action,
    ip: '113.161.72.' + Math.floor(10 + Math.random() * 200),
    device: navigator.userAgent.includes('Mobile') ? 'Mobile Browser' : 'Desktop Browser',
    status
  });
  localStorage.setItem(DB_LOGS_KEY, JSON.stringify(logs.slice(0, 80)));
}

export function getDemoGroups() {
  const users = getUsers();
  return [
    { group: 'Khách thuê', items: users.filter((u) => u.role === 'customer') },
    { group: 'Chủ cửa hàng', items: users.filter((u) => u.role === 'store_owner') },
    { group: 'Nhân viên', items: users.filter((u) => u.role === 'store_staff') },
    { group: 'Quản trị & Vận hành', items: users.filter((u) => u.role === 'operator' || u.role === 'admin') }
  ];
}

