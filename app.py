import sys
from pathlib import Path

SERVICES_DIR = Path(__file__).resolve().parent / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

import json
from datetime import date

import pandas as pd
import streamlit as st

from ai_service import call_ai
from business_service import BRANCHES, SLOT_NAMES, all_rooms, availability_grid, check_extension_availability, get_room, money, search_rooms, slot_info_for_room
from output_validator import validate_output
from prompt_template import OUTPUT_SCHEMA, build_prompt
from storage import (
    connect,
    add_extension, add_review, assign_slot_group_to_room, authenticate, authenticate_with_status,
    cancel_booking, change_password, check_and_update_overstays, check_in_booking, check_out_booking,
    check_password_strength, consume_otp, create_booking, dashboard_metrics, escalate_review, generate_otp,
    get_room_slot_group, get_user_by_email, get_user_by_id, get_user_stats, init_db,
    latest_room_operations, list_bookings, list_reviews, list_transactions, list_users, mark_paid,
    reconcile_transaction, register_customer, release_expired_holds, reset_password_demo,
    reset_password_with_otp, set_user_active, set_user_scope, unlock_user, update_booking_status,
    update_profile, upsert_room_operation, validate_email, validate_phone, verify_otp
)
try:
    from services import email_service
except ImportError:
    import email_service
from theme import COZY_CSS

st.set_page_config(page_title="CozyHome - Homestay & AI", page_icon="🏠", layout="wide", initial_sidebar_state="collapsed")
st.markdown(COZY_CSS, unsafe_allow_html=True)
init_db()

if "page" not in st.session_state: st.session_state.page = "Trang chủ"
if "user" not in st.session_state: st.session_state.user = None
if "selected_room" not in st.session_state: st.session_state.selected_room = None
if "search_results" not in st.session_state: st.session_state.search_results = []
if "ai_history" not in st.session_state: st.session_state.ai_history = []


def nav():
    c1, c2, c3 = st.columns([2.6, 4.8, 2.6], vertical_alignment="center")
    with c1:
        st.markdown('''
        <div style="display:flex;align-items:center;gap:12px">
            <div style="width:40px;height:40px;border-radius:12px;background:#b96b35;color:white;display:flex;align-items:center;justify-content:center;font-size:22px;box-shadow:0 4px 12px rgba(185,107,53,0.25);flex-shrink:0">⌂</div>
            <div>
                <div class="brand" style="font-size:24px;line-height:1">Cozy<span>Home</span></div>
                <div class="small-muted" style="font-size:11px;margin-top:2px">Stay Different, Feel at Home</div>
            </div>
        </div>
        ''', unsafe_allow_html=True)
    with c2:
        choices = ["Trang chủ", "Tìm phòng", "AI tư vấn", "Lượt đặt của tôi"]
        user = st.session_state.user
        if user and user["role"] != "Khách hàng": choices.append("Vận hành")
        current_page = st.session_state.page if st.session_state.page in choices else choices[0]
        selected = st.segmented_control(
            "Điều hướng",
            choices,
            default=current_page,
            label_visibility="collapsed",
            key="nav_segmented_ctrl"
        )
        if selected and selected != st.session_state.page:
            st.session_state.page = selected
            st.rerun()
    with c3:
        if st.session_state.user:
            u = st.session_state.user
            st.markdown(f"<div style='text-align:right;line-height:1.2;margin-bottom:6px'><b>{u['full_name']}</b> <span class='badge' style='margin:0 0 0 6px'>{u['role']}</span></div>", unsafe_allow_html=True)
            cu1, cu2 = st.columns(2)
            with cu1:
                if st.button("Tài khoản", key="nav_profile", use_container_width=True):
                    st.session_state.page = "Tài khoản"
                    st.rerun()
            with cu2:
                if st.button("Đăng xuất", key="nav_logout", use_container_width=True):
                    st.session_state.user = None
                    st.session_state.guest_mode = False
                    st.session_state.page = "Trang chủ"
                    st.rerun()
        else:
            if st.button("🔑 Đăng nhập / Đăng ký", key="nav_login", use_container_width=True):
                st.session_state.guest_mode = False
                st.rerun()
    st.markdown('<div class="divider" style="margin:10px 0 20px"></div>', unsafe_allow_html=True)


def room_card(c, key):
    room = get_room(c["room_id"])
    st.markdown(f'''<div class="room-card"><div class="room-art">{room['concept_name']}</div>
    <div class="small-muted">{c['branch_name']} - {room['room_type']}</div><h3 style="margin:5px 0">{c['room_name']}</h3>
    <div>{', '.join(room['amenities'][:4])}</div><div style="margin-top:8px">Tối đa <b>{c['capacity']} khách</b> - {c['start_time']}–{c['end_time']}</div>
    <div class="price" style="margin-top:10px">{money(c['price'])}</div></div>''', unsafe_allow_html=True)
    if st.button("Xem phòng & chọn giờ", key=f"view_{key}", use_container_width=True):
        st.session_state.selected_room=c["room_id"]; st.session_state.page="Chi tiết phòng"; st.rerun()


def home_page():
    st.markdown('''<div class="hero"><div class="badge">COZY STAY</div><h1>Một căn phòng đúng mood, ngay khi bạn cần.</h1>
    <p>CozyHome kết nối 3 chi nhánh tại TP.HCM trên một lịch phòng tập trung. Tìm theo giờ hoặc qua đêm, xem phòng khả dụng và nhận tư vấn AI dựa trên dữ liệu thật của hệ thống.</p></div>''', unsafe_allow_html=True)
    with st.form("quick_search"):
        kw_col, a, b, c, d, e = st.columns([1.8, 1.4, 0.9, 1.2, 1.2, 1.1])
        kw = kw_col.text_input("🔍 Từ khóa", placeholder="Tên phòng, bồn tắm, view...")
        branch_opts = [""] + list(BRANCHES.keys())
        branch = a.selectbox("Chi nhánh", branch_opts, format_func=lambda x: "Tất cả chi nhánh" if not x else BRANCHES[x])
        guests = b.number_input("Số khách", 1, 6, 2)
        day = c.date_input("Ngày", min_value=date.today())
        slot = d.selectbox("Khung giờ", ["K1", "K2", "K3", "QD"], format_func=lambda x: SLOT_NAMES[x])
        budget = e.number_input("Ngân sách tối đa", min_value=0, value=800000, step=50000)
        go = st.form_submit_button("🔍 Tìm phòng phù hợp", use_container_width=True)
    if go:
        res, _ = search_rooms(branch if branch else None, int(guests), day.isoformat(), slot, int(budget) if budget else None, keyword=kw)
        st.session_state.search_results = res
        st.session_state.page = "Tìm phòng"
        st.session_state.search_ctx = {
            "branch": branch,
            "guests": int(guests),
            "day": day.isoformat(),
            "slot": slot,
            "budget": int(budget) if budget else None,
            "keyword": kw
        }
        st.rerun()

    st.subheader("Ba không gian, ba cảm giác")
    cols = st.columns(3)
    concepts = {"BT": ("Nhịp sống trung tâm", "Đô thị & văn hóa quốc tế"), "TD": ("Một khoảng thở xanh", "Cao nguyên & thiên nhiên"), "PMH": ("Chạm chút nhiệt đới", "Biển & nhiệt đới")}
    for col, (bid, (title, sub)) in zip(cols, concepts.items()):
        with col:
            st.markdown(f'<div class="room-card"><div class="room-art">{sub}</div><h3>{BRANCHES[bid]}</h3><p>{title}</p><span class="badge">8 phòng</span><span class="badge">Theo giờ & qua đêm</span></div>', unsafe_allow_html=True)
    st.subheader("AI hỗ trợ, khách hàng quyết định")
    st.info("AI chỉ tư vấn dựa trên dữ liệu phòng, giá, khung giờ và chính sách CozyHome. AI không tự đặt phòng, thanh toán, hủy hoặc gia hạn — đúng BR-13 trong đồ án.")


