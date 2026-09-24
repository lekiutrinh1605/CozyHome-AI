// -------------------------------------------------------------
// CozyHome Cozy AI Assistant (V3 Safe Guardrails & Full UI)
// -------------------------------------------------------------

function getChatSessionId() {
  let sid = sessionStorage.getItem("cozy_chat_session_id");
  if (!sid) {
    sid = "sess_" + Math.random().toString(36).substring(2, 11) + "_" + Date.now().toString(36);
    sessionStorage.setItem("cozy_chat_session_id", sid);
  }
  return sid;
}

function setupAiAssistant() {
  const toggleBtn = document.getElementById("ai-widget-toggle");
  const closeBtn = document.getElementById("ai-widget-close");
  const resetBtn = document.getElementById("ai-widget-reset");
  const clearHistBtn = document.getElementById("ai-widget-clear-history");
  const widgetBox = document.getElementById("ai-widget-box");
  const sendBtn = document.getElementById("ai-send-btn");
  const inputEl = document.getElementById("ai-chat-input");

  if (toggleBtn && widgetBox) {
    toggleBtn.addEventListener("click", () => {
      const isOpen = widgetBox.classList.contains("active");
      if (isOpen) {
        widgetBox.classList.remove("active");
        widgetBox.style.display = "none";
      } else {
        widgetBox.classList.add("active");
        widgetBox.style.display = "flex";
        if (inputEl) inputEl.focus();
        updateAiHeaderUserBadge();
        loadAiChatHistory();
        scrollChatToBottom();
      }
    });
  }

  if (closeBtn && widgetBox) {
    closeBtn.addEventListener("click", () => {
      widgetBox.classList.remove("active");
      widgetBox.style.display = "none";
    });
  }

  if (resetBtn) {
    resetBtn.addEventListener("click", () => resetAiChat());
  }

  if (clearHistBtn) {
    clearHistBtn.addEventListener("click", () => clearAiChatHistory());
  }

  if (sendBtn && inputEl) {
    sendBtn.addEventListener("click", () => submitAiMessage());
    inputEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        submitAiMessage();
      }
    });
  }
}

function scrollChatToBottom() {
  const container = document.getElementById("ai-messages-container");
  if (container) {
    setTimeout(() => {
      container.scrollTop = container.scrollHeight;
    }, 50);
  }
}

function formatMarkdownText(text) {
  if (!text) return "";

  // Loại bỏ ký hiệu BR-xx hoặc (BR-xx) nếu có
  let cleaned = text.replace(/[\(\[\{]?\s*BR-\d+\s*[\)\]\}]?/gi, "");

  // Loại bỏ icon / emoji
  cleaned = cleaned.replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}⚠️👉🌿🏡📍📜💳⏱🎁🏷🟢❌🌙💡🤖✨⭐]/gu, "");

  let formatted = cleaned
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Bold **text**
  formatted = formatted.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");

  // Bullet points • item & Security Alert banner
  const lines = formatted.split("\n");
  const parsedLines = lines.map(line => {
    const trimmed = line.trim();
    if (trimmed.startsWith("• ") || trimmed.startsWith("- ")) {
      return `<li style="margin-left:14px; margin-bottom:4px;">${trimmed.substring(2)}</li>`;
    }
    if (trimmed.includes("Thông báo an toàn") || trimmed.includes("Lưu ý an toàn")) {
      return `<div class="ai-security-alert">${trimmed}</div>`;
    }
    return line;
  });

  formatted = parsedLines.join("<br>");
  return formatted
    .replace(/(<br><li)/g, "<li").replace(/(<\/li><br>)/g, "</li>")
    .replace(/(<br><div class="ai-security-alert">)/g, '<div class="ai-security-alert">')
    .replace(/(<\/div><br>)/g, '</div>');
}

