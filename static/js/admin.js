// ================================================================
// CozyHome System Administration Portal (Vai trò Quản trị viên)
// Tập trung vào: Dashboard, Quản lý tài khoản, Phân quyền RBAC,
// Tra cứu vận hành Read-only, Nhật ký Audit Log, Cấu hình bảo mật.
// ================================================================

let adminCurrentTab = "dashboard";
let adminUsersCache = [];
let adminAuditLogsCache = [];
let adminAuditTotal = 0;
let adminAuditPage = 0;
const ADMIN_PAGE_SIZE = 25;

// Ma trận quyền mẫu phục vụ live preview
const PERMISSION_PREVIEW_MAP = {
  "Quản trị viên": [
    { name: "Dashboard quản trị toàn hệ thống", granted: true },
    { name: "Quản lý tài khoản và phân quyền", granted: true },
    { name: "Tra cứu vận hành (Read-only)", granted: true },
    { name: "Xem nhật ký hệ thống (Audit Log)", granted: true },
    { name: "Cấu hình bảo mật hệ thống", granted: true },
    { name: "Thực hiện check-in / check-out", granted: false, reason: "Nghiệp vụ thuộc Lễ tân" },
    { name: "Cập nhật trạng thái buồng phòng", granted: false, reason: "Nghiệp vụ thuộc Buồng phòng" },
    { name: "Đối soát và xác nhận tài chính", granted: false, reason: "Nghiệp vụ thuộc Kế toán" },
    { name: "Cấu hình khung giờ và chính sách phòng", granted: false, reason: "Nghiệp vụ thuộc Quản lý chuỗi" },
  ],
  "Lễ tân": [
    { name: "Xem lượt đặt trong chi nhánh", granted: true },
    { name: "Thực hiện check-in cho khách", granted: true },
    { name: "Thực hiện check-out và chuyển dọn phòng", granted: true },
    { name: "Chuyển khiếu nại lên Quản lý chuỗi", granted: true },
    { name: "Xem dữ liệu chi nhánh khác", granted: false, reason: "Giới hạn phạm vi chi nhánh" },
    { name: "Cập nhật dọn phòng thay buồng phòng", granted: false },
    { name: "Đối soát giao dịch kế toán", granted: false },
    { name: "Quản trị người dùng và phân quyền", granted: false },
  ],
  "Buồng phòng": [
    { name: "Xem danh sách phòng cần dọn tại chi nhánh", granted: true },
    { name: "Cập nhật dọn phòng (Cần dọn → Sẵn sàng)", granted: true },
    { name: "Báo trạng thái phòng bất thường / bảo trì", granted: true },
    { name: "Xem đơn đặt phòng của khách", granted: false },
    { name: "Check-in / check-out", granted: false },
    { name: "Quản trị tài khoản", granted: false },
  ],
  "Nhân viên buồng phòng": [
    { name: "Xem danh sách phòng cần dọn tại chi nhánh", granted: true },
    { name: "Cập nhật dọn phòng (Cần dọn → Sẵn sàng)", granted: true },
    { name: "Báo trạng thái phòng bất thường / bảo trì", granted: true },
    { name: "Xem đơn đặt phòng của khách", granted: false },
    { name: "Check-in / check-out", granted: false },
    { name: "Quản trị tài khoản", granted: false },
  ],
  "Kế toán": [
    { name: "Xem giao dịch toàn chuỗi", granted: true },
    { name: "Đối soát thanh toán và hoàn tiền", granted: true },
    { name: "Theo dõi tình trạng doanh thu", granted: true },
    { name: "Check-in / check-out", granted: false },
    { name: "Cập nhật dọn phòng", granted: false },
    { name: "Quản trị tài khoản", granted: false },
  ],
  "Quản lý": [
    { name: "Dashboard kinh doanh toàn chuỗi", granted: true },
    { name: "Cấu hình nhóm khung giờ N1-N4", granted: true },
    { name: "Xử lý khiếu nại từ lễ tân", granted: true },
    { name: "Giám sát hoạt động 3 chi nhánh", granted: true },
    { name: "Check-in / check-out thay lễ tân", granted: false },
    { name: "Đối soát thay kế toán", granted: false },
    { name: "Phân quyền vai trò người dùng", granted: false, reason: "Nghiệp vụ thuộc Quản trị viên" },
  ],
  "Quản lý chuỗi": [
    { name: "Dashboard kinh doanh toàn chuỗi", granted: true },
    { name: "Cấu hình nhóm khung giờ N1-N4", granted: true },
    { name: "Xử lý khiếu nại từ lễ tân", granted: true },
    { name: "Giám sát hoạt động 3 chi nhánh", granted: true },
    { name: "Check-in / check-out thay lễ tân", granted: false },
    { name: "Đối soát thay kế toán", granted: false },
    { name: "Phân quyền vai trò người dùng", granted: false, reason: "Nghiệp vụ thuộc Quản trị viên" },
  ],
  "Khách hàng": [
    { name: "Tìm kiếm và đặt phòng", granted: true },
    { name: "Tư vấn phòng bằng AI", granted: true },
    { name: "Xem và hủy đơn đặt theo chính sách", granted: true },
    { name: "Gửi đánh giá sau khi hoàn tất", granted: true },
    { name: "Truy cập khu vực vận hành nội bộ", granted: false },
  ],
};

// ================================================================
// Khởi tạo và điều hướng các phân hệ Admin
// ================================================================
async function loadAdminPortal() {
  const role = getEffectiveRole();
  if (role !== COZY_ROLES.ADMIN) {
    showToast("Bạn không có quyền truy cập cổng Quản trị hệ thống.", "error");
    navigateTo("home");
    return;
  }

  // Cập nhật tên Admin trên header
  const adminNameEl = document.getElementById("admin-header-name");
  const adminEmailEl = document.getElementById("admin-header-email");
  if (adminNameEl && state.user) adminNameEl.textContent = state.user.full_name;
  if (adminEmailEl && state.user) adminEmailEl.textContent = state.user.email;

  switchAdminTab(adminCurrentTab);
}

function switchAdminTab(tabName) {
  adminCurrentTab = tabName;

  // Cập nhật active sidebar tab
  document.querySelectorAll(".admin-sidebar-item").forEach(item => {
    if (item.getAttribute("data-admintab") === tabName) {
      item.classList.add("active");
    } else {
      item.classList.remove("active");
    }
  });

  // Ẩn hiện các pane
  document.querySelectorAll(".admin-tab-pane").forEach(pane => {
    if (pane.id === `admin-pane-${tabName}`) {
      pane.style.display = "block";
    } else {
      pane.style.display = "none";
    }
  });

  // Tải dữ liệu tương ứng
  if (tabName === "dashboard") loadAdminDashboard();
  else if (tabName === "users" || tabName === "roles") {
    adminCurrentTab = "users";
    const s = document.getElementById("adm-user-filter-search") || document.getElementById("adm-user-search");
    if (s && !s.dataset.userTyped) {
      s.value = "";
    }
    loadAdminUsers();
  }
  else if (tabName === "operations") loadAdminOperationsTab("rooms");
  else if (tabName === "audit") loadAdminAuditLogs(0);
  else if (tabName === "security") loadAdminSecuritySettings();
}

