/* RideHub booking and deposit demo flow */
(function () {
      let draft = {
        orderCode: 'RH-482910',
        vehicle: 'VinFast Feliz S (2025)',
        specs: 'Số tự động • Điện • 2 chỗ',
        schedule: '12/11 21:00 → 15/11 11:00',
        deliveryMode: 'Tôi tự đến lấy xe',
        deliveryAddress: '45 Lý Tự Trọng, Quận 1, TP.HCM',
        deliveryFee: 0,
        addons: [],
        breakdown: '160.000đ × 2 ngày',
        totalNum: 320000,
        depositNum: 96000,
        remainNum: 224000,
        totalText: '320.000đ'
      };
      try {
        const raw = localStorage.getItem('ridehub_checkout_draft');
        if (raw) draft = { ...draft, ...JSON.parse(raw) };
      } catch (_) {}

      document.getElementById('checkoutVehicleHeading').textContent = `Bước 1: Tạo đơn #${draft.orderCode} — ${draft.vehicle}`;
      document.getElementById('checkoutScheduleSub').textContent = 'Thời gian thuê: ' + draft.schedule;
      document.getElementById('sumVehicleSpecs').textContent = draft.specs || 'Số tự động';
      document.getElementById('sumDeliveryMode').textContent = draft.deliveryMode || 'Tôi tự đến lấy xe';
      document.getElementById('sumDeliveryAddr').textContent = draft.deliveryAddress || 'Tại cửa hàng';
      document.getElementById('sumAddons').textContent = (draft.addons && draft.addons.length) ? draft.addons.join(', ') : 'Không chọn';
      document.getElementById('sumBreakdown').textContent = draft.breakdown || draft.totalText;
      document.getElementById('sumDeliveryFee').textContent = (draft.deliveryFee || 0).toLocaleString('vi-VN') + 'đ';
      document.getElementById('sumTotalFee').textContent = (draft.totalNum || 320000).toLocaleString('vi-VN') + 'đ';
      document.getElementById('sumDepositFee').textContent = (draft.depositNum || 96000).toLocaleString('vi-VN') + 'đ';
      document.getElementById('sumRemainFee').textContent = (draft.remainNum || 224000).toLocaleString('vi-VN') + 'đ';
      document.getElementById('qrOrderTitle').textContent =
        `QR Thanh toán cọc đơn #${draft.orderCode} (${(draft.depositNum || 96000).toLocaleString('vi-VN')}đ)`;

      const panels = [0, 1, 2, 3].map((i) => document.getElementById('stepPanel' + i));
      const qrPanel = document.getElementById('qrPaymentPanel');
      const qrWaiting = document.getElementById('qrWaitingNotice');

      const goStep = (idx) => {
        panels.forEach((p, i) => { if (p) p.hidden = i !== idx; });
        // Chỉ hiển thị QR thanh toán khi tiến trình nhảy đến Bước 3 (idx === 2)
        if (qrPanel && qrWaiting) {
          qrPanel.hidden = idx !== 2;
          qrWaiting.hidden = idx === 2;
        }
        if (window.VehicleAnim && typeof window.VehicleAnim.setStepperStep === 'function') {
          window.VehicleAnim.setStepperStep(idx);
        }
      };

      document.addEventListener('DOMContentLoaded', () => goStep(0));

      document.getElementById('goStep2Btn')?.addEventListener('click', () => {
        goStep(1);
        showRideHubToast('Đã tạo đơn giữ chỗ! Đang chờ cửa hàng duyệt.');
      });

      document.getElementById('goStep3Btn')?.addEventListener('click', () => {
        goStep(2);
        showRideHubToast(`Cửa hàng đã duyệt đơn #${draft.orderCode}! Vui lòng quét QR đặt cọc.`);
        if (window.AuthRBAC?.pushNotification) {
          window.AuthRBAC.pushNotification({
            role: 'customer',
            type: 'payment',
            title: `Đơn #${draft.orderCode} đã được cửa hàng duyệt`,
            body: `Cửa hàng đã duyệt xe ${draft.vehicle}. Vui lòng quét VietQR để đặt cọc 30%.`,
            link: 'booking.html'
          });
        }
      });

      const finishOrderOnSystem = () => {
        const orderId = draft.orderCode || ('RH-' + Math.floor(100000 + Math.random() * 899999));
        const listRaw = localStorage.getItem('ridehub_trips_list');
        const list = listRaw ? JSON.parse(listRaw) : [];
        list.unshift({
          id: orderId,
          vehicle: draft.vehicle,
          specs: draft.specs,
          schedule: draft.schedule,
          deliveryMode: draft.deliveryMode,
          address: draft.deliveryAddress,
          addons: draft.addons || [],
          totalNum: draft.totalNum || 320000,
          depositNum: draft.depositNum || 96000,
          phase: 'upcoming',
          remainingSec: 1 * 86400 + 2 * 3600 + 15 * 60
        });
        localStorage.setItem('ridehub_trips_list', JSON.stringify(list));
        if (window.AuthRBAC?.pushNotification) {
          window.AuthRBAC.pushNotification({
            role: 'customer',
            type: 'booking',
            title: `Tạo đơn thuê #${orderId} thành công`,
            body: `Xe ${draft.vehicle} đã được giữ chỗ. Theo dõi đếm ngược nhận xe tại Chuyến đi.`,
            link: 'trips.html'
          });
          window.AuthRBAC.pushNotification({
            roles: ['store_owner', 'store_staff'],
            type: 'payment',
            title: `Đơn thuê mới #${orderId} đã cọc 30%`,
            body: `Khách đã thanh toán cọc cho xe ${draft.vehicle} (${draft.schedule || 'Lịch thuê mới'}).`,
            link: 'store-portal.html'
          });
        }
        document.getElementById('finalOrderInfo').textContent =
          `Mã đơn #${orderId} (${draft.vehicle}) đã được tạo thành công trên hệ thống và đồng bộ vào mục Chuyến đi.`;
        goStep(3);
        if (window.VehicleAnim) {
          window.VehicleAnim.launchConfetti(document.getElementById('bookingSuccessConfetti'));
        }
        showRideHubToast(`Tạo đơn thuê #${orderId} thành công!`);
      };

      document.getElementById('goStep4Btn')?.addEventListener('click', finishOrderOnSystem);
      document.getElementById('simulateQrPayBtn')?.addEventListener('click', () => {
        setTimeout(finishOrderOnSystem, 550);
      });
      document.getElementById('confirmRefundDemoButton')?.addEventListener('click', () => {
        showRideHubToast('Đã tạo yêu cầu hoàn tiền #RF-882 cho Ban quản trị Admin!');
      });
    })();