async function submitAiMessage(presetQuery = null) {
  const inputEl = document.getElementById("ai-chat-input");
  const query = presetQuery || (inputEl ? inputEl.value.trim() : "");
  if (!query) return;

  if (inputEl && !presetQuery) inputEl.value = "";

  const messagesContainer = document.getElementById("ai-messages-container");
  if (!messagesContainer) return;

  // 1. Render Tin nhắn của User
  appendUserMessage(query);
  scrollChatToBottom();

  // 2. Render Typing Indicator
  const loadingId = "ai-loading-" + Date.now();
  appendTypingIndicator(loadingId);
  scrollChatToBottom();

  try {
    const today = new Date().toISOString().split("T")[0];
    const sessionId = getChatSessionId();
    const userId = (typeof state !== "undefined" && state.user) ? state.user.id : null;

    const payload = {
      session_id: sessionId,
      query: query,
      user_id: userId,
    };

    const res = await apiFetch("/api/ai/chat", {
      method: "POST",
      body: payload,
    });

    // Xóa Typing Indicator
    removeElement(loadingId);

    // 3. Render Phản hồi của Trợ lý AI
    renderAssistantResponse(res);
    scrollChatToBottom();

  } catch (err) {
    removeElement(loadingId);
    appendAssistantBubble(`
      <div class="ai-bot-text">
        <p><strong>Thông báo hệ thống:</strong> Rất tiếc, kết nối đến Trợ lý AI đang bị gián đoạn hoặc gặp sự cố tạm thời.</p>
        <p>Để không làm gián đoạn kế hoạch đặt phòng của bạn, bạn có thể chuyển sang sử dụng bộ tìm kiếm phòng trực tiếp trên website hoặc liên hệ hotline để được hỗ trợ nhanh nhất:</p>
      </div>
      <div class="ai-actions-wrap" style="margin-top: 10px; display: flex; flex-direction: column; gap: 8px;">
        <button type="button" class="ai-action-btn" onclick="closeAiAndScrollToSearch()" style="background: var(--cozy-primary, #6B4E3D); color: #fff; border: none; padding: 10px 14px; border-radius: 8px; cursor: pointer; font-weight: 600; text-align: center; width: 100%;">
          Tìm phòng trên Website
        </button>
        <a href="tel:0909000001" class="ai-action-btn" style="background: #f8fafc; color: #334155; text-decoration: none; padding: 9px 14px; border-radius: 8px; font-weight: 500; text-align: center; border: 1px solid #cbd5e1; display: block;">
          Hotline hỗ trợ: 0909 000 001
        </a>
      </div>
    `);
    scrollChatToBottom();
  }
}

function closeAiAndScrollToSearch() {
  const widgetBox = document.getElementById("ai-widget-box");
  if (widgetBox) {
    widgetBox.classList.remove("active");
    widgetBox.style.display = "none";
  }
  if (typeof navigateTo === "function") {
    navigateTo("home");
  }
  setTimeout(() => {
    const searchEl = document.getElementById("search-form") || document.getElementById("search-keyword");
    if (searchEl) {
      searchEl.scrollIntoView({ behavior: "smooth", block: "center" });
      const kwInput = document.getElementById("search-keyword");
      if (kwInput) kwInput.focus();
    }
  }, 150);
}

function appendUserMessage(text) {
  const container = document.getElementById("ai-messages-container");
  if (!container) return;

  const msgDiv = document.createElement("div");
  msgDiv.className = "ai-msg-bubble user-bubble";
  msgDiv.textContent = text;
  container.appendChild(msgDiv);
}

function appendTypingIndicator(id) {
  const container = document.getElementById("ai-messages-container");
  if (!container) return;

  const wrapper = document.createElement("div");
  wrapper.id = id;
  wrapper.className = "ai-typing-indicator";
  wrapper.innerHTML = `
    <div class="ai-dot"></div>
    <div class="ai-dot"></div>
    <div class="ai-dot"></div>
    <span class="ai-typing-label">CozyHome đang xử lý...</span>
  `;
  container.appendChild(wrapper);
}

function appendAssistantBubble(htmlContent) {
  const container = document.getElementById("ai-messages-container");
  if (!container) return;

  const msgDiv = document.createElement("div");
  msgDiv.className = "ai-msg-bubble assistant-bubble";
  msgDiv.innerHTML = htmlContent;
  container.appendChild(msgDiv);
}

