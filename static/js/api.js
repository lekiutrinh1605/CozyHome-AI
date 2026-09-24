// -------------------------------------------------------------
// CozyHome API Client & Notification Helpers
// -------------------------------------------------------------
const API_BASE = "";

let lastToastMsg = "";
let lastToastTime = 0;

function showToast(msg, type = "info") {
  if (!msg) return;
  const now = Date.now();
  if (msg === lastToastMsg && now - lastToastTime < 2500) {
    return; // Chống spam thông báo trùng lặp
  }
  lastToastMsg = msg;
  lastToastTime = now;

  const box = document.getElementById("toast-container") || createToastBox();
  const toast = document.createElement("div");
  toast.className = `toast ${
    type === "error"
      ? "badge-danger"
      : type === "success"
      ? "badge-success"
      : type === "warning"
      ? "badge-warning"
      : "badge-info"
  }`;

  const iconSvg =
    type === "error"
      ? `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>`
      : type === "success"
      ? `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#16a34a" stroke-width="2.2"><polyline points="20 6 9 17 4 12"></polyline></svg>`
      : type === "warning"
      ? `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>`
      : `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>`;

  toast.innerHTML = `<span style="display:inline-flex; align-items:center;">${iconSvg}</span> <span>${msg}</span>`;
  box.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(10px) scale(0.95)";
    setTimeout(() => toast.remove(), 250);
  }, 4000);
}

function createToastBox() {
  const div = document.createElement("div");
  div.id = "toast-container";
  div.className = "toast-box";
  document.body.appendChild(div);
  return div;
}

function formatMoney(amount) {
  if (amount === null || amount === undefined) return "—";
  return new Intl.NumberFormat("vi-VN", { style: "currency", currency: "VND" }).format(amount);
}

async function apiFetch(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const defaultHeaders = {
    "Content-Type": "application/json",
  };

  // Đính kèm Bearer Token xác thực phía server
  const token = localStorage.getItem("cozy_token");
  if (token) {
    defaultHeaders["Authorization"] = `Bearer ${token}`;
  }

  // Nếu là Demo Account đang trong Training Mode, gửi kèm X-Demo-Role và X-Demo-Branch để backend kiểm tra
  const activeRole = localStorage.getItem("cozy_active_role");
  if (activeRole) {
    defaultHeaders["X-Demo-Role"] = encodeURIComponent(activeRole);
  }
  const activeBranch = localStorage.getItem("cozy_active_branch");
  if (activeBranch) {
    defaultHeaders["X-Demo-Branch"] = encodeURIComponent(activeBranch);
  }

  const config = {
    ...options,
    headers: {
      ...defaultHeaders,
      ...(options.headers || {}),
    },
  };

  if (config.body && typeof config.body === "object") {
    config.body = JSON.stringify(config.body);
  }

  try {
    const res = await fetch(url, config);
    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
      console.warn(`[CozyHome API ${res.status}] ${url}:`, data);

      // Xử lý phiên hết hạn (401 Unauthorized)
      if (res.status === 401) {
        if (token && typeof clearUserSession === "function") {
          clearUserSession();
          if (typeof updateAuthUI === "function") updateAuthUI();
          if (typeof navigateTo === "function") navigateTo("auth");
        }
      }

      let errorMsg = "Đã có lỗi xảy ra từ máy chủ.";
      if (typeof data.detail === "string") {
        errorMsg = data.detail;
      } else if (Array.isArray(data.detail)) {
        errorMsg = data.detail.map(d => d.msg || JSON.stringify(d)).join(", ");
      } else if (data.detail && typeof data.detail === "object") {
        errorMsg = data.detail.message || JSON.stringify(data.detail);
      } else if (data.message) {
        errorMsg = data.message;
      } else if (res.status === 500) {
        errorMsg = "Máy chủ đang cập nhật hoặc tải lại, vui lòng thử lại sau giây lát.";
      }
      throw new Error(errorMsg);
    }
    return data;
  } catch (err) {
    showToast(err.message, "error");
    throw err;
  }
}
