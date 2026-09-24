// -------------------------------------------------------------
// CozyHome — Chi tiết phòng (Room Detail Page)
// UX/UI phong cách Homestay hiện đại, sang trọng và tối giản
// -------------------------------------------------------------

let currentRoomData = null;
let currentLightboxImages = [];
let currentLightboxIndex = 0;
let currentGalleryIndex = 0;
let currentRoomImages = [];
let currentStayType = "slot"; // "slot" (theo giờ) | "overnight" (qua đêm)
let currentGuestCount = 2;
let currentSelectedSlotCode = "K1";
let currentSelectedDate = new Date().toISOString().split("T")[0];

const BRANCH_LOCATIONS = {
  BT: {
    address: "123 Lê Thánh Tôn, Phường Bến Thành, Quận 1, TP. Hồ Chí Minh",
    shortAddr: "Bến Thành, Quận 1, TP.HCM",
    mapsQuery: "123 Lê Thánh Tôn, Bến Thành, Quận 1, TP Hồ Chí Minh",
    phone: "0909 000 001",
  },
  TD: {
    address: "45 Xuân Thủy, Phường Thảo Điền, TP. Thủ Đức, TP. Hồ Chí Minh",
    shortAddr: "Thảo Điền, TP. Thủ Đức, TP.HCM",
    mapsQuery: "45 Xuân Thủy, Thảo Điền, TP Thủ Đức, TP Hồ Chí Minh",
    phone: "0909 000 002",
  },
  PMH: {
    address: "88 Nguyễn Đức Cảnh, Phường Tân Phong, Quận 7, TP. Hồ Chí Minh",
    shortAddr: "Phú Mỹ Hưng, Quận 7, TP.HCM",
    mapsQuery: "88 Nguyễn Đức Cảnh, Tân Phong, Quận 7, TP Hồ Chí Minh",
    phone: "0909 000 003",
  },
};

const AMENITY_ICONS = {
  "wifi": `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.55a11 11 0 0 1 14.08 0"></path><path d="M1.42 9a16 16 0 0 1 21.16 0"></path><path d="M8.53 16.11a6 6 0 0 1 6.95 0"></path><line x1="12" y1="20" x2="12.01" y2="20"></line></svg>`,
  "máy lạnh": `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12h20"></path><path d="M12 2v20"></path><path d="m20 16-4-4 4-4"></path><path d="m4 8 4 4-4 4"></path><path d="m16 4-4 4-4-4"></path><path d="m8 20 4-4 4 4"></path></svg>`,
  "điều hòa": `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12h20"></path><path d="M12 2v20"></path><path d="m20 16-4-4 4-4"></path><path d="m4 8 4 4-4 4"></path><path d="m16 4-4 4-4-4"></path><path d="m8 20 4-4 4 4"></path></svg>`,
  "máy chiếu": `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 13h20"></path><path d="M5 13a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2"></path><circle cx="7" cy="9" r="1.5"></circle><path d="m19 13 2 4"></path><path d="m5 13-2 4"></path><path d="M16 8h2"></path><path d="M16 10h2"></path></svg>`,
  "tivi": `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="20" height="15" rx="2" ry="2"></rect><polyline points="17 2 12 7 7 2"></polyline></svg>`,
  "smart tv": `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="20" height="15" rx="2" ry="2"></rect><polyline points="17 2 12 7 7 2"></polyline></svg>`,
  "bồn tắm": `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6h6a3 3 0 0 1 3 3v2H6V9a3 3 0 0 1 3-3z"></path><path d="M4 11h16a1 1 0 0 1 1 1v3a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4v-3a1 1 0 0 1 1-1z"></path><line x1="6" y1="19" x2="5" y2="21"></line><line x1="18" y1="19" x2="19" y2="21"></line></svg>`,
  "ban công": `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"></rect><line x1="3" y1="14" x2="21" y2="14"></line><line x1="7" y1="14" x2="7" y2="21"></line><line x1="12" y1="14" x2="12" y2="21"></line><line x1="17" y1="14" x2="17" y2="21"></line></svg>`,
  "sofa": `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 9V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v3"></path><path d="M2 11v5a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-5a2 2 0 0 0-4 0v2H6v-2a2 2 0 0 0-4 0Z"></path><path d="M4 18v2"></path><path d="M20 18v2"></path></svg>`,
  "trà": `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 8h1a4 4 0 1 1 0 8h-1"></path><path d="M3 8h14v9a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4Z"></path><line x1="6" y1="2" x2="6" y2="4"></line><line x1="10" y1="2" x2="10" y2="4"></line><line x1="14" y1="2" x2="14" y2="4"></line></svg>`,
  "cà phê": `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8h1a4 4 0 0 1 0 8h-1"></path><path d="M2 8h16v9a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4V8z"></path><line x1="6" y1="1" x2="6" y2="4"></line><line x1="10" y1="1" x2="10" y2="4"></line><line x1="14" y1="1" x2="14" y2="4"></line></svg>`,
  "loa": `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="2" width="16" height="20" rx="2"></rect><circle cx="12" cy="14" r="4"></circle><line x1="12" y1="6" x2="12.01" y2="6"></line></svg>`,
  "gương": `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="11" rx="6" ry="8"></ellipse><path d="M8 21h8"></path><path d="M12 19v2"></path></svg>`,
  "gác lửng": `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21h18"></path><path d="M3 10h18"></path><path d="M7 21v-7"></path><path d="M17 21v-7"></path><path d="M3 3l9-2 9 2v18"></path></svg>`,
  "minibar": `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6l-6 7-6-7h12z"></path><line x1="12" y1="13" x2="12" y2="21"></line><line x1="8" y1="21" x2="16" y2="21"></line></svg>`,
  "tủ lạnh": `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="2" width="14" height="20" rx="2"></rect><line x1="5" y1="10" x2="19" y2="10"></line><line x1="9" y1="6" x2="9" y2="7"></line><line x1="9" y1="14" x2="9" y2="16"></line></svg>`,
  "lò vi sóng": `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="2"></rect><rect x="5" y="7" width="10" height="10" rx="1"></rect><circle cx="18" cy="9" r="1"></circle><circle cx="18" cy="13" r="1"></circle></svg>`,
  "bếp mini": `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 2v20"></path><path d="M6 2v7a3 3 0 0 0 6 0V2"></path><line x1="9" y1="9" x2="9" y2="22"></line></svg>`,
  "bếp": `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 2v20"></path><path d="M6 2v7a3 3 0 0 0 6 0V2"></path><line x1="9" y1="9" x2="9" y2="22"></line></svg>`,
  "bàn ăn": `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7h18"></path><path d="M6 7v13"></path><path d="M18 7v13"></path><path d="M4 11h16"></path></svg>`,
  "bàn làm việc": `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="12" rx="2"></rect><line x1="6" y1="20" x2="6" y2="16"></line><line x1="18" y1="20" x2="18" y2="16"></line></svg>`,
  "bàn trang điểm": `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="7" r="4"></circle><path d="M4 15h16"></path><path d="M6 15v6"></path><path d="M18 15v6"></path></svg>`,
  "ghế": `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 9V6a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2v3"></path><path d="M3 11v5a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-5a2 2 0 0 0-4 0v2H7v-2a2 2 0 0 0-4 0Z"></path><path d="M5 18v3"></path><path d="M19 18v3"></path></svg>`,
  "đèn": `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 2h6l3 7H6l3-7Z"></path><path d="M12 9v10"></path><path d="M8 21h8"></path></svg>`,
  "giường": `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 4v16"></path><path d="M2 8h18a2 2 0 0 1 2 2v10"></path><path d="M2 17h20"></path><path d="M6 8v9"></path></svg>`,
  "phòng tắm": `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12h16a1 1 0 0 1 1 1v3a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4v-3a1 1 0 0 1 1-1z"></path><path d="M6 12V5a2 2 0 0 1 2-2h1"></path></svg>`,
  "sông": `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 6c.6.5 1.2 1 2.5 1C7 7 7 5 9.5 5c2.6 0 2.4 2 5 2 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1"></path><path d="M2 12c.6.5 1.2 1 2.5 1 2.5 0 2.5-2 5-2 2.6 0 2.4 2 5 2 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1"></path><path d="M2 18c.6.5 1.2 1 2.5 1 2.5 0 2.5-2 5-2 2.6 0 2.4 2 5 2 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1"></path></svg>`,
  "hồ": `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z"></path></svg>`,
  "landmark": `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="12 2 12 22"></polyline><path d="M7 22l5-18 5 18"></path><line x1="5" y1="17" x2="19" y2="17"></line><line x1="8" y1="12" x2="16" y2="12"></line></svg>`,
  "hoàng hôn": `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v1"></path><path d="M5.22 10.22l.71.71"></path><path d="M18.07 10.93l.71-.71"></path><path d="M2 17h20"></path><path d="M4 21h16"></path><path d="M17 17a5 5 0 0 0-10 0"></path></svg>`,
  "tinh dầu": `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 2h4"></path><path d="M12 2v5"></path><path d="M8 7h8a2 2 0 0 1 2 2v9a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V9a2 2 0 0 1 2-2Z"></path><circle cx="12" cy="14" r="2"></circle></svg>`,
  "view thành phố": `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="2" width="16" height="20" rx="2"></rect><line x1="9" y1="6" x2="9.01" y2="6"></line><line x1="15" y1="6" x2="15.01" y2="6"></line><line x1="9" y1="10" x2="9.01" y2="10"></line><line x1="15" y1="10" x2="15.01" y2="10"></line><line x1="9" y1="14" x2="9.01" y2="14"></line><line x1="15" y1="14" x2="15.01" y2="14"></line><line x1="9" y1="18" x2="15" y2="18"></line></svg>`,
  "cây": `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22v-7"></path><path d="M12 15l-4-5h2.5L8 6h3L12 2l1 4h3l-2.5 4H16l-4 5z"></path></svg>`,
  "vườn": `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22v-7"></path><path d="M12 15l-4-5h2.5L8 6h3L12 2l1 4h3l-2.5 4H16l-4 5z"></path></svg>`,
  "rừng": `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22v-7"></path><path d="M12 15l-4-5h2.5L8 6h3L12 2l1 4h3l-2.5 4H16l-4 5z"></path></svg>`,
  "máy sấy tóc": `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"></circle><path d="M12 3v18"></path><path d="M3 12h18"></path></svg>`,
  "nước nóng": `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h7a4 4 0 0 1 4 4v12"></path><path d="M12 15h6"></path><path d="M15 12l3 3-3 3"></path></svg>`,
  "thang máy": `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"></rect><polyline points="7 10 10 7 13 10"></polyline><polyline points="17 14 14 17 11 14"></polyline></svg>`,
  "máy giặt": `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="2" width="16" height="20" rx="2"></rect><circle cx="12" cy="13" r="5"></circle></svg>`,
};

