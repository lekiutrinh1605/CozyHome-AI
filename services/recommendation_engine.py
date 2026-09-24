"""Bộ lọc nghiệp vụ cho UC-02.4 - AI tư vấn và hỗ trợ khách hàng.

Đây là lớp "Python xử lý nghiệp vụ chắc chắn" trong kiến trúc:
    Python lọc nghiệp vụ -> LLM xử lý ngôn ngữ/xếp hạng -> Python kiểm tra output -> Streamlit hiển thị

Mọi điều kiện có tính giao dịch/dữ liệu (chi nhánh, sức chứa, khả dụng, giá) đều được
xác định ở đây bằng Python thuần, KHÔNG giao cho AI suy đoán - đúng NFR-06 và BR-13.
AI (ở bước sau, chưa triển khai trong file này) chỉ nhận danh sách candidate_rooms đã
được lọc để diễn giải/xếp hạng theo sở thích định tính của khách.

Mô hình khung giờ: "nhóm khung giờ" (slot_group_id, N1-N4, theo Bảng 3.4) khác với
"khung giờ" (khung_code, K1/K2/K3/QD - 4 khung cụ thể của một phòng, tùy nhóm nó
được gán). Thời gian thật (09:30-12:30 v.v.) chỉ có trong slot_definitions.csv, tra
theo (slot_group_id, khung_code) - availability.csv và prices.csv không lưu trùng
thời gian để tránh lệch dữ liệu khi chỉnh sửa.
"""
from __future__ import annotations
import csv
import json
import os

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))


def _load_csv(name):
    with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_data():
    rooms = _load_csv("rooms.csv")
    availability = _load_csv("availability.csv")
    prices = _load_csv("prices.csv")
    slot_definitions = _load_csv("slot_definitions.csv")
    with open(os.path.join(DATA_DIR, "policies.json"), encoding="utf-8") as f:
        policies = json.load(f)
    for r in rooms:
        r["capacity"] = int(r["capacity"])
        r["amenities"] = r["amenities"].split("|") if r["amenities"] else []
    for p in prices:
        p["base_price"] = int(p["base_price"])

    # Kiểm tra toàn vẹn: mọi dòng availability/prices phải khớp đúng slot_group_id
    # thật của phòng trong rooms.csv - phát hiện sớm nếu dữ liệu bị chỉnh lệch tay,
    # tránh lỗi âm thầm khi lọc theo khung giờ.
    room_group = {r["room_id"]: r["slot_group_id"] for r in rooms}
    for row in availability:
        expected = room_group.get(row["room_id"])
        if expected is not None and row["slot_group_id"] != expected:
            raise ValueError(
                f"availability.csv: {row['room_id']} có slot_group_id={row['slot_group_id']!r} "
                f"nhưng rooms.csv gán {expected!r}"
            )
    for row in prices:
        expected = room_group.get(row["room_id"])
        if expected is not None and row["slot_group_id"] != expected:
            raise ValueError(
                f"prices.csv: {row['room_id']} có slot_group_id={row['slot_group_id']!r} "
                f"nhưng rooms.csv gán {expected!r}"
            )

    slot_time = {(s["slot_group_id"], s["khung_code"]): s for s in slot_definitions}
    return rooms, availability, prices, slot_time, policies


def resolve_khung_time(slot_time, slot_group_id, khung_code):
    """Trả về (start_time, end_time, next_slot) thật của một khung cụ thể, tra theo
    đúng nhóm khung giờ của phòng - không suy đoán từ khung_code một mình."""
    s = slot_time.get((slot_group_id, khung_code))
    if not s:
        return None
    clean_end = s["end_time"].replace("+1", "") if s.get("end_time") else s.get("end_time")
    return s["start_time"], clean_end, s["next_slot"]


# ---------------------------------------------------------------------------
# Các hàm lọc đơn lẻ - mỗi hàm chỉ chịu trách nhiệm một điều kiện, dễ kiểm thử
# độc lập (per section "Giai đoạn 2" trong kế hoạch PoC).
# ---------------------------------------------------------------------------

def filter_by_branch(rooms, branch_id):
    if not branch_id:
        return rooms
    return [r for r in rooms if r["branch_id"] == branch_id]


def filter_by_capacity(rooms, guests):
    if not guests:
        return rooms
    return [r for r in rooms if r["capacity"] >= int(guests)]


