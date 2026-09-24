from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

try:
    from services.business_service import check_extension_availability, money, slot_info_for_room, validate_promotion
    from services.storage import (
        add_extension,
        add_review,
        cancel_booking,
        connect,
        create_booking,
        list_bookings,
        mark_paid,
    )
except ImportError:
    from business_service import check_extension_availability, money, slot_info_for_room, validate_promotion
    from storage import (
        add_extension,
        add_review,
        cancel_booking,
        connect,
        create_booking,
        list_bookings,
        mark_paid,
    )

router = APIRouter(prefix="/api", tags=["Bookings & Reviews"])


class CreateBookingRequest(BaseModel):
    user_id: int | None = None
    room_id: str
    branch_id: str = ""
    booking_date: str
    khung_code: str
    start_time: str
    end_time: str
    guests: int
    amount: int
    customer_name: str
    customer_phone: str
    customer_email: str = ""
    note: str = ""
    promo_code: str = ""
    discount_amount: int = 0


class ExtendBookingRequest(BaseModel):
    booking_code: str
    room_id: str
    extension_date: str
    khung_code: str
    start_time: str
    end_time: str
    amount: int
    hours: int = 1


class ReviewRequest(BaseModel):
    booking_code: str
    user_id: int
    rating: int
    content: str
    media_urls: str | None = ""