// ================================================================
// 1. DASHBOARD QUẢN TRỊ (READ-ONLY)
// ================================================================
async function loadAdminDashboard() {
  try {
    const res = await apiFetch("/api/admin/dashboard");
    const data = res.data;
    if (!data) return;

    // Users stats
    document.getElementById("adm-stat-total-users").textContent = data.users.total;
    document.getElementById("adm-stat-active-users").textContent = data.users.active;
    document.getElementById("adm-stat-locked-users").textContent = data.users.locked;
    document.getElementById("adm-stat-disabled-users").textContent = data.users.disabled;

    // Phân bổ role (Dạng thẻ khối danh mục sang trọng, không dùng thanh chỉ mức độ)
    const roleList = document.getElementById("adm-role-distribution");
    if (roleList) {
      const roles = data.users.by_role || {};
      roleList.innerHTML = Object.entries(roles).map(([r, count]) => {
        return `
          <div class="adm-dist-item-tile">
            <div class="adm-dist-item-left">
              <span class="adm-dist-dot role"></span>
              <span class="adm-dist-name">${r}</span>
            </div>
            <div class="adm-dist-item-right">
              <span class="adm-dist-badge role"><b>${count}</b> tài khoản</span>
            </div>
          </div>
        `;
      }).join("");
    }

    // Phân bổ branch
    const branchList = document.getElementById("adm-branch-distribution");
    if (branchList) {
      const branches = data.users.by_branch || {};
      const BRANCH_LABELS = {
        "BT": "Chi nhánh Bến Thành",
        "TD": "Chi nhánh Thảo Điền",
        "PMH": "Chi nhánh Phú Mỹ Hưng",
        "TOÀN CHUỖI": "Văn phòng quản trị toàn chuỗi",
        "null": "Văn phòng quản trị toàn chuỗi"
      };
      branchList.innerHTML = Object.entries(branches).map(([b, count]) => {
        const label = BRANCH_LABELS[b] || (b ? `Chi nhánh ${b}` : "Văn phòng quản trị toàn chuỗi");
        return `
          <div class="adm-dist-item-tile">
            <div class="adm-dist-item-left">
              <span class="adm-dist-dot branch"></span>
              <span class="adm-dist-name">${label}</span>
            </div>
            <div class="adm-dist-item-right">
              <span class="adm-dist-badge branch"><b>${count}</b> nhân sự</span>
            </div>
          </div>
        `;
      }).join("");
    }

    // Room stats
    document.getElementById("adm-room-total").textContent = data.rooms.total;
    document.getElementById("adm-room-ready").textContent = data.rooms.ready;
    document.getElementById("adm-room-staying").textContent = data.rooms.staying;
    document.getElementById("adm-room-cleaning").textContent = data.rooms.cleaning;
    document.getElementById("adm-room-maint").textContent = data.rooms.maintenance;

    // Booking stats
    document.getElementById("adm-bk-total").textContent = data.bookings.total;
    document.getElementById("adm-bk-confirmed").textContent = data.bookings.confirmed;
    document.getElementById("adm-bk-staying").textContent = data.bookings.staying;
    document.getElementById("adm-bk-completed").textContent = data.bookings.completed;
    document.getElementById("adm-bk-cancelled").textContent = data.bookings.cancelled;

    // Transactions stats
    document.getElementById("adm-tx-total").textContent = data.transactions.total;
    document.getElementById("adm-tx-success").textContent = data.transactions.success;
    document.getElementById("adm-tx-pending").textContent = data.transactions.pending_reconciliation;
    document.getElementById("adm-tx-refunds").textContent = data.transactions.refunds;

    // Total audit logs
    const auditCountEl = document.getElementById("adm-stat-audit-count");
    if (auditCountEl) auditCountEl.textContent = data.total_audit_logs;

  } catch (err) {
  }
}

// ================================================================
// 2. QUẢN LÝ TÀI KHOẢN (USER MANAGEMENT)
// ================================================================
let currentPillFilter = "all";

async function loadAdminUsers() {
  const container = document.getElementById("adm-users-table-container");
  if (!container) return;

  const searchInput = document.getElementById("adm-user-filter-search") || document.getElementById("adm-user-search");
  const clearBtn = document.getElementById("adm-search-clear-btn");

  // Ngăn chặn autofill của trình duyệt nếu chưa được người dùng gõ thủ công
  if (searchInput && !searchInput.dataset.userTyped && searchInput.value) {
    if (state.user && searchInput.value.trim().toLowerCase() === state.user.email.toLowerCase()) {
      searchInput.value = "";
    }
  }

  const search = searchInput?.value || "";
  if (clearBtn) {
    clearBtn.style.display = search.trim() ? "block" : "none";
  }
  const role = document.getElementById("adm-user-role-filter")?.value || "";
  const branch = document.getElementById("adm-user-branch-filter")?.value || "";
  const status = document.getElementById("adm-user-status-filter")?.value || "";
  const sort = document.getElementById("adm-user-sort")?.value || "";

  let url = `/api/admin/users?`;
  if (search) url += `search=${encodeURIComponent(search)}&`;
  if (role) url += `role=${encodeURIComponent(role)}&`;
  if (branch) url += `branch_id=${encodeURIComponent(branch)}&`;
  if (status) url += `status=${encodeURIComponent(status)}&`;
  if (sort) url += `sort_by=${encodeURIComponent(sort)}&`;

  try {
    const res = await apiFetch(url);
    adminUsersCache = res.users || [];

    let displayUsers = adminUsersCache;
    if (currentPillFilter === "internal") {
      displayUsers = adminUsersCache.filter(u => u.role !== "Khách hàng");
    }

    let activePill = currentPillFilter;
    if (branch === "NONE") activePill = "chain";
    else if (branch === "CUSTOMER" || role === "Khách hàng") activePill = "customer";
    else if (["BT", "TD", "PMH"].includes(branch)) activePill = branch;
    else if (!branch && !role && currentPillFilter !== "internal") activePill = "all";

    document.querySelectorAll(".adm-user-filter-pill").forEach(btn => {
      if (btn.getAttribute("data-pill") === activePill) btn.classList.add("active");
      else btn.classList.remove("active");
    });

    renderAdminUsersTable(displayUsers);
  } catch (err) {
  }
}

function filterByPill(pillKey) {
  currentPillFilter = pillKey;

  document.querySelectorAll(".adm-user-filter-pill").forEach(btn => {
    if (btn.getAttribute("data-pill") === pillKey) {
      btn.classList.add("active");
    } else {
      btn.classList.remove("active");
    }
  });

  const s = document.getElementById("adm-user-filter-search") || document.getElementById("adm-user-search");
  const r = document.getElementById("adm-user-role-filter");
  const b = document.getElementById("adm-user-branch-filter");
  const st = document.getElementById("adm-user-status-filter");
  const clearBtn = document.getElementById("adm-search-clear-btn");

  if (s) {
    s.value = "";
    delete s.dataset.userTyped;
  }
  if (clearBtn) clearBtn.style.display = "none";
  if (st) st.value = "";

  if (pillKey === "all" || pillKey === "internal") {
    if (r) r.value = "";
    if (b) b.value = "";
  } else if (pillKey === "BT" || pillKey === "TD" || pillKey === "PMH") {
    if (r) r.value = "";
    if (b) b.value = pillKey;
  } else if (pillKey === "chain") {
    if (r) r.value = "";
    if (b) b.value = "NONE";
  } else if (pillKey === "customer") {
    if (r) r.value = "Khách hàng";
    if (b) b.value = "CUSTOMER";
  }

  loadAdminUsers();
}

