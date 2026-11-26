(function () {
  'use strict';

  const PRESET_CATEGORIES = new Set([
    'pricing',
    'ekyc',
    'deposit',
    'delivery',
    'cancel',
    'emergency',
    'general',
  ]);

  const accessMessage = document.getElementById('accessMessage');
  const accessMessageText = document.getElementById('accessMessageText');
  const faqContent = document.getElementById('faqContent');
  const faqTableBody = document.getElementById('faqTableBody');
  const faqEmptyState = document.getElementById('faqEmptyState');
  const faqLastUpdated = document.getElementById('faqLastUpdated');

  const statTotalFaq = document.getElementById('statTotalFaq');
  const statActiveFaq = document.getElementById('statActiveFaq');
  const statInactiveFaq = document.getElementById('statInactiveFaq');
  const statCategories = document.getElementById('statCategories');

  const searchInput = document.getElementById('faqSearchInput');
  const categoryFilter = document.getElementById('faqCategoryFilter');
  const statusFilter = document.getElementById('faqStatusFilter');
  const refreshFaqBtn = document.getElementById('refreshFaqBtn');
  const openCreateFaqBtn = document.getElementById('openCreateFaqBtn');

  // Form modal elements
  const faqModal = document.getElementById('faqModal');
  const faqModalTitle = document.getElementById('faqModalTitle');
  const faqModalEyebrow = document.getElementById('faqModalEyebrow');
  const faqForm = document.getElementById('faqForm');
  const faqFormError = document.getElementById('faqFormError');
  const faqCategoryPreset = document.getElementById('faqCategoryPreset');
  const customCategoryCodeWrap = document.getElementById('customCategoryCodeWrap');
  const customCategoryNameWrap = document.getElementById('customCategoryNameWrap');
  const faqCategoryCode = document.getElementById('faqCategoryCode');
  const faqCategoryName = document.getElementById('faqCategoryName');
  const faqDisplayOrder = document.getElementById('faqDisplayOrder');
  const faqQuestion = document.getElementById('faqQuestion');
  const faqAnswer = document.getElementById('faqAnswer');
  const faqQuestionCount = document.getElementById('faqQuestionCount');
  const faqAnswerCount = document.getElementById('faqAnswerCount');
  const faqIsActive = document.getElementById('faqIsActive');
  const saveFaqBtn = document.getElementById('saveFaqBtn');
  const closeFaqModalBtn = document.getElementById('closeFaqModalBtn');
  const cancelFaqModalBtn = document.getElementById('cancelFaqModalBtn');

  // Delete modal elements
  const deleteFaqModal = document.getElementById('deleteFaqModal');
  const deleteFaqSummary = document.getElementById('deleteFaqSummary');
  const closeDeleteModalBtn = document.getElementById('closeDeleteModalBtn');
  const cancelDeleteBtn = document.getElementById('cancelDeleteBtn');
  const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');

  const toastEl = document.getElementById('faqToast');

  let allFaqs = [];
  let editingFaqId = null;
  let deletingFaqId = null;
  let toastTimer = null;

  function getApiBaseUrl() {
    const configured = window.CONFIG && window.CONFIG.API_BASE_URL;
    return (configured || 'http://127.0.0.1:8000/api').replace(/\/+$/, '');
  }

  function getToken() {
    try {
      const keys = ['ridehub_auth_token', 'ridehub_token', 'access_token', 'token'];
      for (const k of keys) {
        const val = localStorage.getItem(k) || sessionStorage.getItem(k);
        if (val) return val;
      }
      const match = document.cookie.match(/(?:^|;\s*)(?:ridehub_token|access_token|token)=([^;]+)/);
      return match ? decodeURIComponent(match[1]) : '';
    } catch (_) {
      return '';
    }
  }

  function escapeHtml(str) {
    return String(str == null ? '' : str).replace(/[&<>"']/g, (c) => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;',
    }[c]));
  }

  function showToast(message, type = 'success') {
    if (!toastEl) return;
    toastEl.textContent = message;
    toastEl.className = `toast-banner ${type === 'error' ? 'is-error' : 'is-success'}`;
    toastEl.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      toastEl.hidden = true;
    }, 3200);
  }

  async function apiRequest(path, options = {}) {
    const token = getToken();
    const headers = { Accept: 'application/json' };
    if (options.body) headers['Content-Type'] = 'application/json';
    if (token) headers.Authorization = `Bearer ${token}`;

    let response;
    try {
      response = await fetch(`${getApiBaseUrl()}${path}`, {
        ...options,
        headers: { ...headers, ...(options.headers || {}) },
        cache: 'no-store',
      });
    } catch (_) {
      const err = new Error('Không thể kết nối Backend. Vui lòng kiểm tra server đang chạy.');
      err.status = 0;
      throw err;
    }

    let data = {};
    try {
      data = await response.json();
    } catch (_) {
      data = {};
    }

    if (!response.ok) {
      const detail = data.detail || data.message;
      const msg = typeof detail === 'string'
        ? detail
        : Array.isArray(detail) && detail[0]?.msg
          ? detail[0].msg
          : `Yêu cầu thất bại (HTTP ${response.status}).`;
      const err = new Error(msg);
      err.status = response.status;
      throw err;
    }

    return data;
  }

  function showAccessDenied(msg) {
    if (faqContent) faqContent.hidden = true;
    if (accessMessage) {
      accessMessage.hidden = false;
      accessMessageText.textContent = msg;
    }
  }

  function updateStats(list) {
    const activeCount = list.filter((x) => x.is_active).length;
    const inactiveCount = list.length - activeCount;
    const distinctCats = new Set(list.map((x) => x.category)).size;
    if (statTotalFaq) statTotalFaq.textContent = String(list.length);
    if (statActiveFaq) statActiveFaq.textContent = String(activeCount);
    if (statInactiveFaq) statInactiveFaq.textContent = String(inactiveCount);
    if (statCategories) statCategories.textContent = String(distinctCats);
  }

  function syncCategoryFilterOptions(list) {
    if (!categoryFilter) return;
    const currentVal = categoryFilter.value;
    const seen = new Map([
      ['pricing', 'Giá thuê & Phụ phí'],
      ['ekyc', 'eKYC & Thủ tục'],
      ['deposit', 'Tiền cọc & Thanh toán'],
      ['delivery', 'Giao nhận xe'],
      ['cancel', 'Hủy đơn & Hoàn tiền'],
      ['emergency', 'Cứu hộ & Sự cố'],
      ['general', 'Chính sách chung'],
    ]);
    list.forEach((item) => {
      if (item.category && !seen.has(item.category)) {
        seen.set(item.category, item.category_name || item.category);
      }
    });
    categoryFilter.innerHTML = '<option value="all">Tất cả chủ đề</option>' +
      Array.from(seen.entries())
        .map(([code, name]) => `<option value="${escapeHtml(code)}">${escapeHtml(name)}</option>`)
        .join('');
    if (Array.from(categoryFilter.options).some((o) => o.value === currentVal)) {
      categoryFilter.value = currentVal;
    }
  }

  function getCategoryBadgeClass(code) {
    const c = (code || '').toLowerCase();
    if (PRESET_CATEGORIES.has(c) && c !== 'general') return `cat-badge cat-badge--${c}`;
    return 'cat-badge';
  }

  function renderFilteredTable() {
    const q = (searchInput?.value || '').trim().toLowerCase();
    const cat = categoryFilter?.value || 'all';
    const st = statusFilter?.value || 'all';

    const filtered = allFaqs.filter((item) => {
      if (cat !== 'all' && item.category !== cat) return false;
      if (st === 'active' && !item.is_active) return false;
      if (st === 'inactive' && item.is_active) return false;
      if (q) {
        const hay = `${item.id} ${item.category} ${item.category_name} ${item.question} ${item.answer}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });

    if (!faqTableBody) return;
    if (filtered.length === 0) {
      faqTableBody.innerHTML = '';
      if (faqEmptyState) faqEmptyState.hidden = false;
      return;
    }
    if (faqEmptyState) faqEmptyState.hidden = true;

    faqTableBody.innerHTML = filtered.map((item) => `
      <tr data-faq-id="${item.id}">
        <td>
          <strong>#${item.id}</strong>
          <div style="font-size:12px;color:#5b7a67;">STT: ${item.display_order ?? 0}</div>
        </td>
        <td>
          <span class="${getCategoryBadgeClass(item.category)}">${escapeHtml(item.category_name || item.category)}</span>
          <div style="font-size:11.5px;color:#64748b;margin-top:4px;">${escapeHtml(item.category)}</div>
        </td>
        <td>
          <div class="faq-question-text">${escapeHtml(item.question)}</div>
          <div class="faq-answer-preview" title="${escapeHtml(item.answer)}">${escapeHtml(item.answer)}</div>
        </td>
        <td>
          <button
            type="button"
            class="status-pill ${item.is_active ? 'status-pill--active' : 'status-pill--inactive'}"
            data-action="toggle-status"
            data-id="${item.id}"
            title="Bấm để bật/tắt nhanh"
          >
            ${item.is_active ? '● Đang bật' : '○ Tạm ẩn'}
          </button>
        </td>
        <td><strong>${item.view_count ?? 0}</strong></td>
        <td>
          <div class="row-actions">
            <button type="button" class="btn-sm" data-action="edit" data-id="${item.id}">Sửa</button>
            <button type="button" class="btn-sm btn-sm--danger" data-action="delete" data-id="${item.id}">Xóa</button>
          </div>
        </td>
      </tr>
    `).join('');
  }

  async function loadFaqs() {
    try {
      const data = await apiRequest('/chat/knowledge-base/admin?limit=200');
      allFaqs = Array.isArray(data) ? data : [];
      if (accessMessage) accessMessage.hidden = true;
      if (faqContent) faqContent.hidden = false;
      updateStats(allFaqs);
      syncCategoryFilterOptions(allFaqs);
      renderFilteredTable();
      if (faqLastUpdated) {
        faqLastUpdated.textContent = `Cập nhật lúc ${new Date().toLocaleTimeString('vi-VN')} • ${allFaqs.length} mục`;
      }
    } catch (err) {
      if (err.status === 401 || err.status === 403) {
        showAccessDenied(
          err.status === 401
            ? 'Bạn cần đăng nhập bằng tài khoản Quản trị viên (Admin) để quản lý kho FAQ.'
            : 'Tài khoản hiện tại không có quyền Admin để truy cập trang quản lý FAQ.'
        );
      } else {
        showAccessDenied(err.message || 'Không thể tải danh sách FAQ.');
      }
    }
  }

  function updateCharCounts() {
    if (faqQuestionCount && faqQuestion) {
      faqQuestionCount.textContent = `${faqQuestion.value.length} / 500 ký tự (tối thiểu 5 ký tự)`;
    }
    if (faqAnswerCount && faqAnswer) {
      faqAnswerCount.textContent = `${faqAnswer.value.length} ký tự (tối thiểu 10 ký tự)`;
    }
  }

  function toggleCustomCategoryFields() {
    const isCustom = faqCategoryPreset.value === 'custom';
    if (customCategoryCodeWrap) customCategoryCodeWrap.hidden = !isCustom;
    if (customCategoryNameWrap) customCategoryNameWrap.hidden = !isCustom;
  }

  function openCreateModal() {
    editingFaqId = null;
    faqModalEyebrow.textContent = 'THÊM TRI THỨC MỚI';
    faqModalTitle.textContent = 'Thêm FAQ mới';
    saveFaqBtn.textContent = 'Thêm FAQ';
    faqFormError.hidden = true;
    faqCategoryPreset.value = 'pricing|Giá thuê & Phụ phí';
    toggleCustomCategoryFields();
    faqCategoryCode.value = '';
    faqCategoryName.value = '';
    faqDisplayOrder.value = '0';
    faqQuestion.value = '';
    faqAnswer.value = '';
    faqIsActive.checked = true;
    updateCharCounts();
    faqModal.showModal();
  }

  function openEditModal(faqId) {
    const item = allFaqs.find((x) => x.id === faqId);
    if (!item) return;
    editingFaqId = item.id;
    faqModalEyebrow.textContent = `CHỈNH SỬA MỤC #${item.id}`;
    faqModalTitle.textContent = 'Cập nhật nội dung FAQ';
    saveFaqBtn.textContent = 'Lưu thay đổi';
    faqFormError.hidden = true;

    const matchingOption = Array.from(faqCategoryPreset.options).find(
      (opt) => opt.value.startsWith(`${item.category}|`)
    );
    if (matchingOption) {
      faqCategoryPreset.value = matchingOption.value;
      toggleCustomCategoryFields();
    } else {
      faqCategoryPreset.value = 'custom';
      toggleCustomCategoryFields();
      faqCategoryCode.value = item.category || '';
      faqCategoryName.value = item.category_name || '';
    }

    faqDisplayOrder.value = String(item.display_order ?? 0);
    faqQuestion.value = item.question || '';
    faqAnswer.value = item.answer || '';
    faqIsActive.checked = Boolean(item.is_active);
    updateCharCounts();
    faqModal.showModal();
  }

  function openDeleteModal(faqId) {
    const item = allFaqs.find((x) => x.id === faqId);
    if (!item) return;
    deletingFaqId = item.id;
    deleteFaqSummary.innerHTML = `Bạn có chắc muốn xóa mục <strong>#${item.id}</strong>: “${escapeHtml(item.question)}”?`;
    deleteFaqModal.showModal();
  }

  async function handleFormSubmit(e) {
    e.preventDefault();
    faqFormError.hidden = true;

    let category = '';
    let categoryName = '';
    if (faqCategoryPreset.value === 'custom') {
      category = faqCategoryCode.value.trim().toLowerCase();
      categoryName = faqCategoryName.value.trim();
    } else {
      const [code, name] = faqCategoryPreset.value.split('|');
      category = code;
      categoryName = name;
    }

    const question = faqQuestion.value.trim();
    const answer = faqAnswer.value.trim();
    const displayOrder = Math.max(0, parseInt(faqDisplayOrder.value || '0', 10) || 0);
    const isActive = Boolean(faqIsActive.checked);

    if (category.length < 2 || categoryName.length < 2) {
      faqFormError.textContent = 'Mã nhóm và tên nhóm hiển thị phải có ít nhất 2 ký tự.';
      faqFormError.hidden = false;
      return;
    }
    if (question.length < 5) {
      faqFormError.textContent = 'Câu hỏi phải có ít nhất 5 ký tự.';
      faqFormError.hidden = false;
      return;
    }
    if (answer.length < 10) {
      faqFormError.textContent = 'Nội dung trả lời phải có ít nhất 10 ký tự.';
      faqFormError.hidden = false;
      return;
    }

    const payload = {
      category,
      category_name: categoryName,
      question,
      answer,
      display_order: displayOrder,
      is_active: isActive,
    };

    saveFaqBtn.disabled = true;
    try {
      if (editingFaqId === null) {
        await apiRequest('/chat/knowledge-base', {
          method: 'POST',
          body: JSON.stringify(payload),
        });
        showToast('Đã thêm FAQ mới thành công!');
      } else {
        await apiRequest(`/chat/knowledge-base/${editingFaqId}`, {
          method: 'PUT',
          body: JSON.stringify(payload),
        });
        showToast(`Đã cập nhật FAQ #${editingFaqId} thành công!`);
      }
      faqModal.close();
      await loadFaqs();
    } catch (err) {
      faqFormError.textContent = err.message || 'Không thể lưu FAQ.';
      faqFormError.hidden = false;
    } finally {
      saveFaqBtn.disabled = false;
    }
  }

  async function handleQuickToggle(faqId) {
    const item = allFaqs.find((x) => x.id === faqId);
    if (!item) return;
    try {
      await apiRequest(`/chat/knowledge-base/${faqId}`, {
        method: 'PUT',
        body: JSON.stringify({ is_active: !item.is_active }),
      });
      showToast(!item.is_active ? `Đã bật FAQ #${faqId}` : `Đã tạm ẩn FAQ #${faqId}`);
      await loadFaqs();
    } catch (err) {
      showToast(err.message || 'Không thể đổi trạng thái FAQ.', 'error');
    }
  }

  async function handleConfirmDelete() {
    if (deletingFaqId === null) return;
    confirmDeleteBtn.disabled = true;
    try {
      await apiRequest(`/chat/knowledge-base/${deletingFaqId}`, { method: 'DELETE' });
      showToast(`Đã xóa FAQ #${deletingFaqId}.`);
      deleteFaqModal.close();
      deletingFaqId = null;
      await loadFaqs();
    } catch (err) {
      showToast(err.message || 'Không thể xóa FAQ.', 'error');
    } finally {
      confirmDeleteBtn.disabled = false;
    }
  }

  // Event listeners
  if (searchInput) searchInput.addEventListener('input', renderFilteredTable);
  if (categoryFilter) categoryFilter.addEventListener('change', renderFilteredTable);
  if (statusFilter) statusFilter.addEventListener('change', renderFilteredTable);
  if (refreshFaqBtn) refreshFaqBtn.addEventListener('click', loadFaqs);
  if (openCreateFaqBtn) openCreateFaqBtn.addEventListener('click', openCreateModal);

  if (faqCategoryPreset) faqCategoryPreset.addEventListener('change', toggleCustomCategoryFields);
  if (faqQuestion) faqQuestion.addEventListener('input', updateCharCounts);
  if (faqAnswer) faqAnswer.addEventListener('input', updateCharCounts);
  if (faqForm) faqForm.addEventListener('submit', handleFormSubmit);
  if (closeFaqModalBtn) closeFaqModalBtn.addEventListener('click', () => faqModal.close());
  if (cancelFaqModalBtn) cancelFaqModalBtn.addEventListener('click', () => faqModal.close());

  if (closeDeleteModalBtn) closeDeleteModalBtn.addEventListener('click', () => deleteFaqModal.close());
  if (cancelDeleteBtn) cancelDeleteBtn.addEventListener('click', () => deleteFaqModal.close());
  if (confirmDeleteBtn) confirmDeleteBtn.addEventListener('click', handleConfirmDelete);

  if (faqTableBody) {
    faqTableBody.addEventListener('click', (e) => {
      const btn = e.target.closest('[data-action]');
      if (!btn) return;
      const id = Number(btn.dataset.id);
      if (btn.dataset.action === 'edit') openEditModal(id);
      else if (btn.dataset.action === 'delete') openDeleteModal(id);
      else if (btn.dataset.action === 'toggle-status') handleQuickToggle(id);
    });
  }

  document.addEventListener('DOMContentLoaded', loadFaqs);
})();
