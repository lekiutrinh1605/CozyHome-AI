// -------------------------------------------------------------
// CozyHome Rooms — Traveloka-Style Search & Room Cards
// -------------------------------------------------------------

async function loadMetadata() {
  try {
    const [branches, slots] = await Promise.all([
      apiFetch("/api/branches"),
      apiFetch("/api/slots"),
    ]);
    state.branches = branches;
    state.slots = slots;

    // Populate branch selects (hero search bar)
    const branchSelect = document.getElementById("search-branch");
    if (branchSelect) {
      branchSelect.innerHTML = '<option value="">Tất cả 3 chi nhánh</option>' +
        branches.map(b => `<option value="${b.id}">${b.name}</option>`).join("");
    }

    // Populate slot selects with optgroups
    const slotSelect = document.getElementById("search-slot");
    if (slotSelect && Array.isArray(slots) && slots.length > 0) {
      let optHtml = '<option value="">Tất cả khung giờ (Xem toàn bộ)</option>';
      const shiftIcons = {
        "Buổi sáng": "Buổi sáng (09:30 – 14:00)",
        "Buổi chiều": "Buổi chiều (13:00 – 17:30)",
        "Buổi tối": "Buổi tối (16:30 – 21:00)",
        "Qua đêm": "Qua đêm (20:00 – 10:00)"
      };
      ["Buổi sáng", "Buổi chiều", "Buổi tối", "Qua đêm"].forEach(sh => {
        const sub = slots.filter(s => s.shift === sh);
        if (sub.length > 0) {
          optHtml += `<optgroup label="${shiftIcons[sh] || sh}">`;
          sub.forEach(s => {
            optHtml += `<option value="${s.code}">${s.name}</option>`;
          });
          optHtml += `</optgroup>`;
        }
      });
      slotSelect.innerHTML = optHtml;
    }
  } catch (err) {
    console.error("Lỗi tải metadata:", err);
  }
}

async function performSearch() {
  // Thu thập từ thanh tìm kiếm trên
  const branch = document.getElementById("search-branch")?.value || "";
  const guests = document.getElementById("search-guests")?.value || "2";
  const date = document.getElementById("search-date")?.value || new Date().toISOString().split("T")[0];
  const slot = document.getElementById("search-slot")?.value || "";
  const keyword = document.getElementById("search-keyword")?.value || "";
  const budget = document.getElementById("search-budget")?.value || "";

  // Cập nhật hiển thị nút xóa từ khóa
  const clearBtn = document.getElementById("search-clear-btn");
  if (clearBtn) clearBtn.style.display = keyword.trim() ? "inline-flex" : "none";
  if (keyword.trim()) saveRecentSearch(keyword.trim());

  // Thu thập từ sidebar filters (chỉ các đặc tính phòng)
  const sf = state.sidebarFilters || {};
  const branchesToFilter = branch ? [branch] : [];
  const types = sf.types || [];
  const amenities = sf.amenities || [];
  const areaRange = sf.areaRange || "";
  const bedTypes = sf.bedTypes || [];
  const minPrice = sf.minPrice || budget ? (sf.minPrice || "") : "";
  const maxPrice = sf.maxPrice || budget || "";
  const sortBy = sf.sortBy || "popularity";

  const hasSidebarFilters = Boolean(
    (types && types.length > 0) ||
    (amenities && amenities.length > 0) ||
    (bedTypes && bedTypes.length > 0) ||
    (areaRange && areaRange !== "") ||
    (minPrice && minPrice !== "") ||
    (sf.maxPrice && sf.maxPrice !== "")
  );

  // Cập nhật trạng thái nút [Đặt lại] ở Sidebar Header
  const sidebarResetBtn = document.querySelector(".sidebar-reset-btn");
  if (sidebarResetBtn) {
    if (hasSidebarFilters) {
      sidebarResetBtn.style.opacity = "1";
      sidebarResetBtn.style.pointerEvents = "auto";
      sidebarResetBtn.style.cursor = "pointer";
    } else {
      sidebarResetBtn.style.opacity = "0.4";
      sidebarResetBtn.style.pointerEvents = "none";
      sidebarResetBtn.style.cursor = "default";
    }
  }

  const container = document.getElementById("rooms-list-container");
  const countEl = document.getElementById("rooms-count-display");

  if (container) {
    container.innerHTML = renderRoomListSkeleton();
  }

  // Cập nhật Active Filter Badges ngay khi bắt đầu tìm
  renderActiveFilterBadges({
    branch,
    slot,
    keyword,
    types,
    amenities,
    areaRange,
    bedTypes,
    minPrice,
    maxPrice,
  });

  try {
    const query = new URLSearchParams({
      guests: guests,
      date: date,
      khung_code: slot,
      keyword: keyword,
      sort_by: sortBy,
    });
    if (areaRange) query.set("area_range", areaRange);
    if (bedTypes.length > 0) query.set("bed_types", bedTypes.join(","));

    let allRooms = [];
    let lastFallback = null;

    if (branchesToFilter.length > 0) {
      for (const bid of branchesToFilter) {
        const q = new URLSearchParams(query);
        q.set("branch_id", bid);
        if (types.length > 0) q.set("room_types", types.join(","));
        if (amenities.length > 0) q.set("prefs", amenities.join(","));
        if (maxPrice) q.set("budget_max", maxPrice);
        if (minPrice) q.set("min_price", minPrice);
        const res = await apiFetch(`/api/rooms?${q.toString()}`);
        allRooms = allRooms.concat(res.rooms || []);
        if (res.fallback && !lastFallback) lastFallback = res.fallback;
      }
    } else {
      query.set("branch_id", "");
      if (types.length > 0) query.set("room_types", types.join(","));
      if (amenities.length > 0) query.set("prefs", amenities.join(","));
      if (maxPrice) query.set("budget_max", maxPrice);
      if (minPrice) query.set("min_price", minPrice);
      const res = await apiFetch(`/api/rooms?${query.toString()}`);
      allRooms = res.rooms || [];
      if (res.fallback) lastFallback = res.fallback;
    }

    // Loại bỏ trùng lặp khi fetch nhiều chi nhánh
    const seen = new Set();
    allRooms = allRooms.filter(r => {
      if (seen.has(r.room_id)) return false;
      seen.add(r.room_id);
      return true;
    });

    // Sắp xếp gộp theo sort_by
    if (sortBy === "price_asc") allRooms.sort((a, b) => (a.price || 0) - (b.price || 0));
    else if (sortBy === "price_desc") allRooms.sort((a, b) => (b.price || 0) - (a.price || 0));
    else if (sortBy === "capacity_desc") allRooms.sort((a, b) => (b.capacity || 0) - (a.capacity || 0));
    else if (sortBy === "name_asc") allRooms.sort((a, b) => (a.room_name || "").localeCompare(b.room_name || ""));

    state.rooms = allRooms;

    if (countEl) {
      countEl.textContent = allRooms.length > 0
        ? `${allRooms.length} phòng phù hợp`
        : "Không tìm thấy phòng phù hợp";
    }

    // Cập nhật câu phụ đề kết quả tìm kiếm cho chính xác
    const subEl = document.querySelector(".traveloka-results-sub");
    if (subEl) {
      if (hasSidebarFilters && (keyword.trim() || branch || slot)) {
        subEl.textContent = "Dựa trên tiêu chí tìm kiếm và bộ lọc bạn đã chọn.";
      } else if (hasSidebarFilters) {
        subEl.textContent = "Dựa trên bộ lọc phòng bạn đã chọn.";
      } else {
        subEl.textContent = "Dựa trên tiêu chí tìm kiếm và thời gian bạn đã chọn.";
      }
    }

    // Cập nhật count badge sidebar
    const resultsBadge = document.getElementById("results-count-badge");
    if (resultsBadge) resultsBadge.textContent = `${allRooms.length} phòng tìm thấy`;

    // Hiển thị hoặc ẩn Smart Fallback khi 0 kết quả
    renderSmartFallback(allRooms.length === 0 ? lastFallback : null);

    renderRoomListTraveloka(allRooms, date, slot, {
      hasSidebarFilters,
      keyword: keyword.trim(),
      branch,
      slot,
    });
  } catch (err) {
    if (container) {
      container.innerHTML = `<div style="text-align:center; color:var(--danger); padding:40px;">Không thể tải danh sách phòng. Vui lòng thử lại.</div>`;
    }
  }
}

