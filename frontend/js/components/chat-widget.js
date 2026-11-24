/**
 * ==============================================================================
 * RideHub Chatbot AI Client Component (chat-widget.js)
 * Tích hợp đầy đủ:
 * 1. Khởi tạo phiên UUIDv4 chuẩn RFC 4122 (crypto.randomUUID())
 * 2. Gọi API /api/chat/message (RAG, Gemini/OpenAI Fallback, Rate Limit)
 * 3. Nút chuyển nhân viên hỗ trợ trực tiếp (Human Escalation)
 * 4. Tự động nhận diện khiếu nại và hiển thị Banner Cảnh Báo Khiếu Nại
 * 5. Tự động lấy lịch sử và Reset phiên hội thoại
 * 6. Hiển thị danh sách xe & đơn hàng trực quan khi Chatbot phản hồi
 * ==============================================================================
 */

(function () {
  'use strict';

  const STORAGE_KEY_SESSION = 'ridehub_chat_session_id';
  const STORAGE_KEY_ESCALATED = 'ridehub_chat_is_escalated';

  // Dùng CONFIG.API_BASE_URL từ config.js nếu có (hỗ trợ cả Live Server lẫn FastAPI port 8000)
  // CONFIG được load bởi js/config.js (phải load trước chat-widget.js)
  function getApiBase() {
    if (typeof CONFIG !== 'undefined' && CONFIG.API_BASE_URL) {
      return CONFIG.API_BASE_URL.replace(/\/+$/, '') + '/chat';
    }
    // Fallback: nếu chạy trực tiếp trên FastAPI port 8000 thì dùng relative URL
    if (window.location.port === '8000' || window.location.port === '') {
      return '/api/chat';
    }
    // Live Server / VSCode / khác port → chỉ về FastAPI
    return 'http://127.0.0.1:8000/api/chat';
  }

  // 1. Quản lý Session ID chuẩn UUIDv4
  function getOrCreateSessionId() {
    let sessionId = localStorage.getItem(STORAGE_KEY_SESSION);
    if (!sessionId || !/^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$/.test(sessionId)) {
      if (typeof crypto !== 'undefined' && crypto.randomUUID) {
        sessionId = crypto.randomUUID();
      } else {
        // Fallback RFC 4122 v4
        sessionId = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
          const r = (Math.random() * 16) | 0;
          const v = c === 'x' ? r : (r & 0x3) | 0x8;
          return v.toString(16);
        });
      }
      localStorage.setItem(STORAGE_KEY_SESSION, sessionId);
    }
    return sessionId;
  }

  // 2. Class điều khiển Chatbot
  class RideHubChatbot {
    constructor() {
      this.apiBase = getApiBase();
      this.sessionId = getOrCreateSessionId();
      this.isOpen = false;
      this.isEscalated = localStorage.getItem(STORAGE_KEY_ESCALATED) === 'true';
      this.hasComplaintAlert = false;
      this.isSending = false;

      this.initElements();
      this.bindEvents();
      this.loadHistory();
    }

    initElements() {
      this.fab = document.getElementById('chatFab');
      this.window = document.getElementById('chatWindow');
      this.closeBtn = document.getElementById('chatCloseBtn');
      this.resetBtn = document.getElementById('chatResetBtn');
      this.messagesContainer = document.getElementById('chatMessages');
      this.input = document.getElementById('chatInput');
      this.sendBtn = document.getElementById('chatSendBtn');
      this.form = document.getElementById('chatForm');
      this.handoffBtn = document.getElementById('chatHandoffBtn');
      this.alertBanner = document.getElementById('chatAlertBanner');
      this.statusIndicator = document.getElementById('chatStatusIndicator');
      this.statusText = document.getElementById('chatStatusText');
      this.headerTitle = document.getElementById('chatHeaderTitle');
    }

    bindEvents() {
      if (this.fab) {
        this.fab.addEventListener('click', () => this.toggleWindow());
      }
      if (this.closeBtn) {
        this.closeBtn.addEventListener('click', () => this.closeWindow());
      }
      if (this.resetBtn) {
        this.resetBtn.addEventListener('click', () => this.handleResetSession());
      }
      if (this.handoffBtn) {
        this.handoffBtn.addEventListener('click', () => this.triggerHumanEscalation());
      }
      if (this.form) {
        this.form.addEventListener('submit', (e) => {
          e.preventDefault();
          this.handleSendMessage();
        });
      }

      // Quick pills
      document.addEventListener('click', (e) => {
        const pill = e.target.closest('.chat-quick-pill');
        if (pill) {
          const prompt = pill.dataset.prompt || pill.textContent.trim();
          if (pill.dataset.action === 'handoff') {
            this.triggerHumanEscalation();
          } else {
            this.sendMessage(prompt);
          }
        }
      });
    }

    toggleWindow() {
      if (this.isOpen) {
        this.closeWindow();
      } else {
        this.openWindow();
      }
    }

    openWindow() {
      this.isOpen = true;
      if (this.window) this.window.classList.add('is-open');
      if (this.fab) {
        const badge = this.fab.querySelector('.chat-fab-badge');
        if (badge) badge.style.display = 'none';
      }
      if (this.input) this.input.focus();
      this.scrollToBottom();
    }

    closeWindow() {
      this.isOpen = false;
      if (this.window) this.window.classList.remove('is-open');
    }

    scrollToBottom() {
      if (this.messagesContainer) {
        setTimeout(() => {
          this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
        }, 50);
      }
    }

    // 3. Tải lịch sử hội thoại nếu có
    async loadHistory() {
      try {
        const res = await fetch(`${this.apiBase}/conversations/${this.sessionId}/messages?limit=30`);
        if (!res.ok) return;
        const data = await res.json();
        if (data && data.messages && data.messages.length > 0) {
          if (this.messagesContainer) this.messagesContainer.innerHTML = '';
          data.messages.forEach((msg) => {
            const isUser = msg.sender.toUpperCase() === 'USER';
            const isAgent = msg.sender.toUpperCase() === 'AGENT';
            this.renderMessageBubble(msg.message, isUser ? 'user' : (isAgent ? 'agent' : 'bot'), msg.payload_json);
          });
          if (data.status === 'ESCALATED_TO_AGENT') {
            this.setEscalatedState(true, data.assigned_agent);
          }
        }
      } catch (err) {
        console.warn('[Chatbot] Không thể tải lịch sử phiên cũ:', err);
      }
    }

    // 4. Gửi tin nhắn chính
    async handleSendMessage() {
      if (!this.input || this.isSending) return;
      const text = this.input.value.trim();
      if (!text) return;

      this.input.value = '';
      await this.sendMessage(text);
    }

    async sendMessage(text) {
      if (this.isSending) return;
      this.isSending = true;
      if (this.sendBtn) this.sendBtn.disabled = true;

      // 1. Render tin nhắn User
      this.renderMessageBubble(text, 'user');
      this.scrollToBottom();

      // Kiểm tra sơ bộ khiếu nại phía Client để phản hồi tức thì
      this.detectClientComplaint(text);

      // 2. Hiển thị Typing Animation
      const typingEl = this.showTypingIndicator();
      this.scrollToBottom();

      try {
        const token = localStorage.getItem('ridehub_token') || sessionStorage.getItem('ridehub_token') || '';
        const headers = { 'Content-Type': 'application/json' };
        if (token) headers['Authorization'] = `Bearer ${token}`;

        const res = await fetch(`${this.apiBase}/message`, {
          method: 'POST',
          headers,
          body: JSON.stringify({
            session_id: this.sessionId,
            message: text,
          }),
        });

        typingEl.remove();

        if (res.status === 429) {
          const errData = await res.json();
          this.renderMessageBubble(
            `⚠️ Bạn đã gửi tin nhắn quá nhanh! Vui lòng đợi ${errData.detail || 'một chút'} rồi thử lại nhé.`,
            'bot'
          );
          return;
        }

        if (!res.ok) {
          throw new Error(`Mã lỗi máy chủ: ${res.status}`);
        }

        const data = await res.json();
        const role = data.sender === 'agent' ? 'agent' : 'bot';

        // Xử lý chuyển tiếp nhân viên hoặc khiếu nại từ backend
        if (data.is_escalated) {
          this.setEscalatedState(true, data.assigned_agent);
        }

        // Nhận diện khiếu nại từ intent
        if (data.detected_intent === 'agent_escalation' || /khiếu nại|tố cáo|lừa đảo/i.test(text)) {
          this.showComplaintWarningBanner(
            'Hệ thống phát hiện nội dung khiếu nại / sự cố dịch vụ. Cuộc trò chuyện đã được ưu tiên chuyển trực tiếp tới Quản lý Vận hành để xử lý khẩn cấp.'
          );
        }

        this.renderMessageBubble(data.message, role, data.payload, data.citations);
      } catch (error) {
        if (typingEl) typingEl.remove();
        this.renderMessageBubble(
          'Dạ xin lỗi Quý khách, kết nối tạm thời bị gián đoạn. Quý khách vui lòng thử lại sau ít giây ạ!',
          'bot'
        );
        console.error('[Chatbot Error]', error);
      } finally {
        this.isSending = false;
        if (this.sendBtn) this.sendBtn.disabled = false;
        this.scrollToBottom();
      }
    }

    // 5. Nút thủ công chuyển nhân viên hỗ trợ
    async triggerHumanEscalation() {
      if (this.isEscalated) return;
      await this.sendMessage('Tôi muốn kết nối với nhân viên hỗ trợ trực tiếp.');
    }

    // 6. Nhận diện khiếu nại sơ bộ
    detectClientComplaint(text) {
      const complaintKeywords = ['khiếu nại', 'to cao', 'tố cáo', 'lừa đảo', 'gian lận', 'bồi thường', 'hoàn cọc ngay', 'thái độ nhân viên'];
      const hasKeywords = complaintKeywords.some((kw) => text.toLowerCase().includes(kw));
      if (hasKeywords) {
        this.showComplaintWarningBanner(
          'Cảnh báo: Yêu cầu khiếu nại của Quý khách đã được ghi nhận vào hệ thống giám sát chất lượng và chuyển tiếp ngay tới Quản lý.'
        );
      }
    }

    showComplaintWarningBanner(msg) {
      if (!this.alertBanner) return;
      this.alertBanner.className = 'chat-alert-banner is-complaint';
      this.alertBanner.innerHTML = `
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
          <line x1="12" y1="9" x2="12" y2="13"/>
          <line x1="12" y1="17" x2="12.01" y2="17"/>
        </svg>
        <div class="chat-alert-content">
          <div class="chat-alert-title">Ghi nhận Khiếu nại dịch vụ</div>
          <div>${msg}</div>
        </div>
      `;
      this.alertBanner.style.display = 'flex';
      if (this.statusIndicator) this.statusIndicator.className = 'chat-status-indicator is-alert';
    }

    setEscalatedState(isEscalated, agentName = 'Mai Linh (Trưởng ca CSKH)') {
      this.isEscalated = isEscalated;
      localStorage.setItem(STORAGE_KEY_ESCALATED, isEscalated ? 'true' : 'false');

      if (this.handoffBtn) {
        this.handoffBtn.classList.add('active');
        this.handoffBtn.innerHTML = `
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
          Đã nối máy nhân viên
        `;
      }
      if (this.statusIndicator) this.statusIndicator.className = 'chat-status-indicator is-agent';
      if (this.statusText) this.statusText.textContent = `Hỗ trợ bởi: ${agentName}`;
      if (this.headerTitle) this.headerTitle.textContent = 'Hỗ Trợ Trực Tiếp CSKH';
    }

    // 7. Reset phiên trò chuyện — không hỏi lại, reset trực tiếp với animation
    async handleResetSession() {
      // Hiển thị hiệu ứng "đang làm mới" thay vì confirm dialog
      if (this.resetBtn) {
        this.resetBtn.disabled = true;
        this.resetBtn.innerHTML = `
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
            stroke-linecap="round" style="animation:spin 0.6s linear infinite">
            <polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 102.13-9.36L1 10"/>
          </svg>
          Đang làm mới...
        `;
      }

      try {
        await fetch(`${this.apiBase}/conversations/${this.sessionId}/reset`, { method: 'POST' });
      } catch (e) {
        console.warn('[Chatbot] Reset API error (bỏ qua):', e);
      }

      localStorage.removeItem(STORAGE_KEY_SESSION);
      localStorage.removeItem(STORAGE_KEY_ESCALATED);
      this.sessionId = getOrCreateSessionId();
      this.isEscalated = false;

      if (this.messagesContainer) {
        // Fade out → reset → fade in
        this.messagesContainer.style.opacity = '0';
        this.messagesContainer.style.transition = 'opacity 0.25s ease';
        setTimeout(() => {
          this.messagesContainer.innerHTML = `
            <div class="chat-msg-row bot">
              <div class="chat-msg-avatar">AI</div>
              <div class="chat-bubble">
                ✨ Hội thoại đã được làm mới! Em là Trợ lý AI RideHub — Quý khách cần tìm xe, tra cứu đơn hay giải đáp chính sách nào ạ?
                <div class="chat-quick-row">
                  <button class="chat-quick-pill" data-prompt="Tìm thuê xe máy tiết kiệm xăng" type="button">🏍️ Thuê xe máy</button>
                  <button class="chat-quick-pill" data-prompt="Tìm xe ô tô 7 chỗ gia đình" type="button">🚗 Ô tô 7 chỗ</button>
                  <button class="chat-quick-pill" data-prompt="Kiểm tra đơn thuê xe của tôi" type="button">📋 Tra cứu đơn</button>
                  <button class="chat-quick-pill" data-action="handoff" type="button">👤 Gặp nhân viên</button>
                </div>
              </div>
            </div>
          `;
          this.messagesContainer.style.opacity = '1';
        }, 250);
      }
      if (this.alertBanner) this.alertBanner.style.display = 'none';
      if (this.handoffBtn) {
        this.handoffBtn.classList.remove('active');
        this.handoffBtn.disabled = false;
        this.handoffBtn.innerHTML = `
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
            stroke-linecap="round"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></svg>
          Gặp nhân viên hỗ trợ
        `;
      }
      if (this.resetBtn) {
        this.resetBtn.disabled = false;
        this.resetBtn.innerHTML = `
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
            stroke-linecap="round"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 102.13-9.36L1 10"/></svg>
          Làm mới
        `;
      }
      if (this.statusIndicator) this.statusIndicator.className = 'chat-status-dot';
      if (this.statusText) this.statusText.textContent = 'Đang hoạt động';
      if (this.headerTitle) this.headerTitle.textContent = 'Trợ lý AI RideHub';
    }

    showTypingIndicator() {
      const row = document.createElement('div');
      row.className = 'chat-msg-row bot';
      row.innerHTML = `
        <div class="chat-msg-avatar">AI</div>
        <div class="chat-typing">
          <span class="typing-dot"></span>
          <span class="typing-dot"></span>
          <span class="typing-dot"></span>
        </div>
      `;
      this.messagesContainer.appendChild(row);
      return row;
    }

    renderMessageBubble(text, sender, payload = null, citations = []) {
      if (!this.messagesContainer) return;
      const row = document.createElement('div');
      row.className = `chat-msg-row ${sender}`;

      const avatarLabel = sender === 'user' ? 'Tôi' : (sender === 'agent' ? 'CSKH' : 'AI');
      const avatarClass = sender === 'agent' ? 'chat-msg-avatar agent-avatar' : 'chat-msg-avatar';

      let citationHtml = '';
      if (citations && citations.length > 0) {
        citationHtml = '<div style="margin-top:6px;">' + citations.map((c) =>
          `<span class="chat-citation-tag">📖 ${escapeHtml(c.category_name || c.category)}: ${escapeHtml(c.question)}</span>`
        ).join('') + '</div>';
      }

      // Xử lý danh sách xe hoặc đơn hàng trả về từ payload
      let extraHtml = '';
      if (payload && payload.vehicles && payload.vehicles.length > 0) {
        extraHtml = '<div style="margin-top:8px;display:flex;flex-direction:column;gap:6px;">';
        payload.vehicles.forEach((v) => {
          extraHtml += `
            <div class="chat-card-preview">
              <div class="title">🚗 ${escapeHtml(v.brand)} ${escapeHtml(v.model)} (${v.vehicle_type})</div>
              <div>Giá: <strong>${Number(v.price_per_day).toLocaleString('vi-VN')} đ/ngày</strong> | Biển: ${v.plate_number}</div>
              <a href="vehicles.html?id=${v.id}" class="chat-alert-action-btn" target="_blank">Xem chi tiết đặt xe →</a>
            </div>
          `;
        });
        extraHtml += '</div>';
      } else if (payload && payload.bookings && payload.bookings.length > 0) {
        extraHtml = '<div style="margin-top:8px;display:flex;flex-direction:column;gap:6px;">';
        payload.bookings.forEach((b) => {
          extraHtml += `
            <div class="chat-card-preview">
              <div class="title">📋 Đơn #${b.booking_id} • ${escapeHtml(b.vehicle_name)}</div>
              <div>Biển số: <strong>${b.plate_number}</strong> | Trạng thái: <span style="color:var(--green-600);font-weight:700;">${b.status}</span></div>
              <div>Tổng thanh toán: <strong>${Number(b.total_amount).toLocaleString('vi-VN')} đ</strong></div>
            </div>
          `;
        });
        extraHtml += '</div>';
      }

      row.innerHTML = `
        <div class="${avatarClass}">${avatarLabel}</div>
        <div class="chat-bubble">
          ${formatChatText(text)}
          ${citationHtml}
          ${extraHtml}
        </div>
      `;
      this.messagesContainer.appendChild(row);
    }
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function formatChatText(text) {
    if (!text) return '';
    const safe = escapeHtml(text);
    return safe
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(
        /\/vehicles\.html(\?[A-Za-z0-9_=&%-]*)?/g,
        '<a href="vehicles.html$1" target="_blank" style="color:var(--green-600);font-weight:600;text-decoration:underline;">Xem danh sách xe ↗</a>'
      )
      .replace(
        /(1900[\s-]?\d{4})/g,
        '<a href="tel:$1" style="color:var(--green-600);font-weight:700;text-decoration:underline;">📞 $1</a>'
      )
      .replace(/\n/g, '<br/>');
  }

  // Khởi tạo tự động khi trang tải xong
  document.addEventListener('DOMContentLoaded', () => {
    window.ridehubChatbot = new RideHubChatbot();
  });
})();