function renderAdminUsersTable(users) {
  const container = document.getElementById("adm-users-table-container");
  if (!container) return;

  if (users.length === 0) {
    container.innerHTML = `
      <div style="text-align:center; padding:36px; background:#fff; border-radius:12px; border:1px dashed var(--cozy-border); color:var(--text-muted);">
        <p style="font-size:14px; margin-bottom:10px; font-weight:500;">Không tìm thấy tài khoản nào khớp với điều kiện lọc.</p>
        <button class="btn btn-outline btn-sm" onclick="resetAdminUserFilters()">Đặt lại bộ lọc</button>
      </div>
    `;
    return;
  }

  const ROLE_BADGE_MAP = {
    "Quản trị viên": `<span class="badge badge-role-admin" style="white-space:nowrap !important;">Quản trị viên</span>`,
    "Quản lý": `<span class="badge badge-role-manager" style="white-space:nowrap !important;">Quản lý</span>`,
    "Kế toán": `<span class="badge badge-role-accountant" style="white-space:nowrap !important;">Kế toán</span>`,
    "Lễ tân": `<span class="badge badge-role-receptionist" style="white-space:nowrap !important;">Lễ tân</span>`,
    "Buồng phòng": `<span class="badge badge-role-housekeeping" style="white-space:nowrap !important;">Buồng phòng</span>`,
    "Khách hàng": `<span class="badge badge-role-customer" style="white-space:nowrap !important;">Khách hàng</span>`
  };

  container.innerHTML = `
    <div class="table-responsive" style="border-radius:12px; overflow-x:auto; border:1px solid #ebdcd0; box-shadow:0 1px 4px rgba(45,36,30,0.04); background:#fff;">
      <table class="adm-users-table" style="min-width:1120px; width:100%; border-collapse:separate; border-spacing:0;">
        <thead>
          <tr>
            <th style="width:60px; text-align:center; padding:14px 10px;">ID</th>
            <th style="min-width:160px; padding:14px 14px; cursor:pointer;" onclick="toggleAdminUserSort()" title="Nhấn để sắp xếp danh sách theo thứ tự chữ cái">Họ và tên <span style="font-size:11px; opacity:0.6;">⇅</span></th>
            <th style="min-width:230px; padding:14px 14px;">Email và SĐT</th>
            <th style="min-width:130px; padding:14px 12px; text-align:center;">Vai trò</th>
            <th style="min-width:180px; padding:14px 14px;">Phạm vi chi nhánh</th>
            <th style="min-width:155px; padding:14px 12px; text-align:center;">Trạng thái</th>
            <th style="min-width:165px; padding:14px 14px;">Hoạt động gần nhất</th>
            <th style="min-width:180px; padding:14px 14px; text-align:right;">Thao tác</th>
          </tr>
        </thead>
        <tbody>
          ${users.map(u => {
            const isLocked = (u.status === "LOCKED" || u.locked === 1);
            const isDisabled = (u.status === "DISABLED" || u.active === 0);

            let statusBadge = `<span class="badge badge-success" style="white-space:nowrap !important;"><span style="width:6px; height:6px; border-radius:50%; background:#10b981; display:inline-block; margin-right:2px;"></span>Đang hoạt động</span>`;
            if (isLocked) {
              statusBadge = `
                <div style="display:inline-flex; flex-direction:column; align-items:center; gap:2px;">
                  <span class="badge badge-danger" style="white-space:nowrap !important;"><span style="width:6px; height:6px; border-radius:50%; background:#ef4444; display:inline-block; margin-right:2px;"></span>Bị khóa (${u.failed_attempts || 5}/5)</span>
                  ${u.updated_at ? `<span style="font-size:11px; color:#dc2626; font-family:monospace; font-weight:600;" title="Thời điểm khóa thực tế">${u.updated_at.replace('T', ' ')}</span>` : ''}
                </div>
              `;
            } else if (isDisabled) {
              statusBadge = `
                <div style="display:inline-flex; flex-direction:column; align-items:center; gap:2px;">
                  <span class="badge" style="background:#f1f5f9; color:#64748b; border:1px solid #cbd5e1; white-space:nowrap !important;"><span style="width:6px; height:6px; border-radius:50%; background:#94a3b8; display:inline-block; margin-right:2px;"></span>Vô hiệu hóa</span>
                  ${u.updated_at ? `<span style="font-size:11px; color:#64748b; font-family:monospace; font-weight:600;" title="Thời điểm vô hiệu hóa thực tế">${u.updated_at.replace('T', ' ')}</span>` : ''}
                </div>
              `;
            }

            let branchLabel = `<span style="display:inline-flex; align-items:center; gap:5px; color:#7c3aed; font-weight:600; font-size:12.5px; white-space:nowrap !important;">Văn phòng quản trị toàn chuỗi</span>`;
            if (u.branch_id === "BT") {
              branchLabel = `<span style="display:inline-flex; align-items:center; gap:5px; color:#2d241e; font-weight:600; font-size:13px; white-space:nowrap !important;">Chi nhánh Bến Thành</span>`;
            } else if (u.branch_id === "TD") {
              branchLabel = `<span style="display:inline-flex; align-items:center; gap:5px; color:#2d241e; font-weight:600; font-size:13px; white-space:nowrap !important;">Chi nhánh Thảo Điền</span>`;
            } else if (u.branch_id === "PMH") {
              branchLabel = `<span style="display:inline-flex; align-items:center; gap:5px; color:#2d241e; font-weight:600; font-size:13px; white-space:nowrap !important;">Chi nhánh Phú Mỹ Hưng</span>`;
            } else if (u.role === "Khách hàng") {
              branchLabel = `<span style="display:inline-flex; align-items:center; gap:5px; color:#64748b; font-weight:500; font-size:12.5px; white-space:nowrap !important;">Khách đặt toàn hệ thống</span>`;
            }

            const roleBadge = ROLE_BADGE_MAP[u.role] || `<span class="badge badge-cozy" style="white-space:nowrap !important;">${u.role}</span>`;

            const latestTime = u.updated_at || u.last_login_at || u.created_at;
            let actionTag = "Tạo mới";
            let tagColor = "#64748b";
            if (isLocked) {
              actionTag = "Khóa tài khoản";
              tagColor = "#dc2626";
            } else if (isDisabled) {
              actionTag = "Vô hiệu hóa";
              tagColor = "#64748b";
            } else if (u.updated_at && u.updated_at !== u.created_at) {
              actionTag = "Cập nhật hệ thống";
              tagColor = "#0284c7";
            } else if (u.last_login_at) {
              actionTag = "Đăng nhập gần nhất";
              tagColor = "#16a34a";
            }

            return `
              <tr>
                <td style="text-align:center; padding:12px 10px; white-space:nowrap;"><span style="font-weight:700; color:#8c786a; font-size:12px; font-family:monospace;">#${u.id}</span></td>
                <td style="padding:12px 14px; white-space:nowrap !important;"><span style="font-weight:700; color:#2d241e; font-size:13.5px; display:inline-block; white-space:nowrap !important;">${u.full_name}</span></td>
                <td style="padding:12px 14px;">
                  <div style="font-weight:600; font-size:12.5px; color:#2d241e; white-space:nowrap !important;">${u.email}</div>
                  <div style="font-size:11.5px; color:#8c786a; margin-top:3px; white-space:nowrap !important; font-family:monospace;">${u.phone || "—"}</div>
                </td>
                <td style="text-align:center; padding:12px 12px; white-space:nowrap !important;">${roleBadge}</td>
                <td style="padding:12px 14px; white-space:nowrap !important;">${branchLabel}</td>
                <td style="text-align:center; padding:12px 12px; white-space:nowrap !important;">${statusBadge}</td>
                <td style="font-size:12px; padding:12px 14px; white-space:nowrap !important;">
                  <div style="font-family:monospace; font-weight:700; color:#2d241e; font-size:12px;">
                    ${latestTime ? latestTime.replace("T", " ") : '<span style="color:#94a3b8; font-style:italic;">Chưa có</span>'}
                  </div>
                  <div style="font-size:11px; margin-top:2px; display:inline-flex; align-items:center; gap:4px; color:${tagColor}; font-weight:600;">
                    <span style="display:inline-block; width:5px; height:5px; border-radius:50%; background:${tagColor};"></span>
                    ${actionTag}
                    ${u.last_login_at && u.updated_at && u.last_login_at !== u.updated_at ? `<span style="font-weight:400; color:#94a3b8; margin-left:2px;" title="Lần đăng nhập gần nhất: ${u.last_login_at.replace('T', ' ')}">(ĐN: ${u.last_login_at.replace('T', ' ').slice(5, 16)})</span>` : ''}
                  </div>
                </td>
                <td style="text-align:right; padding:12px 14px; white-space:nowrap !important;">
                  <div style="display:inline-flex; gap:6px; align-items:center; justify-content:flex-end;">
                    <button class="btn btn-sm btn-outline" style="padding:5px 10px; font-size:12px; border-radius:6px; font-weight:600; background:#fff;" onclick="openUserDetailModal(${u.id})" title="Xem chi tiết">Xem</button>
                    <button class="btn btn-sm btn-outline" style="padding:5px 10px; font-size:12px; border-radius:6px; font-weight:700; color:var(--cozy-primary); border-color:rgba(180,83,9,0.35); background:#fdf8f4;" onclick="selectUserForRoleAssign(${u.id})" title="Phân quyền vai trò và chi nhánh">Phân quyền</button>
                    ${isLocked 
                      ? `<button class="btn btn-sm btn-success" style="padding:5px 10px; font-size:12px; border-radius:6px; font-weight:600;" onclick="adminUnlockUser(${u.id})">Mở khóa</button>` 
                      : isDisabled 
                        ? `<button class="btn btn-sm btn-outline" style="padding:5px 10px; font-size:12px; border-radius:6px; font-weight:600;" onclick="adminToggleUserStatus(${u.id}, 'ACTIVE')">Kích hoạt</button>`
                        : `<button class="btn btn-sm btn-outline" style="padding:5px 10px; font-size:12px; border-radius:6px; font-weight:600; color:#dc2626; border-color:rgba(220,38,38,0.3); background:#fff5f5;" onclick="adminToggleUserStatus(${u.id}, 'LOCKED')">Khóa</button>`
                    }
                  </div>
                </td>
              </tr>
            `;
          }).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function resetAdminUserFilters() {
  currentPillFilter = "all";
  document.querySelectorAll(".adm-user-filter-pill").forEach(btn => {
    if (btn.getAttribute("data-pill") === "all") btn.classList.add("active");
    else btn.classList.remove("active");
  });

  const s = document.getElementById("adm-user-filter-search") || document.getElementById("adm-user-search");
  const r = document.getElementById("adm-user-role-filter");
  const b = document.getElementById("adm-user-branch-filter");
  const st = document.getElementById("adm-user-status-filter");
  const sort = document.getElementById("adm-user-sort");
  const clearBtn = document.getElementById("adm-search-clear-btn");
  if (s) {
    s.value = "";
    delete s.dataset.userTyped;
  }
  if (clearBtn) clearBtn.style.display = "none";
  if (r) r.value = "";
  if (b) b.value = "";
  if (st) st.value = "";
  if (sort) sort.value = "";
  loadAdminUsers();
}

function toggleAdminUserSort() {
  const select = document.getElementById("adm-user-sort");
  if (!select) return;
  if (select.value === "name_asc") select.value = "name_desc";
  else if (select.value === "name_desc") select.value = "";
  else select.value = "name_asc";
  loadAdminUsers();
}

function clearAdminUserSearch() {
  const s = document.getElementById("adm-user-filter-search") || document.getElementById("adm-user-search");
  const clearBtn = document.getElementById("adm-search-clear-btn");
  if (s) {
    s.value = "";
    delete s.dataset.userTyped;
    s.focus();
  }
  if (clearBtn) clearBtn.style.display = "none";
  loadAdminUsers();
}

function openCreateUserModal() {
  const modal = document.getElementById("adm-modal-create-user");
  if (modal) modal.style.display = "flex";
}

function closeCreateUserModal() {
  const modal = document.getElementById("adm-modal-create-user");
  if (modal) modal.style.display = "none";
}

async function submitCreateUser(e) {
  e.preventDefault();
  const fullName = document.getElementById("new-user-fullname")?.value.trim();
  const email = document.getElementById("new-user-email")?.value.trim();
  const phone = document.getElementById("new-user-phone")?.value.trim();
  const password = document.getElementById("new-user-password")?.value;
  const role = document.getElementById("new-user-role")?.value;
  const branchId = document.getElementById("new-user-branch")?.value || null;

  if (role in {"Lễ tân": 1, "Buồng phòng": 1, "Nhân viên buồng phòng": 1} && !branchId) {
    showToast("Vai trò này bắt buộc phải chọn chi nhánh phân công.", "error");
    return;
  }

  try {
    const res = await apiFetch("/api/admin/users", {
      method: "POST",
      body: {
        full_name: fullName,
        email: email,
        phone: phone,
        password: password,
        role: role,
        branch_id: branchId,
      },
    });

    showToast(res.message || "Tạo tài khoản thành công!", "success");
    closeCreateUserModal();
    document.getElementById("adm-form-create-user")?.reset();
    loadAdminUsers();
  } catch (err) {
  }
}

function onNewUserRoleChange(selectedRole) {
  const branchBox = document.getElementById("new-user-branch-group");
  const branchSelect = document.getElementById("new-user-branch");
  const requiresBranch = (selectedRole === "Lễ tân" || selectedRole === "Buồng phòng" || selectedRole === "Nhân viên buồng phòng");

  if (branchBox && branchSelect) {
    if (requiresBranch) {
      branchBox.style.display = "block";
      branchSelect.required = true;
    } else {
      branchBox.style.display = "none";
      branchSelect.required = false;
      branchSelect.value = "";
    }
  }
}

function openUserDetailModal(userId) {
  const user = adminUsersCache.find(u => u.id === userId);
  if (!user) return;

  const content = document.getElementById("adm-user-detail-content");
  if (!content) return;

  content.innerHTML = `
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-bottom:16px;">
      <div><span style="font-size:12px; color:var(--text-muted);">Mã tài khoản:</span><div style="font-weight:700;">#${user.id}</div></div>
      <div><span style="font-size:12px; color:var(--text-muted);">Trạng thái:</span><div><b>${user.status}</b></div></div>
      <div><span style="font-size:12px; color:var(--text-muted);">Họ và tên:</span><div style="font-weight:700;">${user.full_name}</div></div>
      <div><span style="font-size:12px; color:var(--text-muted);">Email:</span><div>${user.email}</div></div>
      <div><span style="font-size:12px; color:var(--text-muted);">Số điện thoại:</span><div>${user.phone || "—"}</div></div>
      <div><span style="font-size:12px; color:var(--text-muted);">Vai trò hiện tại:</span><div><span class="badge badge-cozy">${user.role}</span></div></div>
      <div><span style="font-size:12px; color:var(--text-muted);">Phạm vi chi nhánh:</span><div>${user.role === "Khách hàng" ? "Khách đặt toàn hệ thống" : (user.branch_id ? (user.branch_id === "BT" ? "Chi nhánh Bến Thành" : user.branch_id === "TD" ? "Chi nhánh Thảo Điền" : "Chi nhánh Phú Mỹ Hưng") : "Văn phòng quản trị toàn chuỗi")}</div></div>
      <div><span style="font-size:12px; color:var(--text-muted);">Số lần đăng nhập sai:</span><div><b>${user.failed_attempts}/5 lần</b></div></div>
      <div><span style="font-size:12px; color:var(--text-muted);">Cập nhật gần nhất:</span><div style="font-weight:700; color:#b45309; font-family:monospace;">${user.updated_at ? user.updated_at.replace("T", " ") : "Chưa có cập nhật"}</div></div>
      <div><span style="font-size:12px; color:var(--text-muted);">Đăng nhập gần nhất:</span><div style="font-family:monospace;">${user.last_login_at ? user.last_login_at.replace("T", " ") : "Chưa đăng nhập"}</div></div>
      <div style="grid-column:1 / -1;"><span style="font-size:12px; color:var(--text-muted);">Thời điểm khởi tạo:</span><div style="font-family:monospace;">${user.created_at ? user.created_at.replace("T", " ") : "—"}</div></div>
    </div>
    <div style="display:flex; justify-content:flex-end; gap:8px; border-top:1px solid var(--cozy-border); padding-top:14px;">
      ${user.failed_attempts > 0 ? `<button class="btn btn-outline btn-sm" onclick="adminResetFails(${user.id}); closeUserDetailModal();">Reset số lần sai</button>` : ""}
      <button class="btn btn-primary btn-sm" onclick="selectUserForRoleAssign(${user.id}); closeUserDetailModal();">Phân quyền tài khoản &rarr;</button>
    </div>
  `;

  const modal = document.getElementById("adm-modal-user-detail");
  if (modal) modal.style.display = "flex";
}

function closeUserDetailModal() {
  const modal = document.getElementById("adm-modal-user-detail");
  if (modal) modal.style.display = "none";
}

async function adminUnlockUser(userId) {
  showAdminConfirmModal({
    title: "Mở khóa tài khoản",
    message: `Bạn có chắc chắn muốn mở khóa tài khoản #${userId}?`,
    warning: "Sau khi mở khóa, trạng thái sẽ chuyển về ACTIVE và số lần nhập sai mật khẩu sẽ được đặt lại về 0.",
    confirmText: "Xác nhận mở khóa",
    onConfirm: async () => {
      try {
        const res = await apiFetch(`/api/admin/users/${userId}/status`, {
          method: "POST",
          body: { status: "ACTIVE" },
        });
        const timeNow = new Date().toLocaleTimeString('vi-VN');
        showToast(`${res.message || "Đã mở khóa tài khoản thành công!"} (Ghi nhận lúc ${timeNow})`, "success");
        await loadAdminUsers();
      } catch (err) {
      }
    }
  });
}

