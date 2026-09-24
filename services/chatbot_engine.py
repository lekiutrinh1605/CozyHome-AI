# -------------------------------------------------------------
# CozyHome — AI Chatbot Engine (Trợ lý tư vấn lưu trú CozyHome)
# Architecture: NLU + Context Memory + Business Service + NLG
# Strict Guardrails (BR-01 to BR-13) & Zero Hallucination
# -------------------------------------------------------------

from __future__ import annotations

import os
import re
import json
import unicodedata
from datetime import date as dt_date, timedelta
from typing import Any

try:
    from business_service import (
        all_rooms,
        get_room,
        money,
        search_rooms,
        slot_info_for_room,
        is_demo_available,
        get_branch_details,
        get_cancellation_policy,
        get_refund_policy,
        get_stay_policy,
        find_room_by_query,
        BRANCH_DETAILS,
    )
except ImportError:
    from services.business_service import (
        all_rooms,
        get_room,
        money,
        search_rooms,
        slot_info_for_room,
        is_demo_available,
        get_branch_details,
        get_cancellation_policy,
        get_refund_policy,
        get_stay_policy,
        find_room_by_query,
        BRANCH_DETAILS,
    )

# Thử import ai_service nếu có
try:
    import ai_service
except ImportError:
    try:
        from services import ai_service
    except ImportError:
        ai_service = None

# Thử import storage để lưu lịch sử hội thoại vĩnh viễn theo tài khoản
try:
    from services.storage import save_chat_message, get_user_chat_history
except ImportError:
    try:
        from storage import save_chat_message, get_user_chat_history
    except ImportError:
        save_chat_message = None
        get_user_chat_history = None

# -------------------------------------------------------------
# 1. Quản lý Context Phiên Hội Thoại (Session Manager)
# -------------------------------------------------------------
class SessionManager:
    _sessions: dict[str, dict[str, Any]] = {}

    @classmethod
    def get_session(cls, session_id: str) -> dict[str, Any]:
        if not session_id or session_id not in cls._sessions:
            sid = session_id or f"sess_{int(dt_date.today().strftime('%Y%m%d'))}_{os.urandom(4).hex()}"
            rehydrated_context: dict[str, Any] = {
                "branch_id": None,
                "stay_type": None,  # "hourly" | "overnight"
                "date": None,
                "khung_code": None,  # "K1", "K2", "K3", "QD"
                "hours": None,
                "guests": None,
                "budget_max": None,
                "preferences": [],
                "room_types": [],
                "last_room_id": None,
                "last_recommended_rooms": [],
                "pending_action": None,
            }
            rehydrated_history: list[dict[str, str]] = []

            # Phục hồi lịch sử hội thoại và ngữ cảnh từ SQLite nếu có (duy trì kết nối khi server reload)
            if get_user_chat_history and session_id:
                try:
                    db_msgs = get_user_chat_history(session_id=session_id, limit=20)
                    for m in db_msgs:
                        role = m.get("sender") or "user"
                        msg_text = m.get("message") or ""
                        rehydrated_history.append({"role": role, "message": msg_text})

                        if role == "user":
                            ent = extract_entities(msg_text, rehydrated_context)
                            for k, v in ent.items():
                                if v is not None:
                                    if k == "preferences" and isinstance(v, list):
                                        rehydrated_context["preferences"] = list(set(rehydrated_context.get("preferences", []) + v))
                                    else:
                                        rehydrated_context[k] = v
                        elif role == "assistant":
                            msg_clean = _norm(msg_text)
                            if "chia phong" in msg_clean and ("phuong an chia" in msg_clean or "ho tro len" in msg_clean or "ban co muon" in msg_clean):
                                rehydrated_context["pending_action"] = "suggest_split_rooms"
                except Exception:
                    pass

            cls._sessions[sid] = {
                "session_id": sid,
                "context": rehydrated_context,
                "history": rehydrated_history,
            }
            return cls._sessions[sid]
        return cls._sessions[session_id]

    @classmethod
    def update_context(cls, session_id: str, updates: dict[str, Any]) -> None:
        sess = cls.get_session(session_id)
        ctx = sess["context"]
        for k, v in updates.items():
            if v is not None:
                if k == "branch_id" and ctx.get("branch_id") != v:
                    ctx["last_room_id"] = None
                    ctx["last_recommended_rooms"] = []
                if k == "preferences" and isinstance(v, list):
                    # Merge preferences
                    merged = list(set(ctx.get("preferences", []) + v))
                    ctx["preferences"] = merged
                elif k == "room_types" and isinstance(v, list):
                    ctx["room_types"] = v
                elif k == "guests":
                    try:
                        ctx["guests"] = int(v)
                    except (ValueError, TypeError):
                        ctx["guests"] = v
                else:
                    ctx[k] = v

    @classmethod
    def add_history(cls, session_id: str, role: str, message: str) -> None:
        sess = cls.get_session(session_id)
        sess["history"].append({"role": role, "message": message})
        # Giữ tối đa 20 tin nhắn gần nhất để tránh tràn bộ nhớ
        if len(sess["history"]) > 20:
            sess["history"] = sess["history"][-20:]

    @classmethod
    def reset_session(cls, session_id: str) -> None:
        if session_id in cls._sessions:
            del cls._sessions[session_id]


# -------------------------------------------------------------
# 2. Xử lý Chuẩn hóa Chuỗi & Trích xuất Thực thể (NLU Helpers)
# -------------------------------------------------------------
def _norm(text: str) -> str:
    s = str(text).lower().replace("đ", "d").replace("Đ", "d").replace("ð", "d")
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("ascii")


def check_security_and_privacy_violation(query: str) -> bool:
    """Kiểm tra xem người dùng có yêu cầu truy cập thông tin nhạy cảm, cá nhân (PII)
    hoặc thông tin nội bộ, tài khoản quản trị hay không (AI-09)."""
    clean = _norm(query)
    sensitive_keywords = [
        "cccd", "cmnd", "can cuoc", "so dien thoai ca nhan", "sdt ca nhan",
        "thong tin ca nhan", "thong tin khach", "danh sach khach", "khach tung o",
        "khach da tung o", "thong tin dat phong cua", "lich su dat phong cua",
        "tai khoan quan tri", "mat khau", "password", "thong tin noi bo",
        "du lieu noi bo", "database", "co so du lieu", "tai khoan admin", "quyen admin"
    ]
    return any(k in clean for k in sensitive_keywords)


def check_transaction_request(query: str) -> dict[str, bool]:
    """Kiểm tra xem người dùng có yêu cầu AI tự thực hiện giao dịch hay không (BR-13/NFR-06).

    Quy tắc an toàn BR-13: AI không được tự thực hiện đặt phòng, thanh toán, hủy hoặc gia hạn.
    """
    clean = _norm(query)
    is_cancel = any(k in clean for k in [
        "huy phong giup", "huy ho", "huy giup", "huy don giup", "huy booking giup", "huy ho toi", "huy giup toi"
    ]) or bool(re.search(r"\bhuy\s+(phong\s+|don\s+|booking\s+)?(giup|ho|cho)\s+(toi|minh|em|anh|chi)\b", clean))

    is_extend = any(k in clean for k in [
        "gia han giup", "gia han ho", "gia han phong giup", "gia han ho toi", "gia han giup toi"
    ]) or bool(re.search(r"\bgia han\s+(phong\s+)?(giup|ho|cho)\s+(toi|minh|em|anh|chi)\b", clean))

    is_book = any(k in clean for k in [
        "dat phong giup", "dat giup", "dat ho", "book giup", "book ho",
        "dat phong cho toi", "dat cho toi", "dat phong ho", "book phong giup",
        "dat luon giup", "dat ho toi", "dat giup toi", "dat phong va thanh toan",
        "dat va thanh toan", "book va pay", "book phong ho", "dat phong ho toi"
    ]) or bool(re.search(r"\b(dat|book)\s+(phong\s+)?(giup|ho|cho)\s+(toi|minh|em|anh|chi)\b", clean))

    is_pay = any(k in clean for k in [
        "thanh toan giup", "thanh toan ho", "tra tien giup", "tra tien ho",
        "pay giup", "chuyen khoan giup", "chuyen tien giup", "quet ma giup",
        "quet qr giup", "thanh toan cho toi", "thanh toan luon giup",
        "thanh toan giup toi", "thanh toan ho toi", "tra tien cho toi",
        "dat phong va thanh toan", "dat va thanh toan"
    ]) or bool(re.search(r"\b(thanh toan|tra tien|chuyen khoan|pay)\s+(giup|ho|cho)\s+(toi|minh|em|anh|chi)\b", clean))

    return {
        "cancel": is_cancel,
        "extend": is_extend,
        "book": is_book,
        "pay": is_pay,
        "any": is_cancel or is_extend or is_book or is_pay,
    }


def is_affirmative_response(text: str) -> bool:
    """Kiểm tra xem câu trả lời của khách có phải là sự đồng ý, xác nhận, tiếp tục hay không."""
    clean = _norm(text).strip()
    # Nếu câu hỏi có dấu hỏi hoặc các từ hỏi nghi vấn ('?', 'khong', 'chua', 'sao', 'nao') thì không phải là câu trả lời khẳng định
    if "?" in text or any(k in clean.split() for k in ["khong", "chua", "nao", "sao", "ha"]):
        return False

    exact_matches = {
        "co", "co chu", "co chu a", "co chu shop", "co chu ban", "co nha", "co nhe", "co a", "co ak", "co luon",
        "co nha shop", "co nhe shop", "co nhe ban", "co nha ban", "co chu em", "co nha em", "co ban nhe",
        "ok", "oke", "okay", "okie", "oki", "ok nha", "ok nhe", "ok ban", "ok ad", "ok shop", "ok luon", "ok nhe shop", "okela", "ok em", "ok anh", "ok chi",
        "duoc", "duoc chu", "duoc nha", "duoc nhe", "duoc ban", "duoc a", "duoc do", "duoc chu shop", "duoc em",
        "vang", "vang a", "vang nha", "vang nhe", "vang ban", "vang shop", "da", "da vang", "da co", "da duoc", "da vang a",
        "u", "uh", "uhm", "uk", "um", "ua", "uh nha", "uh nhe",
        "dong y", "dong y nha", "nhat tri", "chot", "chot luon", "dong y luon",
        "yes", "yep", "yeah", "sure", "yup",
        "ho tro di", "ho tro minh di", "ho tro toi di", "ho tro giup", "ho tro ho",
        "len phuong an di", "len phuong an giup", "len phuong an cho minh",
        "goi y di", "goi y giup", "chia di", "chia giup", "chia ho", "xem di", "cho xem di"
    }
    if clean in exact_matches:
        return True

    # Bắt đầu bằng các từ xác nhận kèm đuôi hỗ trợ
    if clean.startswith(("ok ", "oke ", "duoc ", "vang ", "da ")):
        return True

    if clean.startswith("co ") and any(p in clean for p in ["chia", "len phuong an", "ho tro", "goi y", "xem"]):
        return True

    if any(k in clean for k in ["len phuong an", "ho tro chia", "goi y chia", "giup minh chia", "chia phong giup"]):
        return True

    return False


def is_negative_response(text: str) -> bool:
    """Kiểm tra xem câu trả lời của khách có phải là từ chối hay không."""
    clean = _norm(text).strip()
    if "?" in text or any(k in clean.split() for k in ["nao", "sao", "ha"]):
        return False
    exact_matches = {
        "khong", "hong", "thoi", "khong can", "khoi", "khoi can", "ko", "k", "no", "nope",
        "thoi khoi", "khong can dau", "thoi duoc roi", "thoi bo qua", "khong thich"
    }
    if clean in exact_matches:
        return True
    if clean.startswith(("khong can", "khoi can", "thoi khoi", "thoi khong")):
        return True
    return False


def parse_relative_date(text: str) -> str | None:
    """Chuyển đổi các từ ngữ chỉ ngày tương đối sang định dạng YYYY-MM-DD."""
    today = dt_date.today()
    clean = _norm(text)

    if "hom nay" in clean:
        return today.isoformat()
    if "ngay mai" in clean or "chieu mai" in clean or "toi mai" in clean or "sang mai" in clean:
        return (today + timedelta(days=1)).isoformat()
    if "ngay kia" in clean or "ngay mot" in clean:
        return (today + timedelta(days=2)).isoformat()
    if "cuoi tuan" in clean:
        # Thứ 7 tuần này hoặc tiếp theo
        days_ahead = 5 - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        return (today + timedelta(days=days_ahead)).isoformat()

    # Nhận diện thứ trong tuần: "thu 6", "thu 7", "chu nhat", v.v.
    weekday_map = {
        "thu 2": 0, "thu hai": 0,
        "thu 3": 1, "thu ba": 1,
        "thu 4": 2, "thu tu": 2,
        "thu 5": 3, "thu nam": 3,
        "thu 6": 4, "thu sau": 4,
        "thu 7": 5, "thu bay": 5,
        "chu nhat": 6, "cn": 6,
    }
    for wname, wday in weekday_map.items():
        if wname in clean:
            days_ahead = wday - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            return (today + timedelta(days=days_ahead)).isoformat()

    # Nhận diện ngày định dạng cụ thể: ngày 15, 15/09, 2026-09-15
    m_ymd = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", text)
    if m_ymd:
        return f"{m_ymd.group(1)}-{int(m_ymd.group(2)):02d}-{int(m_ymd.group(3)):02d}"

    m_dm = re.search(r"\b(\d{1,2})[/.-](\d{1,2})\b", text)
    if m_dm:
        d, m = int(m_dm.group(1)), int(m_dm.group(2))
        return f"{today.year}-{m:02d}-{d:02d}"

    m_day = re.search(r"ngay\s+(\d{1,2})\b", clean)
    if m_day:
        d = int(m_day.group(1))
        return f"{today.year}-{today.month:02d}-{d:02d}"

    return None


