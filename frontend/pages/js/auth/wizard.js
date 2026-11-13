/* ==========================================================================
   RideHub Multi-Step Wizard Controller (js/auth/wizard.js)
   ========================================================================== */

export function createWizard({
  trackEl,
  panels,
  draftKey,
  onStepChange
}) {
  let current = 0;
  const total = panels.length;

  const railFill = trackEl?.querySelector('.wizard-rail-fill');
  const vehicle = trackEl?.querySelector('.wizard-vehicle');
  const tags = trackEl ? Array.from(trackEl.querySelectorAll('.wizard-step-tag')) : [];

  const updateUI = () => {
    const pct = total > 1 ? (current / (total - 1)) * 100 : 100;
    if (railFill) railFill.style.width = `${pct}%`;
    if (vehicle) vehicle.style.left = `${pct}%`;

    tags.forEach((tag, idx) => {
      tag.classList.toggle('is-active', idx === current);
      tag.classList.toggle('is-done', idx < current);
    });

    panels.forEach((p, idx) => {
      p.hidden = idx !== current;
      if (idx === current) {
        p.classList.remove('auth-view-pane');
        void p.offsetWidth;
        p.classList.add('auth-view-pane');
      }
    });

    const roadStage = document.querySelector('.auth-road-stage');
    if (roadStage) {
      roadStage.classList.add('is-accelerating');
      setTimeout(() => roadStage.classList.remove('is-accelerating'), 550);
    }

    if (onStepChange) onStepChange(current);
  };

  const saveDraft = (data) => {
    if (!draftKey) return;
    localStorage.setItem(draftKey, JSON.stringify({ step: current, data }));
  };

  const loadDraft = () => {
    if (!draftKey) return null;
    try {
      const raw = localStorage.getItem(draftKey);
      return raw ? JSON.parse(raw) : null;
    } catch (_) {
      return null;
    }
  };

  const clearDraft = () => {
    if (draftKey) localStorage.removeItem(draftKey);
  };

  updateUI();

  return {
    getStep: () => current,
    goTo: (idx) => {
      current = Math.max(0, Math.min(total - 1, idx));
      updateUI();
    },
    next: () => {
      if (current < total - 1) {
        current++;
        updateUI();
      }
    },
    prev: () => {
      if (current > 0) {
        current--;
        updateUI();
      }
    },
    saveDraft,
    loadDraft,
    clearDraft
  };
}

