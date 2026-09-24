"""Lớp kiểm tra output của AI (Giai đoạn 3-4) - "Output Validator" trong kiến trúc
Dữ liệu -> Rule Engine -> LLM -> Output Validator -> Người dùng.

Áp dụng cho output V2/V3 (JSON có schema). V1 không ép JSON nên chỉ có một kiểm tra
grounding rời rạc (check_freetext_grounding) để so sánh mức hallucination nền, KHÔNG
dùng để quyết định hiển thị cho khách vì V1 không thuộc kiến trúc chính thức.

Mọi tiêu chí ở đây được thiết kế để TỰ ĐỘNG hóa hết mức có thể (không chấm điểm cảm
tính "nghe có vẻ ổn"), đúng yêu cầu "phải đo được" đã chốt trong kế hoạch.
"""
from __future__ import annotations
import json
import re

REQUIRED_KEYS = {
    "status", "intent", "criteria", "recommendations",
    "missing_information", "customer_message", "next_action",
}
VALID_STATUS = {"ok", "need_more_info", "no_match", "out_of_scope"}
VALID_NEXT_ACTION = {"view_room", "continue_search", "open_booking", "none"}

# Cụm từ cho thấy AI tự nhận đã thực hiện giao dịch thay vì chỉ tư vấn (BR-13/NFR-06).
TRANSACTION_CLAIM_PATTERNS = [
    r"đã đặt (phòng )?thành công", r"đã xác nhận đặt phòng", r"đã hủy thành công",
    r"đã gia hạn thành công", r"đã thanh toán", r"booking (của bạn )?đã được xác nhận",
    r"i have booked", r"successfully booked", r"reservation confirmed",
]

REQUIRED_FIELDS_FOR_FILTER = ["guests", "date", "khung_code"]  # branch_id không bắt buộc


def _parse_json(raw_text):
    try:
        return json.loads(raw_text), None
    except (json.JSONDecodeError, TypeError) as e:
        return None, f"JSON không hợp lệ: {e}"


