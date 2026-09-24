// -------------------------------------------------------------
// CozyHome Master Application Bootstrap & Router
// -------------------------------------------------------------

document.addEventListener("DOMContentLoaded", async () => {
  setupNavigation();
  setupEventListeners();
  setupAiAssistant();

  // Đặt ngày hôm nay làm giá trị mặc định
  const today = new Date().toISOString().split("T")[0];
  const dateInput = document.getElementById("search-date");
  if (dateInput) {
    dateInput.value = today;
    dateInput.min = today;
  }

  // Tải metadata và cập nhật trạng thái UI
  await loadMetadata();
  updateAuthUI();
  await performSearch();

  // Đảm bảo form đăng nhập không bị lưu vết hoặc tự động điền ngoài ý muốn
  if (typeof resetLoginForm === "function") {
    resetLoginForm();
    setTimeout(resetLoginForm, 100);
    setTimeout(resetLoginForm, 350);
  }

  // Đảm bảo state.user nạp đầy đủ từ localStorage nếu có
  if (!state.user) {
    const stored = localStorage.getItem("cozy_user");
    if (stored) {
      try { state.user = JSON.parse(stored); } catch (e) {}
    }
  }

  // Điều hướng ban đầu theo URL pathname / hash hoặc trạng thái phiên
  const rawPath = window.location.pathname;
  const path = rawPath.toLowerCase();
  const hash = window.location.hash.toLowerCase();

  // Chuyển hướng nếu vào /promotions
  if (path === "/promotions" || hash.includes("promotions")) {
    if (window.history && window.history.replaceState) {
      window.history.replaceState(null, "", "/");
    }
  }

  // Route trực tiếp đến /rooms/:id
  if (path.startsWith("/rooms/")) {
    const rawParts = rawPath.split("/rooms/");
    const targetRoomId = rawParts[1] ? rawParts[1].split("/")[0].trim() : "";
    if (targetRoomId && typeof openRoomDetailView === "function") {
      openRoomDetailView(targetRoomId);
      return;
    }
  }

  // Route /select-role — chỉ cho Demo Account
  if (path === "/select-role" || hash.includes("select-role")) {
    if (!state.user) {
      navigateTo("auth");
      return;
    }
    if (!isDemoAccount(state.user)) {
      // Tài khoản thật không được phép tự chọn role — redirect theo role DB
      navigateByRealUserRole(state.user.role);
      return;
    }
    navigateTo("select-role");
    return;
  }

  if (state.user) {
    // Đã đăng nhập — không giữ người dùng trên /auth
    if (path === "/auth" || path === "/login" || hash.includes("auth") || hash.includes("login")) {
      if (window.history && window.history.replaceState) {
        window.history.replaceState(null, "", "/");
      }
    }

    if (path === "/checkout" || hash.includes("checkout")) {
      navigateTo("checkout");
    } else if (path === "/bookings" || hash.includes("bookings")) {
      navigateTo("bookings");
    } else if (path === "/admin" || hash.includes("admin")) {
      const eff = getEffectiveRole();
      if (eff === COZY_ROLES.ADMIN) {
        navigateTo("admin");
      } else {
        showToast("Chỉ Quản trị viên hệ thống mới có quyền truy cập.", "warning");
        navigateTo("home");
      }
    } else if (path === "/operations" || hash.includes("operations")) {
      const eff = getEffectiveRole();
      if (eff === COZY_ROLES.ADMIN) {
        navigateTo("admin");
      } else if (eff && eff !== COZY_ROLES.CUSTOMER) {
        navigateTo("operations");
      } else if (isDemoAccount(state.user) && !state.activeRole) {
        // Demo chưa chọn role — bắt chọn
        navigateTo("select-role");
      } else {
        navigateTo("home");
      }
    } else if (isDemoAccount(state.user) && !state.activeRole) {
      // Demo Account chưa chọn role — bất buộc chọn
      navigateTo("select-role");
    } else if (isDemoAccount(state.user) && state.activeRole) {
      // Demo đã có activeRole — điều hướng theo role đó
      navigateByActiveRole();
    } else {
      // Tài khoản thật — điều hướng thẳng theo role DB
      navigateByRealUserRole(state.user.role);
    }
  } else if (path === "/auth" || path === "/login" || path === "/register" || path === "/forgot-password" || hash.includes("auth") || hash.includes("login")) {
    navigateTo("auth");
    if (path === "/register" || hash.includes("register")) switchAuthTab("register");
    else if (path === "/forgot-password" || hash.includes("forgot")) switchAuthTab("forgot");
    else switchAuthTab("login");
  } else if (path === "/checkout" || hash.includes("checkout")) {
    navigateTo("checkout");
  } else {
    // Khách chưa đăng nhập — xem trang chủ
    navigateTo("home");
  }
});