// Đánh giá số dựa trên amenities (giả lập chưa có dữ liệu review thực)
function getSimulatedRating(room) {
  const amenCount = (room.amenities || []).length;
  const base = room.room_type === "Deluxe" ? 9.0 : room.room_type === "Family" ? 8.8 : 8.3;
  const bonus = Math.min(amenCount * 0.1, 0.6);
  return (base + bonus).toFixed(1);
}

function getRatingLabel(score) {
  if (score >= 9.5) return "Xuất sắc";
  if (score >= 9.0) return "Tuyệt vời";
  if (score >= 8.5) return "Rất tốt";
  if (score >= 8.0) return "Tốt";
  return "Khá";
}

function renderRoomListSkeleton() {
  const card = `
    <div class="room-card-skeleton">
      <div class="rd-skeleton" style="height:100%; border-radius:0;"></div>
      <div style="padding:16px 20px; display:flex; flex-direction:column; gap:10px;">
        <div class="rd-skeleton" style="width:60%; height:18px;"></div>
        <div class="rd-skeleton" style="width:80%; height:13px;"></div>
        <div class="rd-skeleton" style="width:70%; height:13px;"></div>
      </div>
      <div style="padding:16px; display:flex; flex-direction:column; align-items:flex-end; gap:8px;">
        <div class="rd-skeleton" style="width:70px; height:13px;"></div>
        <div class="rd-skeleton" style="width:90px; height:22px;"></div>
        <div class="rd-skeleton" style="width:100%; height:34px; margin-top:8px;"></div>
      </div>
    </div>
  `;
  return `<div class="room-list-skeleton-wrap">${card.repeat(3)}</div>`;
}

