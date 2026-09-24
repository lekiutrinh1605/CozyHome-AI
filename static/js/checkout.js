// =============================================================
// COZYHOME CHECKOUT & CONFIRMATION LOGIC
// =============================================================

let currentAppliedPromo = null;
let currentDiscountAmount = 0;
let currentFinalAmount = null;

/**
 * Format currency VND
 */
function formatCheckoutVnd(val) {
  if (val === undefined || val === null) return "0 ₫";
  return Number(val).toLocaleString("vi-VN") + " ₫";
}

/**
 * Format ISO date string (YYYY-MM-DD) to friendly Vietnamese date
 */
function formatFriendlyDate(dateStr) {
  if (!dateStr) return "";
  try {
    const parts = dateStr.split("-");
    if (parts.length === 3) {
      const year = parseInt(parts[0], 10);
      const month = parseInt(parts[1], 10) - 1;
      const day = parseInt(parts[2], 10);
      const d = new Date(year, month, day);
      const daysOfWeek = ["Chủ Nhật", "Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy"];
      const dayName = daysOfWeek[d.getDay()];
      const padDay = String(day).padStart(2, "0");
      const padMonth = String(month + 1).padStart(2, "0");
      return `${dayName}, ${padDay}/${padMonth}/${year}`;
    }
  } catch (e) {
    // Fallback
  }
  return dateStr;
}

/**
 * Main function called by app.js router when switching to view-checkout
 */