async function adminToggleUserStatus(userId, newStatus) {
  const isLocking = newStatus === "LOCKED";
  showAdminConfirmModal({
    title: isLocking ? "Khóa tài khoản" : "Kích hoạt tài khoản",
    message: `Bạn có chắc chắn muốn ${isLocking ? "khóa" : "kích hoạt"} tài khoản #${userId}?`,
    warning: isLocking ? "Người dùng này sẽ không thể đăng nhập vào hệ thống CozyHome cho đến khi được Admin mở khóa." : "",
    confirmText: isLocking ? "Khóa tài khoản" : "Kích hoạt",
    onConfirm: async () => {
      try {
        const res = await apiFetch(`/api/admin/users/${userId}/status`, {
          method: "POST",
          body: { status: newStatus },
        });
        const timeNow = new Date().toLocaleTimeString('vi-VN');
        showToast(`${res.message} (Ghi nhận lúc ${timeNow})`, "success");
        await loadAdminUsers();
      } catch (err) {
      }
    }
  });
}

async function adminResetFails(userId) {
  try {
    const res = await apiFetch(`/api/admin/users/${userId}/reset-fails`, { method: "POST" });
    showToast(res.message, "success");
    loadAdminUsers();
  } catch (err) {
  }
}

// ================================================================
// 3. VAI TRÒ VÀ PHÂN QUYỀN (ROLE & BRANCH SCOPE)
// ================================================================
let selectedUserForRole = null;

