import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "services"))

from services.chatbot_engine import ChatbotEngine, SessionManager

TEST_CASES = [
    ("CASE 01: Greeting", "Xin chào", "GREETING"),
    ("CASE 02: Slot filling vague", "Tìm phòng cho tôi", "NEED_MORE_INFO"),
    ("CASE 03: Slot filling missing stay_type", "Tìm phòng Bến Thành cho 2 người tối mai", "ROOM_RECOMMENDATION"),
    ("CASE 04: Slot filling hourly", "Tôi muốn thuê 4 tiếng chiều mai", "ROOM_RECOMMENDATION"),
    ("CASE 05: Overnight check", "Tôi muốn ở Thảo Điền từ thứ 6 đến thứ 7 cho 2 người", "ROOM_RECOMMENDATION"),
    ("CASE 06: Room Amenity BT-103", "BT-103 có ban công không?", "ROOM_AMENITY"),
    ("CASE 07: Room Price BT-103", "BT-103 bao nhiêu tiền?", "ROOM_PRICE"),
    ("CASE 08: Context 'phòng này' availability", "Phòng này còn tối mai không?", "ROOM_AVAILABILITY"),
    ("CASE 09: Context switch branch", "Tôi đổi sang Thảo Điền", "ROOM_RECOMMENDATION"),
    ("CASE 10: Lower price filter", "Có phòng nào rẻ hơn không?", "ROOM_RECOMMENDATION"),
    ("CASE 11: Cancellation policy", "Hủy phòng thì sao?", "CANCELLATION_POLICY"),
    ("CASE 12: Refund policy", "Nếu hủy thì được hoàn tiền không?", "REFUND_POLICY"),
    ("CASE 13: Requesting bot to cancel", "Hủy phòng giúp tôi", "CANCELLATION_POLICY"),
    ("CASE 14: Refund timeline", "Bao lâu tôi nhận lại tiền?", "REFUND_POLICY"),
    ("CASE 15: Branches list", "CozyHome có những chi nhánh nào?", "HOMESTAY_INFORMATION"),
    ("CASE 16: Branch BT location", "Chi nhánh Bến Thành ở đâu?", "BRANCH_INFORMATION"),
    ("CASE 17: Hourly rental policy", "CozyHome có thuê theo giờ không?", "HOURLY_RENTAL_POLICY"),
    ("CASE 18: Capacity 20 guests", "Có phòng cho 20 người không?", "ROOM_RECOMMENDATION"),
    ("CASE 19: Unsupported location Đà Lạt", "Có phòng ở Đà Lạt không?", "OUT_OF_SCOPE"),
    ("CASE 20: Today promotions", "Cho tôi giá khuyến mãi hôm nay", "PROMOTION_POLICY"),
]

def run_tests():
    sid = "test_eval_session_v2"
    SessionManager.reset_session(sid)
    print("=" * 70, flush=True)
    print("KIỂM THỬ 20 TEST CASES CHO CHATBOT AI COZYHOME", flush=True)
    print("=" * 70, flush=True)

    passed = 0
    for case_name, query, expected_intent in TEST_CASES:
        res = ChatbotEngine.process_message(sid, query)
        intent = res.get("intent")
        msg = res.get("message", "")
        recs = res.get("recommendations", [])
        qreplies = res.get("quick_replies", [])
        is_ok = (intent == expected_intent)
        if is_ok:
            passed += 1
        
        status_icon = "✅ PASS" if is_ok else f"❌ FAIL (Expected: {expected_intent})"
        print(f"\n👉 [{case_name}] -> {status_icon}", flush=True)
        print(f"User: '{query}'", flush=True)
        print(f"Bot Intent: {intent}", flush=True)
        print(f"Bot Message:\n{msg[:200]}...", flush=True)
        if recs:
            print(f"Cards ({len(recs)}): {[r['room_name'] for r in recs]}", flush=True)
        if qreplies:
            print(f"Quick Replies: {qreplies}", flush=True)
        print("-" * 50, flush=True)

    print(f"\nKẾT QUẢ TỔNG THỂ: {passed}/{len(TEST_CASES)} CASES ĐẠT CHUẨN!", flush=True)
    print("=" * 70, flush=True)

if __name__ == "__main__":
    run_tests()