def search_page():
    st.title("Tìm phòng")
    ctx = st.session_state.get("search_ctx", {})

    with st.form("search_full"):
        kw_col, a = st.columns([2.5, 1.5])
        keyword = kw_col.text_input("🔍 Tìm theo từ khóa (tên phòng, tiện ích, view, concept, mô tả...)", value=ctx.get("keyword", ""), placeholder="Ví dụ: bồn tắm, ban công, view sông, studio, lãng mạn...")
        branch_opts = [""] + list(BRANCHES.keys())
        default_b_idx = branch_opts.index(ctx.get("branch")) if ctx.get("branch") in branch_opts else 0
        branch = a.selectbox("Chi nhánh", branch_opts, format_func=lambda x: "Tất cả chi nhánh" if not x else BRANCHES[x], index=default_b_idx)

        b, c, d, e, f = st.columns([1, 1.4, 1.4, 1.4, 1.8])
        guests = b.number_input("Số khách", 1, 6, int(ctx.get("guests", 2)))
        day = c.date_input("Ngày sử dụng", value=date.fromisoformat(ctx["day"]) if ctx.get("day") else date.today(), min_value=date.today())
        slot_opts = ["K1", "K2", "K3", "QD"]
        default_s_idx = slot_opts.index(ctx.get("slot", "K1")) if ctx.get("slot") in slot_opts else 0
        slot = d.selectbox("Khung giờ", slot_opts, format_func=lambda x: SLOT_NAMES[x], index=default_s_idx)
        budget = e.number_input("Ngân sách tối đa (0 = không giới hạn)", 0, 5000000, int(ctx.get("budget") or 0), 50000)
        pref = f.text_input("Ghi chú sở thích thêm", value=ctx.get("pref", ""), placeholder="Ví dụ: tầng cao, yên tĩnh, hoa tươi")

        submit = st.form_submit_button("🔍 Lọc và kiểm tra phòng khả dụng", use_container_width=True)

    # Gợi ý từ khóa tìm kiếm nhanh
    st.markdown('<div style="font-size:12.5px;color:#786457;margin-bottom:6px">💡 <b>Gợi ý tìm nhanh theo tiện ích & concept:</b></div>', unsafe_allow_html=True)
    tag_cols = st.columns(6)
    quick_tags = ["bồn tắm", "ban công", "view hồ", "Deluxe", "Bến Thành", "bếp mini"]
    for idx, tag in enumerate(quick_tags):
        with tag_cols[idx]:
            if st.button(f"🏷️ {tag}", key=f"quick_tag_{idx}", use_container_width=True):
                st.session_state.search_ctx = st.session_state.get("search_ctx", {})
                st.session_state.search_ctx["keyword"] = tag
                res, _ = search_rooms(
                    branch if branch else None, int(guests), day.isoformat(), slot,
                    int(budget) if budget else None, keyword=tag
                )
                st.session_state.search_results = res
                st.rerun()

    if submit or st.session_state.get("search_results") is None:
        prefs = [x.strip() for x in pref.split(",") if x.strip()]
        res, trace = search_rooms(
            branch if branch else None, int(guests), day.isoformat(), slot,
            int(budget) if budget else None, preferences=prefs, keyword=keyword
        )
        st.session_state.search_results = res
        st.session_state.search_ctx = {
            "branch": branch,
            "guests": int(guests),
            "day": day.isoformat(),
            "slot": slot,
            "budget": int(budget) if budget else None,
            "keyword": keyword,
            "pref": pref
        }

    res = st.session_state.get("search_results", [])
    kw_info = f" khớp từ khóa '<b>{keyword}</b>'" if keyword else ""
    st.markdown(f"<div style='margin:14px 0 10px;font-size:14px;color:#5c3822'>🎯 Tìm thấy <b>{len(res)}</b> phòng khả dụng{kw_info}. Điều kiện khung giờ và trạng thái vận hành đã được kiểm tra nghiêm ngặt (BR-01, BR-08).</div>", unsafe_allow_html=True)
    if not res:
        st.warning("Không có phòng phù hợp với điều kiện tìm kiếm. Hãy thử đổi từ khóa, đổi ngày hoặc nới lỏng ngân sách.")
    for i in range(0, len(res), 3):
        cols = st.columns(3)
        for col, cand in zip(cols, res[i:i+3]):
            with col:
                room_card(cand, f"{i}_{cand['room_id']}")


def room_detail_page():
    rid=st.session_state.selected_room
    room=get_room(rid) if rid else None
    if not room: st.warning("Chưa chọn phòng."); return
    st.button("← Quay lại tìm phòng", on_click=lambda: st.session_state.update(page="Tìm phòng"))
    left,right=st.columns([1.3,1])
    with left:
        st.markdown(f'<div class="room-art" style="height:310px;font-size:26px">{room["concept_name"]}</div>',unsafe_allow_html=True)
        st.title(room["room_name"]); st.write(room["description"])
        st.write("**Tiện nghi:** "+", ".join(room["amenities"]))
        st.write(f"**Sức chứa:** {room['capacity']} khách - **Diện tích:** {room['area']} m² - **Giường:** {room['bed_type']}")
    with right:
        st.subheader("Chọn thời gian")
        day=st.date_input("Ngày",min_value=date.today(),key="detail_date")
        slots=slot_info_for_room(rid)
        code=st.radio("Khung",[s["khung_code"] for s in slots],format_func=lambda x:next(f"{s['label']} - {s['start_time']}–{s['end_time']} - {money(s['price'])}" for s in slots if s['khung_code']==x))
        chosen=next(s for s in slots if s["khung_code"]==code)
        # show grid inspired by Trần Anh The Home
        st.caption("Lịch 15 ngày — xanh: còn trống, xám: đã có lượt đặt/không sẵn sàng")
        grid=availability_grid(rid,15)
        df=pd.DataFrame([{"Ngày":g["date"],**{SLOT_NAMES[k]:("Còn trống" if g[k] else "Đã đặt") for k in ("K1","K2","K3","QD")}} for g in grid])
        st.dataframe(df,use_container_width=True,hide_index=True)
        if st.button("Đặt phòng này",use_container_width=True):
            st.session_state.booking_draft={"room_id":rid,"branch_id":room["branch_id"],"booking_date":day.isoformat(),"khung_code":code,"start_time":chosen["start_time"],"end_time":chosen["end_time"],"amount":chosen["price"]}; st.session_state.page="Đặt phòng"; st.rerun()


def account_page():
    st.title("Tài khoản CozyHome")
    u = st.session_state.user

    if u:
        st.markdown(f"### Xin chào, **{u['full_name']}** 👋")
        st.caption(f"Vai trò: **{u['role']}** - Email: **{u['email']}** - SĐT: **{u.get('phone') or 'Chưa cập nhật'}**")

        stats = get_user_stats(u["id"])
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f'<div class="stat-pill"><div class="num">{stats["total_bookings"]}</div><div class="lbl">Tổng lượt đặt</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="stat-pill"><div class="num">{stats["upcoming_stays"]}</div><div class="lbl">Chuyến sắp tới</div></div>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div class="stat-pill"><div class="num">{stats["completed_stays"]}</div><div class="lbl">Đã hoàn tất</div></div>', unsafe_allow_html=True)
        with c4:
            st.markdown(f'<div class="stat-pill"><div class="num">{money(stats["total_spent"])}</div><div class="lbl">Tổng chi tiêu</div></div>', unsafe_allow_html=True)

        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        tab_prof, tab_pw = st.tabs(["👤 Cập nhật thông tin cá nhân", "🔒 Đổi mật khẩu"])
        with tab_prof:
            with st.form("form_update_profile"):
                new_name = st.text_input("Họ và tên", value=u["full_name"])
                new_phone = st.text_input("Số điện thoại", value=u.get("phone") or "", help="10 số di động Việt Nam (03x, 05x, 07x, 08x, 09x)")
                st.text_input("Địa chỉ Email", value=u["email"], disabled=True)
                if st.form_submit_button("Lưu thay đổi"):
                    ok, msg = update_profile(u["id"], new_name, new_phone)
                    if ok:
                        st.session_state.user = get_user_by_id(u["id"])
                        st.success(msg)