function renderRoomListTraveloka(rooms, searchDate, searchSlot, searchContext = {}) {
  const container = document.getElementById("rooms-list-container");
  if (!container) return;

  if (rooms.length === 0) {
    const { hasSidebarFilters = false, keyword = "", branch = "", slot = "" } = searchContext;
    const branchNames = { BT: "CozyHome Bến Thành", TD: "CozyHome Thảo Điền", PMH: "CozyHome Phú Mỹ Hưng" };
    const branchName = branchNames[branch] || (branch ? `chi nhánh ${branch}` : "");

    let emptyDesc = "";
    if (keyword) {
      emptyDesc = `Không tìm thấy phòng nào phù hợp với từ khóa "<strong>${escapeHtml(keyword)}</strong>"${branchName ? ` tại ${branchName}` : ""}.`;
    } else if (hasSidebarFilters) {
      emptyDesc = "Không tìm thấy phòng nào phù hợp với các bộ lọc bạn đã chọn.";
    } else if (slot) {
      emptyDesc = `Hiện không có phòng trống trong khung giờ này${branchName ? ` tại ${branchName}` : ""}.`;
    } else {
      emptyDesc = `Không tìm thấy phòng nào phù hợp với tiêu chí tìm kiếm.`;
    }

    container.innerHTML = `
      <div class="room-empty-state" style="padding: 48px 24px; text-align: center;">
        <div style="width:56px; height:56px; border-radius:50%; background:rgba(184,115,51,0.08); display:flex; align-items:center; justify-content:center; margin:0 auto 16px; color:var(--cozy-primary, #b87333);">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
        </div>
        <h3 style="font-size:18px; font-weight:700; color:var(--text); margin-bottom:8px;">Không tìm thấy phòng phù hợp</h3>
        <p style="font-size:14px; color:var(--text-muted); max-width:460px; margin:0 auto; line-height:1.5;">${emptyDesc}</p>
      </div>
    `;
    return;
  }

  const slotLabels = { K1: "Sáng", K2: "Chiều", K3: "Tối", QD: "Qua đêm" };

  container.innerHTML = rooms.map(r => {
    const amenitiesText = (r.amenities || []).slice(0, 4).join(", ");
    const groupName = r.slot_group_id ? r.slot_group_id.replace("N", "Nhóm ") : "Nhóm 1";

    const rating = getSimulatedRating(r);
    const ratingLabel = getRatingLabel(parseFloat(rating));

    const coverImg = (r.images && r.images.length > 0) ? r.images[0] : "";
    const thumbInner = coverImg
      ? `<img src="${coverImg}" alt="${r.room_name}" loading="lazy">`
      : `<svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="color:var(--text-light);"><rect x="2" y="7" width="20" height="12" rx="2"></rect><path d="M2 11h20"></path><path d="M6 7V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v2"></path></svg>`;
    const photosCount = (r.images && r.images.length) || 0;

    // Phân tích hiển thị khung giờ: nếu có chọn khung cụ thể thì hiện khung đó, nếu xem tất cả thì hiện đủ 4 khung giờ của phòng
    const isSpecificSlot = Boolean(r.start_time && r.end_time && r.khung_code);
    let timeHtml = "";
    if (isSpecificSlot) {
      timeHtml = `
        <div class="room-card-time" style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
          <span><b>${r.start_time} – ${(r.end_time || '').replace('+1', '')}</b> (${slotLabels[r.khung_code] || r.khung_code})</span>
          <span style="font-size:11px; padding:1px 6px; border-radius:6px; background:rgba(184,115,51,0.1); color:var(--cozy-primary, #b87333); font-weight:600;" title="Nhóm nấc giờ giãn cách: ${groupName}">${groupName}</span>
        </div>
      `;
    } else {
      const sList = r.slots || [];
      timeHtml = `
        <div class="room-slots-container">
          <div class="room-slots-header" style="display:flex; align-items:center; justify-content:space-between;">
            <span>Các khung giờ lưu trú:</span>
            <span style="font-size:11px; font-weight:600; color:var(--cozy-primary, #b87333);" title="Nhóm nấc giờ giãn cách: ${groupName}">${groupName}</span>
          </div>
          <div class="room-slots-grid">
            ${sList.map(s => {
              const cleanEnd = s.end_time ? s.end_time.replace("+1", "").trim() : "";
              const sh = s.khung_code === "K1" ? "Sáng" : (s.khung_code === "K2" ? "Chiều" : (s.khung_code === "K3" ? "Tối" : "Qua đêm"));
              return `
                <div class="room-slot-chip" onclick="openRoomDetail('${r.room_id}')" title="Khung ${sh}: ${s.start_time} – ${cleanEnd} - Bấm để xem chi tiết">
                  <span class="room-slot-chip-name">${sh}</span>
                  <span class="room-slot-chip-time">${s.start_time} – ${cleanEnd}</span>
                </div>
              `;
            }).join("")}
          </div>
        </div>
      `;
    }

    const bookBtnHtml = isSpecificSlot
      ? `<button class="btn btn-primary" style="width:100%; height:38px; font-size:13px;" onclick="handleBookRoomClick('${r.room_id}', '${searchDate}', '${r.khung_code}', ${r.price}, '${r.start_time}', '${r.end_time}')">Đặt phòng ngay</button>`
      : `<button class="btn btn-primary" style="width:100%; height:38px; font-size:13px;" onclick="openRoomDetail('${r.room_id}')">Chọn khung và Đặt</button>`;

    return `
      <div class="room-card-traveloka">
        <!-- Ảnh Phòng -->
        <div class="room-card-thumb" style="cursor:pointer;" onclick="openRoomDetail('${r.room_id}')">
          ${thumbInner}
          <div class="room-card-concept-badge">${r.concept_name || r.concept}</div>
          ${photosCount > 0 ? `<div class="room-card-photos-tag" onclick="event.stopPropagation(); openRoomDetail('${r.room_id}')">${photosCount} ảnh</div>` : ""}
        </div>

        <!-- Thông tin Phòng -->
        <div class="room-card-info">
          <div class="room-card-title" onclick="openRoomDetail('${r.room_id}')">${r.room_name}</div>
          <div class="room-card-meta">${r.branch_name} - ${r.room_type} - Tối đa ${r.capacity} khách${r.area ? ` - ${r.area}m²` : ''}${r.bed_type ? ` - ${r.bed_type}` : ''}</div>
          ${amenitiesText ? `<div class="room-card-amenities"><span style="font-weight:600; color:var(--cozy-dark);">Tiện ích:</span> ${amenitiesText}</div>` : ""}

          <div class="room-card-foot" style="flex-direction:column; align-items:flex-start; gap:8px;">
            ${timeHtml}
            <div class="room-card-policy">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
              Thanh toán qua VietQR - Khử khuẩn 100%
            </div>
          </div>
        </div>

        <!-- Giá và Đặt phòng -->
        <div class="room-card-pricing">
          <div class="room-rating-box">
            <span class="rating-badge-num">${rating}</span>
            <span class="rating-badge-text">${ratingLabel}</span>
          </div>

          <div style="text-align: right; width: 100%;">
            <div class="room-price-val">${formatMoney(r.price)}</div>
            <div class="room-price-sub">${isSpecificSlot ? '/ khung giờ' : 'giá từ / khung'}</div>

            <div style="margin-top: 12px;">
              ${bookBtnHtml}
            </div>
          </div>
        </div>
      </div>
    `;
  }).join("");
}

// Điều phối đặt phòng tập trung: kiểm tra trạng thái đăng nhập thực tế tại thời điểm người dùng click
function handleBookRoomClick(roomId, bookingDate, slotCode, price, startTime, endTime) {
  // 1. Kiểm tra và đồng bộ phiên đăng nhập từ localStorage nếu memory chưa có
  if (!state.user) {
    const stored = localStorage.getItem("cozy_user");
    if (stored) {
      try {
        state.user = JSON.parse(stored);
      } catch (e) {}
    }
  }

  // 2. Nếu chưa đăng nhập: lưu lại phòng chờ đặt để sau khi login tự động chuyển tiếp
  if (!state.user) {
    state.pendingRoomToBook = { roomId, bookingDate, slotCode, price, startTime, endTime };
    showToast("Vui lòng đăng nhập để tiến hành đặt phòng.", "warning");
    navigateTo("auth");
    return;
  }

  // 3. Đã đăng nhập: chuyển tiếp ngay sang trang Xác nhận đặt phòng / Checkout
  initiateBooking(roomId, bookingDate, slotCode, price, startTime, endTime);
}

// Xử lý khi khách click đặt phòng trực tiếp từ Modal Chi Tiết Phòng
function handleBookFromDetail(roomId) {
  const dateInput = document.getElementById("search-date");
  const slotSelect = document.getElementById("search-slot");
  const searchDate = dateInput?.value || new Date().toISOString().split("T")[0];
  const slotCode = slotSelect?.value || "K1";

  // Tìm thông tin phòng từ state.selectedRoom hoặc state.rooms
  let price = 180000;
  let startTime = "09:30";
  let endTime = "12:30";

  if (state.selectedRoom && state.selectedRoom.slots) {
    const s = state.selectedRoom.slots.find(x => x.khung_code === slotCode) || state.selectedRoom.slots[0];
    if (s) {
      price = s.price;
      startTime = s.start_time;
      endTime = s.end_time;
    }
  }

  closeRoomDetail();
  handleBookRoomClick(roomId, searchDate, slotCode, price, startTime, endTime);
}

