// -------------------------------------------------------------
// CozyHome Authentication & Profile Management
// Phân biệt rõ: user.role (DB) vs activeRole (Training session)
// -------------------------------------------------------------

// Badge màu theo vai trò (dùng normalizeRole để chuẩn hóa trước khi lookup)
const ROLE_BADGE_MAP = {
  "Khách hàng":            { bg: "#e8f5e9", color: "#2e7d32",  label: "Khách hàng" },
  "Lễ tân":                { bg: "#e3f2fd", color: "#1565c0",  label: "Lễ tân" },
  "Nhân viên buồng phòng": { bg: "#f3e5f5", color: "#6a1b9a",  label: "NV Buồng phòng" },
  "Kế toán":               { bg: "#fff3e0", color: "#e65100",  label: "Kế toán" },
  "Quản lý chuỗi":         { bg: "#fce4ec", color: "#880e4f",  label: "Quản lý chuỗi" },
  "Quản trị viên":         { bg: "#263238", color: "#fff",     label: "Quản trị viên" },
  // Backward compat
  "Buồng phòng":           { bg: "#f3e5f5", color: "#6a1b9a",  label: "NV Buồng phòng" },
  "Quản lý":               { bg: "#fce4ec", color: "#880e4f",  label: "Quản lý chuỗi" },
  "Admin":                 { bg: "#263238", color: "#fff",     label: "Quản trị viên" },
};

function getRoleBadgeHtml(role, branchId) {
  const normalized = typeof normalizeRole === "function" ? normalizeRole(role) : role;
  const cfg = ROLE_BADGE_MAP[normalized] || ROLE_BADGE_MAP[role] || { bg: "#f5f5f5", color: "#555", label: role };
  const branchSuffix = branchId ? ` - ${branchId}` : "";
  return `<span class="badge" style="background:${cfg.bg};color:${cfg.color};font-size:11.5px;font-weight:700;">${cfg.label}${branchSuffix}</span>`;
}

function updateAuthUI() {
  const guestNav = document.getElementById("nav-auth-guest");
  const userNav = document.getElementById("nav-auth-user");
  const opsLink = document.getElementById("nav-ops-link");
  const mobileOpsLink = document.getElementById("mobile-nav-ops-link");
  const guestBanner = document.getElementById("nav-guest-banner");

  if (state.user) {
    // ---- ĐĂNG NHẬP RỒI ----
    if (guestNav) guestNav.style.display = "none";
    if (guestBanner) guestBanner.style.display = "none";
    if (userNav) userNav.style.display = "flex";

    const nameEl = document.getElementById("nav-user-name");
    const nameFullEl = document.getElementById("nav-user-name-full");
    const roleEl = document.getElementById("nav-user-role");
    const avatarEl = document.getElementById("nav-user-avatar");

    if (nameEl) nameEl.textContent = state.user.full_name;
    if (nameFullEl) nameFullEl.textContent = state.user.full_name;
    if (avatarEl) {
      const initial = (state.user.full_name || "?").trim().charAt(0).toUpperCase();
      avatarEl.textContent = initial || "?";
    }

    // Hiển thị vai trò trong dropdown
    const effectiveRole = getEffectiveRole();
    if (roleEl) {
      if (isDemoAccount(state.user) && state.activeRole) {
        // Demo đang chọn role trải nghiệm
        roleEl.innerHTML = `<span style="font-size:11px;color:var(--text-muted);">Trải nghiệm:</span> <strong style="color:var(--cozy-primary);">${state.activeRole}</strong>`;
      } else if (isDemoAccount(state.user)) {
        // Demo nhưng chưa chọn role
        roleEl.textContent = "Chưa chọn vai trò";
      } else {
        // Tài khoản thật: hiển thị role DB
        const branchSuffix = state.user.branch_id ? ` - ${state.user.branch_id}` : "";
        roleEl.textContent = `${normalizeRole(state.user.role) || state.user.role}${branchSuffix}`;
      }
    }

    // Hiển thị nút Vận hành (Staff) hoặc Quản trị (Admin)
    const isAdmin = effectiveRole === COZY_ROLES.ADMIN;
    const isStaff = effectiveRole && effectiveRole !== COZY_ROLES.CUSTOMER && !isAdmin;

    const adminLink = document.getElementById("nav-admin-link");
    const mobileAdminLink = document.getElementById("mobile-nav-admin-link");

    if (opsLink) opsLink.style.display = isStaff ? "inline-block" : "none";
    if (mobileOpsLink) mobileOpsLink.style.display = isStaff ? "block" : "none";

    if (adminLink) adminLink.style.display = isAdmin ? "inline-block" : "none";
    if (mobileAdminLink) mobileAdminLink.style.display = isAdmin ? "block" : "none";

    // Chỉ hiển thị "Đổi vai trò trải nghiệm" cho Demo Account
    const switchRoleItem = document.getElementById("nav-switch-role-item");
    if (switchRoleItem) {
      switchRoleItem.style.display = isDemoAccount(state.user) ? "flex" : "none";
    }

  } else if (state.isGuest) {
    // ---- KHÁCH VÃNG LAI ----
    if (guestNav) guestNav.style.display = "none";
    if (userNav) userNav.style.display = "none";
    if (opsLink) opsLink.style.display = "none";
    if (mobileOpsLink) mobileOpsLink.style.display = "none";
    const adminLink = document.getElementById("nav-admin-link");
    const mobileAdminLink = document.getElementById("mobile-nav-admin-link");
    if (adminLink) adminLink.style.display = "none";
    if (mobileAdminLink) mobileAdminLink.style.display = "none";
    if (guestBanner) guestBanner.style.display = "flex";

  } else {
    // ---- CHƯA ĐĂNG NHẬP ----
    if (guestNav) guestNav.style.display = "flex";
    if (guestBanner) guestBanner.style.display = "none";
    if (userNav) userNav.style.display = "none";
    if (opsLink) opsLink.style.display = "none";
    if (mobileOpsLink) mobileOpsLink.style.display = "none";
    const adminLink = document.getElementById("nav-admin-link");
    const mobileAdminLink = document.getElementById("mobile-nav-admin-link");
    if (adminLink) adminLink.style.display = "none";
    if (mobileAdminLink) mobileAdminLink.style.display = "none";
  }
}