async function loadAdminRolesSection() {
  if (adminUsersCache.length === 0) {
    try {
      const res = await apiFetch("/api/admin/users");
      adminUsersCache = res.users || [];
    } catch (e) {}
  }

  const select = document.getElementById("adm-role-user-select");
  if (select) {
    select.innerHTML = `<option value="">-- Chọn người dùng để phân quyền --</option>` +
      adminUsersCache.map(u => `
        <option value="${u.id}">${u.full_name} (${u.email}) — [${u.role}${u.branch_id ? ' - ' + u.branch_id : ''}]</option>
      `).join("");

    if (selectedUserForRole) {
      select.value = selectedUserForRole.id;
      onRoleUserSelected(selectedUserForRole.id);
    }
  }
}

function selectUserForRoleAssign(userId) {
  const user = adminUsersCache.find(u => u.id === parseInt(userId));
  if (!user) return;
  selectedUserForRole = user;

  const formSection = document.getElementById("adm-role-assign-form");
  if (!formSection) return;

  formSection.style.display = "block";
  document.getElementById("role-assign-name").textContent = user.full_name;
  document.getElementById("role-assign-email").textContent = user.email;

  const roleSelect = document.getElementById("role-assign-role-select");
  const branchSelect = document.getElementById("role-assign-branch-select");

  if (roleSelect) roleSelect.value = user.role;
  if (branchSelect) branchSelect.value = user.branch_id || "BT";

  onRoleChangeInForm(user.role);

  formSection.scrollIntoView({ behavior: "smooth", block: "center" });
}

function closeRoleAssignSection() {
  const formSection = document.getElementById("adm-role-assign-form");
  if (formSection) formSection.style.display = "none";
}

function onRoleUserSelected(userId) {
  if (!userId) {
    document.getElementById("adm-role-assign-form").style.display = "none";
    return;
  }

  const user = adminUsersCache.find(u => u.id === parseInt(userId));
  if (!user) return;
  selectedUserForRole = user;

  document.getElementById("adm-role-assign-form").style.display = "block";
  document.getElementById("role-assign-name").textContent = user.full_name;
  document.getElementById("role-assign-email").textContent = user.email;

  const roleSelect = document.getElementById("role-assign-role-select");
  const branchSelect = document.getElementById("role-assign-branch-select");

  if (roleSelect) roleSelect.value = user.role;
  if (branchSelect) branchSelect.value = user.branch_id || "";

  onRoleChangeInForm(user.role);
}

function onRoleChangeInForm(role) {
  const branchGroup = document.getElementById("role-assign-branch-group");
  const branchSelect = document.getElementById("role-assign-branch-select");
  const requiresBranch = (role === "Lễ tân" || role === "Buồng phòng" || role === "Nhân viên buồng phòng");

  if (branchGroup && branchSelect) {
    if (requiresBranch) {
      branchGroup.style.display = "block";
      branchSelect.required = true;
      if (!branchSelect.value) branchSelect.value = "BT";
    } else {
      branchGroup.style.display = "none";
      branchSelect.required = false;
      branchSelect.value = "";
    }
  }

  // Render Ma trận quyền thời gian thực
  renderPermissionPreview(role);
}

function renderPermissionPreview(role) {
  const container = document.getElementById("role-permissions-preview-box");
  if (!container) return;

  const permissions = PERMISSION_PREVIEW_MAP[role] || [];
  container.innerHTML = `
    <h4 style="margin:0 0 12px 0; font-size:14.5px; color:var(--cozy-dark);">
      Ma trận chức năng áp dụng cho vai trò <span style="color:var(--cozy-primary);">${role}</span>:
    </h4>
    <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(280px, 1fr)); gap:8px;">
      ${permissions.map(p => `
        <div style="display:flex; align-items:center; gap:8px; padding:6px 10px; border-radius:8px; background:${p.granted ? '#f0fdf4' : '#fef2f2'}; border:1px solid ${p.granted ? '#bbf7d0' : '#fecaca'};">
          <span style="font-size:14px; font-weight:700; color:${p.granted ? '#166534' : '#991b1b'};">${p.granted ? '✓' : '✕'}</span>
          <div style="font-size:12.5px; color:${p.granted ? '#166534' : '#991b1b'};">
            <b>${p.name}</b>
            ${p.reason ? `<div style="font-size:11px; opacity:0.8;">(${p.reason})</div>` : ''}
          </div>
        </div>
      `).join("")}
    </div>
  `;
}

