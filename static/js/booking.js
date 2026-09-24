// -------------------------------------------------------------
// CozyHome Booking Lifecycle — Thanh toán, Hủy hoàn tiền, Gia hạn
// BR-04 (10 phút giữ chỗ), BR-05 (hủy hoàn tiền), BR-06 (gia hạn)
// -------------------------------------------------------------

// ============================================================
// 1. TẠO ĐẶT PHÒNG
// ============================================================

function initiateBooking(roomId, bookingDate, slotCode, price, startTime, endTime) {
  // Đồng bộ lại state.user từ localStorage nếu trong memory chưa có
  if (!state.user) {
    const stored = localStorage.getItem("cozy_user");
    if (stored) {
      try { state.user = JSON.parse(stored); } catch (e) {}
    }
  }

  // Bắt buộc đăng nhập trước khi đặt phòng
  if (!state.user) {
    state.pendingRoomToBook = { roomId, bookingDate, slotCode, price, startTime, endTime };
    showToast("Vui lòng đăng nhập trước khi tiến hành đặt phòng.", "warning");
    navigateTo("auth");
    return;
  }

  const room = (state.rooms || []).find(r => r.room_id === roomId) || {
    room_id: roomId,
    room_name: roomId,
    branch_id: "BT",
    branch_name: "CozyHome",
  };

  const branchId = room.branch_id || (roomId.includes("BT") ? "BT" : roomId.includes("TD") ? "TD" : "PMH");
  const branchName = room.branch_name || (branchId === "BT" ? "CozyHome Bến Thành" : branchId === "TD" ? "CozyHome Thảo Điền" : "CozyHome Phú Mỹ Hưng");

  // Lưu snapshot đầy đủ dữ liệu phòng (ảnh, sức chứa, tiện nghi...) để trang
  // Xác nhận đặt phòng dùng, không phụ thuộc state.rooms còn giữ hay không.
  state.pendingBooking = {
    room_id: roomId,
    room_name: room.room_name,
    room_type: room.room_type,
    branch_id: branchId,
    branch_name: branchName,
    booking_date: bookingDate,
    khung_code: slotCode,
    start_time: startTime,
    end_time: endTime,
    amount: price,
    capacity: room.capacity,
    concept_name: room.concept_name,
    amenities: room.amenities,
    images: room.images,
  };

  closeRoomDetail();
  navigateTo("checkout");
}

// ============================================================
// 2. THANH TOÁN VietQR (BR-04)
// ============================================================

function openVietQrModal(bkData, isExtension = false) {
  const modal = document.getElementById("modal-vietqr");
  if (!modal) return;

  document.getElementById("qr-booking-code").textContent = bkData.booking_code;
  document.getElementById("qr-amount").textContent = formatMoney(bkData.amount);
  document.getElementById("qr-bank-name").textContent = bkData.bank_name || "MBBank (Quân Đội)";
  document.getElementById("qr-account-no").textContent = bkData.account_no || "0909000001";
  document.getElementById("qr-account-name").textContent = bkData.account_name || "COZYHOME VIETNAM";
  document.getElementById("qr-content").textContent = bkData.transfer_content || bkData.booking_code;

  const qrImg = document.getElementById("qr-image-display");
  if (qrImg) qrImg.src = bkData.vietqr_url;

  // Tiêu đề modal thay đổi tùy loại thanh toán
  const qrTitle = document.getElementById("qr-modal-title");
  if (qrTitle) {
    qrTitle.textContent = isExtension
      ? "Thanh toán phí gia hạn — VietQR MBBank"
      : "Thanh toán đặt phòng — VietQR MBBank";
  }

  // Label countdown chỉ hiện khi đặt phòng mới (không phải gia hạn)
  const countdownWrap = document.getElementById("qr-countdown-wrap");
  if (countdownWrap) {
    countdownWrap.style.display = isExtension ? "none" : "block";
  }

  // Hiển thị giờ check-out sau gia hạn nếu là giao dịch gia hạn
  const extBox = document.getElementById("qr-extension-box");
  const extCheckoutEl = document.getElementById("qr-extension-checkout-time");
  if (extBox) {
    if (isExtension && bkData._extPayload?.newEndTime) {
      extBox.style.display = "block";
      if (extCheckoutEl) {
        extCheckoutEl.textContent = `${bkData._extPayload.newEndTime} (+${bkData._extPayload.hours || 1} tiếng)`;
      }
    } else {
      extBox.style.display = "none";
    }
  }

  // Thiết lập nút xác nhận
  const payBtn = document.getElementById("btn-qr-confirm-paid");
  if (payBtn) {
    payBtn.onclick = () => isExtension
      ? handleConfirmExtensionPaid(bkData.booking_code, bkData._extPayload)
      : handleConfirmPaid(bkData.booking_code);
  }

  // Khởi động đồng hồ đếm ngược 10 phút chỉ khi đặt phòng mới
  if (!isExtension) {
    startHoldCountdown(10 * 60, bkData.booking_code);
  }

  modal.classList.add("active");
}

function closeVietQrModal() {
  if (state.bookingTimerInterval) {
    clearInterval(state.bookingTimerInterval);
    state.bookingTimerInterval = null;
  }
  const modal = document.getElementById("modal-vietqr");
  if (modal) modal.classList.remove("active");
}

