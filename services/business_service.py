from __future__ import annotations

import csv
import json
import re
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


def _norm(text: str) -> str:
    """Chuẩn hóa chuỗi tiếng Việt: thay đ->d, Đ->D, bỏ dấu, lowercase để tìm kiếm không dấu."""
    if not text:
        return ""
    t = str(text).replace("đ", "d").replace("Đ", "D")
    return unicodedata.normalize("NFD", t).encode("ascii", "ignore").decode("ascii").lower().strip()

try:
    from services.recommendation_engine import load_data, recommend_candidates, resolve_khung_time
    from services.storage import booking_exists, get_room_slot_group, latest_room_operations
except ImportError:
    from recommendation_engine import load_data, recommend_candidates, resolve_khung_time
    from storage import booking_exists, get_room_slot_group, latest_room_operations

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# Tiện nghi tiêu chuẩn mặc định cam kết có trong 100% phòng của toàn chuỗi CozyHome (BR-01, BR-02)
STANDARD_AMENITIES = {
    # Phòng tắm riêng và vệ sinh khép kín
    "phong tam rieng", "phong tam", "wc rieng", "ve sinh rieng", "toilet rieng",
    "nha ve sinh rieng", "khan tam", "may say", "may say toc",
    # Điều hòa / Máy lạnh hai chiều
    "dieu hoa", "may lanh", "may lanh hai chieu",
    # Internet tốc độ cao
    "wifi", "wi-fi", "internet", "mang internet",
    # Minibar / Tủ lạnh mini
    "minibar", "tu lanh", "tu lanh mini",
    # Bàn làm việc
    "ban lam viec", "ban lam viec rieng", "ban lam viec ca nhan", "ban ghe lam viec", "ban ghe",
    # Nước nóng và đồ gia dụng tiêu chuẩn
    "nuoc nong", "binh nong lanh", "am dun", "am sieu toc", "am dun nuoc",
}

BRANCHES = {
    "BT": "CozyHome Bến Thành",
    "TD": "CozyHome Thảo Điền",
    "PMH": "CozyHome Phú Mỹ Hưng",
}
# Bảng 3.4. Cấu hình nhóm khung giờ ban đầu của CozyHome
SLOT_GROUPS_SCHEDULE = {
    "N1": {
        "name": "Nhóm 1",
        "rooms_hint": "Phòng 1 và 5 (BT/TD/PMH)",
        "slots": {
            "K1": {"start": "09:30", "end": "12:30", "label": "09:30 – 12:30", "shift": "Sáng"},
            "K2": {"start": "13:00", "end": "16:00", "label": "13:00 – 16:00", "shift": "Chiều"},
            "K3": {"start": "16:30", "end": "19:30", "label": "16:30 – 19:30", "shift": "Tối"},
            "QD": {"start": "20:00", "end": "08:30+1", "label": "20:00 – 08:30 hôm sau", "shift": "Qua đêm"},
        }
    },
    "N2": {
        "name": "Nhóm 2",
        "rooms_hint": "Phòng 2 và 6 (BT/TD/PMH)",
        "slots": {
            "K1": {"start": "10:00", "end": "13:00", "label": "10:00 – 13:00", "shift": "Sáng"},
            "K2": {"start": "13:30", "end": "16:30", "label": "13:30 – 16:30", "shift": "Chiều"},
            "K3": {"start": "17:00", "end": "20:00", "label": "17:00 – 20:00", "shift": "Tối"},
            "QD": {"start": "20:30", "end": "09:00+1", "label": "20:30 – 09:00 hôm sau", "shift": "Qua đêm"},
        }
    },
    "N3": {
        "name": "Nhóm 3",
        "rooms_hint": "Phòng 3 và 7 (BT/TD/PMH)",
        "slots": {
            "K1": {"start": "10:30", "end": "13:30", "label": "10:30 – 13:30", "shift": "Sáng"},
            "K2": {"start": "14:00", "end": "17:00", "label": "14:00 – 17:00", "shift": "Chiều"},
            "K3": {"start": "17:30", "end": "20:30", "label": "17:30 – 20:30", "shift": "Tối"},
            "QD": {"start": "21:00", "end": "09:30+1", "label": "21:00 – 09:30 hôm sau", "shift": "Qua đêm"},
        }
    },
    "N4": {
        "name": "Nhóm 4",
        "rooms_hint": "Phòng 4 và 8 (BT/TD/PMH)",
        "slots": {
            "K1": {"start": "11:00", "end": "14:00", "label": "11:00 – 14:00", "shift": "Sáng"},
            "K2": {"start": "14:30", "end": "17:30", "label": "14:30 – 17:30", "shift": "Chiều"},
            "K3": {"start": "18:00", "end": "21:00", "label": "18:00 – 21:00", "shift": "Tối"},
            "QD": {"start": "21:30", "end": "10:00+1", "label": "21:30 – 10:00 hôm sau", "shift": "Qua đêm"},
        }
    }
}

ALL_SLOT_OPTIONS = [
    {"code": "", "name": "Tất cả khung giờ (Xem toàn bộ)", "shift": "Tất cả", "group_id": "ALL"},
    # Buổi sáng
    {"code": "K1", "name": "Buổi sáng (09:30 – 14:00)", "shift": "Buổi sáng", "group_id": "ALL"},
    {"code": "K1_N1", "name": "09:30 – 12:30", "shift": "Buổi sáng", "group_id": "N1"},
    {"code": "K1_N2", "name": "10:00 – 13:00", "shift": "Buổi sáng", "group_id": "N2"},
    {"code": "K1_N3", "name": "10:30 – 13:30", "shift": "Buổi sáng", "group_id": "N3"},
    {"code": "K1_N4", "name": "11:00 – 14:00", "shift": "Buổi sáng", "group_id": "N4"},
    # Buổi chiều
    {"code": "K2", "name": "Buổi chiều (13:00 – 17:30)", "shift": "Buổi chiều", "group_id": "ALL"},
    {"code": "K2_N1", "name": "13:00 – 16:00", "shift": "Buổi chiều", "group_id": "N1"},
    {"code": "K2_N2", "name": "13:30 – 16:30", "shift": "Buổi chiều", "group_id": "N2"},
    {"code": "K2_N3", "name": "14:00 – 17:00", "shift": "Buổi chiều", "group_id": "N3"},
    {"code": "K2_N4", "name": "14:30 – 17:30", "shift": "Buổi chiều", "group_id": "N4"},
    # Buổi tối
    {"code": "K3", "name": "Buổi tối (16:30 – 21:00)", "shift": "Buổi tối", "group_id": "ALL"},
    {"code": "K3_N1", "name": "16:30 – 19:30", "shift": "Buổi tối", "group_id": "N1"},
    {"code": "K3_N2", "name": "17:00 – 20:00", "shift": "Buổi tối", "group_id": "N2"},
    {"code": "K3_N3", "name": "17:30 – 20:30", "shift": "Buổi tối", "group_id": "N3"},
    {"code": "K3_N4", "name": "18:00 – 21:00", "shift": "Buổi tối", "group_id": "N4"},
    # Qua đêm
    {"code": "QD", "name": "Qua đêm (20:00 – 10:00)", "shift": "Qua đêm", "group_id": "ALL"},
    {"code": "QD_N1", "name": "20:00 – 08:30 (hôm sau)", "shift": "Qua đêm", "group_id": "N1"},
    {"code": "QD_N2", "name": "20:30 – 09:00 (hôm sau)", "shift": "Qua đêm", "group_id": "N2"},
    {"code": "QD_N3", "name": "21:00 – 09:30 (hôm sau)", "shift": "Qua đêm", "group_id": "N3"},
    {"code": "QD_N4", "name": "21:30 – 10:00 (hôm sau)", "shift": "Qua đêm", "group_id": "N4"},
]

SLOT_NAMES = {
    "K1": "Khung 1 (Sáng)",
    "K2": "Khung 2 (Chiều)",
    "K3": "Khung 3 (Tối)",
    "QD": "Khung Qua đêm",
    "K4": "Khung Qua đêm",
}


def money(v: int | None) -> str:
    return "—" if v is None else f"{int(v):,} ₫".replace(",", ".")


def all_rooms() -> list[dict[str, Any]]:
    rooms, *_ = load_data()
    return rooms


def get_room(room_id: str) -> dict[str, Any] | None:
    return next((r for r in all_rooms() if r["room_id"] == room_id), None)


def slot_info_for_room(room_id: str) -> list[dict[str, Any]]:
    rooms, _, prices, slot_time, _ = load_data()
    r = next(x for x in rooms if x["room_id"] == room_id)
    pmap = {(p["room_id"], p["khung_code"]): p["base_price"] for p in prices}
    # BR-03, UC-05.2: Lấy nhóm khung giờ động nếu Quản lý chuỗi đã cấu hình
    sg_id = get_room_slot_group(room_id, r["slot_group_id"])
    result = []
    shift_names = {"K1": "Sáng", "K2": "Chiều", "K3": "Tối", "QD": "Qua đêm", "K4": "Qua đêm"}
    for code in ("K1", "K2", "K3", "QD"):
        t = resolve_khung_time(slot_time, sg_id, code)
        shift = shift_names.get(code, "")
        clean_end = t[1].replace("+1", "")
        slot_label = f"{t[0]} – {clean_end} ({shift})"
        result.append({
            "khung_code": code,
            "label": slot_label,
            "start_time": t[0],
            "end_time": clean_end,
            "next_slot": t[2],
            "price": pmap.get((room_id, code)),
            "slot_group_id": sg_id
        })
    return result