async function submitRoleScopeAssignment(e) {
  e.preventDefault();
  if (!selectedUserForRole) return;

  const newRole = document.getElementById("role-assign-role-select")?.value;
  const newBranch = document.getElementById("role-assign-branch-select")?.value || null;

  if (newRole in {"Lễ tân": 1, "Buồng phòng": 1, "Nhân viên buồng phòng": 1} && !newBranch) {
    showToast("Vai trò này bắt buộc phân công một chi nhánh cụ thể (BT, TD hoặc PMH).", "error");
    return;
  }

  const user = selectedUserForRole;
  showAdminConfirmModal({
    title: "Xác nhận thay đổi phân quyền",
    message: `Bạn có chắc chắn muốn thay đổi phân quyền cho <b>${user.full_name}</b>?`,
    warning: `Vai trò sẽ đổi từ <b>${user.role} (${user.branch_id || 'Toàn chuỗi'})</b> sang <b>${newRole} (${newBranch || 'Toàn chuỗi'})</b>. Người dùng sẽ bị giới hạn đúng theo phạm vi chức năng mới.`,
    confirmText: "Xác nhận thay đổi",
    onConfirm: async () => {
      try {
        const res = await apiFetch(`/api/admin/users/${user.id}/scope`, {
          method: "POST",
          body: {
            role: newRole,
            branch_id: newBranch,
          },
        });

        const timeNow = new Date().toLocaleTimeString('vi-VN');
        showToast(`${res.message || "Phân quyền thành công!"} (Ghi nhận lúc ${timeNow})`, "success");
        // Cập nhật cache
        user.role = newRole;
        user.branch_id = newBranch;
        closeRoleAssignSection();
        await loadAdminUsers();
      } catch (err) {
      }
    }
  });
}

// ================================================================
// 4. TRA CỨU VẬN HÀNH (READ-ONLY OPERATIONS)
// ================================================================
let adminOpsCurrentSubtab = "rooms";

function loadAdminOperationsTab(subtab) {
  adminOpsCurrentSubtab = subtab;
  document.querySelectorAll(".adm-ops-subtab-btn").forEach(btn => {
    if (btn.getAttribute("data-subtab") === subtab) btn.classList.add("active");
    else btn.classList.remove("active");
  });

  document.querySelectorAll(".adm-ops-pane").forEach(p => {
    if (p.id === `adm-ops-pane-${subtab}`) p.style.display = "block";
    else p.style.display = "none";
  });

  if (subtab === "rooms") loadAdminOpsRooms();
  else if (subtab === "bookings") loadAdminOpsBookings();
  else if (subtab === "transactions") loadAdminOpsTransactions();
}