// Hiển thị prompt khi khách vãng lai muốn đặt phòng (BR-07)
function promptLoginToBook(roomId, bookingDate, slotCode, price, startTime, endTime) {
  if (!state.user) {
    const stored = localStorage.getItem("cozy_user");
    if (stored) {
      try { state.user = JSON.parse(stored); } catch (e) {}
    }
  }
  if (state.user) {
    if (roomId) {
      initiateBooking(roomId, bookingDate, slotCode, price, startTime, endTime);
    }
    return;
  }

  showToast("Vui lòng đăng nhập để tiến hành đặt phòng.", "warning");
  navigateTo("auth");
}

async function openRoomDetail(roomId) {
  if (typeof openRoomDetailView === "function") {
    openRoomDetailView(roomId);
    return;
  }
  try {
    const res = await apiFetch(`/api/rooms/${roomId}`);
    state.selectedRoom = res;
    const r = res.room;

    // Gallery ảnh
    renderRoomGallery(r.images || []);

    // Header info
    document.getElementById("modal-room-title").textContent = `${r.room_name} (${r.branch_name})`;
    document.getElementById("detail-room-concept").textContent = `${r.concept} — ${r.concept_name}`;
    document.getElementById("detail-room-desc").textContent = r.description;
    document.getElementById("detail-room-capacity").textContent = `${r.capacity} người (${r.bed_type}, diện tích ${r.area}m²)`;
    document.getElementById("detail-room-amenities").innerHTML = (r.amenities || [])
      .map(a => `<span class="badge badge-cozy">✓ ${a}</span>`)
      .join(" ");

    // 4 Slots info
    const slotsContainer = document.getElementById("detail-slots-container");
    if (slotsContainer) {
      slotsContainer.innerHTML = res.slots
        .map(s => `
          <div style="background: var(--cozy-light); border: 1px solid var(--cozy-border); border-radius: var(--radius-sm); padding: 12px; text-align: center;">
            <div style="font-weight: 700; font-size: 13.5px; color: var(--cozy-dark);">${s.label}</div>
            <div style="font-size: 12px; color: var(--text-muted); margin: 4px 0;">${s.start_time} – ${s.end_time}</div>
            <div style="font-weight: 800; color: var(--cozy-primary); font-size: 15px;">${formatMoney(s.price)}</div>
          </div>
        `)
        .join("");
    }

    // 7-Day Grid Calendar
    renderAvailabilityGrid(res.grid);

    // Thêm nút Đặt phòng ngay vào footer của Modal Chi tiết phòng
    const modalFooter = document.querySelector("#modal-room-detail .modal-footer");
    if (modalFooter) {
      modalFooter.innerHTML = `
        <button class="btn btn-outline" onclick="closeRoomDetail()">Đóng</button>
        <button class="btn btn-primary" style="padding:8px 20px; font-weight:700;" onclick="handleBookFromDetail('${r.room_id}')">
          Đặt phòng này ngay →
        </button>
      `;
    }

    // Open Modal
    const modal = document.getElementById("modal-room-detail");
    if (modal) modal.classList.add("active");
  } catch (err) {}
}

function renderRoomGallery(images) {
  const container = document.getElementById("detail-room-gallery");
  if (!container) return;

  if (!images || images.length === 0) {
    container.innerHTML = "";
    return;
  }

  container.innerHTML = `
    <div id="gallery-main" style="width:100%; height:280px; border-radius:var(--radius-sm); overflow:hidden; background:#eee; margin-bottom:8px;">
      <img id="gallery-main-img" src="${images[0]}" alt="Ảnh phòng" style="width:100%; height:100%; object-fit:cover; display:block;">
    </div>
    ${images.length > 1 ? `
      <div style="display:flex; gap:8px; overflow-x:auto; padding-bottom:2px;">
        ${images.map((img, i) => `
          <img src="${img}" alt="Ảnh phòng ${i + 1}"
               data-idx="${i}"
               onclick="document.getElementById('gallery-main-img').src='${img}'"
               style="width:64px; height:64px; object-fit:cover; border-radius:6px; cursor:pointer; flex-shrink:0; border:2px solid ${i === 0 ? "var(--cozy-primary)" : "transparent"};"
               onmouseover="this.style.borderColor='var(--cozy-primary)'"
               onmouseout="this.style.borderColor='transparent'">
        `).join("")}
      </div>
    ` : ""}
  `;
}

function closeRoomDetail() {
  const modal = document.getElementById("modal-room-detail");
  if (modal) modal.classList.remove("active");
}

function renderAvailabilityGrid(grid) {
  const container = document.getElementById("detail-grid-calendar");
  if (!container) return;

  const dates = grid.dates || [];
  const slots = ["K1", "K2", "K3", "QD"];
  const slotLabels = {
    K1: "09:30 – 12:30 (Sáng)",
    K2: "13:00 – 16:00 (Chiều)",
    K3: "16:30 – 19:30 (Tối)",
    QD: "20:00 – 08:30 (Qua đêm)"
  };

  let html = `
    <table class="grid-calendar">
      <thead>
        <tr>
          <th style="text-align: left; min-width: 180px;">Khung giờ</th>
          ${dates.map(d => `<th>${d.slice(5).replace("-", "/")}</th>`).join("")}
        </tr>
      </thead>
      <tbody>
  `;

  slots.forEach(sCode => {
    html += `<tr><td style="text-align: left; font-weight: 700; background: var(--cozy-light); font-size: 12px;">${slotLabels[sCode]}</td>`;
    dates.forEach(d => {
      const cell = grid.matrix?.[d]?.[sCode];
      const isAvail = cell === "AVAILABLE" || cell === undefined;
      html += `<td><span class="slot-status-pill ${isAvail ? "available" : "booked"}">${isAvail ? "Còn trống" : "Đã đặt"}</span></td>`;
    });
    html += "</tr>";
  });

  html += "</tbody></table>";
  container.innerHTML = html;
}

function resetSearchFilters() {
  const keyword = document.getElementById("search-keyword");
  const budget = document.getElementById("search-budget");
  if (keyword) keyword.value = "";
  if (budget) budget.value = "";
  resetFilters();
}


