/* ==========================================================================
   RideHub Role & Permission Matrix (js/auth/permissions.js)
   Roles: guest, customer, store_staff, store_owner, operator, admin
   ========================================================================== */

export const ROLE_LABELS = {
  guest: 'Khách vãng lai',
  customer: 'Khách thuê',
  store_staff: 'Nhân viên cửa hàng',
  store_owner: 'Chủ cửa hàng',
  operator: 'Vận hành viên',
  admin: 'Quản trị hệ thống'
};

export const PERMISSIONS = {
  guest: ['view_vehicles', 'use_chatbot_faq'],
  customer: ['view_vehicles', 'use_chatbot_faq', 'use_chatbot_order', 'book_vehicle', 'manage_profile', 'upload_kyc', 'view_own_bookings'],
  store_staff: ['view_vehicles', 'use_chatbot_faq', 'handover_vehicle', 'view_store_schedule'],
  store_owner: ['view_vehicles', 'use_chatbot_faq', 'manage_store', 'manage_vehicles', 'manage_staff', 'handover_vehicle', 'view_store_schedule', 'view_store_reports'],
  operator: ['view_vehicles', 'use_chatbot_faq', 'review_kyc', 'review_store', 'handle_refunds', 'handle_disputes', 'view_audit_logs'],
  admin: ['*']
};

export function can(action, user) {
  const role = user?.role || 'guest';
  const list = PERMISSIONS[role] || PERMISSIONS.guest;
  if (list.includes('*')) return true;

  // Store staff granular overrides per BR-24
  if (role === 'store_staff' && user?.staffPerms) {
    if (action === 'manage_vehicles') return !!user.staffPerms.manage_vehicles;
    if (action === 'confirm_booking') return !!user.staffPerms.confirm_booking;
    if (action === 'handover_vehicle') return !!(user.staffPerms.handover_out || user.staffPerms.handover_in);
    if (action === 'view_store_reports') return !!user.staffPerms.view_report;
  }

  return list.includes(action);
}

export function getRoleHome(user) {
  if (!user) return '../../index.html';
  switch (user.role) {
    case 'customer': return '../../vehicles.html';
    case 'store_owner':
      return user.storeStatus === 'approved' ? '../../store-portal.html' : '../xac-thuc/cho-duyet-cua-hang.html';
    case 'store_staff': return '../../store-portal.html';
    case 'operator': return '../quan-tri/duyet-ho-so.html';
    case 'admin': return '../quan-tri/duyet-ho-so.html';
    default: return '../../index.html';
  }
}

