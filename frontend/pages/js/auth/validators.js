/* ==========================================================================
   RideHub Client-Side Validators (js/auth/validators.js)
   ========================================================================== */

export function normalizeVNPhone(raw = '') {
  let digits = raw.replace(/\D/g, '');
  if (digits.startsWith('84') && digits.length >= 11) {
    digits = '0' + digits.slice(2);
  }
  return digits.slice(0, 10);
}

export function isValidVNPhone(raw = '') {
  const phone = normalizeVNPhone(raw);
  return /^0(3|5|7|8|9)\d{8}$/.test(phone);
}

export function isValidEmail(email = '') {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
}

export function getAge(dobStr) {
  if (!dobStr) return 0;
  const dob = new Date(dobStr);
  const now = new Date();
  let age = now.getFullYear() - dob.getFullYear();
  const m = now.getMonth() - dob.getMonth();
  if (m < 0 || (m === 0 && now.getDate() < dob.getDate())) age--;
  return age;
}

export function checkPasswordStrength(pass = '') {
  const checks = {
    len: pass.length >= 8,
    upper: /[A-Z]/.test(pass),
    lower: /[a-z]/.test(pass),
    num: /\d/.test(pass)
  };
  const score = Object.values(checks).filter(Boolean).length;
  return { checks, score, pct: (score / 4) * 100 };
}

export function validateImageFile(file) {
  return new Promise((resolve) => {
    if (!file) return resolve({ ok: false, error: 'Vui lòng chọn tệp ảnh.' });
    if (!['image/jpeg', 'image/png'].includes(file.type)) {
      return resolve({ ok: false, error: 'Chỉ hỗ trợ định dạng JPG hoặc PNG.' });
    }
    if (file.size > 5 * 1024 * 1024) {
      return resolve({ ok: false, error: 'Dung lượng ảnh tối đa là 5MB.' });
    }

    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      if (img.width < 320 || img.height < 200) {
        URL.revokeObjectURL(url);
        return resolve({ ok: false, error: 'Độ phân giải ảnh quá thấp (tối thiểu 320x200px).' });
      }
      // Estimate sharpness via Laplacian/gradient variance on downscaled canvas
      const c = document.createElement('canvas');
      const w = 96, h = 64;
      c.width = w; c.height = h;
      const ctx = c.getContext('2d');
      ctx.drawImage(img, 0, 0, w, h);
      const data = ctx.getImageData(0, 0, w, h).data;
      let diffSum = 0;
      for (let i = 0; i < data.length - 4; i += 4) {
        const g1 = (data[i] + data[i + 1] + data[i + 2]) / 3;
        const g2 = (data[i + 4] + data[i + 5] + data[i + 6]) / 3;
        diffSum += Math.abs(g1 - g2);
      }
      const avgDiff = diffSum / (w * h);
      const isBlurry = avgDiff < 3.2;
      resolve({ ok: true, url, width: img.width, height: img.height, isBlurry, sharpness: Math.round(avgDiff * 10) });
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      resolve({ ok: false, error: 'Không thể đọc tệp ảnh này.' });
    };
    img.src = url;
  });
}