function syncSidebarSlotWithSearch(slotVal) {
  const slotRadios = document.querySelectorAll('input[name="filter-slot-shift"]');
  if (!slotRadios.length) return;
  let targetVal = "";
  if (slotVal) {
    if (slotVal.startsWith("K1")) targetVal = "K1";
    else if (slotVal.startsWith("K2")) targetVal = "K2";
    else if (slotVal.startsWith("K3")) targetVal = "K3";
    else if (slotVal.startsWith("QD")) targetVal = "QD";
    else targetVal = slotVal;
  }
  slotRadios.forEach(r => {
    r.checked = (r.value === targetVal);
  });
}

function handleSlotFilterChange(slotVal) {
  const slotSelect = document.getElementById("search-slot");
  if (slotSelect) {
    slotSelect.value = slotVal || "";
  }
  syncSidebarSlotWithSearch(slotVal);
  performSearch();
}

// -------------------------------------------------------------
// 1. Lịch sử tìm kiếm gần đây (Recent Searches)
// -------------------------------------------------------------
const RECENT_SEARCHES_KEY = "cozyhome_recent_searches";

function getRecentSearches() {
  try {
    return JSON.parse(localStorage.getItem(RECENT_SEARCHES_KEY)) || [];
  } catch (e) {
    return [];
  }
}

function saveRecentSearch(kw) {
  if (!kw || !kw.trim()) return;
  const clean = kw.trim();
  let list = getRecentSearches().filter(item => item.toLowerCase() !== clean.toLowerCase());
  list.unshift(clean);
  if (list.length > 6) list = list.slice(0, 6);
  try {
    localStorage.setItem(RECENT_SEARCHES_KEY, JSON.stringify(list));
  } catch (e) {}
}

function clearRecentSearches() {
  try {
    localStorage.removeItem(RECENT_SEARCHES_KEY);
  } catch (e) {}
  const dropdown = document.getElementById("search-autocomplete-dropdown");
  if (dropdown) dropdown.style.display = "none";
}

// -------------------------------------------------------------
// 2. Active Filter Badges (Thanh hiển thị và Gỡ nhanh tiêu chí)
// Phân tách rõ ràng: Tiêu chí tìm kiếm vs Bộ lọc đặc tính phòng
// -------------------------------------------------------------
function renderActiveFilterBadges(active) {
  const container = document.getElementById("active-filters-container");
  if (!container) return;

  const searchBadges = [];
  const filterBadges = [];

  // Nhóm 1: Tiêu chí từ Thanh tìm kiếm
  if (active.keyword) {
    searchBadges.push({
      label: `Từ khóa: "${active.keyword}"`,
      type: "keyword",
      value: active.keyword,
    });
  }

  if (active.branch) {
    const branchNames = { BT: "Bến Thành", TD: "Thảo Điền", PMH: "Phú Mỹ Hưng" };
    searchBadges.push({
      label: `Chi nhánh: ${branchNames[active.branch] || active.branch}`,
      type: "branch",
      value: active.branch,
    });
  }

  const slotNames = {
    K1: "Sáng (09:30 – 14:00)",
    K1_N1: "Sáng (09:30 – 12:30)",
    K1_N2: "Sáng (10:00 – 13:00)",
    K1_N3: "Sáng (10:30 – 13:30)",
    K1_N4: "Sáng (11:00 – 14:00)",
    K2: "Chiều (13:00 – 17:30)",
    K2_N1: "Chiều (13:00 – 16:00)",
    K2_N2: "Chiều (13:30 – 16:30)",
    K2_N3: "Chiều (14:00 – 17:00)",
    K2_N4: "Chiều (14:30 – 17:30)",
    K3: "Tối (16:30 – 21:00)",
    K3_N1: "Tối (16:30 – 19:30)",
    K3_N2: "Tối (17:00 – 20:00)",
    K3_N3: "Tối (17:30 – 20:30)",
    K3_N4: "Tối (18:00 – 21:00)",
    QD: "Qua đêm (20:00 – 10:00)",
    QD_N1: "Qua đêm (20:00 – 08:30)",
    QD_N2: "Qua đêm (20:30 – 09:00)",
    QD_N3: "Qua đêm (21:00 – 09:30)",
    QD_N4: "Qua đêm (21:30 – 10:00)",
  };
  if (active.slot) {
    const opt = document.querySelector(`#search-slot option[value="${active.slot}"]`);
    const fallbackText = opt ? opt.textContent.trim() : active.slot;
    const displaySlot = slotNames[active.slot] || fallbackText;
    searchBadges.push({
      label: `Khung giờ: ${displaySlot}`,
      type: "slot",
      value: active.slot,
    });
  }

  // Nhóm 2: Tiêu chí từ Bộ lọc phòng (Sidebar)
  if (active.minPrice || active.maxPrice) {
    let priceText = "Giá: ";
    if (active.minPrice && active.maxPrice) priceText += `${parseInt(active.minPrice).toLocaleString("vi-VN")}₫ – ${parseInt(active.maxPrice).toLocaleString("vi-VN")}₫`;
    else if (active.minPrice) priceText += `Từ ${parseInt(active.minPrice).toLocaleString("vi-VN")}₫`;
    else if (active.maxPrice) priceText += `Đến ${parseInt(active.maxPrice).toLocaleString("vi-VN")}₫`;
    filterBadges.push({
      label: priceText,
      type: "price",
    });
  }

  (active.types || []).forEach(t => {
    filterBadges.push({
      label: `Hạng: ${t}`,
      type: "type",
      value: t,
    });
  });

  (active.amenities || []).forEach(a => {
    filterBadges.push({
      label: `Tiện nghi: ${a}`,
      type: "amenity",
      value: a,
    });
  });

  const areaLabels = { small: "Diện tích < 25m²", medium: "Diện tích 25–35m²", large: "Diện tích > 35m²" };
  if (active.areaRange && areaLabels[active.areaRange]) {
    filterBadges.push({
      label: areaLabels[active.areaRange],
      type: "area",
      value: active.areaRange,
    });
  }

  (active.bedTypes || []).forEach(b => {
    filterBadges.push({
      label: `Giường: ${b}`,
      type: "bed",
      value: b,
    });
  });

  if (searchBadges.length === 0 && filterBadges.length === 0) {
    container.style.display = "none";
    container.innerHTML = "";
    return;
  }

  container.style.display = "flex";
  let html = "";

  // Phần 1: Tiêu chí tìm kiếm (nếu có)
  if (searchBadges.length > 0) {
    html += `
      <div class="active-filter-group group-search">
        <span class="active-filter-group-title">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
          Tìm kiếm:
        </span>
        <div class="active-filter-chips">
          ${searchBadges.map(b => `
            <span class="filter-badge badge-search">
              <span>${b.label}</span>
              <span class="badge-remove" onclick="removeActiveFilter('${b.type}', '${b.value || ""}')" title="Gỡ tiêu chí tìm kiếm này">×</span>
            </span>
          `).join("")}
        </div>
      </div>
    `;
  }

  // Dải phân cách giữa Tìm kiếm và Bộ lọc
  if (searchBadges.length > 0 && filterBadges.length > 0) {
    html += `<div class="active-filter-sep"></div>`;
  }

  // Phần 2: Bộ lọc phòng từ sidebar (nếu có)
  if (filterBadges.length > 0) {
    html += `
      <div class="active-filter-group group-filter">
        <span class="active-filter-group-title">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon></svg>
          Bộ lọc phòng:
        </span>
        <div class="active-filter-chips">
          ${filterBadges.map(b => `
            <span class="filter-badge badge-filter">
              <span>${b.label}</span>
              <span class="badge-remove" onclick="removeActiveFilter('${b.type}', '${b.value || ""}')" title="Gỡ bộ lọc này">×</span>
            </span>
          `).join("")}
        </div>
        <button type="button" class="clear-sidebar-filters-btn" onclick="resetSidebarFilters()" title="Xóa toàn bộ bộ lọc phòng">
          Xóa bộ lọc
        </button>
      </div>
    `;
  }

  container.innerHTML = html;
}