function getAmenityIcon(name) {
  const clean = (name || "").toLowerCase().trim();
  for (const [key, icon] of Object.entries(AMENITY_ICONS)) {
    if (clean.includes(key)) return icon;
  }
  return `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
}

// =============================================================
// 1. ENTRY POINT: Mở Màn hình Chi tiết phòng
// =============================================================
async function openRoomDetailView(roomId) {
  if (!roomId) return;

  // Điều hướng sang view room-detail
  if (typeof navigateTo === "function") {
    navigateTo("room-detail");
  } else {
    document.querySelectorAll("main > section").forEach(s => s.style.display = "none");
    const v = document.getElementById("view-room-detail");
    if (v) v.style.display = "block";
  }

  // Cập nhật URL đường dẫn /rooms/{id}
  if (window.history && window.history.pushState) {
    window.history.pushState(null, "", `/rooms/${roomId}`);
  }

  // Hiển thị Skeleton Loader
  renderRoomDetailSkeleton();
  window.scrollTo({ top: 0, behavior: "smooth" });

  try {
    const [detailRes, reviewsRes, similarRes] = await Promise.all([
      apiFetch(`/api/rooms/${roomId}`),
      apiFetch(`/api/rooms/${roomId}/reviews`).catch(() => ({ reviews: [] })),
      apiFetch(`/api/rooms/${roomId}/similar`).catch(() => ({ rooms: [] })),
    ]);

    currentRoomData = detailRes;
    state.selectedRoom = detailRes;

    const r = detailRes.room;
    const slots = detailRes.slots || [];
    const grid = detailRes.grid || { dates: [], matrix: {} };
    const reviews = reviewsRes.reviews || [];
    const similarRooms = similarRes.rooms || [];

    // Thiết lập số khách mặc định theo capacity (tối thiểu 1, mặc định 2 nếu capacity >= 2)
    const maxCap = parseInt(r.capacity) || 2;
    currentGuestCount = Math.min(2, maxCap);
    currentSelectedDate = new Date().toISOString().split("T")[0];
    currentSelectedSlotCode = "K1";
    currentStayType = "slot";

    // Render toàn bộ UI màn hình
    renderRoomDetailContent(r, slots, grid, reviews, similarRooms);

  } catch (err) {
    console.error("Lỗi khi tải chi tiết phòng:", err);
    renderRoomDetailError(roomId, err.message);
  }
}

// =============================================================
// 2. RENDER GIAO DIỆN CHÍNH
// =============================================================
function renderRoomDetailContent(r, slots, grid, reviews, similarRooms) {
  const container = document.getElementById("view-room-detail");
  if (!container) return;

  const branchInfo = BRANCH_LOCATIONS[r.branch_id] || {
    address: `${r.branch_name}, TP.HCM`,
    shortAddr: r.branch_name,
    mapsQuery: `${r.branch_name}, TP Hồ Chí Minh`,
    phone: "0909 000 001",
  };

  const images = (r.images && r.images.length > 0) ? r.images : [];
  currentLightboxImages = images;
  currentRoomImages = images;
  currentGalleryIndex = 0;

  // Lấy giá thấp nhất để hiển thị headline
  const minPrice = slots.reduce((min, s) => (s.price && s.price < min ? s.price : min), (slots[0]?.price || 150000));
  const overnightSlot = slots.find(s => s.khung_code === "QD");
  const overnightPrice = overnightSlot?.price || minPrice;

  // Tách tiện nghi
  const amenitiesList = Array.isArray(r.amenities)
    ? r.amenities
    : (typeof r.amenities === "string" ? r.amenities.split("|").map(a => a.trim()).filter(Boolean) : []);

  // Tính rating tổng hợp
  const reviewCount = reviews.length;
  let avgRating = "4.8";
  if (reviewCount > 0) {
    const sum = reviews.reduce((acc, rv) => acc + (parseFloat(rv.rating) || 5), 0);
    avgRating = (sum / reviewCount).toFixed(1);
  }

  container.innerHTML = `
    <div class="rd-wrapper">
      
      <!-- BREADCRUMB VÀ NÚT QUAY LẠI -->
      <div class="rd-topbar">
        <button class="rd-back-btn" onclick="handleBackToRooms()" title="Quay lại danh sách phòng">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="19" y1="12" x2="5" y2="12"></line>
            <polyline points="12 19 5 12 12 5"></polyline>
          </svg>
          <span>Quay lại danh sách phòng</span>
        </button>

        <nav class="rd-breadcrumb">
          <a href="#" onclick="navigateTo('home'); return false;">Trang chủ</a>
          <span class="rd-breadcrumb-sep">/</span>
          <a href="#" onclick="navigateTo('home'); return false;">Phòng</a>
          <span class="rd-breadcrumb-sep">/</span>
          <span class="rd-breadcrumb-current">${r.room_name}</span>
        </nav>
      </div>

      <!-- TIÊU ĐỀ PHÒNG VÀ THÔNG TIN HEADER (ĐÃ BỎ CHỨC NĂNG CHIA SẺ) -->
      <div class="rd-header-section">
        <div class="rd-header-main">
          <div class="rd-room-code-tag">${r.room_id} - ${r.room_type}</div>
          <h1 class="rd-room-title">${r.room_name}</h1>
          <div class="rd-header-meta">
            <span class="rd-meta-item rd-meta-location">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>
              ${branchInfo.address}
            </span>
            <span class="rd-meta-item rd-meta-rating">
              <span style="color:#d97706; font-size:14px;">★</span> <b>${avgRating}</b> <span class="rd-meta-reviews">(${reviewCount > 0 ? `${reviewCount} đánh giá` : "Mới"})</span>
            </span>
            <span class="rd-meta-item rd-meta-concept">
              ${r.concept_name || r.concept || "Phong cách Cozy"}
            </span>
          </div>
        </div>
      </div>

      <!-- GALLERY ẢNH PHÒNG (AIRBNB / SENSTAY STYLE) -->
      <div class="rd-gallery-container" id="rd-gallery-container">
        ${renderGalleryHtml(images, r.room_name)}
      </div>

      <!-- BỐ CỤC 2 CỘT: NỘI DUNG TRÁI (66%) VÀ STICKY BOOKING CARD PHẢI (34%) -->
      <div class="rd-main-grid">
        
        <!-- CỘT TRÁI -->
        <div class="rd-col-left">

          <!-- HÀNG THÔNG SỐ NHANH CỦA PHÒNG -->
          <div class="rd-quick-specs">
            <div class="rd-spec-pill">
              <span class="rd-spec-icon"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg></span>
              <div>
                <div class="rd-spec-label">Sức chứa</div>
                <div class="rd-spec-val">Tối đa ${r.capacity} khách</div>
              </div>
            </div>
            <div class="rd-spec-pill">
              <span class="rd-spec-icon"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2 4v16"></path><path d="M2 8h18a2 2 0 0 1 2 2v10"></path><path d="M2 17h20"></path><path d="M6 8V6a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2v2"></path></svg></span>
              <div>
                <div class="rd-spec-label">Giường ngủ</div>
                <div class="rd-spec-val">${r.bed_type || "1 giường đôi"}</div>
              </div>
            </div>
            <div class="rd-spec-pill">
              <span class="rd-spec-icon"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-3"></path><path d="M3 10h18"></path><path d="M10 3v18"></path></svg></span>
              <div>
                <div class="rd-spec-label">Diện tích</div>
                <div class="rd-spec-val">${r.area || 25} m²</div>
              </div>
            </div>
            <div class="rd-spec-pill">
              <span class="rd-spec-icon"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21V5a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v16"></path><path d="M13 21V9a1 1 0 0 1 1-1h4a2 2 0 0 1 2 2v11"></path><circle cx="9" cy="12" r="0.8" fill="currentColor" stroke="none"></circle></svg></span>
              <div>
                <div class="rd-spec-label">Hạng phòng</div>
                <div class="rd-spec-val">${r.room_type}</div>
              </div>
            </div>
          </div>

          <div class="rd-divider"></div>

          <!-- SECTION: GIỚI THIỆU PHÒNG -->
          <section class="rd-section">
            <h2 class="rd-section-title">Giới thiệu về phòng</h2>
            <div class="rd-description-box" id="rd-description-box">
              <p class="rd-description-text" id="rd-description-text">${r.description || "Không gian homestay ấm cúng, thiết kế tối giản, tiện nghi và sạch sẽ."}</p>
            </div>
            <button class="rd-expand-btn" id="rd-desc-expand-btn" onclick="toggleDescriptionExpand()" style="display:none;">
              <span>Xem thêm</span>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"></polyline></svg>
            </button>
          </section>

          <div class="rd-divider"></div>

          <!-- SECTION: TIỆN NGHI PHÒNG -->
          <section class="rd-section">
            <div class="rd-section-header-flex">
              <div>
                <h2 class="rd-section-title">Nơi này có những gì cho bạn</h2>
                <p class="rd-section-sub">Trang bị tiện ích đồng bộ tiêu chuẩn chuỗi CozyHome</p>
              </div>
              ${amenitiesList.length > 8 ? `
                <button class="btn btn-outline btn-sm rd-view-all-amenities-btn" onclick="openAmenitiesModal()">
                  Xem tất cả ${amenitiesList.length} tiện nghi
                </button>
              ` : ""}
            </div>

            <div class="rd-amenities-grid">
              ${amenitiesList.slice(0, 8).map(amenity => `
                <div class="rd-amenity-item">
                  <span class="rd-amenity-icon">${getAmenityIcon(amenity)}</span>
                  <span class="rd-amenity-name">${amenity}</span>
                </div>
              `).join("")}
            </div>

            ${amenitiesList.length > 8 ? `
              <div style="margin-top: 16px;">
                <button class="btn btn-outline rd-btn-amenities-mobile" onclick="openAmenitiesModal()">
                  Xem tất cả ${amenitiesList.length} tiện nghi →
                </button>
              </div>
            ` : ""}
          </section>

          <div class="rd-divider"></div>

          <!-- SECTION: BẢNG GIÁ PHÒNG -->
          <section class="rd-section">
            <h2 class="rd-section-title">Bảng giá phòng và khung giờ lưu trú</h2>
            <p class="rd-section-sub">Áp dụng cho các khung giờ luân phiên CozyHome (giúp giãn cách lịch dọn buồng phòng)</p>

            <div class="rd-pricing-table-wrap">
              <table class="rd-pricing-table">
                <thead>
                  <tr>
                    <th>Khung giờ</th>
                    <th>Mức giá niêm yết</th>
                    <th>Trạng thái</th>
                  </tr>
                </thead>
                <tbody id="rd-pricing-table-body">
                  ${renderPricingTableRows(slots, grid, currentSelectedDate)}
                </tbody>
              </table>
            </div>

            <!-- Ma trận lịch 15 ngày tiếp theo -->
            <div class="rd-availability-box">
              <div class="rd-availability-header">
                <div>
                  <div style="display:flex; align-items:center; gap:8px;">
                    <h4 style="margin:0; font-size:15px; color:var(--cozy-dark);">Lịch trống 15 ngày tiếp theo</h4>
                    <span style="font-size:11px; padding:2px 8px; border-radius:12px; background:#e0f2fe; color:#0369a1; font-weight:700;">Hỗ trợ Đặt sớm -10%</span>
                  </div>
                  <div style="font-size:12px; color:var(--text-muted); margin-top:2px;">Cuộn ngang để xem đủ 15 ngày — chọn ngày từ 7 ngày trở lên để áp dụng mã EARLYBIRD10</div>
                </div>
                <div class="rd-legend-strip">
                  <span class="rd-legend-item"><span class="rd-legend-dot avail"></span> Còn trống</span>
                  <span class="rd-legend-item"><span class="rd-legend-dot selected"></span> Đang chọn</span>
                  <span class="rd-legend-item"><span class="rd-legend-dot booked"></span> Đã đặt</span>
                </div>
              </div>
              <div class="rd-grid-table-container" id="rd-grid-table-container">
                ${renderCalendarGridHtml(grid)}
              </div>
            </div>
          </section>

          <div class="rd-divider"></div>

          <!-- SECTION: VỊ TRÍ HOMESTAY -->
          <section class="rd-section">
            <h2 class="rd-section-title">Vị trí homestay</h2>
            <p class="rd-section-sub">Tọa lạc tại vị trí trung tâm, thuận tiện kết nối và di chuyển</p>

            <div class="rd-location-card">
              <div class="rd-location-icon-box"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg></div>
              <div class="rd-location-text">
                <div class="rd-location-branch">${r.branch_name}</div>
                <div class="rd-location-address">${branchInfo.address}</div>
                <div class="rd-location-phone">Hotline hỗ trợ nhận phòng: <b>${branchInfo.phone}</b></div>
              </div>
              <a href="https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(branchInfo.mapsQuery)}"
                 target="_blank"
                 rel="noopener noreferrer"
                 class="btn btn-outline rd-btn-maps">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"></polygon><line x1="8" y1="2" x2="8" y2="18"></line><line x1="16" y1="6" x2="16" y2="22"></line></svg>
                <span>Xem trên Google Maps</span>
              </a>
            </div>
          </section>

          <div class="rd-divider"></div>

          <!-- SECTION: QUY ĐỊNH VÀ CHÍNH SÁCH -->
          <section class="rd-section">
            <h2 class="rd-section-title">Quy định và Chính sách lưu trú</h2>
            <p class="rd-section-sub">Các quy chuẩn cốt lõi đảm bảo trải nghiệm nghỉ dưỡng tốt nhất tại CozyHome</p>

            <div class="rd-policies-grid">
              <!-- Chính sách 1: Check-in / Giờ nhận trả -->
              <div class="rd-policy-card">
                <div class="rd-policy-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg></div>
                <div class="rd-policy-content">
                  <h4>Thời gian nhận và trả phòng</h4>
                  <p>Check-in đúng giờ bắt đầu của khung giờ đã đặt. Vui lòng check-out đúng giờ để buồng phòng kịp khử khuẩn.</p>
                </div>
              </div>

              <!-- Chính sách 2: Hủy phòng và Hoàn tiền -->
              <div class="rd-policy-card">
                <div class="rd-policy-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg></div>
                <div class="rd-policy-content">
                  <h4>Hủy phòng và Hoàn tiền</h4>
                  <p>Hủy trước ≥ 24 giờ: <b>hoàn 100%</b>; từ 12h đến dưới 24h: <b>hoàn 50%</b>; dưới 12h: <b>không hoàn tiền</b>. Tiền hoàn về trong 3–15 ngày làm việc.</p>
                </div>
              </div>

              <!-- Chính sách 3: Giữ chỗ 10 phút -->
              <div class="rd-policy-card">
                <div class="rd-policy-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg></div>
                <div class="rd-policy-content">
                  <h4>Thời gian giữ chỗ</h4>
                  <p>Mỗi lượt đặt phòng có <b>10 phút giữ chỗ tạm thời</b> để quý khách quét mã VietQR MBBank hoàn tất thanh toán.</p>
                </div>
              </div>

              <!-- Chính sách 4: Gia hạn thêm giờ -->
              <div class="rd-policy-card">
                <div class="rd-policy-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg></div>
                <div class="rd-policy-content">
                  <h4>Gia hạn thêm giờ</h4>
                  <p>Khách đang lưu trú được gia hạn sang khung giờ kế tiếp nếu phòng còn trống. Không phụ thu phí dọn dẹp giữa 2 khung.</p>
                </div>
              </div>

              <!-- Chính sách 5: Vệ sinh và Không hút thuốc -->
              <div class="rd-policy-card">
                <div class="rd-policy-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"></line></svg></div>
                <div class="rd-policy-content">
                  <h4>Quy chuẩn buồng phòng</h4>
                  <p>Toàn bộ phòng CozyHome là không gian 100% không hút thuốc. Khử trùng ga gối và tiện nghi trước mỗi lượt nhận phòng.</p>
                </div>
              </div>

              <!-- Chính sách 6: Sức chứa và Phụ thu -->
              <div class="rd-policy-card">
                <div class="rd-policy-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle></svg></div>
                <div class="rd-policy-content">
                  <h4>Sức chứa tiêu chuẩn</h4>
                  <p>Phòng này phù hợp tối đa <b>${r.capacity} khách</b>. Vui lòng không lưu trú vượt quá sức chứa để đảm bảo an toàn PCCC.</p>
                </div>
              </div>
            </div>
          </section>

        </div>

        <!-- CỘT PHẢI: STICKY BOOKING CARD -->
        <div class="rd-col-right">
          <div class="rd-booking-card" id="rd-booking-card">
            ${renderBookingCardHtml(r, slots, grid, minPrice, overnightPrice)}
          </div>
        </div>

      </div>

      <!-- SECTION: CÓ THỂ BẠN CŨNG THÍCH (PHÒNG TƯƠNG TỰ) -->
      ${similarRooms.length > 0 ? `
        <div class="rd-divider" style="margin-top: 48px;"></div>
        <section class="rd-section rd-similar-section">
          <div class="rd-section-header-flex">
            <div>
              <h2 class="rd-section-title">Có thể bạn cũng thích</h2>
              <p class="rd-section-sub">Các phòng cùng chi nhánh hoặc phân khúc tương đương</p>
            </div>
          </div>
          <div class="rd-similar-grid">
            ${similarRooms.map(sim => renderSimilarRoomCard(sim)).join("")}
          </div>
        </section>
      ` : ""}

      <!-- SECTION: ĐÁNH GIÁ TỪ KHÁCH HÀNG -->
      <div class="rd-divider" style="margin-top: 48px;"></div>
      <section class="rd-section rd-reviews-section">
        <div class="rd-reviews-header">
          <div class="rd-reviews-headline">
            <span style="font-size:24px; color:#d97706;">★</span>
            <span class="rd-reviews-score">${avgRating}</span>
            <span class="rd-reviews-count">(${reviewCount > 0 ? `${reviewCount} lượt đánh giá từ khách thực tế` : "Chưa có đánh giá nào cho phòng này"})</span>
          </div>
          <div style="font-size:13px; color:var(--text-muted);">Chỉ khách đã lưu trú hoàn tất mới được gửi đánh giá.</div>
        </div>

        ${reviewCount === 0 ? `
          <div class="rd-empty-reviews">
            
            <h4>Chưa có đánh giá nào cho phòng này</h4>
            <p style="color:var(--text-muted); font-size:13.5px; max-width:440px; margin:0 auto;">
              Hãy là một trong những vị khách đầu tiên trải nghiệm không gian ấm áp này và để lại cảm nhận sau chuyến đi nhé!
            </p>
          </div>
        ` : `
          <div class="rd-reviews-grid">
            ${reviews.slice(0, 4).map(rv => `
              <div class="rd-review-card">
                <div class="rd-review-user">
                  <div class="rd-review-avatar">${(rv.user_name || "K")[0].toUpperCase()}</div>
                  <div>
                    <div class="rd-review-name">${rv.user_name || "Khách hàng CozyHome"}</div>
                    <div class="rd-review-date">${rv.created_at ? rv.created_at.slice(0, 10) : "Gần đây"}</div>
                  </div>
                </div>
                <div class="rd-review-stars">
                  ${"★".repeat(rv.rating || 5)}
                </div>
                <p class="rd-review-content">${rv.content || "Phòng sạch sẽ, không gian thoáng mát và rất yên tĩnh. Sẽ quay lại!"}</p>
              </div>
            `).join("")}
          </div>
        `}
      </section>

    </div>

    <!-- MOBILE STICKY BOTTOM BOOKING BAR -->
    <div class="rd-mobile-bar" id="rd-mobile-bar">
      <div class="rd-mobile-bar-info">
        <div class="rd-mobile-bar-price">
          <span class="rd-mobile-bar-amount">${formatMoney(minPrice)}</span>
          <span class="rd-mobile-bar-unit">/ khung</span>
        </div>
        <div class="rd-mobile-bar-sub">★ ${avgRating} - ${r.room_name}</div>
      </div>
      <button class="btn btn-primary rd-mobile-bar-btn" onclick="scrollToBookingCard()">
        Đặt phòng ngay
      </button>
    </div>

    <!-- LIGHTBOX MODAL: XEM TOÀN BỘ ẢNH -->
    <div id="rd-lightbox-modal" class="rd-lightbox-overlay" onclick="handleLightboxBackdropClick(event)">
      <div class="rd-lightbox-container">
        <div class="rd-lightbox-header">
          <div class="rd-lightbox-counter" id="rd-lightbox-counter">1 / 1</div>
          <div class="rd-lightbox-room-name">${r.room_name}</div>
          <button class="rd-lightbox-close" onclick="closeLightbox()" title="Đóng (Esc)">✕</button>
        </div>

        <div class="rd-lightbox-stage">
          <button class="rd-lightbox-nav prev" onclick="prevLightboxPhoto()" title="Ảnh trước (←)">‹</button>
          <div class="rd-lightbox-image-wrap">
            <img id="rd-lightbox-img" src="" alt="${r.room_name}" />
          </div>
          <button class="rd-lightbox-nav next" onclick="nextLightboxPhoto()" title="Ảnh sau (→)">›</button>
        </div>

        <div class="rd-lightbox-footer" id="rd-lightbox-thumbs">
          <!-- Thumbnails injected by JS -->
        </div>
      </div>
    </div>

    <!-- MODAL: XEM TẤT CẢ TIỆN NGHI -->
    <div id="rd-amenities-modal" class="modal-overlay">
      <div class="modal-dialog" style="max-width: 580px;">
        <div class="modal-header">
          <h3 class="modal-title">Tiện nghi tại ${r.room_name}</h3>
          <button class="modal-close-btn" onclick="closeAmenitiesModal()">&times;</button>
        </div>
        <div class="modal-body" style="padding: 24px;">
          <div class="rd-all-amenities-list">
            ${amenitiesList.map(a => `
              <div class="rd-all-amenity-item">
                <span class="rd-all-amenity-icon">${getAmenityIcon(a)}</span>
                <span class="rd-all-amenity-text">${a}</span>
              </div>
            `).join("")}
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-outline" onclick="closeAmenitiesModal()">Đóng</button>
        </div>
      </div>
    </div>
  `;

  // Kiểm tra mô tả có cần hiển thị nút "Xem thêm" không
  checkDescriptionOverflow();

  // Khởi tạo phím tắt cho Lightbox
  initLightboxKeyboard();
}

// =============================================================
// 3. RENDER GALLERY KHUNG HÌNH CHÍNH VÀ FILMSTRIP (ĐẸP VÀ THẤY TRỌN VẸN TOÀN BỘ)
// =============================================================
function renderGalleryHtml(images, roomName) {
  if (!images || images.length === 0) {
    return `
      <div class="rd-gallery-empty">
        <div style="margin-bottom: 12px; color:var(--cozy-primary);"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M2 4v16"></path><path d="M2 8h18a2 2 0 0 1 2 2v10"></path><path d="M2 17h20"></path><path d="M6 8v9"></path></svg></div>
        <div style="font-size: 16px; font-weight: 700; color: var(--cozy-dark);">Hình ảnh CozyHome</div>
        <div style="font-size: 13px; color: var(--text-muted);">Không gian được giữ gìn sạch sẽ và chuẩn bị chu đáo trước giờ check-in</div>
      </div>
    `;
  }

  const count = images.length;
  currentRoomImages = images;
  currentGalleryIndex = 0;

  return `
    <div class="rd-gallery-showcase">
      <!-- KHUNG HÌNH CHÍNH (STAGE) - HIỂN THỊ TRỌN VẸN 100% KHÔNG BỊ CẮT XÉN -->
      <div class="rd-stage-wrapper" onclick="openLightbox(currentGalleryIndex)" title="Nhấn để phóng to toàn màn hình">
        <!-- Nền mờ nghệ thuật ambient tạo chiều sâu sang trọng, ấm áp -->
        <img id="rd-stage-backdrop-img" class="rd-stage-backdrop" src="${images[0]}" alt="" aria-hidden="true" />
        <div class="rd-stage-overlay"></div>

        <!-- Khung chứa ảnh chính: object-fit contain giữ trọn vẹn toàn bộ ảnh -->
        <div class="rd-stage-img-container">
          <img id="rd-main-stage-img" class="rd-stage-main-img" src="${images[0]}" alt="${roomName}" loading="eager" />
        </div>

        <!-- Nút lướt ảnh Trước / Sau trên khung hình -->
        ${count > 1 ? `
          <button class="rd-stage-nav-btn rd-stage-prev" onclick="event.stopPropagation(); stepGalleryPhoto(-1);" title="Ảnh trước" aria-label="Ảnh trước">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="15 18 9 12 15 6"></polyline></svg>
          </button>
          <button class="rd-stage-nav-btn rd-stage-next" onclick="event.stopPropagation(); stepGalleryPhoto(1);" title="Ảnh tiếp theo" aria-label="Ảnh tiếp theo">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"></polyline></svg>
          </button>
        ` : ''}

        <!-- Nhóm thông tin và Phóng to trên ảnh -->
        <div class="rd-stage-badge-group">
          <span class="rd-stage-counter-pill" id="rd-stage-counter">
            1 / ${count}
          </span>
          <button class="rd-stage-zoom-pill" onclick="event.stopPropagation(); openLightbox(currentGalleryIndex);" title="Phóng to xem chi tiết">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M15 3h6v6"></path><path d="M9 21H3v-6"></path><path d="M21 3l-7 7"></path><path d="M3 21l7-7"></path></svg>
            <span>Phóng to</span>
          </button>
        </div>
      </div>

      <!-- DẢI ẢNH THUMBNAIL (FILMSTRIP) DỄ DÀNG CHỌN TẤT CẢ GÓC PHÒNG -->
      ${count > 1 ? `
        <div class="rd-gallery-filmstrip" id="rd-gallery-filmstrip">
          ${images.map((src, idx) => `
            <button class="rd-filmstrip-thumb ${idx === 0 ? 'active' : ''}"
                    onclick="selectGalleryPhoto(${idx})"
                    title="Xem góc phòng ${idx + 1}"
                    data-index="${idx}">
              <img src="${src}" alt="${roomName} ${idx + 1}" loading="lazy" />
            </button>
          `).join('')}
        </div>
      ` : ''}
    </div>
  `;
}

function selectGalleryPhoto(index) {
  if (!currentRoomImages || currentRoomImages.length === 0) return;
  currentGalleryIndex = Math.max(0, Math.min(index, currentRoomImages.length - 1));

  const mainImg = document.getElementById("rd-main-stage-img");
  const backdropImg = document.getElementById("rd-stage-backdrop-img");
  const counter = document.getElementById("rd-stage-counter");

  if (mainImg) {
    mainImg.style.opacity = "0.7";
    mainImg.src = currentRoomImages[currentGalleryIndex];
    mainImg.onload = () => { mainImg.style.opacity = "1"; };
  }
  if (backdropImg) {
    backdropImg.src = currentRoomImages[currentGalleryIndex];
  }
  if (counter) {
    counter.innerHTML = `${currentGalleryIndex + 1} / ${currentRoomImages.length}`;
  }

  // Cập nhật trạng thái active cho thumbnail
  const thumbs = document.querySelectorAll(".rd-filmstrip-thumb");
  thumbs.forEach((thumb, idx) => {
    if (idx === currentGalleryIndex) {
      thumb.classList.add("active");
      thumb.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
    } else {
      thumb.classList.remove("active");
    }
  });
}

function stepGalleryPhoto(delta) {
  if (!currentRoomImages || currentRoomImages.length <= 1) return;
  const nextIdx = (currentGalleryIndex + delta + currentRoomImages.length) % currentRoomImages.length;
  selectGalleryPhoto(nextIdx);
}

// =============================================================
// 4. RENDER BOOKING CARD (STICKY DESKTOP & INTERACTION)
// =============================================================
function renderBookingCardHtml(r, slots, grid, minPrice, overnightPrice) {
  const today = new Date().toISOString().split("T")[0];
  const isOvernight = (currentStayType === "overnight");

  // Tìm slot hiện tại
  const currentSlot = slots.find(s => s.khung_code === currentSelectedSlotCode) || slots[0];
  const overnightSlot = slots.find(s => s.khung_code === "QD") || slots[slots.length - 1];

  const activePrice = isOvernight ? (overnightSlot?.price || overnightPrice) : (currentSlot?.price || minPrice);
  const maxCap = parseInt(r.capacity) || 2;

  return `
    <!-- CARD PRICE HEAD -->
    <div class="rd-bc-price-header">
      <div>
        <span class="rd-bc-price-from">Từ</span>
        <span class="rd-bc-price-value" id="rd-bc-price-display">${formatMoney(activePrice)}</span>
        <span class="rd-bc-price-unit" id="rd-bc-unit-display">/ ${isOvernight ? 'đêm' : 'khung giờ'}</span>
      </div>
      <div class="rd-bc-verified-badge">Giá niêm yết</div>
    </div>

    <!-- DẢI GỢI Ý MÃ ƯU ĐÃI VÀ VOUCHER -->
    <div class="rd-bc-promo-strip" onclick="openPromotionsModal()" title="Nhấn để xem các chương trình khuyến mãi và mã giảm giá">
      <div class="rd-bc-promo-strip-icon">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="20 12 20 22 4 22 4 12"></polyline>
          <rect x="2" y="7" width="20" height="5"></rect>
          <line x1="12" y1="22" x2="12" y2="7"></line>
          <path d="M12 7H7.5a2.5 2.5 0 0 1 0-5C11 2 12 7 12 7z"></path>
          <path d="M12 7h4.5a2.5 2.5 0 0 0 0-5C13 2 12 7 12 7z"></path>
        </svg>
      </div>
      <div class="rd-bc-promo-strip-content">
        <div class="rd-bc-promo-strip-title">Ưu đãi giảm đến 15%</div>
        <div class="rd-bc-promo-strip-sub">Đặt sớm -10%, Qua đêm -15%, Thành viên -30K</div>
      </div>
      <span class="rd-bc-promo-strip-arrow">›</span>
    </div>

    <!-- SEGMENTED STAY TYPE TOGGLE: [ Theo giờ ] [ Qua đêm ] -->
    <div class="rd-stay-segmented">
      <button class="rd-stay-seg-btn ${!isOvernight ? 'active' : ''}" onclick="switchStayType('slot')">
        Theo giờ (3h)
      </button>
      <button class="rd-stay-seg-btn ${isOvernight ? 'active' : ''}" onclick="switchStayType('overnight')">
        Qua đêm
      </button>
    </div>

    <!-- FORM NỘI DUNG TÙY CHỈNH THEO LOẠI LƯU TRÚ -->
    <div class="rd-bc-form-fields">

      <!-- NGÀY SỬ DỤNG -->
      <div class="rd-form-field">
        <label class="rd-field-label">Ngày nhận phòng</label>
        <input type="date"
               id="rd-bc-date"
               class="rd-field-input"
               value="${today}"
               min="${today}"
               onchange="handleBookingDateChange(this.value)" />
      </div>

      <!-- NẾU THEO GIỜ: CHỌN KHUNG GIỜ -->
      <div id="rd-bc-slot-wrap" style="display: ${!isOvernight ? 'block' : 'none'};">
        <div class="rd-form-field">
          <label class="rd-field-label">Khung giờ lưu trú</label>
          <select id="rd-bc-slot-select" class="rd-field-select" onchange="handleSlotSelectionChange(this.value)">
            ${slots.filter(s => s.khung_code !== "QD").map(s => `
              <option value="${s.khung_code}" ${s.khung_code === currentSelectedSlotCode ? 'selected' : ''}>
                ${s.label || `${s.start_time} – ${s.end_time}`}
              </option>
            `).join("")}
          </select>
        </div>
      </div>

      <!-- NẾU QUA ĐÊM: HIỂN THỊ THÔNG TIN QUA ĐÊM -->
      <div id="rd-bc-overnight-wrap" style="display: ${isOvernight ? 'block' : 'none'};">
        <div class="rd-overnight-info-box">
          <div style="font-weight:600; color:var(--cozy-dark); font-size:13px; margin-bottom:4px;">
            Khung lưu trú qua đêm
          </div>
          <div style="font-size:12.5px; color:var(--text-muted);">
            Nhận phòng: <b>${overnightSlot?.start_time || '20:00'}</b> - Trả phòng: <b>${(overnightSlot?.end_time || '08:30').replace('+1', '')}</b> hôm sau
          </div>
        </div>
      </div>

      <!-- CHỌN SỐ LƯỢNG KHÁCH (POPOVER CHUẨN UX) -->
      <div class="rd-form-field" style="position:relative;">
        <label class="rd-field-label">Số lượng khách</label>
        <button type="button" class="rd-guest-selector-btn" id="rd-guest-selector-btn" onclick="toggleGuestPopover()">
          <span id="rd-guest-display-text">${currentGuestCount} khách</span>
          <span class="rd-chevron">▾</span>
        </button>

        <!-- POPOVER DROPDOWN -->
        <div class="rd-guest-popover" id="rd-guest-popover">
          <div class="rd-guest-popover-row">
            <div>
              <div style="font-weight:600; font-size:14px; color:var(--cozy-dark);">Số khách</div>
            </div>
            <div class="rd-counter-group">
              <button type="button" class="rd-counter-btn" onclick="changeGuestCount(-1)" id="rd-guest-minus-btn" ${currentGuestCount <= 1 ? 'disabled' : ''}>−</button>
              <span class="rd-counter-val" id="rd-guest-counter-val">${currentGuestCount}</span>
              <button type="button" class="rd-counter-btn" onclick="changeGuestCount(1)" id="rd-guest-plus-btn" ${currentGuestCount >= maxCap ? 'disabled' : ''}>+</button>
            </div>
          </div>
          <div class="rd-guest-limit-note" id="rd-guest-limit-note">
            Phòng này phù hợp tối đa <b>${maxCap} khách</b>.
          </div>
        </div>
      </div>

    </div>

    <!-- BẢNG TẠM TÍNH CHI PHÍ -->
    <div class="rd-bc-breakdown">
      <div class="rd-bc-row">
        <span>Tạm tính lưu trú</span>
        <span id="rd-bc-subtotal">${formatMoney(activePrice)}</span>
      </div>
      <div class="rd-bc-row">
        <span>Phụ thu vệ sinh và tiện ích</span>
        <span style="color:var(--success); font-weight:600;">Miễn phí</span>
      </div>
      <div class="rd-bc-row total">
        <span>Tổng cộng thanh toán</span>
        <span class="rd-bc-total-val" id="rd-bc-total">${formatMoney(activePrice)}</span>
      </div>
    </div>

    <!-- TRẠNG THÁI KHẢ DỤNG / CẢNH BÁO -->
    <div id="rd-bc-avail-message" style="margin-bottom:12px;"></div>

    <!-- NÚT ĐẶT PHÒNG -->
    <button class="btn btn-primary rd-btn-book-now" id="rd-btn-submit-booking" onclick="handleBookFromRoomDetail()">
      Đặt phòng ngay
    </button>

    <div class="rd-bc-guarantee">
      Không trừ tiền ngay - Quét VietQR MBBank trong 10 phút
    </div>
  `;
}

// =============================================================
// 5. INTERACTION LOGIC CHO BOOKING CARD
// =============================================================
function switchStayType(type) {
  currentStayType = type;
  if (!currentRoomData) return;

  const r = currentRoomData.room;
  const slots = currentRoomData.slots || [];

  const overnightSlot = slots.find(s => s.khung_code === "QD");
  const slotSlot = slots.find(s => s.khung_code === currentSelectedSlotCode) || slots[0];

  const price = (type === "overnight") ? (overnightSlot?.price || 450000) : (slotSlot?.price || 150000);

  // Cập nhật giao diện tabs
  document.querySelectorAll(".rd-stay-seg-btn").forEach((btn, i) => {
    btn.classList.toggle("active", (type === "slot" && i === 0) || (type === "overnight" && i === 1));
  });

  // Toggle wrap inputs
  const slotWrap = document.getElementById("rd-bc-slot-wrap");
  const overnightWrap = document.getElementById("rd-bc-overnight-wrap");
  if (slotWrap) slotWrap.style.display = (type === "slot") ? "block" : "none";
  if (overnightWrap) overnightWrap.style.display = (type === "overnight") ? "block" : "none";

  // Cập nhật giá hiển thị
  const priceDisplay = document.getElementById("rd-bc-price-display");
  const unitDisplay = document.getElementById("rd-bc-unit-display");
  const subtotal = document.getElementById("rd-bc-subtotal");
  const total = document.getElementById("rd-bc-total");

  if (priceDisplay) priceDisplay.textContent = formatMoney(price);
  if (unitDisplay) unitDisplay.textContent = `/ ${type === "overnight" ? "đêm" : "khung giờ"}`;
  if (subtotal) subtotal.textContent = formatMoney(price);
  if (total) total.textContent = formatMoney(price);

  checkAvailabilityCurrentSelection();
  refreshCalendarGridUI();
}

function handleSlotSelectionChange(slotCode) {
  currentSelectedSlotCode = slotCode;
  if (!currentRoomData) return;

  const slots = currentRoomData.slots || [];
  const s = slots.find(x => x.khung_code === slotCode);
  if (!s) return;

  // Cập nhật giá
  const price = s.price;
  const priceDisplay = document.getElementById("rd-bc-price-display");
  const subtotal = document.getElementById("rd-bc-subtotal");
  const total = document.getElementById("rd-bc-total");
  if (priceDisplay) priceDisplay.textContent = formatMoney(price);
  if (subtotal) subtotal.textContent = formatMoney(price);
  if (total) total.textContent = formatMoney(price);

  checkAvailabilityCurrentSelection();
  refreshCalendarGridUI();
}

function handleBookingDateChange(dateVal) {
  currentSelectedDate = dateVal;
  checkAvailabilityCurrentSelection();
  refreshCalendarGridUI();
}

function handleQuickSelectFromCalendar(dateStr, slotCode) {
  currentSelectedDate = dateStr;
  const dateInput = document.getElementById("rd-bc-date");
  if (dateInput) {
    dateInput.value = dateStr;
  }

  if (slotCode === "QD") {
    switchStayType("overnight");
  } else {
    switchStayType("slot");
    const slotSelect = document.getElementById("rd-bc-slot-select");
    if (slotSelect) {
      slotSelect.value = slotCode;
      handleSlotSelectionChange(slotCode);
    }
  }

  checkAvailabilityCurrentSelection();
  refreshCalendarGridUI();

  const slotTitle = slotCode === "QD" ? "Qua đêm" : (slotCode === "K1" ? "Sáng" : (slotCode === "K2" ? "Chiều" : "Tối"));
  if (typeof showToast === "function") {
    showToast(`Đã chọn ngày ${dateStr} - Khung ${slotTitle}`, "info");
  }

  const bookingCard = document.querySelector(".rd-booking-card");
  if (bookingCard && window.innerWidth <= 992) {
    bookingCard.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

function refreshCalendarGridUI() {
  const container = document.getElementById("rd-grid-table-container");
  if (container && currentRoomData) {
    container.innerHTML = renderCalendarGridHtml(currentRoomData.grid);
  }
  refreshPricingTableUI();
}

// Kiểm tra lịch khả dụng thực tế của ngày và khung đã chọn
function checkAvailabilityCurrentSelection() {
  if (!currentRoomData) return;

  const r = currentRoomData.room;
  const grid = currentRoomData.grid || { dates: [], matrix: {} };
  const dateInput = document.getElementById("rd-bc-date");
  const selectedDate = dateInput?.value || new Date().toISOString().split("T")[0];
  const targetSlotCode = (currentStayType === "overnight") ? "QD" : currentSelectedSlotCode;

  const statusMsg = document.getElementById("rd-bc-avail-message");
  const bookBtn = document.getElementById("rd-btn-submit-booking");
  if (!statusMsg || !bookBtn) return;

  // 1. Kiểm tra trạng thái vật lý của phòng
  if (r.operational_status === "Bảo trì") {
    statusMsg.innerHTML = `<div class="rd-alert-unavailable">Phòng này hiện đang tạm ngưng nhận khách để bảo trì định kỳ.</div>`;
    bookBtn.disabled = true;
    return;
  }

  // 2. Kiểm tra ô ma trận lịch
  const cellStatus = grid.matrix?.[selectedDate]?.[targetSlotCode];
  const isBooked = (cellStatus === "BOOKED" || cellStatus === "UNAVAILABLE");

  if (isBooked) {
    statusMsg.innerHTML = `<div class="rd-alert-unavailable">Khung giờ này vào ngày ${selectedDate} đã có khách đặt. Vui lòng chọn khung giờ hoặc ngày khác.</div>`;
    bookBtn.disabled = true;
  } else {
    statusMsg.innerHTML = `<div class="rd-alert-available">✓ Khung giờ còn trống và sẵn sàng đón bạn!</div>`;
    bookBtn.disabled = false;
  }
}

// =============================================================
// 6. GUEST SELECTOR POPOVER
// =============================================================
function toggleGuestPopover() {
  const popover = document.getElementById("rd-guest-popover");
  if (popover) {
    popover.classList.toggle("active");
  }
}

function changeGuestCount(delta) {
  if (!currentRoomData) return;

  const maxCap = parseInt(currentRoomData.room.capacity) || 2;
  const nextVal = currentGuestCount + delta;

  if (nextVal < 1) return;
  if (nextVal > maxCap) {
    showToast(`Phòng này phù hợp tối đa ${maxCap} khách.`, "warning");
    return;
  }

  currentGuestCount = nextVal;

  const counterVal = document.getElementById("rd-guest-counter-val");
  const displayText = document.getElementById("rd-guest-display-text");
  const minusBtn = document.getElementById("rd-guest-minus-btn");
  const plusBtn = document.getElementById("rd-guest-plus-btn");

  if (counterVal) counterVal.textContent = currentGuestCount;
  if (displayText) displayText.textContent = `${currentGuestCount} khách`;
  if (minusBtn) minusBtn.disabled = (currentGuestCount <= 1);
  if (plusBtn) plusBtn.disabled = (currentGuestCount >= maxCap);
}

// Đóng popover khi click ra ngoài
document.addEventListener("click", (e) => {
  const popover = document.getElementById("rd-guest-popover");
  const btn = document.getElementById("rd-guest-selector-btn");
  if (popover && popover.classList.contains("active") && btn && !btn.contains(e.target) && !popover.contains(e.target)) {
    popover.classList.remove("active");
  }
});

// =============================================================
// 7. HANDLE ĐẶT PHÒNG: TÍCH HỢP CHẶT CHẼ VỚI LUỒNG COZYHOME
// =============================================================
function handleBookFromRoomDetail() {
  if (!currentRoomData) return;

  const r = currentRoomData.room;
  const slots = currentRoomData.slots || [];
  const dateInput = document.getElementById("rd-bc-date");
  const bookingDate = dateInput?.value || new Date().toISOString().split("T")[0];

  const targetSlotCode = (currentStayType === "overnight") ? "QD" : currentSelectedSlotCode;
  const s = slots.find(x => x.khung_code === targetSlotCode) || slots[0];

  const price = s.price;
  const startTime = s.start_time;
  const endTime = s.end_time;

  // Validate phòng bảo trì
  if (r.operational_status === "Bảo trì") {
    showToast("Phòng đang trong trạng thái bảo trì, không thể tạo đặt phòng.", "error");
    return;
  }

  // Chuyển tiếp tới hàm điều phối đặt phòng tập trung của CozyHome
  if (typeof handleBookRoomClick === "function") {
    handleBookRoomClick(r.room_id, bookingDate, targetSlotCode, price, startTime, endTime);
  } else if (typeof initiateBooking === "function") {
    initiateBooking(r.room_id, bookingDate, targetSlotCode, price, startTime, endTime);
  } else {
    showToast("Hệ thống đặt phòng đang bận, vui lòng thử lại.", "error");
  }
}

function scrollToBookingCard() {
  const card = document.getElementById("rd-booking-card");
  if (card) {
    card.scrollIntoView({ behavior: "smooth", block: "center" });
    card.classList.add("highlight-pulse");
    setTimeout(() => card.classList.remove("highlight-pulse"), 1200);
  }
}

function handleBackToRooms() {
  if (typeof navigateTo === "function") {
    navigateTo("home");
  } else {
    window.location.href = "/";
  }
}

function handleShareRoom(name) {
  if (navigator.share) {
    navigator.share({
      title: `${name} — CozyHome`,
      url: window.location.href,
    }).catch(() => {});
  } else {
    navigator.clipboard.writeText(window.location.href);
    showToast("Đã sao chép liên kết phòng vào bộ nhớ tạm!", "success");
  }
}

// =============================================================
// 8. DESCRIPTION EXPAND / COLLAPSE
// =============================================================
function checkDescriptionOverflow() {
  const text = document.getElementById("rd-description-text");
  const btn = document.getElementById("rd-desc-expand-btn");
  if (text && btn) {
    if (text.scrollHeight > 100) {
      btn.style.display = "inline-flex";
    }
  }
}

function toggleDescriptionExpand() {
  const text = document.getElementById("rd-description-text");
  const btn = document.getElementById("rd-desc-expand-btn");
  if (!text || !btn) return;

  const isExpanded = text.classList.contains("expanded");
  if (isExpanded) {
    text.classList.remove("expanded");
    btn.innerHTML = `<span>Xem thêm</span> <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"></polyline></svg>`;
  } else {
    text.classList.add("expanded");
    btn.innerHTML = `<span>Thu gọn</span> <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="18 15 12 9 6 15"></polyline></svg>`;
  }
}