async function handleLogin(email, password, submitBtn) {
  if (submitBtn) submitBtn.classList.add("btn-loading");
  try {
    const res = await apiFetch("/api/auth/login", {
      method: "POST",
      body: { email, password },
    });

    saveUserToStorage(res.user);
    if (res.token) {
      saveSessionToken(res.token);
    }
    state.isGuest = false;

    // Xoá activeRole cũ — luôn bắt đầu sạch
    clearActiveRole();

    updateAuthUI();
    showToast(`Chào mừng ${res.user.full_name} đã đăng nhập!`, "success");

    // Pending booking: tiếp tục booking dở dang, bỏ qua role selection
    if (state.pendingRoomToBook) {
      const p = state.pendingRoomToBook;
      state.pendingRoomToBook = null;
      if (typeof performSearch === "function") performSearch();
      initiateBooking(p.roomId, p.bookingDate, p.slotCode, p.price, p.startTime, p.endTime);
      return;
    }

    if (typeof performSearch === "function") performSearch();

    // ★ PHÂN LUỒNG: Demo Account vs Tài khoản thật
    if (isDemoAccount(res.user)) {
      // Demo Account: bắt buộc chọn vai trò trước khi vào hệ thống
      if (window.history && window.history.pushState) {
        window.history.pushState(null, "", "/select-role");
      }
      navigateTo("select-role");
    } else {
      // Tài khoản thật: điều hướng thẳng theo role trong DB
      navigateByRealUserRole(res.user.role);
    }

  } catch (err) {
    // Lỗi đã được apiFetch toast
  } finally {
    if (submitBtn) submitBtn.classList.remove("btn-loading");
  }
}

async function handleRegisterComplete(otp, submitBtn) {
  if (!state.regDraft) {
    showToast("Vui lòng điền thông tin đăng ký trước.", "error");
    return;
  }
  if (!otp || otp.trim().length !== 6) {
    showToast("Vui lòng nhập đầy đủ mã OTP 6 chữ số.", "error");
    return;
  }
  if (submitBtn) submitBtn.classList.add("btn-loading");
  try {
    const payload = {
      email: state.regDraft.email,
      otp: otp.trim(),
      purpose: "register",
      full_name: state.regDraft.full_name,
      phone: state.regDraft.phone,
      password: state.regDraft.password,
    };

    const res = await apiFetch("/api/auth/register-complete", {
      method: "POST",
      body: payload,
    });

    saveUserToStorage(res.user);
    if (res.token) {
      saveSessionToken(res.token);
    }
    state.isGuest = false;
    clearActiveRole();
    resetRegisterForm();
    updateAuthUI();
    showToast(res.message || "Đăng ký tài khoản thành công! Chào mừng bạn đến CozyHome", "success");
    // Tài khoản mới đăng ký là Khách hàng — vào thẳng home
    navigateTo("home");
  } catch (err) {
  } finally {
    if (submitBtn) submitBtn.classList.remove("btn-loading");
  }
}