function copyQrField(text, label) {
  if (!text) return;
  const cleanText = text.trim();
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(cleanText).then(() => {
      if (typeof showToast === "function") {
        showToast(`Đã sao chép ${label || 'thông tin'}!`, "success");
      }
    }).catch(() => fallbackCopyText(cleanText, label));
  } else {
    fallbackCopyText(cleanText, label);
  }
}

function fallbackCopyText(text, label) {
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.style.position = "fixed";
  ta.style.left = "-9999px";
  document.body.appendChild(ta);
  ta.select();
  try {
    document.execCommand("copy");
    if (typeof showToast === "function") {
      showToast(`Đã sao chép ${label || 'thông tin'}!`, "success");
    }
  } catch (e) {
    if (typeof showToast === "function") {
      showToast(`Không thể tự động sao chép`, "warning");
    }
  }
  document.body.removeChild(ta);
}

function downloadQrCode() {
  const qrImg = document.getElementById("qr-image-display");
  if (!qrImg || !qrImg.src) {
    if (typeof showToast === "function") {
      showToast("Chưa có mã QR để tải về.", "warning");
    }
    return;
  }
  const bkCode = document.getElementById("qr-booking-code")?.textContent || "COZYHOME";
  const link = document.createElement("a");
  link.href = qrImg.src;
  link.download = `VietQR_${bkCode}.png`;
  link.target = "_blank";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  if (typeof showToast === "function") {
    showToast("Đang mở / tải ảnh mã VietQR...", "info");
  }
}