function removeActiveFilter(type, value) {
  if (type === "keyword") {
    const input = document.getElementById("search-keyword");
    if (input) input.value = "";
    const clearBtn = document.getElementById("search-clear-btn");
    if (clearBtn) clearBtn.style.display = "none";
    performSearch();
  } else if (type === "branch") {
    const topSelect = document.getElementById("search-branch");
    if (topSelect) topSelect.value = "";
    performSearch();
  } else if (type === "slot") {
    const slotSelect = document.getElementById("search-slot");
    if (slotSelect) slotSelect.value = "";
    performSearch();
  } else if (type === "price") {
    const minEl = document.getElementById("filter-min-price");
    const maxEl = document.getElementById("filter-max-price");
    if (minEl) minEl.value = "";
    if (maxEl) maxEl.value = "";
    applyFiltersFromSidebar();
  } else if (type === "type") {
    const idMap = { Standard: "filter-type-std", Deluxe: "filter-type-dlx", Family: "filter-type-fam" };
    const el = document.getElementById(idMap[value]);
    if (el) el.checked = false;
    applyFiltersFromSidebar();
  } else if (type === "amenity") {
    const revMap = {
      "bồn tắm": "filter-amen-bon-tam",
      "ban công": "filter-amen-ban-cong",
      "view hồ": "filter-amen-view-ho",
      "bếp mini": "filter-amen-bep-mini",
      "minibar": "filter-amen-minibar",
      "wifi": "filter-amen-wifi",
    };
    const el = document.getElementById(revMap[value]);
    if (el) el.checked = false;
    applyFiltersFromSidebar();
  } else if (type === "area") {
    const areaRadios = document.querySelectorAll('input[name="filter-area"]');
    areaRadios.forEach(r => { r.checked = (r.value === ""); });
    applyFiltersFromSidebar();
  } else if (type === "bed") {
    const revMap = {
      "1 giường đôi": "filter-bed-double",
      "1 giường đôi lớn": "filter-bed-large",
      "3 giường": "filter-bed-twin",
      "3 giường đôi": "filter-bed-twin",
      "2 giường đôi": "filter-bed-twin",
    };
    const el = document.getElementById(revMap[value]);
    if (el) el.checked = false;
    applyFiltersFromSidebar();
  }
}

// -------------------------------------------------------------
// 3. Fallback Container (Đã bỏ nội dung thông báo fallback)
// -------------------------------------------------------------
function renderSmartFallback(fallback) {
  const container = document.getElementById("smart-fallback-container");
  if (!container) return;

  if (!fallback || fallback.type !== "branch_switch" || !fallback.sample_rooms || fallback.sample_rooms.length === 0) {
    container.style.display = "none";
    container.innerHTML = "";
    return;
  }

  container.style.display = "block";
  const branchId = fallback.target_branch_id || "";
  const branchName = fallback.target_branch_name || "chi nhánh khác";
  const curBranch = fallback.cur_branch_name || "Chi nhánh đã chọn";
  const kw = (fallback.keyword || "").trim();

  const titleText = kw
    ? `Đề xuất phòng có "${escapeHtml(kw)}" tại ${escapeHtml(branchName)}`
    : `Đề xuất phòng phù hợp tại ${escapeHtml(branchName)}`;
  const messageText = `Tại ${escapeHtml(curBranch)} hiện không có phòng thỏa mãn tiêu chí này. CozyHome gợi ý bạn các phòng có sẵn tại <b>${escapeHtml(branchName)}</b>:`;

  const cardsHtml = (fallback.sample_rooms || []).map(r => {
    const coverImg = (r.images && r.images.length > 0) ? r.images[0] : "";
    const thumbHtml = coverImg
      ? `<img src="${coverImg}" alt="${escapeHtml(r.room_name)}" class="smart-fallback-thumb" loading="lazy">`
      : `<div class="smart-fallback-thumb" style="display:flex; align-items:center; justify-content:center; background:#f4ede4; color:#b87333;"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="7" width="20" height="12" rx="2"></rect><path d="M2 11h20"></path></svg></div>`;
    const priceFormatted = r.price ? `${Number(r.price).toLocaleString("vi-VN")}₫ / khung` : "Giá liên hệ";

    return `
      <div class="smart-fallback-card" onclick="openRoomDetail('${r.room_id}')" title="Nhấn để xem chi tiết phòng">
        ${thumbHtml}
        <div class="smart-fallback-card-info">
          <div class="smart-fallback-card-name">${escapeHtml(r.room_name)}</div>
          <div class="smart-fallback-card-branch">${escapeHtml(r.branch_name || branchName)} - ${escapeHtml(r.room_type || "")}</div>
          <div class="smart-fallback-card-price">${priceFormatted}</div>
        </div>
      </div>
    `;
  }).join("");

  container.innerHTML = `
    <div class="smart-fallback-box">
      <div class="smart-fallback-header">
        <div class="smart-fallback-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
        </div>
        <div style="flex:1;">
          <div class="smart-fallback-title">${titleText}</div>
          <div class="smart-fallback-message">${messageText}</div>
          <div class="smart-fallback-action">
            <button type="button" class="btn btn-primary btn-sm" onclick="applyFallbackBranch('${branchId}')">
              Xem tất cả phòng tại ${escapeHtml(branchName)} →
            </button>
          </div>
        </div>
      </div>
      <div class="smart-fallback-sample-grid">
        ${cardsHtml}
      </div>
    </div>
  `;
}

