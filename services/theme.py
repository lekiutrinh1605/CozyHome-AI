COZY_CSS = r"""
<style>
:root{
  --cozy:#b96b35;
  --cozy-dark:#60381f;
  --cozy-soft:#f3dfc2;
  --cream:#fffaf3;
  --ink:#3e2b20;
  --muted:#806f63;
  --success:#2e7d32;
  --warning:#e65100;
  --danger:#c62828;
}
.stApp{background:linear-gradient(180deg,#fffdf9 0%,#fffaf3 42%,#f9f0e5 100%);color:var(--ink)}
[data-testid="stHeader"]{background:rgba(255,253,249,.88);backdrop-filter:blur(12px)}
.block-container{max-width:1220px;padding-top:2.4rem;padding-bottom:4rem}
h1,h2,h3{color:var(--cozy-dark);letter-spacing:-.02em}
.cozy-nav{display:flex;align-items:center;gap:14px;padding:8px 2px 18px;border-bottom:1px solid #eadccf;margin-bottom:18px}
.brand{font-weight:800;font-size:26px;color:var(--cozy-dark)} .brand span{color:var(--cozy)}
.hero{padding:40px 42px;border-radius:28px;background:radial-gradient(circle at 75% 20%,#f7e7cb 0,#f7e7cb 20%,transparent 21%),linear-gradient(135deg,#6b4026 0%,#9b5931 52%,#d49a5a 100%);color:white;box-shadow:0 18px 45px rgba(92,55,31,.18);margin:8px 0 22px}
.hero h1{color:white;font-size:42px;margin:0 0 8px}.hero p{font-size:17px;max-width:700px;opacity:.93}
.badge{display:inline-block;padding:6px 12px;border-radius:999px;background:#f7e4c5;color:#6d4328;font-size:12px;font-weight:700;margin-right:6px;margin-bottom:6px}
.badge-success{background:#e8f5e9;color:#2e7d32;border:1px solid #c8e6c9}
.badge-warning{background:#fff3e0;color:#ef6c00;border:1px solid #ffe0b2}
.badge-danger{background:#ffebee;color:#c62828;border:1px solid #ffcdd2}

.room-card{border:1px solid #ead9c8;background:rgba(255,255,255,.92);border-radius:22px;padding:18px;min-height:250px;box-shadow:0 8px 25px rgba(85,52,31,.08);transition:transform .2s ease}
.room-card:hover{transform:translateY(-3px);box-shadow:0 12px 30px rgba(85,52,31,.14)}
.room-art{height:140px;border-radius:16px;background:linear-gradient(135deg,#f0d4ae,#b76e3b 48%,#633b25);display:flex;align-items:flex-end;padding:14px;color:white;font-weight:700;margin-bottom:14px;position:relative;overflow:hidden}
.room-art:after{content:'⌂';position:absolute;right:16px;top:-9px;font-size:90px;color:rgba(255,255,255,.16)}
.price{font-size:22px;font-weight:800;color:var(--cozy)}

.kpi{background:white;border:1px solid #eddfd1;border-radius:18px;padding:18px;box-shadow:0 6px 20px rgba(76,45,28,.06)}
.kpi .n{font-size:27px;font-weight:800;color:var(--cozy-dark)}

.slot-ok{background:#edf5eb;color:#3f6b3b;padding:7px 9px;border-radius:9px;font-weight:650;text-align:center}.slot-no{background:#f5ece6;color:#9c765f;padding:7px 9px;border-radius:9px;text-align:center}
.ai-box{border:1px solid #dec5ad;border-radius:22px;padding:18px;background:linear-gradient(180deg,#fffdfa,#fff5e9)}
.small-muted{font-size:13px;color:#806f63}.divider{height:1px;background:#eadccf;margin:14px 0}

/* Ticket Boarding Pass Card */
.ticket-card{background:#ffffff;border:1.5px dashed #d1b49a;border-radius:18px;padding:20px;margin-bottom:18px;box-shadow:0 6px 18px rgba(70,40,20,.06);position:relative}
.ticket-header{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #f0e6dd;padding-bottom:10px;margin-bottom:12px}
.ticket-code{font-family:monospace;font-size:20px;font-weight:800;color:var(--cozy-dark);background:#fcf4ed;padding:4px 10px;border-radius:8px;border:1px solid #ecd8c5}

/* VietQR Card */
.vietqr-card{background:linear-gradient(145deg,#ffffff,#fff9f4);border:2px solid #ecd3be;border-radius:22px;padding:24px;text-align:center;box-shadow:0 12px 32px rgba(110,60,30,.12);max-width:420px;margin:0 auto}
.vietqr-badge{background:#0054a6;color:white;padding:4px 12px;border-radius:6px;font-weight:800;font-size:14px;letter-spacing:1px;display:inline-block;margin-bottom:12px}
.vietqr-qr{background:#fff;padding:14px;border-radius:16px;display:inline-block;box-shadow:0 4px 14px rgba(0,0,0,.08);margin:12px 0}

/* OTP Display Box */
.otp-box{background:#fff7f0;border:1.5px solid #eecfb7;border-radius:16px;padding:18px;text-align:center;margin:15px 0}
.otp-number{font-family:monospace;font-size:32px;font-weight:800;letter-spacing:8px;color:#9b4d1c;background:#fff;padding:8px 24px;border-radius:10px;border:1px dashed #dca57f;display:inline-block;margin:8px 0}

/* Profile Stat Box */
.stat-pill{background:#ffffff;border:1px solid #ebd9cb;border-radius:14px;padding:12px 16px;text-align:center}
.stat-pill .num{font-size:22px;font-weight:800;color:var(--cozy)}
.stat-pill .lbl{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px}

.stButton>button{border-radius:12px;border:1px solid #b96b35;background:#b96b35;color:white;font-weight:700;transition:all .15s ease}
.stButton>button:hover{border-color:#8d512f;background:#8d512f;color:white}
[data-baseweb="select"]>div,.stTextInput input,.stNumberInput input,.stDateInput input,.stTextArea textarea{border-radius:12px!important}

/* ------------------------------------------------------------- */
/* Streamlit High-Contrast Segmented Tabs                        */
/* ------------------------------------------------------------- */
[data-testid="stTabs"] {
  margin-top: 12px !important;
  margin-bottom: 24px !important;
}
div[data-baseweb="tab-list"] {
  gap: 6px !important;
  background: #f4e8dc !important;
  padding: 6px !important;
  border-radius: 16px !important;
  border: 1px solid #ebd8c8 !important;
}
button[data-baseweb="tab"] {
  border-radius: 12px !important;
  padding: 9px 18px !important;
  background: transparent !important;
  border: none !important;
  transition: all 0.2s ease !important;
}
button[data-baseweb="tab"] p, 
button[data-baseweb="tab"] span, 
button[data-baseweb="tab"] div {
  font-size: 14.5px !important;
  font-weight: 700 !important;
  color: #5c3822 !important; /* Đảm bảo màu chữ tab luôn tương phản rõ nét, không bị chìm/trắng */
}
button[data-baseweb="tab"]:hover {
  background: rgba(255, 255, 255, 0.65) !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
  background: #ffffff !important;
  box-shadow: 0 4px 12px rgba(90, 50, 20, 0.12) !important;
  border-bottom: none !important;
}
button[data-baseweb="tab"][aria-selected="true"] p,
button[data-baseweb="tab"][aria-selected="true"] span,
button[data-baseweb="tab"][aria-selected="true"] div {
  color: #b96b35 !important;
  font-weight: 800 !important;
}
div[data-baseweb="tab-highlight"] {
  display: none !important;
}
div[data-baseweb="tab-border"] {
  display: none !important;
}

/* ------------------------------------------------------------- */
/* Streamlit Horizontal Radio as Modern Navigation Pills        */
/* ------------------------------------------------------------- */
div[data-testid="stRadio"] {
  margin: 0 !important;
}
div[data-testid="stRadio"] > div {
  display: flex !important;
  flex-direction: row !important;
  align-items: center !important;
  justify-content: center !important;
  gap: 4px !important;
  background: #f4e8dc !important;
  padding: 5px 8px !important;
  border-radius: 24px !important;
  border: 1px solid #ebd9cb !important;
  box-shadow: inset 0 1px 3px rgba(80, 40, 10, 0.05) !important;
}
div[data-testid="stRadio"] > div label {
  margin: 0 !important;
  padding: 6px 14px !important;
  border-radius: 20px !important;
  cursor: pointer !important;
  background: transparent !important;
  transition: all 0.2s ease !important;
  display: flex !important;
  align-items: center !important;
}
/* Ẩn hoàn toàn nút tròn radio mặc định của trình duyệt */
div[data-testid="stRadio"] > div label > div:first-child {
  display: none !important;
}
div[data-testid="stRadio"] > div label p,
div[data-testid="stRadio"] > div label div {
  font-size: 13.5px !important;
  font-weight: 700 !important;
  color: #5c3822 !important;
  margin: 0 !important;
  white-space: nowrap !important;
}
div[data-testid="stRadio"] > div label:hover {
  background: rgba(255, 255, 255, 0.7) !important;
}
/* Trạng thái được chọn */
div[data-testid="stRadio"] > div label:has(input:checked) {
  background: #b96b35 !important;
  box-shadow: 0 2px 8px rgba(185, 107, 53, 0.3) !important;
}
div[data-testid="stRadio"] > div label:has(input:checked) p,
div[data-testid="stRadio"] > div label:has(input:checked) div {
  color: #ffffff !important;
  font-weight: 800 !important;
}

/* ------------------------------------------------------------- */
/* Clean Dataframe Styling                                       */
/* ------------------------------------------------------------- */
[data-testid="stDataFrame"] {
  border-radius: 16px !important;
  overflow: hidden !important;
  border: 1px solid #ead9c8 !important;
  box-shadow: 0 4px 16px rgba(80, 45, 20, 0.06) !important;
}

/* ------------------------------------------------------------- */
/* Segmented Control Navigation Styling                          */
/* ------------------------------------------------------------- */
div[data-testid="stSegmentedControl"] {
  display: flex !important;
  justify-content: center !important;
  margin: 0 auto !important;
}
div[data-testid="stSegmentedControl"] > div {
  background: #f4e8dc !important;
  border-radius: 24px !important;
  padding: 4px !important;
  border: 1px solid #ebd8c8 !important;
  box-shadow: 0 2px 8px rgba(80, 45, 20, 0.05) !important;
  gap: 4px !important;
}
div[data-testid="stSegmentedControl"] button {
  border-radius: 20px !important;
  font-weight: 700 !important;
  font-size: 13.5px !important;
  color: #5c3822 !important;
  padding: 7px 16px !important;
  transition: all 0.2s ease !important;
  border: none !important;
  background: transparent !important;
}
div[data-testid="stSegmentedControl"] button:hover {
  background: rgba(255, 255, 255, 0.6) !important;
}
div[data-testid="stSegmentedControl"] button[aria-checked="true"] {
  background: #b96b35 !important;
  color: white !important;
  box-shadow: 0 3px 10px rgba(185, 107, 53, 0.3) !important;
}
div[data-testid="stSegmentedControl"] button[aria-checked="true"] p,
div[data-testid="stSegmentedControl"] button[aria-checked="true"] span {
  color: white !important;
  font-weight: 800 !important;
}
</style>
"""
