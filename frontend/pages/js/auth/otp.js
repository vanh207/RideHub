/* ==========================================================================
   RideHub 6-Digit OTP Widget Controller (js/auth/otp.js)
   ========================================================================== */

import { DEMO_MODE, DEMO_OTP } from './auth-mock.js';

export function mountOTPWidget(container, { onSuccess, onResend } = {}) {
  if (!container) return null;

  let resendSec = 60;
  let expiresAt = Date.now() + 5 * 60 * 1000;
  let attemptsLeft = 5;
  let lockUntil = 0;
  let timerId = null;

  container.innerHTML = `
    <div class="otp-row otp-row--center" role="group" aria-label="Nhập mã OTP 6 số">
      ${Array.from({ length: 6 }, (_, i) => `<input class="otp-box" maxlength="1" inputmode="numeric" aria-label="Số thứ ${i + 1}" style="--otp-i:${i}" />`).join('')}
    </div>
    <div class="otp-meta-bar">
      <span class="otp-status-txt">Hết hạn sau 05:00</span>
      <button type="button" class="btn btn-soft otp-resend-btn" style="min-height:30px;padding:4px 12px;font-size:12px;" disabled>Gửi lại (60s)</button>
    </div>
    <div class="field-error-msg otp-error-msg" aria-live="polite"></div>
  `;

  const boxes = Array.from(container.querySelectorAll('.otp-box'));
  const statusEl = container.querySelector('.otp-status-txt');
  const resendBtn = container.querySelector('.otp-resend-btn');
  const errEl = container.querySelector('.otp-error-msg');

  const notifyOTP = () => {
    if (DEMO_MODE && typeof window.showRideHubToast === 'function') {
      window.showRideHubToast(`[Chỉ môi trường thử] Mã OTP của bạn là: ${DEMO_OTP}`);
    }
  };

  const updateTimers = () => {
    const now = Date.now();
    if (lockUntil > now) {
      const left = Math.ceil((lockUntil - now) / 1000);
      const m = String(Math.floor(left / 60)).padStart(2, '0');
      const s = String(left % 60).padStart(2, '0');
      errEl.textContent = `Nhập sai quá 5 lần. Vui lòng thử lại sau ${m}:${s}.`;
      boxes.forEach((b) => (b.disabled = true));
      return;
    }
    boxes.forEach((b) => (b.disabled = false));

    if (resendSec > 0) {
      resendSec--;
      resendBtn.disabled = true;
      resendBtn.textContent = `Gửi lại (${resendSec}s)`;
    } else {
      resendBtn.disabled = false;
      resendBtn.textContent = 'Gửi lại mã OTP';
    }

    const expLeft = Math.max(0, Math.ceil((expiresAt - now) / 1000));
    const em = String(Math.floor(expLeft / 60)).padStart(2, '0');
    const es = String(expLeft % 60).padStart(2, '0');
    statusEl.textContent = expLeft > 0 ? `Hết hạn sau ${em}:${es}` : 'Mã OTP đã hết hạn';
  };

  timerId = setInterval(updateTimers, 1000);
  updateTimers();

  const verifyCode = () => {
    const code = boxes.map((b) => b.value).join('');
    if (code.length < 6) return;
    if (Date.now() > expiresAt) {
      errEl.textContent = 'Mã OTP đã hết hạn. Vui lòng bấm gửi lại.';
      return;
    }
    if (code === DEMO_OTP) {
      errEl.textContent = '';
      boxes.forEach((b) => {
        b.classList.remove('is-error', 'is-success-wave');
        void b.offsetWidth;
        b.classList.add('is-success-wave');
      });
      clearInterval(timerId);
      setTimeout(() => { if (onSuccess) onSuccess(code); }, 450);
    } else {
      attemptsLeft--;
      boxes.forEach((b) => {
        b.classList.add('is-error');
        b.value = '';
      });
      container.querySelector('.otp-row').classList.remove('field-shake');
      void container.offsetWidth;
      container.querySelector('.otp-row').classList.add('field-shake');
      if (attemptsLeft <= 0) {
        lockUntil = Date.now() + 15 * 60 * 1000;
        updateTimers();
      } else {
        errEl.textContent = `Mã OTP chưa đúng. Còn ${attemptsLeft} lần thử.`;
        boxes[0].focus();
      }
    }
  };

  boxes.forEach((box, idx) => {
    box.addEventListener('input', () => {
      box.classList.remove('is-error');
      box.value = box.value.replace(/\D/g, '').slice(0, 1);
      if (box.value) {
        box.classList.remove('is-pop');
        void box.offsetWidth;
        box.classList.add('is-pop');
        if (idx < 5) boxes[idx + 1].focus();
        else verifyCode();
      }
    });

    box.addEventListener('keydown', (e) => {
      if (e.key === 'Backspace' && !box.value && idx > 0) boxes[idx - 1].focus();
    });

    box.addEventListener('paste', (e) => {
      e.preventDefault();
      const pasted = (e.clipboardData || window.clipboardData).getData('text').replace(/\D/g, '').slice(0, 6);
      if (!pasted) return;
      pasted.split('').forEach((ch, i) => { if (boxes[i]) boxes[i].value = ch; });
      if (pasted.length === 6) verifyCode();
      else if (boxes[pasted.length]) boxes[pasted.length].focus();
    });
  });

  resendBtn.addEventListener('click', () => {
    resendSec = 60;
    expiresAt = Date.now() + 5 * 60 * 1000;
    attemptsLeft = 5;
    errEl.textContent = '';
    boxes.forEach((b) => { b.value = ''; b.classList.remove('is-error', 'is-success-wave'); });
    boxes[0].focus();
    notifyOTP();
    if (onResend) onResend();
  });

  return {
    triggerSend: notifyOTP,
    destroy: () => clearInterval(timerId)
  };
}