def filter_by_availability(rooms, availability, date, khung_code):
    """Giữ lại phòng có dòng availability AVAILABLE đúng ngày/khung của CHÍNH phòng
    đó (khớp cả room_id lẫn slot_group_id đã gắn với phòng, không chỉ khung_code
    đơn thuần); loại phòng đang bảo trì hoặc không có dữ liệu khả dụng cho ngày đó."""
    if not date:
        return rooms
    avail_ok = set()
    for a in availability:
        if a["date"] != date:
            continue
        if khung_code and a["khung_code"] != khung_code:
            continue
        if a["availability_status"] == "AVAILABLE":
            avail_ok.add((a["room_id"], a["khung_code"]))
    result = []
    for r in rooms:
        if r["operational_status"] != "Sẵn sàng":
            continue
        if khung_code:
            if (r["room_id"], khung_code) in avail_ok:
                result.append(r)
        else:
            if any(rid == r["room_id"] for rid, _ in avail_ok):
                result.append(r)
    return result


def filter_by_budget(rooms, prices, budget_max, khung_code):
    if not budget_max:
        return rooms
    price_map = {(p["room_id"], p["khung_code"]): p["base_price"] for p in prices}
    result = []
    for r in rooms:
        price = price_map.get((r["room_id"], khung_code)) if khung_code else min(
            (p["base_price"] for p in prices if p["room_id"] == r["room_id"]), default=None
        )
        if price is not None and price <= int(budget_max):
            result.append(r)
    return result


def filter_by_amenities_hint(rooms, preferences):
    """Lọc mềm: không loại phòng nếu không khớp tuyệt đối, chỉ dùng để xếp hạng sơ bộ
    trước khi giao cho AI diễn giải. So khớp trên cả amenities, concept_name và
    description. Trả về rooms không đổi thứ tự nếu preferences rỗng."""
    if not preferences:
        return rooms
    def score(r):
        haystack = " ".join(r["amenities"]) + " " + r.get("concept_name", "") + " " + r["description"]
        haystack = haystack.lower()
        return sum(1 for p in preferences if p.lower() in haystack)
    return sorted(rooms, key=score, reverse=True)


# ---------------------------------------------------------------------------
# Hàm tổng hợp: nhận "ngữ cảnh phiên" (Nhóm B trong thiết kế input) và trả về
# candidate_rooms đúng định dạng sẽ đưa vào BUSINESS_DATA cho AI (Nhóm C).
# ---------------------------------------------------------------------------

def recommend_candidates(session_context, max_candidates=6):
    """session_context: dict với các khóa branch_id, guests, date, khung_code,
    budget_max, preferences (list). Trả về (candidate_rooms, filter_trace)."""
    rooms, availability, prices, slot_time, policies = load_data()
    trace = {"total_rooms": len(rooms)}

    step = filter_by_branch(rooms, session_context.get("branch_id"))
    trace["after_branch"] = len(step)

    step = filter_by_capacity(step, session_context.get("guests"))
    trace["after_capacity"] = len(step)

    step = filter_by_availability(step, availability, session_context.get("date"),
                                   session_context.get("khung_code"))
    trace["after_availability"] = len(step)

    step = filter_by_budget(step, prices, session_context.get("budget_max"),
                             session_context.get("khung_code"))
    trace["after_budget"] = len(step)

    step = filter_by_amenities_hint(step, session_context.get("preferences"))
    step = step[:max_candidates]
    trace["returned"] = len(step)

    price_map = {(p["room_id"], p["khung_code"]): p["base_price"] for p in prices}
    khung_code = session_context.get("khung_code")
    candidate_rooms = []
    for r in step:
        price = price_map.get((r["room_id"], khung_code)) if khung_code else None
        time_info = resolve_khung_time(slot_time, r["slot_group_id"], khung_code) if khung_code else None
        candidate_rooms.append({
            "room_id": r["room_id"],
            "room_name": r["room_name"],
            "branch_id": r.get("branch_id") or ("BT" if "BT" in r["room_id"] else "TD" if "TD" in r["room_id"] else "PMH"),
            "branch_name": r["branch_name"],
            "room_type": r["room_type"],
            "capacity": r["capacity"],
            "concept": r["concept"],
            "concept_name": r["concept_name"],
            "amenities": r["amenities"],
            "khung_code": khung_code,
            "start_time": time_info[0] if time_info else None,
            "end_time": time_info[1] if time_info else None,
            "price": price,
        })
    return candidate_rooms, trace


if __name__ == "__main__":
    # Tự kiểm tra bằng đúng ví dụ trong kế hoạch: 2 khách, Bến Thành, 29/08/2026,
    # ngân sách <= 800.000đ, khung qua đêm (QD) - không gọi AI, chỉ kiểm tra lớp lọc.
    example_context = {
        "branch_id": "BT",
        "guests": 2,
        "date": "2026-08-29",
        "khung_code": "QD",
        "budget_max": 800000,
        "preferences": ["lãng mạn", "bồn tắm"],
    }
    candidates, trace = recommend_candidates(example_context)
    print("Filter trace:", trace)
    print(f"Số candidate_rooms trả về: {len(candidates)}")
    for c in candidates:
        print(" -", c["room_id"], c["room_name"], c["concept_name"], c["price"],
              f"{c['start_time']}-{c['end_time']}", c["amenities"])
