// =============================================================
// COZYHOME PROMOTIONS & VOUCHERS MODULE
// Quản lý danh mục khuyến mãi, sao chép mã và tự động áp dụng
// =============================================================

const promotionsState = {
  list: [],
  loaded: false,
};

async function loadPromotions() {
  try {
    const res = await apiFetch("/api/promotions");
    promotionsState.list = res.promotions || [];
    promotionsState.loaded = true;
    return promotionsState.list;
  } catch (err) {
    console.error("Không thể tải danh sách khuyến mãi:", err);
    return [];
  }
}

async function openPromotionsModal() {
  const modal = document.getElementById("modal-promotions");
  if (!modal) return;
  modal.style.display = "flex";

  const container = document.getElementById("promotions-modal-list");
  if (!container) return;

  if (!promotionsState.loaded || promotionsState.list.length === 0) {
    container.innerHTML = `
      <div style="text-align:center; padding:30px; color:var(--text-muted);">
        <div class="loading-spinner" style="margin:0 auto 12px;"></div>
        <div>Đang nạp danh sách ưu đãi hấp dẫn từ CozyHome...</div>
      </div>
    `;
    await loadPromotions();
  }

  renderPromotionsList(promotionsState.list, container);
}

function closePromotionsModal() {
  const modal = document.getElementById("modal-promotions");
  if (modal) modal.style.display = "none";
}

function renderPromotionsList(list, container) {
  if (!container) return;

  if (!list || list.length === 0) {
    container.innerHTML = `
      <div style="text-align:center; padding:30px; color:var(--text-muted);">
        Hiện chưa có chương trình khuyến mãi nào đang kích hoạt. Quý khách vui lòng quay lại sau!
      </div>
    `;
    return;
  }

  container.innerHTML = list.map(p => {
    const discountLabel = p.discount_percent > 0 
      ? `Giảm ${p.discount_percent}%` 
      : `Giảm ${Number(p.discount_value).toLocaleString('vi-VN')} ₫`;

    return `
      <div class="promo-card">
        <div class="promo-card-left">
          <div class="promo-badge">${p.badge || "Ưu đãi"}</div>
          <div class="promo-discount-tag">${discountLabel}</div>
        </div>
        <div class="promo-card-body">
          <div class="promo-card-header">
            <h4 class="promo-title">${p.name}</h4>
            <div class="promo-code-box" onclick="copyPromoCode('${p.code}')" title="Bấm để sao chép mã">
              <span class="promo-code-text">${p.code}</span>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
              </svg>
            </div>
          </div>
          <p class="promo-desc">${p.description}</p>
          <div class="promo-card-footer">
            <span class="promo-expiry">Hạn dùng: <b>${p.effective_to ? p.effective_to.split('-').reverse().join('/') : 'Dài hạn'}</b></span>
            <div class="promo-actions">
              <button type="button" class="btn btn-sm btn-outline promo-btn-copy" onclick="copyPromoCode('${p.code}')">
                Sao chép mã
              </button>
              <button type="button" class="btn btn-sm btn-primary promo-btn-use" onclick="usePromoCode('${p.code}')">
                Dùng ngay
              </button>
            </div>
          </div>
        </div>
      </div>
    `;
  }).join("");
}

function copyPromoCode(code) {
  if (!code) return;
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(code).then(() => {
      showToast(`Đã sao chép mã ${code}! Hãy nhập mã này tại trang Thanh toán để nhận chiết khấu.`, "success");
    }).catch(() => {
      fallbackCopy(code);
    });
  } else {
    fallbackCopy(code);
  }
}

function fallbackCopy(code) {
  const t = document.createElement("textarea");
  t.value = code;
  document.body.appendChild(t);
  t.select();
  document.execCommand("copy");
  document.body.removeChild(t);
  showToast(`Đã sao chép mã ${code}!`, "success");
}

function usePromoCode(code) {
  copyPromoCode(code);
  closePromotionsModal();

  // Lưu mã vào state để checkout tự động điền nếu chưa vào
  window.selectedPendingPromoCode = code;

  const checkoutPromoInput = document.getElementById("checkout-promo-input");
  if (checkoutPromoInput && document.getElementById("view-checkout")?.style.display !== "none") {
    checkoutPromoInput.value = code;
    if (typeof handleApplyPromoCode === "function") {
      handleApplyPromoCode();
    }
  } else {
    showToast(`Đã lưu mã ${code}. Bạn hãy chọn phòng và khung giờ, mã sẽ được áp dụng khi thanh toán!`, "info");
    if (typeof navigateTo === "function" && (!state.currentView || state.currentView === "home")) {
      const roomSection = document.getElementById("room-list-container");
      if (roomSection) {
        roomSection.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }
  }
}