/**
 * Điều hướng tài khoản thật thẳng theo role từ DB.
 * KHÔNG đi qua select-role.
 * @param {string} rawRole - role từ res.user.role (chưa normalize)
 */
function navigateByRealUserRole(rawRole) {
  const normalized = normalizeRole(rawRole);
  if (!normalized || normalized === COZY_ROLES.CUSTOMER) {
    navigateTo("home");
  } else if (normalized === COZY_ROLES.ADMIN) {
    navigateTo("admin");
  } else {
    navigateTo("operations");
  }
}

/**
 * Điều hướng tới khu vực chức năng phù hợp với activeRole hiện tại (Demo Account).
 */
function navigateByActiveRole() {
  const role = getEffectiveRole();
  if (!role) {
    navigateTo("select-role");
    return;
  }
  if (role === COZY_ROLES.CUSTOMER) {
    navigateTo("home");
  } else if (role === COZY_ROLES.ADMIN) {
    navigateTo("admin");
  } else {
    // Tất cả staff roles khác → operations
    navigateTo("operations");
  }
}

/**
 * Áp dụng quyền theo activeRole mới đã chọn, cập nhật UI và điều hướng.
 * Gọi sau khi người dùng nhấn "Tiếp tục" trên màn hình select-role.
 * @param {string} selectedRole - Role được chọn từ màn hình select-role
 */
function applyRolePermissions(selectedRole) {
  setActiveRole(selectedRole);
  updateAuthUI();

  // Cập nhật hiển thị tab ops nếu đang mở
  if (typeof setupOpsRoleTabs === "function" && state.activeTab === "operations") {
    setupOpsRoleTabs();
  }

  navigateByActiveRole();
}

function setupNavigation() {
  document.querySelectorAll("[data-nav]").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      const target = btn.getAttribute("data-nav");

      // Kiểm tra quyền khi vào các trang cá nhân / vận hành / admin
      if (!state.user && !state.isGuest && (target === "bookings" || target === "profile" || target === "operations" || target === "admin")) {
        showToast("Vui lòng đăng nhập để truy cập tính năng này.", "warning");
        navigateTo("auth");
        return;
      }

      // Kiểm tra quyền vào admin
      if (target === "admin" && state.user) {
        const eff = getEffectiveRole();
        if (eff !== COZY_ROLES.ADMIN) {
          showToast("Chỉ Quản trị viên hệ thống mới có quyền truy cập khu vực này.", "warning");
          return;
        }
      }

      // Kiểm tra quyền vào operations theo effective role
      if (target === "operations" && state.user) {
        const eff = getEffectiveRole();
        if (eff === COZY_ROLES.ADMIN) {
          navigateTo("admin");
          return;
        }
        if (!eff || eff === COZY_ROLES.CUSTOMER) {
          showToast("Vai trò hiện tại không có quyền vào khu vực vận hành.", "warning");
          return;
        }
      }

      navigateTo(target);
    });
  });

  // Account dropdown
  const accountTrigger = document.getElementById("account-trigger");
  if (accountTrigger) {
    accountTrigger.addEventListener("click", (e) => toggleAccountMenu(e));
  }

  // Đóng account dropdown / mobile menu khi bấm ra ngoài
  document.addEventListener("click", (e) => {
    const accountMenu = document.getElementById("nav-auth-user");
    if (accountMenu && !accountMenu.contains(e.target)) closeAccountMenu();

    const mobilePanel = document.getElementById("mobile-nav-panel");
    const mobileToggle = document.getElementById("mobile-menu-toggle");
    if (mobilePanel && mobilePanel.classList.contains("open")) {
      if (!mobilePanel.contains(e.target) && e.target !== mobileToggle && !mobileToggle?.contains(e.target)) {
        closeMobileMenu();
      }
    }
  });
}