function startHoldCountdown(durationSeconds, bookingCode) {
  if (state.bookingTimerInterval) clearInterval(state.bookingTimerInterval);

  let remaining = durationSeconds;
  const timerEl = document.getElementById("qr-countdown-timer");
  let warnedAt2min = false;

  const updateDisplay = () => {
    const m = Math.floor(remaining / 60);
    const s = remaining % 60;
    if (timerEl) {
      timerEl.textContent = `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
      // Đổi màu đỏ khi còn dưới 2 phút
      timerEl.style.color = remaining <= 120 ? "var(--danger)" : "";
    }
  };

  updateDisplay();
  state.bookingTimerInterval = setInterval(() => {
    remaining--;

    // Cảnh báo khi còn 2 phút
    if (remaining === 120 && !warnedAt2min) {
      warnedAt2min = true;
      showToast("Còn 2 phút để hoàn tất thanh toán! Phòng sẽ được mở lại sau đó.", "warning");
    }

    if (remaining <= 0) {
      clearInterval(state.bookingTimerInterval);
      state.bookingTimerInterval = null;
      showToast("Đã hết thời hạn giữ chỗ 10 phút. Phòng đã mở lại cho khách khác.", "warning");
      closeVietQrModal();
      loadUserBookings();
    } else {
      updateDisplay();
    }
  }, 1000);
}

async function handleConfirmPaid(bookingCode) {
  const payBtn = document.getElementById("btn-qr-confirm-paid");
  if (payBtn) payBtn.classList.add("btn-loading");

  try {
    const res = await apiFetch(`/api/bookings/${bookingCode}/pay`, { method: "POST" });
    closeVietQrModal();
    showToast("Thanh toán thành công! Lượt đặt phòng đã xác nhận. Hẹn gặp bạn tại CozyHome!", "success");
    loadUserBookings();
    navigateTo("bookings");
  } catch (err) {
  } finally {
    if (payBtn) payBtn.classList.remove("btn-loading");
  }
}

function resumePayment(bookingCode, amount) {
  const vietqrUrl = `https://img.vietqr.io/image/MB-0909000001-compact2.png?amount=${amount}&addInfo=${bookingCode}&accountName=COZYHOME%20VIETNAM`;
  openVietQrModal({
    booking_code: bookingCode,
    amount: amount,
    vietqr_url: vietqrUrl,
    bank_name: "MBBank (Quân Đội)",
    account_no: "0909000001",
    account_name: "COZYHOME VIETNAM",
    transfer_content: bookingCode,
  });
}

// ============================================================
// 3. HỦY PHÒNG VÀ HOÀN TIỀN (BR-05)
// ============================================================

async function cancelBookingPrompt(bookingCode, amount, isPaid) {
  const el = (id) => document.getElementById(id);
  if (el("cancel-booking-code")) el("cancel-booking-code").textContent = bookingCode;
  if (el("cancel-reason")) el("cancel-reason").value = "";

  // Trạng thái chờ tải báo giá hoàn tiền
  if (el("cancel-refund-amount")) {
    el("cancel-refund-amount").textContent = isPaid ? "Đang tính toán..." : "0 ₫ (Chưa thanh toán)";
    el("cancel-refund-amount").style.color = "var(--text-muted)";
  }
  if (el("cancel-refund-notice")) {
    el("cancel-refund-notice").style.display = "block";
    el("cancel-refund-notice").innerHTML = isPaid 
      ? "Đang đối soát quy định hủy phòng theo mốc giờ..." 
      : "Lượt đặt chưa thanh toán nên không phát sinh giao dịch hoàn tiền.";
  }

  const modal = el("modal-cancel-booking");
  if (modal) modal.classList.add("active");

  let computedRefund = 0;
  if (isPaid) {
    try {
      const quote = await apiFetch(`/api/bookings/${bookingCode}/cancellation-quote`);
      computedRefund = quote.refund_amount || 0;
      if (el("cancel-refund-amount")) {
        const rateStr = quote.refund_rate || (quote.refund_percent !== undefined ? `${quote.refund_percent}%` : "0%");
        el("cancel-refund-amount").textContent = `${formatMoney(computedRefund)} (${rateStr})`;
        el("cancel-refund-amount").style.color = computedRefund > 0 ? "var(--success)" : "#b91c1c";
      }
      if (el("cancel-refund-notice")) {
        const descStr = quote.description || quote.rule_description || "";
        const timelineStr = quote.time_estimate || quote.processing_timeline || "Từ 3 đến 15 ngày làm việc";
        el("cancel-refund-notice").innerHTML = `
          <b>Chính sách áp dụng:</b> ${descStr}<br>
          <b>Thời gian xử lý hoàn tiền:</b> ${timelineStr}.
        `;
      }
    } catch (e) {
      console.warn("Could not fetch quote, using default:", e);
      computedRefund = amount;
      if (el("cancel-refund-amount")) {
        el("cancel-refund-amount").textContent = formatMoney(amount);
        el("cancel-refund-amount").style.color = "var(--success)";
      }
    }
  }

  // Thiết lập nút xác nhận
  const confirmBtn = el("btn-confirm-cancel");
  if (confirmBtn) {
    confirmBtn.onclick = () => submitCancelBooking(bookingCode, computedRefund);
  }
}

function closeCancelBookingModal() {
  const modal = document.getElementById("modal-cancel-booking");
  if (modal) modal.classList.remove("active");
}

async function submitCancelBooking(bookingCode, expectedRefund) {
  const btn = document.getElementById("btn-confirm-cancel");
  if (btn) btn.classList.add("btn-loading");

  try {
    const res = await apiFetch(`/api/bookings/${bookingCode}/cancel`, { method: "POST" });
    closeCancelBookingModal();

    if (res.refund_amount > 0) {
      showCancelSuccessModal(bookingCode, res.refund_amount);
    } else {
      showToast(res.message || `Đã hủy lượt đặt ${bookingCode} thành công.`, "info");
      loadUserBookings();
    }
  } catch (err) {
    showToast(err.message || "Không thể hủy lượt đặt.", "error");
  } finally {
    if (btn) btn.classList.remove("btn-loading");
  }
}

function showCancelSuccessModal(bookingCode, refundAmount) {
  const el = (id) => document.getElementById(id);
  if (el("cancel-success-code")) el("cancel-success-code").textContent = bookingCode;
  if (el("cancel-success-refund")) el("cancel-success-refund").textContent = formatMoney(refundAmount);

  const modal = el("modal-cancel-success");
  if (modal) modal.classList.add("active");
}

function closeCancelSuccessModal() {
  const modal = document.getElementById("modal-cancel-success");
  if (modal) modal.classList.remove("active");
  loadUserBookings();
}

// ============================================================
// ============================================================
// 4. GIA HẠN THÊM GIỜ (BR-06 & Nghiệp vụ gia hạn theo giờ) — với thanh toán VietQR
// ============================================================

let currentExtensionInfo = null;
let selectedExtensionHours = 1;

async function openExtensionModal(bookingCode) {
  try {
    const info = await apiFetch(`/api/bookings/${bookingCode}/check-extension?hours=1`);
    if (!info) {
      showToast("Không thể tải thông tin gia hạn.", "error");
      return;
    }

    // Kiểm tra tính khả dụng & lý do từ chối nếu có
    if (!info.can_extend && info.current_status && ["Đã hủy", "Hết hạn giữ chỗ", "Chờ thanh toán", "Đã hoàn tất"].includes(info.current_status)) {
      showToast(info.reason || "Lượt đặt phòng không đủ điều kiện để gia hạn.", "warning");
      return;
    }

    currentExtensionInfo = info;
    selectedExtensionHours = 1;

    const modal = document.getElementById("modal-extension");
    if (!modal) return;

    document.getElementById("ext-booking-code").textContent = bookingCode;
    document.getElementById("ext-room-id").textContent = info.room_id || "";
    document.getElementById("ext-next-date").textContent = info.next_date || "";
    document.getElementById("ext-current-checkout").textContent = info.current_end_time || info.start_time || "...";
    
    const slotLabel = info.next_khung_name || info.next_khung || "Khung kế tiếp";
    const nextStart = info.start_time || "";
    const nextEnd = info.next_slot_end || "";
    document.getElementById("ext-next-slot").textContent = `${slotLabel}: ${nextStart} – ${nextEnd}`;

    // Cập nhật phụ đề trên 3 nút chọn giờ để khách hàng thấy ngay giờ check-out tương ứng
    const opt1 = (info.hourly_options || []).find(o => o.hours === 1);
    const opt2 = (info.hourly_options || []).find(o => o.hours === 2);
    const opt3 = (info.hourly_options || []).find(o => o.hours === 3);

    const sub1 = document.getElementById("ext-pill-sub-1");
    if (sub1) sub1.textContent = opt1 ? `Đến ${opt1.end_time}` : "+1h lưu trú";

    const sub2 = document.getElementById("ext-pill-sub-2");
    if (sub2) sub2.textContent = opt2 ? `Đến ${opt2.end_time}` : "+2h lưu trú";

    const sub3 = document.getElementById("ext-pill-sub-3");
    if (sub3) sub3.textContent = opt3 ? `Đến ${opt3.end_time}` : "+3h lưu trú";

    selectExtensionHours(1);

    modal.classList.add("active");
  } catch (err) {
    showToast(err.message || "Không thể kiểm tra khả năng gia hạn.", "error");
  }
}

function selectExtensionHours(hours) {
  selectedExtensionHours = Number(hours) || 1;
  if (!currentExtensionInfo) return;

  // Cập nhật trạng thái active cho các nút chọn giờ
  document.querySelectorAll("#ext-hours-selector .btn-hour-pill").forEach(btn => {
    const h = Number(btn.getAttribute("data-hours"));
    if (h === selectedExtensionHours) {
      btn.classList.add("active");
    } else {
      btn.classList.remove("active");
    }
  });

  const opts = currentExtensionInfo.hourly_options || [];
  const currentOpt = opts.find(o => o.hours === selectedExtensionHours) || {
    hours: selectedExtensionHours,
    amount: (currentExtensionInfo.hourly_rate || 50000) * selectedExtensionHours,
    end_time: currentExtensionInfo.new_end_time,
    is_available: currentExtensionInfo.is_available,
    reason: currentExtensionInfo.reason,
  };

  // Cập nhật giờ check-out sau gia hạn ở cả phần tóm tắt đầu modal và khung chi tiết
  const summaryCheckoutEl = document.getElementById("ext-summary-checkout");
  if (summaryCheckoutEl) {
    summaryCheckoutEl.textContent = `${currentOpt.end_time} (+${selectedExtensionHours} tiếng)`;
  }

  const newCheckoutEl = document.getElementById("ext-new-checkout");
  if (newCheckoutEl) {
    newCheckoutEl.textContent = `${currentOpt.end_time} (Gia hạn +${selectedExtensionHours} tiếng)`;
  }

  const amountEl = document.getElementById("ext-amount");
  if (amountEl) {
    amountEl.textContent = formatMoney(currentOpt.amount);
  }

  const statusAlertEl = document.getElementById("ext-status-alert");
  const confirmBtn = document.getElementById("btn-confirm-extension");

  if (currentOpt.is_available) {
    if (statusAlertEl) {
      statusAlertEl.innerHTML = `
        <div style="background:#ecfdf5; border:1px solid #a7f3d0; color:#065f46; padding:8px 12px; border-radius:8px; font-size:12.5px; display:flex; align-items:center; gap:8px;">
          <span style="font-size:15px; font-weight:700;">✓</span>
          <div>Khung tiếp theo <b>${currentExtensionInfo.next_khung_name}</b> đang trống. Hệ thống sẽ tự động khóa khung này cho bạn. Giờ trả phòng mới: <b>${currentOpt.end_time}</b>.</div>
        </div>
      `;
    }
    if (confirmBtn) {
      confirmBtn.disabled = false;
      confirmBtn.classList.remove("disabled");
      confirmBtn.style.opacity = "1";
      confirmBtn.style.cursor = "pointer";
      confirmBtn.innerHTML = `Xác nhận gia hạn • Trả phòng lúc ${currentOpt.end_time} • ${formatMoney(currentOpt.amount)}`;
      confirmBtn.onclick = () => submitExtension(currentExtensionInfo.booking_code, selectedExtensionHours, currentOpt);
    }
  } else {
    if (statusAlertEl) {
      statusAlertEl.innerHTML = `
        <div style="background:#fef2f2; border:1px solid #fecaca; color:#991b1b; padding:8px 12px; border-radius:8px; font-size:12.5px; display:flex; align-items:center; gap:8px;">
          <span style="font-size:15px; font-weight:700;">⚠️</span>
          <div>${currentOpt.reason || "Khung kế tiếp đã có người đặt trước hoặc không khả dụng. Không thể gia hạn."}</div>
        </div>
      `;
    }
    if (confirmBtn) {
      confirmBtn.disabled = true;
      confirmBtn.classList.add("disabled");
      confirmBtn.style.opacity = "0.6";
      confirmBtn.style.cursor = "not-allowed";
      confirmBtn.innerHTML = `Không thể gia hạn (Khung kế tiếp đã kín)`;
      confirmBtn.onclick = null;
    }
  }
}

function closeExtensionModal() {
  const modal = document.getElementById("modal-extension");
  if (modal) modal.classList.remove("active");
}

async function submitExtension(bookingCode, hours, opt) {
  const btn = document.getElementById("btn-confirm-extension");
  if (btn) btn.classList.add("btn-loading");

  try {
    const payload = {
      booking_code: bookingCode,
      room_id: currentExtensionInfo.room_id,
      extension_date: currentExtensionInfo.next_date,
      khung_code: currentExtensionInfo.next_khung,
      start_time: currentExtensionInfo.current_end_time || currentExtensionInfo.start_time,
      end_time: opt.end_time,
      amount: opt.amount,
      hours: hours,
    };

    const res = await apiFetch("/api/bookings/extend", { method: "POST", body: payload });

    closeExtensionModal();

    // Hiện VietQR để thanh toán phí gia hạn
    const extAmount = opt.amount;
    const vietqrUrl = `https://img.vietqr.io/image/MB-0909000001-compact2.png?amount=${extAmount}&addInfo=${bookingCode}-GH&accountName=COZYHOME%20VIETNAM`;
    openVietQrModal({
      booking_code: `${bookingCode} (Gia hạn +${hours}h)`,
      amount: extAmount,
      vietqr_url: vietqrUrl,
      bank_name: "MBBank (Quân Đội)",
      account_no: "0909000001",
      account_name: "COZYHOME VIETNAM",
      transfer_content: `${bookingCode}-GH`,
      _extPayload: { newEndTime: opt.end_time, hours: hours },
    }, true); // isExtension = true

    showToast(`Đã ghi nhận gia hạn ${hours} tiếng! Giờ check-out mới: ${opt.end_time}. Vui lòng thanh toán phí gia hạn.`, "success");

  } catch (err) {
    showToast(err.message || "Không thể thực hiện gia hạn.", "error");
  } finally {
    if (btn) btn.classList.remove("btn-loading");
  }
}

async function handleConfirmExtensionPaid(bookingCode, extPayload) {
  const payBtn = document.getElementById("btn-qr-confirm-paid");
  if (payBtn) payBtn.classList.add("btn-loading");

  try {
    // Backend đã ghi extension — chỉ cần đóng modal và reload
    closeVietQrModal();
    const newEnd = extPayload?.newEndTime || "";
    showToast(`Đã xác nhận thanh toán phí gia hạn${newEnd ? ". Giờ check-out mới: " + newEnd : ""}!`, "success");
    loadUserBookings();
    navigateTo("bookings");
  } catch (err) {
  } finally {
    if (payBtn) payBtn.classList.remove("btn-loading");
  }
}

// ============================================================
// 5. DANH SÁCH LƯỢT ĐẶT — CARD VIEW
// ============================================================

let bookingsCurrentTab = "all";

async function loadUserBookings() {
  if (!state.user) { navigateTo("auth"); return; }

  const container = document.getElementById("user-bookings-list");
  if (container) {
    container.innerHTML = `
      <div style="text-align:center; padding:40px;">
        <div style="display:inline-block; width:28px; height:28px; border:3px solid var(--cozy-primary); border-right-color:transparent; border-radius:50%; animation:btnSpinner 0.65s linear infinite;"></div>
        <p style="margin-top:10px; color:var(--text-muted); font-size:13.5px;">Đang tải danh sách lượt đặt...</p>
      </div>
    `;
  }

  try {
    const res = await apiFetch(`/api/bookings?user_id=${state.user.id}`);
    state.myBookings = res.bookings || [];
    bookingsCurrentTab = "all";
    document.querySelectorAll(".bk-tab").forEach(t => t.classList.toggle("active", t.getAttribute("data-bktab") === "all"));
    const searchInput = document.getElementById("bk-search-input");
    if (searchInput) searchInput.value = "";
    renderFilteredUserBookings();
  } catch (err) {
    state.myBookings = [];
    if (container) {
      container.innerHTML = `<div style="color:var(--danger); text-align:center; padding:30px;">Không thể tải lịch sử lượt đặt.</div>`;
    }
  }
}

function setBookingsTab(tab) {
  bookingsCurrentTab = tab;
  document.querySelectorAll(".bk-tab").forEach(t => t.classList.toggle("active", t.getAttribute("data-bktab") === tab));
  renderFilteredUserBookings();
}

// Ánh xạ khoá tab (ASCII, an toàn cho id/DOM) sang các trạng thái booking tương ứng
const BK_TAB_STATUS_MAP = {
  pending: ["Chờ thanh toán"],
  confirmed: ["Đã xác nhận"],
  staying: ["Đã check-in", "Quá giờ - chưa checkout"],
  done: ["Đã hoàn tất"],
  cancelled: ["Đã hủy", "Hết hạn giữ chỗ"],
};

function renderFilteredUserBookings() {
  const container = document.getElementById("user-bookings-list");
  if (!container) return;

  const all = state.myBookings || [];
  const q = (document.getElementById("bk-search-input")?.value || "").trim().toLowerCase();

  // Cập nhật số đếm trên từng tab
  const countAll = document.getElementById("bk-tab-count-all");
  if (countAll) countAll.textContent = all.length;
  Object.keys(BK_TAB_STATUS_MAP).forEach(key => {
    const statuses = BK_TAB_STATUS_MAP[key];
    const el = document.getElementById(`bk-tab-count-${key}`);
    if (el) el.textContent = all.filter(b => statuses.includes(b.status)).length;
  });

  let filtered = all;
  if (bookingsCurrentTab !== "all") {
    const statuses = BK_TAB_STATUS_MAP[bookingsCurrentTab] || [];
    filtered = filtered.filter(b => statuses.includes(b.status));
  }
  if (q) {
    const normQ = removeVietnameseTones(q);
    filtered = filtered.filter(b =>
      removeVietnameseTones(b.booking_code || "").includes(normQ) ||
      removeVietnameseTones(b.room_id || "").includes(normQ) ||
      removeVietnameseTones(b.room_name || "").includes(normQ)
    );
  }

  const sort = document.getElementById("bk-sort-select")?.value || "date_desc";
  if (sort === "name_asc") {
    filtered.sort((a, b) => removeVietnameseTones(a.room_name || a.room_id).localeCompare(removeVietnameseTones(b.room_name || b.room_id)));
  } else if (sort === "code_asc") {
    filtered.sort((a, b) => (a.booking_code || "").localeCompare(b.booking_code || ""));
  } else {
    filtered.sort((a, b) => (b.booking_date || "").localeCompare(a.booking_date || "") || (b.id || 0) - (a.id || 0));
  }

  if (all.length === 0) {
    container.innerHTML = `
      <div class="room-empty-state">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>
        <h3>Bạn chưa có lượt đặt phòng nào</h3>
        <p>Hãy khám phá các căn phòng ấm cúng và chọn khung giờ phù hợp cho kỳ nghỉ nhé!</p>
        <button class="btn btn-primary" onclick="navigateTo('home')">Khám phá phòng ngay</button>
      </div>
    `;
    return;
  }

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="room-empty-state">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
        <h3>Không có lượt đặt nào khớp</h3>
        <p>Thử điều chỉnh lại bộ lọc trạng thái ở trên.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = `
    <div style="display:flex; flex-direction:column; gap:14px;">
      ${filtered.map(b => renderBookingCard(b)).join("")}
    </div>
  `;
}

// Màu và cấu hình cho từng trạng thái
const STATUS_CONFIG = {
  "Chờ thanh toán":         { bg: "#fffbeb", color: "#b45309", border: "#fde68a", dot: "#f59e0b" },
  "Đã xác nhận":            { bg: "#ecfdf5", color: "#065f46", border: "#a7f3d0", dot: "#10b981" },
  "Chờ check-in":           { bg: "#ecfdf5", color: "#065f46", border: "#a7f3d0", dot: "#10b981" },
  "Đã check-in":            { bg: "#eff6ff", color: "#1e40af", border: "#bfdbfe", dot: "#3b82f6" },
  "Quá giờ - chưa checkout":{ bg: "#fef2f2", color: "#991b1b", border: "#fecaca", dot: "#ef4444" },
  "Đã hoàn tất":            { bg: "#f8fafc", color: "#475569", border: "#e2e8f0", dot: "#64748b" },
  "Đã hủy":                 { bg: "#f1f5f9", color: "#64748b", border: "#cbd5e1", dot: "#94a3b8" },
  "Hết hạn giữ chỗ":        { bg: "#f1f5f9", color: "#64748b", border: "#cbd5e1", dot: "#94a3b8" },
};

const SLOT_LABELS = {
  K1: "09:30 – 12:30 (Sáng)",
  K2: "13:00 – 16:00 (Chiều)",
  K3: "16:30 – 19:30 (Tối)",
  QD: "20:00 – 08:30 (Qua đêm)",
  K4: "20:00 – 08:30 (Qua đêm)"
};

const BRANCH_NAME_SHORT = { BT: "Bến Thành", TD: "Thảo Điền", PMH: "Phú Mỹ Hưng" };

function buildBookingStepper(status, isPaid) {
  if (status === "Đã hủy" || status === "Hết hạn giữ chỗ") {
    return "";
  }

  // 4 bước: 1. Đặt chỗ -> 2. Thanh toán -> 3. Nhận phòng -> 4. Trả phòng
  let s1Class = "completed";
  let c1Class = "completed";
  let s2Class = "pending";
  let c2Class = "pending";
  let s3Class = "pending";
  let c3Class = "pending";
  let s4Class = "pending";

  let stageHint = "";
  let hintIcon = "✓";
  let hintColor = "#15803d";

  if (status === "Chờ thanh toán") {
    s2Class = "active";
    c1Class = "in-progress";
    stageHint = "Đang giữ chỗ tạm thời (tối đa 10 phút) — Vui lòng thanh toán để xác nhận giữ phòng.";
    hintIcon = "⏳";
    hintColor = "#b45309";
  } else if (status === "Đã xác nhận" || status === "Chờ check-in") {
    s2Class = "completed";
    c1Class = "completed";
    s3Class = "active";
    c2Class = "in-progress";
    stageHint = "Đã xác nhận & thanh toán thành công — Chờ đến ngày nhận phòng tại CozyHome.";
    hintIcon = "🔑";
    hintColor = "#047857";
  } else if (status === "Đã check-in") {
    s2Class = "completed";
    c1Class = "completed";
    s3Class = "completed";
    c2Class = "completed";
    s4Class = "active";
    c3Class = "in-progress";
    stageHint = "Khách đang lưu trú tại CozyHome — Chúc bạn kỳ nghỉ tuyệt vời!";
    hintIcon = "🏡";
    hintColor = "#1e40af";
  } else if (status === "Quá giờ - chưa checkout") {
    s2Class = "completed";
    c1Class = "completed";
    s3Class = "completed";
    c2Class = "completed";
    s4Class = "alert";
    c3Class = "alert";
    stageHint = "Đã quá giờ trả phòng quy định — Vui lòng làm thủ tục check-out hoặc gia hạn thêm giờ.";
    hintIcon = "⚠️";
    hintColor = "#dc2626";
  } else if (status === "Đã hoàn tất") {
    s2Class = "completed";
    c1Class = "completed";
    s3Class = "completed";
    c2Class = "completed";
    s4Class = "completed";
    c3Class = "completed";
    stageHint = "Đã hoàn tất lưu trú và trả phòng. Cảm ơn bạn đã lựa chọn CozyHome!";
    hintIcon = "🎉";
    hintColor = "#475569";
  }

  const checkIcon = `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.5"><polyline points="20 6 9 17 4 12"/></svg>`;

  return `
    <div class="bk-stepper-wrap">
      <div class="bk-stepper">
        <div class="bk-step-item ${s1Class}">
          <div class="bk-step-node">${checkIcon}</div>
          <span class="bk-step-label">Đặt chỗ</span>
        </div>
        <div class="bk-step-connector ${c1Class}"></div>

        <div class="bk-step-item ${s2Class}">
          <div class="bk-step-node">${s2Class === "completed" ? checkIcon : "2"}</div>
          <span class="bk-step-label">Thanh toán</span>
        </div>
        <div class="bk-step-connector ${c2Class}"></div>

        <div class="bk-step-item ${s3Class}">
          <div class="bk-step-node">${s3Class === "completed" ? checkIcon : "3"}</div>
          <span class="bk-step-label">Nhận phòng</span>
        </div>
        <div class="bk-step-connector ${c3Class}"></div>

        <div class="bk-step-item ${s4Class}">
          <div class="bk-step-node">${s4Class === "completed" ? checkIcon : "4"}</div>
          <span class="bk-step-label">Trả phòng</span>
        </div>
      </div>

      <div class="bk-stage-hint">
        <span style="font-size:13px;">${hintIcon}</span>
        <span style="color:${hintColor}; font-weight:600;">${stageHint}</span>
      </div>
    </div>
  `;
}

function renderBookingCard(b) {
  const cfg = STATUS_CONFIG[b.status] || { bg: "#f1f5f9", color: "#475569", border: "#cbd5e1", dot: "#94a3b8" };
  const isPaid = b.payment_status === "Đã thanh toán";
  const thumbSrc = `/static/images/rooms/${b.branch_id}/${b.room_id}-1.png`;
  const branchShort = BRANCH_NAME_SHORT[b.branch_id] || b.branch_id;

  // Nút hành động tuỳ theo trạng thái
  let actionsHtml = "";

  if (b.status === "Chờ thanh toán") {
    actionsHtml += `
      <button class="bk-action-btn bk-action-primary" onclick="resumePayment('${b.booking_code}', ${b.amount})">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="2" y="5" width="20" height="14" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/></svg>
        Tiếp tục thanh toán
      </button>
      <button class="bk-action-btn bk-action-danger" onclick="cancelBookingPrompt('${b.booking_code}', ${b.amount}, false)">
        Hủy đặt phòng
      </button>
    `;
  }

  if (b.status === "Đã xác nhận") {
    actionsHtml += `
      <button class="bk-action-btn bk-action-primary" onclick="openExtensionModal('${b.booking_code}')">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
        Gia hạn thêm giờ
      </button>
      <button class="bk-action-btn bk-action-danger" onclick="cancelBookingPrompt('${b.booking_code}', ${b.amount}, true)">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        Hủy và hoàn tiền
      </button>
    `;
  }

  if (b.status === "Đã check-in" || b.status === "Quá giờ - chưa checkout") {
    actionsHtml += `
      <button class="bk-action-btn bk-action-primary" onclick="openExtensionModal('${b.booking_code}')">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
        Gia hạn thêm giờ
      </button>
    `;
  }

  if (b.status === "Đã hoàn tất") {
    actionsHtml += `
      <button class="bk-action-btn bk-action-outline" onclick="openReviewModal('${b.booking_code}')">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
        Viết đánh giá
      </button>
    `;
  }

  // Tiến trình 4 bước chuẩn
  const stepperHtml = buildBookingStepper(b.status, isPaid);

  // Thông tin hoàn tiền nếu đã hủy
  let cancelNotice = "";
  if (b.status === "Đã hủy" && isPaid) {
    const rf = b.refund_amount !== undefined && b.refund_amount !== null ? b.refund_amount : b.amount;
    if (rf > 0) {
      cancelNotice = `
        <div class="bk-notice bk-notice-success">
          Khoản hoàn tiền <b>${formatMoney(rf)}</b> đã được chuyển sang danh sách đối soát của Kế toán (dự kiến xử lý 3–15 ngày làm việc).
        </div>
      `;
    } else {
      cancelNotice = `
        <div class="bk-notice" style="background:#fef2f2; border:1px solid #fecaca; color:#991b1b; padding:10px 12px; border-radius:8px; font-size:12.5px; margin-top:10px;">
          Lượt đặt đã hủy. Không hoàn tiền theo quy định hủy phòng sát giờ (dưới 12 tiếng trước giờ check-in).
        </div>
      `;
    }
  }

  const pendingNotice = b.status === "Chờ thanh toán" ? `
    <div class="bk-notice bk-notice-warning">
      Hệ thống giữ chỗ tối đa <b>10 phút</b>. Vui lòng thanh toán ngay để giữ phòng.
    </div>
  ` : "";

  return `
    <div class="bk-card">
      <img src="${thumbSrc}" alt="${b.room_id}" class="bk-thumb" loading="lazy"
           onerror="this.onerror=null; this.src='/static/images/cozyhome-logo.png'; this.style.objectFit='contain'; this.style.padding='16px'; this.style.background='#fcf8f5';" />

      <div class="bk-main">
        <div>
          <div class="bk-main-top">
            <span class="bk-code-tag">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
              ${b.booking_code}
            </span>
            <span class="bk-status-pill" style="background:${cfg.bg}; color:${cfg.color}; border:1px solid ${cfg.border};">
              <span class="bk-status-dot" style="background:${cfg.dot};"></span>
              ${b.status}
            </span>
          </div>

          <div class="bk-room-title">${b.room_id} <span class="bk-room-branch">• CozyHome ${branchShort}</span></div>

          <div class="bk-meta-tags">
            <span class="bk-tag-item">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
              <b>${b.booking_date}</b>
            </span>
            <span class="bk-tag-item">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
              ${SLOT_LABELS[b.khung_code] || (b.start_time && b.end_time ? `${b.start_time} – ${b.end_time}` : b.khung_code)}
            </span>
            ${b.extension_hours > 0 ? `
              <span class="bk-tag-item bk-tag-ext" title="Lượt đặt đã được gia hạn thêm ${b.extension_hours} tiếng. Giờ check-out sau gia hạn: ${b.end_time}">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
                ⏰ Check-out sau gia hạn: <b>${b.end_time}</b> (+${b.extension_hours}h)
              </span>
            ` : ""}
            <span class="bk-tag-item">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
              ${b.customer_name} • ${b.customer_phone} • ${b.guests} khách
            </span>
          </div>
        </div>

        ${stepperHtml}
        ${cancelNotice}
        ${pendingNotice}
      </div>

      <div class="bk-side">
        <div class="bk-amount-box">
          <span class="bk-amount-label">Tổng thanh toán</span>
          <div class="bk-amount">${formatMoney(b.amount)}</div>
          <span class="bk-pay-pill ${isPaid ? "paid" : "unpaid"}">
            ${isPaid ? `
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>
              Đã thanh toán
            ` : `
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
              Chưa thanh toán
            `}
          </span>
        </div>
        ${actionsHtml ? `<div class="bk-card-footer">${actionsHtml}</div>` : ""}
      </div>
    </div>
  `;
}

// ============================================================
// 6. ĐÁNH GIÁ (BR-12)
// ============================================================

let reviewUploadedPhotos = [];

function openReviewModal(bookingCode) {
  const modal = document.getElementById("modal-review");
  if (!modal) return;

  document.getElementById("review-booking-code").textContent = bookingCode;
  document.getElementById("review-content").value = "";
  reviewUploadedPhotos = [];
  renderReviewPhotoPreviews();

  const fileInput = document.getElementById("review-file-input");
  if (fileInput) fileInput.value = "";

  const submitBtn = document.getElementById("btn-submit-review");
  if (submitBtn) { submitBtn.onclick = () => submitReview(bookingCode); }

  modal.classList.add("active");
}

function closeReviewModal() {
  const modal = document.getElementById("modal-review");
  if (modal) modal.classList.remove("active");
}

function renderReviewPhotoPreviews() {
  const grid = document.getElementById("review-photo-preview-grid");
  const countEl = document.getElementById("review-photo-count");
  if (countEl) {
    countEl.textContent = `${reviewUploadedPhotos.length}/5 ảnh`;
  }
  if (!grid) return;

  if (reviewUploadedPhotos.length === 0) {
    grid.innerHTML = "";
    return;
  }

  grid.innerHTML = reviewUploadedPhotos.map((url, idx) => `
    <div class="review-thumb-item">
      <img src="${url}" alt="Ảnh ${idx + 1}" onerror="this.src='/static/images/cozyhome-logo.png'" />
      <button type="button" class="review-thumb-del" onclick="removeReviewPhoto(${idx})" title="Xóa ảnh này">&times;</button>
    </div>
  `).join("");
}

function removeReviewPhoto(index) {
  reviewUploadedPhotos.splice(index, 1);
  renderReviewPhotoPreviews();
}

function addSampleReviewPhoto(url, label) {
  if (reviewUploadedPhotos.length >= 5) {
    showToast("Tối đa 5 hình ảnh cho mỗi đánh giá.", "warning");
    return;
  }
  reviewUploadedPhotos.push(url);
  renderReviewPhotoPreviews();
  showToast(`Đã thêm ảnh: ${label}`, "info");
}

async function handleReviewFileSelect(event) {
  const files = Array.from(event.target.files || []);
  if (files.length === 0) return;

  const remainingSlots = 5 - reviewUploadedPhotos.length;
  if (remainingSlots <= 0) {
    showToast("Bạn đã đạt giới hạn tối đa 5 hình ảnh.", "warning");
    return;
  }

  const filesToUpload = files.slice(0, remainingSlots);

  for (const file of filesToUpload) {
    if (!file.type.startsWith("image/")) {
      showToast(`Tệp ${file.name} không phải là hình ảnh hợp lệ.`, "warning");
      continue;
    }

    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch("/api/reviews/upload", {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      if (res.ok && data.url) {
        reviewUploadedPhotos.push(data.url);
      } else {
        const dataUrl = await readFileAsDataUrl(file);
        reviewUploadedPhotos.push(dataUrl);
      }
    } catch (err) {
      try {
        const dataUrl = await readFileAsDataUrl(file);
        reviewUploadedPhotos.push(dataUrl);
      } catch (e) {
        showToast(`Không thể tải ảnh ${file.name}`, "error");
      }
    }
  }

  renderReviewPhotoPreviews();
  event.target.value = "";
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => resolve(e.target.result);
    reader.onerror = (e) => reject(e);
    reader.readAsDataURL(file);
  });
}

async function submitReview(bookingCode) {
  const rating = parseInt(document.getElementById("review-rating")?.value || "5", 10);
  const content = document.getElementById("review-content")?.value.trim();
  const btn = document.getElementById("btn-submit-review");

  if (!content) { showToast("Vui lòng nhập đôi dòng cảm nhận của bạn.", "error"); return; }

  if (btn) btn.classList.add("btn-loading");
  try {
    const mediaUrlsStr = reviewUploadedPhotos.join(",");
    const payload = {
      booking_code: bookingCode,
      user_id: state.user?.id || 0,
      rating,
      content,
      media_urls: mediaUrlsStr,
    };
    const res = await apiFetch("/api/reviews", { method: "POST", body: payload });
    closeReviewModal();
    showToast(res.message || "Đã gửi đánh giá thành công!", "success");
    loadUserBookings();
  } catch (err) {
  } finally {
    if (btn) btn.classList.remove("btn-loading");
  }
}

