/* ==========================================================================
   RideHub UI & Atmospheric Effects Engine (effects.js)
   Attribute-driven: data-reveal, data-tilt, data-magnetic, data-countup, etc.
   ========================================================================== */

(function (global) {
  'use strict';

  const Effects = {
    isReduced() {
      return document.documentElement.classList.contains('reduced-effects') ||
        window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    },

    /* ----------------------------------------------------------------------
       1. Settings "Giảm hiệu ứng" & Mobile Auto-Optimization
       ---------------------------------------------------------------------- */
    initSettings() {
      const saved = localStorage.getItem('ridehub_reduced_effects');
      if (saved === 'true') {
        document.documentElement.classList.add('reduced-effects');
      }
      const toggle = document.getElementById('reduceEffectsToggle');
      if (toggle) {
        toggle.checked = document.documentElement.classList.contains('reduced-effects');
        toggle.addEventListener('change', () => {
          document.documentElement.classList.toggle('reduced-effects', toggle.checked);
          localStorage.setItem('ridehub_reduced_effects', String(toggle.checked));
          this.showToast(toggle.checked ? 'Đã bật chế độ Giảm hiệu ứng' : 'Đã bật hiệu ứng đầy đủ');
        });
      }
    },

    /* ----------------------------------------------------------------------
       2. Ambient Canvas Particles (Leaves, Bubbles, Light Motes <= 40)
       ---------------------------------------------------------------------- */
    initAmbientParticles() {
      const canvas = document.getElementById('ambientParticles');
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      const isMobile = window.innerWidth < 768 || (navigator.hardwareConcurrency && navigator.hardwareConcurrency <= 4);
      const count = isMobile ? 16 : 36; // Max 40

      const resize = () => {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
      };
      resize();
      window.addEventListener('resize', resize, { passive: true });

      const palette = ['rgba(74, 222, 128, 0.35)', 'rgba(217, 249, 157, 0.45)', 'rgba(255, 255, 255, 0.55)'];
      const particles = Array.from({ length: count }, () => ({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        r: Math.random() * 4 + 2,
        vy: -(Math.random() * 0.45 + 0.2),
        vx: (Math.random() - 0.5) * 0.3,
        kind: Math.random() > 0.65 ? 'leaf' : 'orb',
        color: palette[Math.floor(Math.random() * palette.length)],
        angle: Math.random() * Math.PI * 2
      }));

      const draw = () => {
        if (!document.hidden && !this.isReduced()) {
          ctx.clearRect(0, 0, canvas.width, canvas.height);
          particles.forEach((p) => {
            p.y += p.vy;
            p.x += p.vx + Math.sin(p.angle) * 0.2;
            p.angle += 0.02;
            if (p.y < -15) {
              p.y = canvas.height + 15;
              p.x = Math.random() * canvas.width;
            }
            ctx.save();
            ctx.translate(p.x, p.y);
            ctx.fillStyle = p.color;
            if (p.kind === 'leaf') {
              ctx.rotate(p.angle);
              ctx.beginPath();
              ctx.ellipse(0, 0, p.r * 1.4, p.r * 0.7, 0, 0, Math.PI * 2);
              ctx.fill();
            } else {
              ctx.beginPath();
              ctx.arc(0, 0, p.r, 0, Math.PI * 2);
              ctx.fill();
            }
            ctx.restore();
          });
        } else if (this.isReduced()) {
          ctx.clearRect(0, 0, canvas.width, canvas.height);
        }
        requestAnimationFrame(draw);
      };
      requestAnimationFrame(draw);
    },

    /* ----------------------------------------------------------------------
       3. Mouse-Parallax Topo Grid
       ---------------------------------------------------------------------- */
    initTopoParallax() {
      const grids = document.querySelectorAll('.topo-grid-bg');
      if (!grids.length) return;
      window.addEventListener('mousemove', (e) => {
        if (this.isReduced()) return;
        const dx = ((e.clientX / window.innerWidth) - 0.5) * 18;
        const dy = ((e.clientY / window.innerHeight) - 0.5) * 18;
        grids.forEach((g) => {
          g.style.setProperty('--topo-x', `${dx}px`);
          g.style.setProperty('--topo-y', `${dy}px`);
        });
      }, { passive: true });
    },

    /* ----------------------------------------------------------------------
       4. Scroll Progress Bar + Smart Navbar + Sticky Storytelling
       ---------------------------------------------------------------------- */
    initScrollUI() {
      const bar = document.getElementById('scrollProgressBar');
      const navbar = document.getElementById('mainNavbar');
      let lastY = window.scrollY;
      let lastTime = performance.now();

      window.addEventListener('scroll', () => {
        const y = window.scrollY;
        const max = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
        if (bar) bar.style.width = `${Math.min(100, (y / max) * 100)}%`;

        if (navbar) {
          navbar.classList.toggle('is-scrolled', y > 32);
          const now = performance.now();
          const dt = Math.max(1, now - lastTime);
          const velocity = (y - lastY) / dt;
          if (y > 180 && velocity > 0.45) {
            navbar.classList.add('is-hidden');
          } else if (velocity < -0.15 || y < 120) {
            navbar.classList.remove('is-hidden');
          }
          lastY = y;
          lastTime = now;
        }
      }, { passive: true });

      // Sticky storytelling steps
      const stepCards = document.querySelectorAll('.story-step-card');
      const storyTitle = document.getElementById('storyStageTitle');
      const storyDesc = document.getElementById('storyStageDesc');
      const storyCar = document.getElementById('storyCar');
      if (stepCards.length) {
        const storyObs = new IntersectionObserver((entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              stepCards.forEach((c) => c.classList.remove('is-active'));
              entry.target.classList.add('is-active');
              const idx = parseInt(entry.target.dataset.step || '0', 10);
              if (storyTitle) storyTitle.textContent = entry.target.dataset.title || '';
              if (storyDesc) storyDesc.textContent = entry.target.dataset.desc || '';
              if (storyCar) storyCar.style.left = `${idx * 26}%`;
            }
          });
        }, { threshold: 0.55 });
        stepCards.forEach((c) => storyObs.observe(c));
      }
    },

    /* ----------------------------------------------------------------------
       5. IntersectionObserver Reveals, Text Mask, Count-Up & Curve Dividers
       ---------------------------------------------------------------------- */
    initObservers() {
      // Split text-mask headings into word spans
      document.querySelectorAll('[data-reveal="text-mask"]').forEach((el) => {
        const words = el.textContent.trim().split(/\s+/);
        el.innerHTML = words.map((w, i) => `<span class="mask-word"><span style="--word-i:${i}">${w}</span></span>`).join(' ');
      });

      const revealObs = new IntersectionObserver((entries, obs) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-visible');
            if (entry.target.hasAttribute('data-countup')) {
              this.animateCountUp(entry.target);
            }
            obs.unobserve(entry.target);
          }
        });
      }, { threshold: 0.14 });

      document.querySelectorAll('[data-reveal], [data-countup], .section-curve-divider').forEach((el) => {
        revealObs.observe(el);
      });

      // Pause offscreen decorative animations
      const pauseObs = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          entry.target.classList.toggle('anim-paused', !entry.isIntersecting);
        });
      }, { threshold: 0.01 });
      document.querySelectorAll('[data-pause-offscreen]').forEach((el) => pauseObs.observe(el));
    },

    animateCountUp(el) {
      const target = parseFloat(el.dataset.countup || '0');
      const suffix = el.dataset.suffix || '';
      if (this.isReduced()) {
        el.textContent = target.toLocaleString('vi-VN') + suffix;
        return;
      }
      const duration = 1200;
      const start = performance.now();
      const easeOutExpo = (t) => (t === 1 ? 1 : 1 - Math.pow(2, -10 * t));

      const frame = (now) => {
        const p = Math.min(1, (now - start) / duration);
        const val = Math.round(target * easeOutExpo(p));
        el.textContent = val.toLocaleString('vi-VN') + suffix;
        if (p < 1) requestAnimationFrame(frame);
      };
      requestAnimationFrame(frame);
    },

    /* ----------------------------------------------------------------------
       6. Magnetic, Spotlight, Ripple (No 3D Tilt)
       ---------------------------------------------------------------------- */
    initPointerEffects() {

      // Spotlight cards
      document.querySelectorAll('.spotlight-card').forEach((card) => {
        card.addEventListener('mousemove', (e) => {
          const r = card.getBoundingClientRect();
          card.style.setProperty('--mx', `${e.clientX - r.left}px`);
          card.style.setProperty('--my', `${e.clientY - r.top}px`);
        });
      });

      // Magnetic hover
      document.querySelectorAll('[data-magnetic]').forEach((btn) => {
        btn.addEventListener('mousemove', (e) => {
          if (this.isReduced()) return;
          const r = btn.getBoundingClientRect();
          const dx = (e.clientX - (r.left + r.width / 2)) * 0.22;
          const dy = (e.clientY - (r.top + r.height / 2)) * 0.22;
          btn.style.transform = `translate3d(${dx}px, ${dy}px, 0)`;
        });
        btn.addEventListener('mouseleave', () => {
          btn.style.transform = 'translate3d(0, 0, 0)';
        });
      });

      // Click Ripple
      document.querySelectorAll('.btn-premium').forEach((btn) => {
        btn.addEventListener('click', (e) => {
          if (this.isReduced()) return;
          const r = btn.getBoundingClientRect();
          const circle = document.createElement('span');
          circle.className = 'ripple-circle';
          const size = Math.max(r.width, r.height);
          circle.style.width = circle.style.height = size + 'px';
          circle.style.left = (e.clientX - r.left - size / 2) + 'px';
          circle.style.top = (e.clientY - r.top - size / 2) + 'px';
          btn.appendChild(circle);
          setTimeout(() => circle.remove(), 560);
        });
      });
    },

    /* ----------------------------------------------------------------------
       7. Forms, OTP, Dropzone, Fuel Slider, Tabs, Toast, Modals
       ---------------------------------------------------------------------- */
    initFormsAndControls() {
      // Floating input validation
      const phoneInput = document.getElementById('phoneInput');
      const phoneField = document.getElementById('phoneField');
      if (phoneInput && phoneField) {
        phoneInput.addEventListener('blur', () => {
          const ok = /^0\d{9}$/.test(phoneInput.value.trim());
          phoneField.classList.toggle('is-valid', ok);
          phoneField.classList.toggle('is-error', !ok && phoneInput.value.trim().length > 0);
          if (!ok && phoneInput.value.trim().length > 0) {
            phoneField.classList.remove('field-shake');
            void phoneField.offsetWidth;
            phoneField.classList.add('field-shake');
          }
        });
      }

      // 6-digit OTP boxes
      const otpBoxes = Array.from(document.querySelectorAll('.otp-box'));
      otpBoxes.forEach((box, idx) => {
        box.style.setProperty('--otp-i', idx);
        box.addEventListener('input', () => {
          box.value = box.value.replace(/\D/g, '').slice(0, 1);
          if (box.value) {
            box.classList.remove('is-pop');
            void box.offsetWidth;
            box.classList.add('is-pop');
            if (idx < otpBoxes.length - 1) otpBoxes[idx + 1].focus();
          }
          if (otpBoxes.every((b) => b.value.length === 1)) {
            otpBoxes.forEach((b) => {
              b.classList.remove('is-success-wave');
              void b.offsetWidth;
              b.classList.add('is-success-wave');
            });
            this.showToast('Xác thực OTP thành công!');
          }
        });
        box.addEventListener('keydown', (e) => {
          if (e.key === 'Backspace' && !box.value && idx > 0) otpBoxes[idx - 1].focus();
        });
      });

      // Fuel tank slider
      const fuelRange = document.getElementById('fuelRange');
      const fuelFill = document.getElementById('fuelTankFill');
      const fuelLabel = document.getElementById('fuelPercentLabel');
      if (fuelRange && fuelFill) {
        fuelRange.addEventListener('input', () => {
          fuelFill.style.height = fuelRange.value + '%';
          if (fuelLabel) fuelLabel.textContent = fuelRange.value + '%';
        });
      }

      // Drag & drop zone
      const dropzone = document.getElementById('licenseDropzone');
      const dropPreview = document.getElementById('dropzonePreview');
      if (dropzone && dropPreview) {
        ['dragenter', 'dragover'].forEach((ev) => {
          dropzone.addEventListener(ev, (e) => {
            e.preventDefault();
            dropzone.classList.add('is-dragover');
          });
        });
        ['dragleave', 'drop'].forEach((ev) => {
          dropzone.addEventListener(ev, (e) => {
            e.preventDefault();
            dropzone.classList.remove('is-dragover');
          });
        });
        const handleDropSuccess = (name) => {
          dropPreview.innerHTML = `<div class="dropped-thumb" style="padding:8px 12px;background:var(--green-100);border-radius:10px;font-size:13px;font-weight:700;color:var(--green-700);">Đã tải lên: ${name}</div>`;
        };
        dropzone.addEventListener('drop', (e) => {
          const file = e.dataTransfer?.files?.[0];
          handleDropSuccess(file ? file.name : 'GPLX_mat_truoc.jpg');
        });
        dropzone.addEventListener('click', () => handleDropSuccess('GPLX_xac_minh.png'));
      }

      // Shared-element Tabs
      const tabBar = document.getElementById('studioTabs');
      if (tabBar) {
        const indicator = tabBar.querySelector('.tab-indicator');
        const btns = tabBar.querySelectorAll('.tab-btn');
        const panels = document.querySelectorAll('[data-tab-panel]');
        const moveIndicator = (btn) => {
          if (!indicator) return;
          indicator.style.width = btn.offsetWidth + 'px';
          indicator.style.transform = `translateX(${btn.offsetLeft - 4}px)`;
        };
        btns.forEach((btn) => {
          btn.addEventListener('click', () => {
            btns.forEach((b) => b.classList.remove('is-active'));
            btn.classList.add('is-active');
            moveIndicator(btn);
            panels.forEach((p) => {
              p.hidden = p.dataset.tabPanel !== btn.dataset.tab;
            });
          });
        });
        const active = tabBar.querySelector('.tab-btn.is-active');
        if (active) setTimeout(() => moveIndicator(active), 50);
      }

      // Modals (Settings, 404, Booking Success)
      document.querySelectorAll('[data-open-modal]').forEach((trigger) => {
        trigger.addEventListener('click', () => {
          const id = trigger.dataset.openModal;
          const modal = document.getElementById(id);
          if (!modal) return;
          modal.classList.add('is-open');
          if (id === 'successModal' && global.VehicleAnim) {
            const c = document.getElementById('successConfetti');
            setTimeout(() => global.VehicleAnim.launchConfetti(c), 180);
          }
        });
      });

      document.querySelectorAll('.modal-backdrop').forEach((backdrop) => {
        backdrop.addEventListener('click', (e) => {
          if (e.target === backdrop || e.target.closest('[data-close-modal]')) {
            backdrop.classList.remove('is-open');
          }
        });
      });
    },

    showToast(message, isError = false) {
      const container = document.getElementById('toastContainer');
      if (!container) return;
      const item = document.createElement('div');
      item.className = 'toast-item' + (isError ? ' is-error' : '');
      item.innerHTML = `<div style="font-weight:700;font-size:13px;">${message}</div><div class="toast-bar"></div>`;
      container.appendChild(item);
      setTimeout(() => item.remove(), 3550);
    },

    /* ----------------------------------------------------------------------
       8. Hold Timer (30 min SVG ring + Odometer), QR Dissolve, Table FLIP
       ---------------------------------------------------------------------- */
    initHoldTimerAndQR() {
      const ring = document.getElementById('holdTimerRing');
      const odoWrap = document.getElementById('holdOdometer');
      const wheel = document.getElementById('holdTimerWheel');
      const rushBtn = document.getElementById('simulateLowTimerBtn');
      if (ring && odoWrap) {
        let seconds = 29 * 60 + 58;
        const total = 30 * 60;
        const circumference = 2 * Math.PI * 24;
        ring.style.strokeDasharray = circumference;

        const renderOdo = (sec) => {
          const m = String(Math.floor(sec / 60)).padStart(2, '0');
          const s = String(sec % 60).padStart(2, '0');
          odoWrap.textContent = `${m}:${s}`;
          const pct = sec / total;
          ring.style.strokeDashoffset = circumference * (1 - pct);
          if (sec < 300) {
            ring.style.stroke = 'var(--coral-soft)';
            if (wheel) wheel.style.animationDuration = '0.25s';
          } else if (sec < 900) {
            ring.style.stroke = '#eab308';
          } else {
            ring.style.stroke = 'var(--green-500)';
          }
        };
        renderOdo(seconds);
        setInterval(() => {
          if (seconds > 0) seconds--;
          renderOdo(seconds);
        }, 1000);

        if (rushBtn) {
          rushBtn.addEventListener('click', () => {
            seconds = 245;
            renderOdo(seconds);
            this.showToast('Cảnh báo: Thời gian giữ chỗ còn dưới 5 phút!', true);
          });
        }
      }

      // QR Payment dissolve into checkmark
      const qrPayBtn = document.getElementById('simulateQrPayBtn');
      const qrBox = document.getElementById('qrBox');
      const qrSuccess = document.getElementById('qrSuccess');
      if (qrPayBtn && qrBox && qrSuccess) {
        qrPayBtn.addEventListener('click', () => {
          qrBox.style.transition = 'opacity 0.45s var(--ease-out), transform 0.45s var(--ease-out), filter 0.45s var(--ease-out)';
          qrBox.style.opacity = '0';
          qrBox.style.transform = 'scale(0.82)';
          qrBox.style.filter = 'blur(8px)';
          setTimeout(() => {
            qrBox.hidden = true;
            qrSuccess.hidden = false;
            this.showToast('Thanh toán QR thành công!');
          }, 460);
        });
      }

      // Status badge flip demo
      document.querySelectorAll('[data-flip-badge]').forEach((badge) => {
        const states = [
          { cls: 'status-badge--available', text: 'Sẵn sàng' },
          { cls: 'status-badge--booked', text: 'Đã đặt' },
          { cls: 'status-badge--transit', text: 'Đang thuê' },
          { cls: 'status-badge--cleaning', text: 'Đang vệ sinh' }
        ];
        let i = 0;
        badge.addEventListener('click', () => {
          i = (i + 1) % states.length;
          badge.classList.remove('is-flipping');
          void badge.offsetWidth;
          badge.classList.add('is-flipping');
          setTimeout(() => {
            states.forEach((s) => badge.classList.remove(s.cls));
            badge.classList.add(states[i].cls);
            const lbl = badge.querySelector('.badge-text');
            if (lbl) lbl.textContent = states[i].text;
          }, 220);
        });
      });

      // Table FLIP sort
      const sortBtn = document.getElementById('sortFleetTableBtn');
      const tbody = document.getElementById('fleetTableBody');
      if (sortBtn && tbody) {
        let asc = true;
        sortBtn.addEventListener('click', () => {
          const rows = Array.from(tbody.querySelectorAll('tr'));
          const firstRects = new Map(rows.map((r) => [r, r.getBoundingClientRect()]));
          rows.sort((a, b) => {
            const pa = parseInt(a.dataset.price || '0', 10);
            const pb = parseInt(b.dataset.price || '0', 10);
            return asc ? pa - pb : pb - pa;
          });
          asc = !asc;
          rows.forEach((r) => tbody.appendChild(r));
          rows.forEach((r) => {
            const last = r.getBoundingClientRect();
            const dy = firstRects.get(r).top - last.top;
            if (dy) {
              r.style.transform = `translateY(${dy}px)`;
              r.style.transition = 'none';
              requestAnimationFrame(() => {
                r.style.transition = 'transform 0.45s var(--ease-out)';
                r.style.transform = 'translateY(0)';
              });
            }
          });
        });
      }
    },

    /* ----------------------------------------------------------------------
       9. Pure SVG Dashboard Charts, E-Signature, Before/After Slider, Carousel
       ---------------------------------------------------------------------- */
    initInteractiveWidgets() {
      // Dashboard chart tooltip
      const tooltip = document.getElementById('chartTooltip');
      if (tooltip) {
        document.querySelectorAll('[data-chart-tip]').forEach((el) => {
          el.addEventListener('mouseenter', () => {
            tooltip.textContent = el.dataset.chartTip;
            tooltip.style.opacity = '1';
          });
          el.addEventListener('mousemove', (e) => {
            tooltip.style.left = (e.clientX + 12) + 'px';
            tooltip.style.top = (e.clientY - 28) + 'px';
          });
          el.addEventListener('mouseleave', () => {
            tooltip.style.opacity = '0';
          });
        });
      }

      // E-Signature smooth Bezier canvas
      const sigCanvas = document.getElementById('signatureCanvas');
      const clearSig = document.getElementById('clearSigBtn');
      if (sigCanvas) {
        const ctx = sigCanvas.getContext('2d');
        ctx.strokeStyle = '#16a34a';
        ctx.lineWidth = 2.6;
        ctx.lineCap = 'round';
        ctx.shadowColor = 'rgba(74, 222, 128, 0.35)';
        ctx.shadowBlur = 4;
        let drawing = false, pts = [];

        const getPos = (e) => {
          const r = sigCanvas.getBoundingClientRect();
          const clientX = e.touches ? e.touches[0].clientX : e.clientX;
          const clientY = e.touches ? e.touches[0].clientY : e.clientY;
          return { x: clientX - r.left, y: clientY - r.top };
        };

        const start = (e) => { drawing = true; pts = [getPos(e)]; };
        const move = (e) => {
          if (!drawing) return;
          e.preventDefault();
          pts.push(getPos(e));
          if (pts.length >= 3) {
            const lastTwo = pts.slice(-3);
            const mid1 = { x: (lastTwo[0].x + lastTwo[1].x) / 2, y: (lastTwo[0].y + lastTwo[1].y) / 2 };
            const mid2 = { x: (lastTwo[1].x + lastTwo[2].x) / 2, y: (lastTwo[1].y + lastTwo[2].y) / 2 };
            ctx.beginPath();
            ctx.moveTo(mid1.x, mid1.y);
            ctx.quadraticCurveTo(lastTwo[1].x, lastTwo[1].y, mid2.x, mid2.y);
            ctx.stroke();
          }
        };
        const end = () => { drawing = false; pts = []; };

        sigCanvas.addEventListener('mousedown', start);
        sigCanvas.addEventListener('mousemove', move);
        window.addEventListener('mouseup', end);
        sigCanvas.addEventListener('touchstart', start, { passive: true });
        sigCanvas.addEventListener('touchmove', move, { passive: false });
        window.addEventListener('touchend', end);
        if (clearSig) clearSig.addEventListener('click', () => ctx.clearRect(0, 0, sigCanvas.width, sigCanvas.height));
      }

      // Before / After Slider
      const compareBox = document.getElementById('compareBox');
      const compareAfter = document.getElementById('compareAfter');
      const compareHandle = document.getElementById('compareHandle');
      if (compareBox && compareAfter && compareHandle) {
        let dragging = false;
        const updateSplit = (clientX) => {
          const r = compareBox.getBoundingClientRect();
          const pct = Math.min(95, Math.max(5, ((clientX - r.left) / r.width) * 100));
          compareAfter.style.clipPath = `inset(0 ${100 - pct}% 0 0)`;
          compareHandle.style.left = pct + '%';
        };
        compareBox.addEventListener('mousedown', (e) => { dragging = true; updateSplit(e.clientX); });
        window.addEventListener('mousemove', (e) => { if (dragging) updateSplit(e.clientX); });
        window.addEventListener('mouseup', () => { dragging = false; });
        compareBox.addEventListener('touchmove', (e) => { updateSplit(e.touches[0].clientX); }, { passive: true });
      }

      // Reviews Carousel with inertial drag
      const viewport = document.getElementById('reviewsViewport');
      const track = document.getElementById('reviewsTrack');
      if (viewport && track) {
        let offset = 0, isDown = false, startX = 0, vel = 0;
        const cards = Array.from(track.children);
        const updateCenter = () => {
          const vpCenter = viewport.getBoundingClientRect().left + viewport.clientWidth / 2;
          cards.forEach((c) => {
            const cr = c.getBoundingClientRect();
            const dist = Math.abs(vpCenter - (cr.left + cr.width / 2));
            c.classList.toggle('is-center', dist < 180);
          });
        };
        const clampOffset = (val) => Math.min(40, Math.max(-(track.scrollWidth - viewport.clientWidth + 40), val));
        viewport.addEventListener('mousedown', (e) => { isDown = true; startX = e.clientX - offset; });
        window.addEventListener('mousemove', (e) => {
          if (!isDown) return;
          const next = clampOffset(e.clientX - startX);
          vel = next - offset;
          offset = next;
          track.style.transform = `translate3d(${offset}px, 0, 0)`;
          updateCenter();
        });
        window.addEventListener('mouseup', () => {
          if (!isDown) return;
          isDown = false;
          const glide = () => {
            if (Math.abs(vel) < 0.3) return;
            vel *= 0.92;
            offset = clampOffset(offset + vel);
            track.style.transform = `translate3d(${offset}px, 0, 0)`;
            updateCenter();
            requestAnimationFrame(glide);
          };
          requestAnimationFrame(glide);
        });
        updateCenter();
      }
    },

    /* ----------------------------------------------------------------------
       10. Chatbot AI, Mobile Drawer & View Transitions
       ---------------------------------------------------------------------- */
    initChatbotAndNav() {
      const fab = document.getElementById('chatFab');
      const win = document.getElementById('chatWindow');
      const closeBtn = document.getElementById('chatCloseBtn');
      const msgBox = document.getElementById('chatMessages');
      const input = document.getElementById('chatInput');
      const sendBtn = document.getElementById('chatSendBtn');

      if (fab && win) {
        fab.addEventListener('click', () => {
          win.classList.toggle('is-open');
          fab.classList.remove('has-unread');
        });
        if (closeBtn) closeBtn.addEventListener('click', () => win.classList.remove('is-open'));
      }

      const appendBotReply = (text, withStamp = false) => {
        if (!msgBox) return;
        const typing = document.createElement('div');
        typing.className = 'chat-msg chat-msg--bot';
        typing.innerHTML = '<span class="typing-dot"></span> <span class="typing-dot"></span> <span class="typing-dot"></span>';
        msgBox.appendChild(typing);
        msgBox.scrollTop = msgBox.scrollHeight;

        setTimeout(() => {
          typing.remove();
          const msg = document.createElement('div');
          msg.className = 'chat-msg chat-msg--bot';
          msgBox.appendChild(msg);
          let i = 0;
          const typeLoop = () => {
            i += 2;
            msg.textContent = text.slice(0, i);
            msgBox.scrollTop = msgBox.scrollHeight;
            if (i < text.length) {
              setTimeout(typeLoop, 18);
            } else if (withStamp) {
              const stamp = document.createElement('div');
              stamp.className = 'stamp-badge';
              stamp.style.cssText = 'margin-top:8px;padding:6px 10px;border:1.5px dashed var(--green-500);border-radius:8px;background:var(--green-50);font-weight:800;color:var(--green-700);font-size:12px;';
              stamp.textContent = 'MÃ HỖ TRỢ: #RH-2026-889';
              msg.appendChild(stamp);
            }
          };
          typeLoop();
        }, 650);
      };

      document.querySelectorAll('.chat-quick-pill').forEach((pill, idx) => {
        pill.style.setProperty('--pill-i', idx);
        pill.addEventListener('click', () => {
          if (!msgBox) return;
          const u = document.createElement('div');
          u.className = 'chat-msg chat-msg--user';
          u.textContent = pill.textContent;
          msgBox.appendChild(u);
          const isHandoff = pill.dataset.handoff === 'true';
          appendBotReply(pill.dataset.reply || 'RideHub sẵn sàng hỗ trợ bạn chọn xe phù hợp nhất!', isHandoff);
        });
      });

      if (sendBtn && input) {
        const send = () => {
          const val = input.value.trim();
          if (!val) return;
          const u = document.createElement('div');
          u.className = 'chat-msg chat-msg--user';
          u.textContent = val;
          msgBox.appendChild(u);
          input.value = '';
          appendBotReply('Cảm ơn bạn! Xe máy điện & ô tô xanh gần bạn nhất hiện đã sẵn sàng giao trong 15 phút.');
        };
        sendBtn.addEventListener('click', send);
        input.addEventListener('keydown', (e) => { if (e.key === 'Enter') send(); });
      }

      // Mobile Hamburger & Drawer
      const burger = document.getElementById('hamburgerBtn');
      const drawer = document.getElementById('mobileDrawer');
      if (burger && drawer) {
        burger.addEventListener('click', () => {
          burger.classList.toggle('is-open');
          drawer.classList.toggle('is-open');
        });
        drawer.querySelectorAll('a').forEach((a, i) => {
          a.style.setProperty('--drawer-i', i);
          a.addEventListener('click', () => {
            burger.classList.remove('is-open');
            drawer.classList.remove('is-open');
          });
        });
      }

      // View Transitions API navigation helper
      document.querySelectorAll('a[data-vt-link]').forEach((link) => {
        link.addEventListener('click', (e) => {
          const targetId = link.getAttribute('href');
          if (!targetId || !targetId.startsWith('#')) return;
          const target = document.querySelector(targetId);
          if (!target) return;
          e.preventDefault();
          const scrollFn = () => target.scrollIntoView({ behavior: 'smooth' });
          if (document.startViewTransition && !this.isReduced()) {
            document.startViewTransition(scrollFn);
          } else {
            target.classList.remove('page-transition-fallback');
            void target.offsetWidth;
            target.classList.add('page-transition-fallback');
            scrollFn();
          }
        });
      });
    },

    initAll() {
      this.initSettings();
      this.initAmbientParticles();
      this.initTopoParallax();
      this.initScrollUI();
      this.initObservers();
      this.initPointerEffects();
      this.initFormsAndControls();
      this.initHoldTimerAndQR();
      this.initInteractiveWidgets();
      this.initChatbotAndNav();
    }
  };

  global.Effects = Effects;
  global.showRideHubToast = (msg, err) => Effects.showToast(msg, err);

  document.addEventListener('DOMContentLoaded', () => {
    Effects.initAll();
    if (global.VehicleAnim) global.VehicleAnim.initAll();
  });
})(window);