function toggleAccountMenu(e) {
  if (e) e.stopPropagation();
  const dropdown = document.getElementById("account-dropdown");
  const trigger = document.getElementById("account-trigger");
  if (!dropdown || !trigger) return;
  const willOpen = !dropdown.classList.contains("open");
  closeAccountMenu();
  closeMobileMenu();
  if (willOpen) {
    dropdown.classList.add("open");
    trigger.classList.add("open");
  }
}

function closeAccountMenu() {
  document.getElementById("account-dropdown")?.classList.remove("open");
  document.getElementById("account-trigger")?.classList.remove("open");
}

function toggleMobileMenu() {
  const panel = document.getElementById("mobile-nav-panel");
  if (!panel) return;
  closeAccountMenu();
  panel.classList.toggle("open");
}

function closeMobileMenu() {
  document.getElementById("mobile-nav-panel")?.classList.remove("open");
}

function navigateTo(viewName) {
  state.activeTab = viewName;
  closeAccountMenu();
  closeMobileMenu();

  // Auth mode và select-role mode: Ẩn Navbar và Floating Chat Button
  const isAuth = (viewName === "auth");
  const isSelectRole = (viewName === "select-role");
  const isHideNavMode = isAuth || isSelectRole;

  if (isHideNavMode) {
    document.body.classList.add("auth-mode");
  } else {
    document.body.classList.remove("auth-mode");
  }

  const navbar = document.querySelector(".navbar");
  if (navbar) {
    navbar.style.display = isHideNavMode ? "none" : "";
  }

  // Đồng bộ URL trình duyệt
  if (window.history && window.history.pushState) {
    const currentPath = window.location.pathname;
    const targetPath = (viewName === "home") ? "/" : `/${viewName}`;
    if (currentPath !== targetPath && (currentPath !== "/" || targetPath !== "/home")) {
      window.history.pushState(null, "", targetPath);
    }
  }

  // Cập nhật trạng thái active cho navbar link
  document.querySelectorAll(".nav-link, .mobile-nav-link").forEach(l => {
    if (l.getAttribute("data-nav") === viewName) l.classList.add("active");
    else l.classList.remove("active");
  });

  // Ẩn/Hiện các views
  const views = [
    "view-auth",
    "view-home",
    "view-checkout",
    "view-bookings",
    "view-operations",
    "view-admin",
    "view-profile",
    "view-room-detail",
    "view-select-role",
  ];
  views.forEach(v => {
    const el = document.getElementById(v);
    if (el) {
      if (v === `view-${viewName}`) {
        el.style.display = "block";
      } else {
        el.style.display = "none";
      }
    }
  });

  // Khi mở view auth: làm sạch form đăng nhập, loại bỏ autofill lưu sẵn
  if (viewName === "auth" && typeof resetLoginForm === "function") {
    resetLoginForm();
    setTimeout(resetLoginForm, 60);
    setTimeout(resetLoginForm, 250);
  }

  // Kiểm soát hiển thị Cozy AI Widget
  const aiToggleBtn = document.getElementById("ai-widget-toggle");
  const aiWidgetBox = document.getElementById("ai-widget-box");
  if (isHideNavMode) {
    if (aiToggleBtn) aiToggleBtn.style.display = "none";
    if (aiWidgetBox) {
      aiWidgetBox.classList.remove("active");
      aiWidgetBox.style.display = "none";
    }
  } else {
    if (aiToggleBtn) aiToggleBtn.style.display = "";
    if (aiWidgetBox && !aiWidgetBox.classList.contains("active")) {
      aiWidgetBox.style.display = "none";
    }
  }

  // Tải dữ liệu tương ứng khi mở tab
  if (viewName === "bookings") loadUserBookings();
  else if (viewName === "operations") loadOperationsDashboard();
  else if (viewName === "admin" && typeof loadAdminPortal === "function") loadAdminPortal();
  else if (viewName === "profile") loadProfile();
  else if (viewName === "checkout") renderCheckoutPage();
  else if (viewName === "select-role") renderSelectRolePage();

  window.scrollTo({ top: 0, behavior: "smooth" });
}

/**
 * Render màn hình Chọn vai trò (Training Mode).
 * Hiển thị 6 role card, pre-select nếu đã có activeRole.
 */
