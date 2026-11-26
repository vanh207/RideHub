(function (global) {
  'use strict';

  const MODAL_ID = 'ridehubDateTimePicker';
  let activeInstance = null;

  function pad(value) {
    return String(value).padStart(2, '0');
  }

  function getDaysInMonth(year, month) {
    return new Date(year, month + 1, 0).getDate();
  }

  function getToday() {
    const now = new Date();
    return { year: now.getFullYear(), month: now.getMonth(), day: now.getDate() };
  }

  function getDefaultState() {
    const today = getToday();
    const start = new Date(today.year, today.month, today.day + 1);
    const monthDays = getDaysInMonth(start.getFullYear(), start.getMonth());
    const endDay = Math.min(start.getDate() + 3, monthDays);
    return {
      year: start.getFullYear(),
      month: start.getMonth(),
      mode: 'day',
      startDay: start.getDate(),
      endDay,
      pickingEnd: false,
      pickupHour: '21:00',
      returnHour: '11:00'
    };
  }

  function getDaysCount(state) {
    if (state.mode === 'hour') return 1;
    if (!state.endDay) return 1;
    return Math.max(1, state.endDay - state.startDay);
  }

  function getDurationText(state) {
    if (state.mode === 'hour') return '1 ngày (theo giờ)';
    if (!state.endDay) return 'Chưa chọn ngày trả';
    return `${getDaysCount(state)} ngày`;
  }

  function getRangeText(state) {
    const month = state.month + 1;
    if (state.mode === 'hour') {
      return `${state.startDay}/${month} ${state.pickupHour} → ${state.startDay}/${month} ${state.returnHour}`;
    }
    if (!state.endDay) {
      return `${state.startDay}/${month} ${state.pickupHour} → Chọn ngày trả`;
    }
    return `${state.startDay}/${month} ${state.pickupHour} → ${state.endDay}/${month} ${state.returnHour}`;
  }

  function parseRangeText(text, state) {
    const match = String(text || '').match(/(\d{1,2})\/(\d{1,2})\s+(\d{1,2}:\d{2})\s*(?:→|->|—|-)\s*(\d{1,2})\/(\d{1,2})\s+(\d{1,2}:\d{2})/);
    if (!match) return false;
    const startDay = Number(match[1]);
    const startMonth = Number(match[2]) - 1;
    const endDay = Number(match[4]);
    const endMonth = Number(match[5]) - 1;
    if (startMonth !== endMonth) return false;
    const monthDays = getDaysInMonth(state.year, startMonth);
    if (startDay < 1 || startDay > monthDays || endDay < startDay || endDay > monthDays) return false;
    state.month = startMonth;
    state.startDay = startDay;
    state.endDay = endDay;
    state.pickupHour = match[3];
    state.returnHour = match[6];
    state.pickingEnd = false;
    return true;
  }

  function isPastDay(state, day) {
    const today = getToday();
    if (state.year !== today.year) return state.year < today.year;
    if (state.month !== today.month) return state.month < today.month;
    return day < today.day;
  }

  function buildModalHtml() {
    return `
      <div id="${MODAL_ID}" class="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="rhDtTitle">
        <div class="modal-dialog dt-picker-modal">
          <div class="dt-picker-header">
            <h3 id="rhDtTitle">Chọn ngày &amp; giờ</h3>
            <button type="button" class="btn btn-soft dt-picker-close" data-rh-dt-close>Đóng</button>
          </div>
          <div class="dt-picker-body">
            <div class="dt-picker-title">Thời gian nhận/trả xe</div>
            <div class="dt-mode-pills">
              <button type="button" class="dt-mode-btn is-active" data-rh-dt-mode="day">Theo ngày</button>
              <button type="button" class="dt-mode-btn" data-rh-dt-mode="hour">Theo giờ</button>
              <button type="button" class="dt-mode-btn" data-rh-dt-mode="week">Theo tuần/tháng</button>
            </div>
            <div class="dt-calendar-card">
              <div class="dt-cal-header">
                <button type="button" id="rhDtPrevMonth" class="dt-cal-nav" aria-label="Tháng trước">&lt;</button>
                <span id="rhDtMonthTitle">Tháng 1 2026</span>
                <button type="button" id="rhDtNextMonth" class="dt-cal-nav" aria-label="Tháng sau">&gt;</button>
              </div>
              <div class="dt-weekdays">
                <span>T2</span><span>T3</span><span>T4</span><span>T5</span><span>T6</span><span>T7</span><span>CN</span>
              </div>
              <div id="rhDtDaysGrid" class="dt-days-grid"></div>
            </div>
            <div class="dt-summary-strip">
              <div class="dt-picker-summary-block">
                <div class="dt-picker-summary-icon">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="3"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>
                </div>
                <div>
                  <div class="dt-picker-label">Thời lượng</div>
                  <strong id="rhDtSummaryDur">3 ngày</strong>
                </div>
              </div>
              <div class="dt-picker-summary-right">
                <div class="dt-picker-label">Khung thời gian</div>
                <strong id="rhDtSummaryRange">12/11 21:00 → 15/11 11:00</strong>
              </div>
            </div>
            <div class="dt-picker-time-block">
              <div class="dt-picker-time-head">
                <label for="rhDtPickupTimeInput">Giờ nhận xe</label>
                <input id="rhDtPickupTimeInput" type="time" class="form-input dt-picker-time-input" value="21:00" />
              </div>
              <div id="rhDtPickupHours" class="dt-time-scroll"></div>
            </div>
            <div class="dt-picker-time-block">
              <div class="dt-picker-time-head">
                <label for="rhDtReturnTimeInput">Giờ trả xe</label>
                <input id="rhDtReturnTimeInput" type="time" class="form-input dt-picker-time-input" value="11:00" />
              </div>
              <div id="rhDtReturnHours" class="dt-time-scroll"></div>
            </div>
          </div>
          <div class="dt-picker-footer">
            <button id="rhDtDoneBtn" type="button" class="btn btn-primary btn-premium btn-shine dt-picker-done">Xác nhận ngày &amp; giờ</button>
          </div>
        </div>
      </div>
    `;
  }

  function mount(options) {
    if (activeInstance) return activeInstance;

    const settings = Object.assign({ triggerIds: [], onChange: function () {} }, options || {});
    const state = Object.assign(getDefaultState(), settings.initialState || {});
    const modal = document.getElementById(MODAL_ID) || (function () {
      const wrapper = document.createElement('div');
      wrapper.innerHTML = buildModalHtml().trim();
      const node = wrapper.firstElementChild;
      document.body.appendChild(node);
      return node;
    })();

    const byId = (id) => document.getElementById(id);

    function emitChange() {
      settings.onChange({
        rangeText: getRangeText(state),
        durationText: getDurationText(state),
        days: getDaysCount(state),
        state
      });
    }

    function renderCalendar() {
      const firstDay = new Date(state.year, state.month, 1).getDay();
      const offset = (firstDay + 6) % 7;
      const monthDays = getDaysInMonth(state.year, state.month);
      byId('rhDtMonthTitle').textContent = `Tháng ${state.month + 1} ${state.year}`;

      let html = '';
      for (let i = 0; i < offset; i++) html += '<span></span>';
      for (let day = 1; day <= monthDays; day++) {
        const isPast = isPastDay(state, day);
        const isStart = day === state.startDay;
        const hasEnd = state.mode !== 'hour' && state.endDay !== null;
        const isEnd = hasEnd && day === state.endDay;
        const inRange = hasEnd && day > state.startDay && day < state.endDay;
        const classes = [
          'dt-day-btn',
          isPast ? 'is-disabled' : '',
          isStart ? 'is-start' : '',
          isEnd ? 'is-end' : '',
          inRange ? 'is-in-range' : ''
        ].filter(Boolean).join(' ');
        html += `<button type="button" class="${classes}" ${isPast ? 'disabled' : ''} data-rh-dt-day="${day}">${day}</button>`;
      }

      const grid = byId('rhDtDaysGrid');
      grid.innerHTML = html;
      grid.querySelectorAll('[data-rh-dt-day]').forEach((button) => {
        button.addEventListener('click', () => {
          const day = Number(button.dataset.rhDtDay);
          if (state.mode === 'hour') {
            state.startDay = day;
            state.endDay = day;
            state.pickingEnd = false;
          } else if (!state.pickingEnd || day <= state.startDay) {
            state.startDay = day;
            state.endDay = null;
            state.pickingEnd = true;
          } else {
            state.endDay = day;
            state.pickingEnd = false;
          }
          renderCalendar();
          updateSummary();
        });
      });

      const minMonth = getToday().year * 12 + getToday().month;
      const currentMonth = state.year * 12 + state.month;
      byId('rhDtPrevMonth').disabled = currentMonth <= minMonth;
      byId('rhDtNextMonth').disabled = currentMonth >= minMonth + 11;
    }

    function renderHours() {
      const hours = Array.from({ length: 18 }, (_, index) => pad(index + 6) + ':00');
      const renderChips = (elementId, activeHour, key) => {
        const wrap = byId(elementId);
        wrap.innerHTML = hours.map((hour) => `<button type="button" class="dt-time-chip ${hour === activeHour ? 'is-active' : ''}" data-rh-dt-hour="${hour}">${hour}</button>`).join('');
        wrap.querySelectorAll('[data-rh-dt-hour]').forEach((button) => {
          button.addEventListener('click', () => {
            state[key] = button.dataset.rhDtHour;
            renderHours();
            updateSummary();
          });
        });
      };
      renderChips('rhDtPickupHours', state.pickupHour, 'pickupHour');
      renderChips('rhDtReturnHours', state.returnHour, 'returnHour');
      byId('rhDtPickupTimeInput').value = state.pickupHour;
      byId('rhDtReturnTimeInput').value = state.returnHour;
    }

    function updateSummary() {
      byId('rhDtSummaryDur').textContent = getDurationText(state);
      byId('rhDtSummaryRange').textContent = getRangeText(state);
      emitChange();
    }

    function renderAll() {
      renderCalendar();
      renderHours();
      updateSummary();
    }

    function open() {
      renderAll();
      modal.classList.add('is-open');
    }

    function close() {
      modal.classList.remove('is-open');
    }

    function setMode(mode) {
      state.mode = mode;
      document.querySelectorAll('[data-rh-dt-mode]').forEach((button) => {
        button.classList.toggle('is-active', button.dataset.rhDtMode === mode);
      });
      if (mode === 'hour') {
        state.endDay = state.startDay;
        state.pickingEnd = false;
      } else if (mode === 'week') {
        state.endDay = Math.min(getDaysInMonth(state.year, state.month), state.startDay + 7);
        state.pickingEnd = false;
      } else if (!state.endDay || state.endDay <= state.startDay) {
        state.endDay = null;
        state.pickingEnd = true;
      }
      renderAll();
    }

    document.querySelectorAll('[data-rh-dt-mode]').forEach((button) => {
      button.addEventListener('click', () => setMode(button.dataset.rhDtMode));
    });

    byId('rhDtPrevMonth').addEventListener('click', () => {
      const minMonth = getToday().year * 12 + getToday().month;
      if (state.year * 12 + state.month <= minMonth) return;
      state.month -= 1;
      if (state.month < 0) {
        state.month = 11;
        state.year -= 1;
      }
      state.startDay = Math.min(state.startDay, getDaysInMonth(state.year, state.month));
      if (state.endDay) state.endDay = Math.min(state.endDay, getDaysInMonth(state.year, state.month));
      renderAll();
    });

    byId('rhDtNextMonth').addEventListener('click', () => {
      const minMonth = getToday().year * 12 + getToday().month;
      if (state.year * 12 + state.month >= minMonth + 11) return;
      state.month += 1;
      if (state.month > 11) {
        state.month = 0;
        state.year += 1;
      }
      state.startDay = Math.min(state.startDay, getDaysInMonth(state.year, state.month));
      if (state.endDay) state.endDay = Math.min(state.endDay, getDaysInMonth(state.year, state.month));
      renderAll();
    });

    byId('rhDtPickupTimeInput').addEventListener('input', (event) => {
      if (!event.target.value) return;
      state.pickupHour = event.target.value;
      renderHours();
      updateSummary();
    });

    byId('rhDtReturnTimeInput').addEventListener('input', (event) => {
      if (!event.target.value) return;
      state.returnHour = event.target.value;
      renderHours();
      updateSummary();
    });

    byId('rhDtDoneBtn').addEventListener('click', () => {
      close();
      emitChange();
    });

    modal.querySelectorAll('[data-rh-dt-close]').forEach((button) => {
      button.addEventListener('click', close);
    });

    modal.addEventListener('click', (event) => {
      if (event.target === modal) close();
    });

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && modal.classList.contains('is-open')) close();
    });

    settings.triggerIds.forEach((id) => {
      const trigger = document.getElementById(id);
      if (trigger) trigger.addEventListener('click', open);
    });

    activeInstance = {
      open,
      close,
      getState: () => state,
      getDays: () => getDaysCount(state),
      getRangeText: () => getRangeText(state),
      getDurationText: () => getDurationText(state),
      syncFromText: (text) => {
        if (!parseRangeText(text, state)) return false;
        renderAll();
        return true;
      }
    };

    renderAll();
    return activeInstance;
  }

  global.RideHubDateTimePicker = { mount };
})(window);