// =============================================================
// 9. LIGHTBOX MODAL TOÀN MÀN HÌNH
// =============================================================
function openLightbox(index = 0) {
  if (!currentLightboxImages || currentLightboxImages.length === 0) return;

  currentLightboxIndex = Math.max(0, Math.min(index, currentLightboxImages.length - 1));

  const modal = document.getElementById("rd-lightbox-modal");
  if (!modal) return;

  modal.classList.add("active");
  document.body.style.overflow = "hidden"; // chặn scroll nền

  updateLightboxView();
}

function closeLightbox() {
  const modal = document.getElementById("rd-lightbox-modal");
  if (modal) {
    modal.classList.remove("active");
    document.body.style.overflow = "";
  }
  // Đồng bộ lại góc ảnh trên stage theo ảnh vừa xem trong Lightbox
  if (typeof selectGalleryPhoto === "function") {
    selectGalleryPhoto(currentLightboxIndex);
  }
}

function updateLightboxView() {
  const img = document.getElementById("rd-lightbox-img");
  const counter = document.getElementById("rd-lightbox-counter");
  const thumbsContainer = document.getElementById("rd-lightbox-thumbs");

  if (img) {
    img.src = currentLightboxImages[currentLightboxIndex];
  }
  if (counter) {
    counter.textContent = `${currentLightboxIndex + 1} / ${currentLightboxImages.length}`;
  }

  // Render thumbnails bên dưới lightbox
  if (thumbsContainer) {
    thumbsContainer.innerHTML = currentLightboxImages.map((src, i) => `
      <img src="${src}"
           class="rd-lightbox-thumb ${i === currentLightboxIndex ? 'active' : ''}"
           alt="Ảnh ${i + 1}"
           onclick="openLightbox(${i})" />
    `).join("");
  }
}