def render_auth_tabs():
    t1, t2, t3 = st.tabs(["🔑 Đăng nhập", "📝 Đăng ký thành viên", "❓ Quên mật khẩu"])

    with t1:
        st.subheader("Đăng nhập tài khoản")
        with st.form("login_form"):
            email = st.text_input("Email", value="demo@cozyhome.vn")
            pw = st.text_input("Mật khẩu", type="password", value="123456")
            submitted = st.form_submit_button("Đăng nhập ngay", use_container_width=True)
            if submitted:
                if not validate_email(email):
                    st.error("Địa chỉ email không đúng định dạng.")
                else:
                    user_found, msg = authenticate_with_status(email, pw)
                    if user_found:
                        st.session_state.user = user_found
                        st.session_state.guest_mode = False
                        if user_found["role"] != "Khách hàng":
                            st.session_state.page = "Vận hành"
                        else:
                            st.session_state.page = "Trang chủ"
                        st.success(f"Chào mừng {user_found['full_name']} đã đăng nhập thành công!")
                        st.rerun()
                    else:
                        st.error(msg)

    with t2:
        st.subheader("Đăng ký thành viên CozyHome")
        reg_step = st.session_state.get("reg_step", "form")

        if reg_step == "otp":
            reg_data = st.session_state.get("reg_data", {})
            st.info(f"📧 Mã OTP xác thực 6 số đã được gửi tới email: **{reg_data.get('email')}** (Hiệu lực trong 5 phút).\n\n*Nếu không nhận được thư, vui lòng kiểm tra kỹ thư mục Spam hoặc Quảng cáo.*")

            with st.form("form_verify_reg_otp"):
                otp_input = st.text_input("Nhập mã OTP 6 số", max_chars=6, placeholder="Ví dụ: 123456")
                verify_btn = st.form_submit_button("Xác thực OTP & Kích hoạt tài khoản", use_container_width=True)
                if verify_btn:
                    ok, msg = verify_otp(reg_data["email"], otp_input, purpose="register", consume=False)
                    if ok:
                        ok_reg, msg_reg = register_customer(reg_data["full_name"], reg_data["phone"], reg_data["email"], reg_data["password"])
                        if ok_reg:
                            consume_otp(reg_data["email"], purpose="register")
                            u_new = authenticate(reg_data["email"], reg_data["password"])
                            st.session_state.user = u_new
                            st.session_state.guest_mode = False
                            st.session_state.reg_step = "form"
                            st.session_state.page = "Trang chủ"
                            st.success("🎉 Đăng ký và kích hoạt tài khoản thành công! Chào mừng bạn gia nhập CozyHome.")
                            st.rerun()
                        else:
                            st.error(msg_reg)
                    else:
                        st.error(msg)

            if st.button("← Quay lại sửa thông tin đăng ký"):
                st.session_state.reg_step = "form"
                st.rerun()

        else:
            with st.form("reg_form"):
                r_name = st.text_input("Họ và tên", placeholder="Ví dụ: Nguyễn Văn An")
                r_phone = st.text_input("Số điện thoại (VN 10 chữ số)", placeholder="0909123456")
                r_email = st.text_input("Email", placeholder="an.nguyen@gmail.com")
                r_pw1 = st.text_input("Mật khẩu (Tối thiểu 6 ký tự)", type="password")
                r_pw2 = st.text_input("Xác nhận lại mật khẩu", type="password")
                reg_submitted = st.form_submit_button("Tiếp tục nhận mã xác thực OTP", use_container_width=True)
                if reg_submitted:
                    if not r_name.strip():
                        st.error("Vui lòng nhập họ và tên.")
                    elif not validate_phone(r_phone):
                        st.error("Số điện thoại không đúng định dạng VN (10 chữ số bắt đầu bằng 03, 05, 07, 08, 09).")
                    elif not validate_email(r_email):
                        st.error("Email không đúng định dạng.")
                    elif get_user_by_email(r_email):
                        st.error("Email này đã được sử dụng. Vui lòng đăng nhập hoặc dùng email khác.")
                    elif r_pw1 != r_pw2:
                        st.error("Mật khẩu xác nhận không khớp.")
                    else:
                        ok_pw, msg_pw = check_password_strength(r_pw1)
                        if not ok_pw:
                            st.error(msg_pw)
                        else:
                            otp_code = generate_otp(r_email, purpose="register")
                            email_service.send_otp_email(to_email=r_email, otp=otp_code, purpose="register", user_name=r_name.strip())
                            st.session_state.reg_data = {
                                "full_name": r_name.strip(),
                                "phone": r_phone.strip(),
                                "email": r_email.strip(),
                                "password": r_pw1
                            }
                            st.session_state.reg_step = "otp"
                            st.rerun()

    with t3:
        st.subheader("Khôi phục mật khẩu tài khoản")
        forgot_step = st.session_state.get("forgot_step", 1)

        if forgot_step == 1:
            st.caption("Bước 1: Nhập email tài khoản để nhận mã xác thực OTP.")
            with st.form("forgot_step1"):
                f_email = st.text_input("Email tài khoản CozyHome")
                if st.form_submit_button("Gửi mã OTP xác thực", use_container_width=True):
                    if not validate_email(f_email):
                        st.error("Địa chỉ email không đúng định dạng.")
                    elif not get_user_by_email(f_email):
                        st.error("Không tìm thấy tài khoản với email này trong hệ thống.")
                    else:
                        otp_val = generate_otp(f_email, purpose="forgot")
                        u_found = get_user_by_email(f_email)
                        email_service.send_otp_email(
                            to_email=f_email,
                            otp=otp_val,
                            purpose="forgot",
                            user_name=u_found.get("full_name") if u_found else None
                        )
                        st.session_state.forgot_email = f_email
                        st.session_state.forgot_step = 2
                        st.rerun()
        elif forgot_step == 2:
            st.caption(f"Bước 2: Xác nhận mã OTP đã gửi đến **{st.session_state.get('forgot_email')}**")
            st.info("📧 Mã OTP xác thực khôi phục mật khẩu đã được gửi đến hộp thư của bạn (hiệu lực 5 phút). Nếu không thấy email, vui lòng kiểm tra thư mục Spam.")
            with st.form("forgot_step2"):
                f_otp_input = st.text_input("Nhập mã OTP 6 số", max_chars=6)
                if st.form_submit_button("Xác thực OTP", use_container_width=True):
                    ok, msg = verify_otp(st.session_state["forgot_email"], f_otp_input, purpose="forgot", consume=False)
                    if ok:
                        st.session_state.forgot_otp_input = f_otp_input
                        st.session_state.forgot_step = 3
                        st.rerun()
                    else:
                        st.error(msg)
            if st.button("Quay lại Bước 1"):
                st.session_state.forgot_step = 1
                st.rerun()
        elif forgot_step == 3:
            st.caption("Bước 3: Thiết lập mật khẩu mới cho tài khoản.")
            with st.form("forgot_step3"):
                npw1 = st.text_input("Mật khẩu mới", type="password")
                npw2 = st.text_input("Xác nhận mật khẩu mới", type="password")
                if st.form_submit_button("Lưu mật khẩu mới", use_container_width=True):
                    if len(npw1) < 6:
                        st.error("Mật khẩu mới phải có tối thiểu 6 ký tự.")
                    elif npw1 != npw2:
                        st.error("Mật khẩu xác nhận không khớp.")
                    else:
                        otp_to_use = st.session_state.get("forgot_otp_input", "")
                        ok, msg = reset_password_with_otp(st.session_state["forgot_email"], otp_to_use, npw1)
                        if ok:
                            st.session_state.forgot_step = 1
                            if "forgot_otp_input" in st.session_state:
                                del st.session_state.forgot_otp_input
                            st.success(msg)
                        else:
                            st.error(msg)


