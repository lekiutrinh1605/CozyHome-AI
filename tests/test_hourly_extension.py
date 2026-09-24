import sys
from pathlib import Path
from datetime import date, datetime, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure project root in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from services.storage import (
    connect,
    create_booking,
    mark_paid,
    cancel_booking,
    add_extension,
    booking_exists,
    list_bookings,
)
from services.business_service import check_extension_availability


def run_tests():
    print("=== BẮT ĐẦU KIỂM THỬ NGHIỆP VỤ GIA HẠN THEO GIỜ ===")
    test_date = (date.today() + timedelta(days=10)).isoformat()
    room_id = "BT-STD-01"  # N1 group: K1 (09:30 - 12:30), K2 (13:00 - 16:00)

    # Dọn dẹp dữ liệu test cũ nếu có
    with connect() as conn:
        conn.execute("DELETE FROM bookings WHERE room_id=? AND booking_date=?", (room_id, test_date))
        conn.execute("DELETE FROM booking_extensions WHERE room_id=? AND extension_date=?", (room_id, test_date))

    # -------------------------------------------------------------
    # TEST 1: Ràng buộc trạng thái
    # -------------------------------------------------------------
    print("\n--- TEST 1: Ràng buộc trạng thái ---")
    # 1.1: Tạo đơn K1
    code1 = create_booking(
        user_id=1,
        room_id=room_id,
        branch_id="BT",
        booking_date=test_date,
        khung_code="K1",
        start_time="09:30",
        end_time="12:30",
        guests=2,
        amount=140000,
        customer_name="Test Khách",
        customer_phone="0901234567",
    )
    print(f"Đã tạo đơn test: {code1}, trạng thái: Chờ thanh toán")

    # Thử gia hạn khi đơn Chờ thanh toán -> Phải báo lỗi
    try:
        add_extension(code1, room_id, test_date, "K2", "12:30", "13:30", 50000, hours=1)
        assert False, "Lẽ ra phải chặn gia hạn khi đơn Chờ thanh toán!"
    except ValueError as e:
        print(f"✓ Chặn đúng khi đơn 'Chờ thanh toán': {e}")

    # Thanh toán đơn -> Chuyển sang 'Đã xác nhận'
    mark_paid(code1)
    print("Đã thanh toán đơn gốc -> 'Đã xác nhận'")

    # Hủy đơn -> Chuyển sang 'Đã hủy'
    cancel_booking(code1)
    print("Đã hủy đơn -> 'Đã hủy'")

    # Thử gia hạn khi đơn 'Đã hủy' -> Phải báo lỗi
    try:
        add_extension(code1, room_id, test_date, "K2", "12:30", "13:30", 50000, hours=1)
        assert False, "Lẽ ra phải chặn gia hạn khi đơn Đã hủy!"
    except ValueError as e:
        print(f"✓ Chặn đúng khi đơn 'Đã hủy': {e}")

    # -------------------------------------------------------------
    # TEST 2: Kiểm tra tính toán giờ & giá gia hạn (1h, 2h, 3h)
    # -------------------------------------------------------------
    print("\n--- TEST 2: Tính toán giờ & giá gia hạn ---")
    # Tạo đơn mới ở trạng thái 'Đã xác nhận'
    code2 = create_booking(
        user_id=1,
        room_id=room_id,
        branch_id="BT",
        booking_date=test_date,
        khung_code="K1",
        start_time="09:30",
        end_time="12:30",
        guests=2,
        amount=140000,
        customer_name="Khách Lưu Trú",
        customer_phone="0909999999",
    )
    mark_paid(code2)

    avail_1h = check_extension_availability(room_id, test_date, "K1", current_end_time="12:30", hours=1)
    assert avail_1h["can_extend"] is True
    assert avail_1h["new_end_time"] == "13:30", f"Mong đợi 13:30, nhận được {avail_1h['new_end_time']}"
    assert avail_1h["price"] == 50000, f"Mong đợi 50000, nhận được {avail_1h['price']}"
    print(f"✓ Gia hạn 1h: New checkout = {avail_1h['new_end_time']}, Phí = {avail_1h['price']} ₫")

    avail_2h = check_extension_availability(room_id, test_date, "K1", current_end_time="12:30", hours=2)
    assert avail_2h["new_end_time"] == "14:30"
    assert avail_2h["price"] == 100000
    print(f"✓ Gia hạn 2h: New checkout = {avail_2h['new_end_time']}, Phí = {avail_2h['price']} ₫")

    avail_3h = check_extension_availability(room_id, test_date, "K1", current_end_time="12:30", hours=3)
    assert avail_3h["new_end_time"] == "15:30"
    assert avail_3h["price"] == 150000
    print(f"✓ Gia hạn 3h: New checkout = {avail_3h['new_end_time']}, Phí = {avail_3h['price']} ₫")
    assert len(avail_1h["hourly_options"]) == 3
    print("✓ Đã sinh đầy đủ 3 tùy chọn hourly_options cho frontend")

    # -------------------------------------------------------------
    # TEST 3: Gia hạn thành công & Tự động khóa khung tiếp theo
    # -------------------------------------------------------------
    print("\n--- TEST 3: Tự động khóa khung tiếp theo trên lịch chung ---")
    # Trước khi gia hạn, K2 phải trống
    assert booking_exists(room_id, test_date, "K2") is False, "K2 ban đầu phải trống!"
    print("✓ K2 trước khi gia hạn: Trống (False)")

    # Khách gia hạn thêm 2 tiếng (12:30 -> 14:30), lấn sang K2
    add_extension(code2, room_id, test_date, "K2", "12:30", "14:30", 100000, hours=2)
    print("Đã thực hiện add_extension thêm 2 tiếng")

    # Sau khi gia hạn:
    # 1. K2 phải được đánh dấu là ĐÃ ĐẶT (booking_exists = True)
    assert booking_exists(room_id, test_date, "K2") is True, "K2 sau khi gia hạn phải thành BOOKED (True)!"
    print("✓ K2 sau khi gia hạn: ĐÃ ĐƯỢC KHÓA THÀNH CÔNG (booking_exists = True)")

    # 2. Khách khác cố đặt phòng K2 cùng ngày phải bị từ chối
    try:
        create_booking(
            user_id=2,
            room_id=room_id,
            branch_id="BT",
            booking_date=test_date,
            khung_code="K2",
            start_time="13:00",
            end_time="16:00",
            guests=2,
            amount=150000,
            customer_name="Người Khác",
            customer_phone="0988888888",
        )
        assert False, "Lẽ ra phải chặn người khác đặt khung K2 khi đã bị gia hạn chiếm chỗ!"
    except ValueError as e:
        print(f"✓ Chặn đúng người khác đặt khung K2: {e}")

    # 3. Lễ tân list_bookings thấy thông tin gia hạn
    bks = list_bookings(branch_id="BT")
    target_bk = next((b for b in bks if b["booking_code"] == code2), None)
    assert target_bk is not None
    assert target_bk["end_time"] == "14:30", f"Giờ checkout phải là 14:30, thực tế: {target_bk['end_time']}"
    assert target_bk["extension_hours"] == 2, f"Số giờ gia hạn phải là 2, thực tế: {target_bk['extension_hours']}"
    assert target_bk["amount"] == 240000, f"Tổng tiền phải là 240k (140k + 100k), thực tế: {target_bk['amount']}"
    print(f"✓ Lễ tân thấy đơn: Giờ checkout mới={target_bk['end_time']}, Đã gia hạn={target_bk['extension_hours']}h, Tổng tiền={target_bk['amount']:,} ₫")

    # Dọn dẹp dữ liệu test
    with connect() as conn:
        conn.execute("DELETE FROM bookings WHERE room_id=? AND booking_date=?", (room_id, test_date))
        conn.execute("DELETE FROM booking_extensions WHERE room_id=? AND extension_date=?", (room_id, test_date))
        conn.execute("DELETE FROM transactions WHERE booking_code IN (?, ?)", (code1, code2))

    print("\n🎉 TẤT CẢ CÁC BÀI TEST NGHIỆP VỤ GIA HẠN THEO GIỜ ĐÃ VƯỢT QUA 100%!")


if __name__ == "__main__":
    run_tests()