function nextLightboxPhoto() {
  if (currentLightboxImages.length <= 1) return;
  currentLightboxIndex = (currentLightboxIndex + 1) % currentLightboxImages.length;
  updateLightboxView();
}

function prevLightboxPhoto() {
  if (currentLightboxImages.length <= 1) return;
  currentLightboxIndex = (currentLightboxIndex - 1 + currentLightboxImages.length) % currentLightboxImages.length;
  updateLightboxView();
}

function handleLightboxBackdropClick(e) {
  if (e.target.id === "rd-lightbox-modal" || e.target.classList.contains("rd-lightbox-stage")) {
    closeLightbox();
  }
}

function initLightboxKeyboard() {
  document.addEventListener("keydown", (e) => {
    const modal = document.getElementById("rd-lightbox-modal");
    if (!modal || !modal.classList.contains("active")) return;

    if (e.key === "Escape") closeLightbox();
    else if (e.key === "ArrowRight") nextLightboxPhoto();
    else if (e.key === "ArrowLeft") prevLightboxPhoto();
  });
}

// =============================================================
// 10. MODAL TIỆN NGHI
// =============================================================
function openAmenitiesModal() {
  const modal = document.getElementById("rd-amenities-modal");
  if (modal) modal.classList.add("active");
}

function closeAmenitiesModal() {
  const modal = document.getElementById("rd-amenities-modal");
  if (modal) modal.classList.remove("active");
}