def auth_screen():
    st.markdown('''
    <div style="text-align:center;padding:16px 0 20px">
        <div style="display:inline-flex;align-items:center;gap:12px">
            <div style="font-size:38px">🏠</div>
            <div style="text-align:left">
                <div style="font-size:30px;font-weight:800;color:#3a2215;line-height:1.1">Cozy<span style="color:#b96b35">Home</span></div>
                <div style="font-size:12.5px;color:#786457">Hệ thống đặt phòng trực tuyến & Tư vấn AI</div>
            </div>
        </div>
        <h2 style="margin:14px 0 6px;color:#3a2215;font-size:24px">Cổng Đăng Nhập & Đăng Ký Riêng Biệt</h2>
        <p style="color:#786457;max-width:540px;margin:0 auto;font-size:14px">Vui lòng đăng nhập tài khoản để vào hệ thống, quản lý đơn phòng, nhận tư vấn Cozy AI và thực hiện vận hành.</p>
    </div>
    ''', unsafe_allow_html=True)

    col_info, col_form = st.columns([1, 1.18], gap="large")

    with col_info:
        st.markdown('''
        <div style="background:linear-gradient(145deg,#3a2215 0%,#5a341e 50%,#874922 100%);color:white;padding:28px 24px;border-radius:18px;box-shadow:0 8px 24px rgba(80,45,20,0.12)">
            <span class="badge" style="background:rgba(255,255,255,0.25);color:white">COZY STAY - TP. HỒ CHÍ MINH</span>
            <h3 style="color:white;margin:12px 0 10px;font-size:20px">Lưu trú đô thị phong cách, tiện nghi</h3>
            <p style="color:rgba(255,255,255,0.85);font-size:13px;line-height:1.6">Kết nối 3 chi nhánh trung tâm trên một lịch phòng tập trung. Kiểm tra phòng khả dụng tức thì và thanh toán VietQR tự động.</p>
            <div style="margin-top:16px;font-size:12.5px;line-height:1.8">
                <div>🏨 <b>3 Chi nhánh:</b> Bến Thành - Thảo Điền - Phú Mỹ Hưng</div>
                <div>⏱ <b>4 Nhóm khung giờ:</b> Sáng, Chiều, Tối, Qua đêm (BR-01)</div>
                <div>🤖 <b>Trợ lý Cozy AI:</b> Đề xuất phòng chuẩn candidate_rooms (BR-13)</div>
                <div>💳 <b>VietQR MBBank:</b> Giữ chỗ 10 phút bảo mật chuẩn BR-04</div>
            </div>
        </div>
        ''', unsafe_allow_html=True)

        st.markdown('''
        <div style="margin:20px 0 10px;padding:12px 14px;background:#fdf6ef;border-radius:14px;border:1px solid #ebd8c8">
            <div style="font-weight:800;color:#3a2215;font-size:13.5px;margin-bottom:4px">⚡ CHỌN NHÓM TRẢI NGHIỆM ĐỒ ÁN (2 NHÓM CHÍNH):</div>
            <div style="font-size:12px;color:#786457">Hệ thống phân tách thành 2 luồng: Khách hàng (User) và Quản trị vận hành (Admin).</div>
        </div>
        ''', unsafe_allow_html=True)

        # =============================================================
        # NHÓM 1: USER (KHÁCH HÀNG BÌNH THƯỜNG)
        # =============================================================
        st.markdown('''
        <div style="display:flex;align-items:center;justify-content:space-between;margin:12px 0 6px">
            <span style="font-weight:800;color:#3a2215;font-size:13.5px">👤 NHÓM 1: USER (Khách hàng)</span>
            <span class="badge badge-success" style="margin:0;font-size:11px">Giao diện khách</span>
        </div>
        ''', unsafe_allow_html=True)

        c_u1, c_u2 = st.columns([1.35, 1.0])
        with c_u1:
            if st.button("🔑 Đăng nhập User (Khách hàng)", key="btn_quick_user", use_container_width=True):
                u_demo, _ = authenticate_with_status("demo@cozyhome.vn", "123456")
                if u_demo:
                    st.session_state.user = u_demo
                    st.session_state.guest_mode = False
                    st.session_state.page = "Trang chủ"
                    st.success("Đã đăng nhập thành công với tài khoản Khách hàng (User)!")
                    st.rerun()
        with c_u2:
            if st.button("👀 Khách vãng lai →", key="btn_guest_browse", use_container_width=True):
                st.session_state.guest_mode = True
                st.session_state.page = "Trang chủ"
                st.rerun()

        # =============================================================
        # NHÓM 2: ADMIN (QUẢN TRỊ & VẬN HÀNH NỘI BỘ)
        # =============================================================
        st.markdown('''
        <div style="display:flex;align-items:center;justify-content:space-between;margin:16px 0 6px">
            <span style="font-weight:800;color:#3a2215;font-size:13.5px">🛡️ NHÓM 2: ADMIN & VẬN HÀNH</span>
            <span class="badge badge-warning" style="margin:0;font-size:11px">Phân quyền nghiệp vụ</span>
        </div>
        <div style="font-size:12px;color:#786457;margin-bottom:8px">Mỗi tài khoản mở ra màn hình vai trò tương ứng với nghiệp vụ đó:</div>
        ''', unsafe_allow_html=True)

        admin_roles = [
            ("🛎️ Lễ tân BT", "letan.bt@cozyhome.vn", "Check-in/out, cảnh báo quá giờ, khiếu nại"),
            ("🧹 Buồng phòng", "buong.bt@cozyhome.vn", "Chu trình vệ sinh phòng 4 bước"),
            ("📊 Kế toán", "ketoan@cozyhome.vn", "Đối soát giao dịch hoàn tiền & doanh thu"),
            ("🏢 Quản lý chuỗi", "quanly@cozyhome.vn", "Cấu hình 4 nhóm khung giờ & khiếu nại vượt cấp"),
            ("⚙️ Quản trị viên (Admin)", "admin@cozyhome.vn", "Phân quyền người dùng & mở khóa tài khoản")
        ]

        adm_c1, adm_c2 = st.columns(2)
        for idx, (r_title, r_email, r_help) in enumerate(admin_roles):
            target_col = adm_c1 if idx % 2 == 0 else adm_c2
            if idx == 4:
                # Quản trị viên cho trải dài ở cột 1 & 2
                pass
            with target_col:
                if st.button(r_title, key=f"quick_adm_{idx}", use_container_width=True, help=f"Tài khoản: {r_email} - Nghiệp vụ: {r_help}"):
                    u_demo, _ = authenticate_with_status(r_email, "123456")
                    if u_demo:
                        st.session_state.user = u_demo
                        st.session_state.guest_mode = False
                        st.session_state.page = "Vận hành"
                        st.success(f"Đăng nhập thành công với vai trò: {u_demo['role']}!")
                        st.rerun()

    with col_form:
        render_auth_tabs()


def account_page():
    st.title("Tài khoản CozyHome")
    u = st.session_state.user

    if u:
        st.markdown(f"### Xin chào, **{u['full_name']}** 👋")
        st.caption(f"Vai trò: **{u['role']}** - Email: **{u['email']}** - SĐT: **{u.get('phone') or 'Chưa cập nhật'}**")

        stats = get_user_stats(u["id"])
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f'<div class="stat-pill"><div class="num">{stats["total_bookings"]}</div><div class="lbl">Tổng lượt đặt</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="stat-pill"><div class="num">{stats["upcoming_stays"]}</div><div class="lbl">Chuyến sắp tới</div></div>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div class="stat-pill"><div class="num">{stats["completed_stays"]}</div><div class="lbl">Đã hoàn tất</div></div>', unsafe_allow_html=True)
        with c4:
            st.markdown(f'<div class="stat-pill"><div class="num">{money(stats["total_spent"])}</div><div class="lbl">Tổng chi tiêu</div></div>', unsafe_allow_html=True)

        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        tab_prof, tab_pw = st.tabs(["👤 Cập nhật thông tin cá nhân", "🔒 Đổi mật khẩu"])
        with tab_prof:
            with st.form("form_update_profile"):
                new_name = st.text_input("Họ và tên", value=u["full_name"])
                new_phone = st.text_input("Số điện thoại", value=u.get("phone") or "", help="10 số di động Việt Nam (03x, 05x, 07x, 08x, 09x)")
                st.text_input("Địa chỉ Email", value=u["email"], disabled=True)
                if st.form_submit_button("Lưu thay đổi"):
                    ok, msg = update_profile(u["id"], new_name, new_phone)
                    if ok:
                        st.session_state.user = get_user_by_id(u["id"])
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
        with tab_pw:
            with st.form("form_change_pw"):
                old_pw = st.text_input("Mật khẩu hiện tại", type="password")
                new_pw = st.text_input("Mật khẩu mới", type="password")
                cfm_pw = st.text_input("Xác nhận mật khẩu mới", type="password")
                if st.form_submit_button("Cập nhật mật khẩu"):
                    if new_pw != cfm_pw:
                        st.error("Mật khẩu xác nhận không khớp.")
                    else:
                        ok, msg = change_password(u["id"], old_pw, new_pw)
                        if ok: st.success(msg)
                        else: st.error(msg)
        return

    auth_screen()