function renderCheckoutPage() {
  const container = document.getElementById("view-checkout");
  if (!container) return;

  const pb = state.pendingBooking;
  if (!pb || !pb.room_id) {
    container.innerHTML = `
      <div class="checkout-empty-state">
        <div class="checkout-empty-icon"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 4v16"></path><path d="M2 8h18a2 2 0 0 1 2 2v10"></path><path d="M2 17h20"></path><path d="M6 8v9"></path></svg></div>
        <h3 class="checkout-empty-title">Chưa có phòng nào được chọn</h3>
        <p class="checkout-empty-desc">
          Vui lòng chọn một căn phòng yêu thích trên Trang chủ để tiến hành xác nhận đặt phòng và chuyển sang bước thanh toán.
        </p>
        <button class="btn btn-primary" onclick="navigateTo('home')">
          ← Khám phá danh sách phòng ngay
        </button>
      </div>
    `;
    return;
  }

  // Determine branch name
  const branchName = pb.branch_name || (pb.branch_id === "BT" ? "CozyHome Bến Thành - Q.1" : pb.branch_id === "TD" ? "CozyHome Thảo Điền - Thủ Đức" : "CozyHome Phú Mỹ Hưng - Q.7");
  const friendlyDate = formatFriendlyDate(pb.booking_date);
  
  // Format slot name with specific hours
  const slotHoursMap = {
    K1: "09:30 – 12:30 (Sáng)",
    K2: "13:00 – 16:00 (Chiều)",
    K3: "16:30 – 19:30 (Tối)",
    QD: "20:00 – 08:30 (Qua đêm)",
    K4: "20:00 – 08:30 (Qua đêm)"
  };
  const slotDisplay = slotHoursMap[pb.khung_code] || (pb.start_time && pb.end_time ? `${pb.start_time} – ${pb.end_time.replace('+1', '')}` : pb.khung_code || "09:30 – 12:30 (Sáng)");

  const timeRange = (pb.start_time && pb.end_time) ? `${pb.start_time} → ${pb.end_time.replace('+1', '')}` : "Theo khung chuẩn";
  const stayType = pb.khung_code === "K4" ? "Lưu trú qua đêm" : "Homestay theo khung giờ";
  const guestsCount = pb.capacity ? `${pb.capacity} khách tối đa` : "2 khách";

  // Determine real room image
  let roomImg = "/static/images/banner-hero.png";
  if (pb.images && pb.images.length > 0) {
    roomImg = pb.images[0];
  } else if (pb.room_id && pb.branch_id) {
    roomImg = `/static/images/rooms/${pb.branch_id}/${pb.room_id}-1.png`;
  }

  // Pre-fill user data if logged in
  let userHo = "";
  let userTen = "";
  let userPhone = "";
  let userEmail = "";

  if (state.user) {
    userPhone = state.user.phone || "";
    userEmail = state.user.email || "";
    const nameParts = (state.user.full_name || "").trim().split(" ");
    if (nameParts.length > 1) {
      userHo = nameParts.slice(0, -1).join(" ");
      userTen = nameParts[nameParts.length - 1];
    } else if (nameParts.length === 1) {
      userTen = nameParts[0];
    }
  }

  // Render full 2-column layout template
  container.innerHTML = `
    <!-- Top Header Bar with Breadcrumb và Stepper -->
    <div class="checkout-header-bar">
      <a class="checkout-back-link" onclick="navigateTo('home'); return false;">
        ← Đổi phòng khác
      </a>

      <div class="checkout-stepper">
        <div class="checkout-step-item active">
          <div class="step-bubble">1</div>
          <span>Xác nhận</span>
        </div>
        <div class="step-divider-line"></div>
        <div class="checkout-step-item">
          <div class="step-bubble">2</div>
          <span>Thanh toán</span>
        </div>
        <div class="step-divider-line"></div>
        <div class="checkout-step-item">
          <div class="step-bubble">3</div>
          <span>Hoàn tất</span>
        </div>
      </div>
    </div>

    <!-- Main Checkout 2-Column Grid -->
    <div class="checkout-grid">
      <!-- LEFT COLUMN: Main Information Card -->
      <div class="checkout-main-card">
        
        <!-- SECTION 1: SELECTED ROOM SUMMARY -->
        <div class="checkout-room-banner">
          <div class="checkout-room-thumb-wrap">
            <img 
              src="${roomImg}" 
              alt="${pb.room_name || pb.room_id}" 
              class="checkout-room-thumb" 
              onerror="this.src='/static/images/banner-hero.png'" 
            />
          </div>
          <div class="checkout-room-details">
            <div class="checkout-room-header-row">
              <span class="checkout-room-code-badge">${pb.room_id}</span>
              <span class="badge badge-cozy" style="font-size:11.5px;">${pb.concept_name || "Bắc Âu ấm cúng"}</span>
            </div>
            <h3 class="checkout-room-name">${pb.room_name || pb.room_id}</h3>
            
            <div class="checkout-room-meta-grid">
              <div class="checkout-meta-item">
                
                <span><b>${branchName}</b></span>
              </div>
              <div class="checkout-meta-item">
                
                <span>Nhận phòng: <b>${friendlyDate}</b></span>
              </div>
              <div class="checkout-meta-item">
                
                <span>Khung giờ: <b>${slotDisplay}</b></span>
              </div>
              <div class="checkout-meta-item">
                
                <span>Sức chứa: <b>${guestsCount}</b></span>
              </div>
            </div>

            <div class="checkout-room-tags">
              <span class="checkout-room-tag">${stayType}</span>
              <span class="checkout-room-tag">Khử khuẩn tiêu chuẩn</span>
              <span class="checkout-room-tag">Wifi 500Mbps</span>
              <span class="checkout-room-tag">Smart lock riêng tư</span>
            </div>
          </div>
        </div>

        <hr class="checkout-divider" />

        <!-- SECTION 2: CONTACT INFORMATION -->
        <div class="checkout-section">
          <div class="checkout-section-title">
            
            <span>Thông tin liên hệ</span>
          </div>
          <p class="checkout-section-desc">
            Thông tin xác nhận đặt phòng và mã nhận phòng tự động sẽ được gửi đến thông tin liên hệ bên dưới.
          </p>

          <div class="checkout-form-row-2">
            <div class="checkout-field-wrap">
              <label class="checkout-label" for="checkout-ho">
                Họ đệm<span class="required-star">*</span>
              </label>
              <input 
                type="text" 
                id="checkout-ho" 
                class="checkout-input" 
                placeholder="Ví dụ: Nguyễn Văn" 
                value="${userHo}" 
                oninput="handleContactInput(this)" 
              />
              <span id="error-checkout-ho" class="checkout-error-text">Bắt buộc nhập họ đệm.</span>
            </div>

            <div class="checkout-field-wrap">
              <label class="checkout-label" for="checkout-ten">
                Tên<span class="required-star">*</span>
              </label>
              <input 
                type="text" 
                id="checkout-ten" 
                class="checkout-input" 
                placeholder="Ví dụ: An" 
                value="${userTen}" 
                oninput="handleContactInput(this)" 
              />
              <span id="error-checkout-ten" class="checkout-error-text">Bắt buộc nhập tên.</span>
            </div>
          </div>

          <div class="checkout-form-row-2">
            <div class="checkout-field-wrap">
              <label class="checkout-label" for="checkout-phone">
                Số điện thoại di động<span class="required-star">*</span>
              </label>
              <input 
                type="tel" 
                id="checkout-phone" 
                class="checkout-input" 
                placeholder="Ví dụ: 0909000001" 
                value="${userPhone}" 
                oninput="handleContactInput(this)" 
              />
              <span id="error-checkout-phone" class="checkout-error-text">Số điện thoại không hợp lệ (cần 10 chữ số).</span>
            </div>

            <div class="checkout-field-wrap">
              <label class="checkout-label" for="checkout-email">
                Địa chỉ Email<span class="required-star">*</span>
              </label>
              <input 
                type="email" 
                id="checkout-email" 
                class="checkout-input" 
                placeholder="Ví dụ: demo@cozyhome.vn" 
                value="${userEmail}" 
                oninput="handleContactInput(this)" 
              />
              <span id="error-checkout-email" class="checkout-error-text">Email không đúng định dạng.</span>
            </div>
          </div>

          <!-- Checkbox sync guest info -->
          <label class="checkout-checkbox-wrap" for="chk-same-guest">
            <input type="checkbox" id="chk-same-guest" checked onchange="handleGuestSyncToggle()" />
            <span class="checkout-checkbox-label">
              <b>Người đặt phòng cũng là người lưu trú</b> (Thông tin khách nhận phòng sẽ tự động đồng bộ).
            </span>
          </label>
        </div>

        <hr class="checkout-divider" />

        <!-- SECTION 3: GUEST INFORMATION -->
        <div class="checkout-section">
          <div class="checkout-section-title">
            
            <span>Thông tin khách lưu trú</span>
          </div>
          <p class="checkout-section-desc">
            Thông tin của khách đại diện nhận phòng và xuất trình giấy tờ tùy thân tại cơ sở.
          </p>

          <div class="checkout-form-row-2">
            <div class="checkout-field-wrap">
              <label class="checkout-label" for="checkout-guest-ho">
                Họ đệm khách nhận phòng<span class="required-star">*</span>
              </label>
              <input 
                type="text" 
                id="checkout-guest-ho" 
                class="checkout-input" 
                placeholder="Ví dụ: Nguyễn Văn" 
                value="${userHo}" 
                disabled 
                oninput="handleGuestInput(this)" 
              />
              <span id="error-checkout-guest-ho" class="checkout-error-text">Bắt buộc nhập họ đệm khách lưu trú.</span>
            </div>

            <div class="checkout-field-wrap">
              <label class="checkout-label" for="checkout-guest-ten">
                Tên khách nhận phòng<span class="required-star">*</span>
              </label>
              <input 
                type="text" 
                id="checkout-guest-ten" 
                class="checkout-input" 
                placeholder="Ví dụ: An" 
                value="${userTen}" 
                disabled 
                oninput="handleGuestInput(this)" 
              />
              <span id="error-checkout-guest-ten" class="checkout-error-text">Bắt buộc nhập tên khách lưu trú.</span>
            </div>
          </div>

          <div class="checkout-guest-notice">
            
            <div>
              <b>Lưu ý quan trọng:</b> Quý khách vui lòng xuất trình CMND/CCCD hoặc Hộ chiếu khớp với tên khách lưu trú khi làm thủ tục nhận phòng tại quầy lễ tân.
            </div>
          </div>
        </div>

        <hr class="checkout-divider" />

        <!-- SECTION 4: SPECIAL REQUESTS -->
        <div class="checkout-section">
          <div class="checkout-section-title">
            
            <span>Yêu cầu đặc biệt</span>
          </div>
          <p class="checkout-section-desc">
            CozyHome sẽ nỗ lực tối đa để đáp ứng yêu cầu của bạn tùy theo tình trạng thực tế tại cơ sở khi nhận phòng.
          </p>

          <div class="checkout-chips-grid" id="checkout-request-chips">
            <button type="button" class="checkout-chip-btn" data-req="Phòng yên tĩnh" onclick="toggleRequestChip(this)">
              
              <span>Phòng yên tĩnh</span>
            </button>
            <button type="button" class="checkout-chip-btn" data-req="Tầng cao" onclick="toggleRequestChip(this)">
              
              <span>Tầng cao</span>
            </button>
            <button type="button" class="checkout-chip-btn" data-req="Gần thang máy" onclick="toggleRequestChip(this)">
              
              <span>Gần thang máy</span>
            </button>
            <button type="button" class="checkout-chip-btn" data-req="Nhận phòng sớm" onclick="toggleRequestChip(this)">
              
              <span>Nhận phòng sớm</span>
            </button>
            <button type="button" class="checkout-chip-btn" data-req="Trả phòng muộn" onclick="toggleRequestChip(this)">
              
              <span>Trả phòng muộn</span>
            </button>
          </div>

          <div class="checkout-textarea-wrap">
            <label class="checkout-label" for="checkout-note">
              Ghi chú cho CozyHome (tùy chọn)
            </label>
            <textarea 
              id="checkout-note" 
              class="checkout-textarea" 
              rows="3" 
              maxlength="300" 
              placeholder="Nhập ghi chú thêm cho cơ sở (ví dụ: cần thêm chăn gối, đến trước 15 phút...)" 
              oninput="handleNoteInput(this)"
            ></textarea>
            <span id="checkout-char-counter" class="checkout-char-counter">0 / 300 ký tự</span>
          </div>
        </div>

      </div>

      <!-- RIGHT COLUMN: Sticky Price Summary Card -->
      <div class="checkout-sidebar-sticky">
        <div class="checkout-price-card">
          <div class="checkout-price-card-header">
            <h4 class="checkout-price-card-title">
               Chi tiết thanh toán
            </h4>
            <span class="badge badge-cozy">${pb.branch_id || "CozyHome"}</span>
          </div>

          <div class="checkout-price-rows">
            <div class="checkout-price-row">
              <span class="checkout-price-label">Giá thuê phòng</span>
              <span class="checkout-price-val">${formatCheckoutVnd(pb.amount)}</span>
            </div>

            <div class="checkout-price-row">
              <span class="checkout-price-label">Thời lượng lưu trú</span>
              <span class="checkout-price-val">${pb.khung_code === "K4" ? "1 đêm qua đêm" : "1 khung giờ"}</span>
            </div>

            <div class="checkout-price-row free-item">
              <span class="checkout-price-label">Phí dịch vụ và tiện ích</span>
              <span class="checkout-price-val">0 ₫ (Miễn phí)</span>
            </div>

            <div class="checkout-price-row" id="checkout-discount-row" style="display:none;">
              <span class="checkout-price-label" id="checkout-discount-label" style="color:var(--success); font-weight:700;">Khuyến mãi</span>
              <span class="checkout-price-val" id="checkout-discount-val" style="color:var(--success); font-weight:800;">-0 ₫</span>
            </div>
          </div>

          <!-- SECTION: MÃ KHUYẾN MÃI / VOUCHER -->
          <div class="checkout-promo-box">
            <div class="checkout-promo-header-row">
              <span class="checkout-promo-title">Mã ưu đãi / Voucher</span>
              <a href="#" onclick="openPromotionsModal(); return false;" class="checkout-promo-link">Xem tất cả</a>
            </div>
            
            <div class="checkout-promo-input-wrap" id="checkout-promo-input-group">
              <input 
                type="text" 
                id="checkout-promo-input" 
                class="checkout-promo-input" 
                placeholder="Nhập mã (ví dụ: EARLYBIRD10)"
                autocomplete="off"
                onkeypress="if(event.key==='Enter'){ event.preventDefault(); handleApplyPromoCode(); }"
              />
              <button 
                type="button" 
                id="btn-apply-promo" 
                class="btn btn-primary checkout-promo-btn" 
                onclick="handleApplyPromoCode()"
              >
                Áp dụng
              </button>
            </div>

            <!-- Tag khi áp dụng mã thành công -->
            <div id="checkout-promo-applied-tag" class="checkout-promo-applied-tag" style="display:none;">
              <div class="checkout-promo-applied-info">
                <span class="checkout-promo-check">✓</span>
                <span id="checkout-promo-applied-text">Mã EARLYBIRD10: -15.000 ₫</span>
              </div>
              <button type="button" class="checkout-promo-remove-btn" onclick="handleRemovePromoCode()" title="Bỏ áp dụng mã">&times;</button>
            </div>

            <!-- Gợi ý nhanh các voucher phổ biến -->
            <div class="checkout-promo-chips">
              <span class="checkout-promo-chip-label">Gợi ý:</span>
              <button type="button" class="checkout-promo-chip" onclick="quickApplyPromo('EARLYBIRD10')">Đặt sớm -10%</button>
              <button type="button" class="checkout-promo-chip" onclick="quickApplyPromo('MIDWEEK15')">Qua đêm -15%</button>
              <button type="button" class="checkout-promo-chip" onclick="quickApplyPromo('COZYMEMBER')">Thành viên -30K</button>
            </div>
          </div>

          <!-- Total Amount Box -->
          <div class="checkout-total-box">
            <div class="checkout-total-row">
              <span class="checkout-total-label">Tổng cộng</span>
              <span class="checkout-total-val" id="checkout-total-display">${formatCheckoutVnd(pb.amount)}</span>
            </div>
            <div class="checkout-total-note">
              ✓ Đã bao gồm thuế GTGT và các chi phí vệ sinh theo quy chuẩn CozyHome.
            </div>
          </div>

          <!-- Main CTA Confirm & Pay Button -->
          <button 
            type="button" 
            id="btn-checkout-submit" 
            class="btn btn-primary checkout-cta-btn" 
            onclick="handleProceedPayment()"
          >
            Tiếp tục thanh toán →
          </button>

          <!-- Terms and Policy Links -->
          <p class="checkout-terms-disclaimer">
            Bằng việc tiếp tục, bạn đồng ý với 
            <a class="checkout-terms-link" onclick="openCheckoutPolicyModal('terms'); return false;">Điều khoản sử dụng</a> 
            và 
            <a class="checkout-terms-link" onclick="openCheckoutPolicyModal('policy'); return false;">Chính sách đặt phòng</a> 
            của CozyHome.
          </p>
        </div>

        <!-- Trust Badges Card -->
        <div class="checkout-trust-card">
          <div class="checkout-trust-item">
            
            <div><b>Giữ phòng đảm bảo trong 10 phút</b> sau khi bấm thanh toán.</div>
          </div>
          <div class="checkout-trust-item">
            
            <div><b>Chuyển khoản VietQR MBBank</b> nhanh chóng qua tất cả các ứng dụng ngân hàng.</div>
          </div>
          <div class="checkout-trust-item">
            
            <div><b>Chính sách hủy minh bạch:</b> Hủy trước ≥ 24h hoàn 100%, từ 12h–24h hoàn 50%. Giá trọn gói không phí ẩn.</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Mobile Sticky Bottom Summary Bar -->
    <div class="checkout-mobile-bottom-bar">
      <div class="checkout-mobile-total-wrap">
        <span class="checkout-mobile-total-label">Tổng thanh toán</span>
        <span class="checkout-mobile-total-val">${formatCheckoutVnd(pb.amount)}</span>
      </div>
      <button 
        type="button" 
        class="btn btn-primary" 
        style="height:42px; padding:0 20px; font-weight:700;" 
        onclick="handleProceedPayment()"
      >
        Thanh toán ngay →
      </button>
    </div>
  `;

  // Initialize event listeners and states
  initCheckoutEvents();
}