def extract_entities(query: str, current_context: dict[str, Any]) -> dict[str, Any]:
    """Bóc tách các tiêu chí và thực thể từ câu nói của người dùng."""
    clean = _norm(query)
    extracted: dict[str, Any] = {}

    # 1. Trích xuất Chi nhánh
    if any(k in clean for k in ["ben thanh", "quan 1", "q1", "le thanh ton"]):
        extracted["branch_id"] = "BT"
    elif any(k in clean for k in ["thao dien", "thu duc", "quan 2", "q2", "xuan thuy"]):
        extracted["branch_id"] = "TD"
    elif any(k in clean for k in ["phu my hung", "quan 7", "q7", "pmh", "nguyen duc canh"]):
        extracted["branch_id"] = "PMH"
    elif "tat ca" in clean or "toan chuoi" in clean or "o dau cung duoc" in clean:
        extracted["branch_id"] = None

    # Phát hiện hỏi về địa điểm ngoài CozyHome (Đà Lạt, Hà Nội, Vũng Tàu, Nha Trang)
    unsupported_places = ["da lat", "ha noi", "vung tau", "nha trang", "da nang", "can tho", "quy nhon", "phu quoc"]
    for place in unsupported_places:
        if place in clean:
            extracted["unsupported_location"] = place

    # 2. Trích xuất Hình thức lưu trú (Theo giờ vs Qua đêm)
    if (
        any(k in clean for k in ["qua dem", "o dem", "ngu dem", "luu tru qua dem", "den sang mai", "toi sang", "/dem", "dong/dem", "d/dem", "moi dem", "tra phong"])
        or (bool(re.search(r"\btu\s+(ngay\s+)?\d+.*(den|\-)\s+(ngay\s+)?\d+", clean)))
        or (bool(re.search(r"\bnhan\s+phong.*tra\s+phong\b", clean)))
    ):
        extracted["stay_type"] = "overnight"
        extracted["khung_code"] = "QD"
    elif any(k in clean for k in ["theo gio", "thue gio", "thue theo gio", "khung gio", "tam thoi"]):
        extracted["stay_type"] = "hourly"
        m_h = re.search(r"(\d+)\s*(tieng|gio|h)\b", clean)
        if m_h and not re.search(r"\d+\s*gio\s*(sang|chieu|toi|trua|dem)\b", clean):
            extracted["hours"] = int(m_h.group(1))
    elif re.search(r"\b(\d+)\s*tieng\b", clean):
        extracted["stay_type"] = "hourly"
        m_h = re.search(r"(\d+)\s*tieng\b", clean)
        if m_h:
            extracted["hours"] = int(m_h.group(1))

    # 3. Trích xuất Khung giờ cụ thể (K1, K2, K3) nếu theo giờ
    # Lọc bỏ các mốc giờ đồng hồ (ví dụ: "3 giờ sáng", "1 giờ chiều", "8h tối") để không nhầm sang ca thuê
    clean_no_clock = re.sub(r"\b\d+\s*(?:gio|h)\s*(?:sang|chieu|toi|dem|trua)\b", "", clean)
    if any(k in clean_no_clock for k in ["buoi sang", "khung sang", "ca sang", "sang mai", "sang nay", "k1"]) or bool(re.search(r"\b(vao|trong|luc)\s+sang\b", clean_no_clock)):
        extracted["khung_code"] = "K1"
        extracted["stay_type"] = extracted.get("stay_type", "hourly")
    elif any(k in clean_no_clock for k in ["buoi trua", "buoi chieu", "khung chieu", "ca chieu", "chieu mai", "chieu nay", "k2"]) or bool(re.search(r"\b(vao|trong|luc)\s+chieu\b", clean_no_clock)):
        extracted["khung_code"] = "K2"
        extracted["stay_type"] = extracted.get("stay_type", "hourly")
    elif any(k in clean_no_clock for k in ["buoi toi", "khung toi", "ca toi", "toi nay", "toi mai", "chieu toi", "k3", "toi thu ", "toi chu nhat", "toi cn"]) or bool(re.search(r"\b(vao|trong|luc)\s+toi\b", clean_no_clock)):
        extracted["khung_code"] = "K3"
        extracted["stay_type"] = extracted.get("stay_type", "hourly")

    # 4. Trích xuất Ngày
    parsed_date = parse_relative_date(query)
    if parsed_date:
        extracted["date"] = parsed_date

    # 5. Trích xuất Số khách
    # Nhận diện: "cho 2 người", "2 khách", "3 người", "cặp đôi", "gia đình", "20 người"
    m_guests = re.search(r"(\d+)\s*(nguoi|khach|ban|nam|nu)", clean)
    if m_guests:
        extracted["guests"] = int(m_guests.group(1))
    elif "cap doi" in clean or "hai nguoi" in clean or "2 nguoi" in clean:
        extracted["guests"] = 2
    elif "mot minh" in clean or "1 nguoi" in clean:
        extracted["guests"] = 1
    elif "gia dinh" in clean:
        extracted["guests"] = 4

    # 6. Trích xuất Ngân sách
    # Chuẩn hóa dạng: 600.000, 600,000, 50.000, 600k, 1.5 trieu, 600000 dong/dem
    clean_num_text = re.sub(r"(\d+)[.,](\d{3})", r"\1\2", clean)
    m_budget = re.search(r"(?:ngan sach|gia|chi phi|tam gia|muc)\s*(?:khoang|tam|duoi|toi da)?\s*(\d+(?:\.\d+)?)\s*(nghin|k|trieu|tr|dong|d|vnd)?(?:\s*/\s*(?:dem|gio|khung))?", clean_num_text)
    if not m_budget:
        m_budget = re.search(r"\b(\d+(?:\.\d+)?)\s*(nghin|k|trieu|tr|dong|d|vnd|/dem|/gio|/khung)\b", clean_num_text)
    if not m_budget:
        for m in re.finditer(r"\b(\d{5,})\b", clean_num_text):
            m_budget = m
            break

    if m_budget:
        val_str = m_budget.group(1)
        try:
            val = float(val_str)
            unit = m_budget.group(2) if m_budget.lastindex and m_budget.lastindex >= 2 else ""
            unit = (unit or "").lower()
            if unit in ["k", "nghin"]:
                extracted["budget_max"] = int(val * 1000)
            elif unit in ["trieu", "tr"]:
                extracted["budget_max"] = int(val * 1000000)
            elif val >= 10000:
                extracted["budget_max"] = int(val)
        except (ValueError, IndexError):
            pass

    # 7. Trích xuất Sở thích & Tiện nghi
    pref_keywords = {
        "bon tam": "bồn tắm",
        "ban cong": "ban công",
        "view ho": "view hồ",
        "view song": "view sông",
        "view thanh pho": "view thành phố",
        "view dep": "view đẹp",
        "bep": "bếp mini",
        "minibar": "minibar",
        "tu lanh": "minibar",
        "wifi": "wifi",
        "wi-fi": "wifi",
        "dieu hoa": "máy lạnh",
        "may lanh": "máy lạnh",
        "phong tam": "phòng tắm riêng",
        "phong tam rieng": "phòng tắm riêng",
        "wc rieng": "phòng tắm riêng",
        "ve sinh rieng": "phòng tắm riêng",
        "smart tv": "tivi",
        "tivi": "tivi",
        "yen tinh": "yên tĩnh",
        "lang man": "lãng mạn",
        "ho boi": "hồ bơi",
        "be boi": "hồ bơi",
        "ban lam viec rieng": "bàn làm việc",
        "ban lam viec": "bàn làm việc",
        "ban ghe lam viec": "bàn làm việc",
        "may say toc": "máy sấy tóc",
        "may say": "máy sấy tóc",
        "nuoc nong": "nước nóng",
        "may chieu": "máy chiếu",
        "rap phim": "máy chiếu",
        "sofa": "sofa",
        "tra dao": "trà đạo",
        "am tra": "trà đạo",
        "ca phe": "máy pha cà phê",
        "may pha ca phe": "máy pha cà phê",
        "loa": "loa bluetooth",
        "bluetooth": "loa bluetooth",
        "gac lung": "gác lửng",
        "thong tang": "gác lửng",
        "ban trang diem": "bàn trang điểm",
        "guong": "gương",
        "lo vi song": "lò vi sóng",
        "ban an": "bàn ăn",
        "view rung": "view rừng",
        "view vuon": "view vườn",
        "3 giuong": "3 giường",
        "ba giuong": "3 giường",
        "3 giuong doi": "3 giường",
        "2 giuong doi": "3 giường",
    }
    found_prefs = []
    for k, v in pref_keywords.items():
        if k in clean:
            found_prefs.append(v)
    if found_prefs:
        extracted["preferences"] = list(dict.fromkeys(found_prefs))

    # Nhận diện yêu cầu 1 phòng đơn lẻ duy nhất
    if any(k in clean for k in ["1 phong duy nhat", "mot phong duy nhat", "chi 1 phong", "chi mot phong", "phong duy nhat"]):
        extracted["single_room_only"] = True

    # Trích xuất Hạng phòng (Room Types: Standard, Deluxe, Family)
    found_types = []
    if "deluxe" in clean or "sang trong" in clean:
        found_types.append("Deluxe")
    if "standard" in clean or "tieu chuan" in clean:
        found_types.append("Standard")
    if "family" in clean or "gia dinh" in clean:
        found_types.append("Family")
    if found_types:
        extracted["room_types"] = found_types

    # 8. Trích xuất Mã phòng cụ thể
    # Ví dụ: BT-103, BT103, BT-STD-01, TD-DL-02, PMH-01, phòng thứ hai, phòng đầu tiên
    room_found = find_room_by_query(query)
    if room_found:
        extracted["specific_room_id"] = room_found["room_id"]
    elif "phong thu hai" in clean or "phong so 2" in clean or "phong thu 2" in clean:
        last_recs = current_context.get("last_recommended_rooms") or []
        if len(last_recs) >= 2:
            extracted["specific_room_id"] = last_recs[1].get("room_id")
    elif "phong dau tien" in clean or "phong thu nhat" in clean or "phong so 1" in clean:
        last_recs = current_context.get("last_recommended_rooms") or []
        if len(last_recs) >= 1:
            extracted["specific_room_id"] = last_recs[0].get("room_id")
    elif "phong nay" in clean or "phong do" in clean:
        if current_context.get("last_room_id"):
            extracted["specific_room_id"] = current_context["last_room_id"]

    return extracted


def classify_intent(query: str, extracted: dict[str, Any], context: dict[str, Any], history: list[dict[str, Any]] | None = None) -> str:
    clean = _norm(query).strip()

    # 0. Multi-turn affirmative / confirmation handling (Kết nối câu trả lời trong chuỗi hội thoại)
    last_bot_msg = ""
    if history:
        for item in reversed(history):
            if item.get("role") == "assistant":
                last_bot_msg = _norm(item.get("message", ""))
                break

    if is_affirmative_response(query):
        # Trường hợp 1: Trợ lý vừa đề xuất hỗ trợ lên phương án chia phòng
        has_split_prompt = (
            context.get("pending_action") == "suggest_split_rooms"
            or "chia phong" in last_bot_msg
            or "phuong an chia" in last_bot_msg
            or (context.get("guests") or 0) > 6
        )
        if has_split_prompt:
            context["pending_action"] = None
            return "SPLIT_ROOM_RECOMMENDATION"

        # Trường hợp 2: Trợ lý vừa hỏi có muốn tìm phòng tại 3 chi nhánh ở TP.HCM không
        if context.get("pending_action") == "suggest_hcm_branches" or "3 chi nhanh o tp.hcm" in last_bot_msg:
            context["pending_action"] = None
            return "HOMESTAY_INFORMATION"

        # Trường hợp 3: Khách có ngữ cảnh tìm phòng trước đó
        if context.get("branch_id") or context.get("guests") or context.get("stay_type"):
            return "ROOM_RECOMMENDATION"

    if is_negative_response(query):
        if context.get("pending_action") == "suggest_split_rooms" or "chia phong" in last_bot_msg or (context.get("guests") or 0) > 6:
            context["pending_action"] = None
            return "REDUCE_GUESTS_INQUIRY"

    # 1. Out of scope (hỏi ngoài CozyHome: thời tiết, viết code, bitcoin, crypto...)
    out_of_scope_patterns = [
        "thoi tiet", "bitcoin", "crypto", "chung khoan", "viet code", "lam tho",
        "chinh tri", "tong thong", "dich thuat", "toan hoc"
    ]
    if any(p in clean for p in out_of_scope_patterns):
        return "OUT_OF_SCOPE"

    # 2. Greeting / Thank you / Help
    if any(clean == g or clean.startswith(g + " ") for g in ["xin chao", "chao ban", "hello", "hi", "alo"]):
        return "GREETING"
    if any(clean == t or t in clean for t in ["cam on", "thanks", "thank you", "cam on ban"]):
        return "THANK_YOU"
    if any(clean == h for h in ["giup do", "huong dan", "help"]):
        return "HELP"

    # 3. Kiểm tra hỏi đa tiêu chí / đa câu hỏi phức hợp (COMPREHENSIVE_INQUIRY & ROOM_COMPREHENSIVE_INFO)
    specific_room = extracted.get("specific_room_id")
    has_pronoun_room = any(k in clean for k in ["phong nay", "phong do", "phong kia", "phong vua roi", "can nay", "can do"])
    has_room_mention = bool(specific_room or has_pronoun_room)
    if not has_room_mention and context.get("last_room_id") and ("phong" in clean or "can" in clean):
        has_room_mention = True
        specific_room = context.get("last_room_id")

    ask_price = any(k in clean for k in ["chi phi", "bao nhieu tien", "bao nhieu", "bang gia", "gia ca", "gia phong", "co gia bao nhieu"]) or bool(re.search(r"\bgia\b", clean))
    ask_refund = any(k in clean for k in ["hoan bao nhieu", "hoan tien", "tra lai tien", "nhan lai tien", "hoan bao nhieu phan tram", "bao lau co tien", "bao nhieu %"]) or bool(re.search(r"\bhoan\b.*\b(tien|phan tram|%)\b", clean))
    tx_req = check_transaction_request(query)
    ask_cancel = any(k in clean for k in ["huy phong", "huy booking", "huy dat phong", "huy don", "khong den", "neu toi huy", "neu minh huy", "khi huy", "huy truoc"]) or tx_req["cancel"]
    ask_amenities = any(k in clean for k in ["tien nghi", "co nhung tien nghi gi", "co gi", "dieu hoa", "wifi", "bon tam", "ban cong", "may lanh", "tien ich"])
    ask_fees = any(k in clean for k in ["phi dich vu", "thu them phi", "phu phi", "phat sinh phi", "ngoai muc gia", "phi an"])

    # Phát hiện câu hỏi phức hợp đa ý hỏi (ví dụ: Giá + Hủy hoàn tiền + Tiện nghi + Phí dịch vụ)
    multi_aspect_count = sum([bool(ask_price), bool(ask_refund or ask_cancel), bool(ask_amenities), bool(ask_fees)])
    has_category_or_branch = bool(extracted.get("branch_id") or extracted.get("room_types") or has_room_mention)

    if multi_aspect_count >= 2 and (has_category_or_branch or (ask_price and (ask_refund or ask_cancel))):
        return "COMPREHENSIVE_INQUIRY"

    if has_room_mention:
        has_policy_ask = any(k in clean for k in ["chinh sach", "nhan phong", "tra phong", "huy phong", "hoan tien"])
        if (ask_price or ask_amenities) and has_policy_ask:
            return "ROOM_COMPREHENSIVE_INFO"

    # 4. Chính sách hủy / Hoàn tiền đơn lẻ
    is_cancel = ask_cancel
    is_refund = ask_refund

    if is_cancel and is_refund:
        return "CANCELLATION_AND_REFUND_POLICY"
    if is_cancel:
        return "CANCELLATION_POLICY"
    if is_refund:
        return "REFUND_POLICY"

    # 5. Chính sách lưu trú / giờ giấc / quy định
    if any(k in clean for k in ["gio nhan phong", "gio tra phong", "checkin may gio", "checkout may gio", "nhan phong luc may gio"]):
        return "CHECKIN_CHECKOUT_POLICY"
    if tx_req["extend"] or any(k in clean for k in ["hut thuoc", "ve sinh", "gia han", "giu cho", "quy dinh luu tru", "chinh sach luu tru", "pccc"]):
        return "STAY_POLICY"

    # 6. Khuyến mãi / ưu đãi
    if any(k in clean for k in ["khuyen mai", "giam gia", "uu dai", "discount", "voucher"]):
        return "PROMOTION_POLICY"

    # 7. Hỏi chính sách thuê theo giờ chung
    if any(k in clean for k in ["co thue theo gio khong", "co cho thue theo gio khong", "thue theo gio duoc khong", "co cho thue gio khong", "co phong theo gio khong", "co thue gio khong"]):
        return "HOURLY_RENTAL_POLICY"

    # 8. Thông tin chi nhánh / Homestay CozyHome
    if any(k in clean for k in ["cozyhome la gi", "gioi thieu cozyhome", "co may chi nhanh", "co nhung chi nhanh nao", "co o dau", "co chi nhanh o"]):
        return "HOMESTAY_INFORMATION"
    if any(k in clean for k in ["nen chon chi nhanh", "chi nhanh nao dep", "chi nhanh nao tot", "nen o chi nhanh nao", "so sanh chi nhanh", "khu vuc nao dep", "nen o quan may", "nen o dau"]):
        return "BRANCH_COMPARISON"
    if (
        any(k in clean for k in ["chi nhanh ben thanh o dau", "chi nhanh thao dien o dau", "chi nhanh phu my hung o dau", "dia chi chi nhanh", "dia chi o dau"])
        or (extracted.get("branch_id") and any(k in clean for k in ["o dau", "dia chi", "vi tri", "nam o dau"]))
    ):
        return "BRANCH_INFORMATION"

    # 9. Tổng quan về các hạng phòng / loại phòng
    if not has_room_mention and (
        any(k in clean for k in ["co nhung loai phong", "co may loai phong", "cac loai phong", "hang phong nao", "co nhung hang phong", "cac hang phong", "nhung kieu phong", "cac loai phong o cozyhome", "co phong may nguoi", "family may giuong", "phong family may giuong", "family co may giuong", "family phai la 3 giuong", "family 3 giuong"])
        or (any(k in clean for k in ["phong family", "hang family"]) and any(k in clean for k in ["may giuong", "3 giuong", "giuong", "co gi"]))
    ):
        return "ROOM_CATEGORIES_OVERVIEW"

    # 10. Hỏi về phòng cụ thể (giá, tiện nghi, lịch trống, chi tiết)
    if has_room_mention:
        if (
            re.search(r"\bcon\b.*\b(khong|trong)\b", clean)
            or any(k in clean for k in ["con trong", "con phong khong", "con khong", "trong khong", "dat duoc khong"])
        ):
            return "ROOM_AVAILABILITY"
        if any(k in clean for k in ["bao nhieu tien", "gia bao nhieu", "gia phong", "chi phi", "bang gia", "gia ca"]) or bool(re.search(r"\bgia\b", clean)):
            return "ROOM_PRICE"
        if (
            any(k in clean for k in ["co ban cong", "co bon tam", "co bep", "co wifi", "co tu lanh", "tien nghi", "co gi", "co may chieu", "co sofa", "co rap phim", "co tra dao", "co ca phe", "co gac lung", "co view", "co 3 giuong", "3 giuong khong", "may giuong"])
            or (
                any(k in clean for k in ["may chieu", "rap phim", "sofa", "ban cong", "bon tam", "bep", "wifi", "tivi", "smart tv", "tra dao", "am tra", "ca phe", "gac lung", "loa", "trang diem", "guong", "lo vi song", "view song", "view ho", "view pho", "3 giuong", "may giuong", "giuong"])
                and any(w in clean for w in ["co", "khong", "trang bi", "phai la"])
            )
        ):
            return "ROOM_AMENITY"
        if any(k in clean for k in ["chi tiet", "thong tin phong", "anh phong"]):
            return "ROOM_DETAIL"

    # 11. Hỏi chung về giá hoặc tiện nghi (khi không nhắc phòng cụ thể)
    if (
        bool(re.search(r"\b(gia\s+phong|bang\s+gia|gia\s+ca|gia\s+thue|muc\s+gia)\b", clean))
        or any(k in clean for k in ["gia ca the nao", "bang gia phong", "bang gia chung", "gia trung binh", "gia phong bao nhieu", "gia ca o day the nao", "gia the nao", "gia theo gio"])
    ):
        return "GENERAL_PRICING_OVERVIEW"
    if (
        bool(re.search(r"\b(tien\s+nghi|tien\s+ich)\b", clean))
        or any(k in clean for k in ["co tien nghi gi", "co tien ich gi", "phong co gi", "tien nghi o day", "phong co nhung gi"])
    ):
        return "GENERAL_AMENITIES_OVERVIEW"

    # 12. Gợi ý chia phòng / đặt nhiều phòng khi đoàn đông
    if any(k in clean for k in ["chia 2 phong", "chia lam 2 phong", "chia thanh 2 phong", "chia lam 3 phong", "chia 3 phong", "tach phong", "dat 2 phong", "dat nhieu phong", "goi y chia phong", "chia phong", "phuong an chia phong", "chia giup", "chia ho"]):
        return "SPLIT_ROOM_RECOMMENDATION"

    # 13. Giảm số người / đổi số khách
    if any(k in clean for k in ["giam so nguoi", "giam so khach", "giam nguoi", "doi so nguoi", "doi so khach"]):
        return "REDUCE_GUESTS_INQUIRY"

    # 14. Quy định sức chứa
    if any(k in clean for k in ["quy dinh suc chua", "suc chua quy dinh", "suc chua toi da", "o toi da may nguoi", "mot phong o duoc may nguoi", "phong o duoc bao nhieu nguoi"]):
        return "ROOM_CATEGORIES_OVERVIEW"

    # 15. Tìm phòng / Tư vấn phòng (mặc định cho các câu hỏi về nhu cầu lưu trú)
    if (
        any(k in clean for k in [
            "tim phong", "tim mot phong", "tim 1 phong", "co phong nao", "tu van phong", "tu van giup",
            "can phong", "thue phong", "dat phong", "chuyen di", "chuyen di sap toi", "sap toi",
            "o thao dien", "o ben thanh", "o phu my hung", "cho 2 nguoi", "cho 3 nguoi", "2 nguoi", "1 nguoi", "3 nguoi",
            "ngay mai", "toi mai", "chieu mai", "theo gio", "qua dem", "re hon", "tiet kiem hon",
            "doi sang", "doi qua", "chuyen sang", "co them"
        ])
        or extracted.get("branch_id")
        or extracted.get("stay_type")
        or extracted.get("guests")
        or (extracted.get("preferences") and (context.get("branch_id") or context.get("guests")))
        or (context.get("branch_id") and any(p in clean for p in ["dieu hoa", "may lanh", "wifi", "bon tam", "ban cong", "phong tam"]))
    ):
        return "ROOM_RECOMMENDATION"

    # Kiểm tra nếu người dùng yêu cầu AI đặt phòng hoặc thanh toán hộ
    if tx_req["book"] or tx_req["pay"]:
        if extracted.get("branch_id") or extracted.get("stay_type") or extracted.get("specific_room_id") or extracted.get("room_types"):
            return "ROOM_RECOMMENDATION"
        return "NEED_MORE_INFO"

    return "UNKNOWN"