def effective_room_status(room: dict[str, Any]) -> str:
    ops = {o["room_id"]: o["status"] for o in latest_room_operations()}
    return ops.get(room["room_id"], room["operational_status"])


def is_demo_available(room_id: str, booking_date: str, khung_code: str, exclude_booking_code: str | None = None) -> bool:
    room = get_room(room_id)
    if not room:
        return False
    status = effective_room_status(room)
    # Phòng đang bảo trì hoặc ngừng hoạt động thì toàn bộ lịch không khả dụng
    if status in ("Bảo trì", "Ngừng hoạt động"):
        return False
    # Kiểm tra xem đã có lượt đặt trước trong cơ sở dữ liệu hay chưa
    if booking_exists(room_id, booking_date, khung_code, exclude_booking_code=exclude_booking_code):
        return False
    # Dataset kiểm thử chỉ phủ 25–31/08/2026. Với ngày ngoài dataset, demo coi trống
    # nếu không có booking và phòng đang vận hành; đây là dữ liệu demo runtime, không
    # làm thay đổi bộ dữ liệu PoC dùng trong báo cáo.
    try:
        with open(DATA_DIR / "availability.csv", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        matched = [a for a in rows if a["room_id"] == room_id and a["date"] == booking_date and a["khung_code"] == khung_code]
        if matched:
            return matched[0]["availability_status"] == "AVAILABLE"
    except Exception:
        pass
    return True


def search_rooms(
    branch_id: str | None = None,
    guests: int = 2,
    booking_date: str = "",
    khung_code: str = "",
    budget_max: int | None = None,
    preferences: list[str] | None = None,
    keyword: str | None = None,
    room_name: str | None = None,
    room_types: list[str] | None = None,
    min_price: int | None = None,
    sort_by: str = "popularity",
    area_range: str | None = None,
    bed_types: list[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    target_slot_group = None
    clean_khung_code = (khung_code or "").strip()
    if clean_khung_code and "_" in clean_khung_code:
        parts = clean_khung_code.split("_", 1)
        clean_khung_code = parts[0]
        target_slot_group = parts[1]

    # Tận dụng engine V3 để lọc dataset PoC nếu ngày nằm trong bộ dữ liệu; nếu ngày mới,
    # thực hiện cùng quy tắc cứng trên rooms/prices + booking runtime để website vẫn dùng được.
    ctx = {
        "branch_id": branch_id or None,
        "guests": guests,
        "date": booking_date,
        "khung_code": clean_khung_code if clean_khung_code else None,
        "budget_max": budget_max or None,
        "preferences": preferences or []
    }
    candidates, trace = recommend_candidates(ctx, max_candidates=24)
    if not candidates and booking_date > "2026-08-31":
        rooms, _, prices, slot_time, _ = load_data()
        pmap = {(p["room_id"], p["khung_code"]): p["base_price"] for p in prices}
        result = []
        for r in rooms:
            if branch_id and r["branch_id"] != branch_id: continue
            if int(r["capacity"]) < int(guests): continue
            if clean_khung_code and not is_demo_available(r["room_id"], booking_date, clean_khung_code): continue
            price = pmap.get((r["room_id"], clean_khung_code)) if clean_khung_code else min((p["base_price"] for p in prices if p["room_id"] == r["room_id"]), default=140000)
            if budget_max and price and price > int(budget_max): continue
            t = resolve_khung_time(slot_time, r["slot_group_id"], clean_khung_code) if clean_khung_code else None
            result.append({
                "room_id": r["room_id"], "room_name": r["room_name"],
                "branch_id": r.get("branch_id") or ("BT" if "BT" in r["room_id"] else "TD" if "TD" in r["room_id"] else "PMH"),
                "branch_name": r["branch_name"],
                "room_type": r["room_type"], "capacity": r["capacity"], "concept": r["concept"],
                "concept_name": r["concept_name"], "amenities": r["amenities"],
                "area": r.get("area", 22), "bed_type": r.get("bed_type", "1 giường đôi"),
                "slot_group_id": r["slot_group_id"],
                "khung_code": clean_khung_code,
                "start_time": t[0] if t else None, "end_time": t[1] if t else None, "price": price,
            })
        prefs = [p.lower() for p in (preferences or []) if p.strip()]
        if prefs:
            def score(c):
                room = get_room(c["room_id"])
                hay = " ".join(room["amenities"] + [room["concept_name"], room["description"]]).lower()
                return sum(p in hay for p in prefs)
            result.sort(key=score, reverse=True)
        candidates = result
        trace = {"total_rooms": 24, "returned": len(result), "runtime_mode": "dynamic_demo"}

    # Gán thông tin nhóm và toàn bộ 4 khung giờ cho từng phòng để UI luôn hiển thị đầy đủ
    for c in candidates:
        r_info = get_room(c["room_id"]) or {}
        sg = get_room_slot_group(c["room_id"], c.get("slot_group_id", "N1"))
        c["slot_group_id"] = sg
        c["slots"] = slot_info_for_room(c["room_id"])
        c["area"] = int(r_info.get("area") or c.get("area") or 22)
        c["bed_type"] = str(r_info.get("bed_type") or c.get("bed_type") or "1 giường đôi")
        if not c.get("price"):
            c["price"] = min((s["price"] for s in c["slots"] if s.get("price")), default=140000)

    # Thu hẹp kết quả nếu người dùng lọc theo nhóm khung giờ cụ thể (VD: N1, N2, N3, N4)
    if target_slot_group:
        candidates = [c for c in candidates if c.get("slot_group_id") == target_slot_group]

    # 1. Lọc theo tên phòng đầy đủ / cụ thể (Full name search: VD: Standard BT01, Deluxe TD05, BT-STD-01)
    if room_name and room_name.strip():
        name_q = _norm(room_name.strip())
        candidates = [
            c for c in candidates
            if name_q in _norm(c.get("room_name", "")) or name_q in _norm(c.get("room_id", ""))
        ]

    # 2. Lọc theo loại phòng (Room Types: Standard, Deluxe, Family)
    if room_types and len(room_types) > 0:
        valid_types = {t.strip().lower() for t in room_types if t.strip()}
        if valid_types:
            candidates = [c for c in candidates if str(c.get("room_type", "")).lower() in valid_types]

    # 3. Lọc theo khoảng giá tối thiểu và tối đa (Min/Max price)
    if min_price and int(min_price) > 0:
        candidates = [c for c in candidates if c.get("price") and int(c["price"]) >= int(min_price)]
    if budget_max and int(budget_max) > 0:
        candidates = [c for c in candidates if c.get("price") and int(c["price"]) <= int(budget_max)]

    # 4. Lọc theo diện tích phòng (area_range: small <25m2, medium 25-35m2, large >35m2)
    if area_range and area_range.strip():
        ar = area_range.strip().lower()
        if ar == "small":
            candidates = [c for c in candidates if int(c.get("area", 22)) < 25]
        elif ar == "medium":
            candidates = [c for c in candidates if 25 <= int(c.get("area", 22)) <= 35]
        elif ar == "large":
            candidates = [c for c in candidates if int(c.get("area", 22)) > 35]

    # 5. Lọc theo loại giường ngủ (bed_types)
    if bed_types and len(bed_types) > 0:
        norm_beds = [_norm(b) for b in bed_types if b.strip()]
        if norm_beds:
            candidates = [
                c for c in candidates
                if any(nb in _norm(str(c.get("bed_type", ""))) for nb in norm_beds)
            ]

    # 4. Lọc theo tiện nghi nổi bật (Amenities / Preferences: bồn tắm, ban công, view hồ, minibar, bếp mini, wifi,...)
    if preferences and len(preferences) > 0:
        valid_prefs = [_norm(p) for p in preferences if p.strip()]
        if valid_prefs:
            filtered = []
            for c in candidates:
                room = get_room(c["room_id"]) or {}
                raw_amenities = (c.get("amenities") or []) + (room.get("amenities") or [])
                raw_searchables = (
                    raw_amenities
                    + [c.get("room_type", ""), c.get("concept_name", ""), c.get("concept", ""), c.get("room_name", ""), room.get("description", "")]
                )
                norm_searchables = [_norm(str(a)) for a in raw_searchables if a]
                
                def has_amenity(pref: str) -> bool:
                    pref_norm = _norm(pref)
                    # Tiện nghi tiêu chuẩn mặc định có trong 100% phòng của chuỗi CozyHome (phòng tắm riêng, điều hòa, wifi, minibar, bàn làm việc, máy sấy, nước nóng...)
                    if pref_norm in STANDARD_AMENITIES or any(s_am in pref_norm or pref_norm in s_am for s_am in STANDARD_AMENITIES):
                        return True
                    return any(pref_norm in s or s in pref_norm for s in norm_searchables)

                if all(has_amenity(p) for p in valid_prefs):
                    filtered.append(c)
            candidates = filtered

    # 4. Lọc theo từ khóa đa năng (Keyword search: tên phòng, concept, chi nhánh, tiện ích, mô tả)
    if keyword and keyword.strip():
        norm_kw = _norm(keyword.strip())
        tokens = norm_kw.split()
        filtered = []
        for c in candidates:
            room = get_room(c["room_id"]) or {}
            searchable_raw = " ".join([
                str(c.get("room_id", "")),
                str(c.get("room_name", "")),
                str(c.get("branch_name", "")),
                str(c.get("concept_name", "")),
                str(c.get("concept", "")),
                str(c.get("room_type", "")),
                str(room.get("description", "")),
                " ".join(c.get("amenities") or [])
            ])
            searchable_text = _norm(searchable_raw)
            # Khớp nếu cả cụm từ xuất hiện HOẶC tất cả các từ đơn lẻ xuất hiện dưới dạng nguyên từ (\btoken\b)
            if norm_kw in searchable_text or all(re.search(rf"\b{re.escape(tok)}\b", searchable_text) for tok in tokens):
                filtered.append(c)
        candidates = filtered
        trace["keyword"] = keyword

    # 5. Sắp xếp kết quả (Sorting)
    if sort_by == "price_asc":
        candidates.sort(key=lambda x: int(x.get("price") or 0))
    elif sort_by == "price_desc":
        candidates.sort(key=lambda x: int(x.get("price") or 0), reverse=True)
    elif sort_by == "capacity_desc":
        candidates.sort(key=lambda x: int(x.get("capacity") or 0), reverse=True)
    elif sort_by == "name_asc":
        candidates.sort(key=lambda x: _norm(str(x.get("room_name") or "")))

    trace["returned"] = len(candidates)
    return candidates, trace


def get_search_fallback(
    branch_id: str | None = None,
    guests: int = 2,
    booking_date: str = "",
    khung_code: str = "",
    budget_max: int | None = None,
    preferences: list[str] | None = None,
    keyword: str | None = None,
    room_types: list[str] | None = None,
    min_price: int | None = None,
) -> dict[str, Any] | None:
    """
    Phân tích nguyên nhân khi kết quả tìm kiếm rỗng (0 phòng)
    và đưa ra gợi ý hành động 1-chạm (Actionable Fallback Suggestion).
    """
    # 1. Thử nghiệm tìm kiếm nới lỏng chi nhánh nếu đang chọn 1 chi nhánh cụ thể
    if branch_id:
        all_alt_rooms, _ = search_rooms(
            branch_id=None,
            guests=guests,
            booking_date=booking_date,
            khung_code=khung_code,
            budget_max=budget_max,
            preferences=preferences,
            keyword=keyword,
            room_types=room_types,
            min_price=min_price,
        )
        # Chỉ lấy các phòng thuộc chi nhánh KHÁC chi nhánh hiện tại
        diff_branch_rooms = [r for r in all_alt_rooms if r.get("branch_id") and r.get("branch_id") != branch_id]
        if diff_branch_rooms:
            best_alt = diff_branch_rooms[0]
            alt_branch_id = best_alt.get("branch_id")
            alt_branch_name = BRANCHES.get(alt_branch_id, best_alt.get("branch_name"))
            cur_branch_name = BRANCHES.get(branch_id, "chi nhánh đã chọn")
            
            target_rooms = [r for r in diff_branch_rooms if r.get("branch_id") == alt_branch_id]
            pref_str = f"từ khóa '{keyword}'" if keyword else (", ".join(preferences) if preferences else "yêu cầu")
            return {
                "type": "branch_switch",
                "title": f"Gợi ý phòng tại {alt_branch_name}",
                "message": f"Tại {cur_branch_name} hiện không có phòng thỏa mãn {pref_str}. CozyHome gợi ý bạn các phòng phù hợp tại {alt_branch_name}:",
                "action_label": f"Xem phòng tại {alt_branch_name}",
                "target_branch_id": alt_branch_id,
                "target_branch_name": alt_branch_name,
                "cur_branch_name": cur_branch_name,
                "keyword": keyword,
                "sample_rooms": target_rooms[:3],
            }

    # 2. Thử nghiệm nới lỏng tiện nghi (bỏ preferences) nếu có chọn preferences
    if preferences and len(preferences) > 0:
        relax_pref_rooms, _ = search_rooms(
            branch_id=branch_id,
            guests=guests,
            booking_date=booking_date,
            khung_code=khung_code,
            budget_max=budget_max,
            preferences=None,
            keyword=keyword,
            room_types=room_types,
            min_price=min_price,
        )
        if relax_pref_rooms:
            cur_branch_name = BRANCHES.get(branch_id, "chi nhánh") if branch_id else "CozyHome"
            return {
                "type": "relax_amenity",
                "title": f"Không có phòng đủ tiện nghi đã chọn",
                "message": f"Không tìm thấy phòng có đủ các tiện nghi ({', '.join(preferences)}). Bạn có thể bỏ bớt tiêu chí tiện nghi để xem {len(relax_pref_rooms)} phòng sẵn sàng tại {cur_branch_name}:",
                "action_label": "Bỏ chọn tiện nghi",
                "sample_rooms": relax_pref_rooms[:3],
            }

    # 3. Thử nghiệm nới lỏng khung giờ nếu có chọn khung giờ cụ thể
    if khung_code:
        relax_slot_rooms, _ = search_rooms(
            branch_id=branch_id,
            guests=guests,
            booking_date=booking_date,
            khung_code="",
            budget_max=budget_max,
            preferences=preferences,
            keyword=keyword,
            room_types=room_types,
            min_price=min_price,
        )
        if relax_slot_rooms:
            return {
                "type": "relax_slot",
                "title": "Khung giờ này đã kín phòng",
                "message": f"Khung giờ bạn chọn vào ngày {booking_date} đã kín. Hãy xem các khung giờ còn trống khác trong ngày:",
                "action_label": "Xem tất cả khung giờ",
                "sample_rooms": relax_slot_rooms[:3],
            }

    # 4. Thử nghiệm nới lỏng khoảng giá nếu đang lọc giá
    if budget_max or min_price:
        relax_price_rooms, _ = search_rooms(
            branch_id=branch_id,
            guests=guests,
            booking_date=booking_date,
            khung_code=khung_code,
            budget_max=None,
            preferences=preferences,
            keyword=keyword,
            room_types=room_types,
            min_price=None,
        )
        if relax_price_rooms:
            return {
                "type": "relax_price",
                "title": "Khoảng giá chưa phù hợp",
                "message": "Không có phòng trong tầm giá đã chọn. Thử mở rộng khoảng giá để xem các phòng phù hợp:",
                "action_label": "Xóa bộ lọc giá",
                "sample_rooms": relax_price_rooms[:3],
            }

    return None


def check_extension_availability(
    room_id: str,
    current_date: str,
    current_khung: str,
    current_end_time: str | None = None,
    hours: int = 1,
    booking_code: str | None = None,
) -> dict[str, Any]:
    """
    Kiểm tra tính khả dụng và thông tin khung kế tiếp để gia hạn thêm giờ theo BR-06 & Nghiệp vụ gia hạn theo giờ.
    Quy tắc:
    - Khách hàng có thể gia hạn theo số giờ (1 tiếng, 2 tiếng, 3 tiếng...).
    - Hệ thống tính toán giờ check-out mới. Nếu chạm vào hoặc lấn sang khung tiếp theo:
      kiểm tra tính khả dụng của khung tiếp theo trên lịch phòng.
    - Nếu trống: Cho phép gia hạn, khóa khung tiếp theo trên lịch chung.
    - Nếu không trống: Từ chối gia hạn và nêu rõ lý do.
    """
    # Nếu có mã đơn đặt phòng, tự động giải quyết khung giờ và ngày thực tế khách đang ở từ lượt gia hạn gần nhất
    if booking_code:
        try:
            from services.storage import connect
            with connect() as conn:
                last_ext = conn.execute(
                    "SELECT * FROM booking_extensions WHERE booking_code=? ORDER BY id DESC LIMIT 1",
                    (booking_code,)
                ).fetchone()
                if last_ext:
                    current_khung = last_ext["khung_code"]
                    current_date = last_ext["extension_date"]
                    if not current_end_time:
                        current_end_time = last_ext["end_time"]
        except Exception:
            pass

    slots = slot_info_for_room(room_id)
    curr_slot = next((s for s in slots if s["khung_code"] == current_khung), None)
    if not curr_slot or not curr_slot.get("next_slot"):
        return {"can_extend": False, "is_available": False, "reason": "Không xác định được khung giờ tiếp theo."}

    next_khung = curr_slot["next_slot"]
    next_slot_info = next((s for s in slots if s["khung_code"] == next_khung), None)
    if not next_slot_info:
        return {"can_extend": False, "is_available": False, "reason": "Không tìm thấy thông tin khung kế tiếp."}

    next_date = current_date
    if current_khung == "QD" and next_khung == "K1":
        next_date = (date.fromisoformat(current_date) + timedelta(days=1)).isoformat()

    # Tính toán giờ kết thúc mới
    curr_end = (current_end_time or curr_slot["end_time"]).replace("+1", "").strip()
    try:
        curr_h, curr_m = map(int, curr_end.split(":"))
    except Exception:
        curr_h, curr_m = 12, 0

    tot_minutes = curr_h * 60 + curr_m + max(1, hours) * 60
    new_h = (tot_minutes // 60) % 24
    new_m = tot_minutes % 60
    new_end_time = f"{new_h:02d}:{new_m:02d}"

    # Kiểm tra khung kế tiếp trên lịch chung (loại trừ chính mã đơn để không tự chặn mình)
    is_available = is_demo_available(room_id, next_date, next_khung, exclude_booking_code=booking_code)

    # Đơn giá gia hạn theo quy định tại Phụ lục 14: 50.000 đ/giờ/phòng
    next_price = next_slot_info["price"] or 150000
    hourly_rate = 50000
    current_fee = min(hourly_rate * hours, next_price) if hours <= 3 else hourly_rate * hours

    # Danh sách các tùy chọn mặc định: 1 tiếng, 2 tiếng, 3 tiếng
    hourly_options = []
    for h in (1, 2, 3):
        h_tot_m = curr_h * 60 + curr_m + h * 60
        h_end = f"{(h_tot_m // 60) % 24:02d}:{h_tot_m % 60:02d}"
        h_fee = min(hourly_rate * h, next_price) if h <= 3 else hourly_rate * h
        hourly_options.append({
            "hours": h,
            "label": f"{h} tiếng",
            "end_time": h_end,
            "amount": h_fee,
            "is_available": is_available,
            "reason": None if is_available else f"Khung {SLOT_NAMES.get(next_khung, next_khung)} không khả dụng.",
        })

    next_khung_label = SLOT_NAMES.get(next_khung, next_khung)
    reason = None
    if not is_available:
        reason = f"Khung kế tiếp {next_khung_label} ({next_slot_info['start_time']}–{next_slot_info['end_time']}) ngày {next_date} đã có lượt đặt trước hoặc không khả dụng. Không thể gia hạn."

    return {
        "can_extend": is_available,
        "is_available": is_available,
        "room_id": room_id,
        "current_khung": current_khung,
        "current_end_time": curr_end,
        "hours": hours,
        "new_end_time": new_end_time,
        "next_khung": next_khung,
        "next_khung_name": next_khung_label,
        "next_date": next_date,
        "start_time": next_slot_info["start_time"],
        "end_time": new_end_time,
        "next_slot_end": next_slot_info["end_time"],
        "price": current_fee,
        "hourly_rate": hourly_rate,
        "next_slot_price": next_price,
        "hourly_options": hourly_options,
        "reason": reason,
    }


def availability_grid(room_id: str, days: int = 15) -> list[dict[str, Any]]:
    out = []
    for i in range(days):
        d = (date.today() + timedelta(days=i)).isoformat()
        row = {"date": d}
        for code in ("K1", "K2", "K3", "QD"):
            row[code] = is_demo_available(room_id, d, code)
        out.append(row)
    return out


def list_promotions() -> list[dict[str, Any]]:
    promos = []
    try:
        with open(DATA_DIR / "promotions.csv", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                promos.append({
                    "promo_id": r.get("promo_id", ""),
                    "code": (r.get("code") or r.get("promo_id", "")).upper().strip(),
                    "name": r.get("name", ""),
                    "description": r.get("description", ""),
                    "discount_percent": int(r.get("discount_percent") or 0),
                    "discount_value": int(r.get("discount_value") or 0),
                    "condition": r.get("condition", ""),
                    "badge": r.get("badge", "Ưu đãi"),
                    "branch_id": r.get("branch_id", "ALL"),
                    "effective_from": r.get("effective_from", ""),
                    "effective_to": r.get("effective_to", ""),
                    "active": str(r.get("active", "1")).strip().lower() in ("1", "true", "yes"),
                })
    except Exception:
        pass
    return promos


def validate_promotion(
    code: str,
    room_id: str,
    booking_date: str,
    khung_code: str,
    original_amount: int,
    user_id: int | None = None
) -> dict[str, Any]:
    """
    Xác thực mã khuyến mãi dựa trên quy chuẩn điều kiện (BR):
    - Khớp mã voucher
    - Hạn sử dụng & trạng thái hiệu lực (active)
    - Đặt trước >= 7 ngày (PR-01)
    - Khung qua đêm giữa tuần (PR-02)
    - Giờ vàng sáng K1 (PR-04)
    - Thành viên (PR-03)
    """
    clean_code = (code or "").upper().strip()
    if not clean_code:
        return {"valid": False, "message": "Vui lòng nhập mã khuyến mãi."}

    all_p = list_promotions()
    matched = next((p for p in all_p if p["code"] == clean_code or p["promo_id"] == clean_code), None)
    if not matched:
        return {"valid": False, "message": f"Mã khuyến mãi '{clean_code}' không tồn tại hoặc đã hết hạn."}

    if not matched.get("active", True):
        return {"valid": False, "message": f"Chương trình khuyến mãi '{matched['name']}' hiện đang tạm ngừng áp dụng."}

    today = date.today()
    today_str = today.isoformat()

    # 1. Kiểm tra thời hạn hiệu lực của chương trình
    if matched["effective_from"] and today_str < matched["effective_from"]:
        return {"valid": False, "message": f"Chương trình '{matched['name']}' chưa bắt đầu."}
    if matched["effective_to"] and today_str > matched["effective_to"]:
        return {"valid": False, "message": f"Chương trình '{matched['name']}' đã kết thúc vào ngày {matched['effective_to']}."}

    # 2. Kiểm tra chi nhánh
    if matched["branch_id"] != "ALL" and room_id:
        room = get_room(room_id)
        if room and room.get("branch_id") != matched["branch_id"]:
            return {"valid": False, "message": f"Ưu đãi này chỉ áp dụng tại chi nhánh {matched['branch_id']}."}

    # 3. Kiểm tra điều kiện đặt trước (PR-01)
    cond = matched["condition"]
    if "advance_days>=7" in cond and booking_date:
        try:
            b_date = date.fromisoformat(booking_date)
            diff_days = (b_date - today).days
            if diff_days < 7:
                return {
                    "valid": False,
                    "message": f"Ưu đãi Đặt sớm ({matched['code']}) yêu cầu đặt trước ngày nhận phòng ít nhất 7 ngày (hiện tại cách {max(0, diff_days)} ngày)."
                }
        except ValueError:
            pass

    # 4. Kiểm tra điều kiện qua đêm giữa tuần (PR-02)
    if "khung_code=QD" in cond:
        if khung_code != "QD":
            return {
                "valid": False,
                "message": f"Ưu đãi ({matched['code']}) chỉ áp dụng cho khung lưu trú Qua đêm (20:00 – 08:30)."
            }
        if ("midweek=true" in cond or "weekday" in cond) and booking_date:
            try:
                b_date = date.fromisoformat(booking_date)
                # 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
                weekday = b_date.weekday()
                if weekday in (4, 5):
                    day_names = {4: "Thứ 6", 5: "Thứ 7"}
                    return {
                        "valid": False,
                        "message": f"Ưu đãi qua đêm giữa tuần chỉ áp dụng từ Chủ nhật đến Thứ 5 (ngày {booking_date} là {day_names.get(weekday)})."
                    }
            except ValueError:
                pass

    # 5. Kiểm tra điều kiện khung giờ sáng K1 (PR-04)
    if "khung_code=K1" in cond and khung_code != "K1":
        return {
            "valid": False,
            "message": f"Ưu đãi Giờ vàng ({matched['code']}) chỉ áp dụng cho khung sáng K1 (09:30 – 12:30)."
        }

    # Tính toán số tiền chiết khấu
    discount = 0
    if matched["discount_percent"] > 0:
        discount = int(original_amount * matched["discount_percent"] / 100)
    elif matched["discount_value"] > 0:
        discount = matched["discount_value"]

    discount = min(discount, original_amount)
    final_amount = max(0, original_amount - discount)

    return {
        "valid": True,
        "promo": matched,
        "discount_amount": discount,
        "final_amount": final_amount,
        "message": f"Áp dụng thành công ưu đãi {matched['name']}! Giảm {discount:,.0f} ₫.".replace(",", ".")
    }


def promotion_text() -> list[str]:
    promos = list_promotions()
    return [f"{p['name']} ({p['code']}): {p['description']}" for p in promos] or ["Ưu đãi theo chính sách CozyHome"]


# -------------------------------------------------------------
# Dữ liệu phục vụ Trợ lý Tư vấn CozyHome (AI Chatbot)
# -------------------------------------------------------------

BRANCH_DETAILS: dict[str, dict[str, Any]] = {
    "BT": {
        "id": "BT",
        "name": "CozyHome Bến Thành",
        "address": "123 Lê Thánh Tôn, Phường Bến Thành, Quận 1, TP. Hồ Chí Minh",
        "district": "Quận 1",
        "concept": "Đô thị và văn hóa quốc tế",
        "concept_name": "Đô thị năng động",
        "phone": "0909 000 001",
        "room_count": 8,
        "features": ["Gần chợ Bến Thành", "Phố đi bộ Nguyễn Huệ", "Trung tâm ẩm thực"],
    },
    "TD": {
        "id": "TD",
        "name": "CozyHome Thảo Điền",
        "address": "45 Xuân Thủy, Phường Thảo Điền, TP. Thủ Đức, TP. Hồ Chí Minh",
        "district": "TP. Thủ Đức (Quận 2 cũ)",
        "concept": "Cao nguyên và thiên nhiên",
        "concept_name": "Xanh mát thiên nhiên",
        "phone": "0909 000 002",
        "room_count": 8,
        "features": ["Không gian xanh yên tĩnh", "Nhiều quán cafe sân vườn", "View sông thoáng mát"],
    },
    "PMH": {
        "id": "PMH",
        "name": "CozyHome Phú Mỹ Hưng",
        "address": "88 Nguyễn Đức Cảnh, Phường Tân Phong, Quận 7, TP. Hồ Chí Minh",
        "district": "Quận 7",
        "concept": "Nhiệt đới và sông nước Nam Bộ",
        "concept_name": "Nhiệt đới thư giãn",
        "phone": "0909 000 003",
        "room_count": 8,
        "features": ["Hồ Bán Nguyệt", "Cầu Ánh Sao", "Không gian nghỉ dưỡng hiện đại"],
    },
}


def get_branch_details(branch_id: str | None = None) -> list[dict[str, Any]]:
    if branch_id and branch_id.upper() in BRANCH_DETAILS:
        return [BRANCH_DETAILS[branch_id.upper()]]
    return list(BRANCH_DETAILS.values())


def calculate_cancellation_refund(booking: dict[str, Any], cancel_dt: datetime | None = None) -> dict[str, Any]:
    """Tính toán tỷ lệ và số tiền hoàn tiền khi hủy đặt phòng theo quy định Phụ lục 5 (Đồ án CozyHome).
    
    Quy định tại Phụ lục 5 (Mục 6):
    - Từ 24 giờ trở lên trước thời điểm bắt đầu lưu trú: Hoàn lại 100% số tiền thực trả cho phần giá phòng đủ điều kiện hoàn.
    - Từ 12 giờ đến dưới 24 giờ trước thời điểm bắt đầu lưu trú: Hoàn lại 50% tiền phòng.
    - Dưới 12 giờ trước thời điểm bắt đầu lưu trú: Không áp dụng hoàn tiền (0%).
    - Không đến nhận phòng (No-show) hoặc sau thời điểm bắt đầu lưu trú: Không áp dụng hoàn tiền (0%).
    - Thời gian xử lý hoàn tiền: Từ 3 đến 15 ngày làm việc sau khi đối soát kế toán.
    """
    if cancel_dt is None:
        cancel_dt = datetime.now()

    b_date_str = str(booking.get("booking_date") or "").strip()
    start_time_str = str(booking.get("start_time") or "00:00").strip()
    amount = int(booking.get("amount") or 0)

    try:
        time_part = start_time_str.split("-")[0].strip().replace("+1", "")
        if ":" in time_part:
            hh, mm = [int(x) for x in time_part.split(":")[:2]]
        else:
            hh, mm = 0, 0
        if "T" in b_date_str:
            base_date = datetime.fromisoformat(b_date_str).date()
        else:
            base_date = datetime.strptime(b_date_str, "%Y-%m-%d").date()
        checkin_dt = datetime.combine(base_date, datetime.min.time()).replace(hour=hh, minute=mm)
    except Exception:
        try:
            checkin_dt = datetime.fromisoformat(b_date_str)
        except Exception:
            checkin_dt = cancel_dt

    diff_seconds = (checkin_dt - cancel_dt).total_seconds()
    hours_left = diff_seconds / 3600.0

    if hours_left >= 24.0:
        rate = 1.0
        rate_str = "100%"
        tier = "Từ 24 giờ trở lên"
        desc = "Hủy trước thời điểm bắt đầu lưu trú từ 24 giờ trở lên: Được hoàn lại 100% số tiền đã thanh toán."
    elif 12.0 <= hours_left < 24.0:
        rate = 0.5
        rate_str = "50%"
        tier = "Từ 12 giờ đến dưới 24 giờ"
        desc = "Hủy trước thời điểm bắt đầu lưu trú từ 12 giờ đến dưới 24 giờ: Được hoàn lại 50% tiền phòng."
    elif 0 <= hours_left < 12.0:
        rate = 0.0
        rate_str = "0%"
        tier = "Dưới 12 giờ"
        desc = "Hủy dưới 12 giờ trước thời điểm bắt đầu lưu trú: Không áp dụng hoàn tiền theo quy định."
    else:
        rate = 0.0
        rate_str = "0%"
        tier = "Sau giờ nhận phòng / No-show"
        desc = "Đã quá thời điểm bắt đầu lưu trú hoặc không đến nhận phòng: Không áp dụng hoàn tiền."
    payment_status = str(booking.get("payment_status") or "").strip()
    is_paid = payment_status == "Đã thanh toán"
    if payment_status and not is_paid:
        refund_amount = 0
        desc = "Lượt đặt chưa thanh toán, không phát sinh giao dịch hoàn tiền."
    else:
        refund_amount = int(round(amount * rate))

    return {
        "hours_left": round(hours_left, 1),
        "refund_rate": rate_str,
        "refund_rate_float": rate,
        "refund_amount": refund_amount,
        "original_amount": amount,
        "is_paid": is_paid if payment_status else True,
        "tier": tier,
        "description": desc,
        "time_estimate": "Từ 3 đến 15 ngày làm việc (qua phương thức thanh toán ban đầu sau khi đối soát)",
    }


def get_cancellation_policy() -> dict[str, Any]:
    return {
        "rule_code": "cancellation_policy",
        "title": "Chính sách Hủy đặt phòng và Hoàn tiền CozyHome",
        "summary": "Từ 24h trở lên hoàn 100%; Từ 12h đến dưới 24h hoàn 50%; Dưới 12h hoặc sau check-in không áp dụng hoàn tiền.",
        "details": [
            "Khách hàng có thể gửi yêu cầu hủy trước thời điểm bắt đầu lưu trú trên website.",
            "Từ 24 giờ trở lên trước thời điểm lưu trú: Hoàn lại 100% số tiền thực trả cho phần giá phòng đủ điều kiện hoàn.",
            "Từ 12 giờ đến dưới 24 giờ trước thời điểm lưu trú: Hoàn lại 50% tiền phòng.",
            "Dưới 12 giờ trước thời điểm lưu trú: Không hoàn tiền (0%).",
            "Không đến nhận phòng (No-show) hoặc hủy sau thời điểm bắt đầu lưu trú: Không áp dụng hoàn tiền.",
            "Mức hoàn áp dụng thống nhất cho đặt phòng theo giờ và qua đêm, không phân biệt ngày thường, cuối tuần hay ngày lễ.",
            "Cách thực hiện: Đăng nhập -> Vào 'Lượt đặt của tôi' -> Chọn đơn phòng -> Nhấn 'Xác nhận hủy đặt phòng'.",
            "Lưu ý: Trợ lý AI không có quyền hủy đơn phòng trực tiếp thay cho khách để bảo mật giao dịch (BR-13).",
        ],
        "action_guide": "Mở mục 'Lượt đặt của tôi' để kiểm tra số tiền hoàn dự kiến và thao tác hủy an toàn.",
    }


def get_refund_policy() -> dict[str, Any]:
    return {
        "rule_code": "refund_policy",
        "title": "Chính sách Hoàn tiền CozyHome",
        "summary": "Khoản hoàn tiền được kế toán đối soát và chuyển trả về tài khoản ban đầu trong từ 3 đến 15 ngày làm việc.",
        "details": [
            "Điều kiện hoàn tiền: Áp dụng khi lượt đặt phòng được hủy hợp lệ trước giờ bắt đầu lưu trú từ 12 giờ trở lên (hoàn 100% nếu >= 24h, hoàn 50% nếu từ 12h đến dưới 24h).",
            "Thời gian xử lý: Từ 3 đến 15 ngày làm việc phụ thuộc vào quy trình đối soát kế toán và ngân hàng / cổng thanh toán (VietQR MBBank).",
            "Phương thức hoàn tiền: Tiền được gửi về đúng phương thức thanh toán ban đầu mà quý khách đã sử dụng khi xác nhận đặt phòng.",
            "Minh bạch giao dịch: Mọi giao dịch hoàn tiền đều được gắn mã đơn và đưa vào danh sách đối soát định kỳ của bộ phận kế toán.",
        ],
        "action_guide": "Sau khi hủy phòng thành công, giao dịch hoàn tiền sẽ ở trạng thái 'Chờ đối soát' và được giải ngân trong 3-15 ngày làm việc.",
    }


def get_stay_policy() -> dict[str, Any]:
    return {
        "rule_code": "stay_policy",
        "title": "Quy định và Chính sách Lưu trú CozyHome",
        "details": [
            "Hình thức lưu trú: Hỗ trợ cả 2 hình thức: Thuê theo khung 3 tiếng linh hoạt (K1, K2, K3) và Thuê qua đêm (QD).",
            "Vệ sinh buồng phòng: 100% phòng không hút thuốc (No Smoking). Quy trình khử khuẩn 100% được hoàn tất trước mỗi lượt khách nhận phòng.",
            "Gia hạn thêm giờ: Khách đang lưu trú có thể gia hạn sang khung kế tiếp của chính phòng đó nếu khung kế tiếp còn trống, không phát sinh phí vệ sinh nối tiếp.",
            "Sức chứa: Mỗi phòng có sức chứa quy định (Standard 2 khách, Deluxe 2–3 khách, Family tối đa 6 khách). Quý khách vui lòng không lưu trú vượt quá sức chứa.",
            "Thời gian giữ chỗ: Khi tạo đơn đặt phòng, hệ thống giữ chỗ trong 10 phút để quý khách quét mã VietQR MBBank hoàn tất thanh toán.",
        ],
    }


def find_room_by_query(q: str) -> dict[str, Any] | None:
    """Tìm phòng theo mã hoặc tên phòng (BT-STD-01, BT-103, Standard BT01, v.v.)."""
    if not q:
        return None
    raw = q.upper().strip()
    clean = _norm(q)
    rooms = all_rooms()

    # 1. Trực tiếp khớp room_id hoặc room_name chính xác
    for r in rooms:
        if r["room_id"].upper() == raw or _norm(r["room_name"]) == clean:
            return r

    # 2. Xử lý alias dạng BT-103 -> BT-STD-03 / BT-03
    alias_map = {
        "BT-101": "BT-STD-01", "BT101": "BT-STD-01", "BT-01": "BT-STD-01", "BT01": "BT-STD-01",
        "BT-102": "BT-STD-02", "BT102": "BT-STD-02", "BT-02": "BT-STD-02", "BT02": "BT-STD-02",
        "BT-103": "BT-STD-03", "BT103": "BT-STD-03", "BT-03": "BT-STD-03", "BT03": "BT-STD-03",
        "BT-104": "BT-STD-04", "BT104": "BT-STD-04", "BT-04": "BT-STD-04", "BT04": "BT-STD-04",
        "BT-105": "BT-DL-01", "BT105": "BT-DL-01", "BT-05": "BT-DL-01", "BT05": "BT-DL-01",
        "BT-106": "BT-DL-02", "BT106": "BT-DL-02", "BT-06": "BT-DL-02", "BT06": "BT-DL-02",
        "BT-107": "BT-DL-03", "BT107": "BT-DL-03", "BT-07": "BT-DL-03", "BT07": "BT-DL-03",
        "BT-108": "BT-FAM-01", "BT108": "BT-FAM-01", "BT-08": "BT-FAM-01", "BT08": "BT-FAM-01",
        "TD-101": "TD-STD-01", "TD101": "TD-STD-01", "TD-01": "TD-STD-01", "TD01": "TD-STD-01",
        "TD-102": "TD-STD-02", "TD102": "TD-STD-02", "TD-02": "TD-STD-02", "TD02": "TD-STD-02",
        "TD-103": "TD-STD-03", "TD103": "TD-STD-03", "TD-03": "TD-STD-03", "TD03": "TD-STD-03",
        "TD-104": "TD-STD-04", "TD104": "TD-STD-04", "TD-04": "TD-STD-04", "TD04": "TD-STD-04",
        "TD-105": "TD-DL-01", "TD105": "TD-DL-01", "TD-05": "TD-DL-01", "TD05": "TD-DL-01",
        "TD-106": "TD-DL-02", "TD106": "TD-DL-02", "TD-06": "TD-DL-02", "TD06": "TD-DL-02",
        "TD-107": "TD-DL-03", "TD107": "TD-DL-03", "TD-07": "TD-DL-03", "TD07": "TD-DL-03",
        "TD-108": "TD-FAM-01", "TD108": "TD-FAM-01", "TD-08": "TD-FAM-01", "TD08": "TD-FAM-01",
        "PMH-101": "PMH-STD-01", "PMH101": "PMH-STD-01", "PMH-01": "PMH-STD-01", "PMH01": "PMH-STD-01",
        "PMH-102": "PMH-STD-02", "PMH102": "PMH-STD-02", "PMH-02": "PMH-STD-02", "PMH02": "PMH-STD-02",
        "PMH-103": "PMH-STD-03", "PMH103": "PMH-STD-03", "PMH-03": "PMH-STD-03", "PMH03": "PMH-STD-03",
        "PMH-104": "PMH-STD-04", "PMH104": "PMH-STD-04", "PMH-04": "PMH-STD-04", "PMH04": "PMH-STD-04",
        "PMH-105": "PMH-DL-01", "PMH105": "PMH-DL-01", "PMH-05": "PMH-DL-01", "PMH05": "PMH-DL-01",
        "PMH-106": "PMH-DL-02", "PMH106": "PMH-DL-02", "PMH-06": "PMH-DL-02", "PMH06": "PMH-DL-02",
        "PMH-107": "PMH-DL-03", "PMH107": "PMH-DL-03", "PMH-07": "PMH-DL-03", "PMH07": "PMH-DL-03",
        "PMH-108": "PMH-FAM-01", "PMH108": "PMH-FAM-01", "PMH-08": "PMH-FAM-01", "PMH08": "PMH-FAM-01",
    }
    mapped_id = alias_map.get(raw.replace(" ", ""))
    if mapped_id:
        match = next((r for r in rooms if r["room_id"] == mapped_id), None)
        if match:
            return match

    # 3. Tìm tên phòng hoặc mã phòng nằm trong câu hỏi dài (VD: 'phòng Standard BT01 tại Bến Thành...')
    # Ưu tiên khớp tên phòng đầy đủ trước
    for r in sorted(rooms, key=lambda x: len(x["room_name"]), reverse=True):
        if _norm(r["room_name"]) in clean or _norm(r["room_id"]) in clean:
            return r

    # 4. Kiểm tra các alias trong câu dài
    for alias_key, target_id in sorted(alias_map.items(), key=lambda x: len(x[0]), reverse=True):
        alias_norm = _norm(alias_key)
        if re.search(r"\b" + re.escape(alias_norm) + r"\b", clean):
            match = next((r for r in rooms if r["room_id"] == target_id), None)
            if match:
                return match

    return None

    return None


# =============================================================================
# QUẢN LÝ DỊCH VỤ LƯU TRÚ (UC-03) VÀ CHÍNH SÁCH KINH DOANH (UC-04)
# =============================================================================

# 1. QUẢN LÝ KHUYẾN MÃI (UC-04.2, UC-04.3, UC-04.4)
def save_promotions(promos: list[dict[str, Any]]) -> None:
    """Lưu danh sách khuyến mãi vào data/promotions.csv"""
    fieldnames = [
        "promo_id", "code", "name", "description", "discount_percent",
        "discount_value", "condition", "badge", "branch_id",
        "effective_from", "effective_to", "active"
    ]
    with open(DATA_DIR / "promotions.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for p in promos:
            writer.writerow({
                "promo_id": p.get("promo_id", ""),
                "code": (p.get("code") or p.get("promo_id", "")).upper().strip(),
                "name": p.get("name", ""),
                "description": p.get("description", ""),
                "discount_percent": p.get("discount_percent", 0),
                "discount_value": p.get("discount_value", 0),
                "condition": p.get("condition", ""),
                "badge": p.get("badge", "Ưu đãi"),
                "branch_id": p.get("branch_id", "ALL"),
                "effective_from": p.get("effective_from", ""),
                "effective_to": p.get("effective_to", ""),
                "active": 1 if p.get("active", True) else 0,
            })


def add_promotion(promo: dict[str, Any]) -> dict[str, Any]:
    """UC-04.2: Thêm mới chương trình khuyến mãi"""
    promos = list_promotions()
    code = (promo.get("code") or "").upper().strip()
    if not code:
        raise ValueError("Mã khuyến mãi không được để trống.")
    if any(p["code"] == code for p in promos):
        raise ValueError(f"Mã khuyến mãi '{code}' đã tồn tại trong hệ thống.")

    promo_id = promo.get("promo_id") or f"PR-{len(promos) + 1:02d}"
    new_p = {
        "promo_id": promo_id,
        "code": code,
        "name": promo.get("name", "").strip() or f"Ưu đãi {code}",
        "description": promo.get("description", "").strip(),
        "discount_percent": int(promo.get("discount_percent") or 0),
        "discount_value": int(promo.get("discount_value") or 0),
        "condition": promo.get("condition", "").strip(),
        "badge": promo.get("badge", "").strip() or "Ưu đãi",
        "branch_id": promo.get("branch_id", "ALL"),
        "effective_from": promo.get("effective_from", ""),
        "effective_to": promo.get("effective_to", ""),
        "active": True,
    }
    promos.append(new_p)
    save_promotions(promos)
    return new_p


def update_promotion(promo_id_or_code: str, data: dict[str, Any]) -> dict[str, Any]:
    """UC-04.3: Cập nhật chương trình khuyến mãi"""
    promos = list_promotions()
    target_key = promo_id_or_code.upper().strip()
    found = False
    updated_p = None
    for p in promos:
        if p["code"] == target_key or p["promo_id"] == target_key:
            if "name" in data: p["name"] = data["name"].strip()
            if "description" in data: p["description"] = data["description"].strip()
            if "discount_percent" in data: p["discount_percent"] = int(data["discount_percent"])
            if "discount_value" in data: p["discount_value"] = int(data["discount_value"])
            if "condition" in data: p["condition"] = data["condition"].strip()
            if "badge" in data: p["badge"] = data["badge"].strip()
            if "branch_id" in data: p["branch_id"] = data["branch_id"]
            if "effective_from" in data: p["effective_from"] = data["effective_from"]
            if "effective_to" in data: p["effective_to"] = data["effective_to"]
            if "active" in data: p["active"] = bool(data["active"])
            updated_p = p
            found = True
            break
    if not found:
        raise ValueError(f"Không tìm thấy khuyến mãi '{promo_id_or_code}'.")
    save_promotions(promos)
    return updated_p


def toggle_promotion_status(promo_id_or_code: str) -> dict[str, Any]:
    """UC-04.4: Bật / Tắt trạng thái áp dụng khuyến mãi"""
    promos = list_promotions()
    target_key = promo_id_or_code.upper().strip()
    updated = None
    for p in promos:
        if p["code"] == target_key or p["promo_id"] == target_key:
            p["active"] = not p.get("active", True)
            updated = p
            break
    if not updated:
        raise ValueError(f"Không tìm thấy khuyến mãi '{promo_id_or_code}'.")
    save_promotions(promos)
    return updated


# 2. CẤU HÌNH GIÁ VÀ PHỤ THU (UC-04.1)
def get_pricing_policies() -> dict[str, Any]:
    """Đọc tệp cấu hình phụ thu data/pricing_policy.json"""
    policy_file = DATA_DIR / "pricing_policy.json"
    if not policy_file.exists():
        return {
            "weekend_surcharge": {"enabled": True, "percent": 10},
            "holiday_surcharge": {"enabled": True, "percent": 20},
            "extension_hourly_rate": 50000,
            "late_checkout_grace_minutes": 15,
            "late_checkout_hourly_rate": 50000,
            "extra_guest_fee": 50000,
        }
    with open(policy_file, encoding="utf-8") as f:
        return json.load(f)


def update_pricing_policies(new_data: dict[str, Any], updated_by: str = "Quản lý chuỗi") -> dict[str, Any]:
    """Cập nhật các mức phụ thu vào data/pricing_policy.json"""
    curr = get_pricing_policies()
    if "weekend_surcharge" in new_data:
        curr["weekend_surcharge"].update(new_data["weekend_surcharge"])
    if "holiday_surcharge" in new_data:
        curr["holiday_surcharge"].update(new_data["holiday_surcharge"])
    if "extension_hourly_rate" in new_data:
        curr["extension_hourly_rate"] = int(new_data["extension_hourly_rate"])
    if "late_checkout_grace_minutes" in new_data:
        curr["late_checkout_grace_minutes"] = int(new_data["late_checkout_grace_minutes"])
    if "late_checkout_hourly_rate" in new_data:
        curr["late_checkout_hourly_rate"] = int(new_data["late_checkout_hourly_rate"])
    if "extra_guest_fee" in new_data:
        curr["extra_guest_fee"] = int(new_data["extra_guest_fee"])
    curr["updated_at"] = datetime.now().isoformat()
    curr["updated_by"] = updated_by

    with open(DATA_DIR / "pricing_policy.json", "w", encoding="utf-8") as f:
        json.dump(curr, f, ensure_ascii=False, indent=2)
    return curr


def get_room_pricing_matrix() -> dict[str, Any]:
    """
    Tổng hợp ma trận giá phòng theo Hạng phòng x Chi nhánh x Khung giờ
    """
    prices_file = DATA_DIR / "prices.csv"
    with open(prices_file, encoding="utf-8") as f:
        price_rows = list(csv.DictReader(f))

    rooms = all_rooms()
    room_map = {r["room_id"]: r for r in rooms}

    # Bảng giá chuẩn theo hạng phòng (tính trung bình hoặc giá cơ sở đại diện)
    matrix: dict[str, dict[str, int]] = {
        "Standard": {"K1": 140000, "K2": 150000, "K3": 150000, "QD": 450000},
        "Deluxe":   {"K1": 190000, "K2": 200000, "K3": 200000, "QD": 600000},
        "Family":   {"K1": 290000, "K2": 300000, "K3": 300000, "QD": 900000},
    }

    # Cập nhật từ dữ liệu thực tế prices.csv
    for p in price_rows:
        r_info = room_map.get(p["room_id"])
        if r_info:
            r_type = r_info.get("room_type")
            code = p.get("khung_code")
            if r_type in matrix and code in matrix[r_type]:
                matrix[r_type][code] = int(p["base_price"])

    return {
        "standard_matrix": matrix,
        "policies": get_pricing_policies(),
        "total_rooms_priced": len(set(p["room_id"] for p in price_rows)),
    }


def update_base_price(room_type: str, branch_id: str, khung_code: str, new_price: int) -> int:
    """
    UC-04.1: Điều chỉnh giá cơ sở theo Hạng phòng, Chi nhánh và Khung giờ
    """
    prices_file = DATA_DIR / "prices.csv"
    with open(prices_file, encoding="utf-8") as f:
        price_rows = list(csv.DictReader(f))

    rooms = all_rooms()
    target_room_ids = {
        r["room_id"] for r in rooms
        if (not room_type or r["room_type"] == room_type) and
           (not branch_id or branch_id == "ALL" or r["branch_id"] == branch_id)
    }

    updated_count = 0
    today_str = date.today().isoformat()
    for row in price_rows:
        if row["room_id"] in target_room_ids and (not khung_code or row["khung_code"] == khung_code):
            row["base_price"] = str(new_price)
            row["effective_from"] = today_str
            updated_count += 1

    with open(prices_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["room_id", "slot_group_id", "khung_code", "khung_label", "base_price", "effective_from", "effective_to"])
        writer.writeheader()
        writer.writerows(price_rows)

    return updated_count


# 3. QUẢN LÝ DỊCH VỤ LƯU TRÚ - PHÒNG (UC-03.1, UC-03.2, UC-03.3)
def add_room(room_data: dict[str, Any]) -> dict[str, Any]:
    """
    UC-03.1: Thêm phòng mới vào hệ thống CozyHome
    """
    b_id = (room_data.get("branch_id") or "").upper().strip()
    if b_id not in BRANCHES:
        raise ValueError(f"Chi nhánh '{b_id}' không hợp lệ (hỗ trợ BT, TD, PMH).")

    r_id = (room_data.get("room_id") or "").upper().strip()
    if not r_id:
        raise ValueError("Mã phòng không được để trống.")

    rooms = all_rooms()
    if any(r["room_id"] == r_id for r in rooms):
        raise ValueError(f"Mã phòng '{r_id}' đã tồn tại trong hệ thống.")

    r_name = room_data.get("room_name") or r_id
    r_type = room_data.get("room_type") or "Standard"
    if r_type not in ("Standard", "Deluxe", "Family"):
        r_type = "Standard"

    sg_id = room_data.get("slot_group_id") or "N1"
    if sg_id not in ("N1", "N2", "N3", "N4"):
        sg_id = "N1"

    capacity = int(room_data.get("capacity") or 2)
    bed_type = room_data.get("bed_type") or "1 giường đôi"
    area = room_data.get("area") or 22
    concept = room_data.get("concept") or "Đô thị và văn hóa quốc tế"
    concept_name = room_data.get("concept_name") or "Hiện đại tiện nghi"
    description = room_data.get("description") or f"Phòng {r_name} phong cách {concept_name}."
    status = room_data.get("operational_status") or "Sẵn sàng"

    amenities_raw = room_data.get("amenities") or "wifi|máy lạnh|tivi|view thành phố"
    if isinstance(amenities_raw, list):
        amenities_str = "|".join(amenities_raw)
    else:
        amenities_str = str(amenities_raw)

    new_row = {
        "room_id": r_id,
        "room_name": r_name,
        "branch_id": b_id,
        "branch_name": BRANCHES.get(b_id, f"CozyHome {b_id}"),
        "room_type": r_type,
        "concept": concept,
        "concept_name": concept_name,
        "capacity": str(capacity),
        "bed_type": bed_type,
        "area": str(area),
        "amenities": amenities_str,
        "description": description,
        "slot_group_id": sg_id,
        "operational_status": status,
    }

    # 1. Ghi vào rooms.csv
    rooms_file = DATA_DIR / "rooms.csv"
    with open(rooms_file, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "room_id", "room_name", "branch_id", "branch_name", "room_type",
            "concept", "concept_name", "capacity", "bed_type", "area",
            "amenities", "description", "slot_group_id", "operational_status"
        ])
        writer.writerow(new_row)

    # 2. Tạo 4 khung giá tương ứng trong prices.csv
    prices_file = DATA_DIR / "prices.csv"
    default_prices = {
        "Standard": {"K1": 140000, "K2": 150000, "K3": 150000, "QD": 450000},
        "Deluxe":   {"K1": 190000, "K2": 200000, "K3": 200000, "QD": 600000},
        "Family":   {"K1": 290000, "K2": 300000, "K3": 300000, "QD": 900000},
    }.get(r_type, {"K1": 140000, "K2": 150000, "K3": 150000, "QD": 450000})

    khung_labels = {
        "K1": "Khung 1 (buổi sáng)",
        "K2": "Khung 2 (buổi trưa - chiều)",
        "K3": "Khung 3 (buổi chiều - tối)",
        "QD": "Khung qua đêm",
    }
    today_str = date.today().isoformat()
    with open(prices_file, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["room_id", "slot_group_id", "khung_code", "khung_label", "base_price", "effective_from", "effective_to"])
        for k_code in ("K1", "K2", "K3", "QD"):
            writer.writerow({
                "room_id": r_id,
                "slot_group_id": sg_id,
                "khung_code": k_code,
                "khung_label": khung_labels.get(k_code, k_code),
                "base_price": str(default_prices.get(k_code, 150000)),
                "effective_from": today_str,
                "effective_to": "",
            })

    # 3. Tạo khung khả dụng 14 ngày tới trong availability.csv
    avail_file = DATA_DIR / "availability.csv"
    curr_d = date.today()
    avail_rows = []
    for d_offset in range(14):
        target_date = (curr_d + timedelta(days=d_offset)).isoformat()
        for k_code in ("K1", "K2", "K3", "QD"):
            avail_rows.append({
                "room_id": r_id,
                "date": target_date,
                "slot_group_id": sg_id,
                "khung_code": k_code,
                "availability_status": "AVAILABLE"
            })
    with open(avail_file, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["room_id", "date", "slot_group_id", "khung_code", "availability_status"])
        writer.writerows(avail_rows)

    # 4. Gán ảnh mặc định nếu có
    if room_data.get("image_url"):
        img_path = BASE_DIR / "static" / "images" / "rooms" / "room_images.json"
        try:
            imgs = json.loads(img_path.read_text(encoding="utf-8")) if img_path.exists() else {}
            imgs[r_id] = [room_data["image_url"]]
            img_path.write_text(json.dumps(imgs, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    return new_row


def update_room(room_id: str, room_data: dict[str, Any]) -> dict[str, Any]:
    """
    UC-03.2: Cập nhật thông tin phòng
    """
    rooms_file = DATA_DIR / "rooms.csv"
    with open(rooms_file, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    updated_row = None
    old_sg = None
    new_sg = room_data.get("slot_group_id")
    for r in rows:
        if r["room_id"] == room_id:
            old_sg = r["slot_group_id"]
            if "room_name" in room_data: r["room_name"] = room_data["room_name"].strip()
            if "room_type" in room_data: r["room_type"] = room_data["room_type"].strip()
            if "concept_name" in room_data: r["concept_name"] = room_data["concept_name"].strip()
            if "concept" in room_data: r["concept"] = room_data["concept"].strip()
            if "capacity" in room_data: r["capacity"] = str(room_data["capacity"])
            if "bed_type" in room_data: r["bed_type"] = str(room_data["bed_type"])
            if "area" in room_data: r["area"] = str(room_data["area"])
            if "description" in room_data: r["description"] = room_data["description"].strip()
            if "operational_status" in room_data: r["operational_status"] = room_data["operational_status"]
            if new_sg and new_sg in ("N1", "N2", "N3", "N4"):
                r["slot_group_id"] = new_sg
            if "amenities" in room_data:
                am = room_data["amenities"]
                r["amenities"] = "|".join(am) if isinstance(am, list) else str(am)
            updated_row = r
            break

    if not updated_row:
        raise ValueError(f"Không tìm thấy phòng '{room_id}'.")

    # Lưu lại rooms.csv
    with open(rooms_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "room_id", "room_name", "branch_id", "branch_name", "room_type",
            "concept", "concept_name", "capacity", "bed_type", "area",
            "amenities", "description", "slot_group_id", "operational_status"
        ])
        writer.writeheader()
        writer.writerows(rows)

    # Nếu đổi slot_group_id, cập nhật prices.csv và availability.csv để tránh lệch cấu trúc
    if new_sg and new_sg != old_sg:
        prices_file = DATA_DIR / "prices.csv"
        with open(prices_file, encoding="utf-8") as f:
            p_rows = list(csv.DictReader(f))
        for p in p_rows:
            if p["room_id"] == room_id:
                p["slot_group_id"] = new_sg
        with open(prices_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["room_id", "slot_group_id", "khung_code", "khung_label", "base_price", "effective_from", "effective_to"])
            writer.writeheader()
            writer.writerows(p_rows)

        avail_file = DATA_DIR / "availability.csv"
        with open(avail_file, encoding="utf-8") as f:
            a_rows = list(csv.DictReader(f))
        for a in a_rows:
            if a["room_id"] == room_id:
                a["slot_group_id"] = new_sg
        with open(avail_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["room_id", "date", "slot_group_id", "khung_code", "availability_status"])
            writer.writeheader()
            writer.writerows(a_rows)

    if room_data.get("image_url"):
        img_path = BASE_DIR / "static" / "images" / "rooms" / "room_images.json"
        try:
            imgs = json.loads(img_path.read_text(encoding="utf-8")) if img_path.exists() else {}
            imgs[room_id] = [room_data["image_url"]]
            img_path.write_text(json.dumps(imgs, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    return updated_row


def toggle_room_status(room_id: str, new_status: str | None = None) -> dict[str, Any]:
    """
    UC-03.3: Ngừng hoạt động / Tái kích hoạt phòng khai thác
    """
    rooms_file = DATA_DIR / "rooms.csv"
    with open(rooms_file, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    target = None
    for r in rows:
        if r["room_id"] == room_id:
            if new_status:
                r["operational_status"] = new_status
            else:
                r["operational_status"] = "Ngừng khai thác" if r.get("operational_status") == "Sẵn sàng" else "Sẵn sàng"
            target = r
            break

    if not target:
        raise ValueError(f"Không tìm thấy phòng '{room_id}'.")

    with open(rooms_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "room_id", "room_name", "branch_id", "branch_name", "room_type",
            "concept", "concept_name", "capacity", "bed_type", "area",
            "amenities", "description", "slot_group_id", "operational_status"
        ])
        writer.writeheader()
        writer.writerows(rows)

    return target


# 4. QUẢN LÝ CHÍNH SÁCH KINH DOANH (UC-04.5, UC-04.6, UC-04.7)
def list_business_policies() -> list[dict[str, Any]]:
    """Đọc danh sách chính sách kinh doanh từ data/business_policies.json"""
    policy_file = DATA_DIR / "business_policies.json"
    if not policy_file.exists():
        return []
    with open(policy_file, encoding="utf-8") as f:
        return json.load(f)


def save_business_policies(policies: list[dict[str, Any]]) -> None:
    """Ghi danh sách chính sách kinh doanh vào data/business_policies.json"""
    policy_file = DATA_DIR / "business_policies.json"
    with open(policy_file, "w", encoding="utf-8") as f:
        json.dump(policies, f, ensure_ascii=False, indent=2)


def add_business_policy(policy_data: dict[str, Any], created_by: str = "Quản lý chuỗi") -> dict[str, Any]:
    """UC-04.5: Thêm điều khoản chính sách kinh doanh mới"""
    policies = list_business_policies()
    p_id = (policy_data.get("policy_id") or "").upper().strip()
    if not p_id:
        p_id = f"POL-{len(policies) + 1:02d}"
    if any(p["policy_id"] == p_id for p in policies):
        raise ValueError(f"Mã chính sách '{p_id}' đã tồn tại.")

    new_p = {
        "policy_id": p_id,
        "category": policy_data.get("category") or "GENERAL",
        "title": policy_data.get("title", "").strip() or "Chính sách kinh doanh",
        "summary": policy_data.get("summary", "").strip(),
        "effective_from": policy_data.get("effective_from") or date.today().isoformat(),
        "active": True,
        "version": policy_data.get("version") or "1.0",
        "updated_at": datetime.now().isoformat(),
        "updated_by": created_by,
        "rules": policy_data.get("rules", []),
        "content": policy_data.get("content", "").strip(),
    }
    policies.append(new_p)
    save_business_policies(policies)
    return new_p


def update_business_policy(policy_id: str, data: dict[str, Any], updated_by: str = "Quản lý chuỗi") -> dict[str, Any]:
    """UC-04.6: Cập nhật điều khoản chính sách kinh doanh"""
    policies = list_business_policies()
    updated = None
    for p in policies:
        if p["policy_id"] == policy_id:
            if "title" in data: p["title"] = data["title"].strip()
            if "summary" in data: p["summary"] = data["summary"].strip()
            if "category" in data: p["category"] = data["category"]
            if "effective_from" in data: p["effective_from"] = data["effective_from"]
            if "content" in data: p["content"] = data["content"].strip()
            if "rules" in data: p["rules"] = data["rules"]
            if "active" in data: p["active"] = bool(data["active"])
            # Tăng phiên bản khi cập nhật
            try:
                ver_num = float(p.get("version", "1.0"))
                p["version"] = f"{ver_num + 0.1:.1f}"
            except Exception:
                p["version"] = "1.1"
            p["updated_at"] = datetime.now().isoformat()
            p["updated_by"] = updated_by
            updated = p
            break
    if not updated:
        raise ValueError(f"Không tìm thấy chính sách '{policy_id}'.")
    save_business_policies(policies)
    return updated


def toggle_business_policy(policy_id: str) -> dict[str, Any]:
    """UC-04.7: Bật / Tắt hiệu lực chính sách kinh doanh"""
    policies = list_business_policies()
    target = None
    for p in policies:
        if p["policy_id"] == policy_id:
            p["active"] = not p.get("active", True)
            p["updated_at"] = datetime.now().isoformat()
            target = p
            break
    if not target:
        raise ValueError(f"Không tìm thấy chính sách '{policy_id}'.")
    save_business_policies(policies)
    return target