/**
 * Sync guest inputs with contact inputs if checkbox is checked
 */
function handleGuestSyncToggle() {
  const chk = document.getElementById("chk-same-guest");
  const guestHo = document.getElementById("checkout-guest-ho");
  const guestTen = document.getElementById("checkout-guest-ten");
  const contactHo = document.getElementById("checkout-ho");
  const contactTen = document.getElementById("checkout-ten");

  if (!chk || !guestHo || !guestTen) return;

  if (chk.checked) {
    guestHo.value = contactHo ? contactHo.value : "";
    guestTen.value = contactTen ? contactTen.value : "";
    guestHo.disabled = true;
    guestTen.disabled = true;
    clearFieldError("checkout-guest-ho");
    clearFieldError("checkout-guest-ten");
  } else {
    guestHo.disabled = false;
    guestTen.disabled = false;
  }
}

/**
 * Handle real-time input in contact fields
 */
function handleContactInput(inputEl) {
  if (!inputEl) return;
  clearFieldError(inputEl.id);

  // If checkbox sync is on, update guest fields too
  const chk = document.getElementById("chk-same-guest");
  if (chk && chk.checked) {
    if (inputEl.id === "checkout-ho") {
      const gHo = document.getElementById("checkout-guest-ho");
      if (gHo) gHo.value = inputEl.value;
    } else if (inputEl.id === "checkout-ten") {
      const gTen = document.getElementById("checkout-guest-ten");
      if (gTen) gTen.value = inputEl.value;
    }
  }
}