async function loadAdminOpsRooms() {
  const branch = document.getElementById("adm-ops-room-branch")?.value || "";
  const status = document.getElementById("adm-ops-room-status")?.value || "";
  const kw = (document.getElementById("adm-ops-room-kw")?.value || "").trim();
  const sort = document.getElementById("adm-ops-room-sort")?.value || "";

  try {
    const res = await apiFetch(`/api/admin/operations/rooms?branch_id=${branch}`);
    let rooms = res.rooms || [];

    if (status) rooms = rooms.filter(r => r.operational_status === status);
    if (kw) {
      const normKw = removeVietnameseTones(kw);
      rooms = rooms.filter(r => 
        removeVietnameseTones(r.room_id).includes(normKw) || 
        removeVietnameseTones(r.room_name).includes(normKw) ||
        removeVietnameseTones(r.branch_name).includes(normKw) ||
        removeVietnameseTones(r.room_type).includes(normKw)
      );
    }

    if (sort === "name_asc") {
      rooms.sort((a, b) => removeVietnameseTones(a.room_name).localeCompare(removeVietnameseTones(b.room_name)));
    } else if (sort === "name_desc") {
      rooms.sort((a, b) => removeVietnameseTones(b.room_name).localeCompare(removeVietnameseTones(a.room_name)));
    }

    const container = document.getElementById("adm-ops-rooms-table");
    if (!container) return;

    if (rooms.length === 0) {
      container.innerHTML = `<div style="padding:20px; text-align:center; color:var(--text-muted);">Không tìm thấy phòng phù hợp.</div>`;
      return;
    }

    container.innerHTML = `
      <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th>Mã phòng</th>
              <th>Tên phòng</th>
              <th>Chi nhánh</th>
              <th>Hạng phòng</th>
              <th>Sức chứa</th>
              <th>Trạng thái vận hành</th>
              <th>Cập nhật gần nhất</th>
            </tr>
          </thead>
          <tbody>
            ${rooms.map(r => `
              <tr>
                <td><b>${r.room_id}</b></td>
                <td>${r.room_name}</td>
                <td>${r.branch_name}</td>
                <td><span class="badge badge-cozy">${r.room_type}</span></td>
                <td>${r.capacity} khách</td>
                <td><span class="badge ${getRoomStatusBadgeClass(r.operational_status)}">${r.operational_status}</span></td>
                <td style="font-size:12px; color:var(--text-muted);">${r.last_cleaned_by ? `<div><b style="color:var(--text-main);">${r.last_cleaned_by}</b></div><div style="font-size:11px; font-family:monospace; color:#8c786a;">${(r.last_cleaned_at || '').replace('T', ' ')}</div>` : '<span style="color:#94a3b8; font-style:italic;">Chưa có cập nhật</span>'}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    `;
  } catch (err) {}
}

function getRoomStatusBadgeClass(st) {
  if (st === "Sẵn sàng") return "badge-success";
  if (st === "Đang sử dụng" || st === "Đang ở") return "badge-info";
  if (st === "Đang dọn" || st === "Cần dọn") return "badge-warning";
  if (st === "Bảo trì") return "badge-danger";
  return "badge-cozy";
}

async function loadAdminOpsBookings() {
  const branch = document.getElementById("adm-ops-bk-branch")?.value || "";
  const status = document.getElementById("adm-ops-bk-status")?.value || "";
  const kw = document.getElementById("adm-ops-bk-kw")?.value || "";
  const sort = document.getElementById("adm-ops-bk-sort")?.value || "";

  let url = `/api/admin/operations/bookings?`;
  if (branch) url += `branch_id=${encodeURIComponent(branch)}&`;
  if (status) url += `status=${encodeURIComponent(status)}&`;
  if (kw) url += `keyword=${encodeURIComponent(kw)}&`;
  if (sort) url += `sort_by=${encodeURIComponent(sort)}&`;

  try {
    const res = await apiFetch(url);
    const bookings = res.bookings || [];
    const container = document.getElementById("adm-ops-bookings-table");
    if (!container) return;

    if (bookings.length === 0) {
      container.innerHTML = `<div style="padding:20px; text-align:center; color:var(--text-muted);">Không tìm thấy đơn đặt phòng phù hợp.</div>`;
      return;
    }

    container.innerHTML = `
      <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th>Mã đơn</th>
              <th>Phòng</th>
              <th>Chi nhánh</th>
              <th>Khách hàng</th>
              <th>Ngày và Khung</th>
              <th>Trạng thái</th>
              <th>Thanh toán</th>
              <th style="text-align:right;">Chi tiết</th>
            </tr>
          </thead>
          <tbody>
            ${bookings.map(b => `
              <tr>
                <td><b>${b.booking_code}</b></td>
                <td><b>${b.room_id}</b></td>
                <td>${b.branch_id}</td>
                <td>${b.customer_name}<div style="font-size:11px; color:var(--text-muted);">${b.customer_phone || ''}</div></td>
                <td>${b.booking_date} (${b.khung_code})</td>
                <td>
                  <span class="badge badge-cozy">${b.status}</span>
                  ${b.actual_checkin ? `<div style="font-size:11px; color:#10b981; font-family:monospace; margin-top:2px;">In: ${b.actual_checkin.replace('T', ' ')}</div>` : ''}
                  ${b.actual_checkout ? `<div style="font-size:11px; color:#64748b; font-family:monospace; margin-top:2px;">Out: ${b.actual_checkout.replace('T', ' ')}</div>` : ''}
                </td>
                <td><b style="color:var(--cozy-primary);">${formatMoney(b.amount)}</b> - ${b.payment_status}</td>
                <td style="text-align:right;">
                  <button class="btn btn-sm btn-outline" onclick="openAdminBookingDetailModal('${b.booking_code}')">Xem</button>
                </td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    `;
  } catch (err) {}
}

function openAdminBookingDetailModal(bookingCode) {
  apiFetch(`/api/admin/operations/bookings?keyword=${bookingCode}`).then(res => {
    const b = (res.bookings || []).find(item => item.booking_code === bookingCode);
    if (!b) return;

    const content = document.getElementById("adm-booking-detail-content");
    if (!content) return;

    content.innerHTML = `
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-bottom:16px;">
        <div><span style="font-size:12px; color:var(--text-muted);">Mã đơn:</span><div style="font-weight:800; font-size:16px; color:var(--cozy-primary);">${b.booking_code}</div></div>
        <div><span style="font-size:12px; color:var(--text-muted);">Trạng thái hiện tại:</span><div><span class="badge badge-cozy" style="font-size:12px;">${b.status}</span></div></div>
        <div><span style="font-size:12px; color:var(--text-muted);">Phòng đặt:</span><div style="font-weight:700;">${b.room_id} (${b.branch_id})</div></div>
        <div><span style="font-size:12px; color:var(--text-muted);">Khung giờ:</span><div>${b.booking_date} - ${b.start_time && b.end_time ? `${b.start_time} – ${b.end_time}` : b.khung_code} (${b.khung_code === 'K1' ? 'Sáng' : b.khung_code === 'K2' ? 'Chiều' : b.khung_code === 'K3' ? 'Tối' : 'Qua đêm'})</div></div>
        <div><span style="font-size:12px; color:var(--text-muted);">Khách hàng:</span><div style="font-weight:700;">${b.customer_name}</div></div>
        <div><span style="font-size:12px; color:var(--text-muted);">SĐT và Email:</span><div>${b.customer_phone || ''} - ${b.customer_email || 'Chưa cập nhật'}</div></div>
        <div><span style="font-size:12px; color:var(--text-muted);">Tổng số tiền:</span><div style="font-weight:800; color:var(--cozy-primary); font-size:15px;">${formatMoney(b.amount)}</div></div>
        <div><span style="font-size:12px; color:var(--text-muted);">Thanh toán:</span><div><b>${b.payment_status}</b></div></div>
        <div><span style="font-size:12px; color:var(--text-muted);">Giờ check-in thực tế:</span><div>${b.actual_checkin ? b.actual_checkin.replace("T", " ") : "Chưa check-in"}</div></div>
        <div><span style="font-size:12px; color:var(--text-muted);">Giờ check-out thực tế:</span><div>${b.actual_checkout ? b.actual_checkout.replace("T", " ") : "Chưa check-out"}</div></div>
      </div>
      ${b.note ? `<div style="background:#f9fafb; padding:10px; border-radius:8px; font-size:12.5px; margin-bottom:14px;"><b>Ghi chú của khách:</b> ${b.note}</div>` : ''}
      <div style="background:#fff7ed; border:1px solid #fed7aa; padding:10px; border-radius:8px; font-size:12px; color:#9a3412;">
        Chế độ tra cứu quản trị viên: Quản trị viên chỉ xem dữ liệu lưu vết, không có quyền check-in, check-out hoặc hủy thay lễ tân.
      </div>
    `;

    const modal = document.getElementById("adm-modal-booking-detail");
    if (modal) modal.style.display = "flex";
  });
}

function closeAdminBookingDetailModal() {
  const modal = document.getElementById("adm-modal-booking-detail");
  if (modal) modal.style.display = "none";
}

async function loadAdminOpsTransactions() {
  const branch = document.getElementById("adm-ops-tx-branch")?.value || "";
  try {
    const res = await apiFetch(`/api/admin/operations/transactions?branch_id=${branch}`);
    const txs = res.transactions || [];
    const container = document.getElementById("adm-ops-transactions-table");
    if (!container) return;

    if (txs.length === 0) {
      container.innerHTML = `<div style="padding:20px; text-align:center; color:var(--text-muted);">Không có giao dịch nào.</div>`;
      return;
    }

    container.innerHTML = `
      <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Mã đơn</th>
              <th>Khách hàng</th>
              <th>Loại giao dịch</th>
              <th>Số tiền</th>
              <th>Phương thức</th>
              <th>Trạng thái</th>
              <th>Thời gian</th>
              <th>Người đối soát</th>
            </tr>
          </thead>
          <tbody>
            ${txs.map(t => {
              const isRefund = t.tx_type === "Hoàn tiền";
              const isExtension = t.tx_type === "Gia hạn";
              const txBadgeClass = isRefund ? 'badge-tx-refund' : (isExtension ? 'badge-tx-extension' : 'badge-tx-payment');
              return `
                <tr>
                  <td>#${t.id}</td>
                  <td><b>${t.booking_code}</b></td>
                  <td>${t.customer_name || '—'}</td>
                  <td><span class="badge ${txBadgeClass}">${t.tx_type || 'Thanh toán'}</span></td>
                  <td><b style="color:${isRefund ? 'var(--danger)' : 'var(--success)'};">${isRefund ? '-' : '+'}${formatMoney(Math.abs(t.amount || 0))}</b></td>
                  <td style="font-size:12px;">${t.method || 'VietQR'}</td>
                  <td><span class="badge ${t.reconciled === 1 ? 'badge-success' : 'badge-warning'}">${t.status}</span></td>
                  <td style="font-size:11.5px; color:var(--text-muted);">${(t.created_at || '').replace('T', ' ')}</td>
                  <td style="font-size:12px;">${t.reconciled_by ? `<div><b>${t.reconciled_by}</b></div><div style="font-size:11px; color:var(--text-muted); font-family:monospace;" title="Thời điểm đối soát">${(t.reconciled_at || '').replace('T', ' ')}</div>` : '<span style="color:#94a3b8; font-style:italic;">Chờ đối soát</span>'}</td>
                </tr>
              `;
            }).join("")}
          </tbody>
        </table>
      </div>
    `;
  } catch (err) {}
}

// ================================================================
// 5. NHẬT KÝ HỆ THỐNG (AUDIT LOGS)
// ================================================================
async function loadAdminAuditLogs(page = 0) {
  adminAuditPage = page;
  const kw = document.getElementById("adm-audit-kw")?.value || "";
  const role = document.getElementById("adm-audit-role")?.value || "";
  const branch = document.getElementById("adm-audit-branch")?.value || "";
  const action = document.getElementById("adm-audit-action")?.value || "";
  const fromDate = document.getElementById("adm-audit-from")?.value || "";
  const toDate = document.getElementById("adm-audit-to")?.value || "";
  const sort = document.getElementById("adm-audit-sort")?.value || "";

  let url = `/api/admin/audit-logs?limit=${ADMIN_PAGE_SIZE}&offset=${page * ADMIN_PAGE_SIZE}&`;
  if (kw) url += `keyword=${encodeURIComponent(kw)}&`;
  if (role) url += `role=${encodeURIComponent(role)}&`;
  if (branch) url += `branch_id=${encodeURIComponent(branch)}&`;
  if (action) url += `action=${encodeURIComponent(action)}&`;
  if (fromDate) url += `from_date=${encodeURIComponent(fromDate)}&`;
  if (toDate) url += `to_date=${encodeURIComponent(toDate)}&`;
  if (sort) url += `sort_by=${encodeURIComponent(sort)}&`;

  try {
    const res = await apiFetch(url);
    adminAuditLogsCache = res.logs || [];
    adminAuditTotal = res.total || 0;
    renderAdminAuditTable();
  } catch (err) {}
}

function renderAdminAuditTable() {
  const container = document.getElementById("adm-audit-table-container");
  const pagination = document.getElementById("adm-audit-pagination");
  if (!container) return;

  if (adminAuditLogsCache.length === 0) {
    container.innerHTML = `<div style="padding:24px; text-align:center; color:var(--text-muted);">Chưa có bản ghi nhật ký nào phù hợp.</div>`;
    if (pagination) pagination.innerHTML = "";
    return;
  }

  container.innerHTML = `
    <div class="table-responsive">
      <table class="data-table" style="width:100%; table-layout:auto;">
        <thead>
          <tr>
            <th style="width:145px; white-space:nowrap;">Thời gian</th>
            <th style="min-width:180px;">Người thực hiện</th>
            <th style="width:120px; text-align:center;">Vai trò</th>
            <th style="width:110px; text-align:center;">Chi nhánh</th>
            <th style="width:120px; text-align:center;">Hành động</th>
            <th>Mô tả chi tiết</th>
          </tr>
        </thead>
        <tbody>
          ${adminAuditLogsCache.map(l => `
            <tr>
              <td style="font-size:12px; white-space:nowrap; color:var(--text-muted);">${(l.created_at || '').replace('T', ' ')}</td>
              <td>
                <div style="font-weight:600; color:var(--text-main);">${l.user_name || l.user_email}</div>
                <div style="font-size:11px; color:var(--text-muted);">${l.user_email}</div>
              </td>
              <td style="text-align:center;"><span class="badge badge-cozy">${l.role}</span></td>
              <td style="text-align:center; font-size:12.5px;">${l.branch_id || 'Toàn chuỗi'}</td>
              <td style="text-align:center;"><span class="badge ${getAuditActionBadge(l.action)}">${l.action}</span></td>
              <td style="font-size:13px; line-height:1.45;">${l.description}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;

  // Phân trang
  if (pagination) {
    const totalPages = Math.ceil(adminAuditTotal / ADMIN_PAGE_SIZE);
    const currentPage = adminAuditPage + 1;
    pagination.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; padding-top:12px;">
        <span style="font-size:12.5px; color:var(--text-muted);">
          Hiển thị <b>${adminAuditLogsCache.length}</b> trên tổng số <b>${adminAuditTotal}</b> bản ghi (Trang ${currentPage}/${totalPages || 1})
        </span>
        <div style="display:flex; gap:6px;">
          <button class="btn btn-outline btn-sm" ${adminAuditPage === 0 ? 'disabled' : ''} onclick="loadAdminAuditLogs(${adminAuditPage - 1})">&larr; Trang trước</button>
          <button class="btn btn-outline btn-sm" ${currentPage >= totalPages ? 'disabled' : ''} onclick="loadAdminAuditLogs(${adminAuditPage + 1})">Trang sau &rarr;</button>
        </div>
      </div>
    `;
  }
}

function getAuditActionBadge(action) {
  if (action.includes("LOCK")) return "badge-danger";
  if (action.includes("UNLOCK") || action.includes("SUCCESS")) return "badge-success";
  if (action.includes("CHECK_IN") || action.includes("CHECK_OUT")) return "badge-info";
  if (action.includes("ASSIGN") || action.includes("CONFIG")) return "badge-warning";
  return "badge-cozy";
}

function resetAdminAuditFilters() {
  document.getElementById("adm-audit-kw").value = "";
  document.getElementById("adm-audit-role").value = "";
  document.getElementById("adm-audit-branch").value = "";
  document.getElementById("adm-audit-action").value = "";
  document.getElementById("adm-audit-from").value = "";
  document.getElementById("adm-audit-to").value = "";
  const sort = document.getElementById("adm-audit-sort");
  if (sort) sort.value = "";
  loadAdminAuditLogs(0);
}

// ================================================================
// 6. CẤU HÌNH BẢO MẬT VÀ TRUY CẬP (SECURITY SETTINGS)
// ================================================================
async function loadAdminSecuritySettings() {
  try {
    const res = await apiFetch("/api/admin/security");
    const settings = res.settings || {};

    const maxFailedInput = document.getElementById("sec-max-failed-attempts");
    const lockDurationInput = document.getElementById("sec-lockout-duration");
    const sessionTtlInput = document.getElementById("sec-session-timeout");
    const otpTtlInput = document.getElementById("sec-otp-ttl");
    const otpMaxInput = document.getElementById("sec-otp-max-attempts");

    if (maxFailedInput && settings.max_failed_attempts) maxFailedInput.value = settings.max_failed_attempts.value;
    if (lockDurationInput && settings.lockout_duration_minutes) lockDurationInput.value = settings.lockout_duration_minutes.value;
    if (sessionTtlInput && settings.session_timeout_hours) sessionTtlInput.value = settings.session_timeout_hours.value;
    if (otpTtlInput && settings.otp_ttl_minutes) otpTtlInput.value = settings.otp_ttl_minutes.value;
    if (otpMaxInput && settings.otp_max_attempts) otpMaxInput.value = settings.otp_max_attempts.value;

    // Check SMTP status
    const smtpRes = await apiFetch("/api/auth/smtp-status");
    const smtpBox = document.getElementById("sec-smtp-status-box");
    if (smtpBox) {
      smtpBox.innerHTML = `
        <div style="display:flex; align-items:center; gap:10px;">
          <span style="width:10px; height:10px; border-radius:50%; background:${smtpRes.reachable ? '#16a34a' : '#eab308'}; display:inline-block; flex-shrink:0;"></span>
          <div>
            <b>${smtpRes.message || 'Hệ thống gửi Email OTP'}</b>
            <div style="font-size:11.5px; color:var(--text-muted);">Máy chủ: ${smtpRes.host || 'smtp.gmail.com'} (Cổng ${smtpRes.port || 587})</div>
          </div>
        </div>
      `;
    }
  } catch (err) {}
}

async function submitAdminSecuritySettings(e) {
  e.preventDefault();
  const maxFailed = document.getElementById("sec-max-failed-attempts")?.value;
  const lockDuration = document.getElementById("sec-lockout-duration")?.value;
  const sessionTtl = document.getElementById("sec-session-timeout")?.value;
  const otpTtl = document.getElementById("sec-otp-ttl")?.value;
  const otpMax = document.getElementById("sec-otp-max-attempts")?.value;

  try {
    const res = await apiFetch("/api/admin/security", {
      method: "POST",
      body: {
        settings: {
          max_failed_attempts: maxFailed,
          lockout_duration_minutes: lockDuration,
          session_timeout_hours: sessionTtl,
          otp_ttl_minutes: otpTtl,
          otp_max_attempts: otpMax,
        }
      }
    });
    showToast(res.message || "Đã lưu cấu hình bảo mật thành công!", "success");
  } catch (err) {}
}

// ================================================================
// Confirmation Modal Reusable Component (Không dùng window.confirm)
// ================================================================
let adminConfirmCallback = null;

function showAdminConfirmModal({ title, message, warning, confirmText = "Xác nhận", onConfirm }) {
  const modal = document.getElementById("adm-confirm-modal");
  if (!modal) {
    if (confirm(message)) onConfirm();
    return;
  }

  document.getElementById("adm-confirm-modal-title").innerHTML = title;
  document.getElementById("adm-confirm-modal-msg").innerHTML = message;
  const warningEl = document.getElementById("adm-confirm-modal-warning");
  if (warningEl) {
    if (warning) {
      warningEl.innerHTML = warning;
      warningEl.style.display = "block";
    } else {
      warningEl.style.display = "none";
    }
  }

  const btnConfirm = document.getElementById("adm-confirm-modal-btn");
  if (btnConfirm) btnConfirm.textContent = confirmText;

  adminConfirmCallback = onConfirm;
  modal.style.display = "flex";
}

function closeAdminConfirmModal() {
  const modal = document.getElementById("adm-confirm-modal");
  if (modal) modal.style.display = "none";
  adminConfirmCallback = null;
}

function executeAdminConfirm() {
  if (typeof adminConfirmCallback === "function") {
    const cb = adminConfirmCallback;
    adminConfirmCallback = null;
    closeAdminConfirmModal();
    cb();
  }
}