function removeElement(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

function renderAssistantResponse(res) {
  const formattedText = formatMarkdownText(res.message || "");

  let html = `<div class="ai-bot-text">${formattedText}</div>`;

  // 1. Render Room Cards
  if (res.recommendations && res.recommendations.length > 0) {
    html += `<div class="ai-room-cards-list">`;
    res.recommendations.forEach(r => {
      const img = r.image_url || "/static/images/hero_living_room.png";
      const branchName = r.branch_name || "CozyHome";
      const specs = [
        r.room_type || "Standard",
        `${r.capacity || 2} khách`,
        r.bed_type ? `${r.bed_type}` : ""
      ].filter(Boolean).join(" - ");

      const amenities = (r.amenities || []).slice(0, 3);
      const amenitiesHtml = amenities.map(a => `<span class="ai-amenity-pill">${a}</span>`).join("");

      html += `
        <div class="ai-room-card">
          <div class="ai-room-card-body">
            <div class="ai-room-card-header">
              <div class="ai-room-name">${r.room_name}</div>
              <span class="ai-room-branch-badge">${branchName}</span>
            </div>
            <div class="ai-room-specs">${specs}</div>
            ${amenitiesHtml ? `<div class="ai-room-amenities">${amenitiesHtml}</div>` : ""}
            <div class="ai-room-footer">
              <div class="ai-room-price">${r.formatted_price || "150.000 ₫"}</div>
              <button class="ai-room-btn" onclick="selectAiRoom('${r.room_id}')">Xem chi tiết và đặt</button>
            </div>
          </div>
        </div>
      `;
    });
    html += `</div>`;
  }

  // 2. Render Policy Card (BR-05 / BR-09)
  if (res.policy_card) {
    const p = res.policy_card;
    let rulesHtml = "";
    if (p.rules && p.rules.length > 0) {
      rulesHtml = p.rules.map(r => `
        <div class="ai-policy-rule">
          <span class="ai-rule-condition">${r.condition}</span>
          <span class="ai-rule-result ${r.type || 'info'}">${r.result}</span>
        </div>
      `).join("");
    }

    html += `
      <div class="ai-policy-card">
        <div class="ai-policy-header">${p.title || 'Chính sách CozyHome'}</div>
        ${rulesHtml}
        ${p.note ? `<div class="ai-policy-note">${p.note}</div>` : ""}
      </div>
    `;
  }

  // 3. Render Action Button (Contact Hotline, Select Branch, View Room)
  if (res.action) {
    if (res.action.type === "contact_support") {
      html += `
        <div class="ai-contact-card" style="margin-top: 10px; padding: 12px; background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px;">
          <div style="font-weight: 600; color: #1e293b; margin-bottom: 4px;">Bộ phận Chăm sóc khách hàng CozyHome</div>
          <div style="font-size: 13px; color: #475569; margin-bottom: 8px;">Hotline hoạt động 24/7 để hỗ trợ bạn thông tin chi tiết và đặt phòng:</div>
          <a href="tel:${res.action.phone || '0909000001'}" style="display: block; background: var(--cozy-primary, #6B4E3D); color: #fff; text-align: center; padding: 9px 12px; border-radius: 6px; text-decoration: none; font-weight: 600;">
            ${res.action.label || 'Gọi Hotline: 0909 000 001'}
          </a>
        </div>
      `;
    }
  }

  // 4. Render Quick Reply Chips
  if (res.quick_replies && res.quick_replies.length > 0) {
    html += `<div class="ai-quick-replies">`;
    res.quick_replies.forEach(chip => {
      html += `<button class="ai-chip" onclick="submitAiMessage('${escapeQuotes(chip)}')">${chip}</button>`;
    });
    html += `</div>`;
  }

  appendAssistantBubble(html);
}

function escapeQuotes(str) {
  return (str || "").replace(/'/g, "\\'");
}

function selectAiRoom(roomId) {
  if (typeof openRoomDetailView === "function") {
    openRoomDetailView(roomId);
  } else if (typeof openRoomDetail === "function") {
    openRoomDetail(roomId);
  }

  // Trên thiết bị di động thu nhỏ chat để người dùng xem chi tiết phòng
  if (window.innerWidth <= 600) {
    const widgetBox = document.getElementById("ai-widget-box");
    if (widgetBox) {
      widgetBox.classList.remove("active");
      widgetBox.style.display = "none";
    }
  }
}

async function resetAiChat() {
  const sessionId = getChatSessionId();
  const userId = (typeof state !== "undefined" && state.user) ? state.user.id : null;
  try {
    await apiFetch("/api/ai/clear-history", {
      method: "POST",
      body: { session_id: sessionId, user_id: userId },
    });
  } catch (e) {
    console.warn("Reset AI session error:", e);
  }

  // Tạo session ID mới
  sessionStorage.removeItem("cozy_chat_session_id");
  getChatSessionId();

  // Khôi phục giao diện chào mừng ban đầu
  const container = document.getElementById("ai-messages-container");
  if (container) {
    container.innerHTML = `
      <div class="ai-msg-bubble assistant-bubble">
        <div class="ai-bot-greeting">
          <p>Xin chào quý khách! Em là <strong>Trợ lý CozyHome</strong>. Em có thể hỗ trợ bạn tra cứu lịch phòng, tư vấn theo giờ (khung 3h) hoặc qua đêm, và giải đáp các chính sách hủy – hoàn tiền.</p>
          <div class="ai-welcome-chips">
            <button class="ai-chip" onclick="submitAiMessage('Tìm phòng theo giờ chiều mai')">Thuê theo giờ (khung 3h)</button>
            <button class="ai-chip" onclick="submitAiMessage('Tìm phòng qua đêm tại Thảo Điền cho 2 người')">Thuê qua đêm ở Thảo Điền</button>
            <button class="ai-chip" onclick="submitAiMessage('Chính sách hủy phòng thế nào?')">Chính sách hủy phòng</button>
            <button class="ai-chip" onclick="submitAiMessage('CozyHome có những chi nhánh nào?')">3 chi nhánh CozyHome</button>
          </div>
        </div>
      </div>
    `;
  }
  showToast("Đã làm mới và xóa lịch sử trò chuyện Cozy AI.", "info");
}

function updateAiHeaderUserBadge() {
  const statusEl = document.getElementById("ai-header-user-status");
  if (!statusEl) return;
  const user = (typeof state !== "undefined" && state.user) ? state.user : null;
  if (user) {
    const displayName = user.full_name || user.username || user.email || "Thành viên";
    statusEl.innerHTML = `<span style="color:#dcfce7; font-weight:500;">Tài khoản: ${displayName}</span>`;
  } else {
    statusEl.innerHTML = `<span>Trực tuyến 24/7 - Dữ liệu phòng thực tế</span>`;
  }
}

async function loadAiChatHistory() {
  const sessionId = getChatSessionId();
  const userId = (typeof state !== "undefined" && state.user) ? state.user.id : null;
  const container = document.getElementById("ai-messages-container");
  if (!container) return;

  try {
    const q = new URLSearchParams();
    if (userId) q.set("user_id", userId);
    if (sessionId) q.set("session_id", sessionId);

    const res = await apiFetch(`/api/ai/history?${q.toString()}`);
    if (res && res.history && res.history.length > 0) {
      container.innerHTML = "";
      res.history.forEach(item => {
        if (item.sender === "user") {
          appendUserMessage(item.message);
        } else if (item.sender === "assistant") {
          if (item.meta && item.meta.raw_response) {
            renderAssistantResponse(item.meta.raw_response);
          } else {
            const formatted = formatMarkdownText(item.message || "");
            appendAssistantBubble(`<div class="ai-bot-text">${formatted}</div>`);
          }
        }
      });
      scrollChatToBottom();
    }
  } catch (err) {
    console.warn("Could not load AI chat history:", err);
  }
}

async function clearAiChatHistory() {
  const sessionId = getChatSessionId();
  const userId = (typeof state !== "undefined" && state.user) ? state.user.id : null;
  
  if (!confirm("Bạn có chắc chắn muốn xóa toàn bộ lịch sử trò chuyện này không?")) {
    return;
  }

  try {
    await apiFetch("/api/ai/clear-history", {
      method: "POST",
      body: { session_id: sessionId, user_id: userId },
    });
  } catch (e) {
    console.warn("Clear history error:", e);
  }

  // Khôi phục giao diện chào mừng ban đầu
  const container = document.getElementById("ai-messages-container");
  if (container) {
    container.innerHTML = `
      <div class="ai-msg-bubble assistant-bubble">
        <div class="ai-bot-greeting">
          <p>Xin chào quý khách! Em là <strong>Trợ lý CozyHome</strong>. Em có thể hỗ trợ bạn tra cứu lịch phòng, tư vấn theo giờ (khung 3h) hoặc qua đêm, và giải đáp các chính sách hủy – hoàn tiền.</p>
          <div class="ai-welcome-chips">
            <button class="ai-chip" onclick="submitAiMessage('Tìm phòng theo giờ chiều mai')">Thuê theo giờ (khung 3h)</button>
            <button class="ai-chip" onclick="submitAiMessage('Tìm phòng qua đêm tại Thảo Điền cho 2 người')">Thuê qua đêm ở Thảo Điền</button>
            <button class="ai-chip" onclick="submitAiMessage('Chính sách hủy phòng thế nào?')">Chính sách hủy phòng</button>
            <button class="ai-chip" onclick="submitAiMessage('CozyHome có những chi nhánh nào?')">3 chi nhánh CozyHome</button>
          </div>
        </div>
      </div>
    `;
  }
  showToast("Đã xóa sạch lịch sử trò chuyện Cozy AI.", "info");
}