# -------------------------------------------------------------
# 4. Bộ Điều Phối Nghiệp Vụ & Dữ Liệu (Business Resolver)
# -------------------------------------------------------------
class ChatbotEngine:

    @classmethod
    def process_message(cls, session_id: str, query: str, user_id: int | None = None) -> dict[str, Any]:
        session = SessionManager.get_session(session_id)
        ctx = session["context"]
        if user_id:
            ctx["user_id"] = user_id

        # Bước 1: Trích xuất thực thể
        extracted = extract_entities(query, ctx)

        # Cập nhật ngữ cảnh phiên (chỉ cập nhật trường mới, không ghi đè mất thông tin cũ)
        SessionManager.update_context(session_id, extracted)
        ctx = session["context"]

        # Ghi nhận lịch sử câu hỏi trong bộ nhớ phiên và lưu vào database nếu có
        SessionManager.add_history(session_id, "user", query)
        if save_chat_message:
            try:
                save_chat_message(session_id, "user", query, user_id=user_id or ctx.get("user_id"))
            except Exception:
                pass

        # Guardrail: Kiểm tra vi phạm an toàn thông tin & dữ liệu nhạy cảm (AI-09)
        if check_security_and_privacy_violation(query):
            msg = (
                "**Thông báo bảo mật:** Theo quy định an toàn dữ liệu và chính sách bảo vệ quyền riêng tư của CozyHome, "
                "Trợ lý AI **tuyệt đối không cung cấp thông tin cá nhân của khách hàng** (như số CCCD, số điện thoại, lịch sử đặt phòng) "
                "cũng như **tài khoản quản trị hoặc dữ liệu nội bộ của hệ thống**.\n\n"
                "Quý khách vui lòng tra cứu các thông tin lưu trú công khai trên website hoặc liên hệ hotline chính thức của CozyHome nếu cần hỗ trợ."
            )
            return cls._build_response(
                session_id, "OUT_OF_SCOPE", msg,
                quick_replies=["Thông tin chi nhánh", "Chính sách hủy phòng", "Tìm phòng theo giờ"]
            )

        # Bước 2: Phân loại Intent (có truyền kèm lịch sử hội thoại để liên kết đa lượt)
        intent = classify_intent(query, extracted, ctx, history=session.get("history"))

        # Xử lý trường hợp hỏi về địa điểm ngoài CozyHome (ví dụ: Đà Lạt)
        if extracted.get("unsupported_location"):
            loc_name = extracted["unsupported_location"].title()
            msg = (
                f"Hiện tại chuỗi CozyHome chỉ hoạt động với **3 chi nhánh tại TP. Hồ Chí Minh** "
                f"(Bến Thành - Q.1, Thảo Điền - TP. Thủ Đức, và Phú Mỹ Hưng - Q.7). "
                f"Dữ liệu hệ thống chưa có chi nhánh tại {loc_name}. "
                f"Bạn có muốn mình tìm phòng tại một trong 3 chi nhánh ở TP.HCM không?"
            )
            ctx["pending_action"] = "suggest_hcm_branches"
            return cls._build_response(session_id, "OUT_OF_SCOPE", msg, quick_replies=["Bến Thành", "Thảo Điền", "Phú Mỹ Hưng"])

        # Bước 3: Điều phối theo Intent
        if intent == "GREETING":
            msg = (
                "Xin chào! Mình là **Trợ lý CozyHome**. "
                "Mình có thể giúp bạn tìm phòng phù hợp theo giờ hoặc qua đêm, "
                "tra cứu chính sách hủy – hoàn tiền hoặc giải đáp thông tin về các chi nhánh CozyHome. "
                "Bạn cần mình hỗ trợ gì hôm nay?"
            )
            return cls._build_response(
                session_id, intent, msg,
                quick_replies=["Tìm phòng phù hợp", "Chính sách hủy phòng", "Chính sách hoàn tiền", "Thông tin CozyHome"]
            )

        elif intent == "THANK_YOU":
            msg = "Rất vui được hỗ trợ bạn! Nếu cần thêm thông tin phòng hay chính sách nào khác của CozyHome, bạn cứ nhắn mình nhé. Chúc bạn một ngày tốt lành!"
            return cls._build_response(session_id, intent, msg, quick_replies=["Xem phòng Bến Thành", "Xem phòng Thảo Điền"])

        elif intent == "HELP":
            msg = (
                "Mình có thể hỗ trợ bạn các nội dung sau:\n"
                "1. **Tư vấn đặt phòng**: Theo giờ (khung 3h) hoặc qua đêm, theo chi nhánh và số khách.\n"
                "2. **Tra cứu chính sách**: Quy định hủy phòng, hoàn tiền, giờ nhận/trả phòng.\n"
                "3. **Thông tin CozyHome**: Địa chỉ 3 chi nhánh, tiện nghi và bảng giá niêm yết."
            )
            return cls._build_response(
                session_id, intent, msg,
                quick_replies=["Tìm phòng theo giờ", "Tìm phòng qua đêm", "Chính sách hủy phòng"]
            )

        elif intent == "OUT_OF_SCOPE":
            msg = (
                "Mình là trợ lý chuyên trách lưu trú của CozyHome nên chủ yếu hỗ trợ "
                "các thông tin liên quan đến phòng, đặt phòng, giá cả và chính sách lưu trú tại chuỗi CozyHome. "
                "Bạn đang cần tìm phòng hay tra cứu thông tin gì về CozyHome không ạ?"
            )
            return cls._build_response(
                session_id, intent, msg,
                quick_replies=["Tìm phòng Bến Thành", "Chính sách hủy phòng", "3 chi nhánh CozyHome"]
            )

        elif intent == "HOMESTAY_INFORMATION":
            branches = get_branch_details()
            msg = (
                "**CozyHome Hospitality** là chuỗi homestay đô thị phong cách Bắc Âu ấm cúng tại trung tâm TP.HCM.\n\n"
                "Hiện CozyHome có **3 chi nhánh hoạt động** (tổng quy mô 24 phòng tiêu chuẩn):\n"
                "• **CozyHome Bến Thành**: 123 Lê Thánh Tôn, P. Bến Thành, Quận 1 (Phong cách Đô thị năng động)\n"
                "• **CozyHome Thảo Điền**: 45 Xuân Thủy, P. Thảo Điền, TP. Thủ Đức (Phong cách Cao nguyên và Thiên nhiên)\n"
                "• **CozyHome Phú Mỹ Hưng**: 88 Nguyễn Đức Cảnh, P. Tân Phong, Quận 7 (Phong cách Nhiệt đới thư giãn)\n\n"
                "Hệ thống hỗ trợ 2 hình thức: **Thuê theo khung 3 tiếng linh hoạt (K1, K2, K3)** và **Thuê qua đêm (QD)**."
            )
            return cls._build_response(
                session_id, intent, msg,
                quick_replies=["Tìm phòng Bến Thành", "Tìm phòng Thảo Điền", "Tìm phòng Phú Mỹ Hưng", "Bảng giá phòng"]
            )

        elif intent == "BRANCH_INFORMATION":
            bid = ctx.get("branch_id") or "BT"
            b_info = BRANCH_DETAILS.get(bid, BRANCH_DETAILS["BT"])
            msg = (
                f"**{b_info['name']}**\n"
                f"• **Địa chỉ**: {b_info['address']}\n"
                f"• **Khu vực**: {b_info['district']}\n"
                f"• **Phong cách chủ đạo**: {b_info['concept_name']} ({b_info['concept']})\n"
                f"• **Quy mô**: {b_info['room_count']} phòng (Standard, Deluxe, Family)\n"
                f"• **Đặc điểm nổi bật**: {', '.join(b_info['features'])}\n"
                f"• **Hotline hỗ trợ**: {b_info['phone']}"
            )
            return cls._build_response(
                session_id, intent, msg,
                quick_replies=[f"Phòng tại {b_info['name']}", "Chi nhánh khác", "Đặt phòng ngay"]
            )

        elif intent == "BRANCH_COMPARISON":
            msg = (
                "**Gợi ý so sánh 3 chi nhánh CozyHome tại TP.HCM để bạn dễ dàng lựa chọn:**\n\n"
                "• **Chi nhánh Bến Thành (Quận 1)**: Tọa lạc tại số 123 Lê Thánh Tôn, ngay trung tâm Quận 1, cách chợ Bến Thành và phố đi bộ vài bước chân. Phong cách Đô thị năng động, rất phù hợp cho khách đi du lịch, công tác hoặc thích không khí ẩm thực nhộn nhịp (giá từ **140.000 ₫/khung 3h** hoặc từ **450.000 ₫/đêm**).\n\n"
                "• **Chi nhánh Thảo Điền (TP. Thủ Đức)**: Tọa lạc tại số 45 Xuân Thủy, không gian xanh ven sông, nhiều cây cối, phong cách Bắc Âu thanh bình và lãng mạn. Rất lý tưởng cho các cặp đôi hẹn hò, nghỉ ngơi cuối tuần tránh xa khói bụi ồn ào (giá từ **140.000 ₫/khung 3h** hoặc từ **450.000 ₫/đêm**).\n\n"
                "• **Chi nhánh Phú Mỹ Hưng (Quận 7)**: Tọa lạc tại số 88 Nguyễn Đức Cảnh, khu đô thị kiểu mẫu hiện đại, gần Hồ Bán Nguyệt và Cầu Ánh Sao. Không gian thoáng đãng, sang trọng, đặc biệt phù hợp cho gia đình có trẻ nhỏ, nhóm bạn hoặc chuyến công tác dài ngày (giá từ **150.000 ₫/khung 3h** hoặc từ **500.000 ₫/đêm**).\n\n"
                "Bạn đang lên kế hoạch cho chuyến đi mấy người và ưu tiên phong cách nào để mình tư vấn chi tiết hơn nhé?"
            )
            return cls._build_response(
                session_id, intent, msg,
                quick_replies=["Xem phòng Bến Thành", "Xem phòng Thảo Điền", "Xem phòng Phú Mỹ Hưng", "Bảng giá phòng"]
            )

        elif intent == "ROOM_CATEGORIES_OVERVIEW":
            msg = (
                "**Chuỗi CozyHome cung cấp 3 hạng phòng tiêu chuẩn (tổng quy mô 24 phòng):**\n\n"
                "1. **Hạng Standard (Tiêu chuẩn)**:\n"
                "• Sức chứa: Tối đa 2 khách (diện tích 20–22m², 1 giường đôi 1m6).\n"
                "• Tiện nghi: Máy lạnh, TV thông minh, minibar, Wi-Fi tốc độ cao, phòng tắm riêng khép kín có nước nóng.\n"
                "• Mức giá: Từ **140.000 ₫/khung 3 giờ** hoặc từ **450.000 ₫/qua đêm**.\n\n"
                "2. **Hạng Deluxe (Cao cấp)**:\n"
                "• Sức chứa: 2–3 khách (diện tích 28–30m², giường King 1m8, có sofa).\n"
                "• Điểm nhấn: Ban công thoáng mát, view đẹp hoặc bồn tắm ngâm thư giãn.\n"
                "• Mức giá: Từ **150.000 ₫/khung 3 giờ** hoặc từ **550.000 ₫/qua đêm**.\n\n"
                "3. **Hạng Family (Gia đình)**:\n"
                "• Sức chứa: 4–6 khách (diện tích 40m², **3 giường ngủ**: gồm 2 giường đôi lớn + 1 sofa bed cao cấp).\n"
                "• Điểm nhấn: Bếp mini nấu ăn tiện lợi, lò vi sóng, bàn ăn riêng, không gian sinh hoạt chung rộng rãi cho cả gia đình.\n"
                "• Mức giá: Từ **200.000 ₫/khung 3 giờ** hoặc từ **800.000 ₫/qua đêm**.\n\n"
                "Bạn quan tâm hạng phòng nào hoặc cần tìm phòng cho bao nhiêu người để mình tư vấn cụ thể hơn nhé?"
            )
            return cls._build_response(
                session_id, intent, msg,
                quick_replies=["Phòng cho 2 người", "Phòng có bồn tắm", "Phòng gia đình", "Xem bảng giá"]
            )

        elif intent == "GENERAL_PRICING_OVERVIEW":
            msg = (
                "**Bảng giá niêm yết minh bạch tại CozyHome (đã bao gồm VAT và quy trình khử khuẩn buồng phòng):**\n\n"
                "1. **Hình thức thuê theo giờ (khung cố định 3 tiếng linh hoạt):**\n"
                "• **Khung 1 (Sáng 09:30 – 12:30)**: từ **140.000 ₫ – 200.000 ₫/khung**\n"
                "• **Khung 2 (Chiều 13:00 – 16:00)**: từ **150.000 ₫ – 220.000 ₫/khung**\n"
                "• **Khung 3 (Tối 16:30 – 19:30)**: từ **150.000 ₫ – 220.000 ₫/khung**\n\n"
                "2. **Hình thức thuê qua đêm (20:00 nhận phòng – 08:30 sáng hôm sau):**\n"
                "• Hạng Standard (2 khách): từ **450.000 ₫ – 500.000 ₫/đêm**\n"
                "• Hạng Deluxe (2–3 khách): từ **550.000 ₫ – 650.000 ₫/đêm**\n"
                "• Hạng Family (4–6 khách): từ **800.000 ₫ – 950.000 ₫/đêm**\n\n"
                "Giữa các ca luôn có 30 phút để buồng phòng dọn dẹp và khử khuẩn 100%. Bạn muốn tìm phòng theo giờ hay qua đêm tại chi nhánh nào ạ?"
            )
            return cls._build_response(
                session_id, intent, msg,
                quick_replies=["Thuê theo giờ (3h)", "Thuê qua đêm", "Xem 3 chi nhánh"]
            )

        elif intent == "GENERAL_AMENITIES_OVERVIEW":
            msg = (
                "**Tiện nghi tiêu chuẩn tại 100% các phòng thuộc chuỗi CozyHome:**\n\n"
                "• **Tiện nghi cơ bản trong phòng**: Máy lạnh/điều hòa, TV thông minh, minibar/tủ lạnh nhỏ, Wi-Fi tốc độ cao miễn phí, bàn làm việc, máy sấy tóc.\n"
                "• **Khu vệ sinh**: Phòng tắm riêng khép kín, bình nóng lạnh, bộ khăn tắm sạch, dầu gội, sữa tắm và đồ vệ sinh cá nhân miễn phí.\n"
                "• **Tiện ích đặc biệt theo hạng phòng**:\n"
                "  - Hạng Deluxe: Có thêm ban công thoáng mát, view thành phố/view sông hoặc bồn tắm nằm thư giãn.\n"
                "  - Hạng Family: Có thêm khu vực bếp mini, ấm đun siêu tốc, tủ lạnh lớn và bàn ăn riêng.\n\n"
                "Bạn cần phòng có tiện nghi cụ thể nào (ví dụ: bồn tắm, ban công, bếp mini) để mình hỗ trợ tìm nhé?"
            )
            return cls._build_response(
                session_id, intent, msg,
                quick_replies=["Phòng có bồn tắm", "Phòng có ban công", "Phòng có bếp mini", "Xem bảng giá"]
            )

        elif intent == "COMPREHENSIVE_INQUIRY":
            target_branch = extracted.get("branch_id") or ctx.get("branch_id") or "TD"
            target_types = extracted.get("room_types") or ["Deluxe"]
            stay_type = extracted.get("stay_type") or "overnight"

            # Tìm phòng tiêu biểu khớp chi nhánh và hạng phòng
            matching_rooms = [
                r for r in all_rooms()
                if r["branch_id"] == target_branch and (r["room_type"] in target_types or not target_types)
            ]
            if not matching_rooms:
                matching_rooms = [r for r in all_rooms() if r["branch_id"] == target_branch] or all_rooms()

            sample_room = matching_rooms[0]
            slots = slot_info_for_room(sample_room["room_id"])
            qd_slot = next((s for s in slots if s["khung_code"] == "QD"), None)
            qd_price = qd_slot["price"] if qd_slot else 650000

            b_info = BRANCH_DETAILS.get(target_branch, BRANCH_DETAILS.get("TD", {}))
            b_name = b_info.get("name", "CozyHome Thảo Điền")
            rt_name = target_types[0] if target_types else sample_room.get("room_type", "Deluxe")

            # 1. Trả lời về Giá phòng
            section_price = (
                f"1. **Giá phòng {rt_name} tại {b_name}:**\n"
                f"• Khung **Qua đêm (QD)** ngày thường có giá niêm yết là **{money(qd_price)}/đêm** "
                f"(giờ nhận phòng khoảng 20:00 – 21:30, trả phòng 08:30 – 10:00 hôm sau tùy nhóm phòng).\n"
                f"• Thuê theo **khung 3 tiếng**: từ **{money(200000)} – {money(220000)}/khung** (Sáng K1, Chiều K2, Tối K3).\n"
                f"• *Ưu đãi lưu trú:* CozyHome áp dụng chương trình giảm 15% cho lưu trú qua đêm giữa tuần (từ Chủ Nhật đến Thứ Năm)."
            )

            # 2. Trả lời về Hủy phòng & Hoàn tiền (tính theo số giờ nếu có)
            clean_q = _norm(query)
            m_hours = re.search(r"(\d+)\s*(?:gio|tieng|h)\b", clean_q)
            hours_val = int(m_hours.group(1)) if m_hours else None

            if hours_val is not None:
                if hours_val >= 24:
                    calc_explanation = (
                        f"Nếu bạn hủy trước giờ nhận phòng **{hours_val} giờ**, bạn được **HOÀN LẠI 100% số tiền đã thanh toán**.\n"
                        f"*(Căn cứ theo Phụ lục 5 Bộ quy định và chính sách CozyHome: mốc hủy từ 24 giờ trở lên trước thời điểm lưu trú được hoàn 100% giá trị tiền phòng đủ điều kiện hoàn).*"
                    )
                elif 12 <= hours_val < 24:
                    calc_explanation = (
                        f"Nếu bạn hủy trước giờ nhận phòng **{hours_val} giờ**, bạn được **HOÀN LẠI 50% tiền phòng**.\n"
                        f"*(Căn cứ theo Phụ lục 5 CozyHome: mốc hủy từ 12 giờ đến dưới 24 giờ trước thời điểm lưu trú được hoàn 50% tiền phòng).*"
                    )
                else:
                    calc_explanation = (
                        f"Nếu bạn hủy trước giờ nhận phòng **{hours_val} giờ**, hệ thống **KHÔNG ÁP DỤNG HOÀN TIỀN**.\n"
                        f"*(Căn cứ theo Phụ lục 5 CozyHome: mốc hủy dưới 12 giờ trước thời điểm lưu trú sẽ không được hoàn tiền để bảo đảm điều phối lịch phòng).*"
                    )
            else:
                calc_explanation = "Hủy trước giờ nhận phòng từ 24 giờ trở lên được hoàn lại 100% số tiền đã thanh toán."

            section_refund = (
                f"2. **Chính sách hủy phòng và hoàn tiền:**\n"
                f"• {calc_explanation}\n"
                f"• **Bảng tỷ lệ hoàn tiền theo thời điểm hủy (Phụ lục 5):**\n"
                f"  - Từ **24 giờ trở lên** trước giờ nhận phòng: **Hoàn 100%** tiền phòng.\n"
                f"  - Từ **12 giờ đến dưới 24 giờ** trước giờ nhận phòng: **Hoàn 50%** tiền phòng.\n"
                f"  - **Dưới 12 giờ** hoặc sau check-in / No-show: **Không hoàn tiền (0%)**.\n"
                f"• **Thời gian hoàn tiền:** Tiền hoàn được chuyển về đúng phương thức thanh toán ban đầu trong vòng **từ 3 đến 15 ngày làm việc** sau khi bộ phận kế toán đối soát."
            )

            # 3. Trả lời về Tiện nghi phòng
            amenities = sample_room.get("amenities") or []
            special_amenities = [a.capitalize() for a in amenities if any(x in _norm(a) for x in ["ban cong", "bon tam", "view", "bep", "sofa"])]
            section_amenities = (
                f"3. **Tiện nghi phòng {rt_name}:**\n"
                f"• **Tiện ích nâng cao nổi bật**: {', '.join(special_amenities) if special_amenities else 'Ban công thoáng mát, view cây xanh thiên nhiên, bồn tắm ngâm thư giãn'}. Diện tích rộng rãi 28m², sức chứa 2–3 khách với giường King 1m8 và sofa.\n"
                f"• **Tiện nghi tiêu chuẩn 100% phòng CozyHome**: Điều hòa hai chiều, Wi-Fi tốc độ cao miễn phí, Smart TV, minibar/tủ lạnh mini, bàn làm việc, máy sấy tóc, bình nóng lạnh, khăn tắm sạch và bộ đồ vệ sinh cá nhân miễn phí."
            )

            # 4. Trả lời về Phí dịch vụ ngoài giá công bố
            section_fees = (
                f"4. **Chính sách phí dịch vụ ngoài mức giá công bố:**\n"
                f"• **Hoàn toàn KHÔNG thu thêm bất kỳ phí dịch vụ ẩn nào ngoài mức giá công bố.** Mọi mức giá hiển thị trên website CozyHome đều là giá trọn gói, đã bao gồm thuế và quy trình vệ sinh khử khuẩn buồng phòng 100% trước khi quý khách nhận phòng.\n"
                f"• **Các khoản phát sinh chỉ xảy ra khi khách chủ động yêu cầu thêm dịch vụ:**\n"
                f"  - Gia hạn lưu trú thêm giờ: 50.000 ₫/giờ/phòng (miễn phí tối đa 15 phút trả phòng muộn).\n"
                f"  - Phụ thu khách bổ sung khi vượt quá sức chứa tiêu chuẩn nhưng vẫn trong sức chứa tối đa của phòng."
            )

            msg = (
                f"Dạ chào bạn! Trợ lý CozyHome xin giải đáp chi tiết và đầy đủ các câu hỏi của bạn về phòng **{sample_room['room_name']}** ({rt_name}) tại **{b_name}** như sau ạ:\n\n"
                f"{section_price}\n\n"
                f"{section_refund}\n\n"
                f"{section_amenities}\n\n"
                f"{section_fees}\n\n"
                f"Bạn có thể nhấp vào thẻ phòng bên dưới để xem thêm hình ảnh thực tế và đặt phòng trực tiếp trên website nhé!"
            )

            cards = [cls._format_room_card(r, slot_info_for_room(r["room_id"])) for r in matching_rooms[:2]]
            return cls._build_response(
                session_id, "COMPREHENSIVE_INQUIRY", msg,
                recommendations=cards,
                action={"type": "view_room", "target": sample_room["room_id"], "label": f"Xem ảnh và Đặt {sample_room['room_name']}"},
                quick_replies=[f"Đặt {sample_room['room_name']}", "Chính sách hủy phòng", "Xem chi nhánh khác"]
            )

        elif intent in ("CANCELLATION_POLICY", "REFUND_POLICY", "CANCELLATION_AND_REFUND_POLICY"):
            c_pol = get_cancellation_policy()
            r_pol = get_refund_policy()

            tx_req = check_transaction_request(query)
            is_user_requesting_cancel = tx_req["cancel"] or any(k in _norm(query) for k in ["huy phong giup toi", "huy ho toi", "huy don giup", "huy booking giup"])

            if is_user_requesting_cancel:
                msg = (
                    "**Thông báo an toàn:** Theo quy tắc bảo mật của CozyHome, **Trợ lý AI không có quyền trực tiếp hủy phòng hoặc thay đổi giao dịch thay cho khách hàng** (BR-13).\n\n"
                    "**Để hủy phòng, bạn chỉ cần thực hiện 3 bước đơn giản:**\n"
                    "1. Nhấp vào mục **'Lượt đặt của tôi'** trên thanh điều hướng.\n"
                    "2. Chọn mã đơn đặt phòng bạn muốn hủy.\n"
                    "3. Nhấn nút **'Xác nhận hủy đặt phòng'**.\n\n"
                    "Hệ thống sẽ hiển thị rõ điều kiện và số tiền hoàn trước khi bạn bấm xác nhận."
                )
                return cls._build_response(
                    session_id, intent, msg,
                    policy_card=c_pol,
                    action={"type": "navigate", "target": "bookings", "label": "Mở Lượt đặt của tôi"}
                )

            clean_q = _norm(query)
            m_hours = re.search(r"(\d+)\s*(?:gio|tieng|h)\b", clean_q)
            hours_val = int(m_hours.group(1)) if m_hours else None
            hours_note = ""
            if hours_val is not None:
                if hours_val >= 24:
                    hours_note = f"• **Trường hợp hủy trước {hours_val} giờ**: Vì {hours_val}h thuộc mốc từ 24 giờ trở lên, bạn được **hoàn lại 100%** số tiền đã thanh toán.\n\n"
                elif 12 <= hours_val < 24:
                    hours_note = f"• **Trường hợp hủy trước {hours_val} giờ**: Vì {hours_val}h thuộc mốc từ 12 đến dưới 24 giờ, bạn được **hoàn lại 50%** tiền phòng.\n\n"
                else:
                    hours_note = f"• **Trường hợp hủy trước {hours_val} giờ**: Vì {hours_val}h thuộc mốc dưới 12 giờ, theo quy định hệ thống **không áp dụng hoàn tiền**.\n\n"

            if intent == "CANCELLATION_POLICY":
                msg = (
                    "**Chính sách Hủy đặt phòng CozyHome (Phụ lục 5):**\n\n"
                    f"{hours_note}"
                    "**Tỷ lệ hoàn tiền theo thời điểm gửi yêu cầu hủy:**\n"
                    "• **Từ 24 giờ trở lên trước giờ bắt đầu lưu trú**: Hoàn lại **100%** số tiền thực trả cho phần giá phòng đủ điều kiện hoàn.\n"
                    "• **Từ 12 giờ đến dưới 24 giờ trước giờ bắt đầu lưu trú**: Hoàn lại **50%** tiền phòng.\n"
                    "• **Dưới 12 giờ trước giờ bắt đầu lưu trú**: Không hoàn tiền (0%).\n"
                    "• **Không đến nhận phòng (No-show) hoặc hủy sau giờ bắt đầu**: Không hoàn tiền (0%).\n\n"
                    "Mức hoàn trên áp dụng thống nhất cho đặt phòng theo giờ và qua đêm. "
                    "Bạn có thể chủ động thao tác hủy phòng trong mục *'Lượt đặt của tôi'* trên website."
                )
                return cls._build_response(session_id, intent, msg, policy_card=c_pol, quick_replies=["Chính sách hoàn tiền", "Mở Đặt phòng của tôi"])

            elif intent == "REFUND_POLICY":
                msg = (
                    "**Chính sách Hoàn tiền CozyHome (Phụ lục 5):**\n\n"
                    f"{hours_note}"
                    "• **Điều kiện hoàn**: Áp dụng khi bạn hủy đặt phòng trước giờ bắt đầu lưu trú từ 12 giờ trở lên (hoàn 100% nếu >= 24h, hoàn 50% nếu từ 12h đến dưới 24h).\n"
                    "• **Thời gian xử lý hoàn tiền**: Từ **3 đến 15 ngày làm việc** (sau khi bộ phận Kế toán đối soát giao dịch và ngân hàng / cổng thanh toán ghi có).\n"
                    "• **Phương thức hoàn tiền**: Tiền được gửi về đúng phương thức thanh toán ban đầu (quét mã VietQR MBBank).\n"
                    "• **Minh bạch đối soát**: Mọi giao dịch hoàn tiền đều được gắn mã đơn và đưa vào danh sách đối soát định kỳ của kế toán."
                )
                return cls._build_response(session_id, intent, msg, policy_card=r_pol, quick_replies=["Chính sách hủy phòng", "Hotline liên hệ"])

            else:  # CANCELLATION_AND_REFUND_POLICY
                msg = (
                    "**Chính sách Hủy phòng và Hoàn tiền CozyHome (Phụ lục 5):**\n\n"
                    f"{hours_note}"
                    "1. **Tỷ lệ hoàn tiền theo thời điểm hủy:**\n"
                    "• Từ **24 giờ trở lên**: Hoàn **100%** số tiền đã thanh toán.\n"
                    "• Từ **12 giờ đến dưới 24 giờ**: Hoàn **50%** tiền phòng.\n"
                    "• Dưới **12 giờ** hoặc sau khi check-in / No-show: Không hoàn tiền (0%).\n\n"
                    "2. **Quy trình và Thời gian nhận tiền hoàn:**\n"
                    "• Tiền hoàn được bộ phận Kế toán đối soát và chuyển về tài khoản ban đầu trong **từ 3 đến 15 ngày làm việc**.\n\n"
                    "*(Lưu ý: Bạn thao tác hủy trực tiếp trong mục 'Lượt đặt của tôi', AI không trực tiếp can thiệp hủy phòng để bảo mật tài khoản).*"
                )
                return cls._build_response(session_id, intent, msg, policy_card=c_pol, quick_replies=["Mở Đặt phòng của tôi", "Tìm phòng mới"])

        elif intent == "CHECKIN_CHECKOUT_POLICY":
            msg = (
                "**Quy định Giờ Nhận và Trả phòng CozyHome:**\n"
                "CozyHome áp dụng 4 nhóm khung giờ luân phiên để tối ưu công tác buồng phòng:\n"
                "• **Khung 1 (Sáng)**: Nhận khoảng 09:30 – 11:00 - Trả khoảng 12:30 – 14:00 (3 tiếng)\n"
                "• **Khung 2 (Chiều)**: Nhận khoảng 13:00 – 14:30 - Trả khoảng 16:00 – 17:30 (3 tiếng)\n"
                "• **Khung 3 (Tối)**: Nhận khoảng 16:30 – 18:00 - Trả khoảng 19:30 – 21:00 (3 tiếng)\n"
                "• **Khung Qua đêm (QD)**: Nhận khoảng 20:00 – 21:30 - Trả khoảng 08:30 – 10:00 sáng hôm sau.\n\n"
                "Quý khách vui lòng nhận và trả phòng đúng giờ để nhân viên buồng phòng khử khuẩn 100% chuẩn bị cho lượt khách tiếp theo."
            )
            return cls._build_response(session_id, intent, msg, quick_replies=["Tìm phòng theo giờ", "Tìm phòng qua đêm"])

        elif intent == "STAY_POLICY":
            pol = get_stay_policy()
            tx_req = check_transaction_request(query)
            if tx_req["extend"]:
                msg = (
                    "**Thông báo an toàn:** Trợ lý AI **không có quyền tự động gia hạn phòng hoặc can thiệp giao dịch** thay cho khách hàng.\n\n"
                    "**Để gia hạn lưu trú:**\n"
                    "1. Bạn vào mục **'Lượt đặt của tôi'** trên thanh điều hướng.\n"
                    "2. Chọn đơn phòng đang ở và nhấn nút **'Gia hạn khung tiếp theo'**.\n"
                    "3. Nếu khung giờ liền kề còn trống, hệ thống sẽ tự động ghép giờ mà không phát sinh thêm phí dọn phòng."
                )
                return cls._build_response(
                    session_id, intent, msg, policy_card=pol,
                    action={"type": "navigate", "target": "bookings", "label": "Mở Lượt đặt của tôi"},
                    quick_replies=["Lượt đặt của tôi", "Quy định giờ trả phòng", "Tìm phòng mới"]
                )

            msg = (
                "**Quy định Lưu trú Chung tại CozyHome:**\n"
                "• **Không hút thuốc**: 100% phòng CozyHome là không gian không hút thuốc nhằm đảm bảo an toàn và không khí trong lành.\n"
                "• **Sức chứa**: Nghiêm túc tuân thủ sức chứa quy định của từng phòng (Standard: 2 khách, Deluxe: 2–3 khách, Family: tối đa 6 khách).\n"
                "• **Gia hạn lưu trú**: Nếu muốn ở thêm, bạn có thể gia hạn sang khung tiếp theo trên website nếu khung đó còn trống mà không phát sinh thêm phí dọn phòng.\n"
                "• **Giữ chỗ thanh toán**: Bạn có 10 phút giữ chỗ sau khi đặt phòng để hoàn tất quét mã VietQR MBBank."
            )
            return cls._build_response(session_id, intent, msg, policy_card=pol, quick_replies=["Tìm phòng", "Chính sách hủy phòng"])

        elif intent == "HOURLY_RENTAL_POLICY":
            msg = (
                "**Dạ có ạ! CozyHome hỗ trợ dịch vụ cho thuê phòng theo giờ rất linh hoạt:**\n\n"
                "Hệ thống cung cấp **3 khung giờ cố định trong ngày (mỗi khung 3 tiếng)**:\n"
                "• **Khung 1 (Sáng)**: 09:30 – 12:30 (giá từ 140.000 ₫/khung)\n"
                "• **Khung 2 (Chiều)**: 13:00 – 16:00 (giá từ 150.000 ₫/khung)\n"
                "• **Khung 3 (Tối)**: 16:30 – 19:30 (giá từ 150.000 ₫/khung)\n\n"
                "Giữa các khung giờ luôn có **30 phút giãn cách buồng phòng** để khử khuẩn và dọn dẹp sạch sẽ đón bạn. "
                "Bạn muốn tìm phòng theo giờ tại chi nhánh nào ạ?"
            )
            return cls._build_response(
                session_id, intent, msg,
                quick_replies=["Thuê theo giờ Bến Thành", "Thuê theo giờ Thảo Điền", "Thuê theo giờ Phú Mỹ Hưng"]
            )

        elif intent == "PROMOTION_POLICY":
            msg = (
                "**Chương trình Ưu đãi và Khuyến mãi hiện hành tại CozyHome:**\n"
                "1. **Ưu đãi đặt sớm**: Giảm 10% cho các lượt đặt phòng xác nhận trước ngày sử dụng ít nhất 7 ngày.\n"
                "2. **Ưu đãi qua đêm giữa tuần**: Giảm 15% cho khung lưu trú Qua đêm vào các ngày từ Chủ nhật đến thứ Năm.\n\n"
                "Mọi mức giá hiển thị trên website đều là giá niêm yết minh bạch, đã bao gồm thuế và phí dọn phòng buồng phòng."
            )
            return cls._build_response(session_id, intent, msg, quick_replies=["Tìm phòng qua đêm", "Xem phòng Bến Thành"])

        elif intent in ("ROOM_PRICE", "ROOM_AMENITY", "ROOM_AVAILABILITY", "ROOM_DETAIL", "ROOM_COMPREHENSIVE_INFO"):
            # Tra cứu thông tin cho một phòng cụ thể
            target_room_id = extracted.get("specific_room_id") or ctx.get("last_room_id") or "BT-STD-03"
            room = get_room(target_room_id)
            if not room:
                room = all_rooms()[0]
                target_room_id = room["room_id"]

            ctx["last_room_id"] = target_room_id
            slots = slot_info_for_room(target_room_id)
            amenities = room.get("amenities") or []

            if intent == "ROOM_AMENITY":
                amenities_str = ", ".join(amenities) if amenities else "Tiện nghi cơ bản"
                # Kiểm tra cụ thể người dùng hỏi tiện nghi gì
                q_clean = _norm(query)
                check_item = None
                if "may chieu" in q_clean or "rap phim" in q_clean: check_item = "máy chiếu"
                elif "ban cong" in q_clean: check_item = "ban công"
                elif "bon tam" in q_clean: check_item = "bồn tắm"
                elif "bep" in q_clean: check_item = "bếp mini"
                elif "wifi" in q_clean: check_item = "wifi"
                elif "tivi" in q_clean or "smart tv" in q_clean: check_item = "tivi"
                elif "sofa" in q_clean: check_item = "sofa"
                elif "tra dao" in q_clean or "am tra" in q_clean: check_item = "trà đạo"
                elif "ca phe" in q_clean or "may pha" in q_clean: check_item = "máy pha cà phê"
                elif "gac lung" in q_clean or "thong tang" in q_clean: check_item = "gác lửng"
                elif "loa" in q_clean or "bluetooth" in q_clean: check_item = "loa bluetooth"
                elif "guong" in q_clean or "trang diem" in q_clean: check_item = "bàn trang điểm"
                elif "lo vi song" in q_clean: check_item = "lò vi sóng"
                elif "view song" in q_clean: check_item = "view sông"
                elif "view ho" in q_clean: check_item = "view hồ"
                elif "view pho" in q_clean or "view thanh pho" in q_clean: check_item = "view thành phố"
                elif "3 giuong" in q_clean or "ba giuong" in q_clean: check_item = "3 giường"
                elif "may giuong" in q_clean or "giuong" in q_clean: check_item = "giường"

                if check_item == "3 giường":
                    has_item = "3 giường" in (room.get("bed_type") or "") or any("3 giường" in a for a in amenities)
                    if has_item:
                        msg = f"Dạ đúng rồi ạ! Phòng **{room['room_name']}** ({room['branch_name']}) thuộc Hạng Family **được trang bị 3 giường ngủ** (gồm 2 giường đôi lớn + 1 sofa bed cao cấp), đáp ứng trọn vẹn cho gia đình hoặc nhóm bạn 4–6 người."
                    else:
                        msg = f"Dạ phòng **{room['room_name']}** hiện có **{room.get('bed_type', '1 giường đôi')}**, sức chứa tối đa {room['capacity']} khách. Các phòng trang bị **3 giường** tại CozyHome là các phòng **Hạng Family** (như Family BT08, Family TD07, Family TD08, Family PMH08) bạn nhé!"
                elif check_item:
                    has_item = any(_norm(check_item) in _norm(a) for a in amenities) or (_norm(check_item) in _norm(room.get("bed_type", "")))
                    if has_item:
                        msg = f"Dạ có ạ! Phòng **{room['room_name']}** ({room['branch_name']}) **có trang bị {check_item}**. Ngoài ra phòng còn có: {amenities_str}."
                    else:
                        msg = f"Dạ phòng **{room['room_name']}** hiện **chưa có {check_item}** ạ. Tiện nghi của phòng gồm có: {amenities_str}."
                else:
                    msg = f"Phòng **{room['room_name']}** ({room['branch_name']}) được trang bị các tiện nghi: **{amenities_str}**."

                return cls._build_response(
                    session_id, intent, msg,
                    recommendations=[cls._format_room_card(room, slots)],
                    action={"type": "view_room", "target": room["room_id"], "label": f"Xem chi tiết {room['room_name']}"},
                    quick_replies=[f"Giá phòng {room['room_name']}", f"Lịch trống {room['room_name']}", "Tìm phòng khác"]
                )

            elif intent == "ROOM_PRICE":
                price_lines = []
                for s in slots:
                    price_lines.append(f"• **{s['label']}** ({s['start_time']}–{s['end_time']}): **{money(s['price'])}**")
                msg = (
                    f"Bảng giá niêm yết của phòng **{room['room_name']}** ({room['branch_name']}):\n"
                    + "\n".join(price_lines)
                    + "\n\n*(Giá đã bao gồm VAT và dịch vụ buồng phòng khử khuẩn 100%).*"
                )
                return cls._build_response(
                    session_id, intent, msg,
                    recommendations=[cls._format_room_card(room, slots)],
                    action={"type": "view_room", "target": room["room_id"], "label": f"Đặt phòng {room['room_name']}"},
                    quick_replies=[f"Kiểm tra lịch {room['room_name']}", "Tìm phòng khác"]
                )

            elif intent == "ROOM_AVAILABILITY":
                target_date = ctx.get("date") or dt_date.today().isoformat()
                target_slot = ctx.get("khung_code") or "K1"
                avail = is_demo_available(room["room_id"], target_date, target_slot)
                status_str = "**Đang còn trống và sẵn sàng đón bạn!**" if avail else "**Đã kín khách đặt trong khung giờ này.**"

                slot_label = next((s["label"] for s in slots if s["khung_code"] == target_slot), target_slot)
                msg = (
                    f"Kiểm tra tình trạng phòng **{room['room_name']}** vào ngày **{target_date}** ({slot_label}):\n"
                    f"{status_str}\n\n"
                    f"Sức chứa: {room['capacity']} khách - Tiện nghi: {', '.join(amenities[:3])}."
                )
                return cls._build_response(
                    session_id, intent, msg,
                    recommendations=[cls._format_room_card(room, slots)] if avail else [],
                    action={"type": "view_room", "target": room["room_id"], "label": f"Xem chi tiết {room['room_name']}"},
                    quick_replies=["Xem ngày khác", "Tìm phòng khác", "Chính sách đặt phòng"]
                )

            elif intent == "ROOM_COMPREHENSIVE_INFO":
                target_room_id = extracted.get("specific_room_id") or ctx.get("last_room_id") or "BT-STD-01"
                room = get_room(target_room_id) or all_rooms()[0]
                ctx["last_room_id"] = room["room_id"]
                slots = slot_info_for_room(room["room_id"])
                amenities = room.get("amenities") or []

                price_lines = [f"• **{s['label']}** ({s['start_time']}–{s['end_time']}): **{money(s['price'])}**" for s in slots]
                msg = (
                    f"Thông tin chi tiết và chính sách cho phòng **{room['room_name']}** ({room['branch_name']}):\n\n"
                    f"1. **Bảng giá niêm yết các khung giờ:**\n"
                    + "\n".join(price_lines) + "\n\n"
                    f"2. **Tiện nghi phòng:**\n"
                    f"• {', '.join(amenities)}.\n"
                    f"• Phòng tắm riêng khép kín, khăn tắm, máy sấy tóc và đồ vệ sinh cá nhân miễn phí.\n\n"
                    f"3. **Chính sách nhận – trả phòng:**\n"
                    f"• Áp dụng nhận và trả phòng đúng khung giờ quy định: Sáng (09:30–12:30), Chiều (13:00–16:00), Tối (16:30–19:30), Qua đêm (20:00–08:30 sáng hôm sau).\n"
                    f"• Giữa các ca luôn có 30 phút để nhân viên buồng phòng khử khuẩn 100%.\n\n"
                    f"4. **Chính sách hủy phòng và hoàn tiền (Phụ lục 5):**\n"
                    f"• Hủy trước từ **24 giờ trở lên** trước giờ nhận phòng: Hoàn lại **100%** tiền phòng.\n"
                    f"• Hủy từ **12 giờ đến dưới 24 giờ**: Hoàn lại **50%** tiền phòng.\n"
                    f"• Hủy dưới **12 giờ** hoặc sau check-in: Không áp dụng hoàn tiền.\n"
                    f"• Thời gian hoàn tiền: Từ **3 đến 15 ngày làm việc** sau khi kế toán đối soát giao dịch."
                )
                return cls._build_response(
                    session_id, intent, msg,
                    recommendations=[cls._format_room_card(room, slots)],
                    action={"type": "view_room", "target": room["room_id"], "label": f"Xem ảnh và Đặt {room['room_name']}"},
                    quick_replies=[f"Đặt {room['room_name']}", f"Lịch trống {room['room_name']}", "Tìm phòng khác"]
                )

            else:  # ROOM_DETAIL
                msg = (
                    f"Thông tin phòng **{room['room_name']}** ({room['branch_name']}):\n"
                    f"• Hạng phòng: **{room['room_type']}** - Diện tích: **{room['area']}m²**\n"
                    f"• Sức chứa: Tối đa **{room['capacity']} khách** - Giường: **{room['bed_type']}**\n"
                    f"• Phong cách: {room['concept_name']} ({room['concept']})\n"
                    f"• Tiện nghi: {', '.join(amenities)}\n"
                    f"• Mô tả: {room.get('description', '')}"
                )
                return cls._build_response(
                    session_id, intent, msg,
                    recommendations=[cls._format_room_card(room, slots)],
                    action={"type": "view_room", "target": room["room_id"], "label": f"Xem ảnh và Đặt phòng"},
                    quick_replies=[f"Giá {room['room_name']}", f"Lịch trống {room['room_name']}", "Tìm phòng khác"]
                )

        elif intent == "UNKNOWN":
            # Xử lý các câu hỏi mở, câu hỏi chung hoặc câu hỏi ngoài cơ sở dữ liệu
            # Tận dụng LLM Gemini nếu có, với cam kết tuyệt đối không bịa đặt dữ liệu
            llm_text = None
            if ai_service and os.environ.get("GEMINI_API_KEY"):
                try:
                    sys_prompt = (
                        "Bạn là Trợ lý tư vấn homestay CozyHome tại TP. Hồ Chí Minh. "
                        "Dữ liệu chính thức của CozyHome:\n"
                        "- 3 chi nhánh:\n"
                        "  1) CozyHome Bến Thành: 123 Lê Thánh Tôn, P. Bến Thành, Q.1 (gần chợ Bến Thành, phố đi bộ). Hotline: 0909 000 001.\n"
                        "  2) CozyHome Thảo Điền: 45 Xuân Thủy, P. Thảo Điền, TP. Thủ Đức (không gian xanh, yên tĩnh, view sông). Hotline: 0909 000 002.\n"
                        "  3) CozyHome Phú Mỹ Hưng: 88 Nguyễn Đức Cảnh, P. Tân Phong, Q.7 (gần Hồ Bán Nguyệt, Cầu Ánh Sao). Hotline: 0909 000 003.\n"
                        "- Quy định sức chứa phòng: Standard tối đa 2 khách; Deluxe 2–3 khách; Family tối đa 6 khách. Toàn hệ thống KHÔNG CÓ BẤT KỲ PHÒNG ĐƠN NÀO ĐÁP ỨNG > 6 NGƯỜI (ví dụ 7 người, 8 người, 10 người). Tuyệt đối KHÔNG ĐƯỢC TỰ TẠO HOẶC BỊA ĐẶT phòng có sức chứa vượt quá 6 khách. Nếu khách hỏi phòng cho số người vượt quy định, BẮT BUỘC thông báo không có một phòng nào đáp ứng số lượng này, và gợi ý chia thành 2 phòng, giảm số người/phòng hoặc thay đổi tiêu chí.\n"
                        "- Khung giờ lưu trú: K1 (09:30–12:30, từ 140k), K2 (13:00–16:00, từ 150k), K3 (16:30–19:30, từ 150k), Qua đêm (20:00–08:30 sáng hôm sau, từ 450k).\n"
                        "- Giữa các ca luôn có 30 phút khử khuẩn buồng phòng. 100% phòng không hút thuốc, có điều hòa, Wi-Fi, phòng tắm riêng, minibar.\n"
                        "- Hủy phòng (Phụ lục 5): từ 24h trở lên hoàn 100%, từ 12h đến dưới 24h hoàn 50%, dưới 12h hoặc sau check-in không hoàn tiền. Thời gian hoàn 3–15 ngày làm việc qua VietQR MBBank sau khi kế toán đối soát.\n"
                        "- RÀNG BUỘC SỐNG CÒN: Nếu câu hỏi của khách hàng nằm ngoài phạm vi dữ liệu trên hoặc hệ thống chưa có thông tin kiểm chứng chắc chắn "
                        "(ví dụ: bãi đỗ xe ô tô, nuôi thú cưng, dịch vụ giặt ủi lấy liền, trực thăng, xuất hóa đơn VAT công ty...), "
                        "TUYỆT ĐỐI KHÔNG BỊA ĐẶT hay trả lời như thể đã có dữ liệu. Bạn BẮT BUỘC phải thông báo lịch sự rằng hiện tại dữ liệu hệ thống CozyHome "
                        "chưa có thông tin chi tiết về vấn đề này, và hướng dẫn khách hàng liên hệ trực tiếp Hotline CozyHome 0909 000 001 hoặc lễ tân chi nhánh để được kiểm tra và hỗ trợ chu đáo nhất.\n"
                        "Không dùng icon emoji, không dùng ký hiệu mã kỹ thuật như BR."
                    )
                    # Đính kèm ngữ cảnh lịch sử trò chuyện gần nhất để LLM hiểu được mạch đối thoại liên kết
                    history_context_lines = []
                    hist_slice = session.get("history", [])[-6:-1]
                    for h in hist_slice:
                        role_name = "Khách hàng" if h.get("role") == "user" else "Trợ lý CozyHome"
                        msg_snippet = h.get("message", "")[:200].replace("\n", " ")
                        history_context_lines.append(f"- {role_name}: {msg_snippet}")

                    hist_str = "\n".join(history_context_lines)
                    if hist_str:
                        user_prompt = (
                            f"Lịch sử các tin nhắn gần nhất trong cuộc trò chuyện:\n{hist_str}\n\n"
                            f"Khách hàng vừa nói tiếp: '{query}'.\n"
                            f"Dựa vào mạch đối thoại trên, hãy trả lời ngắn gọn, lịch sự, thân thiện bằng tiếng Việt (2-3 câu ngắn)."
                        )
                    else:
                        user_prompt = f"Khách hàng hỏi: '{query}'. Hãy trả lời lịch sự, thân thiện bằng tiếng Việt (2-3 câu ngắn)."

                    llm_res = ai_service.call_ai(
                        system_instruction=sys_prompt,
                        prompt_text=user_prompt,
                        timeout_s=5,
                    )
                    if llm_res and llm_res.get("text"):
                        llm_text = llm_res["text"].strip()
                except Exception:
                    llm_text = None

            if llm_text:
                q_lower = _norm(llm_text)
                is_contact = any(k in q_lower for k in ["chua co thong tin", "chua co du lieu", "lien he hotline", "0909 000 001", "hotline"])
                action = {"type": "contact_support", "phone": "0909000001", "label": "Hotline hỗ trợ: 0909 000 001"} if is_contact else None
                return cls._build_response(
                    session_id, "GENERAL_INQUIRY", llm_text,
                    action=action,
                    quick_replies=["Hotline: 0909 000 001", "Xem thông tin chi nhánh", "Tìm phòng trống"]
                )
            else:
                msg = (
                    "Dạ hiện tại hệ thống dữ liệu CozyHome chưa có thông tin chi tiết về câu hỏi của bạn. "
                    "Để được giải đáp nhanh chóng và hỗ trợ chu đáo nhất, bạn vui lòng liên hệ trực tiếp với bộ phận Chăm sóc khách hàng CozyHome qua **Hotline: 0909 000 001** nhé!"
                )
                return cls._build_response(
                    session_id, "GENERAL_INQUIRY", msg,
                    action={"type": "contact_support", "phone": "0909000001", "label": "Hotline hỗ trợ: 0909 000 001"},
                    quick_replies=["Hotline: 0909 000 001", "Thông tin chi nhánh", "Tìm phòng theo giờ"]
                )

        elif intent == "SPLIT_ROOM_RECOMMENDATION":
            target_branch = extracted.get("branch_id") or ctx.get("branch_id") or "PMH"
            raw_guests = extracted.get("guests") or ctx.get("guests") or 7
            try:
                guests_req = int(raw_guests)
            except (ValueError, TypeError):
                guests_req = 7

            booking_date = ctx.get("date") or dt_date.today().isoformat()
            khung_code = ctx.get("khung_code") or ("QD" if ctx.get("stay_type") == "overnight" else "K1")
            stay_label = "khung Qua đêm" if khung_code == "QD" else "khung 3 giờ"
            b_info = BRANCH_DETAILS.get(target_branch, BRANCH_DETAILS.get("PMH", {}))
            b_name = b_info.get("name", "CozyHome Phú Mỹ Hưng")
            budget_max = extracted.get("budget_max") or ctx.get("budget_max")

            branch_rooms = [
                r for r in all_rooms()
                if r.get("branch_id") == target_branch
                and is_demo_available(r["room_id"], booking_date, khung_code)
                and r.get("operational_status") != "Bảo trì"
            ]

            deluxe_rooms = [r for r in branch_rooms if r.get("room_type") == "Deluxe"]
            standard_rooms = [r for r in branch_rooms if r.get("room_type") == "Standard"]
            family_rooms = [r for r in branch_rooms if r.get("room_type") == "Family"]

            combo_rooms = []
            combo_lines = []
            total_price = 0

            if family_rooms and len(standard_rooms) >= 1:
                fam = family_rooms[0]
                std = standard_rooms[0]
                combo_rooms = [fam, std]
                p_fam = next((s["price"] for s in slot_info_for_room(fam["room_id"]) if s["khung_code"] == khung_code), 800000)
                p_std = next((s["price"] for s in slot_info_for_room(std["room_id"]) if s["khung_code"] == khung_code), 450000)
                total_price = p_fam + p_std
                combo_lines = [
                    f"• **Phòng 1: {fam['room_name']} (Hạng Family)**: Sức chứa tối đa **6 khách** (3 giường tiện nghi gồm 2 giường đôi lớn + 1 sofa bed, bếp mini) — **{money(p_fam)}**",
                    f"• **Phòng 2: {std['room_name']} (Hạng Standard)**: Sức chứa **2 khách** (1 giường đôi 1m6) — **{money(p_std)}**"
                ]
            elif len(deluxe_rooms) >= 2 and len(standard_rooms) >= 1:
                d1 = deluxe_rooms[0]
                d2 = deluxe_rooms[1]
                s1 = standard_rooms[0]
                combo_rooms = [d1, d2, s1]
                p_d1 = next((s["price"] for s in slot_info_for_room(d1["room_id"]) if s["khung_code"] == khung_code), 550000)
                p_d2 = next((s["price"] for s in slot_info_for_room(d2["room_id"]) if s["khung_code"] == khung_code), 550000)
                p_s1 = next((s["price"] for s in slot_info_for_room(s1["room_id"]) if s["khung_code"] == khung_code), 450000)
                total_price = p_d1 + p_d2 + p_s1
                combo_lines = [
                    f"• **Phòng 1: {d1['room_name']} (Hạng Deluxe)**: Sức chứa tối đa **3 khách** (giường King 1m8 + sofa) — **{money(p_d1)}**",
                    f"• **Phòng 2: {d2['room_name']} (Hạng Deluxe)**: Sức chứa tối đa **3 khách** (view hồ thư giãn) — **{money(p_d2)}**",
                    f"• **Phòng 3: {s1['room_name']} (Hạng Standard)**: Sức chứa **2 khách** (ấm cúng, riêng tư) — **{money(p_s1)}**"
                ]
            elif len(deluxe_rooms) >= 1 and len(standard_rooms) >= 2:
                d1 = deluxe_rooms[0]
                s1 = standard_rooms[0]
                s2 = standard_rooms[1]
                combo_rooms = [d1, s1, s2]
                p_d1 = next((s["price"] for s in slot_info_for_room(d1["room_id"]) if s["khung_code"] == khung_code), 550000)
                p_s1 = next((s["price"] for s in slot_info_for_room(s1["room_id"]) if s["khung_code"] == khung_code), 450000)
                p_s2 = next((s["price"] for s in slot_info_for_room(s2["room_id"]) if s["khung_code"] == khung_code), 450000)
                total_price = p_d1 + p_s1 + p_s2
                combo_lines = [
                    f"• **Phòng 1: {d1['room_name']} (Hạng Deluxe)**: Sức chứa tối đa **3 khách** — **{money(p_d1)}**",
                    f"• **Phòng 2: {s1['room_name']} (Hạng Standard)**: Sức chứa **2 khách** — **{money(p_s1)}**",
                    f"• **Phòng 3: {s2['room_name']} (Hạng Standard)**: Sức chứa **2 khách** — **{money(p_s2)}**"
                ]
            else:
                combo_rooms = branch_rooms[:3]
                total_price = sum(next((s["price"] for s in slot_info_for_room(r["room_id"]) if s["khung_code"] == khung_code), 500000) for r in combo_rooms)
                combo_lines = [f"• **{r['room_name']}** ({r['room_type']}): Sức chứa {r['capacity']} khách" for r in combo_rooms]

            cards = [cls._format_room_card(r, slot_info_for_room(r["room_id"])) for r in combo_rooms]
            ctx["last_recommended_rooms"] = combo_rooms
            ctx["pending_action"] = None

            budget_comp = f" (hoàn toàn nằm trong mức ngân sách dự kiến {money(budget_max)} của bạn)" if budget_max and total_price <= budget_max else ""
            msg = (
                f"Dạ có ngay ạ! CozyHome xin gửi bạn phương án chia phòng tối ưu cho đoàn **{guests_req} người** tại **{b_name}** ({stay_label} ngày **{booking_date}**):\n\n"
                f"**Phương án chia phòng đề xuất (Tổng sức chứa 7–8 khách):**\n"
                + "\n".join(combo_lines)
                + f"\n\n**Tổng chi phí dự kiến**: **{money(total_price)}** cho toàn bộ các phòng{budget_comp}.\n\n"
                f"*(Nếu bạn muốn phương án chỉ cần 2 phòng rộng rãi, bạn có thể tham khảo **CozyHome Thảo Điền**: 1 phòng Family TD07 (6 khách) + 1 phòng Standard TD01 (2 khách) với tổng chi phí chỉ **1.250.000 ₫/đêm**).*\n\n"
                f"Mời bạn tham khảo danh sách các phòng khả dụng dưới đây và nhấn nút để tự kiểm tra thông tin và đặt từng phòng nhé!"
            )
            return cls._build_response(
                session_id, "SPLIT_ROOM_RECOMMENDATION", msg,
                recommendations=cards,
                quick_replies=["Đặt các phòng này", "Xem chi nhánh Thảo Điền", "Giảm số người", "Chính sách hủy phòng"]
            )

        elif intent == "REDUCE_GUESTS_INQUIRY":
            msg = (
                "Dạ bạn có thể điều chỉnh số lượng khách lưu trú trong mỗi phòng theo đúng các mức sức chứa tiêu chuẩn của CozyHome:\n\n"
                "• **Phòng cho 1–2 khách (Hạng Standard)**: Giá từ **140.000 ₫/khung 3h** hoặc từ **450.000 ₫/qua đêm**.\n"
                "• **Phòng cho 2–3 khách (Hạng Deluxe)**: Có ban công hoặc bồn tắm, giá từ **150.000 ₫/khung 3h** hoặc từ **550.000 ₫/qua đêm**.\n"
                "• **Phòng cho 4–6 khách (Hạng Family)**: Có bếp mini nấu ăn và 3 giường ngủ thoải mái (2 giường đôi lớn + 1 sofa bed), giá từ **200.000 ₫/khung 3h** hoặc từ **800.000 ₫/qua đêm**.\n\n"
                "Bạn muốn đổi sang tìm phòng cho **mấy người** để mình kiểm tra phòng trống ngay nhé?"
            )
            return cls._build_response(
                session_id, "REDUCE_GUESTS_INQUIRY", msg,
                quick_replies=["Phòng cho 2 người", "Phòng cho 3 người", "Phòng Family 6 người", "Xem bảng giá"]
            )

        # -------------------------------------------------------------
        # Intent: ROOM_RECOMMENDATION / ROOM_SEARCH (Tư vấn và Slot filling)
        # -------------------------------------------------------------
        else:
            tx_req = check_transaction_request(query)
            disclaimer_notice = ""
            if tx_req["book"] and tx_req["pay"]:
                disclaimer_notice = "**Thông báo an toàn:** Trợ lý AI **không có quyền trực tiếp đặt phòng hoặc thực hiện thanh toán** thay cho quý khách nhằm bảo vệ an toàn thông tin cá nhân và tài khoản VietQR."
            elif tx_req["book"]:
                disclaimer_notice = "**Thông báo an toàn:** Trợ lý AI **không có quyền trực tiếp đặt phòng** thay cho quý khách nhằm đảm bảo tính bảo mật và minh bạch."
            elif tx_req["pay"]:
                disclaimer_notice = "**Thông báo an toàn:** Trợ lý AI **không có quyền can thiệp hay xử lý thanh toán tài chính** thay cho quý khách nhằm bảo vệ an toàn tài khoản ngân hàng."

            q_clean = _norm(query)

            # Trường hợp khách yêu cầu AI đặt phòng / thanh toán cho phòng cụ thể hoặc "phòng này" (AI-07)
            if (tx_req["book"] or tx_req["pay"]) and (extracted.get("specific_room_id") or ctx.get("last_room_id") or "phong nay" in q_clean):
                target_room_id = extracted.get("specific_room_id") or ctx.get("last_room_id") or "BT-STD-01"
                room = get_room(target_room_id) or all_rooms()[0]
                slots = slot_info_for_room(room["room_id"])
                msg = (
                    "**Thông báo an toàn:** Trợ lý AI **chỉ có chức năng hỗ trợ tư vấn thông tin**, "
                    "tuyệt đối không có quyền trực tiếp đặt phòng, giữ chỗ hoặc thực hiện thanh toán thay cho khách hàng.\n\n"
                    f"Quý khách vui lòng nhấn nút **'Xem chi tiết và đặt'** của phòng **{room['room_name']}** bên dưới "
                    "để tự kiểm tra thông tin, xác nhận thời gian lưu trú và hoàn tất thanh toán trực tiếp qua mã VietQR MBBank an toàn nhé!"
                )
                return cls._build_response(
                    session_id, "NEED_MORE_INFO", msg,
                    recommendations=[cls._format_room_card(room, slots)],
                    action={"type": "view_room", "target": room["room_id"], "label": f"Xem chi tiết và Đặt {room['room_name']}"},
                    quick_replies=[f"Xem chi tiết {room['room_name']}", "Chính sách hủy phòng", "Tìm phòng khác"]
                )

            # Trường hợp khách chỉ yêu cầu AI đặt phòng / thanh toán hộ mà không có tiêu chí cụ thể
            if (tx_req["book"] or tx_req["pay"]) and not extracted.get("branch_id") and not extracted.get("stay_type") and not extracted.get("specific_room_id") and not extracted.get("room_types"):
                action_text = "đặt phòng và thanh toán" if (tx_req["book"] and tx_req["pay"]) else ("đặt phòng" if tx_req["book"] else "xử lý thanh toán tài chính")
                msg = (
                    f"**Thông báo an toàn:** Theo quy định bảo mật hệ thống và an toàn tài chính, **Trợ lý AI chỉ hỗ trợ tư vấn thông tin, không có quyền trực tiếp {action_text} thay cho khách hàng** — mọi giao dịch tài chính do chính bạn xác nhận qua mã VietQR MBBank.\n\n"
                    "**Để mình hỗ trợ bạn chọn phòng nhanh nhất:**\n"
                    "Bạn muốn tìm phòng tại chi nhánh nào (**Bến Thành, Thảo Điền, Phú Mỹ Hưng**) và dự định thuê **theo giờ (khung 3 tiếng)** hay **qua đêm** ạ?"
                )
                return cls._build_response(
                    session_id, "NEED_MORE_INFO", msg,
                    quick_replies=["Bến Thành", "Thảo Điền", "Phú Mỹ Hưng", "Thuê theo giờ (3h)", "Thuê qua đêm"]
                )

            # Kiểm tra yêu cầu số lượng khách vượt quá sức chứa tối đa của mọi phòng trong chuỗi (Max = 6 ở Family)
            raw_guests = extracted.get("guests") or ctx.get("guests") or 2
            try:
                guests_req = int(raw_guests)
            except (ValueError, TypeError):
                guests_req = 2

            if guests_req > 6:
                target_branch = extracted.get("branch_id") or ctx.get("branch_id")
                b_info = BRANCH_DETAILS.get(target_branch, {}) if target_branch else {}
                b_name = b_info.get("name")

                branch_specific_note = ""
                if target_branch == "PMH":
                    branch_specific_note = (
                        f"\n\nĐặc biệt tại **CozyHome Phú Mỹ Hưng**, các phòng đang sẵn sàng vận hành có sức chứa tối đa **3 khách/phòng** (hạng Deluxe), "
                        f"phòng Family (tối đa 6 khách) hiện đang trong quá trình bảo trì định kỳ."
                    )
                elif b_name:
                    branch_specific_note = f"\n\nTại **{b_name}**, phòng có sức chứa lớn nhất là hạng Family (tối đa **6 khách**)."

                budget_max = extracted.get("budget_max") or ctx.get("budget_max")
                budget_text = f" với ngân sách tối đa {money(budget_max)}" if budget_max else ""

                # Bổ sung thông tin giải đáp tiện nghi nếu khách có hỏi (như ban công, máy chiếu)
                amenity_notes = []
                q_clean = _norm(query)
                if "may chieu" in q_clean:
                    amenity_notes.append("tiện ích máy chiếu phim/rạp phim được trang bị ở các phòng Deluxe đặc biệt (như BT-DL-01, TD-DL-01, PMH-DL-01, PMH-DL-03)")
                if "ban cong" in q_clean:
                    amenity_notes.append("các phòng Deluxe và Family tại Bến Thành, Thảo Điền và Phú Mỹ Hưng đều có ban công thoáng mát")

                amenity_str = f"\n\n*({'; '.join(amenity_notes)}).*" if amenity_notes else ""

                msg = (
                    f"Dạ CozyHome xin thông báo: Hiện tại hệ thống **không có một phòng nào đáp ứng cho {guests_req} người**{budget_text}.\n\n"
                    f"Theo quy định và tiêu chuẩn thiết kế của toàn chuỗi CozyHome, các hạng phòng có sức chứa quy chuẩn như sau:\n"
                    f"• **Hạng Standard**: Sức chứa tối đa **2 khách** (1 giường đôi 1m6).\n"
                    f"• **Hạng Deluxe**: Sức chứa **2–3 khách** (1 giường đôi King 1m8 + sofa).\n"
                    f"• **Hạng Family**: Sức chứa tối đa **6 khách** (3 giường: 2 giường đôi lớn + 1 sofa bed cao cấp).\n\n"
                    f"Để tuân thủ nghiêm ngặt quy định an toàn phòng cháy chữa cháy (PCCC) và chính sách lưu trú của CozyHome (POL-CHECKIN & POL-RULES), "
                    f"**hệ thống tuyệt đối không tự tạo phòng có sức chứa {guests_req} người**.{branch_specific_note}\n\n"
                    f"**Để hỗ trợ tốt nhất cho chuyến đi của đoàn {guests_req} người, CozyHome xin gợi ý các giải pháp sau:**\n\n"
                    f"1. **Gợi ý chia thành 2 phòng (hoặc 2–3 phòng)**:\n"
                    f"• *Tại CozyHome Phú Mỹ Hưng*: Bạn có thể chọn đặt kết hợp **2 phòng Deluxe (mỗi phòng 3 khách) + 1 phòng Standard (2 khách)** hoặc **1 phòng Deluxe (3 khách) + 2 phòng Standard (mỗi phòng 2 khách)** để vừa đủ cho {guests_req} người thoải mái. Tổng chi phí lưu trú qua đêm chỉ từ **1.450.000 ₫ – 1.550.000 ₫/đêm**, hoàn toàn nằm trong mức ngân sách của bạn.\n"
                    f"• *Tại CozyHome Thảo Điền hoặc Bến Thành*: Bạn có thể chọn đặt kết hợp **1 phòng Family (sức chứa 6 khách) + 1 phòng Standard (2 khách)** rất thuận tiện cho sinh hoạt chung (tổng chi phí qua đêm khoảng **1.250.000 ₫/đêm**).\n\n"
                    f"2. **Giảm số người/phòng**:\n"
                    f"• Điều chỉnh số lượng người ở mỗi phòng về đúng sức chứa quy định của từng hạng phòng (Standard: tối đa 2 khách; Deluxe: tối đa 3 khách; Family: tối đa 6 khách).\n\n"
                    f"3. **Thay đổi tiêu chí lưu trú**:\n"
                    f"• Bạn có thể chuyển sang chi nhánh khác có phòng Family khả dụng (như Thảo Điền hoặc Bến Thành), hoặc linh hoạt điều chỉnh ngày nhận phòng và phương án đặt nhiều phòng."
                    f"{amenity_str}\n\n"
                    f"Bạn có muốn mình **hỗ trợ lên phương án chia phòng cụ thể** không ạ?"
                )

                ctx["pending_action"] = "suggest_split_rooms"

                return cls._build_response(
                    session_id, "ROOM_RECOMMENDATION", msg,
                    recommendations=[],
                    quick_replies=["Gợi ý chia 2 phòng", "Giảm số người", "Xem phòng Thảo Điền", "Xem phòng Bến Thành", "Quy định sức chứa"]
                )

            # Slot Filling: Xử lý thông minh và linh hoạt khi thiếu tiêu chí bắt buộc
            has_no_branch = not ctx.get("branch_id")
            has_no_time = (not ctx.get("stay_type") and not ctx.get("khung_code") and not ctx.get("date"))
            has_no_room = not ctx.get("specific_room_id")

            # Trường hợp 1: Người dùng CHƯA CUNG CẤP CẢ CHI NHÁNH LẪN THỜI GIAN
            # (VD: "mình muốn tìm một phòng", "tôi muốn đặt phòng", "cho chuyến đi sắp tới", "tư vấn phòng", "đặt phòng 2 người"...)
            if has_no_branch and has_no_time and has_no_room:
                disclaimer_prefix = f"{disclaimer_notice}\n\n" if disclaimer_notice else ""
                has_guests = extracted.get("guests") or ctx.get("guests")

                # Subcase 1A: Người dùng có nói số khách (VD: "đặt phòng 2 người", "tìm phòng cho 2 người", "cho 3 người")
                if has_guests:
                    req_guests = int(has_guests)
                    ctx["guests"] = req_guests
                    guest_label = f"{req_guests} người" if req_guests > 1 else "1 người"

                    # Lấy 3 phòng mẫu đại diện tại 3 chi nhánh để khách tham khảo trực quan
                    sample_candidates, _ = search_rooms(branch_id=None, guests=req_guests, preferences=None)
                    sample_candidates = [c for c in sample_candidates if c.get("operational_status") != "Bảo trì"]
                    sample_rooms = []
                    seen_branches = set()
                    for c in sample_candidates:
                        b = c.get("branch_id")
                        if b not in seen_branches:
                            sample_rooms.append(c)
                            seen_branches.add(b)
                        if len(sample_rooms) >= 3:
                            break
                    if not sample_rooms and sample_candidates:
                        sample_rooms = sample_candidates[:3]

                    sample_cards = [cls._format_room_card_from_candidate(c) for c in sample_rooms]
                    ctx["last_recommended_rooms"] = sample_rooms
                    if sample_rooms:
                        ctx["last_room_id"] = sample_rooms[0]["room_id"]

                    msg = (
                        f"{disclaimer_prefix}"
                        f"Dạ CozyHome rất hân hạnh được hỗ trợ tư vấn cho bạn! Với nhu cầu lưu trú cho **{guest_label}**, "
                        f"CozyHome có rất nhiều lựa chọn phòng Standard và Deluxe ấm cúng, riêng tư tại cả 3 chi nhánh "
                        f"(mức giá từ **140.000 ₫/khung 3 tiếng** hoặc từ **450.000 ₫/qua đêm**).\n\n"
                        f"Dưới đây là một số gợi ý phòng tiêu biểu dành cho {guest_label} để bạn tham khảo trước. "
                        f"Để mình kiểm tra tình trạng phòng trống và mức giá chính xác nhất, bạn chia sẻ thêm giúp mình:\n"
                        f"• Bạn muốn ở **chi nhánh nào** (**Bến Thành - Q.1**, **Thảo Điền - Thủ Đức**, hay **Phú Mỹ Hưng - Q.7**)?\n"
                        f"• Bạn dự định lưu trú **theo giờ (khung 3 tiếng)** hay **qua đêm**, vào ngày nào ạ?"
                    )
                    return cls._build_response(
                        session_id, "NEED_MORE_INFO", msg,
                        recommendations=sample_cards,
                        quick_replies=["Chi nhánh Bến Thành", "Chi nhánh Thảo Điền", "Chi nhánh Phú Mỹ Hưng", "Thuê theo giờ (3h)", "Thuê qua đêm"],
                        action={"type": "select_branch", "label": "Chọn chi nhánh"}
                    )

                # Subcase 1B: Người dùng hỏi chung chung chưa rõ số khách (AI-02)
                else:
                    msg = (
                        f"{disclaimer_prefix}"
                        "Dạ mình rất sẵn lòng hỗ trợ tư vấn chọn phòng cho chuyến đi sắp tới của bạn tại CozyHome!\n\n"
                        "Hiện chuỗi CozyHome có **3 chi nhánh tại TP.HCM** với đầy đủ các hạng phòng Standard, Deluxe và Family, "
                        "phục vụ linh hoạt theo 2 hình thức: **thuê theo giờ (khung 3 tiếng từ 140.000 ₫)** và **thuê qua đêm (từ 450.000 ₫)**.\n\n"
                        "Để mình gợi ý phương án phòng phù hợp và chính xác nhất, bạn chia sẻ thêm giúp mình một số thông tin nhé:\n"
                        "• **Chi nhánh**: Bạn muốn ở khu vực nào (**Bến Thành - Q.1**, **Thảo Điền - Thủ Đức**, hay **Phú Mỹ Hưng - Q.7**)?\n"
                        "• **Thời gian lưu trú**: Bạn dự định nhận phòng và trả phòng ngày nào (thuê theo giờ 3 tiếng hay qua đêm)?\n"
                        "• **Số khách & Ngân sách**: Chuyến đi có mấy người và mức ngân sách dự kiến khoảng bao nhiêu ạ?"
                    )
                    return cls._build_response(
                        session_id, "NEED_MORE_INFO", msg,
                        quick_replies=["Bến Thành (Q.1)", "Thảo Điền (Thủ Đức)", "Phú Mỹ Hưng (Q.7)", "Thuê theo giờ (3h)", "Thuê qua đêm"]
                    )

            # Trường hợp 2: Khách đã chọn CHI NHÁNH, nhưng CHƯA CÓ THỜI GIAN (theo giờ hay qua đêm, ngày nào)
            if not has_no_branch and has_no_time and has_no_room:
                b_info = BRANCH_DETAILS.get(ctx.get("branch_id"), BRANCH_DETAILS["BT"])
                disclaimer_prefix = f"{disclaimer_notice}\n\n" if disclaimer_notice else ""
                msg = (
                    f"{disclaimer_prefix}"
                    f"Dạ chi nhánh **{b_info['name']}** ({b_info['address']}) có phong cách {b_info['concept_name']} rất ấm cúng và tiện nghi, "
                    f"với các phòng Standard và Deluxe (mức giá từ **140.000 ₫/khung 3 tiếng** hoặc từ **450.000 ₫/qua đêm**).\n\n"
                    f"Để mình kiểm tra phòng trống chính xác tại {b_info['name']}, bạn cho mình biết thêm:\n"
                    f"• Bạn dự định thuê **theo giờ (khung 3 tiếng)** hay **qua đêm**?\n"
                    f"• Bạn nhận phòng vào **ngày nào** và chuyến đi có **mấy người** ạ?"
                )
                return cls._build_response(
                    session_id, "NEED_MORE_INFO", msg,
                    quick_replies=["Thuê theo giờ (3h)", "Thuê qua đêm", f"Xem phòng {b_info['name']}"]
                )

            # Trường hợp 3: Khách đã chọn THỜI GIAN (hoặc hình thức theo giờ/qua đêm), nhưng CHƯA CHỌN CHI NHÁNH
            if has_no_branch and not has_no_time and has_no_room:
                disclaimer_prefix = f"{disclaimer_notice}\n\n" if disclaimer_notice else ""
                msg = (
                    f"{disclaimer_prefix}"
                    "Dạ CozyHome đã ghi nhận thời gian dự định lưu trú của bạn! Hiện CozyHome có **3 chi nhánh tại TP.HCM**:\n"
                    "• **Bến Thành (Quận 1)**: Trung tâm năng động, gần chợ Bến Thành và phố đi bộ.\n"
                    "• **Thảo Điền (TP. Thủ Đức)**: Không gian xanh ven sông, yên tĩnh và lãng mạn.\n"
                    "• **Phú Mỹ Hưng (Quận 7)**: Khu đô thị hiện đại, thoáng mát gần Hồ Bán Nguyệt.\n\n"
                    "Bạn ưu tiên chọn chi nhánh nào và chuyến đi có mấy người để mình kiểm tra phòng trống cụ thể nhé?"
                )
                return cls._build_response(
                    session_id, "NEED_MORE_INFO", msg,
                    quick_replies=["Bến Thành (Q.1)", "Thảo Điền (Thủ Đức)", "Phú Mỹ Hưng (Q.7)"]
                )

            # Trường hợp 4: Khách đã có chi nhánh, ngày và số khách, nhưng chưa rõ thuê theo giờ hay qua đêm
            if ctx.get("stay_type") is None and not ctx.get("khung_code"):
                b_name = BRANCH_DETAILS.get(ctx.get("branch_id"), {}).get("name", "CozyHome")
                disclaimer_prefix = f"{disclaimer_notice}\n\n" if disclaimer_notice else ""
                msg = f"{disclaimer_prefix}Dạ CozyHome đã ghi nhận nhu cầu của bạn tại **{b_name}**. Bạn muốn thuê phòng **theo giờ (khung 3 tiếng)** hay **lưu trú qua đêm** ạ?"
                return cls._build_response(
                    session_id, "NEED_MORE_INFO", msg,
                    quick_replies=["Theo giờ (3 tiếng)", "Qua đêm", "Xem tất cả phòng"]
                )

            # Đã có đủ thông tin hoặc có thể tìm kiếm theo tiêu chí hiện tại
            booking_date = ctx.get("date") or dt_date.today().isoformat()
            khung_code = ctx.get("khung_code") or ("QD" if ctx.get("stay_type") == "overnight" else "K1")
            branch_id = ctx.get("branch_id")
            budget_max = ctx.get("budget_max")
            preferences = ctx.get("preferences") or []
            room_types = ctx.get("room_types") or []

            # Gọi Business Service tìm phòng thực tế (lọc cứng theo BR-01, BR-02, BR-13)
            candidates, _ = search_rooms(
                branch_id=branch_id,
                guests=guests_req,
                booking_date=booking_date,
                khung_code=khung_code,
                budget_max=budget_max,
                preferences=preferences,
                room_types=room_types,
            )

            # Loại bỏ phòng đang bảo trì
            candidates = [c for c in candidates if c.get("operational_status") != "Bảo trì"]

            # Lọc/sắp xếp nếu khách hàng yêu cầu phòng rẻ hơn / tiết kiệm hơn
            is_asking_cheaper = any(k in q_clean for k in ["re hon", "tiet kiem hon", "gia re", "thap hon", "re nhat"])
            if is_asking_cheaper:
                candidates.sort(key=lambda c: c.get("price") or 999999999)

            if not candidates:
                b_info = BRANCH_DETAILS.get(branch_id, {})
                b_name = b_info.get("name", "chi nhánh đã chọn") if branch_id else "chi nhánh đã chọn"

                # Kiểm tra số lượng phòng thực tế còn trống tại chi nhánh đã chọn trong ngày và khung giờ này (đồng bộ 100% với lịch phòng)
                branch_available_rooms = []
                if branch_id:
                    branch_available_rooms = [
                        r for r in all_rooms()
                        if r.get("branch_id") == branch_id
                        and is_demo_available(r["room_id"], booking_date, khung_code)
                        and r.get("operational_status") != "Bảo trì"
                    ]

                # Nếu không có phòng thỏa mãn tại chi nhánh này, thử tìm chi nhánh khác để gợi ý thay thế
                alt_candidates, _ = search_rooms(
                    branch_id=None,
                    guests=guests_req,
                    booking_date=booking_date,
                    khung_code=khung_code,
                    budget_max=budget_max,
                    preferences=preferences,
                    room_types=room_types,
                )
                alt_candidates = [c for c in alt_candidates if c.get("operational_status") != "Bảo trì"]

                disclaimer_prefix = f"{disclaimer_notice}\n\n" if disclaimer_notice else ""

                # Kiểm tra yêu cầu tiện nghi không hỗ trợ (hồ bơi riêng) hoặc ngân sách quá thấp dưới sàn giá chuỗi (AI-06)
                has_unsupported_pref = any(p in ["hồ bơi", "be boi", "ho boi"] for p in preferences)
                is_budget_too_low = budget_max and ((khung_code == "QD" and budget_max < 450000) or budget_max < 140000)

                if has_unsupported_pref or is_budget_too_low:
                    reasons = []
                    if is_budget_too_low:
                        reasons.append(f"mức ngân sách {money(budget_max)} thấp hơn giá niêm yết tối thiểu của chuỗi (từ 140.000 ₫/khung 3h hoặc từ 450.000 ₫/đêm)")
                    if has_unsupported_pref:
                        reasons.append("chuỗi CozyHome là homestay đô thị nên chưa có tiện ích hồ bơi riêng")
                    reason_msg = " do " + " và ".join(reasons) if reasons else ""

                    msg = (
                        f"{disclaimer_prefix}"
                        f"Rất tiếc, hiện tại CozyHome chưa tìm thấy phòng nào đáp ứng các tiêu chí của bạn tại {b_name}{reason_msg}. "
                        f"Hệ thống đề xuất bạn có thể điều chỉnh mức ngân sách hoặc thay đổi tiêu chí tiện nghi để mình hỗ trợ tìm phòng phù hợp nhất nhé!"
                    )
                    return cls._build_response(
                        session_id, "NO_MATCH", msg,
                        quick_replies=["Nâng mức ngân sách", "Bỏ tiêu chí hồ bơi", "Xem tất cả phòng"]
                    )

                # Lọc riêng các phòng có sức chứa đáp ứng đủ số khách yêu cầu
                valid_cap_rooms = [r for r in branch_available_rooms if int(r.get("capacity", 2)) >= guests_req]

                # TRƯỜNG HỢP 1A: Chi nhánh có phòng trống nhưng KHÔNG CÓ PHÒNG NÀO ĐÁP ỨNG ĐỦ SỨC CHỨA
                if branch_available_rooms and not valid_cap_rooms:
                    max_branch_cap = max([int(r.get("capacity", 2)) for r in branch_available_rooms], default=2)
                    has_family = any(r.get("room_type") == "Family" and r.get("branch_id") == branch_id for r in all_rooms())
                    maint_note = "; phòng Family (6 khách) tại chi nhánh hiện đang trong quá trình bảo trì định kỳ" if has_family else ""

                    msg = (
                        f"{disclaimer_prefix}"
                        f"Dạ tại **{b_name}**, hiện tại **không có một phòng nào đáp ứng đủ cho {guests_req} người** "
                        f"(sức chứa tối đa của các phòng đang khả dụng tại chi nhánh là **{max_branch_cap} khách/phòng**{maint_note}).\n\n"
                        f"Hệ thống **tuyệt đối không tự tạo phòng vượt quá sức chứa quy chuẩn** nhằm đảm bảo đúng tiêu chuẩn an toàn PCCC và quy định lưu trú của CozyHome.\n\n"
                        f"**CozyHome xin gợi ý các phương án sau:**\n"
                        f"1. **Chia thành 2 phòng** tại {b_name} (ví dụ: kết hợp các phòng Deluxe và Standard để đủ chỗ cho đoàn {guests_req} người).\n"
                        f"2. **Giảm số người/phòng** về đúng sức chứa tối đa của từng phòng (tối đa 2 khách cho Standard, 3 khách cho Deluxe).\n"
                        f"3. **Thay đổi tiêu chí**: Chuyển sang chi nhánh Thảo Điền hoặc Bến Thành hiện có các phòng Family (sức chứa 6 khách) đang sẵn sàng đón bạn."
                    )

                    if alt_candidates:
                        msg += f"\n\nTuy nhiên, CozyHome có **{len(alt_candidates)} phòng trống** phù hợp cho {guests_req} khách tại các chi nhánh khác, mời bạn tham khảo:"
                        cards = [cls._format_room_card_from_candidate(c) for c in alt_candidates[:3]]
                        ctx["last_recommended_rooms"] = alt_candidates[:3]
                        return cls._build_response(
                            session_id, "ROOM_RECOMMENDATION", msg,
                            recommendations=cards,
                            quick_replies=["Gợi ý chia 2 phòng", "Giảm số người", "Xem phòng Thảo Điền", "Xem phòng Bến Thành"]
                        )
                    else:
                        return cls._build_response(
                            session_id, "ROOM_RECOMMENDATION", msg,
                            recommendations=[],
                            quick_replies=["Gợi ý chia 2 phòng", "Giảm số người", "Xem phòng Thảo Điền", "Xem phòng Bến Thành"]
                        )

                # TRƯỜNG HỢP 1B: Chi nhánh có phòng trống ĐỦ SỨC CHỨA nhưng chưa khớp tiêu chí lọc khác (tiện nghi, ngân sách, hạng phòng)
                elif valid_cap_rooms:
                    top_branch_rooms = valid_cap_rooms[:3]
                    ctx["last_recommended_rooms"] = top_branch_rooms
                    cards = [cls._format_room_card_from_candidate(c) for c in top_branch_rooms]

                    filter_notes = []
                    if budget_max:
                        filter_notes.append(f"ngân sách tối đa {money(budget_max)}")
                    if preferences:
                        filter_notes.append(f"tiện nghi ({', '.join(preferences)})")
                    if room_types:
                        filter_notes.append(f"hạng {', '.join(room_types)}")
                    filter_str = f" phù hợp với {', '.join(filter_notes)}" if filter_notes else ""

                    msg = (
                        f"{disclaimer_prefix}"
                        f"Tại **{b_name}** trong khung giờ đã chọn ngày **{booking_date}**, hệ thống chưa có phòng{filter_str}. "
                        f"Tuy nhiên, chi nhánh hiện vẫn còn **{len(valid_cap_rooms)} phòng trống** đủ sức chứa {guests_req} người sẵn sàng đón bạn, mời bạn tham khảo các phòng khả dụng dưới đây:"
                    )
                    return cls._build_response(
                        session_id, "ROOM_RECOMMENDATION", msg,
                        recommendations=cards,
                        quick_replies=["Xem chi tiết phòng", "Đổi ngày khác", "Xem tất cả phòng"]
                    )

                # TRƯỜNG HỢP 2: Chi nhánh thực sự ĐÃ KÍN PHÒNG trên toàn bộ lịch khung giờ đó
                elif alt_candidates:
                    top_alts = alt_candidates[:3]
                    ctx["last_recommended_rooms"] = top_alts
                    cards = [cls._format_room_card_from_candidate(c) for c in top_alts]
                    msg = (
                        f"{disclaimer_prefix}"
                        f"Trong khung giờ đã chọn ngày **{booking_date}**, tất cả các phòng tại **{b_name}** hiện đã kín. "
                        f"Tuy nhiên, CozyHome vẫn còn **{len(alt_candidates)} phòng trống** rất phù hợp tại các chi nhánh khác, mời bạn tham khảo:"
                    )
                    return cls._build_response(
                        session_id, "ROOM_RECOMMENDATION", msg,
                        recommendations=cards,
                        quick_replies=["Đổi khung giờ khác", "Đổi ngày khác", "Xem chi tiết"]
                    )
                else:
                    msg = (
                        f"{disclaimer_prefix}"
                        f"Rất tiếc, hiện tại CozyHome chưa tìm thấy phòng nào đáp ứng đầy đủ các tiêu chí của bạn tại chi nhánh và thời gian yêu cầu"
                        f"{f' với mức ngân sách tối đa {money(budget_max)}' if budget_max else ''}"
                        f"{f' và các tiện nghi ({', '.join(preferences)})' if preferences else ''}. "
                        f"Hệ thống đề xuất bạn có thể điều chỉnh mức ngân sách hoặc linh hoạt thay đổi tiêu chí tiện nghi / ngày nhận phòng để mình hỗ trợ tìm phòng phù hợp nhất nhé!"
                    )
                    return cls._build_response(
                        session_id, "NO_MATCH", msg,
                        quick_replies=["Nâng mức ngân sách", "Đổi ngày khác", "Xem tất cả phòng"]
                    )

            # Chọn tối đa 3 phòng phù hợp nhất
            top_rooms = candidates[:3]
            ctx["last_recommended_rooms"] = top_rooms
            ctx["last_room_id"] = top_rooms[0]["room_id"]

            cards = [cls._format_room_card_from_candidate(c) for c in top_rooms]

            # Diễn giải câu trả lời theo đúng phong cách Đồ án (Chương 4.3.1)
            reasons_summary = []
            for c in top_rooms:
                matched_amenities = [a for a in (c.get("amenities") or []) if any(p.lower() in a.lower() for p in preferences)]
                pref_text = f", có {', '.join(matched_amenities)}" if matched_amenities else ""
                reasons_summary.append(f"• **{c['room_name']}** ({c['branch_name']}): Hạng {c['room_type']}, sức chứa {c['capacity']} khách{pref_text}, giá {money(c['price'])}.")

            b_info = BRANCH_DETAILS.get(branch_id, {})
            b_name = b_info.get("name", "CozyHome") if branch_id else "CozyHome"
            stay_type_name = "khung qua đêm" if khung_code == "QD" else "khung 3 giờ"
            rt_label = f", hạng {', '.join(room_types)}" if room_types else ""

            if disclaimer_notice:
                base_msg = (
                    f"{disclaimer_notice}\n\n"
                    f"Tuy nhiên, CozyHome đã tìm thấy các phòng còn trống phù hợp với yêu cầu của bạn tại **{b_name}**:\n"
                    + "\n".join(reasons_summary)
                    + "\n\nBạn vui lòng chọn phòng bên dưới và nhấn **'Xem chi tiết và đặt'** để tự hoàn tất đặt chỗ và thanh toán an toàn nhé!"
                )
            else:
                base_msg = (
                    f"Đã ghi nhận yêu cầu tại **{b_name}** cho **{guests_req} người**{rt_label}, **{stay_type_name}** ngày **{booking_date}**.\n\n"
                    f"Các phòng còn trống được hiển thị theo dữ liệu hiện có:\n"
                    + "\n".join(reasons_summary)
                    + "\n\nBạn vui lòng chọn một phòng bên dưới để xem chi tiết và tiếp tục đặt phòng nhé!"
                )

            # Thử làm giàu câu trả lời bằng Gemini nếu có cấu hình LLM (vẫn dựa trên dữ liệu thật 100%)
            if ai_service and os.environ.get("GEMINI_API_KEY"):
                try:
                    notice_instruction = ""
                    if disclaimer_notice:
                        notice_instruction = (
                            "LƯU Ý BẮT BUỘC: Khách hàng đang nhờ đặt phòng hoặc thanh toán giúp. "
                            "AI tuyệt đối KHÔNG được nhận làm thay. Bạn BẮT BUỘC phải mở đầu câu trả lời bằng việc nêu rõ "
                            "AI không thể tự thực hiện đặt phòng hay thanh toán thay cho khách để bảo mật giao dịch, "
                            "sau đó mới giới thiệu các phòng phù hợp và hướng dẫn khách bấm chọn phòng bên dưới để tự hoàn tất giao dịch. "
                            "Không dùng các ký hiệu mã kỹ thuật như BR và không dùng icon emoji. "
                        )
                    llm_prompt = (
                        f"Khách hàng hỏi: '{query}'.\n"
                        f"{notice_instruction}"
                        f"Hệ thống đã lọc được các phòng sau (dữ liệu thật, cấm bịa thêm):\n"
                        f"{json.dumps(top_rooms, ensure_ascii=False)}\n"
                        f"Hãy viết một đoạn trả lời lịch sự, thân thiện bằng tiếng Việt (2-3 câu ngắn), "
                        f"tóm tắt vì sao các phòng trên phù hợp với khách hàng. Tuyệt đối không dùng từ ngữ kỹ thuật như database, API, JSON, và không dùng icon emoji."
                    )
                    llm_res = ai_service.call_ai(
                        system_instruction="Bạn là trợ lý tư vấn phòng CozyHome. Chỉ dùng dữ liệu được cung cấp, không bịa đặt. Tuyệt đối không tự thực hiện đặt phòng, thanh toán, hủy hoặc gia hạn. Không dùng các ký hiệu mã kỹ thuật như BR và không dùng icon emoji.",
                        prompt_text=llm_prompt,
                        timeout_s=5,
                    )
                    if llm_res and llm_res.get("text"):
                        gen_text = llm_res["text"].strip()
                        if disclaimer_notice:
                            if not gen_text.startswith("Thông báo an toàn"):
                                base_msg = f"{disclaimer_notice}\n\n{gen_text}"
                            else:
                                base_msg = gen_text
                        else:
                            base_msg = gen_text
                except Exception:
                    pass

            return cls._build_response(
                session_id, "ROOM_RECOMMENDATION", base_msg,
                recommendations=cards,
                quick_replies=[f"Xem {top_rooms[0]['room_name']}", "Có phòng nào rẻ hơn?", "Chính sách hủy phòng"]
            )

    @classmethod
    def _format_room_card(cls, room: dict[str, Any], slots: list[dict[str, Any]]) -> dict[str, Any]:
        images = room.get("images") or []
        img_url = images[0] if images else "/static/images/cozyhome-logo.png"
        min_price = min([s["price"] for s in slots if s.get("price")] or [150000])
        return {
            "room_id": room["room_id"],
            "room_name": room["room_name"],
            "branch_name": room.get("branch_name", "CozyHome"),
            "room_type": room.get("room_type", "Standard"),
            "capacity": room.get("capacity", 2),
            "price": min_price,
            "formatted_price": money(min_price),
            "amenities": (room.get("amenities") or [])[:3],
            "image": img_url,
            "reason": f"Sức chứa {room.get('capacity', 2)} người, phong cách {room.get('concept_name', 'Cozy')}.",
        }

    @classmethod
    def _format_room_card_from_candidate(cls, c: dict[str, Any]) -> dict[str, Any]:
        room = get_room(c["room_id"]) or {}
        images = room.get("images") or c.get("images") or []
        img_url = images[0] if images else "/static/images/cozyhome-logo.png"
        return {
            "room_id": c["room_id"],
            "room_name": c["room_name"],
            "branch_name": c.get("branch_name", "CozyHome"),
            "room_type": c.get("room_type", "Standard"),
            "capacity": c.get("capacity", 2),
            "price": c.get("price", 150000),
            "formatted_price": money(c.get("price", 150000)),
            "amenities": (c.get("amenities") or [])[:3],
            "image": img_url,
            "reason": f"Phù hợp {c.get('capacity', 2)} khách - {c.get('concept_name', 'Cozy')}.",
        }

    @classmethod
    def _build_response(
        cls,
        session_id: str,
        intent: str,
        message: str,
        recommendations: list[dict[str, Any]] | None = None,
        policy_card: dict[str, Any] | None = None,
        quick_replies: list[str] | None = None,
        action: dict[str, Any] | None = None,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        SessionManager.add_history(session_id, "assistant", message)
        meta = {
            "intent": intent,
            "recommendations": recommendations or [],
            "policy_card": policy_card,
            "quick_replies": quick_replies or [],
            "action": action,
        }
        if save_chat_message:
            try:
                sess_uid = user_id or SessionManager.get_session(session_id).get("context", {}).get("user_id")
                save_chat_message(session_id, "assistant", message, user_id=sess_uid, meta=meta)
            except Exception:
                pass

        return {
            "status": "ok",
            "session_id": session_id,
            "intent": intent,
            "message": message,
            "recommendations": recommendations or [],
            "policy_card": policy_card,
            "quick_replies": quick_replies or [],
            "action": action,
        }