// =============================================================
// 11. SKELETON LOADER VÀ ERROR STATES
// =============================================================
function renderRoomDetailSkeleton() {
  const container = document.getElementById("view-room-detail");
  if (!container) return;

  container.innerHTML = `
    <div class="rd-wrapper">
      <div class="rd-topbar">
        <div class="rd-skeleton" style="width: 180px; height: 32px; border-radius: 8px;"></div>
      </div>
      <div class="rd-header-section" style="margin-bottom: 20px;">
        <div class="rd-skeleton" style="width: 320px; height: 36px; border-radius: 8px; margin-bottom: 8px;"></div>
        <div class="rd-skeleton" style="width: 240px; height: 20px; border-radius: 6px;"></div>
      </div>
      <div class="rd-skeleton" style="width: 100%; height: 420px; border-radius: 16px; margin-bottom: 32px;"></div>
      <div class="rd-main-grid">
        <div class="rd-col-left">
          <div class="rd-skeleton" style="width: 100%; height: 80px; border-radius: 12px; margin-bottom: 20px;"></div>
          <div class="rd-skeleton" style="width: 100%; height: 160px; border-radius: 12px; margin-bottom: 20px;"></div>
          <div class="rd-skeleton" style="width: 100%; height: 200px; border-radius: 12px;"></div>
        </div>
        <div class="rd-col-right">
          <div class="rd-skeleton" style="width: 100%; height: 380px; border-radius: 16px;"></div>
        </div>
      </div>
    </div>
  `;
}

