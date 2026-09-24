from __future__ import annotations

import json
from datetime import date as dt_date
from pathlib import Path
from typing import Any
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, HTTPException

try:
    from services.business_service import (
        ALL_SLOT_OPTIONS,
        BRANCHES,
        SLOT_GROUPS_SCHEDULE,
        SLOT_NAMES,
        all_rooms,
        availability_grid,
        get_room,
        search_rooms,
        slot_info_for_room,
    )
except ImportError:
    # pyrefly: ignore [missing-import]
    from business_service import (
        ALL_SLOT_OPTIONS,
        BRANCHES,
        SLOT_GROUPS_SCHEDULE,
        SLOT_NAMES,
        all_rooms,
        availability_grid,
        get_room,
        search_rooms,
        slot_info_for_room,
    )

router = APIRouter(prefix="/api", tags=["Rooms & Slots"])

_ROOM_IMAGES_PATH = Path(__file__).resolve().parent.parent / "static" / "images" / "rooms" / "room_images.json"
try:
    ROOM_IMAGES: dict[str, list[str]] = json.loads(_ROOM_IMAGES_PATH.read_text(encoding="utf-8"))
except FileNotFoundError:
    ROOM_IMAGES = {}


def with_images(room: dict[str, Any]) -> dict[str, Any]:
    room["images"] = ROOM_IMAGES.get(room.get("room_id"), [])
    return room


@router.get("/branches")
def get_branches():
    return [{"id": k, "name": v} for k, v in BRANCHES.items()]


@router.get("/slots")
def get_slots():
    return ALL_SLOT_OPTIONS


@router.get("/slots/schedule")
def get_slot_schedule():
    return {
        "schedule": SLOT_GROUPS_SCHEDULE,
        "table_3_4": [
            {"group": "Nhóm 1", "rooms": "Phòng 1 & 5", "k1": "09:30 – 12:30", "k2": "13:00 – 16:00", "k3": "16:30 – 19:30", "qd": "20:00 – 08:30 hôm sau"},
            {"group": "Nhóm 2", "rooms": "Phòng 2 & 6", "k1": "10:00 – 13:00", "k2": "13:30 – 16:30", "k3": "17:00 – 20:00", "qd": "20:30 – 09:00 hôm sau"},
            {"group": "Nhóm 3", "rooms": "Phòng 3 & 7", "k1": "10:30 – 13:30", "k2": "14:00 – 17:00", "k3": "17:30 – 20:30", "qd": "21:00 – 09:30 hôm sau"},
            {"group": "Nhóm 4", "rooms": "Phòng 4 & 8", "k1": "11:00 – 14:00", "k2": "14:30 – 17:30", "k3": "18:00 – 21:00", "qd": "21:30 – 10:00 hôm sau"},
        ]
    }


@router.get("/rooms")
def list_rooms(
    branch_id: str = "",
    guests: int = 2,
    date: str = "",
    khung_code: str = "",
    budget_max: str = "",
    min_price: str = "",
    prefs: str = "",
    keyword: str = "",
    room_name: str = "",
    room_types: str = "",
    sort_by: str = "popularity",
    area_range: str = "",
    bed_types: str = "",
):
    today = dt_date.today().isoformat()
    booking_date = date if date else today
    pref_list = [p.strip() for p in prefs.split(",") if p.strip()]
    type_list = [t.strip() for t in room_types.split(",") if t.strip()]
    bed_list = [b.strip() for b in bed_types.split(",") if b.strip()]
    # Xử lý an toàn cho các tham số số nguyên tùy chọn
    budget_max_int = int(budget_max) if budget_max.strip() else None
    min_price_int = int(min_price) if min_price.strip() else None
    candidates, trace = search_rooms(
        branch_id=branch_id if branch_id else None,
        guests=guests,
        booking_date=booking_date,
        khung_code=khung_code,
        budget_max=budget_max_int,
        preferences=pref_list,
        keyword=keyword if keyword else None,
        room_name=room_name if room_name else None,
        room_types=type_list if type_list else None,
        min_price=min_price_int,
        sort_by=sort_by,
        area_range=area_range if area_range else None,
        bed_types=bed_list if bed_list else None,
    )
    candidates = [with_images(c) for c in candidates]

    fallback = None
    if not candidates and branch_id:
        try:
            from services.business_service import get_search_fallback
        except ImportError:
            from business_service import get_search_fallback
        fb = get_search_fallback(
            branch_id=branch_id,
            guests=guests,
            booking_date=booking_date,
            khung_code=khung_code,
            budget_max=budget_max_int,
            preferences=pref_list,
            keyword=keyword if keyword else None,
            room_types=type_list if type_list else None,
            min_price=min_price_int,
        )
        if fb and fb.get("type") == "branch_switch" and fb.get("sample_rooms"):
            fb["sample_rooms"] = [with_images(r) for r in fb["sample_rooms"]]
            fallback = fb

    return {"rooms": candidates, "trace": trace, "fallback": fallback}


@router.get("/rooms/{room_id}")
def get_room_detail(room_id: str):
    room = get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Không tìm thấy thông tin phòng.")
    room = with_images(dict(room))
    slots = slot_info_for_room(room_id)
    raw_grid = availability_grid(room_id, 15)
    dates = [row["date"] for row in raw_grid]
    matrix = {
        row["date"]: {
            code: ("AVAILABLE" if row.get(code) else "BOOKED")
            for code in ("K1", "K2", "K3", "QD")
        }
        for row in raw_grid
    }
    grid_data = {
        "dates": dates,
        "matrix": matrix,
        "rows": raw_grid,
    }
    return {"room": room, "slots": slots, "grid": grid_data}


@router.get("/rooms/{room_id}/reviews")
def get_room_reviews_endpoint(room_id: str):
    from services.storage import get_room_reviews
    reviews = get_room_reviews(room_id)
    return {"reviews": reviews}


@router.get("/rooms/{room_id}/similar")
def get_similar_rooms_endpoint(room_id: str):
    current = get_room(room_id)
    if not current:
        return {"rooms": []}
    all_r = [with_images(dict(r)) for r in all_rooms() if r["room_id"] != room_id]
    
    # Ưu tiên gợi ý theo quy tắc:
    # 1. Cùng chi nhánh
    # 2. Cùng sức chứa
    # 3. Cùng hạng phòng
    def score_similarity(r):
        score = 0
        if r.get("branch_id") == current.get("branch_id"):
            score += 10
        if r.get("room_type") == current.get("room_type"):
            score += 5
        cap_diff = abs(int(r.get("capacity", 2)) - int(current.get("capacity", 2)))
        score += max(0, 5 - cap_diff)
        return score

    all_r.sort(key=score_similarity, reverse=True)
    return {"rooms": all_r[:4]}