function applyFallbackBranch(branchId) {
  const topSelect = document.getElementById("search-branch");
  if (topSelect) topSelect.value = branchId;
  performSearch();
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function clearSearchKeyword() {
  const input = document.getElementById("search-keyword");
  if (input) input.value = "";
  const clearBtn = document.getElementById("search-clear-btn");
  if (clearBtn) clearBtn.style.display = "none";
  const dropdown = document.getElementById("search-autocomplete-dropdown");
  if (dropdown) dropdown.style.display = "none";
  performSearch();
}
window.clearSearchKeyword = clearSearchKeyword;

function resetSearchBranch() {
  const branchSelect = document.getElementById("search-branch");
  if (branchSelect) branchSelect.value = "";
  performSearch();
}
window.resetSearchBranch = resetSearchBranch;

function resetSearchSlot() {
  const slotSelect = document.getElementById("search-slot");
  if (slotSelect) slotSelect.value = "";
  performSearch();
}
window.resetSearchSlot = resetSearchSlot;

function clearAmenitiesAndSearch() {
  ["filter-amen-bon-tam", "filter-amen-ban-cong", "filter-amen-view-ho",
   "filter-amen-bep-mini", "filter-amen-minibar", "filter-amen-wifi"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.checked = false;
  });
  applyFiltersFromSidebar();
}