function renderRoomDetailError(roomId, errorMsg) {
  const container = document.getElementById("view-room-detail");
  if (!container) return;

  container.innerHTML = `
    <div class="rd-wrapper" style="text-align: center; padding: 72px 20px;">
      <div style="margin-bottom: 16px; color:var(--cozy-primary);"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M2 4v16"></path><path d="M2 8h18a2 2 0 0 1 2 2v10"></path><path d="M2 17h20"></path><path d="M6 8v9"></path></svg></div>
      <h2 style="color: var(--cozy-dark); margin-bottom: 8px;">Không tìm thấy thông tin phòng</h2>
      <p style="color: var(--text-muted); font-size: 14px; max-width: 460px; margin: 0 auto 24px;">
        Phòng mã <b>${roomId}</b> có thể đã thay đổi hoặc đang được hệ thống cập nhật.<br>${errorMsg || ""}
      </p>
      <button class="btn btn-primary" onclick="handleBackToRooms()">
        ← Quay lại trang chủ xem phòng khác
      </button>
    </div>
  `;
}

// =============================================================
// 12. HELPER RENDER BẢNG GIÁ VÀ CALENDAR GRID
// =============================================================
function renderPricingTableRows(slots, grid, selectedDate) {
  const todayStr = new Date().toISOString().split("T")[0];
  const targetDate = selectedDate || currentSelectedDate || todayStr;
  let matrix = {};
  if (grid) {
    if (grid.matrix) {
      matrix = grid.matrix;
    } else if (Array.isArray(grid)) {
      grid.forEach(r => {
        matrix[r.date] = {
          K1: r.K1 ? "AVAILABLE" : "BOOKED",
          K2: r.K2 ? "AVAILABLE" : "BOOKED",
          K3: r.K3 ? "AVAILABLE" : "BOOKED",
          QD: r.QD ? "AVAILABLE" : "BOOKED",
        };
      });
    }
  }

  return (slots || []).map(s => {
    const isOvernight = s.khung_code === "QD";
    const cellVal = matrix?.[targetDate]?.[s.khung_code];
    const isAvail = (cellVal === "AVAILABLE" || cellVal === true || cellVal === undefined);
    return `
      <tr>
        <td>
          <div class="rd-price-slot-badge badge-slot">
            ${s.label}
          </div>
          <div class="rd-price-duration" style="margin-top:4px;">${isOvernight ? 'Lưu trú qua đêm (~11–12h)' : 'Khung 3 tiếng thư giãn'}</div>
        </td>
        <td>
          <div class="rd-price-amount">${formatMoney(s.price)}</div>
          <div class="rd-price-note">Đã bao gồm VAT và dọn phòng</div>
        </td>
        <td>
          <span class="rd-status-tag ${isAvail ? 'available' : 'booked'}">${isAvail ? 'Còn trống' : 'Đã đặt'}</span>
        </td>
      </tr>
    `;
  }).join("");
}