function renderSelectRolePage() {
  if (!state.user) {
    navigateTo("auth");
    return;
  }

  // Bảo vệ: Tài khoản thật không được tự chọn role để vượt quyền
  if (!isDemoAccount(state.user)) {
    showToast("Tài khoản của bạn đã được gán vai trò trong hệ thống.", "info");
    navigateByRealUserRole(state.user.role);
    return;
  }

  const container = document.getElementById("view-select-role");
  if (!container) return;

  const currentRole = state.activeRole || "";

  const roleCards = [
    {
      key: COZY_ROLES.CUSTOMER,
      icon: `<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`,
      name: "Khách hàng",
      desc: "Tìm phòng, AI tư vấn, đặt phòng và quản lý lượt lưu trú.",
      features: ["Tìm kiếm và xem chi tiết phòng", "AI tư vấn và hỗ trợ", "Đặt phòng và thanh toán", "Xem và hủy lượt đặt", "Gia hạn và đánh giá", "Quản lý hồ sơ cá nhân"],
      scope: "Dữ liệu tài khoản cá nhân",
    },
    {
      key: COZY_ROLES.RECEPTIONIST,
      icon: `<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>`,
      name: "Lễ tân",
      desc: "Tiếp nhận và theo dõi hoạt động lưu trú tại chi nhánh được phân công.",
      features: ["Danh sách và tra cứu lượt đặt", "Check-in / Check-out", "Theo dõi khách đang lưu trú", "Cảnh báo quá giờ chưa checkout", "Theo dõi phản hồi chi nhánh", "Chuyển vượt thẩm quyền lên Quản lý"],
      scope: "Chi nhánh được phân công",
    },
    {
      key: COZY_ROLES.HOUSEKEEPING,
      icon: `<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21h18"/><path d="M3 10h18"/><path d="M5 6l7-3 7 3"/><path d="M4 10v11"/><path d="M20 10v11"/><path d="M8 14v3"/><path d="M12 14v3"/><path d="M16 14v3"/></svg>`,
      name: "Nhân viên buồng phòng",
      desc: "Theo dõi phòng cần xử lý và cập nhật trạng thái vệ sinh, vận hành.",
      features: ["Danh sách phòng cần dọn", "Bắt đầu và cập nhật tiến độ vệ sinh", "Hoàn tất và chuyển phòng Sẵn sàng", "Kiểm tra tình trạng phòng", "Ghi nhận bảo trì / bất thường"],
      scope: "Chi nhánh được phân công",
    },
    {
      key: COZY_ROLES.ACCOUNTANT,
      icon: `<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>`,
      name: "Kế toán",
      desc: "Đối soát giao dịch và theo dõi dữ liệu tài chính toàn chuỗi.",
      features: ["Danh sách giao dịch và thanh toán", "Hoàn tiền và phụ thu", "Đối soát giao dịch", "Theo dõi trạng thái giao dịch", "Báo cáo doanh thu theo quyền"],
      scope: "Toàn chuỗi 3 chi nhánh",
    },
    {
      key: COZY_ROLES.MANAGER,
      icon: `<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>`,
      name: "Quản lý chuỗi",
      desc: "Theo dõi hoạt động toàn chuỗi và cấu hình các chính sách nghiệp vụ.",
      features: ["Dashboard và thống kê tổng quan", "Doanh thu và công suất phòng", "Quản lý thông tin và giá phòng", "Khung giờ, khuyến mãi, chính sách", "Xử lý phản hồi vượt thẩm quyền", "Theo dõi cả 3 chi nhánh"],
      scope: "Toàn chuỗi 3 chi nhánh",
    },
    {
      key: COZY_ROLES.ADMIN,
      icon: `<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M4.93 4.93a10 10 0 0 0 0 14.14"/><path d="M12 2a10 10 0 0 1 10 10 10 10 0 0 1-10 10A10 10 0 0 1 2 12 10 10 0 0 1 12 2z"/></svg>`,
      name: "Quản trị viên",
      desc: "Quản lý tài khoản, vai trò và phạm vi truy cập hệ thống.",
      features: ["Danh sách và trạng thái tài khoản", "Mở khóa tài khoản", "Gán vai trò và phạm vi chi nhánh", "Quản lý quyền truy cập", "Theo dõi thông tin quản trị"],
      scope: "Toàn hệ thống",
    },
  ];

  const cardsHtml = roleCards.map(r => {
    const isSelected = currentRole === r.key;
    return `
      <div class="role-card${isSelected ? " selected" : ""}"
           data-role="${r.key}"
           onclick="selectRoleCard(this, '${r.key}')">
        ${isSelected ? `<span class="role-card-check">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
        </span>` : ""}
        <div class="role-card-icon">${r.icon}</div>
        <div class="role-card-name">${r.name}</div>
        <div class="role-card-desc">${r.desc}</div>
        <ul class="role-card-features">
          ${r.features.map(f => `<li>${f}</li>`).join("")}
        </ul>
        <div class="role-card-scope">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/></svg>
          ${r.scope}
        </div>
      </div>
    `;
  }).join("");

  container.innerHTML = `
    <div class="select-role-page">
      <div class="select-role-header">
        <div class="select-role-logo" onclick="navigateTo(state.user ? 'home' : 'auth')" style="cursor:pointer;" title="Trang chủ">
          <img src="/static/images/cozyhome-logo.png" alt="CozyHome" class="select-role-logo-img" />
          <span class="select-role-brand-name">Cozy<span>Home</span></span>
        </div>
        <h1 class="select-role-title">Chọn vai trò để trải nghiệm</h1>
        <p class="select-role-subtitle">
          Chọn vai trò nghiệp vụ bạn muốn sử dụng trong phiên trải nghiệm. Mỗi vai trò được cung cấp nhóm chức năng và phạm vi dữ liệu phù hợp với nghiệp vụ của CozyHome.
        </p>
        <p class="select-role-hint">Bạn có thể đổi vai trò khác sau khi đăng nhập.</p>
      </div>

      <div class="role-card-grid" id="role-card-grid">
        ${cardsHtml}
      </div>

      <div class="select-role-footer">
        <button
          class="btn btn-primary role-continue-btn"
          id="btn-continue-role"
          onclick="confirmRoleSelection()"
          ${currentRole ? "" : "disabled"}
        >
          Tiếp tục với vai trò này
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="margin-left:6px;"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
        </button>
        <div class="select-role-user-info">
          <span>Đăng nhập với tư cách: <strong>${state.user.full_name}</strong></span>
          <span class="select-role-sep">-</span>
          <a href="#" onclick="logout(); return false;" class="select-role-logout">Đăng xuất</a>
        </div>
      </div>
    </div>
  `;

  // Lưu role đang được chọn tạm thời (chưa apply)
  container._pendingRole = currentRole;
}