@router.post("/bookings")
def create_new_booking(req: CreateBookingRequest):
    try:
        branch_id = req.branch_id.strip() if req.branch_id else ""
        if not branch_id:
            branch_id = "BT" if "BT" in req.room_id else "TD" if "TD" in req.room_id else "PMH"

        # An toàn giá: không tin amount do client gửi — luôn tính lại từ bảng giá thật
        # theo (room_id, khung_code) để tổng tiền không thể bị chỉnh sửa từ phía client.
        slots = slot_info_for_room(req.room_id)
        slot = next((s for s in slots if s["khung_code"] == req.khung_code), None)
        if not slot or slot.get("price") is None:
            raise HTTPException(status_code=400, detail="Không tìm thấy giá hợp lệ cho phòng/khung giờ này.")
        original_price = slot["price"]
        amount = original_price
        discount_amount = 0

        # Xác thực mã khuyến mãi nếu khách nhập
        clean_promo = req.promo_code.strip().upper() if req.promo_code else ""
        if clean_promo:
            val_res = validate_promotion(
                code=clean_promo,
                room_id=req.room_id,
                booking_date=req.booking_date,
                khung_code=req.khung_code,
                original_amount=original_price,
                user_id=req.user_id,
            )
            if not val_res.get("valid"):
                raise HTTPException(status_code=400, detail=val_res.get("message", "Mã ưu đãi không hợp lệ."))
            discount_amount = val_res.get("discount_amount", 0)
            amount = val_res.get("final_amount", original_price)

        # BR-04: Tạo lượt đặt và giữ chỗ trong 10 phút
        code = create_booking(
            user_id=req.user_id,
            room_id=req.room_id,
            branch_id=branch_id,
            booking_date=req.booking_date,
            khung_code=req.khung_code,
            start_time=req.start_time,
            end_time=req.end_time,
            guests=req.guests,
            amount=amount,
            customer_name=req.customer_name,
            customer_phone=req.customer_phone,
            customer_email=req.customer_email,
            note=req.note,
            promo_code=clean_promo,
            discount_amount=discount_amount,
        )
        # Sinh mã VietQR động
        vietqr_url = (
            f"https://img.vietqr.io/image/MB-0909000001-compact2.png"
            f"?amount={amount}&addInfo={code}&accountName=COZYHOME%20VIETNAM"
        )
        return {
            "status": "ok",
            "booking_code": code,
            "amount": amount,
            "original_amount": original_price,
            "discount_amount": discount_amount,
            "promo_code": clean_promo,
            "vietqr_url": vietqr_url,
            "bank_name": "MBBank (Quân Đội)",
            "account_no": "0909000001",
            "account_name": "COZYHOME VIETNAM",
            "transfer_content": code,
            "hold_minutes": 10,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bookings/{booking_code}/pay")
def pay_booking(booking_code: str):
    try:
        mark_paid(booking_code)
        return {"status": "ok", "message": "Thanh toán thành công! Lượt đặt phòng đã được xác nhận."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/bookings/{booking_code}/cancellation-quote")
def get_cancellation_quote(booking_code: str):
    """UC-05.5: Hiển thị trước tỷ lệ và số tiền dự kiến được hoàn trước khi khách bấm xác nhận hủy."""
    with connect() as conn:
        row = conn.execute(
            "SELECT amount,payment_status,status,branch_id,booking_date,start_time,end_time FROM bookings WHERE booking_code=?",
            (booking_code,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy lượt đặt phòng.")

    row_dict = dict(row)
    status = row_dict["status"]
    if status in ("Đã check-in", "Đã hoàn tất", "Quá giờ - chưa checkout"):
        return {
            "can_cancel": False,
            "reason": "Lượt đặt đã bắt đầu hoặc hoàn tất lưu trú, không thể hủy tại bước này.",
            "status": status,
        }
    if status == "Đã hủy":
        return {
            "can_cancel": False,
            "reason": "Lượt đặt này đã được hủy trước đó.",
            "status": status,
        }

    try:
        from services.business_service import calculate_cancellation_refund
    except ImportError:
        from business_service import calculate_cancellation_refund

    is_paid = row_dict.get("payment_status") == "Đã thanh toán"
    calc = calculate_cancellation_refund(row_dict)
    refund = calc["refund_amount"] if is_paid else 0

    return {
        "can_cancel": True,
        "booking_code": booking_code,
        "is_paid": is_paid,
        "original_amount": calc["original_amount"],
        "hours_left": calc["hours_left"],
        "refund_rate": calc["refund_rate"] if is_paid else "0%",
        "refund_amount": refund,
        "tier": calc["tier"],
        "description": calc["description"],
        "time_estimate": calc["time_estimate"],
    }


@router.post("/bookings/{booking_code}/cancel")
def cancel_existing_booking(booking_code: str):
    try:
        # BR-05: Hủy phòng trước check-in và ghi nhận hoàn tiền theo mốc 24h / 12h
        refund = cancel_booking(booking_code)
        if refund > 0:
            msg = f"Đã hủy lượt đặt thành công. Khoản hoàn tiền {money(refund)} đã được ghi nhận và chuyển kế toán đối soát (hoàn trong 3–15 ngày làm việc)."
        else:
            msg = "Đã hủy lượt đặt phòng thành công."
        return {"status": "ok", "refund_amount": refund, "message": msg}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/bookings/{booking_code}/check-extension")
def check_booking_extension(booking_code: str, hours: int = 1):
    # Kiểm tra tính khả dụng và ràng buộc gia hạn theo giờ
    with connect() as conn:
        row = conn.execute(
            "SELECT room_id, booking_date, khung_code, status, end_time FROM bookings WHERE booking_code=?",
            (booking_code,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy lượt đặt phòng.")

    current_status = row["status"]
    # Ràng buộc chặt chẽ: không gia hạn khi hủy, hết hạn giữ chỗ, chưa thanh toán hoặc đã hoàn tất
    if current_status == "Đã hủy":
        return {
            "can_extend": False,
            "is_available": False,
            "reason": "Lượt đặt phòng này đã bị hủy, không thể thực hiện gia hạn thêm giờ.",
            "current_status": current_status,
        }
    if current_status == "Hết hạn giữ chỗ":
        return {
            "can_extend": False,
            "is_available": False,
            "reason": "Lượt đặt phòng đã hết hạn thời gian giữ chỗ 10 phút.",
            "current_status": current_status,
        }
    if current_status == "Chờ thanh toán":
        return {
            "can_extend": False,
            "is_available": False,
            "reason": "Lượt đặt phòng đang chờ thanh toán. Vui lòng thanh toán đơn gốc trước khi gia hạn.",
            "current_status": current_status,
        }
    if current_status == "Đã hoàn tất":
        return {
            "can_extend": False,
            "is_available": False,
            "reason": "Lượt lưu trú này đã check-out hoàn tất. Nếu muốn ở thêm vui lòng đặt lượt mới.",
            "current_status": current_status,
        }
    if current_status not in ("Đã xác nhận", "Chờ check-in", "Đã check-in", "Quá giờ - chưa checkout"):
        return {
            "can_extend": False,
            "is_available": False,
            "reason": f"Trạng thái '{current_status}' hiện không hỗ trợ gia hạn.",
            "current_status": current_status,
        }

    info = check_extension_availability(
        room_id=row["room_id"],
        current_date=row["booking_date"],
        current_khung=row["khung_code"],
        current_end_time=row["end_time"],
        hours=hours,
        booking_code=booking_code,
    )
    info["current_status"] = current_status
    info["booking_code"] = booking_code
    return info


@router.post("/bookings/extend")
def extend_existing_booking(req: ExtendBookingRequest):
    try:
        # BR-06: Gia hạn cùng phòng không phát sinh yêu cầu dọn phòng nối tiếp
        add_extension(
            booking_code=req.booking_code,
            room_id=req.room_id,
            extension_date=req.extension_date,
            khung_code=req.khung_code,
            start_time=req.start_time,
            end_time=req.end_time,
            amount=req.amount,
            hours=req.hours,
        )
        return {
            "status": "ok",
            "message": f"Gia hạn {req.hours} tiếng thành công! Giờ check-out mới: {req.end_time}. Khung tiếp theo ({req.khung_code}) đã được tự động giữ chỗ trên hệ thống.",
            "new_end_time": req.end_time,
            "amount": req.amount,
            "hours": req.hours,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/bookings")
def get_user_bookings(user_id: int | None = None, branch_id: str | None = None):
    rows = list_bookings(user_id=user_id, branch_id=branch_id)
    return {"bookings": rows}


@router.post("/reviews")
def submit_review(req: ReviewRequest):
    try:
        # BR-12: Chỉ đơn Đã hoàn tất mới được đánh giá
        add_review(req.booking_code, req.user_id, req.rating, req.content, req.media_urls or "")
        return {"status": "ok", "message": "Đã gửi đánh giá thành công. Cảm ơn phản hồi quý báu của bạn!"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/reviews/upload")
async def upload_review_image(file: UploadFile = File(...)):
    """
    Tải ảnh/video minh chứng cho phần Đánh giá trải nghiệm lưu trú (BR-12, UC-07).
    Lưu vào static/uploads và trả về URL truy cập tĩnh.
    """
    import os, uuid, shutil
    from datetime import datetime

    upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4"]:
        ext = ".jpg"

    safe_name = f"review_{uuid.uuid4().hex[:10]}_{int(datetime.now().timestamp())}{ext}"
    target_path = os.path.join(upload_dir, safe_name)

    with open(target_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {
        "status": "ok",
        "url": f"/static/uploads/{safe_name}",
        "filename": safe_name,
    }