/**
 * Handle real-time input in guest fields
 */
function handleGuestInput(inputEl) {
  if (!inputEl) return;
  clearFieldError(inputEl.id);
}

/**
 * Clear field error styles
 */
function clearFieldError(fieldId) {
  const el = document.getElementById(fieldId);
  const errEl = document.getElementById(`error-${fieldId}`);
  if (el) el.classList.remove("is-invalid");
  if (errEl) errEl.classList.remove("show");
}

/**
 * Show field error
 */
function setFieldError(fieldId, customMsg) {
  const el = document.getElementById(fieldId);
  const errEl = document.getElementById(`error-${fieldId}`);
  if (el) el.classList.add("is-invalid");
  if (errEl) {
    if (customMsg) errEl.textContent = customMsg;
    errEl.classList.add("show");
  }
}

/**
 * Toggle special request chip button
 */
function toggleRequestChip(btn) {
  if (!btn) return;
  btn.classList.toggle("active");
}

/**
 * Handle note character counter
 */
function handleNoteInput(textarea) {
  if (!textarea) return;
  const countEl = document.getElementById("checkout-char-counter");
  if (countEl) {
    countEl.textContent = `${textarea.value.length} / 300 ký tự`;
  }
}

/**
 * Form validation logic
 */
function validateCheckoutForm() {
  let isValid = true;
  let firstInvalidEl = null;

  const ho = document.getElementById("checkout-ho");
  const ten = document.getElementById("checkout-ten");
  const phone = document.getElementById("checkout-phone");
  const email = document.getElementById("checkout-email");
  const chk = document.getElementById("chk-same-guest");
  const guestHo = document.getElementById("checkout-guest-ho");
  const guestTen = document.getElementById("checkout-guest-ten");

  // 1. Validate Họ đệm
  if (!ho || !ho.value.trim()) {
    setFieldError("checkout-ho", "Bắt buộc nhập họ đệm.");
    isValid = false;
    if (!firstInvalidEl) firstInvalidEl = ho;
  } else {
    clearFieldError("checkout-ho");
  }

  // 2. Validate Tên
  if (!ten || !ten.value.trim()) {
    setFieldError("checkout-ten", "Bắt buộc nhập tên.");
    isValid = false;
    if (!firstInvalidEl) firstInvalidEl = ten;
  } else {
    clearFieldError("checkout-ten");
  }

  // 3. Validate Số điện thoại (VN: 10 digits starting with 03, 05, 07, 08, 09)
  const phoneVal = phone ? phone.value.trim().replace(/\s+/g, "") : "";
  const phoneRegex = /^(0[3|5|7|8|9])[0-9]{8}$/;
  if (!phoneVal) {
    setFieldError("checkout-phone", "Bắt buộc nhập số điện thoại.");
    isValid = false;
    if (!firstInvalidEl) firstInvalidEl = phone;
  } else if (!phoneRegex.test(phoneVal)) {
    setFieldError("checkout-phone", "Số điện thoại không hợp lệ (cần 10 chữ số VN, ví dụ: 0909000001).");
    isValid = false;
    if (!firstInvalidEl) firstInvalidEl = phone;
  } else {
    clearFieldError("checkout-phone");
  }

  // 4. Validate Email
  const emailVal = email ? email.value.trim() : "";
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailVal) {
    setFieldError("checkout-email", "Bắt buộc nhập địa chỉ email.");
    isValid = false;
    if (!firstInvalidEl) firstInvalidEl = email;
  } else if (!emailRegex.test(emailVal)) {
    setFieldError("checkout-email", "Email không đúng định dạng (ví dụ: demo@cozyhome.vn).");
    isValid = false;
    if (!firstInvalidEl) firstInvalidEl = email;
  } else {
    clearFieldError("checkout-email");
  }

  // 5. Validate Khách lưu trú (nếu không đồng bộ)
  if (chk && !chk.checked) {
    if (!guestHo || !guestHo.value.trim()) {
      setFieldError("checkout-guest-ho", "Bắt buộc nhập họ đệm khách lưu trú.");
      isValid = false;
      if (!firstInvalidEl) firstInvalidEl = guestHo;
    } else {
      clearFieldError("checkout-guest-ho");
    }

    if (!guestTen || !guestTen.value.trim()) {
      setFieldError("checkout-guest-ten", "Bắt buộc nhập tên khách lưu trú.");
      isValid = false;
      if (!firstInvalidEl) firstInvalidEl = guestTen;
    } else {
      clearFieldError("checkout-guest-ten");
    }
  }

  if (firstInvalidEl) {
    firstInvalidEl.focus();
    showToast("Vui lòng kiểm tra và điền đầy đủ các thông tin bắt buộc (*).", "warning");
  }

  return isValid;
}

