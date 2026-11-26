(function () {
  'use strict';

  // Xóa bỏ toàn bộ Avatar & Notif ngay lập tức khi vào trang auth
  const purgeAvatarsOnAuthPage = () => {
    document.querySelectorAll('#rbacUserPill, #rhUserWrap, #rhNotifWrap, #rbacNotifWrap, .user-menu-wrap, .notif-wrap, .user-avatar-trigger, .user-avatar-circle, .user-avatar-dropdown').forEach(el => el.remove());
  };
  purgeAvatarsOnAuthPage();
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', purgeAvatarsOnAuthPage);
  }

  // ── Cookie Helpers ────────────────────────────────────────────────────────────
  function setCookie(name, value, days = 7) {
    let expires = "";
    if (days) {
      const d = new Date();
      d.setTime(d.getTime() + (days * 24 * 60 * 60 * 1000));
      expires = "; expires=" + d.toUTCString();
    }
    document.cookie = `${name}=${encodeURIComponent(value || "")}${expires}; path=/; SameSite=Lax`;
  }

  function getCookie(name) {
    const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
    return match ? decodeURIComponent(match[2]) : null;
  }

  function deleteCookie(name) {
    document.cookie = `${name}=; path=/; expires=Thu, 01 Jan 1970 00:00:01 GMT; SameSite=Lax`;
  }

  window.setCookie = setCookie;
  window.getCookie = getCookie;
  window.deleteCookie = deleteCookie;

  const loginForm = document.getElementById('loginForm');
  const regForm = document.getElementById('registerForm');
  const forgotForm = document.getElementById('forgotForm');
  const waitingView = document.getElementById('waitingRoomView');
  const cardTitle = document.getElementById('authCardTitle');

  let waitingTimer = null;
  let waitingSec = 60;
  let currentWaitingEmail = '';
  let checkVerificationInterval = null;

  const startAutoCheckVerification = (email, user) => {
    if (checkVerificationInterval) {
      clearInterval(checkVerificationInterval);
      checkVerificationInterval = null;
    }
    if (!email) return;

    checkVerificationInterval = setInterval(async () => {
      try {
        const res = await fetch(getApiUrl(`auth/check-verification?email=${encodeURIComponent(email)}`));
        if (!res.ok) return;
        const resData = await res.json().catch(() => ({}));
        if (resData && resData.data && resData.data.verified) {
          clearInterval(checkVerificationInterval);
          checkVerificationInterval = null;

          if (typeof showRideHubToast === 'function') {
            showRideHubToast('🎉 Email đã được xác thực thành công! Đang chuyển hướng vào trang tìm xe...');
          }

          const targetUser = user || window.__lastRegisteredUser || (typeof AuthRBAC !== 'undefined' && AuthRBAC.getCurrentUser()) || { email };
          targetUser.status = 'active';
          targetUser.is_verified = true;
          if (typeof AuthRBAC !== 'undefined') {
            AuthRBAC.setCurrentUser(targetUser);
          }
          window.__lastRegisteredUser = targetUser;
          localStorage.setItem('ridehub_require_docs', 'true');

          setTimeout(() => {
            window.location.href = '../vehicles.html?require_docs=1';
          }, 800);
        }
      } catch (_) {}
    }, 2000);
  };

  const startWaitingResendTimer = () => {
    clearInterval(waitingTimer);
    waitingSec = 60;
    const resendBtn = document.getElementById('waitingResendEmailBtn');
    if (resendBtn) {
      resendBtn.disabled = true;
      resendBtn.innerHTML = `Gửi lại email xác thực (<span id="waitingTimerSpan">60</span>s)`;
    }

    waitingTimer = setInterval(() => {
      if (waitingSec > 0) {
        waitingSec--;
        const span = document.getElementById('waitingTimerSpan');
        if (span) span.textContent = waitingSec;
      } else {
        clearInterval(waitingTimer);
        if (resendBtn) {
          resendBtn.disabled = false;
          resendBtn.textContent = 'Gửi lại email xác thực';
        }
      }
    }, 1000);
  };

  const switchAuthView = (mode, data = {}) => {
    if (loginForm) loginForm.hidden = mode !== 'login';
    if (regForm) regForm.hidden = mode !== 'register';
    if (forgotForm) forgotForm.hidden = mode !== 'forgot';
    if (waitingView) waitingView.hidden = mode !== 'waiting';

    if (cardTitle) {
      if (mode === 'waiting') cardTitle.textContent = 'Phòng chờ kích hoạt email';
      else if (mode === 'register') cardTitle.textContent = 'Đăng ký tài khoản';
      else if (mode === 'forgot') cardTitle.textContent = 'Quên mật khẩu';
      else cardTitle.textContent = 'Đăng nhập';
    }

    if (mode === 'waiting') {
      if (data.name) {
        const nameEl = document.getElementById('waitingUserName');
        if (nameEl) nameEl.textContent = data.name;
      }
      if (data.email) {
        currentWaitingEmail = data.email;
        const emailEl = document.getElementById('waitingUserEmail');
        if (emailEl) emailEl.textContent = data.email;
      }
      if (data.verification_link) {
        const linkBtn = document.getElementById('waitingFirebaseLinkBtn');
        if (linkBtn) {
          linkBtn.href = data.verification_link;
          linkBtn.style.display = 'inline-flex';
        }
      } else {
        const linkBtn = document.getElementById('waitingFirebaseLinkBtn');
        if (linkBtn) linkBtn.style.display = 'none';
      }
      startWaitingResendTimer();
      // Bắt đầu tự động lắng nghe xác thực email từ Firebase
      startAutoCheckVerification(currentWaitingEmail, data);
    } else {
      if (checkVerificationInterval) {
        clearInterval(checkVerificationInterval);
        checkVerificationInterval = null;
      }
    }
  };

  document.getElementById('goToRegisterLink')?.addEventListener('click', () => switchAuthView('register'));
  document.getElementById('goToLoginLink')?.addEventListener('click', () => switchAuthView('login'));
  document.getElementById('goToForgotLink')?.addEventListener('click', () => switchAuthView('forgot'));
  document.getElementById('forgotToLoginLink')?.addEventListener('click', () => switchAuthView('login'));

  // Nút xác nhận sau khi đã bấm link email Firebase
  document.getElementById('waitingVerifyBtn')?.addEventListener('click', async () => {
    const btn = document.getElementById('waitingVerifyBtn');
    const originalText = btn ? btn.innerHTML : '';
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<span>Đang kiểm tra xác thực...</span>';
    }

    const email = currentWaitingEmail || document.getElementById('waitingUserEmail')?.textContent || '';
    let isVerified = false;

    if (email) {
      try {
        const res = await fetch(getApiUrl(`auth/check-verification?email=${encodeURIComponent(email)}`));
        if (res.ok) {
          const resData = await res.json().catch(() => ({}));
          if (resData && resData.data && resData.data.verified) {
            isVerified = true;
          }
        }
      } catch (_) {}
    }

    if (btn) {
      btn.disabled = false;
      btn.innerHTML = originalText;
    }

    if (isVerified) {
      if (checkVerificationInterval) {
        clearInterval(checkVerificationInterval);
        checkVerificationInterval = null;
      }
      const user = window.__lastRegisteredUser || (typeof AuthRBAC !== 'undefined' && AuthRBAC.getCurrentUser()) || { email };
      user.status = 'active';
      user.is_verified = true;
      if (typeof AuthRBAC !== 'undefined') {
        AuthRBAC.setCurrentUser(user);
      }
      if (typeof showRideHubToast === 'function') {
        showRideHubToast('🎉 Email đã được xác thực thành công! Đang chuyển hướng vào trang tìm xe...');
      }
      localStorage.setItem('ridehub_require_docs', 'true');
      setTimeout(() => {
        window.location.href = '../vehicles.html?require_docs=1';
      }, 700);
    } else {
      if (typeof showRideHubToast === 'function') {
        showRideHubToast('Hệ thống chưa ghi nhận bạn đã bấm link xác thực. Bạn vui lòng kiểm tra hộp thư (hoặc mục Spam/Rác) và bấm vào liên kết trong email gửi từ Firebase trước nhé!', true);
      }
    }
  });

  // Nút gửi lại email xác thực chính thức từ Firebase
  document.getElementById('waitingResendEmailBtn')?.addEventListener('click', async () => {
    const email = currentWaitingEmail || document.getElementById('waitingUserEmail')?.textContent || '';
    if (!email) {
      if (typeof showRideHubToast === 'function') showRideHubToast('Không xác định được email nhận.', true);
      return;
    }
    try {
      const res = await fetch(getApiUrl('auth/resend-verification'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim() }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        if (data.data && data.data.verification_link) {
          const linkBtn = document.getElementById('waitingFirebaseLinkBtn');
          if (linkBtn) {
            linkBtn.href = data.data.verification_link;
            linkBtn.style.display = 'inline-flex';
          }
        }
        if (typeof showRideHubToast === 'function') {
          showRideHubToast('Đã gửi lại email xác thực Firebase thành công! Vui lòng kiểm tra hộp thư.');
        }
        startWaitingResendTimer();
      } else {
        if (typeof showRideHubToast === 'function') {
          showRideHubToast(data.detail || 'Không thể gửi lại email vào lúc này.', true);
        }
      }
    } catch (err) {
      if (typeof showRideHubToast === 'function') {
        showRideHubToast('Lỗi kết nối khi gửi lại email xác thực.', true);
      }
    }
  });

  document.getElementById('waitingGoLoginBtn')?.addEventListener('click', () => {
    switchAuthView('login');
  });

  document.getElementById('waitingGoEkycBtn')?.addEventListener('click', () => {
    localStorage.setItem('ridehub_require_docs', 'true');
    window.location.href = '../vehicles.html?require_docs=1';
  });

  // Khôi phục email đã ghi nhớ
  const REMEMBER_KEY = 'ridehub_remembered_email';
  const savedEmail = localStorage.getItem(REMEMBER_KEY);
  if (savedEmail) {
    const emailIn = document.getElementById('loginEmailInput');
    const remChk = document.getElementById('rememberLoginCheck');
    if (emailIn) emailIn.value = savedEmail;
    if (remChk) remChk.checked = true;
  }

  // Nút ẩn/hiện mật khẩu
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

  const getApiUrl = (endpoint) => {
    let base = (typeof CONFIG !== 'undefined' && CONFIG.API_BASE_URL) ? CONFIG.API_BASE_URL : 'http://127.0.0.1:8000/api';
    base = base.replace(/\/+$/, '');
    const path = endpoint.replace(/^\/+/, '');
    return `${base}/${path}`;
  };

  // ======================================================================
  // 1. Xử lý Đăng nhập thông thường (Email & Password qua Backend API)
  // ======================================================================
  loginForm?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const emailEl = document.getElementById('loginEmailInput');
    const passEl = document.getElementById('loginPassInput');
    const submitBtn = loginForm.querySelector('button[type="submit"]');

    let hasEmpty = false;
    [emailEl, passEl].forEach((el) => {
      if (!el.value.trim()) { markInvalid(el); hasEmpty = true; }
    });
    if (hasEmpty) {
      if (typeof showRideHubToast === 'function') {
        showRideHubToast('Vui lòng nhập đầy đủ email và mật khẩu!', true);
      }
      return;
    }

    const originalBtnText = submitBtn ? submitBtn.textContent : '';
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = 'Đang đăng nhập...';
    }

    try {
      const isRemember = !!document.getElementById('rememberLoginCheck')?.checked;
      const response = await fetch(getApiUrl('auth/login'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: JSON.stringify({
          email: emailEl.value.trim(),
          password: passEl.value,
          remember_me: isRemember,
        }),
      });

      const resData = await response.json().catch(() => ({}));

      if (response.ok) {
        const payload = resData.data || resData;
        const user = {
          id: payload.user_id,
          name: payload.full_name || emailEl.value.trim().split('@')[0],
          email: payload.email || emailEl.value.trim(),
          phone: payload.phone || '',
          role: payload.role || 'customer',
          verification_link: payload.verification_link,
        };

        const cookieDays = isRemember ? 30 : 7;
        if (payload.access_token) {
          setCookie('ridehub_token', payload.access_token, cookieDays);
          setCookie('token', payload.access_token, cookieDays);
          setCookie('ridehub_auth_token', payload.access_token, cookieDays);
          localStorage.setItem('ridehub_token', payload.access_token);
          localStorage.setItem('token', payload.access_token);
          localStorage.setItem('ridehub_auth_token', payload.access_token);
        }
        if (payload.refresh_token) {
          setCookie('ridehub_refresh_token', payload.refresh_token, isRemember ? 90 : 30);
          localStorage.setItem('ridehub_refresh_token', payload.refresh_token);
        }

        if (document.getElementById('rememberLoginCheck')?.checked) {
          localStorage.setItem(REMEMBER_KEY, emailEl.value.trim());
        } else {
          localStorage.removeItem(REMEMBER_KEY);
        }

        if (typeof AuthRBAC !== 'undefined') {
          AuthRBAC.setCurrentUser(user);
          AuthRBAC.applyUI();
        }

        if (typeof showRideHubToast === 'function') {
          showRideHubToast('Chào mừng bạn đến với hệ thống!');
        }

        setTimeout(() => {
          const roleHomes = {
            customer: '../vehicles.html',
            store_owner: 'store-portal.html',
            store_staff: 'store-portal.html',
            operator: 'operations-anomalies.html',
            admin: 'operations-anomalies.html',
          };
          const targetUrl = roleHomes[user.role] || '../vehicles.html';
          window.location.href = targetUrl;
        }, 800);
      } else {
        markInvalid(passEl);
        let errMsg = 'Đăng nhập không thành công.';
        if (resData.detail) {
          if (typeof resData.detail === 'string') errMsg = resData.detail;
          else if (Array.isArray(resData.detail)) errMsg = resData.detail.map((d) => d.msg).join(', ');
        } else if (resData.message) {
          errMsg = resData.message;
        }
        if (typeof showRideHubToast === 'function') showRideHubToast(errMsg, true);
      }
    } catch (err) {
      console.error('Login API error:', err);
      if (typeof showRideHubToast === 'function') {
        showRideHubToast('Không thể kết nối đến máy chủ backend (127.0.0.1:8000). Vui lòng kiểm tra server!', true);
      }
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = originalBtnText;
      }
    }
  });

  // ======================================================================
  // 2. Xử lý Đăng nhập qua Google (Firebase Client Auth + Backend RBAC)
  // ======================================================================
  const initFirebaseClient = async () => {
    if (typeof firebase === 'undefined') return null;
    if (!firebase.apps || !firebase.apps.length) {
      if (window.envConfigPromise) {
        await window.envConfigPromise.catch(() => {});
      }
      const storedApiKey = localStorage.getItem('ridehub_firebase_api_key');
      let currentApiKey = (typeof CONFIG !== 'undefined' && CONFIG.FIREBASE && CONFIG.FIREBASE.apiKey) ? CONFIG.FIREBASE.apiKey : (storedApiKey || "");

      if (!currentApiKey) {
        try {
          const cfgRes = await fetch(getApiUrl('auth/config'));
          if (cfgRes.ok) {
            const cfgData = await cfgRes.json();
            if (cfgData?.data?.firebase) {
              const fb = cfgData.data.firebase;
              if (fb.apiKey) currentApiKey = fb.apiKey;
              if (typeof CONFIG !== 'undefined' && CONFIG.FIREBASE) {
                if (fb.apiKey) CONFIG.FIREBASE.apiKey = fb.apiKey;
                if (fb.projectId) CONFIG.FIREBASE.projectId = fb.projectId;
                if (fb.authDomain) CONFIG.FIREBASE.authDomain = fb.authDomain;
                if (fb.storageBucket) CONFIG.FIREBASE.storageBucket = fb.storageBucket;
              }
            }
          }
        } catch (_) {}
      }

      const fbConfig = {
        apiKey: currentApiKey,
        projectId: (typeof CONFIG !== 'undefined' && CONFIG.FIREBASE && CONFIG.FIREBASE.projectId) || "ridehub-carmoto",
        authDomain: (typeof CONFIG !== 'undefined' && CONFIG.FIREBASE && CONFIG.FIREBASE.authDomain) || "ridehub-carmoto.firebaseapp.com",
        storageBucket: (typeof CONFIG !== 'undefined' && CONFIG.FIREBASE && CONFIG.FIREBASE.storageBucket) || "ridehub-carmoto.appspot.com",
      };

      if (!fbConfig.apiKey) {
        const enteredKey = prompt(
          "Cần nhập Firebase Web API Key của dự án 'ridehub-carmoto':\n\n" +
          "1. Truy cập: https://console.firebase.google.com/project/ridehub-carmoto/settings/general\n" +
          "2. Sao chép dòng 'Web API Key' (bắt đầu bằng AIzaSy...)\n" +
          "3. Dán vào ô bên dưới:"
        );
        if (enteredKey && enteredKey.trim()) {
          fbConfig.apiKey = enteredKey.trim();
          localStorage.setItem('ridehub_firebase_api_key', fbConfig.apiKey);
          if (typeof CONFIG !== 'undefined' && CONFIG.FIREBASE) {
            CONFIG.FIREBASE.apiKey = fbConfig.apiKey;
          }
        } else {
          throw new Error('Chưa cung cấp Web API Key từ Firebase Console.');
        }
      }

      try {
        return firebase.initializeApp(fbConfig);
      } catch (e) {
        console.warn('[Firebase] Init client error:', e);
        return null;
      }
    }
    return firebase.app();
  };

  const handleLocalFileGoogleLogin = () => {
    const isFile = window.location.protocol === 'file:';
    const msg = isFile
      ? "LƯU Ý VỀ ĐĂNG NHẬP GOOGLE FIREBASE:\n\n" +
        "Trang đang được mở bằng file:/// trực tiếp.\n" +
        "Google & Firebase OAuth bắt buộc chạy qua máy chủ tên miền localhost (http://localhost:8000 hoặc Live Server http://localhost:5500 / 5501).\n\n" +
        "• Chọn [OK]: Chuyển sang máy chủ backend (http://localhost:8000/frontend/pages/auth.html)\n" +
        "• Chọn [Cancel]: Dùng thử tài khoản Google mô phỏng (Demo Google Mode) để tiếp tục ngay."
      : "Google OAuth popup bị chặn trong môi trường này. Bạn có muốn dùng tài khoản Google mô phỏng?";

    const proceedHttp = confirm(msg);
    if (proceedHttp) {
      window.location.href = 'http://localhost:8000/frontend/pages/auth.html';
    } else {
      const demoUser = {
        id: 'usr_demo_google_' + Date.now().toString(36),
        name: 'Nguyễn Văn An (Google Demo)',
        email: 'an.nguyen.google@ridehub.vn',
        phone: '0988776655',
        role: 'customer'
      };
      if (typeof AuthRBAC !== 'undefined') {
        AuthRBAC.setCurrentUser(demoUser);
        AuthRBAC.applyUI();
      }
      setCookie('ridehub_token', 'demo_google_token_' + Date.now(), 7);
      localStorage.setItem('ridehub_token', 'demo_google_token_' + Date.now());
      if (typeof showRideHubToast === 'function') {
        showRideHubToast(`Đăng nhập Google thành công! Đang chuyển hướng vào trang tìm xe...`);
      }
      window.__lastRegisteredUser = demoUser;
      localStorage.setItem('ridehub_require_docs', 'true');
      setTimeout(() => {
        window.location.href = '../vehicles.html?require_docs=1';
      }, 700);
    }
  };

  document.getElementById('googleLoginBtn')?.addEventListener('click', async () => {
    const googleBtn = document.getElementById('googleLoginBtn');
    const originalHtml = googleBtn.innerHTML;

    if (window.location.protocol === 'file:') {
      alert(
        "LƯU Ý VỀ ĐĂNG NHẬP GOOGLE:\n\n" +
        "Bạn đang mở trang trực tiếp bằng file:/// (nhấp đúp từ ổ đĩa).\n" +
        "Google OAuth bắt buộc chạy qua máy chủ web (Live Server hoặc Backend FastAPI).\n\n" +
        "Hệ thống sẽ chuyển bạn sang máy chủ http://localhost:8000/frontend/pages/auth.html để đăng nhập Google thật."
      );
      window.location.href = 'http://localhost:8000/frontend/pages/auth.html';
      return;
    }

    // Tự động chuyển từ 127.0.0.1 sang localhost để tránh lỗi auth/unauthorized-domain của Firebase
    if (window.location.hostname === '127.0.0.1') {
      const targetUrl = window.location.href.replace('127.0.0.1', 'localhost');
      window.location.replace(targetUrl);
      return;
    }

    googleBtn.disabled = true;
    googleBtn.innerHTML = '<span>Đang kết nối Google Firebase...</span>';

    try {
      const app = await initFirebaseClient();
      if (!app || typeof firebase.auth !== 'function') {
        throw new Error('Firebase Auth SDK chưa sẵn sàng.');
      }

      const provider = new firebase.auth.GoogleAuthProvider();
      provider.addScope('email');
      provider.addScope('profile');
      provider.setCustomParameters({ prompt: 'select_account' });

      const result = await firebase.auth().signInWithPopup(provider);
      const idToken = await result.user.getIdToken();

      // Gửi Firebase ID Token đến Backend API
      const response = await fetch(getApiUrl('auth/firebase-login'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: JSON.stringify({ id_token: idToken }),
      });

      const resData = await response.json().catch(() => ({}));

      if (response.ok) {
        const payload = resData.data || resData;
        const user = {
          id: payload.user_id,
          name: payload.full_name || result.user.displayName || 'Khách hàng Google',
          email: payload.email || result.user.email,
          phone: payload.phone || '',
          role: payload.role || 'customer',
          verification_link: payload.verification_link,
        };

        if (payload.access_token) {
          setCookie('ridehub_token', payload.access_token, 7);
          setCookie('token', payload.access_token, 7);
          setCookie('ridehub_auth_token', payload.access_token, 7);
          localStorage.setItem('ridehub_token', payload.access_token);
          localStorage.setItem('token', payload.access_token);
          localStorage.setItem('ridehub_auth_token', payload.access_token);
        }
        if (payload.refresh_token) {
          setCookie('ridehub_refresh_token', payload.refresh_token, 30);
          localStorage.setItem('ridehub_refresh_token', payload.refresh_token);
        }

        if (typeof AuthRBAC !== 'undefined') {
          AuthRBAC.setCurrentUser(user);
          AuthRBAC.applyUI();
        }

        if (typeof showRideHubToast === 'function') {
          showRideHubToast('Chào mừng bạn đến với hệ thống! Đang chuyển hướng vào trang tìm xe...');
        }

        window.__lastRegisteredUser = user;
        localStorage.setItem('ridehub_require_docs', 'true');

        setTimeout(() => {
          window.location.href = '../vehicles.html?require_docs=1';
        }, 700);
      } else {
        const errMsg = resData.detail || resData.message || 'Xác thực Google qua máy chủ thất bại.';
        if (typeof showRideHubToast === 'function') showRideHubToast(errMsg, true);
      }
    } catch (err) {
      console.warn('Google Firebase Login error:', err);
      if (err.code === 'auth/invalid-api-key') {
        localStorage.removeItem('ridehub_firebase_api_key');
        if (typeof showRideHubToast === 'function') {
          showRideHubToast('Web API Key chưa đúng. Vui lòng kiểm tra lại Web API Key trong Firebase Console.', true);
        }
      } else if (err.code === 'auth/operation-not-supported-in-this-environment') {
        if (typeof showRideHubToast === 'function') {
          showRideHubToast('Môi trường trình duyệt hiện tại không hỗ trợ Google Popup.', true);
        }
      } else if (err.code === 'auth/popup-closed-by-user') {
        if (typeof showRideHubToast === 'function') showRideHubToast('Bạn đã đóng cửa sổ đăng nhập Google.', true);
      } else if (err.code === 'auth/configuration-not-found') {
        if (typeof showRideHubToast === 'function') {
          showRideHubToast('Firebase chưa bật Google Sign-In Provider trong Firebase Console.', true);
        }
      } else if (err.code === 'auth/unauthorized-domain') {
        const currentHost = window.location.hostname;
        if (typeof showRideHubToast === 'function') {
          showRideHubToast(`Tên miền '${currentHost}' chưa được cấp phép trong Firebase Console. Hãy mở web qua 'localhost' (VD: http://localhost:5501/...) hoặc thêm '${currentHost}' vào Authorized Domains trên Firebase Console.`, true);
        }
      } else {
        if (typeof showRideHubToast === 'function') {
          showRideHubToast(`Lỗi Google: ${err.message || 'Không thể hoàn tất xác thực.'}`, true);
        }
      }
    } finally {
      if (googleBtn) {
        googleBtn.disabled = false;
        googleBtn.innerHTML = originalHtml;
      }
    }
  });

  // ======================================================================
  // 3. Xử lý Đăng ký tài khoản -> Nhảy sang PHÒNG CHỜ XÁC THỰC
  // ======================================================================
  const regPassIn = document.getElementById('regPassInput');
  const regPassConfirmIn = document.getElementById('regPassConfirmInput');
  const strengthBar = document.getElementById('regStrengthBar');
  const strengthLabel = document.getElementById('regStrengthLabel');
  const matchMsg = document.getElementById('regPassMatchMsg');

  const checkMatch = () => {
    const p1 = regPassIn?.value || '';
    const p2 = regPassConfirmIn?.value || '';
    if (!matchMsg) return false;
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
    if (strengthBar) strengthBar.style.width = pct + '%';
    if (!strengthLabel) return;
    if (!v) {
      strengthLabel.textContent = 'Chưa nhập';
      strengthLabel.style.color = 'var(--text-muted)';
    } else if (score <= 2) {
      if (strengthBar) strengthBar.style.backgroundColor = '#fb7185';
      strengthLabel.textContent = 'Yếu (cần ≥8 ký tự, chữ hoa, thường, số)';
      strengthLabel.style.color = '#e11d48';
    } else if (score === 3) {
      if (strengthBar) strengthBar.style.backgroundColor = '#eab308';
      strengthLabel.textContent = 'Trung bình';
      strengthLabel.style.color = '#ca8a04';
    } else {
      if (strengthBar) strengthBar.style.backgroundColor = '#22c55e';
      strengthLabel.textContent = 'Mạnh';
      strengthLabel.style.color = 'var(--green-700)';
    }
    checkMatch();
  });

  regPassConfirmIn?.addEventListener('input', checkMatch);

  regForm?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const nameEl = document.getElementById('regNameInput');
    const emailEl = document.getElementById('regEmailInput');
    const phoneEl = document.getElementById('regPhoneInput');
    const termsEl = document.getElementById('regAgreeTerms');
    const termsWrap = document.getElementById('regTermsWrap');
    const submitBtn = regForm.querySelector('button[type="submit"]');

    let hasEmpty = false;
    [nameEl, emailEl, phoneEl, regPassIn, regPassConfirmIn].forEach((el) => {
      if (!el || !el.value.trim()) { markInvalid(el); hasEmpty = true; }
    });
    if (hasEmpty) {
      if (typeof showRideHubToast === 'function') {
        showRideHubToast('Vui lòng điền đầy đủ thông tin đăng ký!', true);
      }
      return;
    }
    if (!checkMatch()) {
      markInvalid(regPassConfirmIn);
      if (typeof showRideHubToast === 'function') {
        showRideHubToast('Mật khẩu nhập lại chưa khớp!', true);
      }
      return;
    }
    if (termsEl && !termsEl.checked) {
      termsWrap?.classList.add('terms-error-ring');
      if (typeof showRideHubToast === 'function') {
        showRideHubToast('Vui lòng đồng ý Điều khoản dịch vụ và Chính sách bảo mật!', true);
      }
      return;
    }

    const originalBtnText = submitBtn ? submitBtn.textContent : '';
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = 'Đang đăng ký...';
    }

    try {
      const response = await fetch(getApiUrl('auth/register'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: JSON.stringify({
          full_name: nameEl.value.trim(),
          email: emailEl.value.trim(),
          phone: phoneEl.value.trim(),
          password: regPassIn.value,
          confirm_password: regPassConfirmIn.value,
        }),
      });

      const resData = await response.json().catch(() => ({}));

      if (response.ok) {
        const payload = resData.data || resData;
        const user = {
          id: payload.user_id,
          name: payload.full_name || nameEl.value.trim(),
          email: payload.email || emailEl.value.trim(),
          phone: payload.phone || phoneEl.value.trim(),
          role: payload.role || 'customer',
          verification_link: payload.verification_link,
        };

        if (payload.access_token) {
          setCookie('ridehub_token', payload.access_token, 7);
          setCookie('token', payload.access_token, 7);
          setCookie('ridehub_auth_token', payload.access_token, 7);
          localStorage.setItem('ridehub_token', payload.access_token);
          localStorage.setItem('token', payload.access_token);
          localStorage.setItem('ridehub_auth_token', payload.access_token);
        }
        if (payload.refresh_token) {
          setCookie('ridehub_refresh_token', payload.refresh_token, 30);
          localStorage.setItem('ridehub_refresh_token', payload.refresh_token);
        }

        if (typeof AuthRBAC !== 'undefined') {
          AuthRBAC.setCurrentUser(user);
          AuthRBAC.applyUI();
        }

        if (typeof showRideHubToast === 'function') {
          showRideHubToast('Xác thực tài khoản thành công!');
        }

        // Lưu thông tin để eKYC sử dụng
        window.__lastRegisteredUser = user;

        // CHUYỂN NGAY VÀO PHÒNG CHỜ XÁC THỰC TÀI KHOẢN (WAITING ROOM & MODAL EKYC)
        setTimeout(() => {
          switchAuthView('waiting', user);
          openEkycModal(user);
        }, 500);
      } else {
        let errMsg = 'Đăng ký không thành công.';
        if (resData.detail) {
          if (typeof resData.detail === 'string') errMsg = resData.detail;
          else if (Array.isArray(resData.detail)) errMsg = resData.detail.map((d) => d.msg).join(', ');
        } else if (resData.message) {
          errMsg = resData.message;
        }
        if (typeof showRideHubToast === 'function') showRideHubToast(errMsg, true);
      }
    } catch (err) {
      console.error('Register API error:', err);
      if (typeof showRideHubToast === 'function') {
        showRideHubToast('Không thể kết nối đến máy chủ backend (127.0.0.1:8000). Vui lòng kiểm tra server!', true);
      }
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = originalBtnText;
      }
    }
  });

  // ======================================================================
  // 4. Quên mật khẩu qua Email (Gửi liên kết đặt lại mật khẩu từ Firebase)
  // ======================================================================
  const fEmailEl = document.getElementById('forgotEmailInput');
  const fErr1 = document.getElementById('forgotErr1');
  const fStep1 = document.getElementById('forgotStep1');
  const fStep2 = document.getElementById('forgotStep2');
  const fSendBtn = document.getElementById('forgotSendOtpBtn');

  fSendBtn?.addEventListener('click', async () => {
    const mail = fEmailEl?.value.trim() || '';
    if (!mail) {
      markInvalid(fEmailEl);
      if (fErr1) fErr1.textContent = 'Vui lòng nhập địa chỉ email.';
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(mail)) {
      markInvalid(fEmailEl);
      if (fErr1) fErr1.textContent = 'Email không đúng định dạng.';
      return;
    }
    if (fErr1) fErr1.textContent = '';

    fSendBtn.disabled = true;
    fSendBtn.textContent = 'Đang gửi email...';

    try {
      const res = await fetch(getApiUrl('auth/forgot-password'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: mail }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        if (fStep1) fStep1.hidden = true;
        if (fStep2) fStep2.hidden = false;
        const disp = document.getElementById('forgotEmailDisplay');
        if (disp) disp.textContent = mail;
        if (typeof showRideHubToast === 'function') {
          showRideHubToast('✓ Đã gửi email đặt lại mật khẩu! Vui lòng kiểm tra hộp thư.');
        }
      } else {
        const msg = data.detail || data.message || 'Không thể gửi email đặt lại mật khẩu.';
        if (fErr1) fErr1.textContent = msg;
        if (typeof showRideHubToast === 'function') showRideHubToast(msg, true);
      }
    } catch (err) {
      if (fErr1) fErr1.textContent = 'Lỗi kết nối máy chủ.';
      if (typeof showRideHubToast === 'function') showRideHubToast('Lỗi kết nối đến server.', true);
    } finally {
      fSendBtn.disabled = false;
      fSendBtn.textContent = 'Gửi link đặt lại mật khẩu qua Email';
    }
  });

  // ======================================================================
  // 4. Quản lý Modal Phòng chờ xác thực eKYC CCCD & Khuôn mặt (FR-08, FR-09)
  // ======================================================================
  const ekycModal = document.getElementById('ekycWaitingRoomModal');
  const eStepTags = [
    document.getElementById('eStepTag1'),
    document.getElementById('eStepTag2'),
    document.getElementById('eStepTag3'),
    document.getElementById('eStepTag4'),
  ];
  const ekycPanels = [
    document.getElementById('ekycPanelStep1'),
    document.getElementById('ekycPanelStep2'),
    document.getElementById('ekycPanelStep3'),
    document.getElementById('ekycPanelStep4'),
  ];

  let currentEkycUser = null;

  const setEkycStep = (stepNum) => {
    eStepTags.forEach((tag, idx) => {
      if (!tag) return;
      tag.classList.remove('is-active', 'is-done');
      if (idx + 1 < stepNum) tag.classList.add('is-done');
      else if (idx + 1 === stepNum) tag.classList.add('is-active');
    });

    ekycPanels.forEach((p, idx) => {
      if (!p) return;
      p.style.display = (idx + 1 === stepNum) ? 'block' : 'none';
    });
  };

  const openEkycModal = (user = {}) => {
    currentEkycUser = user;
    if (ekycModal) {
      ekycModal.style.display = 'flex';
      setEkycStep(1);
    }
    const ocrName = document.getElementById('ocrFullName');
    if (ocrName) ocrName.textContent = user.name || 'NGUYỄN VĂN AN';
    const sName = document.getElementById('succUserName');
    if (sName) sName.textContent = user.name || 'Nguyễn Văn An';
    const sEmail = document.getElementById('succUserEmail');
    if (sEmail) sEmail.textContent = user.email || 'user@example.com';
    const sPhone = document.getElementById('succUserPhone');
    if (sPhone) sPhone.textContent = user.phone || '0912 345 678';
  };

  // Expose ra window để có thể gọi từ bất kỳ đâu
  window.openEkycModal = openEkycModal;

  document.getElementById('closeEkycModalBtn')?.addEventListener('click', () => {
    if (ekycModal) ekycModal.style.display = 'none';
  });

  // --- BƯỚC 1: XỬ LÝ QUÉT CCCD ---
  const btnAutoFill = document.getElementById('btnAutoFillCCCD');
  const cccdFrontScanline = document.getElementById('cccdFrontScanline');
  const cccdBackScanline = document.getElementById('cccdBackScanline');
  const cccdFrontImg = document.getElementById('cccdFrontImg');
  const cccdBackImg = document.getElementById('cccdBackImg');
  const cccdFrontPlaceholder = document.getElementById('cccdFrontPlaceholder');
  const cccdBackPlaceholder = document.getElementById('cccdBackPlaceholder');
  const cccdOcrCard = document.getElementById('cccdOcrResultCard');
  const btnGotoStep2 = document.getElementById('btnGotoStep2');

  const triggerCccdSuccess = () => {
    const sampleFrontSvg = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="300" height="180" viewBox="0 0 300 180"><rect width="300" height="180" fill="%23dcfce7" rx="10"/><rect x="15" y="20" width="70" height="90" fill="%2386efac" rx="6"/><circle cx="50" cy="55" r="20" fill="%2315803d"/><rect x="100" y="30" width="160" height="14" fill="%2315803d" rx="3"/><rect x="100" y="55" width="130" height="10" fill="%2322c55e" rx="2"/><rect x="100" y="75" width="110" height="10" fill="%2322c55e" rx="2"/><rect x="20" y="130" width="260" height="30" fill="%23bbf7d0" rx="4"/></svg>';
    const sampleBackSvg = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="300" height="180" viewBox="0 0 300 180"><rect width="300" height="180" fill="%23e2e8f0" rx="10"/><rect x="30" y="30" width="50" height="40" fill="%23f59e0b" rx="4"/><line x1="20" y1="100" x2="280" y2="100" stroke="%23334155" stroke-width="18"/><line x1="20" y1="130" x2="280" y2="130" stroke="%23334155" stroke-width="18"/></svg>';

    if (cccdFrontImg) {
      cccdFrontImg.src = sampleFrontSvg;
      cccdFrontImg.style.display = 'block';
    }
    if (cccdBackImg) {
      cccdBackImg.src = sampleBackSvg;
      cccdBackImg.style.display = 'block';
    }
    if (cccdFrontPlaceholder) cccdFrontPlaceholder.style.display = 'none';
    if (cccdBackPlaceholder) cccdBackPlaceholder.style.display = 'none';

    if (cccdFrontScanline) cccdFrontScanline.style.display = 'block';
    if (cccdBackScanline) cccdBackScanline.style.display = 'block';

    setTimeout(() => {
      if (cccdFrontScanline) cccdFrontScanline.style.display = 'none';
      if (cccdBackScanline) cccdBackScanline.style.display = 'none';
      if (cccdOcrCard) cccdOcrCard.style.display = 'block';
      if (btnGotoStep2) btnGotoStep2.disabled = false;
      if (typeof showRideHubToast === 'function') {
        showRideHubToast('✓ Quét OCR CCCD thành công! Nhận dạng chip hợp lệ.');
      }
    }, 1000);
  };

  btnAutoFill?.addEventListener('click', triggerCccdSuccess);

  const handleFileInput = (input, img, placeholder) => {
    input?.addEventListener('change', (e) => {
      const file = e.target.files && e.target.files[0];
      if (file) {
        const reader = new FileReader();
        reader.onload = (evt) => {
          if (img) {
            img.src = evt.target.result;
            img.style.display = 'block';
          }
          if (placeholder) placeholder.style.display = 'none';
          triggerCccdSuccess();
        };
        reader.readAsDataURL(file);
      }
    });
  };
  handleFileInput(document.getElementById('cccdFrontInput'), cccdFrontImg, cccdFrontPlaceholder);
  handleFileInput(document.getElementById('cccdBackInput'), cccdBackImg, cccdBackPlaceholder);

  // --- BƯỚC 2: QUÉT KHUÔN MẶT SINH TRẮC HỌC & LIVENESS ---
  btnGotoStep2?.addEventListener('click', () => {
    setEkycStep(2);
  });

  const btnStartFaceScan = document.getElementById('btnStartFaceScan');
  const faceScanline = document.getElementById('faceScanline');
  const faceScanStatusText = document.getElementById('faceScanStatusText');
  const faceMatchBox = document.getElementById('faceMatchSuccessBox');
  const btnGotoStep3 = document.getElementById('btnGotoStep3');
  const liveCheck1 = document.getElementById('liveCheck1');
  const liveCheck2 = document.getElementById('liveCheck2');
  const liveCheck3 = document.getElementById('liveCheck3');

  btnStartFaceScan?.addEventListener('click', () => {
    btnStartFaceScan.disabled = true;
    if (faceScanline) faceScanline.style.display = 'block';
    if (faceScanStatusText) faceScanStatusText.textContent = 'Đang nhận diện liveness... Giữ thẳng khuôn mặt';

    setTimeout(() => {
      if (liveCheck1) {
        liveCheck1.textContent = '✓ Nhìn thẳng';
        liveCheck1.style.background = '#dcfce7';
        liveCheck1.style.color = '#15803d';
        liveCheck1.style.borderColor = '#22c55e';
      }
      if (faceScanStatusText) faceScanStatusText.textContent = 'Nhìn thẳng thành công... Hãy chớp mắt';
    }, 800);

    setTimeout(() => {
      if (liveCheck2) {
        liveCheck2.textContent = '✓ Chớp mắt';
        liveCheck2.style.background = '#dcfce7';
        liveCheck2.style.color = '#15803d';
        liveCheck2.style.borderColor = '#22c55e';
      }
      if (faceScanStatusText) faceScanStatusText.textContent = 'Tuyệt vời... Mỉm cười nhẹ';
    }, 1600);

    setTimeout(() => {
      if (liveCheck3) {
        liveCheck3.textContent = '✓ Mỉm cười';
        liveCheck3.style.background = '#dcfce7';
        liveCheck3.style.color = '#15803d';
        liveCheck3.style.borderColor = '#22c55e';
      }
      if (faceScanline) faceScanline.style.display = 'none';
      if (faceMatchBox) faceMatchBox.style.display = 'block';
      if (faceScanStatusText) faceScanStatusText.textContent = '✓ Sinh trắc học trùng khớp với CCCD (99.4%)';
      btnStartFaceScan.style.display = 'none';
      if (btnGotoStep3) btnGotoStep3.style.display = 'block';
    }, 2400);
  });

  // --- BƯỚC 3: PHÒNG CHỜ ĐỐI SOÁT AI RADAR ---
  const triggerConfetti = () => {
    const canvas = document.getElementById('ekycConfettiCanvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    canvas.width = canvas.parentElement.offsetWidth || 560;
    canvas.height = canvas.parentElement.offsetHeight || 500;
    const pieces = Array.from({ length: 45 }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * -canvas.height,
      r: 4 + Math.random() * 5,
      c: ['#22c55e', '#10b981', '#f59e0b', '#3b82f6', '#ec4899'][Math.floor(Math.random() * 5)],
      vy: 2 + Math.random() * 4,
      vx: (Math.random() - 0.5) * 3,
    }));
    let frames = 0;
    const anim = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      pieces.forEach((p) => {
        p.x += p.vx;
        p.y += p.vy;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = p.c;
        ctx.fill();
      });
      frames++;
      if (frames < 90) requestAnimationFrame(anim);
      else ctx.clearRect(0, 0, canvas.width, canvas.height);
    };
    anim();
  };

  const runAiRadarStep = () => {
    setEkycStep(3);
    const pBar = document.getElementById('aiProgressBar');
    const pText = document.getElementById('aiProgressText');
    const items = [
      document.getElementById('aiCheckItem1'),
      document.getElementById('aiCheckItem2'),
      document.getElementById('aiCheckItem3'),
      document.getElementById('aiCheckItem4'),
    ];

    const markCheckItem = (idx, pct, text) => {
      if (items[idx]) {
        const dot = items[idx].querySelector('.status-dot');
        if (dot) dot.classList.add('is-active');
        items[idx].style.color = '#15803d';
        items[idx].style.fontWeight = '600';
      }
      if (pBar) pBar.style.width = pct + '%';
      if (pText) pText.textContent = text;
    };

    setTimeout(() => markCheckItem(0, 35, 'Đã xác thực tính toàn vẹn chữ ký số Chip CCCD (35%)...'), 700);
    setTimeout(() => markCheckItem(1, 65, 'Đã đối soát dữ liệu nhân thân & GPLX quốc gia (65%)...'), 1400);
    setTimeout(() => markCheckItem(2, 85, 'Đã xác thực Face Liveness chống giả mạo (85%)...'), 2100);
    setTimeout(() => {
      markCheckItem(3, 100, '✓ Hoàn tất đối soát AI! Cấp hạn mức & Miễn cọc xe (100%)...');
      setTimeout(() => {
        setEkycStep(4);
        triggerConfetti();

        // TỰ ĐỘNG CHUYỂN HƯỚNG VÀO HỆ THỐNG SAU 2 GIÂY
        let autoSec = 2;
        const countdownEl = document.getElementById('ekycCountdownSec');
        if (countdownEl) countdownEl.textContent = String(autoSec);

        const autoTimer = setInterval(() => {
          autoSec--;
          if (countdownEl) countdownEl.textContent = String(autoSec);
          if (autoSec <= 0) {
            clearInterval(autoTimer);
            if (typeof showRideHubToast === 'function') {
              showRideHubToast('🎉 Chuyển hướng vào danh sách xe RideHub...');
            }
            window.location.href = '../vehicles.html';
          }
        }, 1000);

        document.getElementById('btnFinishAuth')?.addEventListener('click', () => {
          clearInterval(autoTimer);
          window.location.href = '../vehicles.html';
        }, { once: true });

      }, 800);
    }, 2800);
  };

  btnGotoStep3?.addEventListener('click', runAiRadarStep);

  // --- BƯỚC 4: HOÀN TẤT & KÍCH HOẠT TÀI KHOẢN ---
  document.getElementById('btnFinishAuth')?.addEventListener('click', () => {
    if (typeof showRideHubToast === 'function') {
      showRideHubToast('🎉 Kích hoạt tài khoản thành công! Đang chuyển đến trang xe...');
    }
    setTimeout(() => {
      window.location.href = '../vehicles.html';
    }, 500);
  });

})();