def booking_page():
    d = st.session_state.get("booking_draft")
    if not d:
        st.warning("Chưa có thông tin phòng cần đặt. Vui lòng chọn phòng trước.")
        if st.button("Đi đến Tìm phòng"):
            st.session_state.page = "Tìm phòng"
            st.rerun()
        return

    if not st.session_state.user:
        st.warning("Theo quy tắc nghiệp vụ CozyHome (BR-02), bạn cần đăng nhập tài khoản trước khi xác nhận đặt phòng và thanh toán.")
        if st.button("Đến trang Đăng nhập / Đăng ký"):
            st.session_state.page = "Tài khoản"
            st.rerun()
        return

    room = get_room(d["room_id"])
    u = st.session_state.user
    st.title("Xác nhận thông tin & Thanh toán")

    col_left, col_right = st.columns([1.1, 1.3])
    with col_left:
        st.markdown(f'''
        <div class="room-card">
            <div class="room-art">{room["concept_name"]}</div>
            <h3>{room["room_name"]}</h3>
            <div class="small-muted">{room["branch_name"]} - {room["room_type"]}</div>
            <hr style="margin:12px 0;border:0;border-top:1px solid #eadccf" />
            <div>📅 <b>Ngày:</b> {d["booking_date"]}</div>
            <div>⏰ <b>Khung:</b> {SLOT_NAMES[d["khung_code"]]} ({d["start_time"]}–{d["end_time"]})</div>
            <div>👥 <b>Sức chứa:</b> Tối đa {room["capacity"]} khách</div>
            <div class="price" style="margin-top:14px">Tổng tiền: {money(d["amount"])}</div>
        </div>
        ''', unsafe_allow_html=True)

    with col_right:
        code = st.session_state.get("pending_payment")
        if not code:
            with st.form("booking_confirm"):
                name = st.text_input("Họ tên khách lưu trú", value=u["full_name"])
                phone = st.text_input("Số điện thoại nhận xác nhận", value=u.get("phone") or "")
                guests = st.number_input("Số khách thực tế", 1, int(room["capacity"]), min(2, int(room["capacity"])))
                note = st.text_area("Ghi chú đặc biệt (check-in sớm, trang trí, v.v.)")
                agree = st.checkbox("Tôi đồng ý với chính sách giữ chỗ và hủy phòng CozyHome", value=True)
                submit_btn = st.form_submit_button("Xác nhận & Chuyển sang Thanh toán", use_container_width=True)

                if submit_btn:
                    if not agree:
                        st.error("Vui lòng đồng ý với chính sách đặt phòng.")
                    elif not validate_phone(phone):
                        st.error("Số điện thoại không đúng định dạng.")
                    else:
                        try:
                            new_code = create_booking(
                                user_id=u["id"], room_id=d["room_id"], branch_id=d["branch_id"],
                                booking_date=d["booking_date"], khung_code=d["khung_code"],
                                start_time=d["start_time"], end_time=d["end_time"],
                                guests=int(guests), amount=int(d["amount"]),
                                customer_name=name, customer_phone=phone, note=note
                            )
                            st.session_state.pending_payment = new_code
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))
        else:
            vietqr_url = f"https://img.vietqr.io/image/MB-0909000001-compact2.png?amount={d['amount']}&addInfo={code}&accountName=COZYHOME%20VIETNAM"
            st.markdown(f'''
            <div class="vietqr-card">
                <div class="vietqr-badge">VIETQR NỘI ĐỊA - MBBANK</div>
                <h3 style="margin:5px 0">Mã đơn phòng: {code}</h3>
                <div class="small-muted">Quét mã bằng app ngân hàng bất kỳ để chuyển khoản</div>
                <div class="vietqr-qr">
                    <img src="{vietqr_url}" width="320" style="max-width:100%; border-radius:14px; box-shadow:0 8px 24px rgba(0,0,0,0.09); display:block; margin:14px auto;" alt="VietQR" />
                </div>
                <div style="text-align:left;font-size:13.5px;line-height:1.7;background:#fffaf3;padding:12px 16px;border-radius:12px;border:1px solid #ebd9cb">
                    <div><b>Ngân hàng:</b> MBBank (Quân Đội)</div>
                    <div><b>Số tài khoản:</b> 0909000001</div>
                    <div><b>Chủ tài khoản:</b> COZYHOME VIETNAM</div>
                    <div><b>Số tiền:</b> <span style="color:#b96b35;font-weight:800">{money(d['amount'])}</span></div>
                    <div><b>Nội dung CK:</b> <span style="font-family:monospace;font-weight:800;color:#60381f">{code}</span></div>
                </div>
                <div style="margin-top:10px"><span class="badge badge-warning">⏱ Thời gian giữ chỗ thanh toán: 10 phút (theo quy tắc BR-04)</span></div>
            </div>
            ''', unsafe_allow_html=True)

            st.write("")
            if st.button("✅ Mô phỏng thanh toán thành công (Webhook Ngân hàng)", use_container_width=True):
                mark_paid(code)
                st.session_state.pending_payment = None
                st.session_state.booking_draft = None
                st.session_state.page = "Lượt đặt của tôi"
                st.success("Thanh toán thành công! Vé phòng đã được kích hoạt.")
                st.rerun()


def my_bookings_page():
    st.title("Lượt đặt của tôi")
    u = st.session_state.user
    if not u:
        st.info("Vui lòng đăng nhập để xem danh sách vé và lượt đặt phòng của bạn.")
        if st.button("Đăng nhập ngay"):
            st.session_state.page = "Tài khoản"
            st.rerun()
        return

    rows = list_bookings(user_id=u["id"]) if u["role"] == "Khách hàng" else list_bookings(branch_id=u.get("branch_id"))
    if not rows:
        st.caption("Bạn chưa có lượt đặt nào. Hãy khám phá và đặt phòng ngay nhé!")
        if st.button("Tìm phòng ngay"):
            st.session_state.page = "Tìm phòng"
            st.rerun()
        return

    for r in rows:
        status_color = "badge-success" if r["status"] in ("Đã xác nhận", "Đã check-in", "Đã hoàn tất") else ("badge-danger" if r["status"] == "Đã hủy" else "badge-warning")
        qr_checkin = f"https://api.qrserver.com/v1/create-qr-code/?size=120x120&data={r['booking_code']}"

        st.markdown(f'''
        <div class="ticket-card">
            <div class="ticket-header">
                <div>
                    <span class="ticket-code">{r['booking_code']}</span>
                    <span style="margin-left:10px;font-size:14px;color:#806f63">Ngày đặt: {r['booking_date']}</span>
                </div>
                <div>
                    <span class="badge {status_color}">{r['status']}</span>
                    <span class="badge">{r['payment_status']}</span>
                </div>
            </div>
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap">
                <div>
                    <h3 style="margin:4px 0">{r['room_id']} - Khung {r['khung_code']} ({r['start_time']}–{r['end_time']})</h3>
                    <div>👥 {r['guests']} khách - 💰 <b>{money(r['amount'])}</b></div>
                    <div class="small-muted">Khách đặt: {r['customer_name']} - SĐT: {r['customer_phone']}</div>
                </div>
                <div style="text-align:center;padding:6px">
                    <img src="{qr_checkin}" width="85" style="border-radius:8px;border:1px solid #ebd9cb" alt="QR Check-in" />
                    <div style="font-size:10px;color:#806f63;margin-top:2px">Mã QR Check-in</div>
                </div>
            </div>
        </div>
        ''', unsafe_allow_html=True)

        if u["role"] == "Khách hàng":
            act_col1, act_col2 = st.columns([1, 1.4])
            with act_col1:
                if r["status"] not in ("Đã hủy", "Đã check-in", "Đã hoàn tất", "Quá giờ - chưa checkout"):
                    if st.button(f"❌ Hủy lượt đặt {r['booking_code']}", key=f"cancel_{r['booking_code']}"):
                        refund = cancel_booking(r["booking_code"])
                        st.success("Đã ghi nhận hủy lượt đặt." + (f" Khoản hoàn demo {money(refund)} đã chuyển sang đối soát." if refund else ""))
                        st.rerun()

            # ---------------------------------------------------------
            # TÍNH NĂNG GIA HẠN THÊM GIỜ (BR-06, UC-03)
            # ---------------------------------------------------------
            can_extend_status = r["status"] in ("Đã xác nhận", "Chờ thanh toán", "Chờ check-in", "Đã check-in", "Quá giờ - chưa checkout")
            if can_extend_status:
                ext_info = check_extension_availability(r["room_id"], r["booking_date"], r["khung_code"])
                is_overstay = r["status"] == "Quá giờ - chưa checkout"
                exp_label = f"⚠️ GIA HẠN KHẨN CẤP ({r['booking_code']})" if is_overstay else f"⏱️ Gia hạn thêm giờ (BR-06) - {r['booking_code']}"
                with st.expander(exp_label, expanded=is_overstay):
                    if ext_info["can_extend"]:
                        st.markdown(f'''
                        <div style="background:#f4fbf5;border:1px solid #c8e6c9;border-radius:12px;padding:12px 14px;margin-bottom:10px">
                            <div style="font-weight:700;color:#2e7d32;font-size:13.5px">✅ Khung kế tiếp đang KHẢ DỤNG:</div>
                            <div style="font-size:13px;color:#1b5e20;margin:6px 0;line-height:1.5">
                                • <b>Khung tiếp theo:</b> {ext_info['next_khung_name']} ({ext_info['start_time']}–{ext_info['end_time']})<br>
                                • <b>Ngày áp dụng:</b> {ext_info['next_date']}<br>
                                • <b>Chi phí gia hạn:</b> <b style="color:#b96b35;font-size:14.5px">{money(ext_info['price'])}</b>
                            </div>
                            <div style="font-size:11.5px;color:#558b2f;border-top:1px dashed #c8e6c9;padding-top:6px;margin-top:6px">
                                📌 <i>Quy tắc BR-06: Gia hạn cùng phòng cho cùng khách hàng không phát sinh yêu cầu dọn vệ sinh giữa 2 khoảng thời gian liên tiếp.</i>
                            </div>
                        </div>
                        ''', unsafe_allow_html=True)
                        if st.button(f"💳 Xác nhận gia hạn & Thanh toán {money(ext_info['price'])}", key=f"btn_ext_{r['booking_code']}", use_container_width=True):
                            try:
                                add_extension(
                                    r["booking_code"], r["room_id"], ext_info["next_date"],
                                    ext_info["next_khung"], ext_info["start_time"], ext_info["end_time"],
                                    int(ext_info["price"])
                                )
                                if is_overstay:
                                    with connect() as conn:
                                        conn.execute("UPDATE bookings SET status='Đã check-in' WHERE booking_code=?", (r["booking_code"],))
                                st.success(f"🎉 Gia hạn thành công! Bạn đã được giữ chỗ khung {ext_info['next_khung_name']} ({ext_info['start_time']}–{ext_info['end_time']}).")
                                st.rerun()
                            except ValueError as e:
                                st.error(str(e))
                    else:
                        st.warning(f"⚠️ Không thể gia hạn: {ext_info['reason']}")

            if r["status"] == "Đã hoàn tất":
                with st.expander("⭐ Viết đánh giá cho kỳ nghỉ này"):
                    rating = st.slider("Điểm hài lòng", 1, 5, 5, key=f"rate_{r['booking_code']}")
                    content = st.text_input("Nhận xét của bạn", key=f"rev_{r['booking_code']}", placeholder="Cảm nhận về phòng, vệ sinh, dịch vụ...")
                    if st.button("Gửi đánh giá", key=f"sendrev_{r['booking_code']}"):
                        try:
                            add_review(r["booking_code"], u["id"], rating, content)
                            st.success("Cảm ơn bạn đã chia sẻ đánh giá!")
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))
        st.write("")