// -------------------------------------------------------------
// 4. Live Autocomplete & Quick Clear Input
// -------------------------------------------------------------
function initSearchAutocomplete() {
  const input = document.getElementById("search-keyword");
  const dropdown = document.getElementById("search-autocomplete-dropdown");
  const clearBtn = document.getElementById("search-clear-btn");
  if (!input || !dropdown) return;

  // Xử lý nút xóa nhanh
  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      input.value = "";
      clearBtn.style.display = "none";
      dropdown.style.display = "none";
      input.focus();
      performSearch();
    });
  }

  const headerIcons = {
    history: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>`,
    tag: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"></path><line x1="7" y1="7" x2="7.01" y2="7"></line></svg>`,
    pin: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>`,
    bed: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 4v16"></path><path d="M2 8h18a2 2 0 0 1 2 2v10"></path><path d="M2 17h20"></path><path d="M6 8v9"></path></svg>`,
    compass: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"></polygon></svg>`,
  };

  const svgIcons = {
    history: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>`,
    tag: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"></path><line x1="7" y1="7" x2="7.01" y2="7"></line></svg>`,
    pin: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>`,
    bed: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 4v16"></path><path d="M2 8h18a2 2 0 0 1 2 2v10"></path><path d="M2 17h20"></path><path d="M6 8v9"></path></svg>`,
    compass: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"></polygon></svg>`,
    bath: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6h6a3 3 0 0 1 3 3v2H6V9a3 3 0 0 1 3-3z"></path><path d="M4 11h16a1 1 0 0 1 1 1v3a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4v-3a1 1 0 0 1 1-1z"></path><line x1="6" y1="19" x2="5" y2="21"></line><line x1="18" y1="19" x2="19" y2="21"></line></svg>`,
    balcony: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"></rect><line x1="3" y1="14" x2="21" y2="14"></line><line x1="7" y1="14" x2="7" y2="21"></line><line x1="12" y1="14" x2="12" y2="21"></line><line x1="17" y1="14" x2="17" y2="21"></line></svg>`,
    water: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z"></path></svg>`,
    drink: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6l-6 7-6-7h12z"></path><line x1="12" y1="13" x2="12" y2="21"></line><line x1="8" y1="21" x2="16" y2="21"></line></svg>`,
    kitchen: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 2v20"></path><path d="M6 2v7a3 3 0 0 0 6 0V2"></path><line x1="9" y1="9" x2="9" y2="22"></line></svg>`,
    tree: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22v-7"></path><path d="M12 15l-4-5h2.5L8 6h3L12 2l1 4h3l-2.5 4H16l-4 5z"></path></svg>`,
    city: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="2" width="16" height="20" rx="2"></rect><line x1="9" y1="6" x2="9.01" y2="6"></line><line x1="15" y1="6" x2="15.01" y2="6"></line><line x1="9" y1="10" x2="9.01" y2="10"></line><line x1="15" y1="10" x2="15.01" y2="10"></line><line x1="9" y1="14" x2="9.01" y2="14"></line><line x1="15" y1="14" x2="15.01" y2="14"></line><line x1="9" y1="18" x2="15" y2="18"></line></svg>`,
    sparkle: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>`,
    users: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>`,
  };

  const catalog = {
    amenities: [
      { name: "Bồn tắm nằm", query: "bồn tắm", icon: svgIcons.bath, sub: "Thư giãn bồn tắm nằm" },
      { name: "Ban công view thoáng", query: "ban công", icon: svgIcons.balcony, sub: "Không gian mở ngắm cảnh" },
      { name: "View hồ cảnh quan", query: "view hồ", icon: svgIcons.water, sub: "CozyHome Phú Mỹ Hưng" },
      { name: "Minibar tiện ích", query: "minibar", icon: svgIcons.drink, sub: "CozyHome Bến Thành" },
      { name: "Bếp mini nấu nướng", query: "bếp mini", icon: svgIcons.kitchen, sub: "Trang bị bếp nấu nhỏ" },
      { name: "View cây xanh", query: "view cây xanh", icon: svgIcons.tree, sub: "CozyHome Thảo Điền" },
      { name: "View thành phố", query: "view thành phố", icon: svgIcons.city, sub: "CozyHome Bến Thành" },
    ],
    branches: [
      { name: "CozyHome Bến Thành", query: "Bến Thành", icon: svgIcons.pin, sub: "Quận 1, TP.HCM - Đô thị và văn hóa" },
      { name: "CozyHome Thảo Điền", query: "Thảo Điền", icon: svgIcons.pin, sub: "TP. Thủ Đức - Xanh mát thiên nhiên" },
      { name: "CozyHome Phú Mỹ Hưng", query: "Phú Mỹ Hưng", icon: svgIcons.pin, sub: "Quận 7 - Ven hồ và nhiệt đới" },
    ],
    types: [
      { name: "Hạng phòng Standard", query: "Standard", icon: svgIcons.bed, sub: "2 khách - 22m² - Giá từ 140.000₫" },
      { name: "Hạng phòng Deluxe", query: "Deluxe", icon: svgIcons.sparkle, sub: "3 khách - 28m² - Giá từ 200.000₫" },
      { name: "Hạng phòng Family", query: "Family", icon: svgIcons.users, sub: "6 khách - 40m² - Giá từ 300.000₫" },
    ],
    concepts: [
      { name: "Xanh mát thiên nhiên", query: "Xanh mát", icon: svgIcons.tree, sub: "Phong cách cao nguyên" },
      { name: "Lãng mạn ven hồ", query: "Lãng mạn", icon: svgIcons.water, sub: "Cảnh hồ thơ mộng" },
      { name: "Đô thị năng động", query: "Đô thị", icon: svgIcons.city, sub: "Trung tâm náo nhiệt" },
      { name: "Nhiệt đới trong lành", query: "Nhiệt đới", icon: svgIcons.compass, sub: "Không gian biển và gió" },
    ],
  };

  function renderDropdown(keyword) {
    const q = (keyword || "").trim().toLowerCase();
    let html = "";

    if (!q) {
      // Chỉ hiển thị Tìm kiếm gần đây (Recent Searches)
      const recents = getRecentSearches();
      if (recents.length > 0) {
        html += `<div class="search-ac-section">
          <div class="search-ac-header" style="justify-content: space-between;">
            <div style="display: flex; align-items: center; gap: 8px;">
              ${headerIcons.history}
              <span>Tìm kiếm gần đây</span>
            </div>
            <span style="font-size: 11px; cursor: pointer; color: var(--danger); font-weight: 600;" onclick="clearRecentSearches()">Xóa tất cả</span>
          </div>`;
        recents.forEach(item => {
          html += `
            <div class="search-ac-item" onclick="applySearchAutocomplete('${item.replace(/'/g, "\\'")}')">
              <div class="ac-main">
                <span class="ac-icon">${svgIcons.history}</span>
                <span>${item}</span>
              </div>
            </div>
          `;
        });
        html += `</div>`;
      } else {
        dropdown.style.display = "none";
        dropdown.innerHTML = "";
        return;
      }
    } else {
      // Tìm khớp trong danh mục
      const matchAmenities = catalog.amenities.filter(a => a.name.toLowerCase().includes(q) || a.query.toLowerCase().includes(q));
      const matchBranches = catalog.branches.filter(b => b.name.toLowerCase().includes(q) || b.query.toLowerCase().includes(q));
      const matchTypes = catalog.types.filter(t => t.name.toLowerCase().includes(q) || t.query.toLowerCase().includes(q));
      const matchConcepts = catalog.concepts.filter(c => c.name.toLowerCase().includes(q) || c.query.toLowerCase().includes(q));

      if (matchAmenities.length > 0) {
        html += `<div class="search-ac-section"><div class="search-ac-header">${headerIcons.tag} <span>Tiện nghi</span></div>`;
        matchAmenities.forEach(a => {
          html += `
            <div class="search-ac-item" onclick="applySearchAutocomplete('${a.query}')">
              <div class="ac-main"><span class="ac-icon">${a.icon}</span><div><div>${a.name}</div><div class="ac-sub">${a.sub}</div></div></div>
            </div>`;
        });
        html += `</div>`;
      }

      if (matchBranches.length > 0) {
        html += `<div class="search-ac-section"><div class="search-ac-header">${headerIcons.pin} <span>Chi nhánh</span></div>`;
        matchBranches.forEach(b => {
          html += `
            <div class="search-ac-item" onclick="applySearchAutocomplete('${b.query}')">
              <div class="ac-main"><span class="ac-icon">${b.icon}</span><div><div>${b.name}</div><div class="ac-sub">${b.sub}</div></div></div>
            </div>`;
        });
        html += `</div>`;
      }

      if (matchTypes.length > 0) {
        html += `<div class="search-ac-section"><div class="search-ac-header">${headerIcons.bed} <span>Hạng phòng</span></div>`;
        matchTypes.forEach(t => {
          html += `
            <div class="search-ac-item" onclick="applySearchAutocomplete('${t.query}')">
              <div class="ac-main"><span class="ac-icon">${t.icon}</span><div><div>${t.name}</div><div class="ac-sub">${t.sub}</div></div></div>
            </div>`;
        });
        html += `</div>`;
      }

      if (matchConcepts.length > 0) {
        html += `<div class="search-ac-section"><div class="search-ac-header">${headerIcons.compass} <span>Concept và Phong cách</span></div>`;
        matchConcepts.forEach(c => {
          html += `
            <div class="search-ac-item" onclick="applySearchAutocomplete('${c.query}')">
              <div class="ac-main"><span class="ac-icon">${c.icon}</span><div><div>${c.name}</div><div class="ac-sub">${c.sub}</div></div></div>
            </div>`;
        });
        html += `</div>`;
      }

      if (!html) {
        html = `
          <div class="search-ac-empty">
            Bấm <strong>Enter</strong> hoặc nút <strong>Tìm phòng</strong> để tìm "${keyword}"
          </div>
        `;
      }
    }

    dropdown.innerHTML = html;
    dropdown.style.display = "block";
  }

  input.addEventListener("focus", () => {
    renderDropdown(input.value);
  });

  input.addEventListener("input", () => {
    if (clearBtn) clearBtn.style.display = input.value.trim() ? "inline-flex" : "none";
    renderDropdown(input.value);
  });

  // Đóng khi click ngoài
  document.addEventListener("click", (e) => {
    if (!input.contains(e.target) && !dropdown.contains(e.target)) {
      dropdown.style.display = "none";
    }
  });

  // Phím ESC đóng
  input.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      dropdown.style.display = "none";
    }
  });
}

function applySearchAutocomplete(val) {
  const input = document.getElementById("search-keyword");
  const dropdown = document.getElementById("search-autocomplete-dropdown");
  const clearBtn = document.getElementById("search-clear-btn");
  if (input) {
    input.value = val;
    if (clearBtn) clearBtn.style.display = "inline-flex";
  }
  if (dropdown) dropdown.style.display = "none";
  performSearch();
}

// Tự động khởi tạo khi tài liệu sẵn sàng
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initSearchAutocomplete);
} else {
  initSearchAutocomplete();
}