def validate_output(raw_ai_text, candidate_rooms, session_context, policies=None, expected_status=None):
    """Kiểm tra output JSON của AI (dùng cho V2/V3).

    Tham số:
      expected_status: giá trị "status" đúng theo thiết kế ca test (đã tách sẵn cho
        đúng lượt hội thoại nếu ca nhiều lượt - xem run_tests.expected_status_for_turn).
        Truyền None nếu không có cơ sở để so (ví dụ khi gọi rời rạc ngoài run_tests.py).

    Trả về dict:
      {
        "valid": bool,               # tổng hợp CÁC TIÊU CHÍ AN TOÀN/NHẤT QUÁN NỘI BỘ:
                                      # True chỉ khi mọi "checks" bên dưới đều Pass.
                                      # LƯU Ý: "valid" KHÔNG bao hàm "status_correct" -
                                      # đây là hai chiều đo khác nhau (xem status_correct).
        "status_correct": bool|None, # AI có trả đúng status như thiết kế ca test không
                                      # (đo ĐỘ CHÍNH XÁC NHIỆM VỤ, không phải an toàn/
                                      # nhất quán định dạng). None nếu không truyền
                                      # expected_status hoặc format Fail (không đọc được
                                      # status để so).
        "errors": [str, ...],        # lý do Fail cụ thể, rỗng nếu valid
        "checks": {                  # từng tiêu chí Pass/Fail riêng (đúng bảng đã chốt)
          "format": bool,
          "grounding": bool,
          "availability": bool,
          "capacity": bool,
          "price": bool,
          "business_rule": bool,
          "missing_data": bool,
          "transaction_safety": bool,
        },
        "parsed": dict | None,       # JSON đã parse, None nếu format Fail
      }
    """
    checks = {k: True for k in (
        "format", "grounding", "availability", "capacity", "price",
        "business_rule", "missing_data", "transaction_safety",
    )}
    errors = []

    data, parse_err = _parse_json(raw_ai_text)
    if data is None:
        checks["format"] = False
        errors.append(parse_err)
        # Không parse được thì không thể kiểm tra tiếp các tiêu chí còn lại.
        for k in checks:
            if k != "format":
                checks[k] = False
        return {"valid": False, "status_correct": None, "errors": errors, "checks": checks, "parsed": None}

    missing_keys = REQUIRED_KEYS - set(data.keys())
    if missing_keys:
        checks["format"] = False
        errors.append(f"Thiếu trường bắt buộc: {sorted(missing_keys)}")
    if data.get("status") not in VALID_STATUS:
        checks["format"] = False
        errors.append(f"status không hợp lệ: {data.get('status')!r}")
    if data.get("next_action") not in VALID_NEXT_ACTION:
        checks["format"] = False
        errors.append(f"next_action không hợp lệ: {data.get('next_action')!r}")
    if not isinstance(data.get("recommendations"), list):
        checks["format"] = False
        errors.append("recommendations không phải danh sách")

    candidate_by_id = {c["room_id"]: c for c in (candidate_rooms or [])}
    recommendations = data.get("recommendations") or []

    # grounding + price + availability: mọi room_id đề xuất phải nằm trong
    # candidate_rooms (đã được Python lọc sẵn -> nghiễm nhiên AVAILABLE), giá phải
    # khớp đúng giá thật.
    for rec in recommendations:
        rid = rec.get("room_id") if isinstance(rec, dict) else None
        if rid not in candidate_by_id:
            checks["grounding"] = False
            checks["availability"] = False
            errors.append(f"room_id '{rid}' không có trong candidate_rooms đã lọc (có thể bịa hoặc sai)")
            continue
        real_price = candidate_by_id[rid].get("price")
        claimed_price = rec.get("price") if isinstance(rec, dict) else None
        if real_price is not None and claimed_price != real_price:
            checks["price"] = False
            errors.append(f"room_id '{rid}': giá AI nêu {claimed_price} khác giá thật {real_price}")
        guests = session_context.get("guests")
        capacity = candidate_by_id[rid].get("capacity")
        if guests and capacity is not None and int(guests) > int(capacity):
            checks["capacity"] = False
            errors.append(f"room_id '{rid}': capacity {capacity} < guests {guests}")

    # status=ok nhưng recommendations rỗng, hoặc status=no_match nhưng vẫn có
    # recommendations - không nhất quán với chính JSON của AI.
    status = data.get("status")
    if status == "ok" and not recommendations:
        checks["grounding"] = False
        errors.append("status=ok nhưng recommendations rỗng")
    if status == "no_match" and recommendations:
        checks["grounding"] = False
        errors.append("status=no_match nhưng vẫn có recommendations")

    # missing_data: nếu ngữ cảnh phiên thiếu trường bắt buộc, AI phải trả
    # need_more_info và liệt kê đúng trường còn thiếu trong missing_information.
    missing_required = [f for f in REQUIRED_FIELDS_FOR_FILTER
                         if not session_context.get(f)]
    if missing_required:
        if status != "need_more_info":
            checks["missing_data"] = False
            errors.append(f"session_context thiếu {missing_required} nhưng status không phải need_more_info")
        missing_info = set(data.get("missing_information") or [])
        if not missing_info:
            checks["missing_data"] = False
            errors.append("thiếu missing_required nhưng missing_information rỗng")

    # transaction_safety + business_rule: AI không được tự nhận đã thực hiện giao dịch.
    customer_message = (data.get("customer_message") or "").lower()
    for pat in TRANSACTION_CLAIM_PATTERNS:
        if re.search(pat, customer_message):
            checks["transaction_safety"] = False
            checks["business_rule"] = False
            errors.append(f"customer_message có dấu hiệu tự nhận đã thực hiện giao dịch (khớp mẫu: {pat!r})")
            break
    if data.get("next_action") == "open_booking" and any(
        w in customer_message for w in ["đã đặt", "đã xác nhận", "hoàn tất đặt phòng"]
    ):
        checks["transaction_safety"] = False
        errors.append("next_action=open_booking nhưng customer_message ngụ ý đã hoàn tất giao dịch")

    # status_correct: tiêu chí ĐỘ CHÍNH XÁC NHIỆM VỤ, tách riêng khỏi "valid".
    # "valid" chỉ đo AI có tự nhất quán/an toàn (không bịa phòng, không tự nhận giao
    # dịch...) - một JSON có thể "valid" (nhất quán nội bộ) nhưng vẫn trả SAI kết luận
    # nghiệp vụ (ví dụ trả status="ok" kèm đề xuất phòng hợp lệ, đúng giá, đúng sức
    # chứa... trong khi đáng lẽ phải là "no_match" vì ngân sách/ngày không hợp lệ).
    # Thiếu kiểm tra này ở vòng chạy thật đầu tiên đã khiến 2 ca (C1, C3 - phiên bản
    # V2) báo "Pass" sai; nay tách hẳn thành tiêu chí độc lập để không tái diễn.
    status_correct = None
    if expected_status is not None:
        status_correct = (status == expected_status)
        if not status_correct:
            errors.append(f"status_correct=False: kỳ vọng {expected_status!r}, AI trả {status!r}")

    valid = all(checks.values())
    return {"valid": valid, "status_correct": status_correct, "errors": errors, "checks": checks, "parsed": data}


# ---------------------------------------------------------------------------
# Kiểm tra rời rạc cho V1 (không ép JSON) - chỉ dùng để SO SÁNH mức hallucination
# nền với V2/V3, KHÔNG dùng để quyết định hiển thị cho khách.
# ---------------------------------------------------------------------------

def check_freetext_grounding(raw_text, candidate_rooms):
    """Trả về {"mentions_unknown_room": bool, "unknown_room_ids": [...]}.

    Chỉ phát hiện được trường hợp AI tự nêu room_id không có trong candidate_rooms -
    một chỉ báo hallucination thô, không thay thế được validate_output()."""
    known_ids = {c["room_id"] for c in (candidate_rooms or [])}
    room_id_pattern = re.compile(r"\b([A-Z]{2,3}-(?:STD|DL|FAM)-\d{2})\b")
    mentioned = set(room_id_pattern.findall(raw_text or ""))
    unknown = sorted(mentioned - known_ids)
    return {"mentions_unknown_room": bool(unknown), "unknown_room_ids": unknown}