def ai_page():
    st.title("Cozy AI - Tư vấn phòng")
    st.caption("Kiến trúc V3: Python lọc điều kiện cứng → AI diễn giải/xếp hạng → validator kiểm tra output. Nếu không có API key, hệ thống dùng fallback xác định để website vẫn trình diễn được.")
    a,b,c,d=st.columns(4)
    branch=a.selectbox("Chi nhánh",list(BRANCHES),format_func=lambda x:BRANCHES[x],key="ai_branch")
    guests=b.number_input("Số khách",1,6,2,key="ai_guests")
    day=c.date_input("Ngày",min_value=date.today(),key="ai_day")
    slot=d.selectbox("Khung",["K1","K2","K3","QD"],format_func=lambda x:SLOT_NAMES[x],key="ai_slot")
    budget=st.number_input("Ngân sách tối đa",0,5000000,800000,50000,key="ai_budget")
    q=st.text_area("Bạn đang tìm một căn phòng như thế nào?",placeholder="Ví dụ: Mình đi 2 người, thích phòng lãng mạn, có bồn tắm, ưu tiên view thành phố.")
    if st.button("Tư vấn với Cozy AI",use_container_width=True):
        prefs=[x for x in ["lãng mạn" if "lãng mạn" in q.lower() else "", "bồn tắm" if "bồn tắm" in q.lower() else "", "view" if "view" in q.lower() else ""] if x]
        candidates,_=search_rooms(branch,int(guests),day.isoformat(),slot,int(budget) if budget else None,prefs)
        session_ctx={"branch_id":branch,"guests":int(guests),"date":day.isoformat(),"khung_code":slot,"budget_max":int(budget) if budget else None,"preferences":prefs}
        business_data={"candidate_rooms":candidates[:6]}
        system,prompt=build_prompt("v3",q,business_data,session_ctx)
        try:
            result=call_ai(system,prompt,response_schema=OUTPUT_SCHEMA)
            val=validate_output(result["text"],candidates[:6],session_ctx)
            parsed=val.get("parsed") or json.loads(result["text"])
            if not val["valid"]: st.warning("Phản hồi AI bị validator đánh dấu cần kiểm tra; website chỉ hiển thị phần đã đối chiếu với candidate_rooms.")
        except Exception:
            # Fallback tuân thủ BR-13: chỉ dùng candidate_rooms đã lọc, không bịa dữ liệu.
            if not candidates:
                parsed={"status":"no_match","customer_message":"Hiện chưa tìm thấy phòng phù hợp với các điều kiện bạn đã chọn. Bạn có thể thử đổi khung giờ, ngày hoặc ngân sách.","recommendations":[]}
            else:
                parsed={"status":"ok","customer_message":"Mình đã lọc các phòng đang phù hợp với điều kiện bắt buộc. Dưới đây là những lựa chọn nên xem trước.","recommendations":[{"room_id":x["room_id"],"reason":f"Phù hợp {x['capacity']} khách, concept {x['concept_name']} và đang còn khung đã chọn.","price":x["price"]} for x in candidates[:3]]}
        st.session_state.ai_history.append((q,parsed))
    for q0,p in reversed(st.session_state.ai_history[-3:]):
        st.markdown('<div class="ai-box">',unsafe_allow_html=True); st.write(f"**Bạn:** {q0}"); st.write(f"**Cozy AI:** {p.get('customer_message','')}")
        for rec in p.get("recommendations",[]):
            rr=next((x for x in search_rooms(branch,int(guests),day.isoformat(),slot,int(budget) if budget else None)[0] if x["room_id"]==rec["room_id"]),None)
            if rr: st.write(f"• **{rr['room_name']}** — {rec.get('reason','')} — {money(rec.get('price'))}")
        st.markdown('</div>',unsafe_allow_html=True)


