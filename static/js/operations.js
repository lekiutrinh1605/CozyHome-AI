// -------------------------------------------------------------
// CozyHome Operations Portal (5 Internal Roles)
// -------------------------------------------------------------

let opsCurrentTab = "letan";

async function loadOperationsDashboard() {
  // Dùng getEffectiveRole() để hỗ trợ Training Mode (activeRole)
  const role = getEffectiveRole();
  if (!state.user || !role || role === COZY_ROLES.CUSTOMER) {
    showToast("Bạn không có quyền truy cập khu vực vận hành nội bộ.", "error");
    navigateTo("home");
    return;
  }

  // Phân quyền hiển thị tab theo vai trò hiệu quả
  setupOpsRoleTabs();

  // Tải dữ liệu tương ứng tab đang mở
  switchOpsTab(opsCurrentTab);
}

function setupOpsRoleTabs() {
  // Dùng getEffectiveRole() để hỗ trợ Training Mode
  const role = getEffectiveRole();

  if (role === COZY_ROLES.ADMIN) {
    // Quản trị viên có cổng Quản trị hệ thống chuyên biệt, không dùng tab tác vụ lễ tân/buồng phòng
    navigateTo("admin");
    return;
  }

  const tabBtns = document.querySelectorAll(".ops-tab-btn");

  tabBtns.forEach(btn => {
    const tabName = btn.getAttribute("data-opstab");
    let allowed = false;

    if (role === COZY_ROLES.MANAGER) {
      // Quản lý chuỗi: xem baocao, quanly, buong, letan (giám sát vận hành), không xem tab admin cũ
      if (tabName === "baocao" || tabName === "quanly" || tabName === "letan" || tabName === "buong") allowed = true;
    } else if (role === COZY_ROLES.RECEPTIONIST && tabName === "letan") {
      allowed = true;
    } else if (role === COZY_ROLES.HOUSEKEEPING && tabName === "buong") {
      allowed = true;
    } else if (role === COZY_ROLES.ACCOUNTANT && tabName === "ketoan") {
      allowed = true;
    }

    btn.style.display = allowed ? "inline-flex" : "none";
  });

  // Mặc định chọn tab phù hợp vai trò hiệu quả
  if (role === COZY_ROLES.RECEPTIONIST) opsCurrentTab = "letan";
  else if (role === COZY_ROLES.HOUSEKEEPING) opsCurrentTab = "buong";
  else if (role === COZY_ROLES.ACCOUNTANT) opsCurrentTab = "ketoan";
  else if (role === COZY_ROLES.MANAGER) opsCurrentTab = "baocao";
}

function switchOpsTab(tabName) {
  opsCurrentTab = tabName;

  document.querySelectorAll(".ops-tab-btn").forEach(btn => {
    if (btn.getAttribute("data-opstab") === tabName) btn.classList.add("active");
    else btn.classList.remove("active");
  });

  document.querySelectorAll(".ops-tab-pane").forEach(pane => {
    if (pane.id === `ops-pane-${tabName}`) pane.style.display = "block";
    else pane.style.display = "none";
  });

  if (tabName === "baocao") loadDashboardReportData();
  else if (tabName === "letan") {
    switchReceptionTab(letanCurrentTab);
    loadReceptionistData();
  }
  else if (tabName === "buong") loadHousekeepingData();
  else if (tabName === "ketoan") loadAccountingData();
  else if (tabName === "quanly") loadManagerData();
  else if (tabName === "admin") loadAdminData();
}

// -------------------------------------------------------------
// 0. Dashboard Báo Cáo và Phân Tích Chuỗi (Admin và Quản Lý Chuỗi)
// -------------------------------------------------------------
let reportFilters = {
  period: "30days",
  branch_id: "ALL",
  from_date: "",
  to_date: ""
};

let reportChartInstances = {
  timeline: null,
  branch: null,
  stayType: null,
  roomStatus: null
};

function setReportPeriod(period) {
  reportFilters.period = period;
  
  // Đánh dấu nút kỳ nhanh được chọn
  document.querySelectorAll(".dashboard-period-btn").forEach(btn => {
    if (btn.getAttribute("data-period") === period) {
      btn.classList.add("active");
    } else {
      btn.classList.remove("active");
    }
  });

  reportFilters.from_date = "";
  reportFilters.to_date = "";
  loadDashboardReportData();
}

function onCustomDateInputChange() {
  // Khi người dùng tự chọn ngày trên lịch, bỏ active ở các nút kỳ nhanh
  document.querySelectorAll(".dashboard-period-btn").forEach(btn => {
    btn.classList.remove("active");
  });
}

function applyReportCustomDates() {
  const from = document.getElementById("report-date-from")?.value;
  const to = document.getElementById("report-date-to")?.value;

  if (!from || !to) {
    showToast("Vui lòng chọn đầy đủ ngày bắt đầu và ngày kết thúc.", "warning");
    return;
  }
  if (from > to) {
    showToast("Ngày bắt đầu không được lớn hơn ngày kết thúc.", "error");
    return;
  }

  // Bỏ active ở các nút kỳ nhanh
  document.querySelectorAll(".dashboard-period-btn").forEach(btn => {
    btn.classList.remove("active");
  });

  reportFilters.period = "custom";
  reportFilters.from_date = from;
  reportFilters.to_date = to;
  loadDashboardReportData();
}

function onReportBranchChange(branchId) {
  reportFilters.branch_id = branchId;
  loadDashboardReportData();
}

async function resetDashboardReport() {
  // 1. Đặt lại bộ lọc về mặc định: Toàn chuỗi & 30 ngày gần nhất
  reportFilters.period = "30days";
  reportFilters.branch_id = "ALL";
  reportFilters.from_date = "";
  reportFilters.to_date = "";

  // 2. Cập nhật dropdown chọn chi nhánh về 'ALL' (Toàn chuỗi)
  const branchSelect = document.getElementById("report-branch-select");
  if (branchSelect) {
    branchSelect.value = "ALL";
  }

  // 3. Đánh dấu nút '30 ngày' là active, bỏ active ở các nút khác
  document.querySelectorAll(".dashboard-period-btn").forEach(btn => {
    if (btn.getAttribute("data-period") === "30days") {
      btn.classList.add("active");
    } else {
      btn.classList.remove("active");
    }
  });

  // 4. Xóa giá trị cũ trong 2 ô lịch (sẽ được tự động điền lại bằng dải 30 ngày từ server)
  const inputFrom = document.getElementById("report-date-from");
  const inputTo = document.getElementById("report-date-to");
  if (inputFrom) inputFrom.value = "";
  if (inputTo) inputTo.value = "";

  // 5. Tải lại dữ liệu mới nhất từ server
  await loadDashboardReportData();
  showToast("Đã đặt lại toàn bộ bộ lọc và cập nhật báo cáo mới nhất!", "success");
}

async function loadDashboardReportData() {
  try {
    let url = `/api/operations/report?period=${reportFilters.period}&branch_id=${reportFilters.branch_id}`;
    if (reportFilters.period === "custom" && reportFilters.from_date && reportFilters.to_date) {
      url += `&from_date=${reportFilters.from_date}&to_date=${reportFilters.to_date}`;
    }

    const res = await apiFetch(url);
    if (!res || res.status !== "ok" || !res.data) {
      showToast("Không thể tải dữ liệu báo cáo", "error");
      return;
    }

    const report = res.data;

    // 1. Cập nhật ngày cụ thể lên 2 ô lịch
    const inputFrom = document.getElementById("report-date-from");
    const inputTo = document.getElementById("report-date-to");
    if (inputFrom && report.date_range && report.date_range.from) {
      inputFrom.value = report.date_range.from;
    }
    if (inputTo && report.date_range && report.date_range.to) {
      inputTo.value = report.date_range.to;
    }

    // 2. Cập nhật 4 KPI cốt lõi
    const kpiRev = document.getElementById("report-kpi-revenue");
    if (kpiRev) kpiRev.innerText = formatMoney(report.summary.total_revenue);

    const kpiBookings = document.getElementById("report-kpi-bookings");
    if (kpiBookings) kpiBookings.innerText = `${report.summary.total_bookings} lượt`;

    const kpiSub = document.getElementById("report-kpi-bookings-sub");
    if (kpiSub) {
      kpiSub.innerText = `${report.summary.confirmed_bookings} xác nhận - ${report.summary.staying_bookings} đang ở - ${report.summary.completed_bookings} hoàn tất`;
    }

    const kpiOcc = document.getElementById("report-kpi-occupancy");
    if (kpiOcc) kpiOcc.innerText = `${report.summary.occupancy_rate}%`;

    const kpiInhouse = document.getElementById("report-kpi-inhouse");
    if (kpiInhouse) kpiInhouse.innerText = `${report.summary.in_house_guests} khách`;

    // 3. Trạng thái 24 buồng phòng
    const readyObj = report.room_status.find(s => s.status === "Sẵn sàng");
    const stayingObj = report.room_status.find(s => s.status === "Đang sử dụng");
    const cleanObj = report.room_status.find(s => s.status === "Đang dọn");
    const maintObj = report.room_status.find(s => s.status === "Bảo trì");

    if (document.getElementById("report-room-ready")) document.getElementById("report-room-ready").innerText = readyObj ? readyObj.count : 0;
    if (document.getElementById("report-room-staying")) document.getElementById("report-room-staying").innerText = stayingObj ? stayingObj.count : 0;
    if (document.getElementById("report-room-cleaning")) document.getElementById("report-room-cleaning").innerText = cleanObj ? cleanObj.count : 0;
    if (document.getElementById("report-room-maint")) document.getElementById("report-room-maint").innerText = maintObj ? maintObj.count : 0;

    // 4. Chỉ số Hủy và Hoàn tiền
    if (document.getElementById("report-cancel-count")) document.getElementById("report-cancel-count").innerText = `${report.cancellation.cancelled_bookings} đơn`;
    if (document.getElementById("report-cancel-rate")) document.getElementById("report-cancel-rate").innerText = `${report.cancellation.cancellation_rate}%`;
    if (document.getElementById("report-refund-sum")) document.getElementById("report-refund-sum").innerText = formatMoney(report.cancellation.total_refunded_amount);

    // 5. Render Biểu đồ Chart.js
    renderReportCharts(report);

    // 6. Render Bảng Hiệu Quả Chi Nhánh
    renderBranchTable(report.branch_performance);

    // 7. Render Top 5 Phòng
    renderTopRooms(report.top_rooms);

    // 8. Render Lượt Đặt Phòng Gần Nhất
    renderRecentBookings(report.recent_bookings);

  } catch (err) {
    console.error("Lỗi tải dashboard báo cáo:", err);
    if (badge) badge.innerText = "Lỗi tải báo cáo";
    showToast("Lỗi khi tải dữ liệu báo cáo phân tích", "error");
  }
}

function renderReportCharts(report) {
  if (typeof Chart === "undefined") {
    console.warn("Chart.js chưa được tải.");
    return;
  }

  // Chart 1: Doanh thu và Lượt đặt theo thời gian
  const ctxTimeline = document.getElementById("chart-revenue-timeline");
  if (ctxTimeline) {
    if (reportChartInstances.timeline) reportChartInstances.timeline.destroy();

    const labels = (report.timeline || []).map(t => {
      const parts = t.date.split("-");
      return parts.length === 3 ? `${parts[2]}/${parts[1]}` : t.date;
    });
    const revData = (report.timeline || []).map(t => t.revenue);
    const bookData = (report.timeline || []).map(t => t.bookings);

    reportChartInstances.timeline = new Chart(ctxTimeline, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Doanh thu (₫)",
            data: revData,
            backgroundColor: "rgba(185, 107, 53, 0.75)",
            borderColor: "#b96b35",
            borderRadius: 4,
            yAxisID: "y",
            order: 2
          },
          {
            label: "Lượt đặt",
            data: bookData,
            type: "line",
            borderColor: "#2563eb",
            backgroundColor: "#2563eb",
            pointBackgroundColor: "#2563eb",
            pointRadius: 3,
            tension: 0.25,
            yAxisID: "y1",
            order: 1
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: "index",
          intersect: false
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function(context) {
                if (context.dataset.yAxisID === "y") {
                  return ` Doanh thu: ${formatMoney(context.parsed.y)}`;
                } else {
                  return ` Đơn đặt: ${context.parsed.y} lượt`;
                }
              }
            }
          }
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { maxRotation: 0, font: { size: 11 } }
          },
          y: {
            type: "linear",
            display: true,
            position: "left",
            ticks: {
              callback: val => val >= 1000000 ? (val / 1000000).toFixed(1) + "M" : (val / 1000).toFixed(0) + "k"
            }
          },
          y1: {
            type: "linear",
            display: true,
            position: "right",
            grid: { drawOnChartArea: false },
            ticks: { precision: 0 }
          }
        }
      }
    });
  }

  // Chart 2: Tỷ trọng doanh thu theo chi nhánh
  const ctxBranch = document.getElementById("chart-branch-share");
  if (ctxBranch) {
    if (reportChartInstances.branch) reportChartInstances.branch.destroy();

    const branchColors = ["#b96b35", "#16a34a", "#2563eb"];
    const branchNames = (report.branch_performance || []).map(b => b.branch_name.replace("CozyHome ", ""));
    const branchRevenues = (report.branch_performance || []).map(b => b.revenue);

    reportChartInstances.branch = new Chart(ctxBranch, {
      type: "doughnut",
      data: {
        labels: branchNames,
        datasets: [{
          data: branchRevenues,
          backgroundColor: branchColors,
          borderWidth: 2,
          borderColor: "#ffffff"
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "bottom", labels: { boxWidth: 12, font: { size: 11 } } },
          tooltip: {
            callbacks: {
              label: function(context) {
                return ` ${context.label}: ${formatMoney(context.raw)}`;
              }
            }
          }
        },
        cutout: "68%"
      }
    });
  }


  // Chart 4: Trạng thái buồng phòng
  const ctxRoom = document.getElementById("chart-room-status");
  if (ctxRoom) {
    if (reportChartInstances.roomStatus) reportChartInstances.roomStatus.destroy();

    const statuses = report.room_status || [];
    reportChartInstances.roomStatus = new Chart(ctxRoom, {
      type: "doughnut",
      data: {
        labels: statuses.map(s => s.status),
        datasets: [{
          data: statuses.map(s => s.count),
          backgroundColor: statuses.map(s => s.color),
          borderWidth: 2,
          borderColor: "#ffffff"
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "bottom", labels: { boxWidth: 12, font: { size: 11 } } },
          tooltip: {
            callbacks: {
              label: function(context) {
                return ` ${context.label}: ${context.raw} phòng`;
              }
            }
          }
        },
        cutout: "65%"
      }
    });
  }
}

function renderBranchTable(branches) {
  const tbody = document.getElementById("report-branch-table-body");
  if (!tbody) return;

  if (!branches || branches.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:var(--text-muted); padding:16px;">Không có dữ liệu chi nhánh</td></tr>`;
    return;
  }

  tbody.innerHTML = branches.map(b => {
    return `
      <tr>
        <td><b>${b.branch_id}</b></td>
        <td>
          <div style="font-weight:700; color:var(--cozy-dark);">${b.branch_name}</div>
          <div style="font-size:11.5px; color:var(--text-muted);">${b.address || ''}</div>
        </td>
        <td>${b.room_count} phòng</td>
        <td><span class="badge" style="background:#eff6ff; color:#1d4ed8; font-weight:700;">${b.bookings} đơn</span></td>
        <td style="font-weight:700; color:var(--cozy-primary);">${formatMoney(b.revenue)}</td>
        <td>
          <div style="display:flex; align-items:center; gap:8px;">
            <div style="flex:1; background:#e5e7eb; border-radius:4px; height:8px; overflow:hidden; min-width:60px;">
              <div style="background:var(--cozy-primary); width:${Math.min(100, b.occupancy_rate)}%; height:100%;"></div>
            </div>
            <span style="font-size:12px; font-weight:600;">${b.occupancy_rate}%</span>
          </div>
        </td>
        <td><span class="badge badge-success">Đang hoạt động</span></td>
      </tr>
    `;
  }).join("");
}

function renderTopRooms(topRooms) {
  const container = document.getElementById("report-top-rooms-list");
  if (!container) return;

  if (!topRooms || topRooms.length === 0) {
    container.innerHTML = `<div style="text-align:center; color:var(--text-muted); padding:16px;">Chưa có dữ liệu lượt đặt phòng</div>`;
    return;
  }

  const medals = ["#1", "#2", "#3", "#4", "#5"];

  container.innerHTML = topRooms.map((r, idx) => {
    return `
      <div style="display:flex; justify-content:space-between; align-items:center; padding:10px 14px; background:#fffaf5; border:1px solid var(--cozy-border); border-radius:10px;">
        <div style="display:flex; align-items:center; gap:10px;">
          <div style="font-size:20px;">${medals[idx] || (idx + 1)}</div>
          <div>
            <div style="font-weight:700; color:var(--cozy-dark); font-size:13.5px;">${r.room_code} - ${r.room_name}</div>
            <div style="font-size:11.5px; color:var(--text-muted);">${r.branch_id} - ${r.room_type} (${r.concept})</div>
          </div>
        </div>
        <div style="text-align:right;">
          <div style="font-weight:700; color:var(--cozy-primary); font-size:13.5px;">${formatMoney(r.revenue)}</div>
          <div style="font-size:11.5px; color:#2563eb; font-weight:600;">${r.bookings} lượt đặt</div>
        </div>
      </div>
    `;
  }).join("");
}

function renderRecentBookings(bookings) {
  const tbody = document.getElementById("report-recent-bookings-body");
  if (!tbody) return;

  if (!bookings || bookings.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:var(--text-muted); padding:16px;">Chưa có lượt đặt phòng nào trong khoảng thời gian này</td></tr>`;
    return;
  }

  tbody.innerHTML = bookings.map(b => {
    let statusBadge = "badge-cozy";
    if (b.status === "Đã hoàn tất") statusBadge = "badge-success";
    else if (b.status === "Đã check-in") statusBadge = "badge-info";
    else if (b.status === "Đã xác nhận") statusBadge = "badge-cozy";
    else if (b.status === "Đã hủy") statusBadge = "badge-danger";
    else if (b.status === "Chờ thanh toán") statusBadge = "badge-warning";

    const isOvernight = b.slot_id === "K4" || (b.stay_type && b.stay_type.includes("đêm"));

    return `
      <tr>
        <td><b>${b.booking_code}</b></td>
        <td>
          <div style="font-weight:600;">${b.customer_name || 'Khách hàng'}</div>
          <div style="font-size:11px; color:var(--text-muted);">${b.customer_phone || ''}</div>
        </td>
        <td>
          <div><b>${b.room_code || ''}</b></div>
          <div style="font-size:11px; color:var(--text-muted);">${b.branch_id || ''}</div>
        </td>
        <td>
          <span class="badge" style="font-size:11px; background:${isOvernight ? '#f3e8ff' : '#ffedd5'}; color:${isOvernight ? '#7e22ce' : '#c2410c'}; font-weight:600;">
            ${isOvernight ? 'Qua đêm' : 'Theo giờ'}
          </span>
        </td>
        <td style="font-weight:700; color:var(--cozy-primary);">${formatMoney(b.total_amount || 0)}</td>
        <td><span class="badge ${statusBadge}">${b.status}</span></td>
      </tr>
    `;
  }).join("");
}

// -------------------------------------------------------------
// 1. Lễ tân (Receptionist - BR-08, BR-12, UC-04)
// -------------------------------------------------------------
let letanCurrentTab = "checkin";
let receptionBookingsCache = [];
let receptionStatusFilter = "ALL";
let receptionBranchFilter = localStorage.getItem("cozy_active_branch") || "ALL";

function changeReceptionBranch(branchVal) {
  receptionBranchFilter = branchVal || "ALL";
  localStorage.setItem("cozy_active_branch", receptionBranchFilter);
  loadReceptionistData();
}

function switchReceptionTab(subTab) {
  letanCurrentTab = subTab;

  document.querySelectorAll(".letan-tab-item").forEach(item => {
    if (item.getAttribute("data-letantab") === subTab) {
      item.classList.add("active");
    } else {
      item.classList.remove("active");
    }
  });

  document.querySelectorAll(".letan-sub-pane").forEach(pane => {
    if (pane.id === `letan-pane-${subTab}`) {
      pane.style.display = "block";
    } else {
      pane.style.display = "none";
    }
  });
}

function updateReceptionPillCounts() {
  const bks = receptionBookingsCache || [];
  const total = bks.length;
  const checkin = bks.filter(b => b.status === "Đã xác nhận" || b.status === "Chờ check-in").length;
  const staying = bks.filter(b => b.status === "Đã check-in" || b.status === "Quá giờ - chưa checkout").length;
  const completed = bks.filter(b => b.status === "Đã hoàn tất").length;

  const elAll = document.getElementById("count-pill-all");
  const elCheckin = document.getElementById("count-pill-checkin");
  const elStaying = document.getElementById("count-pill-staying");
  const elCompleted = document.getElementById("count-pill-completed");

  if (elAll) elAll.textContent = total;
  if (elCheckin) elCheckin.textContent = checkin;
  if (elStaying) elStaying.textContent = staying;
  if (elCompleted) elCompleted.textContent = completed;
}

function setReceptionStatusFilter(status) {
  receptionStatusFilter = status;
  document.querySelectorAll(".btn-filter-pill").forEach(pill => {
    if (pill.getAttribute("data-statusfilter") === status) {
      pill.classList.add("active");
    } else {
      pill.classList.remove("active");
    }
  });
  renderFilteredReceptionTable();
}

function filterReceptionTable() {
  renderFilteredReceptionTable();
}

function renderFilteredReceptionTable() {
  const container = document.getElementById("ops-reception-table");
  if (!container) return;

  const kw = (document.getElementById("letan-search-input")?.value || "").toLowerCase().trim();

  let filtered = receptionBookingsCache || [];

  // Lọc theo từ khóa tìm kiếm (mã đơn, mã phòng, tên khách, sđt)
  if (kw) {
    filtered = filtered.filter(b => 
      (b.booking_code || "").toLowerCase().includes(kw) ||
      (b.room_id || "").toLowerCase().includes(kw) ||
      (b.customer_name || "").toLowerCase().includes(kw) ||
      (b.customer_phone || "").toLowerCase().includes(kw)
    );
  }

  // Lọc theo trạng thái chuẩn hóa (4 nút: Tất cả, Chờ Check-in, Đang ở, Đã hoàn tất)
  if (receptionStatusFilter !== "ALL") {
    if (receptionStatusFilter === "CHECKIN_PENDING" || receptionStatusFilter === "Đã xác nhận" || receptionStatusFilter === "Chờ check-in") {
      filtered = filtered.filter(b => b.status === "Đã xác nhận" || b.status === "Chờ check-in");
    } else if (receptionStatusFilter === "STAYING" || receptionStatusFilter === "Đã check-in") {
      filtered = filtered.filter(b => b.status === "Đã check-in" || b.status === "Quá giờ - chưa checkout");
    } else if (receptionStatusFilter === "COMPLETED" || receptionStatusFilter === "Hoàn tất" || receptionStatusFilter === "Đã hoàn tất" || receptionStatusFilter === "Đã trả") {
      filtered = filtered.filter(b => b.status === "Đã hoàn tất");
    } else {
      filtered = filtered.filter(b => b.status === receptionStatusFilter);
    }
  }

  if (filtered.length === 0) {
    const isFilteredBranch = receptionBranchFilter !== "ALL";
    container.innerHTML = `
      <div style="padding:32px 20px; text-align:center; color:var(--text-muted); font-size:13.5px;">
        <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="margin-bottom:8px; opacity:0.6;"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        <div style="font-weight:600; color:var(--cozy-dark); margin-bottom:4px;">Không tìm thấy lượt đặt phòng nào phù hợp với bộ lọc${kw ? ` "${kw}"` : ""}.</div>
        ${isFilteredBranch ? `
          <div style="margin-top:10px;">
            <button type="button" class="btn btn-sm btn-outline" onclick="changeReceptionBranch('ALL')" style="font-weight:600;">
              🔍 Mở rộng tìm kiếm trên Toàn hệ thống chuỗi (Tất cả 3 cơ sở)
            </button>
          </div>
        ` : ""}
      </div>
    `;
    return;
  }

  container.innerHTML = `
    <div class="table-responsive">
      <table class="data-table">
        <thead>
          <tr>
            <th>Mã đơn</th>
            <th>Phòng</th>
            <th>Khách hàng</th>
            <th>Ngày và Khung</th>
            <th>Trạng thái</th>
            <th style="text-align: right;">Thủ tục</th>
          </tr>
        </thead>
        <tbody>
          ${filtered.map(b => renderReceptionRow(b)).join("")}
        </tbody>
      </table>
    </div>
  `;
}

