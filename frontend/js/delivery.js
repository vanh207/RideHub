/* ==========================================================================
   LOGIC XỬ LÝ ĐIỂM GIAO NHẬN & TÍNH PHÍ (DELIVERY.JS)
   ========================================================================== */

(function () {
  'use strict';

  // Lấy các phần tử DOM
  const btnSelf = document.getElementById('btnSelfPickup');
  const btnDel = document.getElementById('btnDelivery');
  const noteSelf = document.getElementById('pickupAddressNote');
  const wrapDel = document.getElementById('deliveryAddressWrap');
  const inputDel = document.getElementById('deliveryAddressInput');
  const chkNight = document.getElementById('chkNightDelivery');

  const cfgBaseFee = document.getElementById('cfgBaseFee');
  const cfgNightFee = document.getElementById('cfgNightFee');
  const cfgDefaultHub = document.getElementById('cfgDefaultHub');

  const dispMode = document.getElementById('dispMode');
  const dispAddress = document.getElementById('dispAddress');
  const dispTotalFee = document.getElementById('dispTotalFee');
  const storeViewDelivery = document.getElementById('storeViewDelivery');
  const storeViewFee = document.getElementById('storeViewFee');

  // Hàm tính toán và cập nhật chi phí giao nhận lên giao diện
  function updateCalculation() {
    const isDelivery = btnDel.classList.contains('btn-primary');
    const baseFeeVal = Number(cfgBaseFee.value) || 0;
    const nightFeeVal = Number(cfgNightFee.value) || 0;

    const deliveryFee = isDelivery ? baseFeeVal : 0;
    const nightFee = chkNight.checked ? nightFeeVal : 0;
    const total = deliveryFee + nightFee;

    // 1. Cập nhật góc nhìn khách thuê
    dispMode.textContent = isDelivery ? 'Giao xe tận nơi' : 'Tôi tự đến lấy xe';
    const currentAddr = isDelivery ? (inputDel.value.trim() || 'Chưa nhập địa chỉ') : cfgDefaultHub.value.trim();
    dispAddress.textContent = currentAddr;
    dispTotalFee.textContent = total.toLocaleString('vi-VN') + 'đ';

    // 2. Cập nhật mô phỏng sang góc nhìn cửa hàng đối soát
    storeViewDelivery.textContent = isDelivery ? `Giao xe tận nơi • ${currentAddr}` : `Nhận tại cửa hàng • ${currentAddr}`;
    storeViewFee.textContent = total === 0 ? '0đ (Khách nhận tại bãi)' : `${total.toLocaleString('vi-VN')}đ (Đã cộng vào tổng đơn)`;
  }

  // Sự kiện khi bấm "Tôi tự đến lấy xe"
  btnSelf.addEventListener('click', () => {
    btnSelf.className = 'btn btn-primary';
    btnDel.className = 'btn btn-soft';
    noteSelf.hidden = false;
    wrapDel.hidden = true;
    updateCalculation();
  });

  // Sự kiện khi bấm "Giao xe tận nơi"
  btnDel.addEventListener('click', () => {
    btnDel.className = 'btn btn-primary';
    btnSelf.className = 'btn btn-soft';
    noteSelf.hidden = true;
    wrapDel.hidden = false;
    updateCalculation();
  });

  // Sự kiện khi thay đổi các ô nhập liệu
  inputDel.addEventListener('input', updateCalculation);
  chkNight.addEventListener('change', updateCalculation);
  cfgBaseFee.addEventListener('input', updateCalculation);
  cfgNightFee.addEventListener('input', updateCalculation);
  cfgDefaultHub.addEventListener('input', () => {
    noteSelf.textContent = `📍 Bãi xe nhận miễn phí: ${cfgDefaultHub.value}`;
    updateCalculation();
  });

  // Hàm lưu cấu hình tham số
  window.handleSaveConfig = function () {
    alert('✅ Đã lưu cấu hình tham số biểu phí thành công vào hệ thống!');
  };

  // Khởi chạy tính toán ngay khi tải trang
  updateCalculation();
})();