def operations_page():
    u = st.session_state.user
    if not u or u["role"] == "Khách hàng":
        st.error("Bạn không có quyền truy cập khu vực vận hành nội bộ (BR-11).")
        return

    role = u["role"]
    branch_name = BRANCHES.get(u.get("branch_id"), "Toàn chuỗi CozyHome")
    st.title(f"Trung tâm vận hành - {role}")
    st.caption(f"Đang làm việc tại: **{branch_name}** | Người dùng: **{u['full_name']}**")

    # -------------------------------------------------------------
    # 1. LỄ TÂN (Receptionist - UC-04, BR-07, BR-08, BR-12)
    # -------------------------------------------------------------
    if role == "Lễ tân":
        b_id = u.get("branch_id")
        rows = list_bookings(branch_id=b_id)
        overstays = [r for r in rows if r.get("status") == "Quá giờ - chưa checkout"]

        t_rec1, t_rec2, t_rec3 = st.tabs([
            f"🛎️ Lượt đặt chi nhánh ({len(rows)})",
            f"⚠️ Quá giờ - chưa checkout ({len(overstays)})",
            "⭐ Đánh giá & Chuyển khiếu nại (BR-12)"
        ])

        with t_rec1:
            st.subheader("Danh sách lượt đặt phòng tại chi nhánh")
            if rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                st.markdown("---")
                st.subheader("Thực hiện thủ tục Check-in / Check-out (BR-08)")
                c_act1, c_act2 = st.columns(2)
                with c_act1:
                    code_in = st.selectbox(
                        "Chọn lượt đặt để Check-in:",
                        [r["booking_code"] for r in rows if r["status"] in ("Đã xác nhận", "Chờ check-in")],
                        key="sel_checkin"
                    ) if any(r["status"] in ("Đã xác nhận", "Chờ check-in") for r in rows) else None
                    if code_in:
                        if st.button("🚪 Xác nhận Khách nhận phòng (Check-in)", use_container_width=True):
                            try:
                                check_in_booking(code_in)
                                st.success(f"Đã ghi nhận Check-in thực tế cho đơn {code_in}.")
                                st.rerun()
                            except ValueError as e:
                                st.error(str(e))
                    else:
                        st.info("Hiện không có lượt đặt nào đang chờ check-in.")

                with c_act2:
                    code_out = st.selectbox(
                        "Chọn lượt đặt để Check-out:",
                        [r["booking_code"] for r in rows if r["status"] in ("Đã check-in", "Quá giờ - chưa checkout")],
                        key="sel_checkout"
                    ) if any(r["status"] in ("Đã check-in", "Quá giờ - chưa checkout") for r in rows) else None
                    if code_out:
                        if st.button("🔑 Xác nhận Khách trả phòng (Check-out)", use_container_width=True):
                            try:
                                check_out_booking(code_out, staff_name=u["full_name"])
                                st.success(f"Đã Check-out cho đơn {code_out}. Phòng đã tự động chuyển sang trạng thái 'Cần dọn' cho buồng phòng (BR-08).")
                                st.rerun()
                            except ValueError as e:
                                st.error(str(e))
                    else:
                        st.info("Hiện không có phòng nào đang lưu trú cần check-out.")
            else:
                st.info("Chưa có lượt đặt phòng nào tại chi nhánh này.")

        with t_rec2:
            st.subheader("⚠️ Danh sách phòng Quá giờ lưu trú nhưng chưa Check-out (BR-08)")
            st.caption("Quy tắc BR-08: Khi hết thời gian lưu trú mà chưa ghi nhận check-out hoặc gia hạn, hệ thống hiển thị trạng thái 'Quá giờ - chưa checkout'.")
            if overstays:
                for ov in overstays:
                    st.warning(f"🚨 **Phòng {ov['room_id']}** - Mã đơn: `{ov['booking_code']}` | Khách: **{ov['customer_name']}** ({ov['customer_phone']}) | Giờ kết thúc: **{ov['end_time']}** | Ngày: **{ov['booking_date']}**")
                    c_ov1, c_ov2 = st.columns(2)
                    with c_ov1:
                        if st.button(f"🔑 Check-out ngay ({ov['booking_code']})", key=f"btn_ov_out_{ov['booking_code']}"):
                            check_out_booking(ov["booking_code"], staff_name=u["full_name"])
                            st.success(f"Đã check-out và chuyển phòng {ov['room_id']} sang Cần dọn.")
                            st.rerun()
                    with c_ov2:
                        st.caption("Lễ tân hãy gọi điện thoại cho khách để hỗ trợ gia hạn khung giờ tiếp theo hoặc tính phụ thu quá giờ theo chính sách.")
            else:
                st.success("Tuyệt vời! Không có lượt đặt nào bị quá giờ tại chi nhánh.")

        with t_rec3:
            st.subheader("Phản hồi & Đánh giá của khách tại chi nhánh")
            st.caption("Quy tắc BR-12: Lễ tân theo dõi phản hồi trong phạm vi chi nhánh và chuyển các trường hợp vượt thẩm quyền (khiếu nại, đánh giá thấp) cho Quản lý chuỗi xử lý.")
            b_reviews = list_reviews(branch_id=b_id)
            if b_reviews:
                for rev in b_reviews:
                    is_low = rev["rating"] <= 3
                    box_color = "#fff3f3" if is_low else "#faf8f5"
                    border_color = "#ffcdd2" if is_low else "#e8ded4"
                    st.markdown(f'''
                    <div style="background:{box_color};border:1px solid {border_color};border-radius:12px;padding:14px;margin-bottom:12px">
                        <div style="display:flex;justify-content:space-between">
                            <b>Đơn #{rev['booking_code']} - {rev.get('user_name') or 'Khách hàng'}</b>
                            <span>{'⭐' * rev['rating']} ({rev['rating']}/5 sao)</span>
                        </div>
                        <div style="margin:8px 0;color:#4a382c">"{rev.get('content') or 'Không có nội dung nhận xét'}"</div>
                        <div class="small-muted">Ngày gửi: {rev.get('created_at')}</div>
                        {f'<div style="color:#d32f2f;font-weight:700;margin-top:6px">🚨 Đã chuyển lên Quản lý chuỗi xử lý: {rev.get("escalation_note")}</div>' if rev.get("escalated") else ''}
                    </div>
                    ''', unsafe_allow_html=True)

                    if is_low and not rev.get("escalated"):
                        with st.expander(f"🚨 Chuyển khiếu nại đơn #{rev['booking_code']} lên Quản lý chuỗi"):
                            esc_note = st.text_input(f"Ghi chú chuyển khiếu nại (Đơn #{rev['booking_code']})", placeholder="Lý do khách không hài lòng, đề xuất giải quyết...")
                            if st.button("Gửi lên Quản lý chuỗi", key=f"esc_{rev['id']}"):
                                if not esc_note.strip():
                                    st.error("Vui lòng nhập ghi chú khiếu nại.")
                                else:
                                    escalate_review(rev["id"], esc_note.strip())
                                    st.success("Đã chuyển khiếu nại lên Quản lý chuỗi thành công!")
                                    st.rerun()
            else:
                st.info("Chưa có đánh giá nào tại chi nhánh này.")

    # -------------------------------------------------------------
    # 2. BUỒNG PHÒNG (Housekeeping - UC-04, BR-08)
    # -------------------------------------------------------------
    elif role == "Buồng phòng":
        st.subheader("Quy trình vệ sinh & tình trạng phòng (Chuẩn BR-08)")
        st.caption("Quy tắc BR-08: Sau khi khách trả phòng, phòng được chuyển tuần tự: Cần dọn → Đang dọn → Đã vệ sinh → Sẵn sàng (hoặc Bảo trì).")

        b_id = u.get("branch_id")
        rooms = [r for r in all_rooms() if r["branch_id"] == b_id]
        latest_ops = {o["room_id"]: o for o in latest_room_operations(b_id)}

        c_hk1, c_hk2 = st.columns([1.2, 1.8])
        with c_hk1:
            st.markdown("### Cập nhật công việc")
            rid = st.selectbox("Chọn phòng:", [r["room_id"] for r in rooms], format_func=lambda x: next(f"{r['room_name']} ({x})" for r in rooms if r["room_id"] == x))
            cur_st = latest_ops.get(rid, {}).get("status", "Sẵn sàng")
            st.info(f"Trạng thái hiện tại của phòng: **{cur_st}**")

            next_status = st.selectbox("Chuyển sang trạng thái:", ["Cần dọn", "Đang dọn", "Đã vệ sinh", "Sẵn sàng", "Bảo trì"])
            hk_note = st.text_area("Ghi chú buồng phòng / vật tư hư hỏng:", placeholder="Ví dụ: Đã thay drap gối, phòng sạch sẽ sẵn sàng đón khách.")
            if st.button("Lưu cập nhật buồng phòng", use_container_width=True):
                upsert_room_operation(rid, b_id, next_status, hk_note, u["full_name"])
                st.success(f"Đã cập nhật phòng {rid} sang trạng thái '{next_status}'.")
                st.rerun()

        with c_hk2:
            st.markdown("### Tình trạng các phòng tại chi nhánh")
            room_cards = []
            for r in rooms:
                op = latest_ops.get(r["room_id"], {})
                st_name = op.get("status", r.get("operational_status", "Sẵn sàng"))
                badge_class = {
                    "Sẵn sàng": "badge-ready",
                    "Đã vệ sinh": "badge-cleaned",
                    "Đang dọn": "badge-cleaning",
                    "Cần dọn": "badge-warning",
                    "Bảo trì": "badge-maintenance"
                }.get(st_name, "badge-ready")
                room_cards.append({
                    "Mã phòng": r["room_id"],
                    "Tên phòng": r["room_name"],
                    "Trạng thái": st_name,
                    "Ghi chú gần nhất": op.get("note", "—"),
                    "Cập nhật bởi": op.get("updated_by", "Hệ thống"),
                    "Thời gian": op.get("updated_at", "—")
                })
            st.dataframe(pd.DataFrame(room_cards), use_container_width=True, hide_index=True)

    # -------------------------------------------------------------
    # 3. KẾ TOÁN (Accounting - UC-06, BR-09)
    # -------------------------------------------------------------
    elif role == "Kế toán":
        st.subheader("Đối soát giao dịch & Báo cáo doanh thu chuỗi (UC-06)")
        st.caption("Quy tắc BR-09: Mỗi giao dịch thanh toán, phụ thu, gia hạn hoặc hoàn tiền phải gắn với lượt đặt và chi nhánh phát sinh. Kế toán thực hiện đối soát trên dữ liệu hệ thống lưu trữ.")

        m = dashboard_metrics()
        c_kpi1, c_kpi2, c_kpi3, c_kpi4 = st.columns(4)
        c_kpi1.metric("Tổng lượt đặt toàn chuỗi", m["bookings"])
        c_kpi2.metric("Doanh thu thực nhận", money(m["revenue"]))
        c_kpi3.metric("Khoản hoàn tiền demo", money(m["refunds"]))
        c_kpi4.metric("Lượt lưu trú hoàn tất", m["completed"])

        t_acc1, t_acc2 = st.tabs(["📊 Đối soát giao dịch (UC-06.1)", "📈 Doanh thu theo từng chi nhánh"])

        with t_acc1:
            st.subheader("Bảng giao dịch phục vụ đối soát")
            all_tx = list_transactions()
            if all_tx:
                st.dataframe(pd.DataFrame(all_tx), use_container_width=True, hide_index=True)
                st.markdown("---")
                pending_txs = [t for t in all_tx if not t.get("reconciled")]
                if pending_txs:
                    st.markdown("### Thực hiện đối soát giao dịch")
                    sel_tx_id = st.selectbox(
                        "Chọn giao dịch cần xác nhận đối soát:",
                        [t["id"] for t in pending_txs],
                        format_func=lambda x: next(f"GD #{t['id']} - Đơn {t['booking_code']} - {t['tx_type']} - {money(t['amount'])}" for t in pending_txs if t["id"] == x)
                    )
                    if st.button("✅ Xác nhận đã đối soát với ngân hàng / cổng thanh toán", use_container_width=True):
                        try:
                            reconcile_transaction(sel_tx_id, reconciled_by=u["full_name"])
                            st.success(f"Đã hoàn tất đối soát giao dịch #{sel_tx_id}!")
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))
                else:
                    st.success("Tất cả các giao dịch phát sinh đã được đối soát đầy đủ!")
            else:
                st.info("Chưa có giao dịch nào được ghi nhận.")

        with t_acc2:
            st.subheader("Báo cáo doanh thu theo chi nhánh")
            branch_data = []
            for b_code, b_title in BRANCHES.items():
                b_metrics = dashboard_metrics(branch_id=b_code)
                branch_data.append({
                    "Mã": b_code,
                    "Chi nhánh": b_title,
                    "Số lượt đặt": b_metrics["bookings"],
                    "Lượt hoàn tất": b_metrics["completed"],
                    "Doanh thu (VNĐ)": money(b_metrics["revenue"]),
                    "Hoàn tiền (VNĐ)": money(b_metrics["refunds"])
                })
            st.dataframe(pd.DataFrame(branch_data), use_container_width=True, hide_index=True)

    # -------------------------------------------------------------
    # 4. QUẢN LÝ CHUỖI (Chain Manager - UC-05, UC-07, BR-01..03, BR-12)
    # -------------------------------------------------------------
    elif role == "Quản lý":
        st.subheader("Quản trị vận hành & cấu hình chuỗi CozyHome (UC-05)")
        m = dashboard_metrics()
        c_kpi1, c_kpi2, c_kpi3, c_kpi4 = st.columns(4)
        c_kpi1.metric("Lượt đặt toàn chuỗi", m["bookings"])
        c_kpi2.metric("Doanh thu toàn chuỗi", money(m["revenue"]))
        c_kpi3.metric("Hoàn tiền", money(m["refunds"]))
        c_kpi4.metric("Hoàn tất lưu trú", m["completed"])

        t_mgr1, t_mgr2, t_mgr3 = st.tabs([
            "📋 Giám sát lượt đặt toàn chuỗi",
            "⚙️ Cấu hình Nhóm khung giờ (BR-01, BR-02, BR-03, UC-05.2)",
            "🚨 Xử lý khiếu nại vượt thẩm quyền (BR-12, UC-07)"
        ])

        with t_mgr1:
            st.subheader("Danh sách lượt đặt trên toàn bộ 3 chi nhánh")
            all_b = list_bookings()
            st.dataframe(pd.DataFrame(all_b), use_container_width=True, hide_index=True)

        with t_mgr2:
            st.subheader("Cấu hình 4 Nhóm khung giờ chuẩn (Bảng 3.4)")
            st.markdown('''
            | Nhóm | Khung 1 | Khung 2 | Khung 3 | Khung qua đêm |
            |---|---|---|---|---|
            | **Nhóm 1 (SG01)** | 09:30 - 12:30 | 13:00 - 16:00 | 16:30 - 19:30 | 20:00 - 08:30 hôm sau |
            | **Nhóm 2 (SG02)** | 10:00 - 13:00 | 13:30 - 16:30 | 17:00 - 20:00 | 20:30 - 09:00 hôm sau |
            | **Nhóm 3 (SG03)** | 10:30 - 13:30 | 14:00 - 17:00 | 17:30 - 20:30 | 21:00 - 09:30 hôm sau |
            | **Nhóm 4 (SG04)** | 11:00 - 14:00 | 14:30 - 17:30 | 18:00 - 21:00 | 21:30 - 10:00 hôm sau |
            
            *Khoảng đệm: 30 phút giữa các khung giờ ngày và 60 phút sau khung qua đêm để phục vụ dọn phòng (BR-02).*
            ''')
            st.markdown("---")
            st.subheader("Gán hoặc thay đổi Nhóm khung giờ cho từng phòng (BR-03, UC-05.2)")
            rooms_list = all_rooms()
            c_g1, c_g2 = st.columns(2)
            with c_g1:
                sel_room_id = st.selectbox(
                    "Chọn phòng:",
                    [r["room_id"] for r in rooms_list],
                    format_func=lambda x: next(f"{r['room_name']} ({BRANCHES.get(r['branch_id'])}) - {x}" for r in rooms_list if r["room_id"] == x),
                    key="sel_assign_room"
                )
            with c_g2:
                sel_sg = st.selectbox(
                    "Gán nhóm khung giờ mới:",
                    ["N1", "N2", "N3", "N4"],
                    format_func=lambda x: f"Nhóm {x[-1]} (Mã {x})",
                    key="sel_assign_group"
                )
            if st.button("Lưu gán nhóm khung giờ cho phòng", use_container_width=True):
                assign_slot_group_to_room(sel_room_id, sel_sg)
                st.success(f"Đã gán thành công Nhóm {sel_sg[-1]} cho phòng {sel_room_id}! Lịch phòng sẽ cập nhật ngay lập tức.")
                st.rerun()

        with t_mgr3:
            st.subheader("Danh sách khiếu nại khách hàng được chuyển từ chi nhánh (BR-12)")
            esc_reviews = list_reviews(escalated_only=True)
            if esc_reviews:
                for rev in esc_reviews:
                    st.error(f"🚨 **Đơn #{rev['booking_code']}** tại **{BRANCHES.get(rev.get('branch_id'))}** | Khách: **{rev.get('user_name') or 'Khách hàng'}** | Đánh giá: **{'⭐' * rev['rating']} ({rev['rating']}/5 sao)**")
                    st.write(f"**Nội dung phản hồi của khách:** \"{rev.get('content')}\"")
                    st.info(f"**Ghi chú của Lễ tân chi nhánh:** {rev.get('escalation_note')}")
                    st.caption("Quản lý chuỗi có thể liên hệ trực tiếp khách hàng hoặc gửi voucher bồi hoàn theo chính sách.")
                    st.markdown("---")
            else:
                st.success("Hiện tại không có khiếu nại nào vượt thẩm quyền cần giải quyết.")

    # -------------------------------------------------------------
    # 5. QUẢN TRỊ VIÊN (Admin - UC-08, BR-11)
    # -------------------------------------------------------------
    elif role == "Quản trị viên":
        st.subheader("Quản trị tài khoản & phân quyền hệ thống (UC-08)")
        st.caption("Quy tắc BR-11: Quản trị viên quản lý tài khoản, vai trò và phạm vi truy cập; mở khóa tài khoản tạm khóa sau 5 lần nhập sai mật khẩu (UC-01).")

        users = list_users()
        st.dataframe(pd.DataFrame(users), use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("Điều chỉnh phân quyền & Trạng thái tài khoản")
        uid = st.selectbox(
            "Chọn tài khoản người dùng:",
            [x["id"] for x in users],
            format_func=lambda x: next(f"{u0['full_name']} ({u0['email']}) - {u0['role']} - {'🔒 BỊ KHÓA' if u0.get('locked') else 'Hoạt động'}" for u0 in users if u0['id'] == x)
        )
        target = next(x for x in users if x["id"] == uid)

        if target.get("locked"):
            st.error(f"⚠️ Tài khoản này đang bị **TẠM KHÓA** do nhập sai mật khẩu 5 lần (failed_attempts = {target.get('failed_attempts', 5)}).")
            if st.button("🔓 Mở khóa tài khoản ngay (Unlock)", use_container_width=True):
                unlock_user(uid)
                st.success(f"Đã mở khóa tài khoản {target['email']} thành công!")
                st.rerun()

        c1, c2, c3 = st.columns(3)
        role_opts = ["Khách hàng", "Lễ tân", "Buồng phòng", "Kế toán", "Quản lý", "Quản trị viên"]
        role2 = c1.selectbox("Vai trò", role_opts, index=role_opts.index(target["role"]) if target["role"] in role_opts else 0)
        branch_opts = [None, "BT", "TD", "PMH"]
        branch = c2.selectbox("Phạm vi chi nhánh", branch_opts, format_func=lambda x: "Toàn chuỗi / Không áp dụng" if x is None else BRANCHES[x], index=branch_opts.index(target["branch_id"]) if target["branch_id"] in branch_opts else 0)
        active = c3.checkbox("Kích hoạt tài khoản", value=bool(target["active"]))

        if st.button("Lưu cập nhật người dùng", use_container_width=True):
            set_user_scope(uid, role2, branch)
            set_user_active(uid, active)
            st.success("Đã cập nhật phân quyền người dùng thành công.")
            st.rerun()


if st.session_state.user is None and not st.session_state.get("guest_mode", False):
    auth_screen()
else:
    nav()
    page = st.session_state.page
    if page == "Trang chủ": home_page()
    elif page == "Tìm phòng": search_page()
    elif page == "Chi tiết phòng": room_detail_page()
    elif page == "Tài khoản": account_page()
    elif page == "Đặt phòng": booking_page()
    elif page == "Lượt đặt của tôi": my_bookings_page()
    elif page == "AI tư vấn": ai_page()
    elif page == "Vận hành": operations_page()