async function handleRegisterInit(formData, submitBtn) {
  if (submitBtn) submitBtn.classList.add("btn-loading");
  try {
    const res = await apiFetch("/api/auth/register-init", {
      method: "POST",
      body: formData,
    });

    state.regDraft = formData;
    showToast(res.message, "success");

    const initBox = document.getElementById("reg-step-init");
    const otpBox = document.getElementById("reg-step-otp");
    const maskedEmailEl = document.getElementById("reg-masked-email");

    if (initBox) initBox.style.display = "none";
    if (otpBox) otpBox.style.display = "block";
    if (maskedEmailEl && res.email_masked) {
      maskedEmailEl.textContent = res.email_masked;
    }

    if (res.delivery === "failed") {
      showToast("Không thể gửi email xác thực. Vui lòng kiểm tra lại địa chỉ hoặc thử lại sau.", "warning");
    }

    startOtpCountdown({
      expiryElId: "reg-otp-expiry",
      resendBtnId: "btn-resend-reg-otp",
      countdownElId: "reg-resend-countdown",
      inputElId: "reg-otp-input",
      expiresIn: res.expires_in || 300,
      resendAfter: res.resend_after || 60,
    });

    const otpInput = document.getElementById("reg-otp-input");
    if (otpInput) {
      otpInput.value = "";
      otpInput.focus();
    }
  } catch (err) {
  } finally {
    if (submitBtn) submitBtn.classList.remove("btn-loading");
  }
}

// -------------------------------------------------------------
// OTP Countdown Timers & Resend Helpers (UC-01, BR-OTP-01 - 05)
// -------------------------------------------------------------
let otpCountdownTimers = {};

function clearOtpTimers() {
  for (const k in otpCountdownTimers) {
    if (otpCountdownTimers[k]) clearInterval(otpCountdownTimers[k]);
  }
  otpCountdownTimers = {};
}