function refreshPricingTableUI() {
  const tbody = document.getElementById("rd-pricing-table-body");
  if (tbody && currentRoomData) {
    const dateInput = document.getElementById("rd-bc-date");
    const targetDate = dateInput ? dateInput.value : (currentSelectedDate || new Date().toISOString().split("T")[0]);
    tbody.innerHTML = renderPricingTableRows(currentRoomData.slots || [], currentRoomData.grid, targetDate);
  }
}

function renderCalendarGridHtml(grid) {
  let dates = [];
  let matrix = {};

  if (Array.isArray(grid)) {
    dates = grid.map(r => r.date);
    grid.forEach(r => {
      matrix[r.date] = {
        K1: r.K1 ? "AVAILABLE" : "BOOKED",
        K2: r.K2 ? "AVAILABLE" : "BOOKED",
        K3: r.K3 ? "AVAILABLE" : "BOOKED",
        QD: r.QD ? "AVAILABLE" : "BOOKED",
      };
    });
  } else if (grid && typeof grid === "object") {
    dates = grid.dates || [];
    matrix = grid.matrix || {};
    if (dates.length === 0 && Array.isArray(grid.rows)) {
      dates = grid.rows.map(r => r.date);
      grid.rows.forEach(r => {
        matrix[r.date] = {
          K1: r.K1 ? "AVAILABLE" : "BOOKED",
          K2: r.K2 ? "AVAILABLE" : "BOOKED",
          K3: r.K3 ? "AVAILABLE" : "BOOKED",
          QD: r.QD ? "AVAILABLE" : "BOOKED",
        };
      });
    }
  }

  if (!dates || dates.length === 0) {
    return `<div style="padding:16px; text-align:center; color:var(--text-muted); font-size:13px;">Không có dữ liệu lịch cho phòng này.</div>`;
  }

  const slots = ["K1", "K2", "K3", "QD"];
  const roomSlots = currentRoomData?.slots || [];
  const slotMap = {};
  roomSlots.forEach(s => {
    slotMap[s.khung_code] = s;
  });

  const defaultSlotInfo = {
    K1: { name: "Sáng", time: "09:30 – 12:30" },
    K2: { name: "Chiều", time: "13:00 – 16:00" },
    K3: { name: "Tối", time: "16:30 – 19:30" },
    QD: { name: "Qua đêm", time: "20:00 – 08:30" },
  };

  const todayStr = new Date().toISOString().split("T")[0];

  let html = `
    <table class="rd-calendar-table">
      <thead>
        <tr>
          <th class="rd-cal-slot-header" style="text-align:left; padding-left:14px; min-width:130px; position:sticky; left:0; z-index:2; background:var(--cozy-light);">Khung giờ</th>
          ${dates.map(d => {
            const dt = new Date(d + "T00:00:00");
            const dayNames = ["CN", "Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7"];
            const isToday = (d === todayStr);
            const dayName = isToday ? "Hôm nay" : dayNames[dt.getDay()];
            const [y, m, day] = d.split("-");
            const diffDays = Math.round((dt - new Date(todayStr + "T00:00:00")) / 86400000);
            const isEarlyBird = diffDays >= 7;
            return `
              <th style="min-width:82px; text-align:center; padding:8px 4px; ${isToday ? 'background:#fef7ee; color:var(--cozy-primary);' : ''}">
                <div style="font-size:11px; font-weight:700; ${isToday ? 'color:var(--cozy-primary);' : 'color:var(--text-muted);'}">${dayName}</div>
                <div style="font-size:12.5px; font-weight:700; margin-top:2px;">${day}/${m}</div>
                ${isEarlyBird ? `<div style="margin-top:3px;"><span style="display:inline-block; font-size:9.5px; font-weight:800; color:#15803d; background:#dcfce7; padding:1px 5px; border-radius:4px;" title="Đặt trước >= 7 ngày: Giảm 10% (EARLYBIRD10)">-10%</span></div>` : ''}
              </th>
            `;
          }).join("")}
        </tr>
      </thead>
      <tbody>
  `;

  slots.forEach(sCode => {
    const sInfo = slotMap[sCode];
    const def = defaultSlotInfo[sCode];
    const slotTitle = sCode === "QD" ? "Qua đêm" : (sCode === "K1" ? "Sáng" : (sCode === "K2" ? "Chiều" : "Tối"));
    const slotTime = sInfo ? `${sInfo.start_time} – ${(sInfo.end_time || '').replace('+1', '')}` : def.time;

    html += `<tr>`;
    html += `
      <td class="rd-cal-slot-name" style="vertical-align:middle; padding:10px 14px;">
        <div style="font-size:13px; font-weight:700; color:var(--cozy-dark);">${slotTitle}</div>
        <div style="font-size:11px; color:var(--text-muted); margin-top:2px;">${slotTime}</div>
      </td>
    `;

    const dateInput = document.getElementById("rd-bc-date");
    const selectedDate = dateInput ? dateInput.value : (currentSelectedDate || todayStr);
    const targetSlotCode = (currentStayType === "overnight") ? "QD" : currentSelectedSlotCode;

    dates.forEach(d => {
      const cellVal = matrix?.[d]?.[sCode];
      const isAvail = (cellVal === "AVAILABLE" || cellVal === true || cellVal === undefined);
      const isSelected = (d === selectedDate && sCode === targetSlotCode);

      if (isSelected) {
        html += `
          <td style="text-align:center; vertical-align:middle; padding:8px 4px;">
            <button type="button" class="rd-cal-pill selected" onclick="handleQuickSelectFromCalendar('${d}', '${sCode}')" title="Đang chọn: Ngày ${d} - Khung ${slotTitle}" style="border:none; cursor:pointer; font-family:inherit; transition:all 0.15s ease;">
              Đang chọn
            </button>
          </td>
        `;
      } else if (isAvail) {
        html += `
          <td style="text-align:center; vertical-align:middle; padding:8px 4px;">
            <button type="button" class="rd-cal-pill avail" onclick="handleQuickSelectFromCalendar('${d}', '${sCode}')" title="Bấm để chọn ngày ${d} khung ${slotTitle}" style="border:none; cursor:pointer; font-family:inherit; transition:all 0.15s ease;">
              Còn trống
            </button>
          </td>
        `;
      } else {
        html += `
          <td style="text-align:center; vertical-align:middle; padding:8px 4px;">
            <span class="rd-cal-pill booked" title="Đã có khách đặt">Đã đặt</span>
          </td>
        `;
      }
    });
    html += `</tr>`;
  });

  html += `</tbody></table>`;
  return html;
}

function renderSimilarRoomCard(r) {
  const coverImg = (r.images && r.images.length > 0) ? r.images[0] : "";
  const thumb = coverImg
    ? `<img src="${coverImg}" alt="${r.room_name}" loading="lazy" />`
    : `<div style="display:flex; align-items:center; justify-content:center; height:100%; background:var(--cozy-sand); color:var(--cozy-primary);"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M2 4v16"></path><path d="M2 8h18a2 2 0 0 1 2 2v10"></path><path d="M2 17h20"></path><path d="M6 8v9"></path></svg></div>`;

  return `
    <div class="rd-similar-card" onclick="openRoomDetailView('${r.room_id}')">
      <div class="rd-similar-thumb">
        ${thumb}
        <div class="rd-similar-badge">${r.room_type}</div>
      </div>
      <div class="rd-similar-info">
        <h4 class="rd-similar-title">${r.room_name}</h4>
        <div class="rd-similar-meta">${r.branch_name} - Tối đa ${r.capacity} khách</div>
        <div class="rd-similar-price">
          Từ <b>${formatMoney(r.price || 150000)}</b> <span style="font-size:11px; font-weight:normal; color:var(--text-muted);">/ khung</span>
        </div>
      </div>
    </div>
  `;
}
