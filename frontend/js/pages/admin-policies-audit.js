/* ==========================================================================
   ADMIN POLICIES & AUDIT LOG CONTROLLER
   - Quản lý cấu hình chính sách hệ thống (/api/admin/policies)
   - Tra cứu bảng nhật ký Audit có lọc theo thời gian & người thao tác (/api/admin/audit-logs)
   ========================================================================== */
(function () {
  'use strict';

  const CATEGORY_META = {
    DEPOSIT: { title: 'Chính sách Đặt cọc (BR-03)', badge: 'Đặt cọc' },
    CANCELLATION: { title: 'Chính sách Hủy đơn & Hoàn tiền', badge: 'Hủy & Hoàn tiền' },
    BOOKING: { title: 'Chính sách Thuê xe & Thời hạn', badge: 'Đặt xe' },
    SECURITY: { title: 'Bảo mật & Giới hạn đăng nhập', badge: 'Bảo mật' },
  };

  let currentPage = 1;
  const pageSize = 15;
  let totalPages = 1;
  let loadedAuditItems = [];

  const getApiBase = () => {
    if (typeof window.CONFIG !== 'undefined' && window.CONFIG.API_BASE_URL) {
      return window.CONFIG.API_BASE_URL.replace(/\/+$/, '');
    }
    return 'http://127.0.0.1:8000/api';
  };

  const getAuthToken = () => {
    const cookieMatch =
      document.cookie.match(/(?:^|;\s*)ridehub_token=([^;]+)/) ||
      document.cookie.match(/(?:^|;\s*)access_token=([^;]+)/) ||
      document.cookie.match(/(?:^|;\s*)token=([^;]+)/);
    if (cookieMatch) return decodeURIComponent(cookieMatch[1]);
    return (
      localStorage.getItem('ridehub_token') ||
      localStorage.getItem('token') ||
      localStorage.getItem('ridehub_auth_token') ||
      ''
    );
  };

  const escapeHtml = (val) => {
    if (val === null || val === undefined) return '';
    return String(val)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  };

  const formatDateTime = (iso) => {
    if (!iso) return '—';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString('vi-VN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  const apiFetch = async (path, options = {}) => {
    const token = getAuthToken();
    const headers = {
      Accept: 'application/json',
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    };
    const res = await fetch(`${getApiBase()}${path}`, {
      ...options,
      headers,
      credentials: 'include',
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const err = new Error(data.detail || data.message || `HTTP ${res.status}`);
      err.status = res.status;
      throw err;
    }
    return data;
  };

  const showAuthBanner = (show, customMsg) => {
    const banner = document.getElementById('adminAuthBanner');
    if (!banner) return;
    banner.classList.toggle('is-visible', show);
    if (customMsg) {
      const msgEl = document.getElementById('adminAuthBannerMsg');
      if (msgEl) msgEl.textContent = customMsg;
    }
  };

  // --------------------------------------------------------------------------
  // 1. TAB SWITCHING (CHUYỂN TẠI CHỖ KHÔNG NHẢY TRANG)
  // --------------------------------------------------------------------------
  const activateTab = (target) => {
    document.querySelectorAll('.admin-tab-btn[data-admin-tab]').forEach((b) => {
      const active = b.getAttribute('data-admin-tab') === target;
      b.classList.toggle('is-active', active);
      b.setAttribute('aria-selected', active ? 'true' : 'false');
    });
    document.querySelectorAll('.admin-panel').forEach((panel) => {
      panel.classList.toggle('is-active', panel.id === `panel-${target}`);
    });
    if (target === 'audit') {
      loadAuditStats();
      loadAuditLogs(1);
    }
  };

  const initTabs = () => {
    document.querySelectorAll('[data-admin-tab]').forEach((el) => {
      el.addEventListener('click', (e) => {
        if (el.tagName === 'A') e.preventDefault();
        const target = el.getAttribute('data-admin-tab');
        if (!target) return;
        history.replaceState(null, '', `#${target}`);
        activateTab(target);
      });
    });

    if (window.location.hash === '#audit') {
      activateTab('audit');
    }
  };

  // --------------------------------------------------------------------------
  // 2. POLICIES MANAGEMENT
  // --------------------------------------------------------------------------
  const renderPolicies = (items) => {
    const container = document.getElementById('policyContainer');
    if (!container) return;

    if (!items || !items.length) {
      container.innerHTML = '<div class="surface-card">Chưa có cấu hình chính sách nào.</div>';
      return;
    }

    const grouped = {};
    items.forEach((item) => {
      const cat = item.category || 'GENERAL';
      if (!grouped[cat]) grouped[cat] = [];
      grouped[cat].push(item);
    });

    container.innerHTML = Object.entries(grouped)
      .map(([cat, list]) => {
        const meta = CATEGORY_META[cat] || { title: cat, badge: cat };
        const fieldsHtml = list
          .map(
            (p) => `
          <div class="form-group">
            <label class="form-label" for="pol_${escapeHtml(p.policy_key)}">${escapeHtml(p.label)}</label>
            <div class="policy-input-row">
              <input
                id="pol_${escapeHtml(p.policy_key)}"
                name="${escapeHtml(p.policy_key)}"
                data-policy-key="${escapeHtml(p.policy_key)}"
                type="${p.value_type === 'number' || p.value_type === 'percent' ? 'number' : 'text'}"
                class="form-control"
                value="${escapeHtml(p.value)}"
                min="0"
                ${p.value_type === 'percent' ? 'max="100"' : ''}
                required
              />
              ${p.unit ? `<span class="policy-unit">${escapeHtml(p.unit)}</span>` : ''}
            </div>
            ${p.description ? `<div class="form-hint">${escapeHtml(p.description)}</div>` : ''}
          </div>
        `
          )
          .join('');

        return `
          <article class="surface-card">
            <div class="policy-card-head">
              <h2 class="policy-card-title">${escapeHtml(meta.title)}</h2>
              <span class="policy-badge">${escapeHtml(meta.badge)}</span>
            </div>
            ${fieldsHtml}
          </article>
        `;
      })
      .join('');
  };

  const loadPolicies = async () => {
    const container = document.getElementById('policyContainer');
    if (window.RideHubUI?.Loader && container) {
      window.RideHubUI.Loader.showInline(container, 'Đang tải cấu hình chính sách...');
    }
    try {
      const res = await apiFetch('/admin/policies');
      showAuthBanner(false);
      renderPolicies(res.data || []);
    } catch (err) {
      if (err.status === 401 || err.status === 403) {
        showAuthBanner(true, 'Bạn cần đăng nhập bằng tài khoản Quản trị viên (Admin) để xem và chỉnh sửa chính sách.');
      }
      if (container) {
        container.innerHTML = `<div class="surface-card" style="color:#b91c1c;">Không thể tải cấu hình chính sách: ${escapeHtml(err.message)}</div>`;
      }
    }
  };

  const initPolicyForm = () => {
    const form = document.getElementById('policyConfigForm');
    const saveBtn = document.getElementById('btnSavePolicies');
    const reloadBtn = document.getElementById('btnReloadPolicies');

    reloadBtn?.addEventListener('click', () => loadPolicies());

    form?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const inputs = form.querySelectorAll('[data-policy-key]');
      const updates = Array.from(inputs).map((input) => ({
        policy_key: input.getAttribute('data-policy-key'),
        value: String(input.value).trim(),
      }));

      if (!updates.length) return;
      window.RideHubUI?.Form?.setLoading(saveBtn, true, 'Đang lưu...');
      try {
        const res = await apiFetch('/admin/policies', {
          method: 'PUT',
          body: JSON.stringify({ updates }),
        });
        window.RideHubUI?.Toast?.show(res.message || 'Đã lưu cấu hình chính sách!', 'success');
      } catch (err) {
        window.RideHubUI?.Toast?.show(err.message || 'Lưu chính sách thất bại.', 'error');
      } finally {
        window.RideHubUI?.Form?.setLoading(saveBtn, false);
      }
    });
  };

  // --------------------------------------------------------------------------
  // 3. AUDIT LOGS TABLE & FILTERS (THỜI GIAN + NGƯỜI THAO TÁC)
  // --------------------------------------------------------------------------
  const loadAuditStats = async () => {
    try {
      const stats = await apiFetch('/admin/audit-logs/stats/summary');
      document.getElementById('statTotalLogs').textContent = stats.total_logs ?? 0;
      document.getElementById('statSuccessLogs').textContent = stats.total_success ?? 0;
      document.getElementById('statFailedLogs').textContent = stats.total_failed ?? 0;
      document.getElementById('statReviewLogs').textContent = stats.by_category?.reviews ?? 0;
      document.getElementById('statStatusLogs').textContent = stats.by_category?.status_changes ?? 0;
      document.getElementById('statRefundLogs').textContent = stats.by_category?.refunds ?? 0;
    } catch (_) {
      // Bỏ qua nếu chưa đăng nhập Admin
    }
  };

  const buildAuditQuery = (page) => {
    const params = new URLSearchParams();
    params.set('page', String(page));
    params.set('size', String(pageSize));

    const search = document.getElementById('auditSearchInput')?.value?.trim();
    const userId = document.getElementById('auditUserIdInput')?.value?.trim();
    const action = document.getElementById('auditActionSelect')?.value;
    const status = document.getElementById('auditStatusSelect')?.value;
    const fromDate = document.getElementById('auditFromDate')?.value;
    const toDate = document.getElementById('auditToDate')?.value;

    if (search) params.set('search', search);
    if (userId) params.set('user_id', userId);
    if (action) params.set('action', action);
    if (status) params.set('status', status);
    if (fromDate) params.set('from_date', new Date(fromDate).toISOString());
    if (toDate) params.set('to_date', new Date(toDate).toISOString());

    return params.toString();
  };

  const renderAuditRows = (items) => {
    const tbody = document.getElementById('auditTableBody');
    if (!tbody) return;
    loadedAuditItems = items || [];

    if (!loadedAuditItems.length) {
      window.RideHubUI?.Table?.renderEmpty(tbody, 'Không có bản ghi nhật ký Audit nào khớp bộ lọc.', 7);
      return;
    }

    tbody.innerHTML = loadedAuditItems
      .map((item) => {
        const actor = item.user_email
          ? `<strong>${escapeHtml(item.user_email)}</strong><br><small style="color:var(--text-muted);">ID: ${escapeHtml(item.user_id ?? '—')} • ${escapeHtml(item.user_role || 'guest')}</small>`
          : `<span>ID: ${escapeHtml(item.user_id ?? '—')} (${escapeHtml(item.user_role || 'anonymous')})</span>`;
        const statusCls = item.status === 'SUCCESS' ? 'status-pill--success' : 'status-pill--failed';

        return `
          <tr>
            <td>#${escapeHtml(item.id)}</td>
            <td>
              <div>${escapeHtml(formatDateTime(item.created_at))}</div>
              <small style="color:var(--text-muted);">${item.execution_time_ms != null ? `${item.execution_time_ms} ms` : ''}</small>
            </td>
            <td>${actor}</td>
            <td>
              <span class="action-tag">${escapeHtml(item.action)}</span>
              <div style="font-size:12.5px; color:var(--text-muted); margin-top:4px;">${escapeHtml(item.description || item.endpoint)}</div>
            </td>
            <td><code>${escapeHtml(item.resource_type)}${item.resource_id ? `:${escapeHtml(item.resource_id)}` : ''}</code></td>
            <td><span class="status-pill ${statusCls}">${escapeHtml(item.status)} (${escapeHtml(item.status_code)})</span></td>
            <td>
              <button type="button" class="btn btn-soft btn-xs" data-view-audit="${escapeHtml(item.id)}">Xem</button>
            </td>
          </tr>
        `;
      })
      .join('');
  };

  const loadAuditLogs = async (page = 1) => {
    const tbody = document.getElementById('auditTableBody');
    if (window.RideHubUI?.Loader && tbody) {
      window.RideHubUI.Loader.showInline(tbody, 'Đang tải nhật ký Audit...');
    }
    try {
      const qs = buildAuditQuery(page);
      const data = await apiFetch(`/admin/audit-logs?${qs}`);
      showAuthBanner(false);
      currentPage = data.page || 1;
      totalPages = Math.max(1, data.pages || 1);
      renderAuditRows(data.items || []);

      document.getElementById('auditPaginationInfo').textContent = `Tổng ${data.total ?? 0} bản ghi`;
      document.getElementById('auditPageNumber').textContent = `Trang ${currentPage} / ${totalPages}`;
      document.getElementById('btnPrevAuditPage').disabled = currentPage <= 1;
      document.getElementById('btnNextAuditPage').disabled = currentPage >= totalPages;
    } catch (err) {
      if (err.status === 401 || err.status === 403) {
        showAuthBanner(true);
      }
      window.RideHubUI?.Table?.renderEmpty(tbody, `Không thể tải nhật ký Audit: ${err.message}`, 7);
    }
  };

  const toLocalInputValue = (d) => {
    const pad = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  };

  const initAuditFilters = () => {
    const filterForm = document.getElementById('auditFilterForm');
    const resetBtn = document.getElementById('btnResetAuditFilter');
    const fromEl = document.getElementById('auditFromDate');
    const toEl = document.getElementById('auditToDate');

    filterForm?.addEventListener('submit', (e) => {
      e.preventDefault();
      loadAuditLogs(1);
    });

    resetBtn?.addEventListener('click', () => {
      filterForm.reset();
      loadAuditLogs(1);
    });

    document.querySelectorAll('[data-date-preset]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const preset = btn.getAttribute('data-date-preset');
        const now = new Date();
        if (preset === 'all') {
          if (fromEl) fromEl.value = '';
          if (toEl) toEl.value = '';
        } else {
          const start = new Date(now);
          if (preset === 'today') {
            start.setHours(0, 0, 0, 0);
          } else if (preset === '7d') {
            start.setDate(start.getDate() - 7);
          } else if (preset === '30d') {
            start.setDate(start.getDate() - 30);
          }
          if (fromEl) fromEl.value = toLocalInputValue(start);
          if (toEl) toEl.value = toLocalInputValue(now);
        }
        loadAuditLogs(1);
      });
    });

    document.getElementById('btnPrevAuditPage')?.addEventListener('click', () => {
      if (currentPage > 1) loadAuditLogs(currentPage - 1);
    });
    document.getElementById('btnNextAuditPage')?.addEventListener('click', () => {
      if (currentPage < totalPages) loadAuditLogs(currentPage + 1);
    });

    document.getElementById('auditTableBody')?.addEventListener('click', (e) => {
      const btn = e.target.closest('[data-view-audit]');
      if (!btn) return;
      const id = Number(btn.getAttribute('data-view-audit'));
      const record = loadedAuditItems.find((x) => x.id === id);
      if (!record) return;

      const body = document.getElementById('auditModalBody');
      if (body) {
        body.innerHTML = `
          <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:14px; font-size:13.5px;">
            <div><strong>Mã bản ghi:</strong> #${escapeHtml(record.id)}</div>
            <div><strong>Thời điểm:</strong> ${escapeHtml(formatDateTime(record.created_at))} (${escapeHtml(record.execution_time_ms ?? 0)} ms)</div>
            <div><strong>Người thao tác:</strong> ${escapeHtml(record.user_email || '—')} (ID: ${escapeHtml(record.user_id ?? '—')})</div>
            <div><strong>Vai trò:</strong> ${escapeHtml(record.user_role || '—')}</div>
            <div><strong>Hành động:</strong> ${escapeHtml(record.action)}</div>
            <div><strong>Endpoint:</strong> <code>${escapeHtml(record.http_method)} ${escapeHtml(record.endpoint)}</code></div>
            <div><strong>IP nguồn:</strong> ${escapeHtml(record.ip_address || '—')}</div>
            <div><strong>Kết quả:</strong> ${escapeHtml(record.status)} (${escapeHtml(record.status_code)})</div>
          </div>
          <div style="margin-bottom:12px; font-size:13.5px;">
            <strong>Mô tả:</strong> ${escapeHtml(record.description || '—')}
          </div>
          ${record.error_message ? `<div style="margin-bottom:12px; color:#b91c1c;"><strong>Lỗi:</strong> ${escapeHtml(record.error_message)}</div>` : ''}
          <div>
            <strong style="display:block; margin-bottom:6px; font-size:13.5px;">Request Payload (đã che thông tin nhạy cảm):</strong>
            <pre class="json-preview">${escapeHtml(JSON.stringify(record.request_payload || {}, null, 2))}</pre>
          </div>
        `;
      }
      window.RideHubUI?.Modal?.open('auditDetailModal');
    });
  };

  // --------------------------------------------------------------------------
  // BOOTSTRAP
  // --------------------------------------------------------------------------
  document.addEventListener('DOMContentLoaded', async () => {
    if (window.envConfigPromise) {
      await window.envConfigPromise.catch(() => {});
    }
    initTabs();
    initPolicyForm();
    initAuditFilters();

    document.getElementById('btnRefreshAll')?.addEventListener('click', () => {
      loadPolicies();
      loadAuditStats();
      loadAuditLogs(currentPage);
    });

    await loadPolicies();
  });
})();
