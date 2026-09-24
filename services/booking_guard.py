from __future__ import annotations

try:
    from services import storage
    from services.storage import check_and_update_overstays, cleanup_expired_otps, release_expired_holds
except ImportError:
    import storage
    from storage import check_and_update_overstays, cleanup_expired_otps, release_expired_holds


def run_system_maintenance() -> dict[str, int]:
    """Tự động kiểm tra và cập nhật các trạng thái thời gian thực:

    - BR-04: Giải phóng các phòng giữ chỗ quá 10 phút chưa thanh toán.
    - BR-08: Đánh dấu các phòng 'Quá giờ - chưa checkout' khi hết giờ lưu trú.
    - L9: Tự động dọn dẹp các mã OTP đã hết hạn hoặc đã dùng quá 24 giờ.
    """
    released = release_expired_holds()
    check_and_update_overstays()
    cleaned_otps = 0
    try:
        cleaned_otps = cleanup_expired_otps()
    except Exception:
        pass
    return {"released_holds": released, "cleaned_otps": cleaned_otps}