/**
 * Handle Confirm and Proceed to Payment
 */
async function handleProceedPayment() {
  const pb = state.pendingBooking;
  if (!pb) {
    showToast("Phiên đặt phòng không còn khả dụng. Vui lòng chọn lại phòng.", "danger");
    navigateTo("home");
    return;
  }

  // Validate form
  if (!validateCheckoutForm()) {
    return;
  }

  // Collect form data
  const ho = document.getElementById("checkout-ho")?.value.trim() || "";
  const ten = document.getElementById("checkout-ten")?.value.trim() || "";
  const phone = document.getElementById("checkout-phone")?.value.trim() || "";
  const email = document.getElementById("checkout-email")?.value.trim() || "";
  const chk = document.getElementById("chk-same-guest");
  
  let guestHo = ho;
  let guestTen = ten;
  if (chk && !chk.checked) {
    guestHo = document.getElementById("checkout-guest-ho")?.value.trim() || ho;
    guestTen = document.getElementById("checkout-guest-ten")?.value.trim() || ten;
  }

  const customerName = `${ho} ${ten}`.trim();
  const guestName = `${guestHo} ${guestTen}`.trim();

  // Collect active special requests
  const activeChips = [];
  document.querySelectorAll("#checkout-request-chips .checkout-chip-btn.active").forEach(b => {
    const req = b.getAttribute("data-req");
    if (req) activeChips.push(req);
  });

  const rawNote = document.getElementById("checkout-note")?.value.trim() || "";
  
  // Compile comprehensive note for booking
  const noteParts = [];
  if (guestName && guestName !== customerName) {
    noteParts.push(`[Khách nhận phòng: ${guestName}]`);
  }
  if (activeChips.length > 0) {
    noteParts.push(`[Yêu cầu: ${activeChips.join(", ")}]`);
  }
  if (rawNote) {
    noteParts.push(`[Ghi chú: ${rawNote}]`);
  }
  const compiledNote = noteParts.join(" ");

  // Set loading state on submit buttons
  const btnDesktop = document.getElementById("btn-checkout-submit");
  const mobileButtons = document.querySelectorAll(".checkout-mobile-bottom-bar .btn");

  if (btnDesktop) {
    btnDesktop.classList.add("btn-loading");
    btnDesktop.disabled = true;
  }
  mobileButtons.forEach(b => {
    b.classList.add("btn-loading");
    b.disabled = true;
  });

  try {
    const payload = {
      user_id: state.user ? state.user.id : null,
      room_id: pb.room_id,
      branch_id: pb.branch_id || (pb.room_id.includes("BT") ? "BT" : pb.room_id.includes("TD") ? "TD" : "PMH"),
      booking_date: pb.booking_date,
      khung_code: pb.khung_code,
      start_time: pb.start_time || "09:30",
      end_time: pb.end_time || "12:30",
      guests: parseInt(pb.capacity || 2, 10),
      amount: currentFinalAmount !== null ? currentFinalAmount : pb.amount,
      customer_name: customerName,
      customer_phone: phone,
      customer_email: email,
      note: compiledNote,
      promo_code: currentAppliedPromo ? currentAppliedPromo.code : "",
      discount_amount: currentDiscountAmount || 0,
    };

    const res = await apiFetch("/api/bookings", {
      method: "POST",
      body: payload,
    });

    // Success: Open VietQR MBBank modal
    showToast(`Giữ phòng thành công! Mã đơn: ${res.booking_code}.`, "success");

    // Invoke existing VietQR modal helper from booking.js
    if (typeof openVietQrModal === "function") {
      openVietQrModal(res);
    } else {
      // Fallback if modal function is directly accessible
      const codeEl = document.getElementById("qr-booking-code");
      const amtEl = document.getElementById("qr-amount");
      const imgEl = document.getElementById("qr-image-display");
      const contentEl = document.getElementById("qr-content");
      const modal = document.getElementById("modal-vietqr");
      if (codeEl) codeEl.textContent = res.booking_code;
      if (amtEl) amtEl.textContent = formatCheckoutVnd(res.amount);
      if (imgEl) imgEl.src = res.vietqr_url;
      if (contentEl) contentEl.textContent = res.transfer_content;
      if (modal) modal.style.display = "flex";
    }

  } catch (err) {
    showToast(err.message || "Không thể tạo lượt đặt phòng. Khung giờ này có thể vừa được đặt.", "danger");
  } finally {
    if (btnDesktop) {
      btnDesktop.classList.remove("btn-loading");
      btnDesktop.disabled = false;
    }
    mobileButtons.forEach(b => {
      b.classList.remove("btn-loading");
      b.disabled = false;
    });
  }
}