let _selectRolePending = null;

function selectRoleCard(cardEl, roleKey) {
  // Bỏ selected của card cũ
  document.querySelectorAll(".role-card").forEach(c => {
    c.classList.remove("selected");
    const check = c.querySelector(".role-card-check");
    if (check) check.remove();
  });

  // Chọn card mới
  cardEl.classList.add("selected");

  // Thêm check icon nếu chưa có
  if (!cardEl.querySelector(".role-card-check")) {
    const checkEl = document.createElement("span");
    checkEl.className = "role-card-check";
    checkEl.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`;
    cardEl.prepend(checkEl);
  }

  _selectRolePending = roleKey;

  // Enable nút tiếp tục
  const btn = document.getElementById("btn-continue-role");
  if (btn) btn.disabled = false;
}

function confirmRoleSelection() {
  if (!_selectRolePending) {
    showToast("Vui lòng chọn một vai trò trước.", "warning");
    return;
  }

  // Validate role hợp lệ
  if (!COZY_ROLE_LIST.includes(_selectRolePending)) {
    showToast("Vai trò không hợp lệ.", "error");
    return;
  }

  applyRolePermissions(_selectRolePending);
  showToast(`Đã chọn vai trò: ${_selectRolePending}`, "success");
}

function makeRadioGroupToggleable(groupName, onDeselect) {
  const radios = document.querySelectorAll(`input[type="radio"][name="${groupName}"]`);
  radios.forEach(radio => {
    let wasChecked = false;

    const setPrevState = () => {
      wasChecked = radio.checked;
    };

    radio.addEventListener("pointerdown", setPrevState);
    radio.addEventListener("mousedown", setPrevState);
    radio.addEventListener("touchstart", setPrevState, { passive: true });

    const parentLabel = radio.closest(".filter-chip") || radio.parentElement;
    if (parentLabel && parentLabel !== radio) {
      parentLabel.addEventListener("pointerdown", setPrevState);
      parentLabel.addEventListener("mousedown", setPrevState);
      parentLabel.addEventListener("touchstart", setPrevState, { passive: true });
    }

    radio.addEventListener("keydown", (e) => {
      if (e.key === " " || e.key === "Enter") {
        wasChecked = radio.checked;
      }
    });

    radio.addEventListener("click", (e) => {
      if (wasChecked && radio.value !== "") {
        e.preventDefault();
        radio.checked = false;
        const def = document.querySelector(`input[type="radio"][name="${groupName}"][value=""]`);
        if (def) def.checked = true;
        if (typeof onDeselect === "function") {
          onDeselect();
        }
      }
      wasChecked = false;
    });
  });
}

function setupEventListeners() {
  // Form Tìm kiếm phòng
  const searchForm = document.getElementById("search-form");
  if (searchForm) {
    searchForm.addEventListener("submit", (e) => {
      e.preventDefault();
      performSearch();
    });
  }

  // Sidebar filters (chỉ các đặc tính phòng: Hạng phòng, Tiện nghi, Loại giường)
  ["filter-type-std", "filter-type-dlx", "filter-type-fam",
   "filter-amen-bon-tam", "filter-amen-ban-cong", "filter-amen-view-ho",
   "filter-amen-bep-mini", "filter-amen-minibar", "filter-amen-wifi",
   "filter-bed-double", "filter-bed-large", "filter-bed-twin"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener("change", () => applyFiltersFromSidebar());
  });

  const areaRadios = document.querySelectorAll('input[name="filter-area"]');
  areaRadios.forEach(r => {
    r.addEventListener("change", () => applyFiltersFromSidebar());
  });

  // Hỗ trợ nhấn lại nút radio diện tích đang chọn để bỏ chọn
  makeRadioGroupToggleable("filter-area", () => {
    applyFiltersFromSidebar();
  });

  // Min/max price filter (debounced)
  const minPriceInput = document.getElementById("filter-min-price");
  const maxPriceInput = document.getElementById("filter-max-price");
  let priceTimer;
  [minPriceInput, maxPriceInput].forEach(el => {
    if (el) {
      el.addEventListener("input", () => {
        clearTimeout(priceTimer);
        priceTimer = setTimeout(() => applyFiltersFromSidebar(), 600);
      });
    }
  });

  // Sắp xếp
  const sortSelect = document.getElementById("sort-select");
  if (sortSelect) sortSelect.addEventListener("change", () => applyFiltersFromSidebar());

  // Chuyển tab trong trang Auth
  const authTabBtns = document.querySelectorAll(".auth-page-tab-btn");
  authTabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      const tab = btn.getAttribute("data-authtab");
      switchAuthTab(tab);
    });
  });

  // Form Đăng nhập
  const loginForm = document.getElementById("form-login");
  if (loginForm) {
    loginForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const email = document.getElementById("login-email")?.value.trim();
      const pass = document.getElementById("login-pass")?.value;
      const btn = document.getElementById("btn-submit-login");
      handleLogin(email, pass, btn);
    });
  }

  // Form Đăng ký Bước 1
  const regForm = document.getElementById("form-register");
  if (regForm) {
    regForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const fullName = document.getElementById("reg-fullname")?.value.trim();
      const phone = document.getElementById("reg-phone")?.value.trim();
      const email = document.getElementById("reg-email")?.value.trim();
      const pass = document.getElementById("reg-password")?.value;
      const btn = document.getElementById("btn-submit-reg-init");
      handleRegisterInit({ full_name: fullName, phone, email, password: pass }, btn);
    });
  }

  // Form Đăng ký Bước 2 (Xác thực OTP)
  const btnVerifyRegOtp = document.getElementById("btn-verify-reg-otp");
  if (btnVerifyRegOtp) {
    btnVerifyRegOtp.addEventListener("click", () => {
      const otp = document.getElementById("reg-otp-input")?.value.trim();
      handleRegisterComplete(otp, btnVerifyRegOtp);
    });
  }

  // Form Cập nhật Profile
  const profileForm = document.getElementById("form-edit-profile");
  if (profileForm) {
    profileForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = document.getElementById("edit-profile-name")?.value.trim();
      const phone = document.getElementById("edit-profile-phone")?.value.trim();
      try {
        const res = await apiFetch("/api/auth/profile", {
          method: "PUT",
          body: { user_id: state.user.id, full_name: name, phone },
        });
        saveUserToStorage(res.user);
        updateAuthUI();
        showToast(res.message || "Đã cập nhật thông tin cá nhân!", "success");
        loadProfile();
      } catch (err) {}
    });
  }

  // Form Đổi Mật khẩu
  const changePassForm = document.getElementById("form-change-password");
  if (changePassForm) {
    changePassForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const oldPass = document.getElementById("change-pass-old")?.value;
      const newPass = document.getElementById("change-pass-new")?.value;
      try {
        const res = await apiFetch("/api/auth/change-password", {
          method: "POST",
          body: { user_id: state.user.id, old_password: oldPass, new_password: newPass },
        });
        showToast(res.message, "success");
        changePassForm.reset();
      } catch (err) {}
    });
  }

  // Back / Forward trình duyệt
  window.addEventListener("popstate", () => {
    const rawP = window.location.pathname;
    const p = rawP.toLowerCase();
    if (p.startsWith("/rooms/")) {
      const parts = rawP.split("/rooms/");
      const rid = parts[1] ? parts[1].split("/")[0].trim() : "";
      if (rid && typeof openRoomDetailView === "function") {
        openRoomDetailView(rid);
        return;
      }
    }
    if (p === "/select-role") {
      if (state.user) navigateTo("select-role");
      else navigateTo("auth");
    } else if (p === "/checkout") navigateTo("checkout");
    else if (p === "/bookings") navigateTo("bookings");
    else if (p === "/operations") navigateTo("operations");
    else if (p === "/profile") navigateTo("profile");
    else if (p === "/auth" || p === "/login") navigateTo("auth");
    else navigateTo("home");
  });
}

// Áp dụng bộ lọc sidebar vào URL và tìm kiếm lại
// Áp dụng bộ lọc phòng (sidebar) và tìm kiếm lại
function applyFiltersFromSidebar() {
  const types = [];
  if (document.getElementById("filter-type-std")?.checked) types.push("Standard");
  if (document.getElementById("filter-type-dlx")?.checked) types.push("Deluxe");
  if (document.getElementById("filter-type-fam")?.checked) types.push("Family");

  const amenities = [];
  const amenMap = {
    "filter-amen-bon-tam": "bồn tắm",
    "filter-amen-ban-cong": "ban công",
    "filter-amen-view-ho": "view hồ",
    "filter-amen-bep-mini": "bếp mini",
    "filter-amen-minibar": "minibar",
    "filter-amen-wifi": "wifi",
  };
  Object.entries(amenMap).forEach(([id, label]) => {
    if (document.getElementById(id)?.checked) amenities.push(label);
  });

  const areaRange = document.querySelector('input[name="filter-area"]:checked')?.value || "";
  const bedTypes = [];
  if (document.getElementById("filter-bed-double")?.checked) bedTypes.push("1 giường đôi");
  if (document.getElementById("filter-bed-large")?.checked) bedTypes.push("1 giường đôi lớn");
  if (document.getElementById("filter-bed-twin")?.checked) bedTypes.push("3 giường");

  const minPrice = document.getElementById("filter-min-price")?.value || "";
  const maxPrice = document.getElementById("filter-max-price")?.value || "";
  const sortBy = document.getElementById("sort-select")?.value || "popularity";

  state.sidebarFilters = { types, amenities, minPrice, maxPrice, sortBy, areaRange, bedTypes };
  performSearch();
}

// Đặt lại các bộ lọc phòng ở Sidebar (giữ nguyên tiêu chí tìm kiếm ngày/giờ/chi nhánh ở thanh tìm kiếm)
function resetSidebarFilters() {
  ["filter-type-std","filter-type-dlx","filter-type-fam",
   "filter-amen-bon-tam","filter-amen-ban-cong","filter-amen-view-ho",
   "filter-amen-bep-mini","filter-amen-minibar","filter-amen-wifi",
   "filter-bed-double","filter-bed-large","filter-bed-twin"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.checked = false;
  });
  const areaRadios = document.querySelectorAll('input[name="filter-area"]');
  areaRadios.forEach(r => { r.checked = (r.value === ""); });
  const minEl = document.getElementById("filter-min-price");
  const maxEl = document.getElementById("filter-max-price");
  if (minEl) minEl.value = "";
  if (maxEl) maxEl.value = "";
  const sortEl = document.getElementById("sort-select");
  if (sortEl) sortEl.value = "popularity";
  state.sidebarFilters = {};
  performSearch();
}

function resetFilters() {
  resetSidebarFilters();
}
