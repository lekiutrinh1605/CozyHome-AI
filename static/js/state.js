// -------------------------------------------------------------
// CozyHome State Management & Utility Helpers
// -------------------------------------------------------------

// ================================================================
// TIỆN ÍCH CHUẨN HÓA TIẾNG VIỆT KHÔNG DẤU (SEARCH ACCENT-FREE)
// ================================================================
function removeVietnameseTones(str) {
  if (!str) return "";
  return str
    .toString()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "d")
    .toLowerCase()
    .trim();
}

// ================================================================
// ROLE CONSTANTS — nguồn duy nhất định nghĩa 6 vai trò CozyHome
// ================================================================
const COZY_ROLES = {
  CUSTOMER:     "Khách hàng",
  RECEPTIONIST: "Lễ tân",
  HOUSEKEEPING: "Nhân viên buồng phòng",
  ACCOUNTANT:   "Kế toán",
  MANAGER:      "Quản lý chuỗi",
  ADMIN:        "Quản trị viên",
};

// Danh sách hợp lệ để validate (dùng trong select-role)
const COZY_ROLE_LIST = Object.values(COZY_ROLES);

// ================================================================
// DEMO ACCOUNT CONFIG — TRAINING / DEMO ONLY
// Không hard-code email/password này ở nhiều nơi khác.
// Không dùng cơ chế này trong môi trường production thật.
// ================================================================
const DEMO_ACCOUNT = {
  email:       "demo@cozyhome.vn",
  password:    "123456",
  displayName: "CozyHome Demo",
};

// ================================================================
// NORMALIZE ROLE — DB cũ → chuẩn COZY_ROLES
// ================================================================
function normalizeRole(rawRole) {
  if (!rawRole) return null;
  const map = {
    "Buồng phòng":           COZY_ROLES.HOUSEKEEPING,
    "Quản lý":               COZY_ROLES.MANAGER,
    "Manager":               COZY_ROLES.MANAGER,
    "Admin":                 COZY_ROLES.ADMIN,
    "Quản trị viên":         COZY_ROLES.ADMIN,
    "Khách hàng":            COZY_ROLES.CUSTOMER,
    "Lễ tân":                COZY_ROLES.RECEPTIONIST,
    "Kế toán":               COZY_ROLES.ACCOUNTANT,
    "Nhân viên buồng phòng": COZY_ROLES.HOUSEKEEPING,
    "Quản lý chuỗi":         COZY_ROLES.MANAGER,
    "Demo":                  COZY_ROLES.CUSTOMER, // role gốc demo account fallback
  };
  return map[rawRole] || rawRole;
}

// ================================================================
// MAIN STATE OBJECT
// ================================================================
const state = {
  // Authentication State
  user: JSON.parse(localStorage.getItem("cozy_user") || "null"),
  token: localStorage.getItem("cozy_token") || null,
  isGuest: false,

  // Training / Demo Active Role (tách biệt hoàn toàn với user.role trong DB)
  // Chỉ có ý nghĩa với Demo Account — tài khoản thật dùng role từ DB.
  activeRole: localStorage.getItem("cozy_active_role") || null,

  // Metadata
  branches: [],
  slots: [],

  // Room & Search State
  rooms: [],
  selectedRoom: null,
  activeTab: "home",

  // Flow State
  regDraft: null,
  forgotEmail: null,
  pendingBooking: null,
  bookingTimerInterval: null,
  verifiedForgotOtp: null,
  sidebarFilters: {},

  // Pending room booking (khi bấm đặt phòng lúc chưa đăng nhập)
  pendingRoomToBook: null,
};

// ================================================================
// USER SESSION HELPERS
// ================================================================
function saveUserToStorage(user) {
  state.user = user;
  if (user) {
    localStorage.setItem("cozy_user", JSON.stringify(user));
  } else {
    localStorage.removeItem("cozy_user");
  }
}

function saveSessionToken(token) {
  state.token = token;
  if (token) {
    localStorage.setItem("cozy_token", token);
  } else {
    localStorage.removeItem("cozy_token");
  }
}

function clearUserSession() {
  state.user = null;
  state.token = null;
  state.isGuest = false;
  localStorage.removeItem("cozy_user");
  localStorage.removeItem("cozy_token");
  clearActiveRole();
}

// ================================================================
// DEMO ACCOUNT HELPERS
// ================================================================

/**
 * Kiểm tra xem user hiện tại có phải Demo Account không.
 * Nhận diện qua email — không suy luận từ display name.
 * @param {object|null} user
 * @returns {boolean}
 */
function isDemoAccount(user) {
  return user?.email === DEMO_ACCOUNT.email;
}

// ================================================================
// ACTIVE ROLE HELPERS — Training Mode (chỉ cho Demo Account)
// Không update DB, chỉ lưu trong localStorage với key riêng.
// Tài khoản thật KHÔNG dùng activeRole để thay đổi quyền.
// ================================================================

/**
 * Lưu vai trò trải nghiệm. Không thay đổi user.role trong DB.
 * @param {string} role - Một trong 6 giá trị COZY_ROLES
 */
function setActiveRole(role) {
  state.activeRole = role;
  if (role) {
    localStorage.setItem("cozy_active_role", role);
  } else {
    localStorage.removeItem("cozy_active_role");
  }
}

/**
 * Xóa activeRole — gọi khi logout hoặc Demo Account login mới.
 */
function clearActiveRole() {
  state.activeRole = null;
  localStorage.removeItem("cozy_active_role");
}

/**
 * Lấy activeRole hiện tại (raw, chưa normalize).
 * @returns {string|null}
 */
function getActiveRole() {
  return state.activeRole || null;
}

/**
 * Lấy vai trò hiệu quả để hiển thị UI/menu/phân quyền.
 *
 * PHÂN BIỆT:
 * - Demo Account (demo@cozyhome.vn): dùng activeRole do người dùng chọn trong Training Mode.
 *   → Cho phép trải nghiệm bất kỳ role nào mà không sửa DB.
 * - Tài khoản thật: chỉ dùng role từ DB.
 *   → Không thể tự chọn Admin/role khác để vượt quyền.
 *
 * @returns {string|null}
 */
function getEffectiveRole() {
  if (isDemoAccount(state.user)) {
    // Demo: dùng activeRole (normalize), chưa chọn role → null
    return state.activeRole ? normalizeRole(state.activeRole) : null;
  }
  // Tài khoản thật: luôn dùng role từ DB
  return normalizeRole(state.user?.role) || null;
}