/**
 * Xử lý kiểm tra và áp dụng mã khuyến mãi
 */
async function handleApplyPromoCode(customCode) {
  const pb = state.pendingBooking;
  if (!pb) return;

  const input = document.getElementById("checkout-promo-input");
  const code = (customCode || input?.value || "").trim().toUpperCase();
  if (!code) {
    showToast("Vui lòng nhập mã ưu đãi hoặc bấm chọn mã gợi ý.", "warning");
    return;
  }

  const btn = document.getElementById("btn-apply-promo");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "...";
  }

  try {
    const res = await apiFetch("/api/promotions/validate", {
      method: "POST",
      body: {
        code: code,
        room_id: pb.room_id,
        booking_date: pb.booking_date,
        khung_code: pb.khung_code,
        amount: pb.amount,
        user_id: state.user ? state.user.id : null,
      }
    });

    if (res && res.valid) {
      currentAppliedPromo = res.promo;
      currentDiscountAmount = res.discount_amount;
      currentFinalAmount = res.final_amount;

      updateCheckoutPromoUI(res);
      showToast(res.message || `Áp dụng thành công mã ${code}!`, "success");
    } else {
      showToast(res?.message || `Mã ${code} không đủ điều kiện áp dụng cho lượt đặt này.`, "warning");
    }
  } catch (err) {
    showToast(err.message || "Lỗi khi kiểm tra mã ưu đãi.", "danger");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "Áp dụng";
    }
  }
}

