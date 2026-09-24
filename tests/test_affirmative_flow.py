import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.chatbot_engine import ChatbotEngine, SessionManager

def test_flow():
    # Test 1: Standard Turn 1 + Turn 2 with "có"
    sid = "test_multi_turn_flow_01"
    r1 = ChatbotEngine.process_message(sid, "tôi muốn tìm một phòng cho 7 người qua đêm tại Phú Mỹ Hưng với ngân sách tối đa 2 triệu, có ban công hoặc máy chiếu không?")
    assert r1["intent"] == "ROOM_RECOMMENDATION"
    assert "không có một phòng nào đáp ứng cho 7 người" in r1["message"]
    
    r2 = ChatbotEngine.process_message(sid, "có")
    assert r2["intent"] == "SPLIT_ROOM_RECOMMENDATION"
    assert len(r2["recommendations"]) == 3
    print("Test 1 ('có') Passed!")

    # Test 2: Turn 2 with "ok bạn"
    sid2 = "test_multi_turn_flow_02"
    ChatbotEngine.process_message(sid2, "tôi muốn tìm một phòng cho 7 người qua đêm tại Phú Mỹ Hưng")
    r2_ok = ChatbotEngine.process_message(sid2, "ok bạn")
    assert r2_ok["intent"] == "SPLIT_ROOM_RECOMMENDATION"
    print("Test 2 ('ok bạn') Passed!")

    # Test 3: Turn 2 with "lên phương án đi"
    sid3 = "test_multi_turn_flow_03"
    ChatbotEngine.process_message(sid3, "tôi muốn tìm một phòng cho 7 người qua đêm tại Phú Mỹ Hưng")
    r3_plan = ChatbotEngine.process_message(sid3, "lên phương án đi")
    assert r3_plan["intent"] == "SPLIT_ROOM_RECOMMENDATION"
    print("Test 3 ('lên phương án đi') Passed!")

    # Test 4: Turn 2 with "không"
    sid4 = "test_multi_turn_flow_04"
    ChatbotEngine.process_message(sid4, "tôi muốn tìm một phòng cho 7 người qua đêm tại Phú Mỹ Hưng")
    r4_no = ChatbotEngine.process_message(sid4, "không")
    assert r4_no["intent"] == "REDUCE_GUESTS_INQUIRY"
    print("Test 4 ('không' -> REDUCE_GUESTS_INQUIRY) Passed!")

    # Test 5: Server reload simulation (clearing memory, rehydrating from DB)
    sid5 = "test_rehydration_from_db"
    r5_1 = ChatbotEngine.process_message(sid5, "tôi muốn tìm một phòng cho 7 người qua đêm tại Phú Mỹ Hưng với ngân sách tối đa 2 triệu")
    # Clear memory
    SessionManager._sessions.clear()
    # Now ask "có"
    r5_2 = ChatbotEngine.process_message(sid5, "có")
    assert r5_2["intent"] == "SPLIT_ROOM_RECOMMENDATION"
    assert len(r5_2["recommendations"]) == 3
    print("Test 5 (Server reload rehydration) Passed!")

    print("\nALL 5 MULTI-TURN TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_flow()
