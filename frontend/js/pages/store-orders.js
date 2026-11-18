/**
 * RIDEHUB — LOGIC XỬ LÝ DUYỆT / HỦY ĐƠN HÀNG CỬA HÀNG & ĐỒNG BỘ DỮ LIỆU
 * File: frontend/js/pages/store-orders.js
 */

(function (global) {
  'use strict';

  const STORAGE_KEY = 'ridehub_store_orders_v1';

  const DEFAULT_ORDERS = [
    {
      id: 'RH-8842',
      vehicle: 'VinFast Feliz S',
      category: 'moto',
      categoryLabel: 'Xe máy điện • Tay ga',
      licensePlate: '59A-123.45',
      customer: 'Nguyễn Văn An',
      phone: '0901234567',
      email: 'an.nguyen@ridehub.vn',
      cccd: '079201008899',
      ekycStatus: 'pass',
      schedule: '14/11/2026 08:00 → 16/11/2026 08:00',
      durationDays: 2,
      delivery: 'Giao xe tận nơi • 120 Nguyễn Huệ, Q.1',
      addons: '2 nón bảo hiểm 3/4, Áo mưa đôi RideHub',
      total: 320000,
      deposit: 96000,
      collateral: 'Miễn tiền cọc thế chấp (eKYC Hợp lệ)',
      status: 'pending',
      cancelReason: '',
      note: 'Khách cần nhận xe đúng giờ để đi gặp đối tác.'
    },
    {
      id: 'RH-8845',
      vehicle: 'VinFast VF 5 Plus',
      category: 'car',
      categoryLabel: 'Ô tô điện • SUV 5 chỗ',
      licensePlate: '51K-889.92',
      customer: 'Trần Thanh Bình',
      phone: '0901000002',
      email: 'binh.tran@ridehub.vn',
      cccd: '079202001122',
      ekycStatus: 'pass',
      schedule: '15/11/2026 09:00 → 17/11/2026 18:00',
      durationDays: 2.5,
      delivery: 'Nhận tại cửa hàng • GreenRide Q.1',
      addons: 'Bảo hiểm chuyến đi mở rộng thân vỏ PTI',
      total: 1875000,
      deposit: 562500,
      collateral: '5.000.000đ hoặc Cavet xe máy chính chủ',
      status: 'pending',
      cancelReason: '',
      note: 'Yêu cầu mức pin xe tối thiểu 95% trước khi bàn giao.'
    },
    {
      id: 'RH-8835',
      vehicle: 'Dat Bike Weaver++',
      category: 'moto',
      categoryLabel: 'Xe máy điện • Côn tay thể thao',
      licensePlate: '59B-987.65',
      customer: 'Lê Kim Chi',
      phone: '0901000003',
      email: 'kimchi.le@ridehub.vn',
      cccd: '079199003344',
      ekycStatus: 'pass',
      schedule: '13/11/2026 10:00 → 14/11/2026 10:00',
      durationDays: 1,
      delivery: 'Giao xe tận nơi • 45 Lê Lợi, Q.1',
      addons: 'Giá đỡ điện thoại chống rung MagSafe',
      total: 240000,
      deposit: 72000,
      collateral: '500.000đ tiền mặt (đã giữ cọc)',
      status: 'approved',
      cancelReason: '',
      rescheduleRequest: {
        status: 'pending_store',
        oldSchedule: '13/11/2026 10:00 → 14/11/2026 10:00 (1 ngày)',
        newSchedule: '14/11/2026 10:00 → 16/11/2026 10:00 (2 ngày)',
        durationDiff: '+1 ngày',
        surcharge: 240000,
        reason: 'Khách dời lịch công tác sang ngày 14/11 và xin gia hạn thêm 1 ngày.'
      }
    },
    {
      id: 'RH-8820',
      vehicle: 'VinFast Klara S',
      category: 'moto',
      categoryLabel: 'Xe máy điện • Cốp rộng',
      licensePlate: '59C-456.78',
      customer: 'Hoàng Minh Trí',
      phone: '0901000004',
      email: 'tri.hoang@ridehub.vn',
      cccd: '079198005566',
      ekycStatus: 'pass',
      schedule: '14/11/2026 09:00 → 15/11/2026 09:00',
      durationDays: 1,
      delivery: 'Nhận tại cửa hàng • GreenRide Q.1',
      addons: '2 nón bảo hiểm tiêu chuẩn, Bộ sạc theo xe',
      total: 180000,
      deposit: 54000,
      collateral: 'Miễn thế chấp eKYC',
      status: 'approved',
      cancelReason: ''
    },
    {
      id: 'RH-8812',
      vehicle: 'Mazda 3 Luxury 2023',
      category: 'car',
      categoryLabel: 'Ô tô xăng • Sedan 5 chỗ',
      licensePlate: '51H-998.11',
      customer: 'Phạm Quốc Hùng',
      phone: '0901888999',
      email: 'hung.pham@ridehub.vn',
      cccd: '079195007788',
      ekycStatus: 'pass',
      schedule: '10/11/2026 07:00 → 12/11/2026 19:00',
      durationDays: 2.5,
      delivery: 'Giao xe tận nơi • Sân bay Tân Sơn Nhất',
      addons: 'Ghế ngồi an toàn cho trẻ em',
      total: 2250000,
      deposit: 675000,
      collateral: '5.000.000đ tiền mặt',
      status: 'cancelled',
      cancelReason: 'Xe gặp sự cố kỹ thuật đột xuất cần bảo dưỡng'
    }
  ];

  global.RideHubStoreOrders = {
    getOrders() {
      try {
        const raw = localStorage.getItem(STORAGE_KEY);
        return raw ? JSON.parse(raw) : DEFAULT_ORDERS;
      } catch (_) {
        return DEFAULT_ORDERS;
      }
    },
    saveOrders(orders) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(orders));
    }
  };

})(typeof window !== 'undefined' ? window : this);