async function loadReceptionistData() {
  const branchSelect = document.getElementById("letan-branch-select");
  if (branchSelect) {
    if (branchSelect.value !== receptionBranchFilter) {
      branchSelect.value = receptionBranchFilter;
    }
  }

  const branchParam = (receptionBranchFilter === "ALL" || !receptionBranchFilter) ? "" : receptionBranchFilter;
  const overstayContainer = document.getElementById("ops-overstay-table");

  try {
    const res = await apiFetch(`/api/operations/dashboard?branch_id=${branchParam}`);
    // Chỉ lấy các đơn phòng hợp lệ phục vụ công tác Lễ tân (loại bỏ đơn Đã hủy và Hết hạn giữ chỗ)
    const bookings = (res.bookings || []).filter(b => b.status !== "Đã hủy" && b.status !== "Hết hạn giữ chỗ");
    receptionBookingsCache = bookings;

    // Cập nhật số lượng đếm trên các nút bộ lọc
    updateReceptionPillCounts();

    // Cập nhật badge số lượng check-in
    const badgeCheckin = document.getElementById("letan-badge-checkin");
    if (badgeCheckin) badgeCheckin.textContent = bookings.length;

    // Render danh sách check-in theo bộ lọc và tìm kiếm
    renderFilteredReceptionTable();

    // Danh sách Quá giờ - chưa checkout
    const overstays = bookings.filter(b => b.status === "Quá giờ - chưa checkout");
    const badgeOverstay = document.getElementById("letan-badge-overstay");
    if (badgeOverstay) {
      badgeOverstay.textContent = overstays.length;
      if (overstays.length > 0) {
        badgeOverstay.classList.add("badge-danger-alert");
      } else {
        badgeOverstay.classList.remove("badge-danger-alert");
      }
    }

    if (overstayContainer) {
      if (overstays.length === 0) {
        overstayContainer.innerHTML = `<div style="padding: 18px; color: var(--success); font-size: 13.5px; display:flex; align-items:center; gap:8px;">Không có phòng nào đang quá giờ lưu trú tại chi nhánh.</div>`;
      } else {
        overstayContainer.innerHTML = `
          <div class="table-responsive" style="border-color: rgba(198,40,40,0.3);">
            <table class="data-table">
              <thead>
                <tr style="background: var(--danger-bg);">
                  <th>Mã đơn</th>
                  <th>Phòng</th>
                  <th>Khách hàng</th>
                  <th>Hạn checkout</th>
                  <th style="text-align: right;">Hành động khẩn cấp</th>
                </tr>
              </thead>
              <tbody>
                ${overstays.map(b => `
                  <tr>
                    <td><b style="color: var(--danger);">${b.booking_code}</b></td>
                    <td><b>${b.room_id}</b></td>
                    <td>${b.customer_name} (${b.customer_phone})</td>
                    <td><span class="badge badge-danger">${b.end_time}</span></td>
                    <td style="text-align: right;">
                      <button class="btn btn-sm" style="background:#ea580c; color:#fff; font-weight:600; font-size:12px; height:28px; padding:0 12px; border:none; border-radius:6px; line-height:26px;" onclick="openReceptionEmergencyExtension('${b.booking_code}')">Gia hạn khẩn</button>
                      <button class="btn btn-sm btn-danger" style="font-weight:600; font-size:12px; height:28px; padding:0 12px; border-radius:6px; line-height:26px;" onclick="executeCheckOut('${b.booking_code}')">Trả phòng ngay</button>
                    </td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          </div>
        `;
      }
    }

    // Load đánh giá để xử lý khiếu nại (BR-12)
    loadReceptionReviews(branchParam);
  } catch (err) {
  }
}

function getBookingStatusBadge(status) {
  const s = (status || "").trim();
  if (s === "Đã xác nhận" || s === "Chờ check-in") {
    return `<span class="badge badge-warning" style="font-weight:600;">${s}</span>`;
  }
  if (s === "Đã check-in") {
    return `<span class="badge badge-success" style="font-weight:600;">${s}</span>`;
  }
  if (s === "Quá giờ - chưa checkout") {
    return `<span class="badge badge-danger" style="font-weight:600;">${s}</span>`;
  }
  if (s === "Đã hoàn tất" || s === "Hoàn tất") {
    return `<span class="badge badge-info" style="font-weight:600;">${s}</span>`;
  }
  if (s === "Đã hủy" || s === "Hết hạn giữ chỗ") {
    return `<span class="badge" style="background:#f1f5f9; color:#64748b; border:1px solid #cbd5e1; font-weight:600;">${s}</span>`;
  }
  return `<span class="badge badge-cozy">${s}</span>`;
}

function renderReceptionRow(b) {
  let actions = "—";

  if (b.status === "Đã xác nhận") {
    actions = `<button class="btn btn-sm btn-success" onclick="executeCheckIn('${b.booking_code}')" style="height:28px; padding:0 12px; font-size:12px; font-weight:600; border-radius:6px; line-height:26px;">Nhận phòng</button>`;
  } else if (b.status === "Đã check-in" || b.status === "Quá giờ - chưa checkout") {
    actions = `
      <div style="display:inline-flex; gap:6px; align-items:center;">
        <button class="btn btn-sm" style="background:#ea580c; color:#fff; font-weight:600; font-size:12px; height:28px; padding:0 10px; border:none; border-radius:6px; line-height:26px;" onclick="openReceptionEmergencyExtension('${b.booking_code}')" title="Gia hạn khẩn cấp cho khách tại quầy">Gia hạn khẩn</button>
        <button class="btn btn-sm btn-primary" onclick="executeCheckOut('${b.booking_code}')" style="height:28px; padding:0 12px; font-size:12px; font-weight:600; border-radius:6px; line-height:26px;">Trả phòng</button>
      </div>`;
  }

  const extensionBadge = b.extension_hours > 0 ? `
    <div style="margin-top:3px;">
      <span class="badge" style="background:#ecfdf5; color:#059669; border:1px solid #a7f3d0; font-size:10.5px; font-weight:700;" title="Đã gia hạn thêm ${b.extension_hours}h sang khung ${b.extended_khung || ''}">
        Check-out sau gia hạn: ${b.end_time} (+${b.extension_hours}h)
      </span>
    </div>
  ` : "";

  return `
    <tr>
      <td><b>${b.booking_code}</b></td>
      <td><b>${b.room_id}</b> <span class="badge" style="font-size:10.5px; background:#f1f5f9; color:#475569; border:1px solid #cbd5e1; margin-left:4px;" title="Cơ sở chi nhánh">${b.branch_id || ''}</span></td>
      <td>${b.customer_name}<div style="font-size:11px;color:var(--text-muted);">${b.customer_phone}</div></td>
      <td>
        <div>${b.booking_date} (${b.khung_code})</div>
        ${extensionBadge}
      </td>
      <td>
        ${getBookingStatusBadge(b.status)}
        ${b.actual_checkin ? `<div style="font-size:11px; color:#10b981; font-family:monospace; margin-top:2px;" title="Check-in thực tế">In: ${b.actual_checkin.replace('T', ' ')}</div>` : ''}
        ${b.actual_checkout ? `<div style="font-size:11px; color:#64748b; font-family:monospace; margin-top:2px;" title="Check-out thực tế">Out: ${b.actual_checkout.replace('T', ' ')}</div>` : ''}
      </td>
      <td style="text-align: right;">${actions}</td>
    </tr>
  `;
}

// -------------------------------------------------------------
// Nghiệp vụ Lễ tân: Gia hạn lưu trú khẩn cấp tại quầy (BR-06)
// -------------------------------------------------------------
let currentRecExtInfo = null;
let selectedRecExtHours = 1;

async function openReceptionEmergencyExtension(bookingCode) {
  try {
    const info = await apiFetch(`/api/bookings/${bookingCode}/check-extension?hours=1`);
    if (!info) {
      showToast("Không thể tải thông tin kiểm tra phòng gia hạn.", "error");
      return;
    }

    currentRecExtInfo = info;
    selectedRecExtHours = 1;

    const modal = document.getElementById("modal-reception-extension");
    if (!modal) return;

    const b = (receptionBookingsCache || []).find(x => x.booking_code === bookingCode);

    document.getElementById("rec-ext-code").textContent = bookingCode;
    document.getElementById("rec-ext-room").textContent = info.room_id || (b ? b.room_id : "—");
    const branchEl = document.getElementById("rec-ext-branch");
    if (branchEl) branchEl.textContent = b ? b.branch_id : "";
    document.getElementById("rec-ext-customer").textContent = b ? `${b.customer_name} (${b.customer_phone || ''})` : "Khách lưu trú";
    
    const statusBadgeEl = document.getElementById("rec-ext-status-badge");
    if (statusBadgeEl) {
      statusBadgeEl.innerHTML = getBookingStatusBadge(info.current_status || (b ? b.status : "Đang ở"));
    }

    document.getElementById("rec-ext-curr-checkout").textContent = info.current_end_time || (b ? b.end_time : "—");
    
    const slotLabel = info.next_khung_name || info.next_khung || "Khung kế tiếp";
    document.getElementById("rec-ext-next-slot").textContent = `${slotLabel} (${info.start_time}–${info.next_slot_end})`;

    const opt1 = (info.hourly_options || []).find(o => o.hours === 1);
    const opt2 = (info.hourly_options || []).find(o => o.hours === 2);
    const opt3 = (info.hourly_options || []).find(o => o.hours === 3);

    const sub1 = document.getElementById("rec-pill-sub-1");
    if (sub1) sub1.textContent = opt1 ? `Đến ${opt1.end_time}` : "+1 tiếng";
    const sub2 = document.getElementById("rec-pill-sub-2");
    if (sub2) sub2.textContent = opt2 ? `Đến ${opt2.end_time}` : "+2 tiếng";
    const sub3 = document.getElementById("rec-pill-sub-3");
    if (sub3) sub3.textContent = opt3 ? `Đến ${opt3.end_time}` : "+3 tiếng";

    selectReceptionExtHours(1);

    modal.classList.add("active");
  } catch (err) {
    showToast(err.message || "Không thể kiểm tra khả năng gia hạn.", "error");
  }
}

function selectReceptionExtHours(hours) {
  selectedRecExtHours = Number(hours) || 1;
  if (!currentRecExtInfo) return;

  [1, 2, 3].forEach(h => {
    const btn = document.getElementById(`btn-rec-ext-${h}`);
    if (btn) {
      if (h === selectedRecExtHours) btn.classList.add("active");
      else btn.classList.remove("active");
    }
  });

  const opts = currentRecExtInfo.hourly_options || [];
  const currentOpt = opts.find(o => o.hours === selectedRecExtHours) || {
    hours: selectedRecExtHours,
    amount: (currentRecExtInfo.hourly_rate || 50000) * selectedRecExtHours,
    end_time: currentRecExtInfo.new_end_time,
    is_available: currentRecExtInfo.is_available,
    reason: currentRecExtInfo.reason,
  };

  const newCheckoutEl = document.getElementById("rec-ext-new-checkout");
  if (newCheckoutEl) newCheckoutEl.textContent = `${currentOpt.end_time} (+${selectedRecExtHours} tiếng)`;

  const amountEl = document.getElementById("rec-ext-amount");
  if (amountEl) amountEl.textContent = formatMoney(currentOpt.amount);

  const alertEl = document.getElementById("rec-ext-alert");
  const confirmBtn = document.getElementById("btn-confirm-rec-ext");

  if (currentOpt.is_available) {
    if (alertEl) {
      alertEl.innerHTML = `<span style="font-size:12px; color:#065f46; font-weight:600;">Khung kế tiếp trống. Hệ thống sẽ tự động khóa phòng trên lịch chung ngay khi xác nhận.</span>`;
    }
    if (confirmBtn) {
      confirmBtn.disabled = false;
      confirmBtn.style.opacity = "1";
      confirmBtn.style.cursor = "pointer";
      confirmBtn.textContent = `Xác nhận gia hạn khẩn cấp • Check-out lúc ${currentOpt.end_time}`;
    }
  } else {
    if (alertEl) {
      alertEl.innerHTML = `<span style="font-size:12px; color:#dc2626; font-weight:600;">${currentOpt.reason || "Khung kế tiếp đã có người đặt trước hoặc không khả dụng."}</span>`;
    }
    if (confirmBtn) {
      confirmBtn.disabled = true;
      confirmBtn.style.opacity = "0.5";
      confirmBtn.style.cursor = "not-allowed";
      confirmBtn.textContent = `Không thể gia hạn (Khung kế tiếp đã kín)`;
    }
  }
}

function closeReceptionExtModal() {
  const modal = document.getElementById("modal-reception-extension");
  if (modal) modal.classList.remove("active");
  currentRecExtInfo = null;
}

async function confirmReceptionEmergencyExtension() {
  if (!currentRecExtInfo) return;
  const bookingCode = document.getElementById("rec-ext-code").textContent.trim();
  const paymentMethodInput = document.querySelector('input[name="rec-payment-method"]:checked');
  const paymentMethod = paymentMethodInput ? paymentMethodInput.value : "Tiền mặt tại quầy";
  const note = (document.getElementById("rec-ext-note").value || "").trim();

  const confirmBtn = document.getElementById("btn-confirm-rec-ext");
  if (confirmBtn) {
    confirmBtn.disabled = true;
    confirmBtn.innerHTML = `Đang xử lý gia hạn...`;
  }

  try {
    const res = await apiFetch("/api/operations/emergency-extend", {
      method: "POST",
      body: {
        booking_code: bookingCode,
        hours: selectedRecExtHours,
        payment_method: paymentMethod,
        note: note,
      }
    });

    closeReceptionExtModal();
    showToast(res.message || `Đã gia hạn thành công! Giờ check-out mới: ${res.new_end_time}`, "success");
    loadReceptionistData();
  } catch (err) {
    showToast(err.message || "Gia hạn khẩn cấp thất bại.", "error");
    if (confirmBtn) {
      confirmBtn.disabled = false;
      confirmBtn.innerHTML = `⚡ Xác nhận gia hạn khẩn cấp`;
    }
  }
}

async function executeCheckIn(bookingCode) {
  // Kiểm tra an toàn vận hành: Cảnh báo nếu buồng phòng chưa 'Sẵn sàng'
  const booking = (receptionBookingsCache || []).find(b => b.booking_code === bookingCode);
  if (booking) {
    try {
      const resHk = await apiFetch(`/api/operations/housekeeping?branch_id=${booking.branch_id || ""}`);
      const ops = resHk.operations || [];
      const op = ops.find(o => o.room_id === booking.room_id);
      const roomStatus = op ? op.status : "Sẵn sàng";
      if (roomStatus !== "Sẵn sàng") {
        const confirmCheckin = confirm(
          `⚠️ CẢNH BÁO BUỒNG PHÒNG:\nPhòng ${booking.room_id} hiện chưa ở trạng thái 'Sẵn sàng' (Trạng thái hiện tại: '${roomStatus}').\n\nBạn có chắc chắn muốn tiến hành Check-in cho khách ${booking.customer_name} ngay không?`
        );
        if (!confirmCheckin) return;
      }
    } catch (e) {
      // Bỏ qua lỗi phụ để không cản trở check-in khẩn cấp
    }
  }

  try {
    const res = await apiFetch("/api/operations/check-in", {
      method: "POST",
      body: { booking_code: bookingCode },
    });
    const timeNow = new Date().toLocaleTimeString('vi-VN');
    showToast(`${res.message} (Ghi nhận lúc ${timeNow})`, "success");
    loadReceptionistData();
    if (typeof loadHousekeepingData === "function" && opsCurrentTab === "buong") {
      loadHousekeepingData();
    }
  } catch (err) {
  }
}

async function executeCheckOut(bookingCode) {
  try {
    const res = await apiFetch("/api/operations/check-out", {
      method: "POST",
      body: { booking_code: bookingCode, staff_name: state.user.full_name },
    });
    const timeNow = new Date().toLocaleTimeString('vi-VN');
    showToast(`${res.message} (Ghi nhận lúc ${timeNow})`, "success");
    loadReceptionistData();
  } catch (err) {
  }
}

let receptionReviewsCache = [];

function parseReviewMedia(raw) {
  if (!raw) return [];
  if (Array.isArray(raw)) return raw;
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) return parsed;
  } catch (e) {}
  if (typeof raw === "string" && raw.includes(",")) {
    return raw.split(",").map(s => s.trim()).filter(Boolean);
  }
  return [String(raw).trim()].filter(Boolean);
}

function filterReceptionReviewsTable() {
  renderReceptionReviewsTable();
}

function openEvidenceModal(reviewId) {
  const r = (receptionReviewsCache || []).find(item => item.id === reviewId);
  if (!r) return;
  const modal = document.getElementById("modal-evidence-preview");
  if (!modal) return;

  const titleEl = document.getElementById("evidence-modal-title");
  const subEl = document.getElementById("evidence-modal-subtitle");
  const bodyEl = document.getElementById("evidence-modal-body");
  const captionEl = document.getElementById("evidence-modal-caption");

  if (titleEl) titleEl.textContent = `Minh chứng đơn ${r.booking_code}`;
  if (subEl) subEl.textContent = `Khách: ${r.user_name || 'Khách hàng'} • Phòng: ${r.room_id || 'N/A'}`;

  const mediaList = parseReviewMedia(r.media_urls);
  if (mediaList.length === 0) {
    bodyEl.innerHTML = `<p style="color:#94a3b8; padding:30px;">Không có hình ảnh hoặc video minh chứng đính kèm.</p>`;
  } else {
    bodyEl.innerHTML = `
      <div style="display:flex; flex-direction:column; gap:16px; align-items:center; justify-content:center;">
        ${mediaList.map((url, idx) => {
          const isVideo = url.endsWith(".mp4") || url.endsWith(".webm") || url.includes("video");
          if (isVideo) {
            return `
              <div style="width:100%; max-width:600px;">
                <video controls style="width:100%; border-radius:8px; max-height:420px; background:#000;">
                  <source src="${url}" type="video/mp4">
                  Trình duyệt không hỗ trợ xem video.
                </video>
                <div style="color:#94a3b8; font-size:12px; margin-top:4px;">Video minh chứng #${idx + 1}</div>
              </div>
            `;
          } else {
            return `
              <div style="width:100%; max-width:600px; text-align:center;">
                <a href="${url}" target="_blank" title="Mở ảnh gốc trong tab mới">
                  <img src="${url}" alt="Minh chứng" style="max-width:100%; max-height:450px; object-fit:contain; border-radius:8px; box-shadow:0 8px 20px rgba(0,0,0,0.5);" />
                </a>
                <div style="color:#94a3b8; font-size:12px; margin-top:6px;">Hình ảnh minh chứng #${idx + 1} (Bấm vào ảnh để xem kích thước đầy đủ)</div>
              </div>
            `;
          }
        }).join("")}
      </div>
    `;
  }

  if (captionEl) {
    captionEl.textContent = `Nội dung phản hồi: "${r.content}"`;
  }

  modal.style.display = "flex";
}

function closeEvidenceModal() {
  const modal = document.getElementById("modal-evidence-preview");
  if (modal) modal.style.display = "none";
}

function renderReceptionReviewsTable() {
  const container = document.getElementById("ops-reception-reviews");
  if (!container) return;

  const kw = (document.getElementById("letan-review-search-input")?.value || "").toLowerCase().trim();

  let list = receptionReviewsCache || [];
  if (kw) {
    list = list.filter(r => 
      (r.booking_code || "").toLowerCase().includes(kw) ||
      (r.room_id || "").toLowerCase().includes(kw) ||
      (r.user_name || "").toLowerCase().includes(kw) ||
      (r.user_phone || "").toLowerCase().includes(kw) ||
      (r.content || "").toLowerCase().includes(kw)
    );
  }

  if (list.length === 0) {
    container.innerHTML = `<div style="padding:28px 16px; text-align:center; color:var(--text-muted); font-size:13.5px;">Không tìm thấy đánh giá hoặc phản hồi nào phù hợp.</div>`;
    return;
  }

  container.innerHTML = `
    <div class="table-responsive">
      <table class="data-table">
        <thead>
          <tr>
            <th>Đơn đặt</th>
            <th>Khách hàng</th>
            <th>Mức độ hài lòng</th>
            <th>Nội dung đánh giá & phản hồi</th>
            <th>Hình ảnh / Video minh chứng</th>
            <th>Tình trạng xử lý</th>
            <th style="text-align: right;">Hành động</th>
          </tr>
        </thead>
        <tbody>
          ${list.map(r => {
            const isEscalated = r.escalated === 1;

            const stars = `<div style="color:#f59e0b; font-size:13px; font-weight:700; white-space:nowrap;">
              ${"★".repeat(r.rating)}${"<span style='color:#cbd5e1;'>★</span>".repeat(Math.max(0, 5 - r.rating))}
              <span style="font-size:12px; color:var(--text-muted); font-weight:600; margin-left:2px;">(${r.rating}/5)</span>
            </div>`;

            const mediaList = parseReviewMedia(r.media_urls);
            let mediaHtml = `<span style="color:var(--text-muted); font-size:12px;">—</span>`;
            if (mediaList.length > 0) {
              const firstMedia = mediaList[0];
              const isVideo = firstMedia.endsWith(".mp4") || firstMedia.endsWith(".webm") || firstMedia.includes("video");
              mediaHtml = `
                <div style="display:inline-flex; align-items:center; gap:8px; cursor:pointer;" onclick="openEvidenceModal(${r.id})" title="Nhấn để xem phóng to minh chứng">
                  <div style="position:relative; width:44px; height:44px; border-radius:6px; overflow:hidden; border:1px solid #cbd5e1; background:#0f172a; flex-shrink:0;">
                    ${isVideo 
                      ? `<div style="display:flex; align-items:center; justify-content:center; width:100%; height:100%; color:#fff; font-size:18px;">▶</div>` 
                      : `<img src="${firstMedia}" alt="Minh chứng" style="width:100%; height:100%; object-fit:cover;" />`
                    }
                  </div>
                  <div>
                    <span class="badge ${isVideo ? 'badge-warning' : 'badge-info'}" style="font-size:11px; padding:2px 6px; white-space:nowrap;">
                      ${isVideo ? '🎥 Video' : `📷 ${mediaList.length} ảnh`}
                    </span>
                    <div style="font-size:11px; color:#2563eb; text-decoration:underline; margin-top:2px;">Xem minh chứng</div>
                  </div>
                </div>
              `;
            }

            let processStatus = "";
            if (isEscalated) {
              if (r.resolved === 1) {
                processStatus = `
                  <span class="badge badge-success" style="font-size:11px; font-weight:600;">✓ Quản lý đã giải quyết</span>
                  ${r.resolution_note ? `<div style="font-size:11px; color:#15803d; margin-top:3px; max-width:210px; line-height:1.3;" title="${r.resolution_note}">Giải pháp: ${r.resolution_note}</div>` : ''}
                `;
              } else {
                processStatus = `
                  <span class="badge badge-warning" style="font-size:11px; font-weight:600;">Chờ Quản lý xử lý</span>
                `;
              }
            } else {
              if (r.rating >= 4) {
                processStatus = `<span class="badge badge-success" style="font-size:11px; font-weight:600;">Khách hài lòng</span>`;
              } else {
                processStatus = `<span class="badge badge-cozy" style="font-size:11px; font-weight:600;">Cần lưu ý</span>`;
              }
            }

            let actionHtml = "";
            if (isEscalated) {
              actionHtml = `<span style="color:var(--text-muted); font-size:12px; font-style:italic;">Đã chuyển Quản lý</span>`;
            } else {
              actionHtml = `<button class="btn btn-sm btn-outline" onclick="promptEscalateReview(${r.id})" style="border-color:#ea580c; color:#ea580c; font-size:11.5px; padding:3px 8px; white-space:nowrap;" title="Chuyển phản hồi vượt thẩm quyền lên Quản lý chuỗi giải quyết">Chuyển Quản lý</button>`;
            }

            return `
              <tr>
                <td>
                  <b>${r.booking_code}</b>
                  ${r.room_id ? `<div style="font-size:11.5px; color:var(--text-muted); font-weight:600;">Phòng: ${r.room_id}</div>` : ''}
                </td>
                <td>
                  ${r.user_name || "Khách hàng"}
                  ${r.user_phone ? `<div style="font-size:11px; color:var(--text-muted);">${r.user_phone}</div>` : ''}
                </td>
                <td>${stars}</td>
                <td style="max-width: 260px;">
                  <div style="font-size:12.5px; line-height:1.4;">${r.content}</div>
                  ${isEscalated && r.escalation_note ? `
                    <div style="margin-top:6px; padding:4px 8px; background:#fff7ed; border-left:3px solid #f97316; border-radius:4px; font-size:11.5px; color:#9a3412; line-height:1.35;">
                      <b>Ghi chú chuyển:</b> ${r.escalation_note}
                    </div>
                  ` : ''}
                </td>
                <td>${mediaHtml}</td>
                <td>${processStatus}</td>
                <td style="text-align: right;">${actionHtml}</td>
              </tr>
            `;
          }).join("")}
        </tbody>
      </table>
    </div>
  `;
}

async function loadReceptionReviews(branchId) {
  const container = document.getElementById("ops-reception-reviews");
  if (!container) return;

  try {
    const res = await apiFetch(`/api/operations/reviews?branch_id=${branchId || ""}`);
    receptionReviewsCache = res.reviews || [];

    // Cập nhật badge số lượng đánh giá
    const badgeReviews = document.getElementById("letan-badge-reviews");
    if (badgeReviews) badgeReviews.textContent = receptionReviewsCache.length;

    // Render bảng đánh giá & phản hồi
    renderReceptionReviewsTable();
  } catch (err) {
    container.innerHTML = `<p style="color:var(--danger); padding:12px;">Lỗi tải dữ liệu đánh giá: ${err.message}</p>`;
  }
}

async function promptEscalateReview(reviewId) {
  const note = prompt("Nhập lý do chuyển khiếu nại lên Quản lý chuỗi:");
  if (!note || !note.trim()) return;

  try {
    const res = await apiFetch("/api/operations/escalate-review", {
      method: "POST",
      body: { review_id: reviewId, note: note.trim() },
    });
    showToast(res.message, "success");
    loadReceptionistData();
  } catch (err) {
  }
}

// -------------------------------------------------------------
// 2. Buồng phòng (Housekeeping - BR-08, UC-04.4)
// -------------------------------------------------------------
let hkState = {
  rooms: [],
  operations: [],
  todayBookings: {},
  filterStatus: "ALL",
  searchKeyword: ""
};

function onHousekeepingSearchChange(val) {
  hkState.searchKeyword = (val || "").trim().toLowerCase();
  const clearBtn = document.getElementById("hk-search-clear-btn");
  if (clearBtn) {
    clearBtn.style.display = val ? "inline-block" : "none";
  }
  renderHousekeepingCards();
}

function clearHousekeepingSearch() {
  const searchInput = document.getElementById("hk-search-input");
  const clearBtn = document.getElementById("hk-search-clear-btn");
  if (searchInput) {
    searchInput.value = "";
    searchInput.focus();
  }
  if (clearBtn) clearBtn.style.display = "none";
  hkState.searchKeyword = "";
  renderHousekeepingCards();
}

async function resetAndRefreshHousekeeping(btn) {
  const searchInput = document.getElementById("hk-search-input");
  const clearBtn = document.getElementById("hk-search-clear-btn");
  if (searchInput) searchInput.value = "";
  if (clearBtn) clearBtn.style.display = "none";
  hkState.searchKeyword = "";

  // Reset tab về 'Tất cả'
  hkState.filterStatus = "ALL";
  const pills = document.querySelectorAll("#hk-filter-pills-container .hk-tab-btn");
  pills.forEach(p => {
    if (p.getAttribute("data-hkfilter") === "ALL") {
      p.classList.add("active");
    } else {
      p.classList.remove("active");
    }
  });

  if (btn) btn.classList.add("btn-loading");
  try {
    await loadHousekeepingData();
    showToast("Đã làm mới dữ liệu và xóa bộ lọc tìm kiếm", "success");
  } finally {
    if (btn) btn.classList.remove("btn-loading");
  }
}

function setHousekeepingFilter(filter) {
  hkState.filterStatus = filter;
  const pills = document.querySelectorAll("#hk-filter-pills-container .hk-tab-btn");
  pills.forEach(p => {
    if (p.getAttribute("data-hkfilter") === filter) {
      p.classList.add("active");
    } else {
      p.classList.remove("active");
    }
  });
  renderHousekeepingCards();
}

async function loadHousekeepingData() {
  const container = document.getElementById("ops-housekeeping-grid");
  if (!container) return;

  const effRole = typeof getEffectiveRole === "function" ? getEffectiveRole() : state.user.role;
  const isDemo = typeof isDemoAccount === "function" && isDemoAccount(state.user);
  const isAdminOrManager = effRole === COZY_ROLES.ADMIN || effRole === COZY_ROLES.MANAGER || isDemo;
  const branchWrap = document.getElementById("hk-branch-selector-wrap");
  const branchSelect = document.getElementById("hk-branch-select");

  if (branchWrap) {
    branchWrap.style.display = isAdminOrManager ? "block" : "none";
  }

  let branchId = "";
  if (isAdminOrManager && branchSelect) {
    branchId = branchSelect.value;
  } else {
    branchId = state.user.branch_id || "";
  }

  try {
    const res = await apiFetch(`/api/operations/housekeeping?branch_id=${branchId || ""}`);
    hkState.rooms = res.rooms || [];
    hkState.operations = res.operations || [];
    hkState.todayBookings = res.today_bookings || {};

    updateHousekeepingKPIs();
    renderHousekeepingCards();
  } catch (err) {
    console.error("Lỗi tải dữ liệu buồng phòng:", err);
  }
}

function updateHousekeepingKPIs() {
  const opMap = {};
  hkState.operations.forEach(o => { opMap[o.room_id] = o; });

  let counts = {
    total: hkState.rooms.length,
    need: 0,
    cleaning: 0,
    ready: 0,
    maint: 0
  };

  hkState.rooms.forEach(r => {
    const op = opMap[r.room_id];
    const status = op ? op.status : (r.operational_status || "Sẵn sàng");
    if (status === "Cần dọn") counts.need++;
    else if (status === "Đang dọn") counts.cleaning++;
    else if (status === "Sẵn sàng" || status === "Đã vệ sinh") counts.ready++;
    else if (status === "Bảo trì") counts.maint++;
  });

  const elAll = document.getElementById("hk-count-all");
  const elNeed = document.getElementById("hk-count-need");
  const elCleaning = document.getElementById("hk-count-cleaning");
  const elReady = document.getElementById("hk-count-ready");
  const elMaint = document.getElementById("hk-count-maint");

  if (elAll) elAll.textContent = counts.total;
  if (elNeed) elNeed.textContent = counts.need;
  if (elCleaning) elCleaning.textContent = counts.cleaning;
  if (elReady) elReady.textContent = counts.ready;
  if (elMaint) elMaint.textContent = counts.maint;
}

function formatKhungGioTiet(khungCode, startTime, endTime) {
  if (!khungCode) return "";
  const code = String(khungCode).toUpperCase().trim();
  let name = "";
  if (code.includes("K1") || code.includes("SÁNG") || code.includes("SANG")) name = "Khung sáng";
  else if (code.includes("K2") || code.includes("CHIỀU") || code.includes("CHIEU")) name = "Khung chiều";
  else if (code.includes("K3") || code.includes("TỐI") || code.includes("TOI")) name = "Khung tối";
  else if (code.includes("QD") || code.includes("K4") || code.includes("ĐÊM") || code.includes("DEM")) name = "Khung qua đêm";
  else name = `Khung giờ ${khungCode}`;

  let timeRange = "";
  if (startTime && endTime) {
    const s = startTime.includes("T") ? startTime.split("T")[1].substring(0, 5) : startTime.substring(0, 5);
    const e = endTime.includes("T") ? endTime.split("T")[1].substring(0, 5) : endTime.substring(0, 5);
    timeRange = `${s} – ${e}`;
  } else {
    if (code.includes("K1")) timeRange = "09:00 – 12:00";
    else if (code.includes("K2")) timeRange = "13:00 – 16:00";
    else if (code.includes("K3")) timeRange = "17:00 – 20:00";
    else if (code.includes("QD") || code.includes("K4")) timeRange = "21:30 – 08:30";
  }

  return timeRange ? `${name} (${timeRange})` : name;
}

function renderHousekeepingCards() {
  const container = document.getElementById("ops-housekeeping-grid");
  if (!container) return;

  const opMap = {};
  hkState.operations.forEach(o => { opMap[o.room_id] = o; });

  const statusBadgeMap = {
    "Cần dọn": "hk-badge-need",
    "Đang dọn": "hk-badge-cleaning",
    "Đã vệ sinh": "hk-badge-inspected",
    "Sẵn sàng": "hk-badge-ready",
    "Bảo trì": "hk-badge-maint"
  };

  const statusBorderMap = {
    "Cần dọn": "border-need",
    "Đang dọn": "border-cleaning",
    "Đã vệ sinh": "border-inspected",
    "Sẵn sàng": "border-ready",
    "Bảo trì": "border-maint"
  };

  let filtered = hkState.rooms.filter(r => {
    const op = opMap[r.room_id];
    const status = op ? op.status : (r.operational_status || "Sẵn sàng");

    if (hkState.filterStatus !== "ALL" && status !== hkState.filterStatus) {
      return false;
    }

    if (hkState.searchKeyword) {
      const q = hkState.searchKeyword;
      const matchRoom = (r.room_name || "").toLowerCase().includes(q) ||
                        (r.room_id || "").toLowerCase().includes(q) ||
                        (r.room_type || "").toLowerCase().includes(q) ||
                        (r.branch_name || "").toLowerCase().includes(q);
      
      const bookings = hkState.todayBookings[r.room_id] || [];
      const matchBooking = bookings.some(b => 
        (b.customer_name || "").toLowerCase().includes(q) ||
        (b.customer_phone || "").includes(q) ||
        (b.booking_code || "").toLowerCase().includes(q)
      );

      if (!matchRoom && !matchBooking) return false;
    }

    return true;
  });

  if (filtered.length === 0) {
    container.innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; padding: 48px 16px; background: #ffffff; border-radius: 12px; border: 1px dashed var(--cozy-border); color: var(--text-muted);">
        <div style="font-size: 15px; font-weight: 700; color: var(--cozy-dark);">Không có phòng nào trong danh mục này</div>
        <div style="font-size: 12.5px; margin-top: 4px;">Chọn mục 'Tất cả' để xem toàn bộ danh sách buồng phòng.</div>
      </div>
    `;
    return;
  }

  container.innerHTML = filtered.map(r => {
    const op = opMap[r.room_id];
    const curStatus = op ? op.status : (r.operational_status || "Sẵn sàng");
    const badgeClass = statusBadgeMap[curStatus] || "hk-badge-ready";
    const borderClass = statusBorderMap[curStatus] || "border-ready";

    const bookings = hkState.todayBookings[r.room_id] || [];
    const upcomingGuest = bookings.find(b => b.status === "Đã xác nhận");
    const checkoutGuest = bookings.find(b => b.status === "Đã hoàn tất");

    // Dải thông tin bổ trợ (Gọn gàng, phân biệt màu sắc, ghi rõ tên khung giờ không dùng ký hiệu)
    let contextAlertHtml = "";
    if (curStatus === "Bảo trì") {
      contextAlertHtml = `
        <div style="background:#faf5ff; border:1px solid #e9d5ff; border-radius:8px; padding:8px 10px; font-size:12px; color:#5b21b6; margin-bottom:12px;">
          <b>Lý do bảo trì:</b> ${op?.note || "Đang chờ bảo dưỡng kỹ thuật"}
        </div>
      `;
    } else if (curStatus === "Cần dọn" && upcomingGuest) {
      const khungStr = formatKhungGioTiet(upcomingGuest.khung_code, upcomingGuest.start_time, upcomingGuest.end_time);
      contextAlertHtml = `
        <div style="background:#fff7ed; border:1px solid #fed7aa; border-radius:8px; padding:6px 10px; font-size:12px; color:#9a3412; margin-bottom:12px;">
          <b>Ưu tiên dọn trước:</b> Khách ${upcomingGuest.customer_name} nhận phòng - ${khungStr}
        </div>
      `;
    } else if (checkoutGuest && curStatus === "Cần dọn") {
      const outTime = checkoutGuest.actual_checkout ? checkoutGuest.actual_checkout.split("T")[1]?.substring(0, 5) : "";
      contextAlertHtml = `
        <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:6px 10px; font-size:12px; color:#475569; margin-bottom:12px;">
          Khách vừa trả phòng ${outTime ? `lúc ${outTime}` : ""}. Cần vệ sinh phòng.
        </div>
      `;
    }

    // Nút hành động chính theo luồng nghiệp vụ buồng phòng chuẩn (Phân màu chuẩn theo từng trạng thái)
    let mainActionBtn = "";
    if (curStatus === "Cần dọn") {
      mainActionBtn = `<button class="btn btn-hk-need" style="width:100%; height:38px; font-weight:700; font-size:13px;" onclick="advanceHousekeepingStep('${r.room_id}', '${r.branch_id}', 'Đang dọn')">Bắt đầu dọn</button>`;
    } else if (curStatus === "Đang dọn") {
      mainActionBtn = `<button class="btn btn-hk-ready" style="width:100%; height:38px; font-weight:700; font-size:13px;" onclick="advanceHousekeepingStep('${r.room_id}', '${r.branch_id}', 'Sẵn sàng')">Hoàn tất dọn phòng</button>`;
    } else if (curStatus === "Đã vệ sinh") {
      mainActionBtn = `<button class="btn btn-hk-ready" style="width:100%; height:38px; font-weight:700; font-size:13px;" onclick="advanceHousekeepingStep('${r.room_id}', '${r.branch_id}', 'Sẵn sàng')">Xác nhận sẵn sàng</button>`;
    } else if (curStatus === "Sẵn sàng") {
      mainActionBtn = `<div style="text-align:center; padding:9px 12px; font-weight:700; color:#15803d; background:#f0fdf4; border-radius:8px; border:1px solid #86efac; font-size:13px;">Phòng sẵn sàng đón khách</div>`;
    } else if (curStatus === "Bảo trì") {
      mainActionBtn = `<button class="btn btn-hk-maint" style="width:100%; height:38px; font-weight:700; font-size:13px;" onclick="advanceHousekeepingStep('${r.room_id}', '${r.branch_id}', 'Cần dọn')">Hoàn tất sửa chữa</button>`;
    } else {
      mainActionBtn = `<button class="btn btn-outline" style="width:100%; height:38px; font-weight:600; font-size:13px;" onclick="advanceHousekeepingStep('${r.room_id}', '${r.branch_id}', 'Đang dọn')">Dọn phòng</button>`;
    }

    // Các nút chức năng phụ rõ ràng, bấm được 100% (Không dùng icon)
    let extraActions = "";
    if (curStatus === "Bảo trì") {
      extraActions = `
        <button type="button" class="btn btn-sm btn-outline" style="font-size:11.5px; padding:3px 10px; border-color:#c4b5fd; color:#7c3aed; font-weight:700; cursor:pointer;" onclick="openHousekeepingModal('${r.room_id}', '${r.branch_id}', '${r.room_name}', 'MAINTENANCE')">Đổi lý do bảo trì</button>
        <span style="font-size:11px; color:var(--text-muted);">${op?.updated_by || 'Kỹ thuật'}</span>
      `;
    } else if (curStatus === "Sẵn sàng") {
      extraActions = `
        <button type="button" class="btn btn-sm btn-outline" style="font-size:11.5px; padding:3px 10px; border-color:#e2e8f0; color:var(--text-muted); cursor:pointer;" onclick="advanceHousekeepingStep('${r.room_id}', '${r.branch_id}', 'Cần dọn')">Yêu cầu dọn lại</button>
        <button type="button" class="btn btn-sm btn-outline" style="font-size:11.5px; padding:3px 10px; border-color:#c4b5fd; color:#7c3aed; font-weight:700; cursor:pointer;" onclick="openHousekeepingModal('${r.room_id}', '${r.branch_id}', '${r.room_name}', 'MAINTENANCE')">Báo bảo trì</button>
      `;
    } else {
      extraActions = `
        <button type="button" class="btn btn-sm btn-outline" style="font-size:11.5px; padding:3px 10px; border-color:#c4b5fd; color:#7c3aed; font-weight:700; cursor:pointer;" onclick="openHousekeepingModal('${r.room_id}', '${r.branch_id}', '${r.room_name}', 'MAINTENANCE')">Báo bảo trì</button>
        <button type="button" class="btn btn-sm btn-outline" style="font-size:11.5px; padding:3px 10px; border-color:#cbd5e1; color:#475569; cursor:pointer;" onclick="openHousekeepingModal('${r.room_id}', '${r.branch_id}', '${r.room_name}', 'NOTE')">Ghi chú</button>
      `;
    }

    const lastTimeStr = op?.updated_at ? op.updated_at.replace('T', ' ').substring(11, 16) : '';
    const lastStaffStr = op ? op.updated_by : 'Mới';

    return `
      <div class="hk-clean-card ${borderClass}">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:10px;">
          <div>
            <h4 style="margin:0; font-size:16px; font-weight:800; color:var(--cozy-dark);">${r.room_name}</h4>
            <div style="font-size:12px; color:var(--text-muted); margin-top:3px;">${r.branch_name} - ${r.room_type}</div>
          </div>
          <span class="badge ${badgeClass}">${curStatus}</span>
        </div>

        ${contextAlertHtml}

        <div style="font-size:11.5px; color:var(--text-muted); margin-bottom:14px; display:flex; justify-content:space-between; align-items:center;">
          <span>Cập nhật: <b>${lastStaffStr}</b></span>
          ${lastTimeStr ? `<span style="font-family:monospace;">${lastTimeStr}</span>` : ''}
        </div>

        <div style="margin-top:auto;">
          ${mainActionBtn}
          <div style="display:flex; justify-content:space-between; align-items:center; margin-top:10px; padding-top:8px; border-top:1px dashed #f1f5f9;">
            ${extraActions}
          </div>
        </div>
      </div>
    `;
  }).join("");
}

async function advanceHousekeepingStep(roomId, branchId, newStatus, customNote) {
  try {
    const res = await apiFetch("/api/operations/housekeeping", {
      method: "POST",
      body: {
        room_id: roomId,
        branch_id: branchId,
        status: newStatus,
        note: customNote || `Chuyển trạng thái sang ${newStatus}`,
        updated_by: state.user.full_name || "Nhân viên buồng phòng",
      },
    });
    const timeNow = new Date().toLocaleTimeString('vi-VN');
    showToast(`${res.message} (Ghi nhận lúc ${timeNow})`, "success");
    loadHousekeepingData();
  } catch (err) {
    console.error("Lỗi cập nhật buồng phòng:", err);
  }
}

// Alias tương thích ngược cho các hàm gọi cũ
async function updateHousekeeping(roomId, branchId, newStatus) {
  await advanceHousekeepingStep(roomId, branchId, newStatus);
}

function openHousekeepingModal(roomId, branchId, roomName, actionType) {
  const modal = document.getElementById("modal-housekeeping-action");
  if (!modal) return;

  const rIdInput = document.getElementById("modal-hk-room-id");
  const bIdInput = document.getElementById("modal-hk-branch-id");
  const actInput = document.getElementById("modal-hk-action-type");
  const rInfo = document.getElementById("modal-hk-room-info");

  if (rIdInput) rIdInput.value = roomId;
  if (bIdInput) bIdInput.value = branchId;
  if (actInput) actInput.value = actionType;
  if (rInfo) rInfo.textContent = `${roomName} (Mã phòng: ${roomId})`;

  const titleEl = document.getElementById("modal-hk-title");
  const labelEl = document.getElementById("modal-hk-label");
  const submitBtn = document.getElementById("modal-hk-submit-btn");
  const noteInput = document.getElementById("modal-hk-note-input");
  const quickOptions = document.getElementById("modal-hk-quick-options");

  if (actionType === "MAINTENANCE") {
    if (titleEl) titleEl.textContent = "Báo cáo bảo trì phòng";
    if (labelEl) labelEl.textContent = "Nhập lý do bảo trì chi tiết:";
    if (quickOptions) quickOptions.style.display = "block";
    if (submitBtn) {
      submitBtn.textContent = "Xác nhận chuyển bảo trì";
      submitBtn.className = "btn btn-hk-maint";
    }
    if (noteInput) {
      const op = hkState.operations.find(o => o.room_id === roomId);
      noteInput.placeholder = "Nhập cụ thể sự cố cần kỹ thuật xử lý...";
      noteInput.value = (op && op.status === "Bảo trì" && op.note) ? op.note : "";
    }
  } else {
    if (titleEl) titleEl.textContent = "Ghi chú buồng phòng";
    if (labelEl) labelEl.textContent = "Nhập nội dung ghi chú:";
    if (quickOptions) quickOptions.style.display = "none";
    if (submitBtn) {
      submitBtn.textContent = "Lưu ghi chú";
      submitBtn.className = "btn btn-primary";
    }
    if (noteInput) {
      noteInput.placeholder = "Nhập ghi chú cho phòng...";
      noteInput.value = "";
    }
  }

  modal.classList.add("active");
  modal.style.display = "flex";
  modal.style.opacity = "1";
  modal.style.pointerEvents = "auto";
  if (noteInput) {
    setTimeout(() => noteInput.focus(), 60);
  }
}

function closeHousekeepingModal() {
  const modal = document.getElementById("modal-housekeeping-action");
  if (modal) {
    modal.classList.remove("active");
    modal.style.display = "none";
    modal.style.opacity = "0";
    modal.style.pointerEvents = "none";
  }
}

function fillHkQuickNote(text) {
  const input = document.getElementById("modal-hk-note-input");
  if (input) {
    input.value = text;
    input.focus();
  }
}

async function submitHousekeepingModal() {
  const roomId = document.getElementById("modal-hk-room-id")?.value;
  const branchId = document.getElementById("modal-hk-branch-id")?.value;
  const actionType = document.getElementById("modal-hk-action-type")?.value;
  const noteVal = document.getElementById("modal-hk-note-input")?.value.trim();

  if (!noteVal) {
    showToast(actionType === "MAINTENANCE" ? "Vui lòng nhập lý do bảo trì." : "Vui lòng nhập nội dung ghi chú.", "warning");
    return;
  }

  const op = hkState.operations.find(o => o.room_id === roomId);
  const curStatus = op ? op.status : "Cần dọn";
  const newStatus = actionType === "MAINTENANCE" ? "Bảo trì" : curStatus;

  closeHousekeepingModal();
  await advanceHousekeepingStep(roomId, branchId, newStatus, noteVal);
}

// -------------------------------------------------------------
// Tiện ích xuất dữ liệu bảng tính CSV chuẩn UTF-8 BOM (Excel tiếng Việt không lỗi font)
// -------------------------------------------------------------
function exportToCSV(filename, headers, rows) {
  const escapeCell = (val) => {
    if (val === null || val === undefined) return '""';
    const str = String(val).replace(/"/g, '""');
    return `"${str}"`;
  };

  const headerLine = headers.map(h => escapeCell(h)).join(",");
  const rowLines = rows.map(row => row.map(cell => escapeCell(cell)).join(","));
  const csvContent = "\uFEFF" + [headerLine, ...rowLines].join("\r\n");

  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.setAttribute("href", url);
  link.setAttribute("download", filename.endsWith(".csv") ? filename : `${filename}.csv`);
  link.style.visibility = "hidden";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

// -------------------------------------------------------------
// 3. Kế toán & Đối soát theo kỳ (Accounting Reconciliation - BR-09, UC-08.2)
// -------------------------------------------------------------
let actTransactionsCache = [];
let actFilteredCache = [];
let actPeriodsCache = [];
let actCurrentPeriodCode = "KY-2026-09";
let actCurrentMatchFilter = "all"; // 'all' | 'matched' | 'discrepancy' | 'pending' | 'reconciled'
let actCurrentPage = 1;
let actPageSize = 25;
let actSortAsc = true; // Mặc định sắp xếp theo ID nhỏ nhất đến lớn nhất (thời gian)
let currentReconcileDetailTxId = null;

async function loadAccountingData() {
  const container = document.getElementById("ops-accounting-table");
  if (!container) return;

  try {
    // 1. Tải danh sách kỳ đối soát nếu chưa có hoặc cập nhật lại
    try {
      const perRes = await apiFetch("/api/operations/accounting/periods");
      actPeriodsCache = perRes.periods || [];
      updateAccountingPeriodDropdown();
    } catch (e) {
      console.warn("Không thể tải danh sách kỳ đối soát:", e);
    }

    // 2. Xác định kỳ hiện tại
    const periodSelect = document.getElementById("act-period-select");
    if (periodSelect && periodSelect.value) {
      actCurrentPeriodCode = periodSelect.value;
    }

    updateAccountingPeriodBadgeAndControls();

    // 3. Gọi API đối soát theo kỳ
    let url = `/api/operations/accounting/transactions?period_code=${encodeURIComponent(actCurrentPeriodCode)}`;
    if (actCurrentPeriodCode === "custom") {
      const fromD = document.getElementById("act-from-date")?.value;
      const toD = document.getElementById("act-to-date")?.value;
      if (fromD) url += `&start_date=${encodeURIComponent(fromD)}`;
      if (toD) url += `&end_date=${encodeURIComponent(toD)}`;
    }

    const res = await apiFetch(url);
    actTransactionsCache = res.transactions || [];

    // Sắp xếp mặc định ID nhỏ nhất đến lớn nhất (thời gian)
    actTransactionsCache.sort((a, b) => (Number(a.id) || 0) - (Number(b.id) || 0));

    // Cập nhật 5 thẻ KPI tài chính & nhận diện chênh lệch
    updateAccountingKPICards(res.summary, actTransactionsCache);

    // Cập nhật số lượng trên các tab phân loại
    updateAccountingMatchTabCounts(actTransactionsCache);

    // Lọc và hiển thị bảng dữ liệu
    filterAccountingTable(false);
  } catch (err) {
    console.error("Lỗi khi tải dữ liệu kế toán:", err);
    container.innerHTML = `<p style="color:var(--danger); padding:16px;">Lỗi tải dữ liệu kế toán: ${err.message}</p>`;
  }
}

function updateAccountingPeriodDropdown() {
  const select = document.getElementById("act-period-select");
  if (!select || !actPeriodsCache || actPeriodsCache.length === 0) return;

  const currentVal = select.value || actCurrentPeriodCode;

  let html = "";
  actPeriodsCache.forEach(p => {
    const isClosed = p.is_closed === 1;
    const statusText = isClosed ? "Đã khóa sổ" : "Đang mở";
    const countInfo = p.tx_count !== undefined ? ` (${p.tx_count} giao dịch)` : "";
    html += `<option value="${p.period_code}">${p.period_name} — ${statusText}${countInfo}</option>`;
  });

  html += `<option value="all">Tất cả thời gian (Xem toàn bộ)</option>`;
  html += `<option value="custom">Tùy chọn khoảng ngày...</option>`;

  select.innerHTML = html;
  if ([...select.options].some(o => o.value === currentVal)) {
    select.value = currentVal;
  }
}

function updateAccountingPeriodBadgeAndControls() {
  const badgeWrap = document.getElementById("act-period-status-badge");
  const closeBtn = document.getElementById("btn-close-period");
  const customDatesWrap = document.getElementById("act-custom-dates-wrap");

  if (actCurrentPeriodCode === "custom") {
    if (customDatesWrap) customDatesWrap.style.display = "flex";
  } else {
    if (customDatesWrap) customDatesWrap.style.display = "none";
  }

  const periodObj = (actPeriodsCache || []).find(p => p.period_code === actCurrentPeriodCode);

  if (actCurrentPeriodCode === "all" || actCurrentPeriodCode === "custom") {
    if (badgeWrap) {
      badgeWrap.innerHTML = `<span class="badge" style="background:#f1f5f9; color:#475569; border:1px solid #cbd5e1; font-weight:600; font-size:12px; padding:6px 12px; border-radius:6px;">Chế độ xem linh hoạt</span>`;
    }
    if (closeBtn) {
      closeBtn.disabled = true;
      closeBtn.style.opacity = "0.5";
      closeBtn.style.cursor = "not-allowed";
      closeBtn.textContent = "Khóa sổ và chốt kỳ";
      closeBtn.title = "Vui lòng chọn một kỳ cụ thể để khóa sổ.";
    }
    return;
  }

  if (periodObj && periodObj.is_closed === 1) {
    if (badgeWrap) {
      badgeWrap.innerHTML = `<span class="badge" style="background:#fee2e2; color:#b91c1c; border:1px solid #fecaca; font-weight:600; font-size:12px; padding:6px 12px; border-radius:6px;">Đã khóa sổ và chốt đối soát (${periodObj.closed_by || 'Kế toán'})</span>`;
    }
    if (closeBtn) {
      closeBtn.disabled = true;
      closeBtn.style.opacity = "0.5";
      closeBtn.style.cursor = "not-allowed";
      closeBtn.textContent = "Kỳ này đã khóa sổ";
      closeBtn.title = "Kỳ này đã được chốt và khóa sổ, không thể khóa lại.";
    }
  } else {
    if (badgeWrap) {
      badgeWrap.innerHTML = `<span class="badge" style="background:#fef3c7; color:#d97706; border:1px solid #fde68a; font-weight:600; font-size:12px; padding:6px 12px; border-radius:6px;">Đang mở (Đang nhận và đối chiếu giao dịch)</span>`;
    }
    if (closeBtn) {
      closeBtn.disabled = false;
      closeBtn.style.opacity = "1";
      closeBtn.style.cursor = "pointer";
      closeBtn.textContent = "Khóa sổ và chốt kỳ";
      closeBtn.title = "Khóa sổ và chốt đối soát kỳ này";
    }
  }
}

function onAccountingPeriodChange() {
  const select = document.getElementById("act-period-select");
  if (select) {
    actCurrentPeriodCode = select.value;
  }
  updateAccountingPeriodBadgeAndControls();
  loadAccountingData();
}

function updateAccountingKPICards(summary, txs) {
  let revenue = summary ? summary.total_revenue : undefined;
  let refunds = summary ? summary.total_refund : undefined;
  let reconciledCount = summary ? summary.reconciled_count : undefined;
  let pendingCount = summary ? summary.pending_count : undefined;
  let discCount = summary ? summary.discrepancy_count : undefined;

  if (revenue === undefined) {
    revenue = 0; refunds = 0; reconciledCount = 0; pendingCount = 0; discCount = 0;
    txs.forEach(t => {
      const isRefund = t.tx_type === "Hoàn tiền";
      if (isRefund) refunds += Math.abs(t.amount || 0);
      else revenue += (t.amount || 0);

      if (t.reconciled === 1) reconciledCount++;
      else pendingCount++;

      if (t.is_discrepancy) discCount++;
    });
  }

  const revEl = document.getElementById("act-kpi-revenue");
  const refEl = document.getElementById("act-kpi-refunds");
  const recEl = document.getElementById("act-kpi-reconciled");
  const penEl = document.getElementById("act-kpi-pending");
  const discEl = document.getElementById("act-kpi-discrepancy");

  if (revEl) revEl.textContent = formatMoney(revenue);
  if (refEl) refEl.textContent = formatMoney(refunds);
  if (recEl) recEl.textContent = reconciledCount;
  if (penEl) penEl.textContent = pendingCount;
  if (discEl) discEl.textContent = discCount;
}

function updateAccountingMatchTabCounts(txs) {
  const allCount = txs.length;
  const matchedCount = txs.filter(t => !t.is_discrepancy && (t.match_status === "Khớp đúng (100%)" || t.match_status === "Khớp hoàn tiền" || t.match_status === "matched" || t.match_status === "refund_matched")).length;
  const discCount = txs.filter(t => t.is_discrepancy === true).length;
  const pendingCount = txs.filter(t => t.reconciled !== 1).length;
  const reconciledCount = txs.filter(t => t.reconciled === 1).length;

  const setElText = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  };

  setElText("cnt-tab-all", allCount);
  setElText("cnt-tab-matched", matchedCount);
  setElText("cnt-tab-disc", discCount);
  setElText("cnt-tab-pending", pendingCount);
  setElText("cnt-tab-reconciled", reconciledCount);
}

function filterAccountingByMatch(filterType) {
  actCurrentMatchFilter = filterType;

  document.querySelectorAll(".act-match-tab").forEach(btn => {
    btn.classList.remove("active");
    btn.style.boxShadow = "none";
  });

  const tabIdMap = {
    "all": "act-tab-all",
    "matched": "act-tab-matched",
    "discrepancy": "act-tab-disc",
    "pending": "act-tab-pending",
    "reconciled": "act-tab-reconciled",
  };

  const activeTab = document.getElementById(tabIdMap[filterType]);
  if (activeTab) {
    activeTab.classList.add("active");
    activeTab.style.boxShadow = "0 2px 6px rgba(0,0,0,0.15)";
  }

  filterAccountingTable(true);
}

function filterAccountingTable(resetPage = false) {
  const container = document.getElementById("ops-accounting-table");
  if (!container) return;

  if (resetPage) {
    actCurrentPage = 1;
  }

  const q = (document.getElementById("act-search-input")?.value || "").trim().toLowerCase();
  const typeFilter = document.getElementById("act-type-filter")?.value || "";
  const statusFilter = document.getElementById("act-status-filter")?.value || "";
  const branchFilter = document.getElementById("act-branch-filter")?.value || "";

  actFilteredCache = actTransactionsCache.filter(t => {
    const code = (t.booking_code || "").toLowerCase();
    const name = (t.customer_name || "").toLowerCase();
    const idStr = String(t.id || "");
    const matchQ = !q || code.includes(q) || name.includes(q) || idStr.includes(q);

    const matchType = !typeFilter || t.tx_type === typeFilter;
    
    let matchStatus = true;
    if (statusFilter === "reconciled") {
      matchStatus = t.reconciled === 1;
    } else if (statusFilter === "unreconciled") {
      matchStatus = t.reconciled !== 1;
    }

    let matchBranch = true;
    if (branchFilter) {
      matchBranch = (t.branch_id === branchFilter) || 
                    (t.booking_code && t.booking_code.toUpperCase().startsWith(branchFilter));
    }

    let matchTab = true;
    if (actCurrentMatchFilter === "matched") {
      matchTab = !t.is_discrepancy && (t.match_status === "Khớp đúng (100%)" || t.match_status === "Khớp hoàn tiền" || t.match_status === "matched" || t.match_status === "refund_matched");
    } else if (actCurrentMatchFilter === "discrepancy") {
      matchTab = t.is_discrepancy === true;
    } else if (actCurrentMatchFilter === "pending") {
      matchTab = t.reconciled !== 1;
    } else if (actCurrentMatchFilter === "reconciled") {
      matchTab = t.reconciled === 1;
    }

    return matchQ && matchType && matchStatus && matchBranch && matchTab;
  });

  // Sắp xếp theo ID
  actFilteredCache.sort((a, b) => {
    const idA = Number(a.id) || 0;
    const idB = Number(b.id) || 0;
    return actSortAsc ? (idA - idB) : (idB - idA);
  });

  renderAccountingTable();
}

function toggleAccountingSortId() {
  actSortAsc = !actSortAsc;
  actFilteredCache.sort((a, b) => {
    const idA = Number(a.id) || 0;
    const idB = Number(b.id) || 0;
    return actSortAsc ? (idA - idB) : (idB - idA);
  });
  renderAccountingTable();
}

function goToAccountingPage(page) {
  actCurrentPage = page;
  renderAccountingTable();
}

function changeAccountingPageSize(size) {
  actPageSize = parseInt(size, 10);
  actCurrentPage = 1;
  renderAccountingTable();
}

function buildPaginationButtonsHtml(current, total) {
  if (total <= 1) {
    return `<button class="btn btn-sm btn-primary" style="height:28px; padding:0 10px; font-size:12px; font-weight:700; border-radius:6px; min-width:30px; line-height:26px;">1</button>`;
  }

  let pages = [];
  if (total <= 7) {
    for (let i = 1; i <= total; i++) pages.push(i);
  } else {
    pages.push(1);
    if (current > 3) {
      pages.push('...');
    }
    const start = Math.max(2, current - 1);
    const end = Math.min(total - 1, current + 1);
    for (let i = start; i <= end; i++) {
      if (!pages.includes(i)) pages.push(i);
    }
    if (current < total - 2) {
      pages.push('...');
    }
    if (!pages.includes(total)) pages.push(total);
  }

  return pages.map(p => {
    if (p === '...') {
      return `<span style="padding:0 6px; font-size:12px; color:var(--text-muted); user-select:none; line-height:28px;">...</span>`;
    }
    const isActive = p === current;
    return `
      <button class="btn btn-sm ${isActive ? 'btn-primary' : 'btn-outline'}" 
              ${isActive ? 'disabled' : ''} 
              onclick="goToAccountingPage(${p})" 
              style="height:28px; padding:0 10px; font-size:12px; font-weight:${isActive ? '700' : '500'}; border-radius:6px; min-width:30px; line-height:26px; ${isActive ? '' : 'background:white; border:1px solid #cbd5e1;'}">
        ${p}
      </button>
    `;
  }).join("");
}

function renderAccountingTable() {
  const container = document.getElementById("ops-accounting-table");
  if (!container) return;

  const totalRecords = actFilteredCache ? actFilteredCache.length : 0;
  if (!actFilteredCache || totalRecords === 0) {
    container.innerHTML = `<p style="text-align:center; padding:24px; color:var(--text-muted);">Không tìm thấy giao dịch nào phù hợp điều kiện lọc.</p>`;
    return;
  }

  // Phân trang
  let totalPages = 1;
  let pageTxs = actFilteredCache;
  let startIdx = 1;
  let endIdx = totalRecords;

  if (actPageSize > 0) {
    totalPages = Math.max(1, Math.ceil(totalRecords / actPageSize));
    if (actCurrentPage > totalPages) actCurrentPage = totalPages;
    if (actCurrentPage < 1) actCurrentPage = 1;

    startIdx = (actCurrentPage - 1) * actPageSize + 1;
    endIdx = Math.min(totalRecords, actCurrentPage * actPageSize);
    pageTxs = actFilteredCache.slice(startIdx - 1, endIdx);
  } else {
    actCurrentPage = 1;
  }

  container.innerHTML = `
    <div class="table-responsive">
      <table class="data-table" style="font-size:12.5px; margin-bottom:0;">
        <thead>
          <tr style="background:#f0fdf4;">
            <th style="width:75px; cursor:pointer; user-select:none;" onclick="toggleAccountingSortId()" title="Bấm để đổi chiều sắp xếp ID (${actSortAsc ? 'Đang tăng dần' : 'Đang giảm dần'})">
              ID <span style="color:var(--cozy-primary); font-size:11px;">${actSortAsc ? '▲' : '▼'}</span>
            </th>
            <th style="width:140px;">Mã đơn PMS</th>
            <th>Khách hàng</th>
            <th style="width:135px;">Loại giao dịch & kênh</th>
            <th style="text-align:right; width:115px;">Tiền cổng</th>
            <th style="text-align:right; width:115px;">Tiền đơn PMS</th>
            <th style="width:135px; text-align:center;">Đối chiếu PMS</th>
            <th style="width:125px;">Thời gian</th>
            <th style="width:95px;">Trạng thái</th>
            <th style="text-align:right; width:185px;">Thao tác</th>
          </tr>
        </thead>
        <tbody>
          ${pageTxs.map(t => {
            const isRefund = t.tx_type === "Hoàn tiền";
            const isExtension = t.tx_type === "Gia hạn";
            const isReconciled = t.reconciled === 1;
            const txBadgeClass = isRefund ? 'badge-tx-refund' : (isExtension ? 'badge-tx-extension' : 'badge-tx-payment');

            // Badge kết quả đối chiếu
            let matchBadgeHtml = "";
            if (!t.is_discrepancy && (t.match_status === "Khớp đúng (100%)" || t.match_status === "matched")) {
              matchBadgeHtml = `<span class="badge" style="background:#ecfdf5; color:#059669; border:1px solid #a7f3d0; font-size:11px; padding:3px 7px;">Khớp 100%</span>`;
            } else if (!t.is_discrepancy && (t.match_status === "Khớp hoàn tiền" || t.match_status === "refund_matched")) {
              matchBadgeHtml = `<span class="badge" style="background:#eff6ff; color:#2563eb; border:1px solid #bfdbfe; font-size:11px; padding:3px 7px;">Khớp hoàn tiền</span>`;
            } else if (t.is_discrepancy) {
              const diffStr = t.discrepancy_amount ? formatMoney(Math.abs(t.discrepancy_amount)) : '';
              const text = diffStr ? `Lệch ${diffStr}` : `${t.match_status || 'Chênh lệch'}`;
              matchBadgeHtml = `<span class="badge" style="background:#fef2f2; color:#dc2626; border:1px solid #fecaca; font-size:11px; padding:3px 7px; font-weight:700;" title="Chênh lệch: ${diffStr || t.match_status}">${text}</span>`;
            } else {
              matchBadgeHtml = `<span class="badge" style="background:#f1f5f9; color:#64748b; font-size:11px; padding:3px 7px;">—</span>`;
            }

            const pmsAmountDisplay = (t.booking_amount !== undefined && t.booking_amount !== null)
              ? formatMoney(t.booking_amount)
              : `<span style="color:#94a3b8;">—</span>`;

            return `
              <tr style="${t.is_discrepancy ? 'background:#fff5f5;' : (isReconciled ? '' : 'background:#fffdfa;')}">
                <td><span style="font-family:monospace; font-weight:700; color:var(--cozy-dark);">#${t.id}</span></td>
                <td>
                  <b style="color:var(--cozy-primary); font-family:monospace;">${t.booking_code || '—'}</b>
                  ${t.room_id ? `<div style="font-size:11px; color:var(--text-muted);">${t.room_id} (${t.branch_id || ''})</div>` : ''}
                </td>
                <td>
                  <div style="font-weight:600; color:var(--cozy-dark);">${t.customer_name || "—"}</div>
                  ${t.customer_phone ? `<div style="font-size:11px; color:var(--text-muted);">${t.customer_phone}</div>` : ''}
                </td>
                <td>
                  <span class="badge ${txBadgeClass}" style="font-size:11px; padding:2px 7px;">
                    ${t.tx_type || 'Thanh toán'}
                  </span>
                  <div style="font-size:10.5px; color:var(--text-muted); margin-top:2px;">${t.payment_method || 'VietQR'}</div>
                </td>
                <td style="text-align:right;">
                  <b style="color: ${isRefund ? 'var(--danger)' : '#059669'}; font-size:13px;">
                    ${isRefund ? '-' : '+'}${formatMoney(Math.abs(t.amount || 0))}
                  </b>
                </td>
                <td style="text-align:right;">
                  <span style="font-weight:600; color:var(--cozy-dark); font-size:12.5px;">${pmsAmountDisplay}</span>
                </td>
                <td style="text-align:center;">
                  ${matchBadgeHtml}
                </td>
                <td style="font-size:11.5px; color:var(--text-muted); font-family:monospace;">
                  ${(t.created_at || '').replace('T', ' ')}
                </td>
                <td>
                  <span class="badge ${isReconciled ? 'badge-success' : 'badge-warning'}" style="font-size:11px; padding:2px 7px;">
                    ${isReconciled ? 'Đã duyệt' : (t.status || 'Chờ duyệt')}
                  </span>
                </td>
                <td style="text-align:right;">
                  <div style="display:inline-flex; gap:6px; align-items:center; justify-content:flex-end;">
                    <button class="btn btn-sm btn-outline" onclick="openReconcileDetailModal(${t.id})" style="height:28px; padding:0 10px; font-size:12px; font-weight:600; border-radius:6px; line-height:26px; border:1px solid #cbd5e1; background:#fff;" title="Xem đối chiếu chi tiết 2 chiều PMS & Cổng thanh toán">
                      Chi tiết
                    </button>
                    ${isReconciled 
                      ? `<span class="badge" style="background:#ecfdf5; color:#059669; border:1px solid #a7f3d0; height:28px; padding:0 10px; font-size:11.5px; font-weight:700; border-radius:6px; display:inline-flex; align-items:center;" title="Đã đối soát bởi ${t.reconciled_by || 'Kế toán'}">Đã đối soát</span>`
                      : `<button class="btn btn-sm btn-primary" onclick="reconcileTx(${t.id})" style="height:28px; padding:0 12px; font-size:12px; font-weight:700; border-radius:6px; line-height:26px;">
                          Đối soát
                        </button>`
                    }
                  </div>
                </td>
              </tr>
            `;
          }).join("")}
        </tbody>
      </table>
    </div>

    <!-- Phân trang & Tùy chọn số lượng hiển thị -->
    <div class="act-pagination-bar" style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; padding:12px 14px; background:#fafafa; border:1px solid var(--cozy-border); border-top:none; border-radius:0 0 8px 8px;">
      <div style="display:flex; align-items:center; gap:12px; font-size:12.5px; color:var(--text-muted); flex-wrap:wrap;">
        <span>Hiển thị <b>${totalRecords === 0 ? 0 : startIdx} - ${endIdx}</b> / <b>${totalRecords}</b> giao dịch</span>
        <div style="display:inline-flex; align-items:center; gap:6px;">
          <span>Số lượng:</span>
          <select class="form-select" onchange="changeAccountingPageSize(this.value)" style="width:auto; font-size:12px; padding:3px 8px; border-radius:6px; cursor:pointer;">
            <option value="25" ${actPageSize === 25 ? 'selected' : ''}>25 dòng/trang</option>
            <option value="50" ${actPageSize === 50 ? 'selected' : ''}>50 dòng/trang</option>
            <option value="100" ${actPageSize === 100 ? 'selected' : ''}>100 dòng/trang</option>
            <option value="-1" ${actPageSize === -1 ? 'selected' : ''}>Tất cả (${totalRecords})</option>
          </select>
        </div>
      </div>

      <div style="display:flex; align-items:center; gap:4px; flex-wrap:wrap;">
        <button class="btn btn-sm btn-outline" ${actCurrentPage <= 1 ? 'disabled' : ''} onclick="goToAccountingPage(${actCurrentPage - 1})" style="height:28px; padding:0 12px; font-size:12px; font-weight:500; border-radius:6px; line-height:26px; background:white; border:1px solid #cbd5e1;" title="Trang trước">
          Trước
        </button>
        ${buildPaginationButtonsHtml(actCurrentPage, totalPages)}
        <button class="btn btn-sm btn-outline" ${actCurrentPage >= totalPages ? 'disabled' : ''} onclick="goToAccountingPage(${actCurrentPage + 1})" style="height:28px; padding:0 12px; font-size:12px; font-weight:500; border-radius:6px; line-height:26px; background:white; border:1px solid #cbd5e1;" title="Trang sau">
          Sau
        </button>
      </div>
    </div>
  `;
}

async function reconcileTx(txId) {
  try {
    const operatorName = state.user?.full_name || "Kế toán viên";
    const res = await apiFetch("/api/operations/reconcile", {
      method: "POST",
      body: { tx_id: txId, reconciled_by: operatorName },
    });
    const timeNow = new Date().toLocaleTimeString('vi-VN');
    showToast(`${res.message} (Ghi nhận lúc ${timeNow})`, "success");
    await loadAccountingData();
  } catch (err) {
    showToast(err.message || "Lỗi khi đối soát giao dịch", "error");
  }
}

async function reconcileAllPendingTx() {
  const pendingList = actFilteredCache.filter(t => t.reconciled !== 1);
  if (pendingList.length === 0) {
    showToast("Không có giao dịch nào đang chờ đối soát trong bộ lọc hiện tại!", "info");
    return;
  }

  const confirmed = confirm(`Bạn có chắc chắn muốn đối soát hàng loạt cho ${pendingList.length} giao dịch đang chờ?`);
  if (!confirmed) return;

  const operatorName = state.user?.full_name || "Kế toán viên";
  let successCount = 0;

  for (const t of pendingList) {
    try {
      await apiFetch("/api/operations/reconcile", {
        method: "POST",
        body: { tx_id: t.id, reconciled_by: operatorName },
      });
      successCount++;
    } catch (e) {
      console.warn(`Lỗi đối soát đơn #${t.id}:`, e);
    }
  }

  showToast(`Đã hoàn tất đối soát thành công ${successCount}/${pendingList.length} giao dịch!`, "success");
  await loadAccountingData();
}

async function openReconcileDetailModal(txId) {
  currentReconcileDetailTxId = txId;
  const modal = document.getElementById("modal-reconcile-detail");
  if (!modal) return;

  try {
    const data = await apiFetch(`/api/operations/accounting/reconcile-detail/${txId}`);
    if (!data) return;

    const tx = data.transaction;
    const bk = data.booking;
    const isDisc = data.is_discrepancy;
    const matchStatus = data.match_status;

    // 1. Phân tích kết quả đối chiếu banner
    const analysisBox = document.getElementById("rec-detail-analysis-box");
    if (analysisBox) {
      if (isDisc) {
        analysisBox.style.background = "#fef2f2";
        analysisBox.style.border = "1px solid #fecaca";
        analysisBox.innerHTML = `
          <div>
            <b style="color:#b91c1c; font-size:13.5px;">Phát hiện chênh lệch đối chiếu (Cần kiểm tra kỹ trước khi chốt kỳ):</b>
            <div style="font-size:12.5px; color:#991b1b; margin-top:2px;">${data.discrepancy_reason || "Số tiền hoặc trạng thái giữa cổng thanh toán và PMS không khớp nhau."}</div>
            ${data.discrepancy_amount ? `<div style="font-size:12px; color:#b91c1c; font-weight:700; margin-top:4px;">Số tiền chênh lệch: ${formatMoney(Math.abs(data.discrepancy_amount))}</div>` : ''}
          </div>
        `;
      } else if (matchStatus === "matched" || matchStatus === "refund_matched") {
        analysisBox.style.background = "#ecfdf5";
        analysisBox.style.border = "1px solid #a7f3d0";
        analysisBox.innerHTML = `
          <div>
            <b style="color:#065f46; font-size:13.5px;">Khớp đúng 100% (Dữ liệu hoàn toàn đồng bộ):</b>
            <div style="font-size:12.5px; color:#047857; margin-top:2px;">Số tiền ghi nhận từ cổng thanh toán khớp chính xác với giá trị đơn phòng trên hệ thống PMS CozyHome.</div>
          </div>
        `;
      } else {
        analysisBox.style.background = "#fffbeb";
        analysisBox.style.border = "1px solid #fde68a";
        analysisBox.innerHTML = `
          <div>
            <b style="color:#92400e; font-size:13.5px;">Giao dịch đang chờ kiểm tra đối chiếu:</b>
            <div style="font-size:12.5px; color:#b45309; margin-top:2px;">${data.discrepancy_reason || "Vui lòng xem xét các trường thông tin bên dưới."}</div>
          </div>
        `;
      }
    }

    // 2. Cột Cổng thanh toán
    document.getElementById("rec-d-tx-id").textContent = `#${tx.id}`;
    document.getElementById("rec-d-tx-type").innerHTML = `<span class="badge ${tx.tx_type === 'Hoàn tiền' ? 'badge-tx-refund' : (tx.tx_type === 'Gia hạn' ? 'badge-tx-extension' : 'badge-tx-payment')}">${tx.tx_type}</span>`;
    document.getElementById("rec-d-tx-amount").textContent = `${tx.tx_type === 'Hoàn tiền' ? '-' : '+'}${formatMoney(Math.abs(tx.amount || 0))}`;
    document.getElementById("rec-d-tx-method").textContent = tx.payment_method || "VietQR";
    document.getElementById("rec-d-tx-time").textContent = (tx.created_at || "").replace("T", " ");
    document.getElementById("rec-d-tx-status").textContent = tx.status || "Hoàn thành";
    document.getElementById("rec-d-tx-reconciled").innerHTML = tx.reconciled === 1 
      ? `<span style="color:#059669; font-weight:700;">Đã đối soát (${tx.reconciled_by || 'Kế toán'})</span>`
      : `<span style="color:#d97706; font-weight:700;">Chưa đối soát</span>`;

    // 3. Cột PMS
    if (bk) {
      document.getElementById("rec-d-bk-code").textContent = bk.booking_code;
      document.getElementById("rec-d-bk-room").textContent = `${bk.room_id || '—'} (Chi nhánh ${bk.branch_id || '—'})`;
      document.getElementById("rec-d-bk-customer").textContent = `${bk.customer_name || '—'} (${bk.customer_phone || '—'})`;
      document.getElementById("rec-d-bk-date").textContent = `${bk.khung_gio || '—'} • ${bk.booking_date || '—'}`;
      document.getElementById("rec-d-bk-amount").textContent = formatMoney(bk.amount || 0);
      document.getElementById("rec-d-bk-status").innerHTML = getBookingStatusBadge(bk.status);
      document.getElementById("rec-d-bk-payment").textContent = bk.payment_status || "—";
    } else {
      document.getElementById("rec-d-bk-code").innerHTML = `<span style="color:#dc2626;">Không tìm thấy</span>`;
      document.getElementById("rec-d-bk-room").textContent = "—";
      document.getElementById("rec-d-bk-customer").textContent = "—";
      document.getElementById("rec-d-bk-date").textContent = "—";
      document.getElementById("rec-d-bk-amount").textContent = "—";
      document.getElementById("rec-d-bk-status").textContent = "—";
      document.getElementById("rec-d-bk-payment").textContent = "—";
    }

    // 4. Các giao dịch liên quan cùng đơn (nếu có thanh toán đợt 2, gia hạn)
    const relWrap = document.getElementById("rec-d-related-txs-wrap");
    if (relWrap) {
      if (data.related_transactions && data.related_transactions.length > 1) {
        relWrap.style.display = "block";
        relWrap.innerHTML = `
          <div style="font-size:12.5px; font-weight:700; color:var(--cozy-dark); margin-bottom:6px;">
            Các giao dịch thuộc cùng mã đơn ${bk ? bk.booking_code : ''} (${data.related_transactions.length} giao dịch):
          </div>
          <table class="data-table" style="font-size:12px; margin-bottom:0; background:#fff;">
            <thead>
              <tr style="background:#f8fafc;">
                <th>ID</th>
                <th>Loại giao dịch</th>
                <th>Kênh</th>
                <th style="text-align:right;">Số tiền</th>
                <th>Thời gian</th>
                <th>Trạng thái</th>
              </tr>
            </thead>
            <tbody>
              ${data.related_transactions.map(rt => `
                <tr style="${rt.id === tx.id ? 'background:#f0fdf4; font-weight:600;' : ''}">
                  <td>#${rt.id} ${rt.id === tx.id ? '<span class="badge" style="background:#dcfce7; color:#15803d; font-size:10px;">Đang xem</span>' : ''}</td>
                  <td>${rt.tx_type}</td>
                  <td>${rt.payment_method || 'VietQR'}</td>
                  <td style="text-align:right; color:#059669;">${formatMoney(rt.amount)}</td>
                  <td>${(rt.created_at || '').replace('T', ' ')}</td>
                  <td>${rt.reconciled === 1 ? '<span style="color:#059669;">Đã đối soát</span>' : '<span style="color:#d97706;">Chờ đối soát</span>'}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        `;
      } else {
        relWrap.style.display = "none";
        relWrap.innerHTML = "";
      }
    }

    // 5. Nút xác nhận đối soát từ modal
    const confirmBtn = document.getElementById("btn-rec-d-confirm");
    if (confirmBtn) {
      if (tx.reconciled === 1) {
        confirmBtn.disabled = true;
        confirmBtn.style.opacity = "0.5";
        confirmBtn.style.cursor = "not-allowed";
        confirmBtn.textContent = "Giao dịch đã được đối soát";
      } else {
        confirmBtn.disabled = false;
        confirmBtn.style.opacity = "1";
        confirmBtn.style.cursor = "pointer";
        confirmBtn.textContent = "Xác nhận đối soát ngay";
      }
    }

    modal.classList.add("active");
  } catch (err) {
    showToast(err.message || "Lỗi khi tải chi tiết đối chiếu", "error");
  }
}

function closeReconcileDetailModal() {
  const modal = document.getElementById("modal-reconcile-detail");
  if (modal) modal.classList.remove("active");
  currentReconcileDetailTxId = null;
}

async function confirmReconcileFromDetail() {
  if (!currentReconcileDetailTxId) return;
  const txId = currentReconcileDetailTxId;
  closeReconcileDetailModal();
  await reconcileTx(txId);
}

async function promptCloseAccountingPeriod() {
  if (actCurrentPeriodCode === "all" || actCurrentPeriodCode === "custom") {
    showToast("Vui lòng chọn một kỳ cụ thể trong danh sách để thực hiện khóa sổ!", "warning");
    return;
  }

  const periodObj = (actPeriodsCache || []).find(p => p.period_code === actCurrentPeriodCode);
  if (periodObj && periodObj.is_closed === 1) {
    showToast(`Kỳ ${periodObj.period_name} đã được khóa sổ trước đó (${periodObj.closed_by || 'Kế toán'})!`, "info");
    return;
  }

  const periodName = periodObj ? periodObj.period_name : actCurrentPeriodCode;
  const pendingCount = actTransactionsCache.filter(t => t.reconciled !== 1).length;
  const discCount = actTransactionsCache.filter(t => t.is_discrepancy === true).length;

  let msg = `Bạn có chắc chắn muốn khóa sổ và chốt đối soát cho "${periodName}"?\n\n`;
  if (pendingCount > 0 || discCount > 0) {
    msg += `LƯU Ý QUAN TRỌNG:\n`;
    if (pendingCount > 0) msg += `- Còn ${pendingCount} giao dịch chưa hoàn tất đối soát.\n`;
    if (discCount > 0) msg += `- Còn ${discCount} giao dịch có cảnh báo chênh lệch.\n`;
    msg += `\nHệ thống sẽ chốt số liệu và ghi nhật ký khóa sổ đối soát. Tiếp tục khóa sổ?`;
  } else {
    msg += `Tất cả giao dịch trong kỳ đã khớp 100% và đối soát hoàn tất. Nhấn OK để xác nhận khóa sổ.`;
  }

  if (!confirm(msg)) return;

  const note = prompt(`Nhập ghi chú khóa sổ kỳ "${periodName}" (tùy chọn):`, "Khóa sổ đối soát định kỳ");
  if (note === null) return; // User cancelled

  try {
    const operatorName = state.user?.full_name || "Kế toán viên chuỗi";
    const res = await apiFetch("/api/operations/accounting/periods/close", {
      method: "POST",
      body: {
        period_code: actCurrentPeriodCode,
        closed_by: operatorName,
        note: note || "Khóa sổ đối soát hoàn tất",
      }
    });

    showToast(res.message || `Đã khóa sổ kỳ ${periodName} thành công!`, "success");
    await loadAccountingData();
  } catch (err) {
    showToast(err.message || "Lỗi khi khóa sổ kỳ đối soát", "error");
  }
}

function exportAccountingCSV() {
  const dataToExport = actFilteredCache.length > 0 ? actFilteredCache : actTransactionsCache;
  if (!dataToExport || dataToExport.length === 0) {
    showToast("Không có dữ liệu giao dịch để xuất!", "warning");
    return;
  }

  const branchNames = {
    "BT": "Bến Thành (BT)",
    "TD": "Thảo Điền (TD)",
    "PMH": "Phú Mỹ Hưng (PMH)"
  };

  const headers = [
    "Mã giao dịch",
    "Mã đơn đặt phòng (PMS)",
    "Khách hàng",
    "Số điện thoại",
    "Chi nhánh",
    "Loại giao dịch",
    "Kênh thanh toán",
    "Tiền GD Cổng (VNĐ)",
    "Tiền đơn PMS (VNĐ)",
    "Kết quả đối chiếu PMS",
    "Thời gian tạo",
    "Trạng thái đối soát",
    "Thời điểm đối soát",
    "Người đối soát"
  ];

  const rows = dataToExport.map(t => {
    let bId = (t.branch_id || "").toUpperCase();
    if (!bId && t.room_id) {
      if (t.room_id.startsWith("BT")) bId = "BT";
      else if (t.room_id.startsWith("TD")) bId = "TD";
      else if (t.room_id.startsWith("PMH")) bId = "PMH";
    }
    const branchDisplay = branchNames[bId] || (bId ? bId : "Toàn hệ thống");

    const isRefund = t.tx_type === "Hoàn tiền";
    const amountVal = isRefund ? -Math.abs(t.amount || 0) : Math.abs(t.amount || 0);

    let matchDesc = "Khớp đúng 100%";
    if (t.match_status === "refund_matched") matchDesc = "Khớp hoàn tiền";
    else if (t.match_status === "discrepancy_amount") matchDesc = `Lệch ${formatMoney(Math.abs(t.discrepancy_amount || 0))}`;
    else if (t.match_status === "booking_not_found") matchDesc = "Không tìm thấy đơn PMS";
    else if (t.match_status === "status_mismatch") matchDesc = "Lệch trạng thái đơn";

    return [
      `#${t.id}`,
      t.booking_code || "—",
      t.customer_name || "Khách đặt phòng",
      t.customer_phone || "—",
      branchDisplay,
      t.tx_type || "Thanh toán",
      t.payment_method || "VietQR",
      amountVal,
      t.booking_amount !== undefined ? t.booking_amount : "—",
      matchDesc,
      (t.created_at || "").replace("T", " "),
      t.reconciled === 1 ? "Đã đối soát" : (t.status || "Chưa đối soát"),
      t.reconciled_at ? t.reconciled_at.replace("T", " ") : "Chưa đối soát",
      t.reconciled_by || "Chưa đối soát"
    ];
  });

  const dateStr = new Date().toISOString().slice(0, 10);
  exportToCSV(`CozyHome_SoDoiSoatGiaoDich_${actCurrentPeriodCode}_${dateStr}.csv`, headers, rows);
  showToast(`Đã xuất thành công ${rows.length} dòng dữ liệu đối soát ra tệp CSV!`, "success");
}


// -------------------------------------------------------------
// 4. Quản lý chuỗi (Chain Manager - BR-01..03, BR-12, UC-05, UC-07)
// -------------------------------------------------------------
let mgrCurrentSubTab = "kpi";
let mgrBranchesKpiCache = null;
let mgrEscalationsCache = [];
let mgrEscFilter = "unresolved"; // 'unresolved' | 'resolved' | 'all'
let mgrRoomsSlotCache = [];
let mgrMonitorRoomsCache = [];
let mgrMonitorBookingsCache = [];

function switchManagerSubTab(subTabName) {
  mgrCurrentSubTab = subTabName;
  document.querySelectorAll(".mgr-subtab-btn").forEach(btn => {
    if (btn.getAttribute("data-mgrsub") === subTabName) {
      btn.classList.add("active");
      btn.style.background = "var(--cozy-primary)";
      btn.style.color = "#fff";
      btn.style.borderColor = "var(--cozy-primary)";
    } else {
      btn.classList.remove("active");
      btn.style.background = "";
      btn.style.color = "";
      btn.style.borderColor = "";
    }
  });

  document.querySelectorAll(".mgr-subpane").forEach(pane => {
    pane.style.display = pane.id === `mgr-subpane-${subTabName}` ? "block" : "none";
  });

  if (subTabName === "kpi") {
    loadManagerBranchesKPI();
  } else if (subTabName === "rooms") {
    loadManagerRooms();
  } else if (subTabName === "policies") {
    loadManagerPolicies();
  } else if (subTabName === "escalations") {
    loadManagerEscalations();
  } else if (subTabName === "slots") {
    loadManagerSlotAssignment();
  } else if (subTabName === "monitor") {
    loadManagerMonitorData();
  }
}

async function loadManagerData() {
  try {
    await Promise.all([
      loadManagerBranchesKPI(),
      loadManagerRooms(),
      loadManagerPolicies(),
      loadManagerEscalations(),
      loadManagerSlotAssignment(),
      loadManagerMonitorData(),
    ]);
  } catch (err) {
    console.error("Lỗi khi tải dữ liệu Quản lý chuỗi:", err);
  }
}

// -------------------------------------------------------------
// 4.1. KPI & Bảng so sánh 3 Chi nhánh (UC-05.1)
// -------------------------------------------------------------
async function loadManagerBranchesKPI() {
  try {
    const res = await apiFetch("/api/operations/manager/branches-kpi");
    if (res.status !== "ok" || !res.data) return;
    mgrBranchesKpiCache = res.data;

    // Cập nhật thẻ KPI theo bộ lọc hiện tại
    updateManagerKPICards();

    // Vẽ lưới so sánh 3 chi nhánh
    renderManagerBranchesComparison(mgrBranchesKpiCache.branches || []);
  } catch (err) {
    console.error("Lỗi load KPI chi nhánh:", err);
  }
}

function onManagerBranchFilterChange() {
  updateManagerKPICards();
}

function updateManagerKPICards() {
  if (!mgrBranchesKpiCache) return;
  const filterVal = document.getElementById("mgr-kpi-branch-filter")?.value || "ALL";
  const scopeDesc = document.getElementById("mgr-kpi-scope-desc");

  let data = null;
  if (filterVal === "ALL") {
    data = mgrBranchesKpiCache.total;
    if (scopeDesc) scopeDesc.innerHTML = `Đang xem số liệu: <b style="color:var(--cozy-primary);">Toàn hệ thống 3 chi nhánh (24 phòng)</b>`;
  } else {
    data = (mgrBranchesKpiCache.branches || []).find(b => b.branch_id === filterVal);
    const bName = data ? data.branch_name : filterVal;
    if (scopeDesc) scopeDesc.innerHTML = `Đang xem số liệu: <b style="color:var(--cozy-primary);">${bName} (8 phòng)</b>`;
  }

  if (data) {
    const bkEl = document.getElementById("mgr-kpi-bookings");
    const revEl = document.getElementById("mgr-kpi-revenue");
    const refEl = document.getElementById("mgr-kpi-refunds");
    const compEl = document.getElementById("mgr-kpi-completed");

    if (bkEl) bkEl.textContent = data.bookings ?? 0;
    if (revEl) revEl.textContent = formatMoney(data.revenue ?? 0);
    if (refEl) refEl.textContent = formatMoney(data.refunds ?? 0);
    if (compEl) compEl.textContent = data.completed ?? 0;
  }
}

function renderManagerBranchesComparison(branches) {
  const container = document.getElementById("mgr-branches-comparison-grid");
  if (!container) return;

  if (!branches || branches.length === 0) {
    container.innerHTML = `<p style="text-align:center; padding:20px; color:var(--text-muted);">Không có dữ liệu chi nhánh.</p>`;
    return;
  }

  const branchColors = {
    BT: { border: "#f97316", tag: "#fff7ed", text: "#c2410c", gradient: "linear-gradient(135deg, #fffaf5 0%, #fff7ed 100%)" },
    TD: { border: "#06b6d4", tag: "#ecfeff", text: "#0e7490", gradient: "linear-gradient(135deg, #f0fdfa 0%, #ecfeff 100%)" },
    PMH: { border: "#8b5cf6", tag: "#f5f3ff", text: "#6d28d9", gradient: "linear-gradient(135deg, #faf5ff 0%, #f5f3ff 100%)" },
  };

  container.innerHTML = `
    <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:18px;">
      ${branches.map(b => {
        const theme = branchColors[b.branch_id] || { border: "#64748b", tag: "#f1f5f9", text: "#334155", gradient: "#fff" };
        return `
          <div class="card" style="border-top:4px solid ${theme.border}; background:${theme.gradient}; border-radius:12px; padding:18px; box-shadow:var(--shadow-sm); display:flex; flex-direction:column; justify-content:space-between;">
            <div>
              <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:10px;">
                <div>
                  <h4 style="margin:0; font-size:16px; font-weight:800; color:var(--cozy-dark);">${b.branch_name}</h4>
                  <div style="font-size:12px; color:var(--text-muted); margin-top:3px;">${b.address}</div>
                </div>
                <span class="badge" style="background:${theme.tag}; color:${theme.text}; font-weight:800; font-size:11.5px; padding:3px 8px; border-radius:6px;">
                  ${b.branch_id}
                </span>
              </div>

              <!-- Occupancy bar -->
              <div style="margin:14px 0 16px 0; background:rgba(255,255,255,0.85); padding:10px 12px; border-radius:8px; border:1px solid rgba(0,0,0,0.05);">
                <div style="display:flex; justify-content:space-between; font-size:12.5px; margin-bottom:6px;">
                  <span style="font-weight:600; color:var(--cozy-dark);">Tỷ lệ lấp đầy ước tính:</span>
                  <b style="color:${theme.text};">${b.occupancy_rate}%</b>
                </div>
                <div style="width:100%; height:8px; background:#e2e8f0; border-radius:4px; overflow:hidden;">
                  <div style="width:${Math.min(100, Math.max(5, b.occupancy_rate))}%; height:100%; background:${theme.border}; border-radius:4px; transition:width 0.5s ease;"></div>
                </div>
              </div>

              <!-- Mini metrics grid -->
              <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:14px;">
                <div style="background:#fff; padding:10px; border-radius:8px; border:1px solid #f1f5f9;">
                  <div style="font-size:11.5px; color:var(--text-muted);">Doanh thu</div>
                  <div style="font-size:15px; font-weight:800; color:#059669; margin-top:2px;">${formatMoney(b.revenue)}</div>
                </div>
                <div style="background:#fff; padding:10px; border-radius:8px; border:1px solid #f1f5f9;">
                  <div style="font-size:11.5px; color:var(--text-muted);">Lượt đặt / Hoàn tất</div>
                  <div style="font-size:15px; font-weight:800; color:var(--cozy-dark); margin-top:2px;">${b.bookings} <span style="font-size:12px; font-weight:500; color:var(--text-muted);">(${b.completed} xong)</span></div>
                </div>
              </div>
            </div>

            <!-- Operational Rooms Status Chips -->
            <div style="border-top:1px dashed #cbd5e1; padding-top:10px; margin-top:4px;">
              <div style="font-size:11.5px; font-weight:700; color:var(--text-muted); margin-bottom:6px;">Hiện trạng 8 buồng phòng:</div>
              <div style="display:flex; gap:6px; flex-wrap:wrap; font-size:11.5px;">
                <span class="badge" style="background:#dcfce7; color:#15803d; padding:3px 7px;">${b.ready_rooms} Sẵn sàng</span>
                <span class="badge" style="background:#fef9c3; color:#a16207; padding:3px 7px;">${b.cleaning_rooms} Đang dọn</span>
                <span class="badge" style="background:#fee2e2; color:#b91c1c; padding:3px 7px;">${b.dirty_rooms} Cần dọn</span>
                ${b.maintenance_rooms > 0 ? `<span class="badge" style="background:#f1f5f9; color:#475569; padding:3px 7px;">${b.maintenance_rooms} Bảo trì</span>` : ''}
              </div>
            </div>
          </div>
        `;
      }).join("")}
    </div>
  `;
}

// -------------------------------------------------------------
// 4.1.B. QUẢN LÝ DỊCH VỤ LƯU TRÚ (UC-03)
// -------------------------------------------------------------
let mgrRoomsListCache = [];

async function loadManagerRooms() {
  const container = document.getElementById("mgr-rooms-table-container");
  if (!container) return;

  try {
    const res = await apiFetch("/api/operations/manager/rooms");
    if (res.status === "ok") {
      mgrRoomsListCache = res.rooms || [];
      filterManagerRoomsTable();
    }
  } catch (err) {
    console.error("Lỗi khi tải danh mục phòng:", err);
    if (container) {
      container.innerHTML = `<div style="text-align:center; padding:30px; color:var(--danger);">Lỗi tải danh mục phòng: ${err.message || 'Lỗi kết nối máy chủ'}</div>`;
    }
  }
}

function filterManagerRoomsTable() {
  const container = document.getElementById("mgr-rooms-table-container");
  if (!container) return;

  const branchFilter = document.getElementById("mgr-rooms-filter-branch")?.value || "ALL";
  const typeFilter = document.getElementById("mgr-rooms-filter-type")?.value || "ALL";
  const statusFilter = document.getElementById("mgr-rooms-filter-status")?.value || "ALL";
  const searchKw = (document.getElementById("mgr-rooms-search-input")?.value || "").toLowerCase().trim();

  const filtered = mgrRoomsListCache.filter(r => {
    if (branchFilter !== "ALL" && r.branch_id !== branchFilter) return false;
    if (typeFilter !== "ALL" && r.room_type !== typeFilter) return false;
    if (statusFilter !== "ALL" && r.operational_status !== statusFilter) return false;
    if (searchKw) {
      const matchId = (r.room_id || "").toLowerCase().includes(searchKw);
      const matchName = (r.room_name || "").toLowerCase().includes(searchKw);
      const matchConcept = (r.concept_name || "").toLowerCase().includes(searchKw);
      const matchAmenities = (r.amenities || []).join(" ").toLowerCase().includes(searchKw);
      if (!matchId && !matchName && !matchConcept && !matchAmenities) return false;
    }
    return true;
  });

  renderManagerRoomsTable(filtered);
}

function renderManagerRoomsTable(rooms) {
  const container = document.getElementById("mgr-rooms-table-container");
  if (!container) return;

  if (!rooms || rooms.length === 0) {
    container.innerHTML = `
      <div style="text-align:center; padding:40px 20px; color:var(--text-muted); background:#f8fafc; border-radius:10px; border:1px dashed #cbd5e1;">
        <div style="font-size:15px; font-weight:700; color:var(--cozy-dark); margin-bottom:4px;">Không tìm thấy phòng phù hợp</div>
        <div style="font-size:13px;">Hãy thử điều chỉnh bộ lọc hoặc nhấn "Thêm phòng mới" để bổ sung phòng vào hệ thống.</div>
      </div>
    `;
    return;
  }

  const branchNames = { BT: "Bến Thành", TD: "Thảo Điền", PMH: "Phú Mỹ Hưng" };

  let html = `
    <table class="table" style="width:100%; border-collapse:collapse; font-size:13px;">
      <thead>
        <tr style="background:#f8fafc; border-bottom:2px solid #e2e8f0; color:var(--cozy-dark); text-align:left;">
          <th style="padding:10px 12px; font-weight:700;">Mã phòng</th>
          <th style="padding:10px 12px; font-weight:700;">Tên phòng</th>
          <th style="padding:10px 12px; font-weight:700;">Chi nhánh</th>
          <th style="padding:10px 12px; font-weight:700;">Hạng phòng</th>
          <th style="padding:10px 12px; font-weight:700;">Sức chứa</th>
          <th style="padding:10px 12px; font-weight:700;">Nhóm khung</th>
          <th style="padding:10px 12px; font-weight:700;">Trạng thái</th>
          <th style="padding:10px 12px; font-weight:700; text-align:center; width:190px;">Thao tác</th>
        </tr>
      </thead>
      <tbody>
  `;

  rooms.forEach(r => {
    const isReady = r.operational_status === "Sẵn sàng";
    const statusBg = isReady ? "#dcfce7" : (r.operational_status === "Bảo trì" ? "#fef9c3" : "#fee2e2");
    const statusColor = isReady ? "#15803d" : (r.operational_status === "Bảo trì" ? "#a16207" : "#b91c1c");
    const statusLabel = isReady ? "Đang khai thác" : (r.operational_status || "Ngừng khai thác");

    html += `
      <tr style="border-bottom:1px solid #f1f5f9;">
        <td style="padding:10px 12px; font-weight:700; color:var(--cozy-primary);">${r.room_id}</td>
        <td style="padding:10px 12px;">
          <div style="font-weight:700; color:var(--cozy-dark);">${r.room_name}</div>
          <div style="font-size:11.5px; color:var(--text-muted);">${r.concept_name || r.concept || ''}</div>
        </td>
        <td style="padding:10px 12px; font-weight:600;">${branchNames[r.branch_id] || r.branch_id}</td>
        <td style="padding:10px 12px;">
          <span class="badge" style="background:#f1f5f9; color:#334155; font-size:11.5px; padding:3px 8px; border-radius:6px; font-weight:600;">
            ${r.room_type}
          </span>
        </td>
        <td style="padding:10px 12px;">${r.capacity} khách (${r.area || 22} m²)</td>
        <td style="padding:10px 12px;">
          <span class="badge" style="background:#eff6ff; color:#1d4ed8; font-weight:700; font-size:11.5px; padding:3px 8px; border-radius:6px;">
            ${r.slot_group_id || 'N1'}
          </span>
        </td>
        <td style="padding:10px 12px;">
          <span class="badge" style="background:${statusBg}; color:${statusColor}; font-weight:700; font-size:11.5px; padding:3px 8px; border-radius:6px;">
            ${statusLabel}
          </span>
        </td>
        <td style="padding:10px 12px; text-align:center;">
          <div style="display:flex; gap:6px; justify-content:center; align-items:center;">
            <button class="btn btn-outline" onclick="openEditRoomModal('${r.room_id}')" style="height:28px; padding:0 8px; font-size:11.5px; font-weight:600;" title="Chỉnh sửa thông tin phòng">
              Chỉnh sửa
            </button>
            ${isReady ? `
              <button class="btn btn-outline" onclick="toggleRoomOperationalStatus('${r.room_id}', 'Ngừng khai thác')" style="height:28px; padding:0 8px; font-size:11.5px; font-weight:600; border-color:#dc2626; color:#dc2626;" title="Tạm ngưng khai thác phòng">
                Ngừng khai thác
              </button>
            ` : `
              <button class="btn btn-outline" onclick="toggleRoomOperationalStatus('${r.room_id}', 'Sẵn sàng')" style="height:28px; padding:0 8px; font-size:11.5px; font-weight:600; border-color:#16a34a; color:#16a34a;" title="Kích hoạt lại phòng">
                Kích hoạt lại
              </button>
            `}
          </div>
        </td>
      </tr>
    `;
  });

  html += `</tbody></table>`;
  container.innerHTML = html;
}

function openAddRoomModal() {
  const form = document.getElementById("form-mgr-room");
  if (form) form.reset();

  const titleEl = document.getElementById("modal-mgr-room-title");
  if (titleEl) titleEl.textContent = "Thêm phòng mới";
  const modeEl = document.getElementById("mgr-room-edit-mode");
  if (modeEl) modeEl.value = "create";
  const idEl = document.getElementById("mgr-room-id");
  if (idEl) {
    idEl.disabled = false;
    idEl.value = "";
  }
  const branchEl = document.getElementById("mgr-room-branch");
  if (branchEl) branchEl.disabled = false;
  
  const setVal = (id, v) => { const el = document.getElementById(id); if (el) el.value = v; };
  setVal("mgr-room-status", "Sẵn sàng");
  setVal("mgr-room-capacity", "2");
  setVal("mgr-room-area", "22");
  setVal("mgr-room-slotgroup", "N1");
  setVal("mgr-room-amenities", "wifi|máy lạnh|tivi|view thành phố|minibar");

  onMgrRoomBranchChange();
  const modal = document.getElementById("modal-mgr-room");
  if (modal) {
    modal.style.display = "flex";
    modal.classList.add("active");
  }
}

function openEditRoomModal(roomId) {
  const room = mgrRoomsListCache.find(r => r.room_id === roomId);
  if (!room) {
    showToast("Không tìm thấy thông tin phòng cần chỉnh sửa!", "error");
    return;
  }

  const titleEl = document.getElementById("modal-mgr-room-title");
  if (titleEl) titleEl.textContent = `Cập nhật thông tin phòng ${roomId}`;
  const modeEl = document.getElementById("mgr-room-edit-mode");
  if (modeEl) modeEl.value = "edit";
  
  const idEl = document.getElementById("mgr-room-id");
  if (idEl) {
    idEl.value = room.room_id;
    idEl.disabled = true;
  }

  const branchEl = document.getElementById("mgr-room-branch");
  if (branchEl) {
    branchEl.value = room.branch_id;
    branchEl.disabled = true;
  }

  const setVal = (id, v) => { const el = document.getElementById(id); if (el) el.value = v; };
  setVal("mgr-room-name", room.room_name || "");
  setVal("mgr-room-type", room.room_type || "Standard");
  setVal("mgr-room-slotgroup", room.slot_group_id || "N1");
  setVal("mgr-room-capacity", room.capacity || 2);
  setVal("mgr-room-area", room.area || 22);
  setVal("mgr-room-bedtype", room.bed_type || "1 giường đôi");
  setVal("mgr-room-concept", room.concept_name || room.concept || "");
  
  const amenitiesVal = Array.isArray(room.amenities) ? room.amenities.join("|") : (room.amenities || "");
  setVal("mgr-room-amenities", amenitiesVal);
  setVal("mgr-room-status", room.operational_status || "Sẵn sàng");
  
  const imgUrl = (room.images && room.images.length > 0) ? room.images[0] : "";
  setVal("mgr-room-image", imgUrl);
  setVal("mgr-room-desc", room.description || "");

  const modal = document.getElementById("modal-mgr-room");
  if (modal) {
    modal.style.display = "flex";
    modal.classList.add("active");
  }
}

function closeMgrRoomModal() {
  const modal = document.getElementById("modal-mgr-room");
  if (modal) {
    modal.classList.remove("active");
    modal.style.display = "none";
  }
}

function onMgrRoomBranchChange() {
  const b = document.getElementById("mgr-room-branch")?.value || "BT";
  const conceptInput = document.getElementById("mgr-room-concept");
  if (!conceptInput) return;

  if (document.getElementById("mgr-room-edit-mode")?.value === "create") {
    if (b === "BT") conceptInput.value = "Đô thị năng động";
    else if (b === "TD") conceptInput.value = "Xanh mát thiên nhiên";
    else if (b === "PMH") conceptInput.value = "Hiện đại ven sông";
  }
}

async function submitMgrRoomForm(event) {
  event.preventDefault();
  const mode = document.getElementById("mgr-room-edit-mode")?.value || "create";
  const roomId = document.getElementById("mgr-room-id")?.value.trim().toUpperCase();
  const branchId = document.getElementById("mgr-room-branch")?.value;
  const roomName = document.getElementById("mgr-room-name")?.value.trim();
  const roomType = document.getElementById("mgr-room-type")?.value;
  const slotGroupId = document.getElementById("mgr-room-slotgroup")?.value;
  const capacity = parseInt(document.getElementById("mgr-room-capacity")?.value || 2);
  const area = parseInt(document.getElementById("mgr-room-area")?.value || 22);
  const bedType = document.getElementById("mgr-room-bedtype")?.value.trim();
  const conceptName = document.getElementById("mgr-room-concept")?.value.trim();
  const amenities = document.getElementById("mgr-room-amenities")?.value.trim();
  const status = document.getElementById("mgr-room-status")?.value;
  const imageUrl = document.getElementById("mgr-room-image")?.value.trim();
  const desc = document.getElementById("mgr-room-desc")?.value.trim();

  const payload = {
    room_id: roomId,
    branch_id: branchId,
    room_name: roomName,
    room_type: roomType,
    slot_group_id: slotGroupId,
    capacity: capacity,
    area: area,
    bed_type: bedType,
    concept_name: conceptName,
    amenities: amenities,
    operational_status: status,
    image_url: imageUrl,
    description: desc,
  };

  const btn = document.getElementById("btn-submit-mgr-room");
  if (btn) btn.disabled = true;

  try {
    let res;
    if (mode === "create") {
      res = await apiFetch("/api/operations/manager/rooms", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    } else {
      res = await apiFetch(`/api/operations/manager/rooms/${roomId}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
    }

    if (res.status === "ok") {
      showToast(res.message || "Thao tác phòng thành công!", "success");
      closeMgrRoomModal();
      await loadManagerRooms();
      loadManagerMonitorData();
    } else {
      showToast(res.detail || "Không thể lưu thông tin phòng!", "error");
    }
  } catch (err) {
    showToast(err.message || "Lỗi kết nối máy chủ khi lưu phòng!", "error");
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function toggleRoomOperationalStatus(roomId, targetStatus) {
  const confirmMsg = targetStatus === "Sẵn sàng"
    ? `Bạn có chắc muốn kích hoạt lại phòng '${roomId}' để mở bán trở lại?`
    : `Bạn có chắc muốn ngừng khai thác phòng '${roomId}'? (Lưu ý: Không làm ảnh hưởng đơn đặt đã xác nhận)`;

  if (!confirm(confirmMsg)) return;

  try {
    const res = await apiFetch(`/api/operations/manager/rooms/${roomId}/status`, {
      method: "POST",
      body: JSON.stringify({ status: targetStatus }),
    });

    if (res.status === "ok") {
      showToast(res.message || "Cập nhật trạng thái phòng thành công!", "success");
      await loadManagerRooms();
      loadManagerMonitorData();
    } else {
      showToast(res.detail || "Không thể cập nhật trạng thái phòng!", "error");
    }
  } catch (err) {
    showToast(err.message || "Lỗi máy chủ khi đổi trạng thái phòng!", "error");
  }
}

function exportManagerRoomsCSV() {
  if (!mgrRoomsListCache || mgrRoomsListCache.length === 0) {
    showToast("Không có danh mục phòng để xuất!", "warning");
    return;
  }

  const branchNames = { BT: "Bến Thành", TD: "Thảo Điền", PMH: "Phú Mỹ Hưng" };
  const headers = [
    "Mã phòng",
    "Tên phòng",
    "Mã chi nhánh",
    "Tên chi nhánh",
    "Hạng phòng",
    "Chủ đề Concept",
    "Sức chứa tiêu chuẩn",
    "Diện tích (m²)",
    "Loại giường",
    "Nhóm khung giờ",
    "Trạng thái vận hành",
    "Danh mục tiện nghi",
    "Mô tả chi tiết"
  ];

  const rows = mgrRoomsListCache.map(r => [
    r.room_id || "",
    r.room_name || "",
    r.branch_id || "",
    branchNames[r.branch_id] || r.branch_name || "",
    r.room_type || "",
    r.concept_name || r.concept || "",
    r.capacity || 2,
    r.area || 22,
    r.bed_type || "",
    r.slot_group_id || "N1",
    r.operational_status || "Sẵn sàng",
    Array.isArray(r.amenities) ? r.amenities.join(", ") : (r.amenities || ""),
    r.description || ""
  ]);

  const dateStr = new Date().toISOString().slice(0, 10);
  exportToCSV(`CozyHome_DanhMucPhong_${dateStr}.csv`, headers, rows);
  showToast("Đã xuất danh mục phòng toàn chuỗi ra tệp CSV!", "success");
}

// -------------------------------------------------------------
// 4.1.C. QUẢN LÝ CHÍNH SÁCH KINH DOANH (UC-04)
// -------------------------------------------------------------
let mgrPolicySubTab = "pricing";
let mgrPricingDataCache = null;
let mgrPromosCache = [];
let mgrBusinessPoliciesCache = [];

function switchManagerPolicySubTab(tabName) {
  mgrPolicySubTab = tabName;
  document.querySelectorAll(".mgr-policy-subtab-btn").forEach(btn => {
    if (btn.getAttribute("data-polsnap") === tabName) {
      btn.classList.add("active");
      btn.classList.remove("btn-outline");
      btn.style.background = "var(--cozy-primary)";
      btn.style.color = "#fff";
      btn.style.borderColor = "var(--cozy-primary)";
    } else {
      btn.classList.remove("active");
      btn.classList.add("btn-outline");
      btn.style.background = "";
      btn.style.color = "";
      btn.style.borderColor = "";
    }
  });

  const panes = ["pricing", "promotions", "terms"];
  panes.forEach(p => {
    const paneEl = document.getElementById(`mgr-policy-pane-${p}`);
    if (paneEl) paneEl.style.display = p === tabName ? "block" : "none";
  });
}

async function loadManagerPolicies() {
  await Promise.all([
    loadManagerPricingData(),
    loadManagerPromotionsData(),
    loadManagerBusinessPoliciesData(),
  ]);
}

async function loadManagerPricingData() {
  const matrixContainer = document.getElementById("mgr-pricing-matrix-container");
  const surchargesContainer = document.getElementById("mgr-surcharges-cards-container");
  if (!matrixContainer && !surchargesContainer) return;

  try {
    const res = await apiFetch("/api/operations/manager/pricing");
    if (res.status === "ok" && res.data) {
      mgrPricingDataCache = res.data;
      renderManagerPricingMatrix(res.data.standard_matrix);
      renderManagerSurcharges(res.data.policies);
    }
  } catch (err) {
    console.error("Lỗi tải biểu giá:", err);
  }
}

function renderManagerPricingMatrix(matrix) {
  const container = document.getElementById("mgr-pricing-matrix-container");
  if (!container || !matrix) return;

  const roomTypes = [
    { key: "Standard", name: "Hạng Tiêu Chuẩn (Standard)", desc: "Diện tích ~22m², 2 khách" },
    { key: "Deluxe", name: "Hạng Cao Cấp (Deluxe)", desc: "Diện tích ~28m², 3 khách" },
    { key: "Family", name: "Hạng Gia Đình (Family)", desc: "Diện tích ~40m², 6 khách" },
  ];

  let html = `
    <table class="table" style="width:100%; border-collapse:collapse; font-size:13px;">
      <thead>
        <tr style="background:#f8fafc; border-bottom:2px solid #e2e8f0; color:var(--cozy-dark); text-align:left;">
          <th style="padding:10px 12px; font-weight:700;">Hạng phòng</th>
          <th style="padding:10px 12px; font-weight:700;">Khung 1 (Sáng)</th>
          <th style="padding:10px 12px; font-weight:700;">Khung 2 (Chiều)</th>
          <th style="padding:10px 12px; font-weight:700;">Khung 3 (Tối)</th>
          <th style="padding:10px 12px; font-weight:700;">Khung Qua đêm</th>
        </tr>
      </thead>
      <tbody>
  `;

  roomTypes.forEach(rt => {
    const p = matrix[rt.key] || { K1: 140000, K2: 150000, K3: 150000, QD: 450000 };
    html += `
      <tr style="border-bottom:1px solid #f1f5f9;">
        <td style="padding:12px;">
          <div style="font-weight:700; color:var(--cozy-dark);">${rt.name}</div>
          <div style="font-size:11.5px; color:var(--text-muted);">${rt.desc}</div>
        </td>
        <td style="padding:12px; font-weight:700; color:#059669;">${formatMoney(p.K1)}</td>
        <td style="padding:12px; font-weight:700; color:#059669;">${formatMoney(p.K2)}</td>
        <td style="padding:12px; font-weight:700; color:#059669;">${formatMoney(p.K3)}</td>
        <td style="padding:12px; font-weight:700; color:var(--cozy-primary);">${formatMoney(p.QD)}</td>
      </tr>
    `;
  });

  html += `</tbody></table>`;
  container.innerHTML = html;
}

function renderManagerSurcharges(policies) {
  const container = document.getElementById("mgr-surcharges-cards-container");
  if (!container || !policies) return;

  const weekend = policies.weekend_surcharge || { enabled: true, percent: 10 };
  const holiday = policies.holiday_surcharge || { enabled: true, percent: 20 };
  const extRate = policies.extension_hourly_rate || 50000;
  const graceMins = policies.late_checkout_grace_minutes || 15;
  const lateHourly = policies.late_checkout_hourly_rate || 50000;
  const extraGuest = policies.extra_guest_fee || 50000;

  container.innerHTML = `
    <div class="card" style="border:1px solid #e2e8f0; padding:14px; background:#fafafa; border-radius:10px;">
      <div style="font-size:12px; color:var(--text-muted); font-weight:600;">Phụ thu cuối tuần</div>
      <div style="font-size:22px; font-weight:800; color:var(--cozy-primary); margin-top:4px;">+${weekend.percent}%</div>
      <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">Áp dụng Thứ 6, Thứ 7, Chủ nhật (${weekend.enabled ? 'Đang bật' : 'Đang tắt'})</div>
    </div>

    <div class="card" style="border:1px solid #e2e8f0; padding:14px; background:#fafafa; border-radius:10px;">
      <div style="font-size:12px; color:var(--text-muted); font-weight:600;">Phụ thu ngày lễ cao điểm</div>
      <div style="font-size:22px; font-weight:800; color:#dc2626; margin-top:4px;">+${holiday.percent}%</div>
      <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">Tết & ngày nghỉ lễ quốc gia (${holiday.enabled ? 'Đang bật' : 'Đang tắt'})</div>
    </div>

    <div class="card" style="border:1px solid #e2e8f0; padding:14px; background:#fafafa; border-radius:10px;">
      <div style="font-size:12px; color:var(--text-muted); font-weight:600;">Phí gia hạn lưu trú</div>
      <div style="font-size:20px; font-weight:800; color:#2563eb; margin-top:4px;">${formatMoney(extRate)} / giờ</div>
      <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">Phần chưa đủ 1 giờ làm tròn thành 1 giờ</div>
    </div>

    <div class="card" style="border:1px solid #e2e8f0; padding:14px; background:#fafafa; border-radius:10px;">
      <div style="font-size:12px; color:var(--text-muted); font-weight:600;">Miễn phí trả phòng trễ</div>
      <div style="font-size:20px; font-weight:800; color:#16a34a; margin-top:4px;">Tối đa ${graceMins} phút</div>
      <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">Từ phút 16 tính ${formatMoney(lateHourly)}/giờ</div>
    </div>

    <div class="card" style="border:1px solid #e2e8f0; padding:14px; background:#fafafa; border-radius:10px;">
      <div style="font-size:12px; color:var(--text-muted); font-weight:600;">Phụ thu khách bổ sung</div>
      <div style="font-size:20px; font-weight:800; color:#ea580c; margin-top:4px;">${formatMoney(extraGuest)} / người</div>
      <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">Khi vượt chuẩn nhưng dưới sức chứa tối đa</div>
    </div>
  `;
}

function openPricingAdjustModal() {
  const modal = document.getElementById("modal-mgr-pricing");
  if (modal) {
    modal.style.display = "flex";
    modal.classList.add("active");
  }
}

function closePricingAdjustModal() {
  const modal = document.getElementById("modal-mgr-pricing");
  if (modal) {
    modal.classList.remove("active");
    modal.style.display = "none";
  }
}

async function submitPricingAdjustForm(event) {
  event.preventDefault();
  const roomType = document.getElementById("mgr-pricing-roomtype")?.value || "";
  const branchId = document.getElementById("mgr-pricing-branch")?.value || "ALL";
  const khungCode = document.getElementById("mgr-pricing-khung")?.value || "";
  const newPrice = parseInt(document.getElementById("mgr-pricing-newprice")?.value || 0);

  if (newPrice <= 0) {
    showToast("Vui lòng nhập mức giá mới hợp lệ!", "warning");
    return;
  }

  try {
    const res = await apiFetch("/api/operations/manager/pricing/adjust", {
      method: "POST",
      body: JSON.stringify({
        room_type: roomType,
        branch_id: branchId,
        khung_code: khungCode,
        new_price: newPrice,
      }),
    });

    if (res.status === "ok") {
      showToast(res.message || "Cập nhật biểu giá thành công!", "success");
      closePricingAdjustModal();
      await loadManagerPricingData();
    } else {
      showToast(res.detail || "Lỗi khi cập nhật biểu giá!", "error");
    }
  } catch (err) {
    showToast(err.message || "Lỗi máy chủ khi cập nhật giá!", "error");
  }
}

function openSurchargesModal() {
  const policies = mgrPricingDataCache?.policies || {};
  const weekend = policies.weekend_surcharge || { enabled: true, percent: 10 };
  const holiday = policies.holiday_surcharge || { enabled: true, percent: 20 };

  const setVal = (id, v) => { const el = document.getElementById(id); if (el) el.value = v; };
  const setChecked = (id, c) => { const el = document.getElementById(id); if (el) el.checked = !!c; };

  setVal("mgr-sur-weekend-pct", weekend.percent ?? 10);
  setChecked("mgr-sur-weekend-enable", weekend.enabled);
  setVal("mgr-sur-holiday-pct", holiday.percent ?? 20);
  setChecked("mgr-sur-holiday-enable", holiday.enabled);
  setVal("mgr-sur-extension-fee", policies.extension_hourly_rate ?? 50000);
  setVal("mgr-sur-grace-mins", policies.late_checkout_grace_minutes ?? 15);
  setVal("mgr-sur-late-hourly", policies.late_checkout_hourly_rate ?? 50000);
  setVal("mgr-sur-extra-guest", policies.extra_guest_fee ?? 50000);

  const modal = document.getElementById("modal-mgr-surcharges");
  if (modal) {
    modal.style.display = "flex";
    modal.classList.add("active");
  }
}

function closeSurchargesModal() {
  const modal = document.getElementById("modal-mgr-surcharges");
  if (modal) {
    modal.classList.remove("active");
    modal.style.display = "none";
  }
}

async function submitSurchargesForm(event) {
  event.preventDefault();
  const payload = {
    weekend_surcharge: {
      enabled: document.getElementById("mgr-sur-weekend-enable").checked,
      percent: parseInt(document.getElementById("mgr-sur-weekend-pct").value || 10),
    },
    holiday_surcharge: {
      enabled: document.getElementById("mgr-sur-holiday-enable").checked,
      percent: parseInt(document.getElementById("mgr-sur-holiday-pct").value || 20),
    },
    extension_hourly_rate: parseInt(document.getElementById("mgr-sur-extension-fee").value || 50000),
    late_checkout_grace_minutes: parseInt(document.getElementById("mgr-sur-grace-mins").value || 15),
    late_checkout_hourly_rate: parseInt(document.getElementById("mgr-sur-late-hourly").value || 50000),
    extra_guest_fee: parseInt(document.getElementById("mgr-sur-extra-guest").value || 50000),
  };

  try {
    const res = await apiFetch("/api/operations/manager/pricing/surcharges", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    if (res.status === "ok") {
      showToast(res.message || "Cập nhật chính sách phụ thu thành công!", "success");
      closeSurchargesModal();
      await loadManagerPricingData();
    } else {
      showToast(res.detail || "Không thể cập nhật chính sách phụ thu!", "error");
    }
  } catch (err) {
    showToast(err.message || "Lỗi máy chủ khi cập nhật phụ thu!", "error");
  }
}

// -------------------------------------------------------------
// KHUYẾN MÃI (UC-04.2, UC-04.3, UC-04.4)
// -------------------------------------------------------------
async function loadManagerPromotionsData() {
  const container = document.getElementById("mgr-promotions-table-container");
  if (!container) return;

  try {
    const res = await apiFetch("/api/operations/manager/promotions");
    if (res.status === "ok") {
      mgrPromosCache = res.promotions || [];
      renderManagerPromotionsTable(mgrPromosCache);
    }
  } catch (err) {
    console.error("Lỗi tải khuyến mãi:", err);
  }
}

function renderManagerPromotionsTable(promos) {
  const container = document.getElementById("mgr-promotions-table-container");
  if (!container) return;

  if (!promos || promos.length === 0) {
    container.innerHTML = `
      <div style="text-align:center; padding:30px; color:var(--text-muted);">
        Chưa có chương trình khuyến mãi nào được tạo. Hãy nhấn "Thêm khuyến mãi mới".
      </div>
    `;
    return;
  }

  let html = `
    <table class="table" style="width:100%; border-collapse:collapse; font-size:13px;">
      <thead>
        <tr style="background:#f8fafc; border-bottom:2px solid #e2e8f0; color:var(--cozy-dark); text-align:left;">
          <th style="padding:10px 12px; font-weight:700;">Mã voucher</th>
          <th style="padding:10px 12px; font-weight:700;">Tên chương trình</th>
          <th style="padding:10px 12px; font-weight:700;">Mức chiết khấu</th>
          <th style="padding:10px 12px; font-weight:700;">Điều kiện áp dụng</th>
          <th style="padding:10px 12px; font-weight:700;">Thời hạn hiệu lực</th>
          <th style="padding:10px 12px; font-weight:700;">Trạng thái</th>
          <th style="padding:10px 12px; font-weight:700; text-align:center; width:180px;">Thao tác</th>
        </tr>
      </thead>
      <tbody>
  `;

  promos.forEach(p => {
    const discountText = p.discount_percent > 0 ? `Giảm ${p.discount_percent}%` : `Giảm ${formatMoney(p.discount_value)}`;
    const isActive = !!p.active;
    const stBg = isActive ? "#dcfce7" : "#fee2e2";
    const stColor = isActive ? "#15803d" : "#b91c1c";
    const stText = isActive ? "Đang áp dụng" : "Tạm ngưng";

    html += `
      <tr style="border-bottom:1px solid #f1f5f9;">
        <td style="padding:10px 12px; font-weight:800; color:var(--cozy-primary);">${p.code}</td>
        <td style="padding:10px 12px;">
          <div style="font-weight:700; color:var(--cozy-dark);">${p.name}</div>
          <div style="font-size:11.5px; color:var(--text-muted);">${p.description || ''}</div>
        </td>
        <td style="padding:10px 12px; font-weight:700; color:#059669;">${discountText}</td>
        <td style="padding:10px 12px; font-size:12px; color:var(--cozy-dark);">${p.condition || 'Tất cả đơn đặt'}</td>
        <td style="padding:10px 12px; font-size:12px;">${p.effective_from || '—'} đến ${p.effective_to || '—'}</td>
        <td style="padding:10px 12px;">
          <span class="badge" style="background:${stBg}; color:${stColor}; font-weight:700; font-size:11.5px; padding:3px 8px; border-radius:6px;">
            ${stText}
          </span>
        </td>
        <td style="padding:10px 12px; text-align:center;">
          <div style="display:flex; gap:6px; justify-content:center; align-items:center;">
            <button class="btn btn-outline" onclick="openEditPromoModal('${p.code}')" style="height:28px; padding:0 8px; font-size:11.5px; font-weight:600;">
              Chỉnh sửa
            </button>
            <button class="btn btn-outline" onclick="togglePromoStatus('${p.code}')" style="height:28px; padding:0 8px; font-size:11.5px; font-weight:600; border-color:${isActive ? '#dc2626' : '#16a34a'}; color:${isActive ? '#dc2626' : '#16a34a'};">
              ${isActive ? 'Tạm ngưng' : 'Kích hoạt'}
            </button>
          </div>
        </td>
      </tr>
    `;
  });

  html += `</tbody></table>`;
  container.innerHTML = html;
}

function openAddPromoModal() {
  const form = document.getElementById("form-mgr-promo");
  if (form) form.reset();

  const titleEl = document.getElementById("modal-mgr-promo-title");
  if (titleEl) titleEl.textContent = "Thêm khuyến mãi mới";
  const modeEl = document.getElementById("mgr-promo-edit-mode");
  if (modeEl) modeEl.value = "create";
  const codeEl = document.getElementById("mgr-promo-code");
  if (codeEl) codeEl.disabled = false;
  const fromEl = document.getElementById("mgr-promo-from");
  if (fromEl) fromEl.value = new Date().toISOString().slice(0, 10);
  const toEl = document.getElementById("mgr-promo-to");
  if (toEl) toEl.value = "2026-12-31";

  const modal = document.getElementById("modal-mgr-promo");
  if (modal) {
    modal.style.display = "flex";
    modal.classList.add("active");
  }
}

function openEditPromoModal(code) {
  const p = mgrPromosCache.find(x => x.code === code);
  if (!p) return;

  const titleEl = document.getElementById("modal-mgr-promo-title");
  if (titleEl) titleEl.textContent = `Cập nhật khuyến mãi: ${p.name || code}`;
  const modeEl = document.getElementById("mgr-promo-edit-mode");
  if (modeEl) modeEl.value = "edit";
  
  const codeEl = document.getElementById("mgr-promo-code");
  if (codeEl) {
    codeEl.value = p.code;
    codeEl.disabled = true;
  }

  const setVal = (id, v) => { const el = document.getElementById(id); if (el) el.value = v; };
  setVal("mgr-promo-name", p.name || "");
  setVal("mgr-promo-percent", p.discount_percent || 0);
  setVal("mgr-promo-value", p.discount_value || 0);
  setVal("mgr-promo-badge", p.badge || "");
  setVal("mgr-promo-branch", p.branch_id || "ALL");
  setVal("mgr-promo-from", p.effective_from || "");
  setVal("mgr-promo-to", p.effective_to || "");
  setVal("mgr-promo-cond", p.condition || "");
  setVal("mgr-promo-desc", p.description || "");

  const modal = document.getElementById("modal-mgr-promo");
  if (modal) {
    modal.style.display = "flex";
    modal.classList.add("active");
  }
}

function closeMgrPromoModal() {
  const modal = document.getElementById("modal-mgr-promo");
  if (modal) {
    modal.classList.remove("active");
    modal.style.display = "none";
  }
}

async function submitMgrPromoForm(event) {
  event.preventDefault();
  const mode = document.getElementById("mgr-promo-edit-mode")?.value || "create";
  const code = document.getElementById("mgr-promo-code")?.value.trim().toUpperCase();
  const name = document.getElementById("mgr-promo-name")?.value.trim();
  const percent = parseInt(document.getElementById("mgr-promo-percent")?.value || 0);
  const val = parseInt(document.getElementById("mgr-promo-value")?.value || 0);
  const badge = document.getElementById("mgr-promo-badge")?.value.trim();
  const branchId = document.getElementById("mgr-promo-branch")?.value || "ALL";
  const fromDate = document.getElementById("mgr-promo-from")?.value;
  const toDate = document.getElementById("mgr-promo-to")?.value;
  const condition = document.getElementById("mgr-promo-cond")?.value.trim();
  const desc = document.getElementById("mgr-promo-desc")?.value.trim();

  const payload = {
    code: code,
    name: name,
    discount_percent: percent,
    discount_value: val,
    badge: badge,
    branch_id: branchId,
    effective_from: fromDate,
    effective_to: toDate,
    condition: condition,
    description: desc,
  };

  try {
    let res;
    if (mode === "create") {
      res = await apiFetch("/api/operations/manager/promotions", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    } else {
      res = await apiFetch(`/api/operations/manager/promotions/${code}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
    }

    if (res.status === "ok") {
      showToast(res.message || "Lưu khuyến mãi thành công!", "success");
      closeMgrPromoModal();
      await loadManagerPromotionsData();
    } else {
      showToast(res.detail || "Không thể lưu khuyến mãi!", "error");
    }
  } catch (err) {
    showToast(err.message || "Lỗi máy chủ khi lưu khuyến mãi!", "error");
  }
}

async function togglePromoStatus(code) {
  try {
    const res = await apiFetch(`/api/operations/manager/promotions/${code}/toggle`, {
      method: "POST",
    });

    if (res.status === "ok") {
      showToast(res.message || "Đã đổi trạng thái khuyến mãi!", "success");
      await loadManagerPromotionsData();
    } else {
      showToast(res.detail || "Không thể đổi trạng thái khuyến mãi!", "error");
    }
  } catch (err) {
    showToast(err.message || "Lỗi máy chủ khi đổi trạng thái khuyến mãi!", "error");
  }
}

// -------------------------------------------------------------
// CHÍNH SÁCH KINH DOANH (UC-04.5, UC-04.6, UC-04.7)
// -------------------------------------------------------------
async function loadManagerBusinessPoliciesData() {
  const container = document.getElementById("mgr-policies-list-container");
  if (!container) return;

  try {
    const res = await apiFetch("/api/operations/manager/policies");
    if (res.status === "ok") {
      mgrBusinessPoliciesCache = res.policies || [];
      renderManagerBusinessPoliciesList(mgrBusinessPoliciesCache);
    }
  } catch (err) {
    console.error("Lỗi tải chính sách kinh doanh:", err);
  }
}

function renderManagerBusinessPoliciesList(policies) {
  const container = document.getElementById("mgr-policies-list-container");
  if (!container) return;

  if (!policies || policies.length === 0) {
    container.innerHTML = `
      <div style="text-align:center; padding:30px; color:var(--text-muted);">
        Chưa có chính sách kinh doanh nào được thiết lập.
      </div>
    `;
    return;
  }

  const categoryNames = {
    CANCELLATION: "Hủy phòng & hoàn tiền",
    EXTENSION: "Gia hạn & quá giờ",
    CHECKIN_CHECKOUT: "Nhận/trả phòng & định danh",
    HOUSE_RULES: "Nội quy & an toàn",
    COMPENSATION: "Biểu phí bồi thường tài sản",
    GENERAL: "Quy định chung",
  };

  let html = `<div style="display:flex; flex-direction:column; gap:16px;">`;

  policies.forEach(p => {
    const isActive = !!p.active;
    const catLabel = categoryNames[p.category] || p.category;
    const stBg = isActive ? "#dcfce7" : "#fee2e2";
    const stColor = isActive ? "#15803d" : "#b91c1c";
    const stText = isActive ? "Đang áp dụng" : "Ngừng áp dụng";

    let rulesHtml = "";
    if (p.rules && p.rules.length > 0) {
      rulesHtml = `
        <div style="margin:10px 0; background:#f8fafc; border-radius:8px; border:1px solid #e2e8f0; overflow:hidden;">
          <table style="width:100%; border-collapse:collapse; font-size:12px;">
            <thead>
              <tr style="background:#f1f5f9; border-bottom:1px solid #e2e8f0; text-align:left; color:var(--cozy-dark);">
                <th style="padding:6px 10px; font-weight:700;">Điều kiện / Hạng mục</th>
                <th style="padding:6px 10px; font-weight:700;">Tỷ lệ / Mức phí</th>
                <th style="padding:6px 10px; font-weight:700;">Quy tắc áp dụng</th>
              </tr>
            </thead>
            <tbody>
              ${p.rules.map(r => `
                <tr style="border-bottom:1px solid #f1f5f9;">
                  <td style="padding:6px 10px; font-weight:600; color:var(--cozy-dark);">${r.condition}</td>
                  <td style="padding:6px 10px; font-weight:700; color:var(--cozy-primary);">${r.refund_rate}</td>
                  <td style="padding:6px 10px; color:var(--text-muted);">${r.description || ''}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      `;
    }

    html += `
      <div class="card" style="border:1px solid #e2e8f0; border-radius:12px; padding:18px; background:#fff; box-shadow:var(--shadow-sm);">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:10px; margin-bottom:10px;">
          <div>
            <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
              <span class="badge" style="background:#f1f5f9; color:#475569; font-weight:600; font-size:11.5px; padding:3px 8px; border-radius:6px;">
                ${catLabel}
              </span>
              <span class="badge" style="background:${stBg}; color:${stColor}; font-weight:700; font-size:11.5px; padding:3px 8px; border-radius:6px;">
                ${stText}
              </span>
              <span style="font-size:12px; color:var(--text-muted);">Phiên bản: <b>v${p.version || '1.0'}</b></span>
            </div>
            <h4 style="margin:8px 0 4px 0; font-size:16px; font-weight:800; color:var(--cozy-dark);">${p.title}</h4>
            <div style="font-size:13px; color:var(--text-muted);">${p.summary || ''}</div>
          </div>
          <div style="display:flex; gap:6px; align-items:center;">
            <button class="btn btn-outline" onclick="openEditPolicyModal('${p.policy_id}')" style="height:28px; padding:0 10px; font-size:11.5px; font-weight:600;">
              Chỉnh sửa
            </button>
            <button class="btn btn-outline" onclick="togglePolicyStatus('${p.policy_id}')" style="height:28px; padding:0 10px; font-size:11.5px; font-weight:600; border-color:${isActive ? '#dc2626' : '#16a34a'}; color:${isActive ? '#dc2626' : '#16a34a'};">
              ${isActive ? 'Ngừng áp dụng' : 'Áp dụng lại'}
            </button>
          </div>
        </div>

        ${rulesHtml}

        <div style="font-size:12.5px; color:#475569; line-height:1.6; background:#f8fafc; padding:10px 12px; border-radius:8px; border-left:3px solid var(--cozy-primary);">
          ${p.content}
        </div>

        <div style="display:flex; justify-content:space-between; align-items:center; font-size:11.5px; color:var(--text-muted); margin-top:10px; padding-top:8px; border-top:1px dashed #e2e8f0;">
          <div>Hiệu lực từ: <b>${p.effective_from || '2026-08-01'}</b></div>
          <div>Cập nhật lần cuối: ${p.updated_at ? p.updated_at.replace('T', ' ').slice(0, 16) : '—'} (Bởi: ${p.updated_by || 'Quản lý chuỗi'})</div>
        </div>
      </div>
    `;
  });

  html += `</div>`;
  container.innerHTML = html;
}

function openAddPolicyModal() {
  const form = document.getElementById("form-mgr-policy");
  if (form) form.reset();

  const titleEl = document.getElementById("modal-mgr-policy-title");
  if (titleEl) titleEl.textContent = "Thêm chính sách kinh doanh";
  const modeEl = document.getElementById("mgr-policy-edit-mode");
  if (modeEl) modeEl.value = "create";
  const idEl = document.getElementById("mgr-policy-id");
  if (idEl) idEl.disabled = false;
  const fromEl = document.getElementById("mgr-policy-effective-from");
  if (fromEl) fromEl.value = new Date().toISOString().slice(0, 10);
  const actEl = document.getElementById("mgr-policy-active");
  if (actEl) actEl.checked = true;

  const modal = document.getElementById("modal-mgr-policy");
  if (modal) {
    modal.style.display = "flex";
    modal.classList.add("active");
  }
}

function openEditPolicyModal(policyId) {
  const p = mgrBusinessPoliciesCache.find(x => x.policy_id === policyId);
  if (!p) return;

  const titleEl = document.getElementById("modal-mgr-policy-title");
  if (titleEl) titleEl.textContent = `Cập nhật chính sách: ${p.title || policyId}`;
  const modeEl = document.getElementById("mgr-policy-edit-mode");
  if (modeEl) modeEl.value = "edit";
  
  const idEl = document.getElementById("mgr-policy-id");
  if (idEl) {
    idEl.value = p.policy_id;
    idEl.disabled = true;
  }

  const setVal = (id, v) => { const el = document.getElementById(id); if (el) el.value = v; };
  setVal("mgr-policy-category", p.category || "GENERAL");
  setVal("mgr-policy-title-input", p.title || "");
  setVal("mgr-policy-summary", p.summary || "");
  setVal("mgr-policy-effective-from", p.effective_from || "");
  const actEl = document.getElementById("mgr-policy-active");
  if (actEl) actEl.checked = !!p.active;
  setVal("mgr-policy-content", p.content || "");

  const modal = document.getElementById("modal-mgr-policy");
  if (modal) {
    modal.style.display = "flex";
    modal.classList.add("active");
  }
}

function closeMgrPolicyModal() {
  const modal = document.getElementById("modal-mgr-policy");
  if (modal) {
    modal.classList.remove("active");
    modal.style.display = "none";
  }
}

async function submitMgrPolicyForm(event) {
  event.preventDefault();
  const mode = document.getElementById("mgr-policy-edit-mode")?.value || "create";
  const policyId = document.getElementById("mgr-policy-id")?.value.trim().toUpperCase();
  const category = document.getElementById("mgr-policy-category")?.value;
  const title = document.getElementById("mgr-policy-title-input")?.value.trim();
  const summary = document.getElementById("mgr-policy-summary")?.value.trim();
  const effectiveFrom = document.getElementById("mgr-policy-effective-from")?.value;
  const active = document.getElementById("mgr-policy-active").checked;
  const content = document.getElementById("mgr-policy-content")?.value.trim();

  const payload = {
    policy_id: policyId,
    category: category,
    title: title,
    summary: summary,
    effective_from: effectiveFrom,
    active: active,
    content: content,
  };

  try {
    let res;
    if (mode === "create") {
      res = await apiFetch("/api/operations/manager/policies", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    } else {
      res = await apiFetch(`/api/operations/manager/policies/${policyId}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
    }

    if (res.status === "ok") {
      showToast(res.message || "Lưu chính sách thành công!", "success");
      closeMgrPolicyModal();
      await loadManagerBusinessPoliciesData();
    } else {
      showToast(res.detail || "Không thể lưu chính sách!", "error");
    }
  } catch (err) {
    showToast(err.message || "Lỗi máy chủ khi lưu chính sách!", "error");
  }
}

async function togglePolicyStatus(policyId) {
  try {
    const res = await apiFetch(`/api/operations/manager/policies/${policyId}/toggle`, {
      method: "POST",
    });

    if (res.status === "ok") {
      showToast(res.message || "Đã chuyển trạng thái chính sách!", "success");
      await loadManagerBusinessPoliciesData();
    } else {
      showToast(res.detail || "Không thể chuyển trạng thái chính sách!", "error");
    }
  } catch (err) {
    showToast(err.message || "Lỗi máy chủ khi đổi trạng thái chính sách!", "error");
  }
}

// -------------------------------------------------------------
// 4.2. Xử lý Khiếu nại Vượt cấp (BR-12, UC-07)
// -------------------------------------------------------------
async function loadManagerEscalations() {
  const container = document.getElementById("ops-manager-escalations");
  if (!container) return;

  try {
    const res = await apiFetch("/api/operations/reviews?escalated_only=true&resolved_status=all");
    mgrEscalationsCache = res.reviews || [];

    // Cập nhật badge đếm các khiếu nại đang chờ xử lý
    const pendingCount = mgrEscalationsCache.filter(r => !r.resolved || r.resolved === 0).length;
    const badgeEl = document.getElementById("mgr-esc-badge");
    if (badgeEl) {
      if (pendingCount > 0) {
        badgeEl.textContent = pendingCount;
        badgeEl.style.display = "inline-block";
      } else {
        badgeEl.style.display = "none";
      }
    }

    renderManagerEscalationsTable();
  } catch (err) {
    container.innerHTML = `<p style="color:var(--danger); padding:16px;">Lỗi tải danh sách khiếu nại: ${err.message}</p>`;
  }
}

function filterManagerEscalations(filterType) {
  mgrEscFilter = filterType;
  document.querySelectorAll(".mgr-esc-filter").forEach(btn => {
    if (btn.getAttribute("data-escfilter") === filterType) {
      btn.classList.add("active");
      btn.style.background = "var(--cozy-primary)";
      btn.style.color = "#fff";
      btn.style.borderColor = "var(--cozy-primary)";
    } else {
      btn.classList.remove("active");
      btn.style.background = "";
      btn.style.color = "";
      btn.style.borderColor = "";
    }
  });
  renderManagerEscalationsTable();
}

function renderManagerEscalationsTable() {
  const container = document.getElementById("ops-manager-escalations");
  if (!container) return;

  let list = mgrEscalationsCache;
  if (mgrEscFilter === "unresolved") {
    list = list.filter(r => !r.resolved || r.resolved === 0);
  } else if (mgrEscFilter === "resolved") {
    list = list.filter(r => r.resolved === 1);
  }

  if (list.length === 0) {
    const msg = mgrEscFilter === "unresolved" 
      ? "Hiện tại không có khiếu nại nào đang tồn đọng chờ xử lý." 
      : (mgrEscFilter === "resolved" ? "Chưa có khiếu nại nào đã giải quyết." : "Không có khiếu nại nào trong hệ thống.");
    container.innerHTML = `<div style="text-align:center; padding:30px 20px; color:var(--success); font-weight:600; background:#f0fdf4; border-radius:8px; border:1px solid #bbf7d0;">${msg}</div>`;
    return;
  }

  const branchNames = { BT: "Bến Thành", TD: "Thảo Điền", PMH: "Phú Mỹ Hưng" };

  container.innerHTML = `
    <div class="table-responsive">
      <table class="data-table" style="font-size:13px;">
        <thead>
          <tr style="background:#fff7ed;">
            <th style="width:110px;">Mã đơn</th>
            <th>Khách hàng</th>
            <th style="width:110px;">Chi nhánh</th>
            <th>Đánh giá &amp; Nội dung phản hồi</th>
            <th>Ghi chú chuyển lên của Lễ tân</th>
            <th style="width:140px; text-align:center;">Trạng thái</th>
            <th style="text-align:right; width:130px;">Hành động</th>
          </tr>
        </thead>
        <tbody>
          ${list.map(r => {
            const isResolved = r.resolved === 1;
            const bName = branchNames[r.branch_id] || (r.branch_id || "Toàn chuỗi");
            return `
              <tr style="${isResolved ? 'background:#fafafa;' : 'background:#fff;'}">
                <td>
                  <b style="color:var(--cozy-primary); font-family:monospace; font-size:13.5px;">${r.booking_code}</b>
                  ${r.room_id ? `<div style="font-size:11px; color:var(--text-muted);">${r.room_id}</div>` : ''}
                </td>
                <td>
                  <div style="font-weight:700; color:var(--cozy-dark);">${r.user_name || "Khách hàng"}</div>
                  ${r.user_phone || r.user_email || "—"}
                </td>
                <td>
                  <span class="badge" style="background:#f1f5f9; color:#334155; font-size:11.5px;">${bName}</span>
                </td>
                <td>
                  <div style="display:flex; align-items:center; gap:6px; margin-bottom:4px;">
                    <span class="badge" style="background:#fef2f2; color:#b91c1c; font-weight:800;">${r.rating}/5 sao</span>
                  </div>
                  <div style="color:var(--text-color); font-style:italic; line-height:1.4;">"${r.content || 'Không có ghi chú thêm'}"</div>
                </td>
                <td>
                  <div style="color:#991b1b; font-weight:600; background:#fef2f2; padding:6px 10px; border-radius:6px; border:1px solid #fee2e2; font-size:12px;">
                    ${r.escalation_note || "Lễ tân yêu cầu hỗ trợ bồi hoàn"}
                  </div>
                </td>
                <td style="text-align:center;">
                  ${isResolved ? `
                    <span class="badge" style="background:#dcfce7; color:#15803d; padding:4px 8px; font-weight:700; font-size:11.5px;">
                      Đã giải quyết
                    </span>
                    <div style="font-size:10.5px; color:var(--text-muted); margin-top:3px;">Bởi: ${r.resolved_by || 'Quản lý'}</div>
                  ` : `
                    <span class="badge" style="background:#fef3c7; color:#b45309; padding:4px 8px; font-weight:700; font-size:11.5px;">
                      Chờ xử lý
                    </span>
                  `}
                </td>
                <td style="text-align:right;">
                  ${!isResolved ? `
                    <button class="btn btn-sm btn-primary" onclick="openResolveEscalationModal(${r.id})" style="padding:5px 10px; font-size:12px; font-weight:700; white-space:nowrap;">
                      Xử lý ngay
                    </button>
                  ` : `
                    <button class="btn btn-sm btn-outline" onclick="showResolvedEscalationDetails(${r.id})" style="padding:4px 8px; font-size:11.5px; white-space:nowrap;">
                      Xem chi tiết
                    </button>
                  `}
                </td>
              </tr>
            `;
          }).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function openResolveEscalationModal(reviewId) {
  const r = mgrEscalationsCache.find(x => x.id === reviewId);
  if (!r) return;

  const branchNames = { BT: "Chi nhánh Bến Thành", TD: "Chi nhánh Thảo Điền", PMH: "Chi nhánh Phú Mỹ Hưng" };

  document.getElementById("res-modal-review-id").value = r.id;
  document.getElementById("res-modal-sub").textContent = `Mã đơn: #${r.booking_code} — ${r.room_id || ''}`;
  document.getElementById("res-modal-customer").textContent = `${r.user_name || 'Khách hàng'} (${r.user_phone || r.user_email || 'Chưa có SĐT'})`;
  document.getElementById("res-modal-branch").textContent = branchNames[r.branch_id] || (r.branch_id || "Toàn chuỗi");
  document.getElementById("res-modal-rating").textContent = `${r.rating}/5 ★`;
  document.getElementById("res-modal-content").textContent = `"${r.content || 'Đánh giá không kèm văn bản'}"`;
  document.getElementById("res-modal-esc-note").textContent = r.escalation_note || "Lễ tân chuyển vụ việc vượt thẩm quyền.";

  document.getElementById("res-modal-comp-type").value = "VOUCHER";
  onCompensationTypeChange();
  document.getElementById("res-modal-note").value = "";

  const modal = document.getElementById("modal-resolve-escalation");
  if (modal) modal.style.display = "flex";
}

function closeResolveEscalationModal() {
  const modal = document.getElementById("modal-resolve-escalation");
  if (modal) modal.style.display = "none";
}

function onCompensationTypeChange() {
  const type = document.getElementById("res-modal-comp-type")?.value;
  const detailInput = document.getElementById("res-modal-comp-detail");
  if (!detailInput) return;

  if (type === "VOUCHER") {
    detailInput.value = "COZYCARE20 (Voucher giảm 20% toàn chuỗi CozyHome)";
    detailInput.placeholder = "Nhập mã voucher tri ân...";
  } else if (type === "REFUND_PARTIAL") {
    detailInput.value = "Đề xuất hoàn tiền demo 30% giá trị lưu trú qua MBBank";
    detailInput.placeholder = "Nhập số tiền hoặc tỷ lệ hoàn...";
  } else if (type === "DIRECT_CALL") {
    detailInput.value = "Gọi điện trực tiếp xin lỗi và lắng nghe phản ánh của khách";
    detailInput.placeholder = "Ghi chú nội dung cuộc gọi...";
  } else if (type === "UPGRADE_NEXT") {
    detailInput.value = "Gắn thẻ VIP: Tự động nâng hạng phòng Deluxe cho chuyến sau";
    detailInput.placeholder = "Chi tiết quyền lợi nâng hạng...";
  } else {
    detailInput.value = "Lưu biên bản chấn chỉnh nội bộ và tổ chức đào tạo lại nghiệp vụ";
    detailInput.placeholder = "Chi tiết biện pháp nội bộ...";
  }
}

async function submitResolveEscalation(event) {
  event.preventDefault();
  const reviewId = document.getElementById("res-modal-review-id")?.value;
  const compType = document.getElementById("res-modal-comp-type")?.value;
  const compDetail = document.getElementById("res-modal-comp-detail")?.value;
  const note = document.getElementById("res-modal-note")?.value;

  if (!reviewId) return;
  if (!note || !note.trim()) {
    showToast("Vui lòng nhập phương án / ghi chú giải quyết khiếu nại.", "warning");
    return;
  }

  const btn = document.getElementById("btn-submit-resolve-escalation");
  if (btn) btn.classList.add("btn-loading");

  try {
    const res = await apiFetch("/api/operations/resolve-review", {
      method: "POST",
      body: {
        review_id: parseInt(reviewId),
        resolution_note: note.trim(),
        compensation_type: compType,
        compensation_detail: (compDetail || "").trim(),
      },
    });

    closeResolveEscalationModal();
    showToast(res.message || "Đã xử lý và giải quyết khiếu nại thành công!", "success");

    // Tải lại danh sách khiếu nại và KPI
    await loadManagerEscalations();
    await loadManagerBranchesKPI();
  } catch (err) {
    showToast(err.message || "Lỗi khi giải quyết khiếu nại", "error");
  } finally {
    if (btn) btn.classList.remove("btn-loading");
  }
}

function showResolvedEscalationDetails(reviewId) {
  const r = mgrEscalationsCache.find(x => x.id === reviewId);
  if (!r) return;

  const compLabels = {
    VOUCHER: "Tặng voucher bồi hoàn",
    REFUND_PARTIAL: "Hoàn tiền hỗ trợ",
    DIRECT_CALL: "Gọi điện xin lỗi",
    UPGRADE_NEXT: "Cam kết nâng hạng phòng",
    INTERNAL_ACTION: "Chấn chỉnh nội bộ",
  };

  alert(
    `[THÔNG TIN GIẢI QUYẾT KHIẾU NẠI #${r.id}]\n` +
    `Mã đơn: #${r.booking_code} (${r.branch_id || ''})\n` +
    `Khách hàng: ${r.user_name || 'Khách'}\n` +
    `Đánh giá: ${r.rating}/5 sao: "${r.content || ''}"\n` +
    `Lý do chuyển lên: ${r.escalation_note || '—'}\n` +
    `----------------------------------------\n` +
    `Người giải quyết: ${r.resolved_by || 'Quản lý chuỗi'}\n` +
    `Thời gian giải quyết: ${r.resolved_at || 'Mới đây'}\n` +
    `Hình thức bồi hoàn: ${compLabels[r.compensation_type] || r.compensation_type || '—'}\n` +
    `Chi tiết: ${r.compensation_detail || '—'}\n` +
    `Phương án xử lý: "${r.resolution_note || '—'}"`
  );
}

// -------------------------------------------------------------
// 4.3. Cấu hình Nhóm Khung giờ (N1–N4 - BR-01..03, UC-05.2)
// -------------------------------------------------------------
function toggleSlotScheduleReference() {
  const ref = document.getElementById("mgr-slot-schedule-reference");
  const arrow = document.getElementById("mgr-slot-ref-arrow");
  if (!ref) return;
  const isHidden = ref.style.display === "none";
  ref.style.display = isHidden ? "block" : "none";
  if (arrow) arrow.innerHTML = isHidden ? "&#9650;" : "&#9660;";
}

async function loadManagerSlotAssignment() {
  const container = document.getElementById("ops-slot-assign-table");
  if (!container) return;

  try {
    const res = await apiFetch("/api/operations/housekeeping");
    mgrRoomsSlotCache = res.rooms || [];

    renderManagerSlotDistribution();
    renderManagerSlotTable(mgrRoomsSlotCache);
  } catch (err) {
    container.innerHTML = `<p style="color:var(--danger); padding:16px;">Lỗi tải bảng gán phòng: ${err.message}</p>`;
  }
}

function renderManagerSlotDistribution() {
  const container = document.getElementById("mgr-slot-distribution-container");
  if (!container) return;

  const counts = { N1: 0, N2: 0, N3: 0, N4: 0 };
  mgrRoomsSlotCache.forEach(r => {
    if (counts[r.slot_group_id] !== undefined) counts[r.slot_group_id]++;
  });

  const total = mgrRoomsSlotCache.length || 24;

  container.innerHTML = `
    <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:12px 16px;">
      <div style="font-size:12.5px; font-weight:700; color:var(--cozy-dark); margin-bottom:8px;">
        Cân bằng phân bổ tải dọn phòng và nhận/trả phòng toàn chuỗi (${total} phòng):
      </div>
      <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:10px;">
        <div style="background:#eff6ff; border:1px solid #bfdbfe; border-radius:8px; padding:8px 12px;">
          <div style="font-size:11.5px; color:#1e40af; font-weight:700;">Nhóm 1 (09:30)</div>
          <div style="font-size:18px; font-weight:800; color:#1e3a8a; margin-top:2px;">${counts.N1} <span style="font-size:11px; font-weight:500;">phòng</span></div>
        </div>
        <div style="background:#f0fdfa; border:1px solid #99f6e4; border-radius:8px; padding:8px 12px;">
          <div style="font-size:11.5px; color:#0f766e; font-weight:700;">Nhóm 2 (10:00)</div>
          <div style="font-size:18px; font-weight:800; color:#115e59; margin-top:2px;">${counts.N2} <span style="font-size:11px; font-weight:500;">phòng</span></div>
        </div>
        <div style="background:#fff7ed; border:1px solid #fed7aa; border-radius:8px; padding:8px 12px;">
          <div style="font-size:11.5px; color:#c2410c; font-weight:700;">Nhóm 3 (10:30)</div>
          <div style="font-size:18px; font-weight:800; color:#9a3412; margin-top:2px;">${counts.N3} <span style="font-size:11px; font-weight:500;">phòng</span></div>
        </div>
        <div style="background:#faf5ff; border:1px solid #e9d5ff; border-radius:8px; padding:8px 12px;">
          <div style="font-size:11.5px; color:#7e22ce; font-weight:700;">Nhóm 4 (11:00)</div>
          <div style="font-size:18px; font-weight:800; color:#581c87; margin-top:2px;">${counts.N4} <span style="font-size:11px; font-weight:500;">phòng</span></div>
        </div>
      </div>
    </div>
  `;
}

function filterManagerSlotTable() {
  const q = (document.getElementById("mgr-slot-search-input")?.value || "").trim().toLowerCase();
  const branch = document.getElementById("mgr-slot-branch-filter")?.value || "";

  const filtered = mgrRoomsSlotCache.filter(r => {
    const matchQ = !q || r.room_id.toLowerCase().includes(q) || r.room_name.toLowerCase().includes(q);
    const matchBranch = !branch || r.branch_id === branch;
    return matchQ && matchBranch;
  });

  renderManagerSlotTable(filtered);
}

function renderManagerSlotTable(rooms) {
  const container = document.getElementById("ops-slot-assign-table");
  if (!container) return;

  if (rooms.length === 0) {
    container.innerHTML = `<p style="text-align:center; padding:24px; color:var(--text-muted);">Không tìm thấy phòng nào phù hợp điều kiện lọc.</p>`;
    return;
  }

  const groupInfo = {
    N1: { name: "Nhóm 1", times: "09:30 | 13:00 | 16:30 | 20:00", bg: "#dbeafe", text: "#1e40af" },
    N2: { name: "Nhóm 2", times: "10:00 | 13:30 | 17:00 | 20:30", bg: "#ccfbf1", text: "#0f766e" },
    N3: { name: "Nhóm 3", times: "10:30 | 14:00 | 17:30 | 21:00", bg: "#ffedd5", text: "#c2410c" },
    N4: { name: "Nhóm 4", times: "11:00 | 14:30 | 18:00 | 21:30", bg: "#f3e8ff", text: "#6b21a8" },
  };

  container.innerHTML = `
    <div class="table-responsive">
      <table class="data-table" style="font-size:13px;">
        <thead>
          <tr style="background:#f8fafc;">
            <th style="width:100px;">Mã phòng</th>
            <th>Tên phòng</th>
            <th style="width:140px;">Chi nhánh</th>
            <th>Nhóm khung giờ hiện tại</th>
            <th>Các mốc giờ áp dụng</th>
            <th style="text-align:right; width:220px;">Gán nhóm mới</th>
          </tr>
        </thead>
        <tbody>
          ${rooms.map(r => {
            const grp = groupInfo[r.slot_group_id] || { name: r.slot_group_id, times: "—", bg: "#f1f5f9", text: "#334155" };
            return `
              <tr>
                <td><b style="color:var(--cozy-primary); font-family:monospace; font-size:13.5px;">${r.room_id}</b></td>
                <td>
                  <div style="font-weight:700; color:var(--cozy-dark);">${r.room_name}</div>
                  <div style="font-size:11.5px; color:var(--text-muted);">${r.room_type || 'Tiêu chuẩn'}</div>
                </td>
                <td><span class="badge" style="background:#f1f5f9; color:#475569; font-size:11.5px;">${r.branch_name}</span></td>
                <td>
                  <span class="badge" style="background:${grp.bg}; color:${grp.text}; font-weight:800; font-size:12px; padding:3px 8px; border-radius:6px;">
                    ${r.slot_group_id} — ${grp.name}
                  </span>
                </td>
                <td style="font-size:12px; color:var(--text-muted); font-family:monospace;">${grp.times}</td>
                <td style="text-align:right;">
                  <div style="display:inline-flex; align-items:center; gap:6px;">
                    <select id="slot-sel-${r.room_id}" class="form-select" style="width:auto; padding:4px 8px; font-size:12px; font-weight:600;">
                      <option value="N1" ${r.slot_group_id === 'N1' ? 'selected' : ''}>N1 (09:30)</option>
                      <option value="N2" ${r.slot_group_id === 'N2' ? 'selected' : ''}>N2 (10:00)</option>
                      <option value="N3" ${r.slot_group_id === 'N3' ? 'selected' : ''}>N3 (10:30)</option>
                      <option value="N4" ${r.slot_group_id === 'N4' ? 'selected' : ''}>N4 (11:00)</option>
                    </select>
                    <button class="btn btn-sm btn-primary" onclick="assignSlotGroup('${r.room_id}')" style="padding:4px 10px; font-size:12px; font-weight:700;">
                      Lưu
                    </button>
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

async function assignSlotGroup(roomId) {
  const select = document.getElementById(`slot-sel-${roomId}`);
  if (!select) return;
  const slotGroup = select.value;

  try {
    const res = await apiFetch("/api/operations/rooms/slot-group", {
      method: "POST",
      body: { room_id: roomId, slot_group_id: slotGroup },
    });
    showToast(res.message || `Đã chuyển phòng ${roomId} sang Nhóm ${slotGroup}!`, "success");
    await loadManagerSlotAssignment();
  } catch (err) {
    showToast(err.message || "Lỗi khi gán nhóm khung giờ", "error");
  }
}

// -------------------------------------------------------------
// 4.4. Giám sát Buồng phòng & Đơn đặt Toàn chuỗi
// -------------------------------------------------------------
async function loadManagerMonitorData() {
  try {
    const [hkRes, dashRes] = await Promise.all([
      apiFetch("/api/operations/housekeeping"),
      apiFetch("/api/operations/dashboard"),
    ]);

    const rooms = hkRes.rooms || [];
    const ops = hkRes.operations || [];
    const opMap = {};
    ops.forEach(o => { opMap[o.room_id] = o; });

    mgrMonitorRoomsCache = rooms.map(r => ({
      ...r,
      _status: opMap[r.room_id]?.status || r.operational_status || "Sẵn sàng",
      _note: opMap[r.room_id]?.note || "",
      _updated_by: opMap[r.room_id]?.updated_by || "",
      _updated_at: opMap[r.room_id]?.updated_at || "",
    }));

    mgrMonitorBookingsCache = dashRes.bookings || [];

    renderManagerRoomsMonitor(mgrMonitorRoomsCache);
    renderManagerBookingsMonitor(mgrMonitorBookingsCache);
  } catch (err) {
    console.error("Lỗi load dữ liệu giám sát Quản lý:", err);
  }
}

function filterManagerRoomsMonitor() {
  const branch = document.getElementById("mgr-monitor-branch-filter")?.value || "";
  const status = document.getElementById("mgr-monitor-status-filter")?.value || "";

  const filtered = mgrMonitorRoomsCache.filter(r => {
    const matchBranch = !branch || r.branch_id === branch;
    const matchStatus = !status || r._status === status;
    return matchBranch && matchStatus;
  });
  renderManagerRoomsMonitor(filtered);
}

function renderManagerRoomsMonitor(rooms) {
  const container = document.getElementById("mgr-monitor-rooms-grid");
  if (!container) return;

  if (rooms.length === 0) {
    container.innerHTML = `<div style="text-align:center; padding:30px; color:var(--text-muted); grid-column:1/-1;">Không có phòng nào thỏa mãn bộ lọc.</div>`;
    return;
  }

  const statusBadge = {
    "Sẵn sàng": { bg: "#dcfce7", color: "#15803d" },
    "Đã vệ sinh": { bg: "#e0f2fe", color: "#0369a1" },
    "Đã kiểm tra": { bg: "#e0f2fe", color: "#0369a1" },
    "Đang dọn": { bg: "#fef9c3", color: "#a16207" },
    "Cần dọn": { bg: "#fee2e2", color: "#b91c1c" },
    "Đang ở": { bg: "#ede9fe", color: "#6d28d9" },
    "Bảo trì": { bg: "#f1f5f9", color: "#475569" },
  };

  container.innerHTML = rooms.map(r => {
    const st = statusBadge[r._status] || { bg: "#f1f5f9", color: "#334155" };
    return `
      <div class="card" style="padding:14px; border-radius:10px; border:1px solid #e2e8f0; display:flex; flex-direction:column; justify-content:space-between; box-shadow:var(--shadow-xs);">
        <div>
          <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:6px;">
            <div>
              <span style="font-family:monospace; font-weight:800; font-size:14px; color:var(--cozy-primary);">${r.room_id}</span>
              <span style="font-size:11.5px; color:var(--text-muted); margin-left:6px;">${r.branch_name}</span>
            </div>
            <span class="badge" style="background:${st.bg}; color:${st.color}; font-weight:700; font-size:11px; padding:2px 7px;">
              ${r._status}
            </span>
          </div>
          <div style="font-weight:700; font-size:13.5px; color:var(--cozy-dark); margin-bottom:4px;">${r.room_name}</div>
          <div style="font-size:12px; color:var(--text-muted); margin-bottom:8px;">
            Khung giờ: <b style="color:var(--cozy-dark);">${r.slot_group_id || 'N1'}</b> • Giá: <b style="color:#059669;">${formatMoney(r.price_per_slot || 280000)}</b>/khung
          </div>
        </div>
        ${r._note ? `<div style="font-size:11.5px; color:#64748b; background:#f8fafc; padding:4px 8px; border-radius:4px; border:1px solid #f1f5f9; font-style:italic;">"${r._note}"</div>` : ''}
      </div>
    `;
  }).join("");
}

function filterManagerBookingsTable() {
  const q = (document.getElementById("mgr-bookings-search-input")?.value || "").trim().toLowerCase();
  const branch = document.getElementById("mgr-bookings-branch-filter")?.value || "";

  const filtered = mgrMonitorBookingsCache.filter(b => {
    const code = (b.booking_code || "").toLowerCase();
    const name = (b.customer_name || "").toLowerCase();
    const phone = (b.customer_phone || "").toLowerCase();
    const matchQ = !q || code.includes(q) || name.includes(q) || phone.includes(q);
    const matchBranch = !branch || b.branch_id === branch;
    return matchQ && matchBranch;
  });

  renderManagerBookingsMonitor(filtered);
}

function renderManagerBookingsMonitor(bookings) {
  const container = document.getElementById("mgr-bookings-monitor-table");
  if (!container) return;

  if (bookings.length === 0) {
    container.innerHTML = `<p style="text-align:center; padding:24px; color:var(--text-muted);">Không tìm thấy lượt đặt nào phù hợp.</p>`;
    return;
  }

  const branchNames = { BT: "Bến Thành", TD: "Thảo Điền", PMH: "Phú Mỹ Hưng" };
  const statusStyles = {
    "Đã thanh toán": "background:#dcfce7; color:#15803d;",
    "Đã xác nhận": "background:#dbeafe; color:#1e40af;",
    "Đã check-in": "background:#ede9fe; color:#6d28d9;",
    "Đang ở": "background:#ede9fe; color:#6d28d9;",
    "Đã hoàn tất": "background:#ecfdf5; color:#065f46;",
    "Quá giờ - chưa checkout": "background:#fee2e2; color:#b91c1c;",
    "Đã hủy": "background:#f1f5f9; color:#64748b;",
  };

  container.innerHTML = `
    <div class="table-responsive">
      <table class="data-table" style="font-size:12.5px;">
        <thead>
          <tr style="background:#f8fafc;">
            <th style="width:110px;">Mã đơn</th>
            <th>Khách hàng</th>
            <th>Phòng &amp; Chi nhánh</th>
            <th>Ngày &amp; Khung giờ</th>
            <th style="text-align:right;">Tổng tiền</th>
            <th style="text-align:center; width:130px;">Trạng thái</th>
          </tr>
        </thead>
        <tbody>
          ${bookings.slice(0, 30).map(b => `
            <tr>
              <td><b style="color:var(--cozy-primary); font-family:monospace;">${b.booking_code}</b></td>
              <td>
                <div style="font-weight:700; color:var(--cozy-dark);">${b.customer_name || 'Khách hàng'}</div>
                <div style="font-size:11px; color:var(--text-muted);">${b.customer_phone || '—'}</div>
              </td>
              <td>
                <div><b>${b.room_id}</b></div>
                <div style="font-size:11px; color:var(--text-muted);">${branchNames[b.branch_id] || b.branch_id || 'Toàn chuỗi'}</div>
              </td>
              <td>
                <div>${b.booking_date}</div>
                <div style="font-size:11px; color:var(--text-muted); font-family:monospace;">${b.khung_code} (${b.start_time || ''} - ${b.end_time || ''})</div>
              </td>
              <td style="text-align:right; font-weight:700; color:#059669;">${formatMoney(b.total_price || b.amount || 0)}</td>
              <td style="text-align:center;">
                <span class="badge" style="${statusStyles[b.status] || 'background:#f1f5f9; color:#334155;'} font-size:11px; padding:3px 7px;">
                  ${b.status}
                </span>
              </td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

// -------------------------------------------------------------
// 4.5. Xuất dữ liệu báo cáo Quản lý chuỗi (CSV chuẩn UTF-8 BOM)
// -------------------------------------------------------------
function exportManagerBranchesCSV() {
  if (!mgrBranchesKpiCache || !mgrBranchesKpiCache.branches || mgrBranchesKpiCache.branches.length === 0) {
    showToast("Không có dữ liệu hiệu suất chi nhánh để xuất!", "warning");
    return;
  }

  const headers = [
    "Mã chi nhánh",
    "Tên chi nhánh",
    "Địa chỉ cơ sở",
    "Quy mô phòng",
    "Tổng lượt đặt",
    "Lưu trú hoàn tất",
    "Doanh thu thực thu (VNĐ)",
    "Tiền hoàn trả (VNĐ)",
    "Tỷ lệ lấp đầy (%)",
    "Phòng sẵn sàng",
    "Phòng đang dọn",
    "Phòng cần dọn",
    "Phòng bảo trì"
  ];

  const rows = mgrBranchesKpiCache.branches.map(b => [
    b.branch_id || "",
    b.branch_name || "",
    b.address || "",
    b.room_count || 8,
    b.bookings || 0,
    b.completed || 0,
    b.revenue || 0,
    b.refunds || 0,
    `${b.occupancy_rate || 0}%`,
    b.ready_rooms || 0,
    b.cleaning_rooms || 0,
    b.dirty_rooms || 0,
    b.maintenance_rooms || 0
  ]);

  if (mgrBranchesKpiCache.total) {
    const tot = mgrBranchesKpiCache.total;
    rows.push([
      "TOÀN CHUỖI",
      "Tổng cộng 3 chi nhánh CozyHome",
      "TP. Hồ Chí Minh",
      tot.room_count || 24,
      tot.bookings || 0,
      tot.completed || 0,
      tot.revenue || 0,
      tot.refunds || 0,
      `${tot.occupancy_rate || 0}%`,
      tot.ready_rooms || 0,
      tot.cleaning_rooms || 0,
      tot.dirty_rooms || 0,
      tot.maintenance_rooms || 0
    ]);
  }

  const dateStr = new Date().toISOString().slice(0, 10);
  exportToCSV(`CozyHome_HieuSuatChiNhanh_${dateStr}.csv`, headers, rows);
  showToast("Đã xuất báo cáo hiệu suất 3 chi nhánh ra tệp CSV!", "success");
}

function exportManagerEscalationsCSV() {
  if (!mgrEscalationsCache || mgrEscalationsCache.length === 0) {
    showToast("Không có khiếu nại nào để xuất dữ liệu!", "warning");
    return;
  }

  const branchNames = { BT: "Bến Thành", TD: "Thảo Điền", PMH: "Phú Mỹ Hưng" };
  const headers = [
    "Mã khiếu nại",
    "Mã đơn đặt",
    "Mã phòng",
    "Chi nhánh",
    "Khách hàng",
    "Số điện thoại / Email",
    "Điểm đánh giá (Sao)",
    "Nội dung phản ánh",
    "Ghi chú lễ tân chuyển lên",
    "Trạng thái xử lý",
    "Người giải quyết",
    "Thời gian giải quyết",
    "Hình thức bồi hoàn",
    "Chi tiết bồi hoàn",
    "Phương án giải quyết"
  ];

  const rows = mgrEscalationsCache.map(r => [
    `#${r.id}`,
    r.booking_code || "",
    r.room_id || "",
    branchNames[r.branch_id] || r.branch_id || "Toàn chuỗi",
    r.user_name || "",
    r.user_phone || r.user_email || "",
    `${r.rating || 5}/5`,
    r.content || "",
    r.escalation_note || "",
    r.resolved === 1 ? "Đã giải quyết" : "Chờ xử lý",
    r.resolved_by || "",
    (r.resolved_at || "").replace("T", " "),
    r.compensation_type || "",
    r.compensation_detail || "",
    r.resolution_note || ""
  ]);

  const dateStr = new Date().toISOString().slice(0, 10);
  exportToCSV(`CozyHome_DanhSachKhieuNai_${dateStr}.csv`, headers, rows);
  showToast("Đã xuất danh sách khiếu nại khách hàng ra tệp CSV!", "success");
}

function exportManagerSlotsCSV() {
  if (!mgrRoomsSlotCache || mgrRoomsSlotCache.length === 0) {
    showToast("Không có dữ liệu cấu hình phòng để xuất!", "warning");
    return;
  }

  const groupInfo = {
    N1: { name: "Nhóm 1", times: "09:30 | 13:00 | 16:30 | 20:00" },
    N2: { name: "Nhóm 2", times: "10:00 | 13:30 | 17:00 | 20:30" },
    N3: { name: "Nhóm 3", times: "10:30 | 14:00 | 17:30 | 21:00" },
    N4: { name: "Nhóm 4", times: "11:00 | 14:30 | 18:00 | 21:30" },
  };

  const headers = [
    "Mã phòng",
    "Tên phòng",
    "Chi nhánh",
    "Hạng phòng",
    "Nhóm khung giờ",
    "Tên nhóm",
    "Mốc giờ áp dụng theo ca (Sáng, Chiều, Tối, Đêm)",
    "Giá niêm yết theo khung (VNĐ)"
  ];

  const rows = mgrRoomsSlotCache.map(r => {
    const grp = groupInfo[r.slot_group_id] || { name: r.slot_group_id, times: "—" };
    return [
      r.room_id || "",
      r.room_name || "",
      r.branch_name || r.branch_id || "",
      r.room_type || "Tiêu chuẩn",
      r.slot_group_id || "N1",
      grp.name,
      grp.times,
      r.price_per_slot || 280000
    ];
  });

  const dateStr = new Date().toISOString().slice(0, 10);
  exportToCSV(`CozyHome_CauHinhKhungGio24Phong_${dateStr}.csv`, headers, rows);
  showToast("Đã xuất cấu hình nhóm khung giờ phòng ra tệp CSV!", "success");
}

function exportManagerBookingsCSV() {
  if (!mgrMonitorBookingsCache || mgrMonitorBookingsCache.length === 0) {
    showToast("Không có dữ liệu đơn đặt để xuất!", "warning");
    return;
  }

  const branchNames = { BT: "Bến Thành", TD: "Thảo Điền", PMH: "Phú Mỹ Hưng" };
  const headers = [
    "Mã đơn",
    "Khách hàng",
    "Số điện thoại",
    "Mã phòng",
    "Chi nhánh",
    "Ngày lưu trú",
    "Khung giờ",
    "Giờ bắt đầu",
    "Giờ kết thúc",
    "Tổng tiền (VNĐ)",
    "Trạng thái đơn",
    "Thời gian tạo"
  ];

  const rows = mgrMonitorBookingsCache.map(b => [
    b.booking_code || "",
    b.customer_name || "",
    b.customer_phone || "",
    b.room_id || "",
    branchNames[b.branch_id] || b.branch_id || "",
    b.booking_date || "",
    b.khung_code || "",
    b.start_time || "",
    b.end_time || "",
    b.total_price || b.amount || 0,
    b.status || "",
    (b.created_at || "").replace("T", " ")
  ]);

  const dateStr = new Date().toISOString().slice(0, 10);
  exportToCSV(`CozyHome_GiamSatDonDatToanChuoi_${dateStr}.csv`, headers, rows);
  showToast("Đã xuất danh sách lượt đặt toàn chuỗi ra tệp CSV!", "success");
}

function exportManagerCurrentSubTab() {
  if (mgrCurrentSubTab === "kpi") {
    exportManagerBranchesCSV();
  } else if (mgrCurrentSubTab === "rooms") {
    exportManagerRoomsCSV();
  } else if (mgrCurrentSubTab === "policies") {
    showToast("Vui lòng xuất báo cáo chi tiết từ các nút tương ứng trong phân hệ Chính sách kinh doanh.", "info");
  } else if (mgrCurrentSubTab === "escalations") {
    exportManagerEscalationsCSV();
  } else if (mgrCurrentSubTab === "slots") {
    exportManagerSlotsCSV();
  } else if (mgrCurrentSubTab === "monitor") {
    exportManagerBookingsCSV();
  } else {
    exportManagerBranchesCSV();
  }
}

// -------------------------------------------------------------
// 5. Quản trị viên (Admin - BR-11, UC-08)
// -------------------------------------------------------------

// Tra cứu phòng theo mã / tên (toàn chuỗi)
let adminRoomsCache = [];

async function loadAdminRoomsData() {
  const container = document.getElementById("ops-admin-rooms-table");
  if (!container) return;

  try {
    const res = await apiFetch("/api/operations/housekeeping");
    const rooms = res.rooms || [];
    const opMap = {};
    (res.operations || []).forEach(o => { opMap[o.room_id] = o; });
    adminRoomsCache = rooms.map(r => ({ ...r, _status: opMap[r.room_id]?.status || r.operational_status }));

    renderAdminRoomsTable(adminRoomsCache);
    setupAdminRoomsFilters();
  } catch (err) {
  }
}

function setupAdminRoomsFilters() {
  const searchInput = document.getElementById("admin-room-search");
  const branchSelect = document.getElementById("admin-room-branch-filter");
  if (searchInput && !searchInput.dataset.wired) {
    searchInput.dataset.wired = "1";
    searchInput.addEventListener("input", filterAdminRooms);
  }
  if (branchSelect && !branchSelect.dataset.wired) {
    branchSelect.dataset.wired = "1";
    branchSelect.addEventListener("change", filterAdminRooms);
  }
}

function filterAdminRooms() {
  const q = (document.getElementById("admin-room-search")?.value || "").trim().toLowerCase();
  const branch = document.getElementById("admin-room-branch-filter")?.value || "";

  const filtered = adminRoomsCache.filter(r => {
    const matchQ = !q || r.room_id.toLowerCase().includes(q) || r.room_name.toLowerCase().includes(q);
    const matchBranch = !branch || r.branch_id === branch;
    return matchQ && matchBranch;
  });
  renderAdminRoomsTable(filtered);
}

const ADMIN_ROOM_STATUS_BADGE = {
  "Sẵn sàng": "badge-success",
  "Đã vệ sinh": "badge-info",
  "Đã kiểm tra": "badge-info",
  "Cần dọn": "badge-danger",
  "Đang dọn": "badge-warning",
  "Bảo trì": "badge-danger",
};

function renderAdminRoomsTable(rooms) {
  const container = document.getElementById("ops-admin-rooms-table");
  if (!container) return;

  if (rooms.length === 0) {
    container.innerHTML = `<div style="padding:16px; color:var(--text-muted); font-size:13.5px;">Không tìm thấy phòng phù hợp.</div>`;
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
              <td><span class="badge ${ADMIN_ROOM_STATUS_BADGE[r._status] || "badge-cozy"}">${r._status}</span></td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

// Tra cứu lượt đặt / phòng đã đặt (toàn chuỗi)
let adminBookingsCache = [];

async function loadAdminBookingsData() {
  const container = document.getElementById("ops-admin-bookings-table");
  if (!container) return;

  try {
    const res = await apiFetch("/api/operations/dashboard");
    adminBookingsCache = res.bookings || [];
    renderAdminBookingsTable(adminBookingsCache);
    setupAdminBookingsFilters();
  } catch (err) {
  }
}

function setupAdminBookingsFilters() {
  const searchInput = document.getElementById("admin-booking-search");
  const statusSelect = document.getElementById("admin-booking-status-filter");
  if (searchInput && !searchInput.dataset.wired) {
    searchInput.dataset.wired = "1";
    searchInput.addEventListener("input", filterAdminBookings);
  }
  if (statusSelect && !statusSelect.dataset.wired) {
    statusSelect.dataset.wired = "1";
    statusSelect.addEventListener("change", filterAdminBookings);
  }
}

function filterAdminBookings() {
  const q = (document.getElementById("admin-booking-search")?.value || "").trim().toLowerCase();
  const status = document.getElementById("admin-booking-status-filter")?.value || "";

  const filtered = adminBookingsCache.filter(b => {
    const haystack = `${b.booking_code} ${b.room_id} ${b.customer_name || ""} ${b.customer_phone || ""}`.toLowerCase();
    const matchQ = !q || haystack.includes(q);
    const matchStatus = !status || b.status === status;
    return matchQ && matchStatus;
  });
  renderAdminBookingsTable(filtered);
}

function renderAdminBookingsTable(bookings) {
  const container = document.getElementById("ops-admin-bookings-table");
  if (!container) return;

  if (bookings.length === 0) {
    container.innerHTML = `<div style="padding:16px; color:var(--text-muted); font-size:13.5px;">Không tìm thấy lượt đặt phù hợp.</div>`;
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
            <th style="text-align:right;">Thanh toán</th>
          </tr>
        </thead>
        <tbody>
          ${bookings.map(b => {
            const cfg = (typeof STATUS_CONFIG !== "undefined" && STATUS_CONFIG[b.status]) || { bg: "#f5f5f5", color: "#555" };
            return `
              <tr>
                <td><b>${b.booking_code}</b></td>
                <td><b>${b.room_id}</b></td>
                <td>${b.branch_id}</td>
                <td>${b.customer_name || "—"}<div style="font-size:11px; color:var(--text-muted);">${b.customer_phone || ""}</div></td>
                <td>${b.booking_date} (${b.khung_code})</td>
                <td><span class="badge" style="background:${cfg.bg}; color:${cfg.color};">${b.status}</span></td>
                <td style="text-align:right;">${b.payment_status || "—"}</td>
              </tr>
            `;
          }).join("")}
        </tbody>
      </table>
    </div>
  `;
}

async function loadAdminData() {
  loadAdminRoomsData();
  loadAdminBookingsData();

  const container = document.getElementById("ops-admin-users-table");
  if (!container) return;

  try {
    const res = await apiFetch("/api/operations/users");
    const users = res.users || [];

    container.innerHTML = `
      <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Họ và tên</th>
              <th>Email</th>
              <th>Vai trò</th>
              <th>Chi nhánh</th>
              <th>Bảo mật</th>
              <th style="text-align: right;">Quản trị tài khoản</th>
            </tr>
          </thead>
          <tbody>
            ${users.map(u => {
              const isLocked = u.locked === 1;

              return `
                <tr>
                  <td>#${u.id}</td>
                  <td><b>${u.full_name}</b></td>
                  <td>${u.email}</td>
                  <td><span class="badge badge-cozy">${u.role}</span></td>
                  <td>${u.branch_id || "Toàn chuỗi"}</td>
                  <td>
                    ${isLocked 
                      ? `<span class="badge badge-danger">Đã khóa (5 lần sai)</span>` 
                      : `<span class="badge badge-success">Bình thường</span>`
                    }
                  </td>
                  <td style="text-align: right; white-space: nowrap;">
                    ${isLocked 
                      ? `<button class="btn btn-sm btn-success" onclick="unlockUserAccount(${u.id})">Mở khóa</button> ` 
                      : ""
                    }
                    <button class="btn btn-sm btn-outline" onclick="changeUserRoleScopePrompt(${u.id}, '${u.role}', '${u.branch_id || ''}')">Phân quyền</button>
                  </td>
                </tr>
              `;
            }).join("")}
          </tbody>
        </table>
      </div>
    `;
  } catch (err) {
  }
}

async function unlockUserAccount(userId) {
  try {
    const res = await apiFetch(`/api/operations/users/${userId}/unlock`, { method: "POST" });
    showToast(res.message, "success");
    loadAdminData();
  } catch (err) {
  }
}

async function changeUserRoleScopePrompt(userId, currentRole, currentBranch) {
  const newRole = prompt("Nhập vai trò mới (Khách hàng, Lễ tân, Buồng phòng, Kế toán, Quản lý, Quản trị viên):", currentRole);
  if (!newRole) return;

  let newBranch = null;
  if (newRole === "Lễ tân" || newRole === "Buồng phòng") {
    newBranch = prompt("Nhập mã chi nhánh (BT, TD, PMH):", currentBranch || "BT");
  }

  try {
    const res = await apiFetch(`/api/operations/users/${userId}`, {
      method: "POST",
      body: { role: newRole, branch_id: newBranch },
    });
    showToast(res.message, "success");
    loadAdminData();
  } catch (err) {
  }
}

// =========================================================================
// GÁN TOÀN BỘ HÀM QUẢN LÝ (UC-03, UC-04) VÀO WINDOW ĐỂ GỌI TRỰC TIẾP TỪ ONCLICK
// =========================================================================
Object.assign(window, {
  openPricingAdjustModal,
  closePricingAdjustModal,
  submitPricingAdjustForm,
  openSurchargesModal,
  closeSurchargesModal,
  submitSurchargesForm,
  openAddPromoModal,
  openEditPromoModal,
  closeMgrPromoModal,
  submitMgrPromoForm,
  togglePromoStatus,
  openAddPolicyModal,
  openEditPolicyModal,
  closeMgrPolicyModal,
  submitMgrPolicyForm,
  togglePolicyStatus,
  openAddRoomModal,
  openEditRoomModal,
  closeMgrRoomModal,
  submitMgrRoomForm,
  toggleRoomOperationalStatus,
  switchManagerPolicySubTab,
  exportManagerRoomsCSV,
  onMgrRoomBranchChange,
  filterManagerRoomsTable,
  loadManagerRooms,
  loadManagerPolicies,
  loadManagerPricingData,
  loadManagerPromotionsData,
  loadManagerBusinessPoliciesData,
  switchManagerSubTab,
  loadManagerData,
});