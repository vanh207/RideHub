/* ==========================================================================
   RideHub Vehicle Animation Engine (vehicle-anim.js)
   Handles all road scenes, SVG vehicles, wheelies, honks, timeline & confetti
   ========================================================================== */

(function (global) {
  'use strict';

  const VehicleAnim = {
    vehicles: [],
    rafId: null,
    lastTime: 0,
    scrollRatio: 0,
    isHeroVisible: true,
    isTabVisible: true,

    isReduced() {
      return document.documentElement.classList.contains('reduced-effects') ||
        window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    },

    /* ----------------------------------------------------------------------
       1. SVG Templates (Motorbike & Car)
       ---------------------------------------------------------------------- */
    createMotoSVG(color = '#22c55e', accent = '#d9f99d') {
      return `
        <svg class="vehicle-inner" viewBox="0 0 110 64" width="100%" height="100%" aria-hidden="true">
          <ellipse class="vehicle-shadow" cx="55" cy="59" rx="38" ry="4.5" fill="#132a1c" opacity="0.2"/>
          <path class="wind-streak" d="M2 22 H24 M6 30 H20" stroke="#ffffff" stroke-width="2" stroke-linecap="round"/>
          <g class="vehicle-body-bounce">
            <!-- Exhaust pipe -->
            <rect x="14" y="39" width="18" height="5" rx="2.5" fill="#6b8a76"/>
            <!-- Frame & Seat -->
            <path d="M26 36 C30 24, 46 22, 58 26 L74 18 L82 20 L74 36 Z" fill="${color}"/>
            <path d="M32 25 C40 21, 52 21, 58 25 L48 29 L30 29 Z" fill="#132a1c"/>
            <path d="M56 26 L68 20 L73 25 L62 34 Z" fill="${accent}"/>
            <!-- Handlebar & Headlight -->
            <path d="M71 18 L66 11 M75 18 L83 22" stroke="#132a1c" stroke-width="3" stroke-linecap="round"/>
            <circle cx="84" cy="24" r="4.5" fill="#fef08a"/>
            <polygon class="headlight-beam" points="88,22 109,14 109,34 88,26" fill="#fef08a"/>
          </g>
          <!-- Rear Wheel -->
          <g transform="translate(27,45)">
            <g class="wheel-spin">
              <circle cx="0" cy="0" r="12" fill="#132a1c"/>
              <circle cx="0" cy="0" r="6.5" fill="#e6f7ec"/>
              <line x1="-6" y1="0" x2="6" y2="0" stroke="#22c55e" stroke-width="1.8"/>
              <line x1="0" y1="-6" x2="0" y2="6" stroke="#22c55e" stroke-width="1.8"/>
            </g>
          </g>
          <!-- Front Wheel -->
          <g transform="translate(81,45)">
            <g class="wheel-spin">
              <circle cx="0" cy="0" r="12" fill="#132a1c"/>
              <circle cx="0" cy="0" r="6.5" fill="#e6f7ec"/>
              <line x1="-6" y1="0" x2="6" y2="0" stroke="#22c55e" stroke-width="1.8"/>
              <line x1="0" y1="-6" x2="0" y2="6" stroke="#22c55e" stroke-width="1.8"/>
            </g>
          </g>
        </svg>`;
    },

    createCarSVG(color = '#16a34a', accent = '#ecfccb') {
      return `
        <svg class="vehicle-inner" viewBox="0 0 150 68" width="100%" height="100%" aria-hidden="true">
          <ellipse class="vehicle-shadow" cx="75" cy="62" rx="58" ry="5" fill="#132a1c" opacity="0.22"/>
          <path class="wind-streak" d="M2 24 H24 M8 32 H26" stroke="#ffffff" stroke-width="2" stroke-linecap="round"/>
          <g class="vehicle-body-bounce">
            <!-- Body -->
            <path d="M16 42 C16 32, 22 28, 34 27 L48 14 C52 10, 62 9, 86 9 C100 9, 108 15, 116 26 L132 29 C139 30, 142 35, 142 42 L140 48 L16 48 Z" fill="${color}"/>
            <!-- Windows -->
            <path d="M51 15 L84 15 C95 15, 102 19, 108 26 L42 26 Z" fill="${accent}"/>
            <line x1="76" y1="15" x2="76" y2="26" stroke="${color}" stroke-width="3"/>
            <!-- Headlight -->
            <rect x="134" y="32" width="7" height="6" rx="2" fill="#fef08a"/>
            <polygon class="headlight-beam" points="141,31 150,24 150,44 141,38" fill="#fef08a"/>
          </g>
          <!-- Rear Wheel -->
          <g transform="translate(38,49)">
            <g class="wheel-spin">
              <circle cx="0" cy="0" r="11" fill="#132a1c"/>
              <circle cx="0" cy="0" r="5.5" fill="#dcfce7"/>
              <line x1="-5" y1="0" x2="5" y2="0" stroke="#16a34a" stroke-width="1.8"/>
              <line x1="0" y1="-5" x2="0" y2="5" stroke="#16a34a" stroke-width="1.8"/>
            </g>
          </g>
          <!-- Front Wheel -->
          <g transform="translate(112,49)">
            <g class="wheel-spin">
              <circle cx="0" cy="0" r="11" fill="#132a1c"/>
              <circle cx="0" cy="0" r="5.5" fill="#dcfce7"/>
              <line x1="-5" y1="0" x2="5" y2="0" stroke="#16a34a" stroke-width="1.8"/>
              <line x1="0" y1="-5" x2="0" y2="5" stroke="#16a34a" stroke-width="1.8"/>
            </g>
          </g>
        </svg>`;
    },

    /* ----------------------------------------------------------------------
       2. Page Loader
       ---------------------------------------------------------------------- */
    initLoader() {
      const loader = document.getElementById('pageLoader');
      if (!loader) return;
      const delay = this.isReduced() ? 120 : 1280;
      setTimeout(() => {
        loader.classList.add('is-revealing');
        setTimeout(() => loader.classList.add('is-done'), 880);
      }, delay);
    },

    /* ----------------------------------------------------------------------
       3. Hero Road Vehicles, Honk, Wheelie & Scroll Parallax
       ---------------------------------------------------------------------- */
    spawnExhaust(vehicleEl) {
      if (this.isReduced()) return;
      const puff = document.createElement('span');
      puff.className = 'exhaust-puff';
      puff.style.cssText = 'position:absolute;left:-4px;bottom:14px;width:9px;height:9px;border-radius:50%;background:rgba(255,255,255,0.75);';
      vehicleEl.appendChild(puff);
      setTimeout(() => puff.remove(), 900);
    },

    triggerBeep(vehicleEl, text = 'Beep!') {
      const existing = vehicleEl.querySelector('.beep-bubble');
      if (existing) existing.remove();
      const bubble = document.createElement('span');
      bubble.className = 'beep-bubble';
      bubble.textContent = text;
      vehicleEl.appendChild(bubble);
      setTimeout(() => bubble.remove(), 780);
    },

    initHeroScene() {
      const track = document.getElementById('heroVehiclesTrack');
      const hero = document.getElementById('heroScene');
      if (!track || !hero) return;

      const specs = [
        { type: 'moto', x: 60, y: 12, speed: 92, width: 92, color: '#22c55e', accent: '#d9f99d' },
        { type: 'car', x: 340, y: 42, speed: 128, width: 132, color: '#16a34a', accent: '#ecfccb' },
        { type: 'moto', x: 680, y: 18, speed: 148, width: 88, color: '#4ade80', accent: '#ffffff' },
        { type: 'car', x: 960, y: 46, speed: 102, width: 126, color: '#15803d', accent: '#d9f99d' }
      ];

      this.vehicles = specs.map((spec, idx) => {
        const el = document.createElement('div');
        el.className = 'road-vehicle';
        el.style.width = spec.width + 'px';
        el.style.bottom = spec.y + 'px';
        el.innerHTML = spec.type === 'moto'
          ? this.createMotoSVG(spec.color, spec.accent)
          : this.createCarSVG(spec.color, spec.accent);

        const state = { ...spec, el, boost: 1, exhaustTick: idx * 0.3 };

        el.addEventListener('mouseenter', () => {
          state.boost = 1.85;
          this.triggerBeep(el, 'Beep!');
        });
        el.addEventListener('mouseleave', () => {
          state.boost = 1;
        });
        el.addEventListener('click', () => {
          el.classList.remove('is-wheelie');
          void el.offsetWidth;
          el.classList.add('is-wheelie');
          this.triggerBeep(el, spec.type === 'moto' ? 'Vút!' : 'Bíp!');
        });

        track.appendChild(el);
        return state;
      });

      // Time of day switcher
      document.querySelectorAll('.time-btn').forEach((btn) => {
        btn.addEventListener('click', () => {
          document.querySelectorAll('.time-btn').forEach((b) => b.classList.remove('is-active'));
          btn.classList.add('is-active');
          hero.setAttribute('data-time', btn.dataset.time);
        });
      });

      // Scroll-linked hero parallax & vehicles shrinking toward horizon
      const parallaxLayers = hero.querySelectorAll('[data-parallax]');
      const onScroll = () => {
        const rect = hero.getBoundingClientRect();
        const ratio = Math.min(1, Math.max(0, -rect.top / Math.max(1, hero.offsetHeight)));
        this.scrollRatio = ratio;
        parallaxLayers.forEach((layer) => {
          const factor = parseFloat(layer.dataset.parallax || '0.2');
          layer.style.transform = `translate3d(0, ${ratio * factor * 110}px, 0)`;
        });
      };
      window.addEventListener('scroll', onScroll, { passive: true });

      // Pause when hero is off-screen
      const io = new IntersectionObserver((entries) => {
        this.isHeroVisible = entries[0].isIntersecting;
      }, { threshold: 0.05 });
      io.observe(hero);

      document.addEventListener('visibilitychange', () => {
        this.isTabVisible = !document.hidden;
      });

      const tick = (now) => {
        if (!this.lastTime) this.lastTime = now;
        const dt = Math.min(0.05, (now - this.lastTime) / 1000);
        this.lastTime = now;

        if (this.isHeroVisible && this.isTabVisible && !this.isReduced()) {
          const trackW = track.clientWidth || window.innerWidth;
          const horizonScale = 1 - this.scrollRatio * 0.34;
          const horizonLift = -this.scrollRatio * 26;

          this.vehicles.forEach((v) => {
            v.x += v.speed * v.boost * dt;
            if (v.x > trackW + 160) v.x = -160;
            v.el.style.transform = `translate3d(${v.x}px, ${horizonLift}px, 0) scale(${horizonScale})`;

            v.exhaustTick += dt * v.boost;
            if (v.exhaustTick > 0.55) {
              v.exhaustTick = 0;
              this.spawnExhaust(v.el);
            }
          });
        }
        this.rafId = requestAnimationFrame(tick);
      };
      this.rafId = requestAnimationFrame(tick);
    },

    /* ----------------------------------------------------------------------
       4. Stepper Vehicle + Ripple Ring + Checkmark
       ---------------------------------------------------------------------- */
    initStepper() {
      const track = document.getElementById('bookingStepper');
      if (!track) return;
      const nodes = Array.from(track.querySelectorAll('.step-node'));
      const car = document.getElementById('stepperVehicle');
      const fill = document.getElementById('stepperFill');

      const setStep = (stepIdx) => {
        const pct = (stepIdx / (nodes.length - 1)) * 100;
        if (fill) fill.style.width = pct + '%';
        if (car) {
          const maxLeft = Math.max(0, track.clientWidth - 68);
          car.style.left = (12 + (maxLeft * pct) / 100) + 'px';
          car.querySelectorAll('.wheel-spin').forEach((w) => w.classList.add('wheel-spin--fast'));
          setTimeout(() => {
            car.querySelectorAll('.wheel-spin').forEach((w) => w.classList.remove('wheel-spin--fast'));
          }, 600);
        }

        nodes.forEach((node, idx) => {
          const wasDone = node.classList.contains('is-done');
          node.classList.toggle('is-done', idx < stepIdx);
          node.classList.toggle('is-current', idx === stepIdx);
          node.classList.toggle('step-done', idx < stepIdx);
          if (idx < stepIdx && !wasDone) {
            const ring = document.createElement('span');
            ring.className = 'step-ripple';
            node.querySelector('.step-circle').appendChild(ring);
            setTimeout(() => ring.remove(), 820);
          }
        });
      };

      nodes.forEach((node, idx) => {
        node.addEventListener('click', () => setStep(idx));
      });
      setStep(1);
      this.setStepperStep = setStep;
    },

    /* ----------------------------------------------------------------------
       5. Curved SVG Order Timeline (getPointAtLength)
       ---------------------------------------------------------------------- */
    initCurvedTimeline() {
      const pathBg = document.getElementById('timelinePathBg');
      const pathLit = document.getElementById('timelinePathLit');
      const marker = document.getElementById('timelineVehicleMarker');
      const slider = document.getElementById('timelineProgressRange');
      const label = document.getElementById('timelineStatusLabel');
      if (!pathBg || !pathLit || !marker) return;

      const totalLen = pathBg.getTotalLength();
      pathLit.style.strokeDasharray = totalLen;

      const stages = ['Đã xác nhận', 'Tài xế đang giao xe', 'Đang sử dụng', 'Đang trả xe', 'Hoàn tất'];

      const updateAt = (pct) => {
        const len = (pct / 100) * totalLen;
        pathLit.style.strokeDashoffset = totalLen - len;
        const pt = pathBg.getPointAtLength(len);
        const ptAhead = pathBg.getPointAtLength(Math.min(totalLen, len + 2));
        const angle = Math.atan2(ptAhead.y - pt.y, ptAhead.x - pt.x) * (180 / Math.PI);
        marker.setAttribute('transform', `translate(${pt.x}, ${pt.y}) rotate(${angle})`);
        if (label) {
          const idx = Math.min(stages.length - 1, Math.floor((pct / 100) * stages.length));
          label.textContent = `${stages[idx]} (${Math.round(pct)}%)`;
        }
      };

      if (slider) {
        slider.addEventListener('input', (e) => updateAt(parseFloat(e.target.value)));
      }
      updateAt(42);
    },

    /* ----------------------------------------------------------------------
       6. Vehicle Type Morph Toggle (Xe máy <-> Ô tô)
       ---------------------------------------------------------------------- */
    initVehicleMorphToggle() {
      const toggle = document.getElementById('vehicleTypeToggle');
      const morphPath = document.getElementById('morphVehiclePath');
      if (!toggle || !morphPath) return;

      const motoD = 'M8 22 C11 14, 18 14, 24 16 L30 11 L35 13 L31 22 Z';
      const carD = 'M4 22 C4 16, 8 14, 14 14 L19 9 L31 9 L36 14 L41 16 L41 22 Z';

      toggle.querySelectorAll('.vehicle-toggle-btn').forEach((btn) => {
        btn.addEventListener('click', () => {
          const mode = btn.dataset.mode;
          toggle.setAttribute('data-mode', mode);
          morphPath.setAttribute('d', mode === 'car' ? carD : motoD);
          if (typeof global.showRideHubToast === 'function') {
            global.showRideHubToast(mode === 'car' ? 'Đã chuyển sang chế độ Ô tô' : 'Đã chuyển sang chế độ Xe máy');
          }
        });
      });
    },

    /* ----------------------------------------------------------------------
       7. Footer Vehicle + Search Loader + Booking Success Confetti
       ---------------------------------------------------------------------- */
    initFooterVehicle() {
      const footerCar = document.getElementById('footerCruisingCar');
      if (!footerCar) return;
      let x = -100;
      footerCar.addEventListener('click', () => this.triggerBeep(footerCar, 'Beep!'));

      const step = () => {
        if (this.isTabVisible && !this.isReduced()) {
          const w = footerCar.parentElement.clientWidth || window.innerWidth;
          x += 1.4;
          if (x > w + 120) x = -120;
          footerCar.style.transform = `translate3d(${x}px, 0, 0)`;
        }
        requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    },

    launchConfetti(canvas) {
      if (!canvas || this.isReduced()) return;
      const ctx = canvas.getContext('2d');
      canvas.width = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
      const colors = ['#22c55e', '#4ade80', '#bef264', '#d9f99d', '#ffffff'];
      const pieces = Array.from({ length: 65 }, () => ({
        x: canvas.width / 2,
        y: canvas.height * 0.45,
        vx: (Math.random() - 0.5) * 11,
        vy: -Math.random() * 9 - 2,
        size: Math.random() * 7 + 4,
        rot: Math.random() * 360,
        vr: (Math.random() - 0.5) * 10,
        color: colors[Math.floor(Math.random() * colors.length)],
        life: 1
      }));

      const draw = () => {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        let alive = false;
        pieces.forEach((p) => {
          if (p.life <= 0) return;
          alive = true;
          p.x += p.vx;
          p.y += p.vy;
          p.vy += 0.28;
          p.rot += p.vr;
          p.life -= 0.012;
          ctx.save();
          ctx.globalAlpha = Math.max(0, p.life);
          ctx.translate(p.x, p.y);
          ctx.rotate((p.rot * Math.PI) / 180);
          ctx.fillStyle = p.color;
          ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size * 0.6);
          ctx.restore();
        });
        if (alive) requestAnimationFrame(draw);
      };
      requestAnimationFrame(draw);
    },

    initAll() {
      this.initLoader();
      this.initHeroScene();
      this.initStepper();
      this.initCurvedTimeline();
      this.initVehicleMorphToggle();
      this.initFooterVehicle();
    }
  };

  global.VehicleAnim = VehicleAnim;
})(window);