function startOtpCountdown({ expiryElId, resendBtnId, countdownElId, inputElId, expiresIn = 300, resendAfter = 60 }) {
  if (otpCountdownTimers[expiryElId]) clearInterval(otpCountdownTimers[expiryElId]);
  if (otpCountdownTimers[resendBtnId]) clearInterval(otpCountdownTimers[resendBtnId]);

  const expiryEl = document.getElementById(expiryElId);
  const resendBtn = document.getElementById(resendBtnId);
  const inputEl = document.getElementById(inputElId);

  if (inputEl) inputEl.disabled = false;

  // 1. Đồng hồ đếm ngược hiệu lực mã
  let remainSec = expiresIn;
  function updateExpiryDisplay() {
    if (!expiryEl) return;
    const m = Math.floor(remainSec / 60);
    const s = remainSec % 60;
    const str = `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    expiryEl.textContent = `Hiệu lực: ${str}`;
    if (remainSec <= 60) {
      expiryEl.style.color = "var(--danger, #c62828)";
    } else {
      expiryEl.style.color = "var(--cozy-primary, #b96b35)";
    }
  }
  updateExpiryDisplay();

  otpCountdownTimers[expiryElId] = setInterval(() => {
    remainSec--;
    if (remainSec <= 0) {
      clearInterval(otpCountdownTimers[expiryElId]);
      if (expiryEl) {
        expiryEl.textContent = "Mã đã hết hạn!";
        expiryEl.style.color = "var(--danger, #c62828)";
      }
      if (inputEl) inputEl.disabled = true;
      if (resendBtn) {
        resendBtn.disabled = false;
        resendBtn.textContent = "Gửi lại mã ngay";
      }
    } else {
      updateExpiryDisplay();
    }
  }, 1000);

  // 2. Đồng hồ cooldown gửi lại mã
  let cooldownSec = resendAfter;
  if (resendBtn) {
    resendBtn.disabled = true;
    resendBtn.innerHTML = `Gửi lại mã (<span id="${countdownElId}">${cooldownSec}</span>s)`;
  }

  otpCountdownTimers[resendBtnId] = setInterval(() => {
    cooldownSec--;
    const currentCountEl = document.getElementById(countdownElId);
    if (currentCountEl) currentCountEl.textContent = cooldownSec;

    if (cooldownSec <= 0) {
      clearInterval(otpCountdownTimers[resendBtnId]);
      if (resendBtn) {
        resendBtn.disabled = false;
        resendBtn.textContent = "Gửi lại mã";
      }
    }
  }, 1000);
}

async function handleResendRegisterOtp() {
  if (!state.regDraft || !state.regDraft.email) {
    showToast("Không tìm thấy thông tin đăng ký. Vui lòng quay lại điền thông tin.", "error");
    return;
  }
  const btn = document.getElementById("btn-resend-reg-otp");
  await handleResendOtp(state.regDraft.email, "register", btn, {
    expiryElId: "reg-otp-expiry",
    resendBtnId: "btn-resend-reg-otp",
    countdownElId: "reg-resend-countdown",
    inputElId: "reg-otp-input",
  });
}

async function handleResendForgotOtp() {
  if (!state.forgotEmail) {
    showToast("Không tìm thấy email khôi phục. Vui lòng điền lại email.", "error");
    return;
  }
  const btn = document.getElementById("btn-resend-forgot-otp");
  await handleResendOtp(state.forgotEmail, "forgot", btn, {
    expiryElId: "forgot-otp-expiry",
    resendBtnId: "btn-resend-forgot-otp",
    countdownElId: "forgot-resend-countdown",
    inputElId: "forgot-otp-input",
  });
}

async function handleResendOtp(email, purpose, btn, countdownConfig) {
  if (btn) btn.classList.add("btn-loading");
  try {
    const res = await apiFetch("/api/auth/resend-otp", {
      method: "POST",
      body: { email, purpose },
    });
    showToast(res.message, "success");
    if (countdownConfig) {
      startOtpCountdown({
        ...countdownConfig,
        expiresIn: res.expires_in || 300,
        resendAfter: res.resend_after || 60,
      });
    }
  } catch (err) {
  } finally {
    if (btn) btn.classList.remove("btn-loading");
  }
}

function resetRegisterForm() {
  state.regDraft = null;
  clearOtpTimers();

  const initBox = document.getElementById("reg-step-init");
  const otpBox = document.getElementById("reg-step-otp");
  if (initBox) initBox.style.display = "block";
  if (otpBox) otpBox.style.display = "none";

  const form = document.getElementById("form-register");
  if (form) form.reset();

  const otpInput = document.getElementById("reg-otp-input");
  if (otpInput) otpInput.value = "";

  const maskedEmail = document.getElementById("reg-masked-email");
  if (maskedEmail) maskedEmail.textContent = "email của bạn";

  const expiryEl = document.getElementById("reg-otp-expiry");
  if (expiryEl) {
    expiryEl.textContent = "Hiệu lực: 05:00";
    expiryEl.style.color = "var(--cozy-primary, #b96b35)";
  }

  const resendBtn = document.getElementById("btn-resend-reg-otp");
  if (resendBtn) {
    resendBtn.disabled = true;
    resendBtn.innerHTML = `Gửi lại mã (<span id="reg-resend-countdown">60</span>s)`;
  }
}

function cancelRegDraft() {
  resetRegisterForm();
}

function setupOtpInputFormatting(inputId, onCompleteCallback) {
  const el = document.getElementById(inputId);
  if (!el) return;
  el.addEventListener("input", () => {
    el.value = el.value.replace(/\D/g, "").slice(0, 6);
    if (el.value.length === 6 && typeof onCompleteCallback === "function") {
      onCompleteCallback(el.value);
    }
  });
  el.addEventListener("paste", (e) => {
    e.preventDefault();
    const clipText = (e.clipboardData || window.clipboardData).getData("text");
    const digits = clipText.replace(/\D/g, "").slice(0, 6);
    el.value = digits;
    if (digits.length === 6 && typeof onCompleteCallback === "function") {
      onCompleteCallback(digits);
    }
  });
}

function initOtpInputs() {
  setupOtpInputFormatting("reg-otp-input", (code) => {
    const btn = document.getElementById("btn-verify-reg-otp");
    handleRegisterComplete(code, btn);
  });
  setupOtpInputFormatting("forgot-otp-input", (code) => {
    if (typeof submitForgotVerify === "function") {
      submitForgotVerify();
    }
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initOtpInputs);
} else {
  initOtpInputs();
}

// ================================================================
// DEMO ACCOUNT HELPERS — TRAINING / DEMO ONLY
// ================================================================

/**
 * Làm sạch form đăng nhập về trạng thái trống hoàn toàn.
 * Chống tự động điền (autofill) các tài khoản lưu trong cache trình duyệt.
 */
function resetLoginForm() {
  const emailInput = document.getElementById("login-email");
  const passInput = document.getElementById("login-pass");
  if (emailInput) {
    emailInput.value = "";
    emailInput.defaultValue = "";
  }
  if (passInput) {
    passInput.value = "";
    passInput.defaultValue = "";
  }
}

/**
 * Điền sẵn thông tin Demo Account vào form đăng nhập.
 * Không tự đăng nhập, để người dùng bấm nút THEO QUY TRÌNH.
 * Chỉ inject vào form (phương án B theo yêu cầu).
 * Không lưu password vào localStorage.
 */
function useDemoAccount() {
  if (typeof switchAuthTab === "function") switchAuthTab("login");
  const emailInput = document.getElementById("login-email");
  const passInput = document.getElementById("login-pass");
  if (emailInput) emailInput.value = DEMO_ACCOUNT.email;
  if (passInput) passInput.value = DEMO_ACCOUNT.password;
  emailInput?.focus();
  showToast("Đã điền tài khoản Demo. Nhấn ĐĂNG NHẬP để tiếp tục.", "info");
}

/**
 * Điền sẵn và đăng nhập ngay (phục vụ trình diễn nhanh).
 * Vẫn gọi API login thật, không bypass authentication.
 */
function fillDemoAndLogin() {
  if (typeof switchAuthTab === "function") switchAuthTab("login");
  const emailInput = document.getElementById("login-email");
  const passInput = document.getElementById("login-pass");
  if (emailInput) emailInput.value = DEMO_ACCOUNT.email;
  if (passInput) passInput.value = DEMO_ACCOUNT.password;
  const btn = document.getElementById("btn-submit-login");
  handleLogin(DEMO_ACCOUNT.email, DEMO_ACCOUNT.password, btn);
}

/**
 * [DEPRECATED] quickLogin(role) cũ — giữ lại để không bể gọi cũ, nhưng
 * không còn gắn với các nút trên UI nữa.
 * @deprecated Dùng useDemoAccount() hoặc fillDemoAndLogin() thay thế.
 */
function quickLogin(role) {
  console.warn("quickLogin() is deprecated. Use useDemoAccount() instead.");
  fillDemoAndLogin();
}

function enterAsGuest() {
  state.isGuest = true;
  state.user = null;
  clearActiveRole();
  updateAuthUI();
  showToast("Đang xem phòng với tư cách Khách vãng lai. Đăng nhập để đặt phòng!", "info");
  navigateTo("home");
}

function logout() {
  if (state.token) {
    apiFetch("/api/auth/logout", { method: "POST" }).catch(() => {});
  }
  clearUserSession(); // clearActiveRole() đã được gọi bên trong clearUserSession()
  state.isGuest = false;
  if (typeof resetLoginForm === "function") resetLoginForm();
  if (typeof resetRegisterForm === "function") resetRegisterForm();
  if (typeof resetForgotForm === "function") resetForgotForm();
  updateAuthUI();
  showToast("Bạn đã đăng xuất khỏi hệ thống.", "info");
  navigateTo("auth");
}

async function loadProfile() {
  if (!state.user) {
    navigateTo("auth");
    return;
  }

  try {
    const res = await apiFetch(`/api/auth/profile/${state.user.id}`);
    const u = res.user;
    const s = res.stats;

    const nameEl = document.getElementById("profile-name-val");
    const emailEl = document.getElementById("profile-email-val");
    const phoneEl = document.getElementById("profile-phone-val");
    const roleEl = document.getElementById("profile-role-val");

    if (nameEl) nameEl.textContent = u.full_name;
    if (emailEl) emailEl.textContent = u.email;
    if (phoneEl) phoneEl.textContent = u.phone || "Chưa cập nhật";
    if (roleEl) roleEl.innerHTML = getRoleBadgeHtml(u.role, u.branch_id);

    const editName = document.getElementById("edit-profile-name");
    const editPhone = document.getElementById("edit-profile-phone");
    if (editName) editName.value = u.full_name;
    if (editPhone) editPhone.value = u.phone || "";

    const statBookings = document.getElementById("stat-total-bookings");
    const statSpent = document.getElementById("stat-total-spent");
    const statCompleted = document.getElementById("stat-completed-stays");
    if (statBookings) statBookings.textContent = s.total_bookings;
    if (statSpent) statSpent.textContent = formatMoney(s.total_spent);
    if (statCompleted) statCompleted.textContent = s.completed_stays;
  } catch (err) {}
}
