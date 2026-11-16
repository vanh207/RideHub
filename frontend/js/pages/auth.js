 const loginForm = document.getElementById('loginForm');
    const regForm = document.getElementById('registerForm');
    const forgotForm = document.getElementById('forgotForm');
    const cardTitle = document.getElementById('authCardTitle');

    const switchAuthView = (mode) => {
      loginForm.hidden = mode !== 'login';
      regForm.hidden = mode !== 'register';
      forgotForm.hidden = mode !== 'forgot';
      cardTitle.textContent = mode === 'register' ? 'Đăng ký' : mode === 'forgot' ? 'Tạo lại mật khẩu' : 'Đăng nhập';
    };

    document.getElementById('goToRegisterLink')?.addEventListener('click', () => switchAuthView('register'));
    document.getElementById('goToLoginLink')?.addEventListener('click', () => switchAuthView('login'));
    document.getElementById('goToForgotLink')?.addEventListener('click', () => switchAuthView('forgot'));
    document.getElementById('forgotToLoginLink')?.addEventListener('click', () => switchAuthView('login'));

    // Remembered email restore
    const REMEMBER_KEY = 'ridehub_remembered_email';
    const savedEmail = localStorage.getItem(REMEMBER_KEY);
    if (savedEmail) {
      document.getElementById('loginEmailInput').value = savedEmail;
      document.getElementById('rememberLoginCheck').checked = true;
    }

    document.querySelectorAll('.toggle-pass-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const inp = document.getElementById(btn.dataset.target);
        if (!inp) return;
        const show = inp.type === 'password';
        inp.type = show ? 'text' : 'password';
        btn.textContent = show ? 'Ẩn' : 'Hiện';
      });
    });

    const markInvalid = (el) => {
      if (!el) return;
      el.classList.remove('is-input-error', 'field-shake');
      void el.offsetWidth;
      el.classList.add('is-input-error', 'field-shake');
    };

    document.querySelectorAll('#loginForm input, #registerForm input').forEach((inp) => {
      inp.addEventListener('input', () => inp.classList.remove('is-input-error'));
    });
    document.getElementById('regAgreeTerms')?.addEventListener('change', () => {
      document.getElementById('regTermsWrap')?.classList.remove('terms-error-ring');
    });

    loginForm?.addEventListener('submit', (e) => {
      e.preventDefault();
      const emailEl = document.getElementById('loginEmailInput');
      const passEl = document.getElementById('loginPassInput');
      let hasEmpty = false;
      [emailEl, passEl].forEach((el) => {
        if (!el.value.trim()) { markInvalid(el); hasEmpty = true; }
      });
      if (hasEmpty) {
        showRideHubToast('Vui lòng nhập đầy đủ email và mật khẩu!', true);
        return;
      }

      const res = AuthRBAC.login(emailEl.value, passEl.value);
      if (res.ok) {
        if (document.getElementById('rememberLoginCheck')?.checked) {
          localStorage.setItem(REMEMBER_KEY, emailEl.value.trim());
        } else {
          localStorage.removeItem(REMEMBER_KEY);
        }
        AuthRBAC.applyUI();
        showRideHubToast(`Xin chào ${res.user.name}!`);
      } else {
        markInvalid(passEl);
        showRideHubToast(res.message, true);
      }
    });

    const regPassIn = document.getElementById('regPassInput');
    const regPassConfirmIn = document.getElementById('regPassConfirmInput');
    const strengthBar = document.getElementById('regStrengthBar');
    const strengthLabel = document.getElementById('regStrengthLabel');
    const matchMsg = document.getElementById('regPassMatchMsg');

    const checkMatch = () => {
      const p1 = regPassIn.value;
      const p2 = regPassConfirmIn.value;
      if (!p2) {
        matchMsg.textContent = '';
        return false;
      }
      if (p1 === p2) {
        matchMsg.textContent = 'Mật khẩu trùng khớp';
        matchMsg.style.color = 'var(--green-700)';
        return true;
      } else {
        matchMsg.textContent = 'Mật khẩu nhập lại chưa khớp';
        matchMsg.style.color = '#e11d48';
        return false;
      }
    };

    regPassIn?.addEventListener('input', () => {
      const v = regPassIn.value;
      let score = 0;
      if (v.length >= 8) score++;
      if (/[A-Z]/.test(v)) score++;
      if (/[a-z]/.test(v)) score++;
      if (/\d/.test(v)) score++;

      const pct = (score / 4) * 100;
      strengthBar.style.width = pct + '%';
      if (!v) {
        strengthLabel.textContent = 'Chưa nhập';
        strengthLabel.style.color = 'var(--text-muted)';
      } else if (score <= 2) {
        strengthBar.style.backgroundColor = '#fb7185';
        strengthLabel.textContent = 'Yếu (cần ≥8 ký tự, chữ hoa, thường, số)';
        strengthLabel.style.color = '#e11d48';
      } else if (score === 3) {
        strengthBar.style.backgroundColor = '#eab308';
        strengthLabel.textContent = 'Trung bình';
        strengthLabel.style.color = '#ca8a04';
      } else {
        strengthBar.style.backgroundColor = '#22c55e';
        strengthLabel.textContent = 'Mạnh';
        strengthLabel.style.color = 'var(--green-700)';
      }
      checkMatch();
    });

    regPassConfirmIn?.addEventListener('input', checkMatch);

    regForm?.addEventListener('submit', (e) => {
      e.preventDefault();
      const nameEl = document.getElementById('regNameInput');
      const emailEl = document.getElementById('regEmailInput');
      const phoneEl = document.getElementById('regPhoneInput');
      const termsEl = document.getElementById('regAgreeTerms');
      const termsWrap = document.getElementById('regTermsWrap');

      let hasEmpty = false;
      [nameEl, emailEl, phoneEl, regPassIn, regPassConfirmIn].forEach((el) => {
        if (!el.value.trim()) { markInvalid(el); hasEmpty = true; }
      });
      if (hasEmpty) {
        showRideHubToast('Vui lòng điền đầy đủ thông tin đăng ký!', true);
        return;
      }
      if (!checkMatch()) {
        markInvalid(regPassConfirmIn);
        showRideHubToast('Mật khẩu nhập lại chưa khớp!', true);
        return;
      }
      if (!termsEl.checked) {
        termsWrap?.classList.add('terms-error-ring');
        showRideHubToast('Vui lòng đồng ý Điều khoản dịch vụ và Chính sách bảo mật!', true);
        return;
      }

      const res = AuthRBAC.register({
        name: nameEl.value.trim(),
        email: emailEl.value.trim(),
        phone: phoneEl.value.trim(),
        pass: regPassIn.value,
        role: 'customer'
      });
      if (res.ok) {
        AuthRBAC.applyUI();
        showRideHubToast(`Hoàn tất đăng ký! Xin chào ${res.user.name}.`);
      } else {
        showRideHubToast(res.message, true);
      }
    });

    // ======================================================================
    // Tạo lại mật khẩu bằng Email (Đầy đủ các trường hợp)
    // ======================================================================
    const fEmailEl = document.getElementById('forgotEmailInput');
    const fErr1 = document.getElementById('forgotErr1');
    const fStep1 = document.getElementById('forgotStep1');
    const fStep2 = document.getElementById('forgotStep2');
    const fStep3 = document.getElementById('forgotStep3');
    const fOtpBoxes = Array.from(document.querySelectorAll('.forgot-otp-box'));
    const fErr2 = document.getElementById('forgotErr2');
    const fResendBtn = document.getElementById('forgotResendBtn');
    const fOtpStatus = document.getElementById('forgotOtpStatus');
    let forgotTimer = null, fResendSec = 60, fExpiresAt = 0, fAttempts = 5, fLockUntil = 0, verifiedResetEmail = '';

    const startForgotTimer = () => {
      clearInterval(forgotTimer);
      fResendSec = 60;
      fExpiresAt = Date.now() + 5 * 60 * 1000;
      forgotTimer = setInterval(() => {
        const now = Date.now();
        if (fLockUntil > now) {
          const left = Math.ceil((fLockUntil - now) / 1000);
          fErr2.textContent = `Nhập sai quá 5 lần. Thử lại sau ${Math.floor(left / 60)}:${String(left % 60).padStart(2, '0')}.`;
          fOtpBoxes.forEach((b) => (b.disabled = true));
          return;
        }
        fOtpBoxes.forEach((b) => (b.disabled = false));
        if (fResendSec > 0) {
          fResendSec--;
          fResendBtn.disabled = true;
          fResendBtn.textContent = `Gửi lại (${fResendSec}s)`;
        } else {
          fResendBtn.disabled = false;
          fResendBtn.textContent = 'Gửi lại mã';
        }
        const exp = Math.max(0, Math.ceil((fExpiresAt - now) / 1000));
        fOtpStatus.textContent = exp > 0 ? `Hết hạn sau ${String(Math.floor(exp / 60)).padStart(2, '0')}:${String(exp % 60).padStart(2, '0')}` : 'Mã OTP đã hết hạn';
      }, 1000);
    };

    document.getElementById('forgotSendOtpBtn')?.addEventListener('click', () => {
      const mail = fEmailEl.value.trim();
      if (!mail) {
        markInvalid(fEmailEl);
        fErr1.textContent = 'Vui lòng nhập email.';
        return;
      }
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(mail)) {
        markInvalid(fEmailEl);
        fErr1.textContent = 'Email không đúng định dạng.';
        return;
      }
      if (!AuthRBAC.hasEmail(mail)) {
        markInvalid(fEmailEl);
        fErr1.textContent = 'Email này chưa được đăng ký tài khoản.';
        return;
      }
      fErr1.textContent = '';
      verifiedResetEmail = mail;
      document.getElementById('forgotEmailDisplay').textContent = mail;
      fStep1.hidden = true;
      fStep2.hidden = false;
      fAttempts = 5;
      fOtpBoxes.forEach((b) => (b.value = ''));
      startForgotTimer();
      showRideHubToast('[Môi trường thử] Mã OTP khôi phục qua Email là: 123456');
    });

    fResendBtn?.addEventListener('click', () => {
      fAttempts = 5;
      fErr2.textContent = '';
      fOtpBoxes.forEach((b) => (b.value = ''));
      startForgotTimer();
      showRideHubToast('[Môi trường thử] Đã gửi lại mã OTP: 123456');
    });

    document.getElementById('forgotBackEmailBtn')?.addEventListener('click', () => {
      clearInterval(forgotTimer);
      fStep2.hidden = true;
      fStep1.hidden = false;
    });

    const verifyForgotOtp = () => {
      const code = fOtpBoxes.map((b) => b.value).join('');
      if (code.length < 6) return;
      if (Date.now() > fExpiresAt) {
        fErr2.textContent = 'Mã OTP đã hết hạn. Vui lòng bấm gửi lại.';
        return;
      }
      if (code === '123456') {
        clearInterval(forgotTimer);
        fErr2.textContent = '';
        fStep2.hidden = true;
        fStep3.hidden = false;
      } else {
        fAttempts--;
        fOtpBoxes.forEach((b) => { b.value = ''; b.classList.add('is-input-error'); });
        if (fAttempts <= 0) {
          fLockUntil = Date.now() + 15 * 60 * 1000;
        } else {
          fErr2.textContent = `Mã OTP không đúng. Còn ${fAttempts} lần thử.`;
          fOtpBoxes[0].focus();
        }
      }
    };

    fOtpBoxes.forEach((box, idx) => {
      box.addEventListener('input', () => {
        box.classList.remove('is-input-error');
        box.value = box.value.replace(/\D/g, '').slice(0, 1);
        if (box.value) {
          if (idx < 5) fOtpBoxes[idx + 1].focus();
          else verifyForgotOtp();
        }
      });
      box.addEventListener('keydown', (e) => {
        if (e.key === 'Backspace' && !box.value && idx > 0) fOtpBoxes[idx - 1].focus();
      });
    });

    const fPass1 = document.getElementById('forgotNewPassInput');
    const fPass2 = document.getElementById('forgotNewPassConfirm');
    const fBar = document.getElementById('forgotStrengthBar');
    const fLbl = document.getElementById('forgotStrengthLabel');
    const fMatch = document.getElementById('forgotMatchMsg');

    const checkForgotMatch = () => {
      if (!fPass2.value) { fMatch.textContent = ''; return false; }
      if (fPass1.value === fPass2.value) {
        fMatch.textContent = 'Mật khẩu trùng khớp';
        fMatch.style.color = 'var(--green-700)';
        return true;
      }
      fMatch.textContent = 'Mật khẩu nhập lại chưa khớp';
      fMatch.style.color = '#e11d48';
      return false;
    };

    fPass1?.addEventListener('input', () => {
      const v = fPass1.value;
      let score = 0;
      if (v.length >= 8) score++;
      if (/[A-Z]/.test(v)) score++;
      if (/[a-z]/.test(v)) score++;
      if (/\d/.test(v)) score++;
      fBar.style.width = (score / 4) * 100 + '%';
      fBar.style.backgroundColor = score <= 2 ? '#fb7185' : score === 3 ? '#eab308' : '#22c55e';
      fLbl.textContent = !v ? 'Chưa nhập' : score <= 2 ? 'Yếu' : score === 3 ? 'Trung bình' : 'Mạnh';
      checkForgotMatch();
    });
    fPass2?.addEventListener('input', checkForgotMatch);

    forgotForm?.addEventListener('submit', (e) => {
      e.preventDefault();
      let empty = false;
      [fPass1, fPass2].forEach((el) => { if (!el.value.trim()) { markInvalid(el); empty = true; } });
      if (empty) { showRideHubToast('Vui lòng nhập mật khẩu mới!', true); return; }
      if (!checkForgotMatch()) { markInvalid(fPass2); showRideHubToast('Mật khẩu nhập lại chưa khớp!', true); return; }

      const res = AuthRBAC.resetPasswordByEmail(verifiedResetEmail, fPass1.value);
      if (res.ok) {
        document.getElementById('loginEmailInput').value = verifiedResetEmail;
        document.getElementById('loginPassInput').value = '';
        fStep3.hidden = true;
        fStep1.hidden = false;
        switchAuthView('login');
        showRideHubToast('Tạo lại mật khẩu thành công! Vui lòng đăng nhập.');
      } else {
        showRideHubToast(res.message, true);
      }
    });