function quickApplyPromo(code) {
  const input = document.getElementById("checkout-promo-input");
  if (input) input.value = code;
  handleApplyPromoCode(code);
}

function handleRemovePromoCode() {
  currentAppliedPromo = null;
  currentDiscountAmount = 0;
  currentFinalAmount = null;
  window.selectedPendingPromoCode = null;

  const input = document.getElementById("checkout-promo-input");
  if (input) input.value = "";

  const inputGroup = document.getElementById("checkout-promo-input-group");
  const appliedTag = document.getElementById("checkout-promo-applied-tag");
  const discountRow = document.getElementById("checkout-discount-row");
  const totalDisplay = document.getElementById("checkout-total-display");
  const mobileTotalDisplay = document.getElementById("checkout-mobile-total-val");

  if (inputGroup) inputGroup.style.display = "flex";
  if (appliedTag) appliedTag.style.display = "none";
  if (discountRow) discountRow.style.display = "none";

  const pb = state.pendingBooking;
  if (pb && totalDisplay) {
    totalDisplay.textContent = formatCheckoutVnd(pb.amount);
  }
  if (pb && mobileTotalDisplay) {
    mobileTotalDisplay.textContent = formatCheckoutVnd(pb.amount);
  }
  showToast("Đã hủy áp dụng mã ưu đãi.", "info");
}

function updateCheckoutPromoUI(res) {
  const inputGroup = document.getElementById("checkout-promo-input-group");
  const appliedTag = document.getElementById("checkout-promo-applied-tag");
  const appliedText = document.getElementById("checkout-promo-applied-text");
  const discountRow = document.getElementById("checkout-discount-row");
  const discountLabel = document.getElementById("checkout-discount-label");
  const discountVal = document.getElementById("checkout-discount-val");
  const totalDisplay = document.getElementById("checkout-total-display");
  const mobileTotalDisplay = document.getElementById("checkout-mobile-total-val");

  if (inputGroup) inputGroup.style.display = "none";
  if (appliedTag) appliedTag.style.display = "flex";
  if (appliedText) {
    appliedText.innerHTML = `Mã <b>${res.promo?.code}</b>: <b>-${formatCheckoutVnd(res.discount_amount)}</b>`;
  }

  if (discountRow) discountRow.style.display = "flex";
  if (discountLabel) discountLabel.textContent = `Ưu đãi (${res.promo?.code})`;
  if (discountVal) discountVal.textContent = `-${formatCheckoutVnd(res.discount_amount)}`;

  if (totalDisplay) totalDisplay.textContent = formatCheckoutVnd(res.final_amount);
  if (mobileTotalDisplay) mobileTotalDisplay.textContent = formatCheckoutVnd(res.final_amount);
}

/**
 * Initialize page event listeners
 */
function initCheckoutEvents() {
  // Ensure same guest checkbox is bound
  const chk = document.getElementById("chk-same-guest");
  if (chk) {
    chk.addEventListener("change", handleGuestSyncToggle);
  }

  // Tự động kiểm tra nếu có mã ưu đãi đang chờ
  if (window.selectedPendingPromoCode) {
    quickApplyPromo(window.selectedPendingPromoCode);
  }
}

/**
 * Open Policy and Terms Modal
 */
function openCheckoutPolicyModal(type) {
  const modal = document.getElementById("modal-checkout-policy");
  const title = document.getElementById("policy-modal-title");
  const content = document.getElementById("policy-modal-body");

  if (!modal || !title || !content) return;

  if (type === "terms") {
    title.textContent = "Điều Khoản Sử Dụng CozyHome";
    content.innerHTML = `
      <div style="font-size:13.5px; line-height:1.7; color:var(--text-main);">
        <p><b>1. Quy định nhận và trả phòng:</b></p>
        <p>Khách hàng cần tuân thủ thời gian nhận phòng và trả phòng theo đúng khung giờ đã đặt. Trường hợp quá giờ chưa check-out, hệ thống sẽ tự động kích hoạt cảnh báo vận hành.</p>
        <p><b>2. Giữ phòng trong 10 phút:</b></p>
        <p>Sau khi bấm Xác nhận, đơn đặt sẽ được giữ tạm thời trong 10 phút để bạn thực hiện thanh toán qua VietQR MBBank. Sau 10 phút nếu chưa thanh toán, hệ thống sẽ tự động giải phóng phòng cho khách hàng khác.</p>
        <p><b>3. Giấy tờ tùy thân:</b></p>
        <p>Khách lưu trú bắt buộc xuất trình CCCD/CMND hoặc Hộ chiếu bản gốc còn hạn khi làm thủ tục nhận phòng theo quy định pháp luật Việt Nam.</p>
      </div>
    `;
  } else {
    title.textContent = "Chính Sách Đặt Phòng và Hủy Phòng";
    content.innerHTML = `
      <div style="font-size:13.5px; line-height:1.7; color:var(--text-main);">
        <div style="background:#e8f5e9; border:1px solid #c8e6c9; border-radius:10px; padding:12px 14px; margin-bottom:12px; color:#2e7d32;">
          <b>Hủy trước ≥ 24 giờ:</b> Hoàn lại <b>100%</b> số tiền đã thanh toán.
        </div>
        <div style="background:#fff3e0; border:1px solid #ffe0b2; border-radius:10px; padding:12px 14px; margin-bottom:12px; color:#e65100;">
          <b>Hủy từ 12 giờ đến dưới 24 giờ:</b> Hoàn lại <b>50%</b> tiền phòng.
        </div>
        <div style="background:#fef2f2; border:1px solid #fecaca; border-radius:10px; padding:12px 14px; margin-bottom:14px; color:#b91c1c;">
          <b>Hủy dưới 12 giờ hoặc vắng mặt:</b> Không áp dụng hoàn tiền theo quy định điều phối buồng phòng.
        </div>
        <p><b>Quy trình hoàn tiền:</b> Khoản hoàn trả sẽ được bộ phận Kế toán đối soát và chuyển khoản về tài khoản ban đầu trong vòng <b>3 đến 15 ngày làm việc</b>.</p>
        <p><b>Chính sách giá minh bạch:</b> Giá niêm yết đã bao gồm toàn bộ thuế, tiện ích và không phát sinh bất kỳ khoản phụ phí dịch vụ ẩn nào.</p>
      </div>
    `;
  }

  modal.style.display = "flex";
  modal.classList.add("active");
}

/**
 * Close Policy Modal
 */
function closeCheckoutPolicyModal() {
  const modal = document.getElementById("modal-checkout-policy");
  if (modal) {
    modal.classList.remove("active");
    modal.style.display = "none";
  }
}
