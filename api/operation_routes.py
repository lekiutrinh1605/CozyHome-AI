from datetime import date, datetime, timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

try:
    from services.auth_guard import (
        enforce_branch_scope,
        get_current_user,
        record_audit,
        require_permission,
        require_role,
    )
    from services.business_service import (
        all_rooms,
        check_extension_availability,
        add_room,
        update_room,
        toggle_room_status,
        get_room_pricing_matrix,
        update_base_price,
        get_pricing_policies,
        update_pricing_policies,
        list_promotions,
        add_promotion,
        update_promotion,
        toggle_promotion_status,
        list_business_policies,
        add_business_policy,
        update_business_policy,
        toggle_business_policy,
    )
    from services.report_service import get_dashboard_report
    from services.storage import (
        add_extension,
        assign_slot_group_to_room,
        check_in_booking,
        check_out_booking,
        close_reconciliation_period,
        create_reconciliation_period,
        dashboard_metrics,
        escalate_review,
        get_booking_by_code,
        get_chain_branches_kpi,
        get_reconciliation_period,
        latest_room_operations,
        list_bookings,
        list_reconciliation_periods,
        list_reviews,
        list_transactions,
        list_users,
        reconcile_transaction,
        reconcile_transactions_batch,
        resolve_review,
        set_user_active,
        set_user_scope,
        unlock_user,
        update_booking_status,
        upsert_room_operation,
        connect,
    )
except ImportError:
    from auth_guard import (
        enforce_branch_scope,
        get_current_user,
        record_audit,
        require_permission,
        require_role,
    )
    from business_service import (
        all_rooms,
        check_extension_availability,
        add_room,
        update_room,
        toggle_room_status,
        get_room_pricing_matrix,
        update_base_price,
        get_pricing_policies,
        update_pricing_policies,
        list_promotions,
        add_promotion,
        update_promotion,
        toggle_promotion_status,
        list_business_policies,
        add_business_policy,
        update_business_policy,
        toggle_business_policy,
    )
    from report_service import get_dashboard_report
    from storage import (
        add_extension,
        assign_slot_group_to_room,
        check_in_booking,
        check_out_booking,
        close_reconciliation_period,
        create_reconciliation_period,
        dashboard_metrics,
        escalate_review,
        get_booking_by_code,
        get_chain_branches_kpi,
        get_reconciliation_period,
        latest_room_operations,
        list_bookings,
        list_reconciliation_periods,
        list_reviews,
        list_transactions,
        list_users,
        reconcile_transaction,
        reconcile_transactions_batch,
        resolve_review,
        set_user_active,
        set_user_scope,
        unlock_user,
        update_booking_status,
        upsert_room_operation,
        connect,
    )

router = APIRouter(prefix="/api/operations", tags=["Operations Portal"])


# -------------------------------------------------------------
# 1. Dashboard & Báo Cáo Vận Hành
# -------------------------------------------------------------
@router.get("/dashboard")
def get_ops_dashboard(
    branch_id: str | None = None,
    user: dict[str, Any] = Depends(get_current_user),
):
    """
    Dashboard vận hành cho nhân sự nội bộ (Lễ tân, Buồng phòng, Kế toán, Quản lý, Admin).
    Kiểm tra chặt chẽ Branch Scope: Lễ tân / Buồng phòng chỉ được lấy dữ liệu chi nhánh mình.
    """
    effective_branch = enforce_branch_scope(user, branch_id)
    m = dashboard_metrics(branch_id=effective_branch)
    txs = list_transactions(branch_id=effective_branch)
    bks = list_bookings(branch_id=effective_branch)
    return {
        "status": "ok",
        "branch_id": effective_branch,
        "metrics": m,
        "transactions": txs,
        "bookings": bks,
    }


@router.get("/report")
@router.get("/dashboard-report")
def get_ops_report(
    period: str = "30days",
    from_date: str | None = None,
    to_date: str | None = None,
    branch_id: str | None = None,
    user: dict[str, Any] = Depends(require_permission("dashboard.view_all")),
):
    """
    Báo cáo & Phân tích chuyên sâu chuỗi.
    Chỉ dành cho Quản lý chuỗi và Quản trị viên (dashboard.view_all).
    """
    try:
        report = get_dashboard_report(
            period=period,
            from_date=from_date,
            to_date=to_date,
            branch_id=branch_id if branch_id and branch_id != "ALL" else None,
        )

        normalized_branches = []
        for b in report.get("branch_performance", []):
            normalized_branches.append({
                "branch_id": b.get("branch_id"),
                "branch_name": b.get("branch_name"),
                "address": b.get("address", ""),
                "room_count": b.get("rooms_count", 0),
                "bookings": b.get("bookings_count", 0),
                "revenue": b.get("revenue", 0),
                "occupancy_rate": b.get("occupancy_rate", 0.0),
            })

        normalized_top_rooms = []
        for r in report.get("top_rooms", []):
            normalized_top_rooms.append({
                "room_id": r.get("room_id"),
                "room_code": r.get("room_id"),
                "room_name": r.get("room_name"),
                "branch_id": r.get("branch_id"),
                "room_type": r.get("room_type", "Standard"),
                "concept": r.get("concept", ""),
                "bookings": r.get("bookings_count", 0),
                "revenue": r.get("total_revenue", 0),
            })

        normalized_recent = []
        for b in report.get("recent_bookings", []):
            normalized_recent.append({
                "booking_code": b.get("booking_code"),
                "customer_name": b.get("customer_name"),
                "customer_phone": b.get("customer_phone"),
                "room_id": b.get("room_id"),
                "room_code": b.get("room_id"),
                "branch_id": b.get("branch_id"),
                "stay_type": b.get("stay_type"),
                "booking_date": b.get("booking_date"),
                "slot_id": b.get("khung_code"),
                "status": b.get("status"),
                "total_amount": b.get("amount", 0),
            })

        stay_types_dict = {}
        for st in report.get("stay_type_distribution", []):
            code = st.get("code", "other")
            stay_types_dict[code] = {
                "bookings": st.get("count", 0),
                "percentage": st.get("percentage", 0.0),
            }

        cm = report.get("cancellation_metrics", {})
        cancellation_norm = {
            "cancelled_bookings": cm.get("cancelled_bookings", 0),
            "cancellation_rate": cm.get("cancellation_rate", 0.0),
            "total_refunded_amount": cm.get("total_refunded_amount", 0),
            "refund_transactions": cm.get("refund_transactions", 0),
        }

        normalized_report = {
            "period": report.get("period"),
            "date_range": report.get("date_range"),
            "branch_id": report.get("branch_id"),
            "summary": report.get("summary"),
            "timeline": report.get("timeline"),
            "branch_performance": normalized_branches,
            "stay_types": stay_types_dict,
            "room_status": report.get("room_status"),
            "cancellation": cancellation_norm,
            "top_rooms": normalized_top_rooms,
            "recent_bookings": normalized_recent,
        }

        return {"status": "ok", "data": normalized_report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi truy xuất dữ liệu báo cáo: {str(e)}")


# -------------------------------------------------------------
# 2. Nghiệp Vụ Lễ Tân (Receptionist Operations)
# BẢO VỆ CHẶT CHẼ: Admin KHÔNG có quyền Check-in / Check-out
# -------------------------------------------------------------
@router.post("/check-in")
def api_check_in(
    req: dict[str, Any],
    request: Request,
    user: dict[str, Any] = Depends(require_permission("booking.check_in")),
):
    code = req.get("booking_code")
    if not code:
        raise HTTPException(status_code=400, detail="Thiếu mã đơn đặt phòng.")

    booking = get_booking_by_code(code)
    if not booking:
        raise HTTPException(status_code=404, detail="Không tìm thấy lượt đặt phòng.")

    # Kiểm tra Branch Scope: Lễ tân chỉ được check-in đơn của chi nhánh mình phụ trách
    enforce_branch_scope(user, booking["branch_id"])

    try:
        check_in_booking(code)
        try:
            today_str = date.today().isoformat()
            upsert_room_operation(
                room_id=booking["room_id"],
                branch_id=booking["branch_id"],
                status="Đang ở",
                note=f"Khách {booking['customer_name']} đã nhận phòng ({code})",
                updated_by=user.get("full_name", "Lễ tân")
            )
        except Exception:
            pass

        record_audit(
            request=request,
            user=user,
            action="CHECK_IN",
            entity_type="BOOKING",
            entity_id=code,
            description=f"Lễ tân hoàn tất Check-in cho đơn {code} (Phòng: {booking['room_id']}, Chi nhánh: {booking['branch_id']})",
            old_value=booking["status"],
            new_value="Đã check-in",
        )
        return {"status": "ok", "message": f"Đã Check-in thành công cho đơn {code}."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/check-out")
def api_check_out(
    req: dict[str, Any],
    request: Request,
    user: dict[str, Any] = Depends(require_permission("booking.check_out")),
):
    code = req.get("booking_code")
    if not code:
        raise HTTPException(status_code=400, detail="Thiếu mã đơn đặt phòng.")

    booking = get_booking_by_code(code)
    if not booking:
        raise HTTPException(status_code=404, detail="Không tìm thấy lượt đặt phòng.")

    # Kiểm tra Branch Scope
    enforce_branch_scope(user, booking["branch_id"])

    staff_name = user.get("full_name", "Lễ tân")
    try:
        check_out_booking(code, staff_name=staff_name)
        record_audit(
            request=request,
            user=user,
            action="CHECK_OUT",
            entity_type="BOOKING",
            entity_id=code,
            description=f"Lễ tân hoàn tất Check-out cho đơn {code}. Phòng {booking['room_id']} tự động chuyển sang trạng thái 'Cần dọn'.",
            old_value=booking["status"],
            new_value="Đã hoàn tất",
        )
        return {
            "status": "ok",
            "message": f"Đã Check-out thành công cho đơn {code}. Phòng tự động chuyển sang 'Cần dọn'.",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/booking-status")
def update_ops_booking_status(
    req: dict[str, Any],
    request: Request,
    user: dict[str, Any] = Depends(get_current_user),
):
    code = req.get("booking_code")
    status_val = req.get("status")
    if not code or not status_val:
        raise HTTPException(status_code=400, detail="Thiếu mã đơn hoặc trạng thái.")

    booking = get_booking_by_code(code)
    if not booking:
        raise HTTPException(status_code=404, detail="Không tìm thấy lượt đặt phòng.")

    # Kiểm tra quyền theo từng trạng thái cụ thể
    effective_role = user.get("effective_role", "")
    if status_val == "Đã check-in":
        if "booking.check_in" not in user.get("effective_perms", []):
            require_permission("booking.check_in")(request, user)
        enforce_branch_scope(user, booking["branch_id"])
    elif status_val == "Đã hoàn tất":
        if "booking.check_out" not in user.get("effective_perms", []):
            require_permission("booking.check_out")(request, user)
        enforce_branch_scope(user, booking["branch_id"])
    else:
        # Trạng thái khác chỉ dành cho Quản lý
        require_permission("review.handle")(request, user)

    update_booking_status(code, status_val)
    return {"status": "ok", "message": f"Đã cập nhật trạng thái đơn {code} sang '{status_val}'."}


@router.post("/emergency-extend")
def api_emergency_extend(
    req: dict[str, Any],
    request: Request,
    user: dict[str, Any] = Depends(require_permission("booking.check_in")),
):
    """
    Gia hạn lưu trú khẩn cấp tại quầy lễ tân (BR-06 & Nghiệp vụ Lễ tân tại quầy).
    Hỗ trợ thu tiền mặt, POS, VietQR quầy hoặc ghi nợ phòng.
    Khôi phục trạng thái từ 'Quá giờ - chưa checkout' về 'Đã check-in' ngay lập tức.
    """
    code = req.get("booking_code")
    hours = int(req.get("hours", 1))
    payment_method = req.get("payment_method", "Tiền mặt tại quầy")
    staff_note = req.get("note", "").strip()

    if not code:
        raise HTTPException(status_code=400, detail="Thiếu mã đơn đặt phòng.")

    booking = get_booking_by_code(code)
    if not booking:
        raise HTTPException(status_code=404, detail="Không tìm thấy lượt đặt phòng.")

    enforce_branch_scope(user, booking["branch_id"])

    # Kiểm tra tính khả dụng & lấy thông tin khung kế tiếp
    info = check_extension_availability(
        room_id=booking["room_id"],
        current_date=booking["booking_date"],
        current_khung=booking["khung_code"],
        current_end_time=booking["end_time"],
        hours=hours,
        booking_code=code,
    )

    if not info.get("can_extend"):
        raise HTTPException(status_code=400, detail=info.get("reason", "Khung giờ kế tiếp không khả dụng để gia hạn."))

    # Lấy thông tin option đã chọn
    opts = info.get("hourly_options", [])
    selected_opt = next((o for o in opts if o["hours"] == hours), None)
    new_end_time = selected_opt["end_time"] if selected_opt else info["new_end_time"]
    fee = selected_opt["amount"] if selected_opt else info["price"]

    staff_name = user.get("full_name") or user.get("email") or "Lễ tân"
    payment_status = "Đã thanh toán (Tại quầy)" if "Ghi nợ" not in payment_method else "Chờ thanh toán (Ghi nợ phòng)"

    try:
        add_extension(
            booking_code=code,
            room_id=booking["room_id"],
            extension_date=info["next_date"],
            khung_code=info["next_khung"],
            start_time=info["start_time"],
            end_time=new_end_time,
            amount=fee,
            hours=hours,
            payment_method=payment_method,
            payment_status=payment_status,
        )

        # Cập nhật trạng thái phòng vận hành
        try:
            today_str = date.today().isoformat()
            note_text = f"Lễ tân {staff_name} gia hạn khẩn +{hours}h đến {new_end_time} ({payment_method})"
            if staff_note:
                note_text += f". Ghi chú: {staff_note}"
            upsert_room_operation(
                room_id=booking["room_id"],
                branch_id=booking["branch_id"],
                status="Đang ở",
                note=note_text,
                updated_by=staff_name,
            )
        except Exception:
            pass

        record_audit(
            request=request,
            user=user,
            action="EMERGENCY_EXTEND",
            entity_type="BOOKING",
            entity_id=code,
            description=f"Lễ tân {staff_name} gia hạn khẩn cấp +{hours}h cho đơn {code} (Phòng: {booking['room_id']}). Giờ checkout mới: {new_end_time}. Phí: {fee:,} ₫ ({payment_method}).",
            old_value=f"Checkout: {booking['end_time']}, Trạng thái: {booking['status']}",
            new_value=f"Checkout: {new_end_time}, Trạng thái: Đã check-in",
        )

        return {
            "status": "ok",
            "message": f"Đã gia hạn khẩn cấp +{hours} tiếng thành công cho đơn {code}! Giờ check-out mới: {new_end_time}.",
            "new_end_time": new_end_time,
            "hours": hours,
            "amount": fee,
            "payment_method": payment_method,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# -------------------------------------------------------------
# 3. Nghiệp Vụ Buồng Phòng (Housekeeping)
# BẢO VỆ CHẶT CHẼ: Admin KHÔNG có quyền cập nhật dọn phòng
# -------------------------------------------------------------
@router.get("/housekeeping")
def get_housekeeping(
    branch_id: str | None = None,
    user: dict[str, Any] = Depends(get_current_user),
):
    effective_branch = enforce_branch_scope(user, branch_id)
    rooms = [r for r in all_rooms() if not effective_branch or r["branch_id"] == effective_branch]
    ops = latest_room_operations(effective_branch)
    today_str = date.today().isoformat()
    booking_map: dict[str, list[dict[str, Any]]] = {}
    try:
        with connect() as conn:
            active_bookings = conn.execute(
                """SELECT booking_code, room_id, customer_name, customer_phone, 
                          khung_code, start_time, end_time, status, actual_checkin, actual_checkout 
                   FROM bookings 
                   WHERE booking_date >= ? AND status IN ('Đã xác nhận', 'Đã check-in', 'Quá giờ - chưa checkout', 'Đã hoàn tất')
                   ORDER BY id DESC""",
                (today_str,)
            ).fetchall()
            for b in active_bookings:
                r_id = b["room_id"]
                if r_id not in booking_map:
                    booking_map[r_id] = []
                booking_map[r_id].append(dict(b))
    except Exception:
        pass

    return {
        "status": "ok", 
        "branch_id": effective_branch, 
        "rooms": rooms, 
        "operations": ops,
        "today_bookings": booking_map
    }


@router.post("/housekeeping")
def set_housekeeping(
    req: dict[str, Any],
    request: Request,
    user: dict[str, Any] = Depends(require_permission("housekeeping.update")),
):
    room_id = req.get("room_id")
    branch_id = req.get("branch_id")
    new_status = req.get("status")
    if not room_id or not branch_id or not new_status:
        raise HTTPException(status_code=400, detail="Thiếu thông tin phòng hoặc trạng thái.")

    # Kiểm tra Branch Scope: Nhân viên buồng phòng chỉ dọn phòng thuộc chi nhánh được gán
    enforce_branch_scope(user, branch_id)

    staff_name = user.get("full_name", "Nhân viên buồng phòng")
    note = req.get("note", f"Cập nhật trạng thái sang '{new_status}'")
    upsert_room_operation(room_id, branch_id, new_status, note, staff_name)

    record_audit(
        request=request,
        user=user,
        action="HOUSEKEEPING_STATUS_CHANGE",
        entity_type="ROOM",
        entity_id=room_id,
        description=f"Nhân viên buồng phòng cập nhật phòng {room_id} ({branch_id}) sang '{new_status}' (Ghi chú: {note})",
        new_value=new_status,
    )
    return {"status": "ok", "message": f"Đã cập nhật buồng phòng {room_id} sang '{new_status}'."}


# -------------------------------------------------------------
# 4. Nghiệp Vụ Kế Toán (Accounting & Reconciliation)
# BẢO VỆ CHẶT CHẼ: Admin KHÔNG có quyền đối soát giao dịch
# -------------------------------------------------------------
@router.post("/reconcile")
def api_reconcile(
    req: dict[str, Any],
    request: Request,
    user: dict[str, Any] = Depends(require_permission("transaction.reconcile")),
):
    tx_id = req.get("tx_id")
    if not tx_id:
        raise HTTPException(status_code=400, detail="Thiếu ID giao dịch cần đối soát.")

    staff_name = user.get("full_name", "Kế toán")
    try:
        reconcile_transaction(int(tx_id), staff_name)
        record_audit(
            request=request,
            user=user,
            action="RECONCILE_TRANSACTION",
            entity_type="TRANSACTION",
            entity_id=str(tx_id),
            description=f"Kế toán {staff_name} đã xác nhận đối soát thành công giao dịch #{tx_id}",
            new_value="Đã đối soát",
        )
        return {"status": "ok", "message": f"Đã hoàn tất đối soát giao dịch #{tx_id}."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# -------------------------------------------------------------
# 5. Nghiệp Vụ Quản Lý Chuỗi (Chain Manager)
# -------------------------------------------------------------
@router.post("/rooms/slot-group")
def api_assign_slot_group(
    req: dict[str, Any],
    request: Request,
    user: dict[str, Any] = Depends(require_permission("business_config.update")),
):
    room_id = req.get("room_id")
    slot_group = req.get("slot_group_id")
    if not room_id or not slot_group:
        raise HTTPException(status_code=400, detail="Thiếu mã phòng hoặc mã nhóm khung giờ.")

    assign_slot_group_to_room(room_id, slot_group)
    record_audit(
        request=request,
        user=user,
        action="BUSINESS_CONFIG_CHANGE",
        entity_type="ROOM_SLOT",
        entity_id=room_id,
        description=f"Quản lý chuỗi cấu hình gán nhóm khung giờ '{slot_group}' cho phòng {room_id}",
        new_value=slot_group,
    )
    return {"status": "ok", "message": f"Đã gán nhóm {slot_group} cho phòng {room_id} thành công."}


@router.post("/escalate-review")
def api_escalate_review(
    req: dict[str, Any],
    request: Request,
    user: dict[str, Any] = Depends(require_permission("review.escalate")),
):
    rev_id = req.get("review_id")
    note = req.get("note", "")
    if not rev_id or not note.strip():
        raise HTTPException(status_code=400, detail="Thiếu ID đánh giá hoặc ghi chú khiếu nại.")

    escalate_review(int(rev_id), note.strip())
    record_audit(
        request=request,
        user=user,
        action="REVIEW_ESCALATE",
        entity_type="REVIEW",
        entity_id=str(rev_id),
        description=f"Lễ tân chuyển khiếu nại đánh giá #{rev_id} lên Quản lý chuỗi: {note.strip()}",
    )
    return {"status": "ok", "message": "Đã chuyển khiếu nại lên Quản lý chuỗi thành công!"}


@router.post("/resolve-review")
def api_resolve_review(
    req: dict[str, Any],
    request: Request,
    user: dict[str, Any] = Depends(require_permission("review.handle")),
):
    rev_id = req.get("review_id")
    note = req.get("resolution_note", "")
    comp_type = req.get("compensation_type", "NONE")
    comp_detail = req.get("compensation_detail", "")

    if not rev_id:
        raise HTTPException(status_code=400, detail="Thiếu ID đánh giá/khiếu nại.")
    if not note.strip():
        raise HTTPException(status_code=400, detail="Vui lòng nhập phương án / ghi chú giải quyết khiếu nại.")

    manager_name = user.get("full_name") or user.get("email") or "Quản lý chuỗi"
    resolve_review(
        review_id=int(rev_id),
        resolution_note=note.strip(),
        resolved_by=manager_name,
        compensation_type=comp_type,
        compensation_detail=comp_detail.strip(),
    )
    record_audit(
        request=request,
        user=user,
        action="REVIEW_RESOLVE",
        entity_type="REVIEW",
        entity_id=str(rev_id),
        description=f"Quản lý chuỗi ({manager_name}) đã giải quyết khiếu nại #{rev_id}: {note.strip()} (Hình thức: {comp_type})",
    )
    return {"status": "ok", "message": f"Đã giải quyết khiếu nại #{rev_id} thành công!"}


@router.get("/reviews")
def api_get_reviews(
    branch_id: str | None = None,
    escalated_only: bool = False,
    resolved_status: str = "all",
    user: dict[str, Any] = Depends(get_current_user),
):
    effective_branch = enforce_branch_scope(user, branch_id)
    return {"reviews": list_reviews(effective_branch, escalated_only, resolved_status)}


@router.get("/manager/branches-kpi")
def api_get_manager_branches_kpi(
    user: dict[str, Any] = Depends(require_permission("dashboard.view_all")),
):
    """Tổng hợp KPI 3 chi nhánh dành cho Quản lý chuỗi và Admin"""
    data = get_chain_branches_kpi()
    return {"status": "ok", "data": data}


# -------------------------------------------------------------
# PHÂN HỆ QUẢN LÝ DỊCH VỤ LƯU TRÚ (UC-03) & CHÍNH SÁCH KINH DOANH (UC-04)
# Dành cho Quản lý chuỗi và Quản trị viên
# -------------------------------------------------------------

# 1. QUẢN LÝ DỊCH VỤ LƯU TRÚ (UC-03)
@router.get("/manager/rooms")
def api_manager_get_rooms(
    branch_id: str | None = None,
    room_type: str | None = None,
    user: dict[str, Any] = Depends(require_permission("business_config.view")),
):
    """UC-03: Lấy danh sách toàn bộ phòng và chi tiết vận hành"""
    import json
    from pathlib import Path
    img_path = Path(__file__).resolve().parent.parent / "static" / "images" / "rooms" / "room_images.json"
    imgs = {}
    try:
        if img_path.exists():
            imgs = json.loads(img_path.read_text(encoding="utf-8"))
    except Exception:
        pass

    rooms = all_rooms()
    res = []
    for r in rooms:
        if branch_id and branch_id != "ALL" and r["branch_id"] != branch_id:
            continue
        if room_type and room_type != "ALL" and r["room_type"] != room_type:
            continue
        item = dict(r)
        item["images"] = imgs.get(r["room_id"], [])
        res.append(item)
    return {"status": "ok", "rooms": res}


@router.post("/manager/rooms")
def api_manager_create_room(
    room_data: dict[str, Any],
    request: Request,
    user: dict[str, Any] = Depends(require_permission("business_config.update")),
):
    """UC-03.1: Thêm phòng mới"""
    try:
        new_room = add_room(room_data)
        record_audit(
            request=request,
            user=user,
            action="ROOM_CREATE",
            entity_type="ROOM",
            entity_id=new_room["room_id"],
            description=f"Quản lý chuỗi tạo mới phòng {new_room['room_id']} ({new_room['room_name']}) tại {new_room['branch_name']}",
        )
        return {"status": "ok", "message": f"Tạo mới phòng '{new_room['room_id']}' thành công!", "room": new_room}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@router.put("/manager/rooms/{room_id}")
def api_manager_update_room(
    room_id: str,
    room_data: dict[str, Any],
    request: Request,
    user: dict[str, Any] = Depends(require_permission("business_config.update")),
):
    """UC-03.2: Cập nhật thông tin phòng"""
    try:
        updated = update_room(room_id, room_data)
        record_audit(
            request=request,
            user=user,
            action="ROOM_UPDATE",
            entity_type="ROOM",
            entity_id=room_id,
            description=f"Quản lý chuỗi cập nhật thông tin phòng {room_id}",
        )
        return {"status": "ok", "message": f"Cập nhật thông tin phòng '{room_id}' thành công!", "room": updated}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@router.post("/manager/rooms/{room_id}/status")
def api_manager_toggle_room_status(
    room_id: str,
    req: dict[str, Any] = None,
    request: Request = None,
    user: dict[str, Any] = Depends(require_permission("business_config.update")),
):
    """UC-03.3: Ngừng hoạt động / Tái kích hoạt phòng"""
    try:
        new_status = req.get("status") if req else None
        target = toggle_room_status(room_id, new_status)
        record_audit(
            request=request,
            user=user,
            action="ROOM_STATUS_TOGGLE",
            entity_type="ROOM",
            entity_id=room_id,
            description=f"Quản lý chuỗi chuyển trạng thái phòng {room_id} thành '{target['operational_status']}'",
        )
        return {"status": "ok", "message": f"Đã chuyển trạng thái phòng '{room_id}' thành '{target['operational_status']}'", "room": target}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


# 2. QUẢN LÝ CHÍNH SÁCH GIÁ & PHỤ THU (UC-04.1)
@router.get("/manager/pricing")
def api_manager_get_pricing(
    user: dict[str, Any] = Depends(require_permission("business_config.view")),
):
    """UC-04.1: Xem ma trận giá và cấu hình phụ thu"""
    data = get_room_pricing_matrix()
    return {"status": "ok", "data": data}


@router.post("/manager/pricing/adjust")
def api_manager_adjust_base_price(
    req: dict[str, Any],
    request: Request,
    user: dict[str, Any] = Depends(require_permission("business_config.update")),
):
    """UC-04.1: Điều chỉnh giá cơ sở theo Hạng phòng, Chi nhánh và Khung giờ"""
    room_type = req.get("room_type", "")
    branch_id = req.get("branch_id", "ALL")
    khung_code = req.get("khung_code", "")
    new_price = req.get("new_price")
    if new_price is None or int(new_price) < 0:
        raise HTTPException(status_code=400, detail="Mức giá mới không hợp lệ.")
    
    cnt = update_base_price(room_type, branch_id, khung_code, int(new_price))
    record_audit(
        request=request,
        user=user,
        action="PRICE_ADJUST",
        entity_type="PRICING",
        entity_id=f"{room_type}_{branch_id}_{khung_code}",
        description=f"Quản lý chuỗi điều chỉnh giá cơ sở: {room_type or 'Tất cả'} - Chi nhánh {branch_id} - Khung {khung_code or 'Tất cả'}: {int(new_price):,} ₫ ({cnt} bản ghi cập nhật)",
    )
    return {"status": "ok", "message": f"Đã cập nhật mức giá mới cho {cnt} cấu hình phòng!", "updated_count": cnt}


@router.post("/manager/pricing/surcharges")
def api_manager_update_surcharges(
    req: dict[str, Any],
    request: Request,
    user: dict[str, Any] = Depends(require_permission("business_config.update")),
):
    """UC-04.1: Cập nhật cấu hình phụ thu cuối tuần, lễ tết, quá giờ"""
    updated = update_pricing_policies(req, updated_by=user.get("full_name") or "Quản lý chuỗi")
    record_audit(
        request=request,
        user=user,
        action="SURCHARGE_UPDATE",
        entity_type="PRICING_POLICY",
        entity_id="GLOBAL",
        description=f"Quản lý chuỗi cập nhật chính sách phụ thu kinh doanh",
    )
    return {"status": "ok", "message": "Cập nhật chính sách phụ thu thành công!", "policies": updated}


# 3. QUẢN LÝ CHƯƠNG TRÌNH KHUYẾN MÃI (UC-04.2, UC-04.3, UC-04.4)
@router.get("/manager/promotions")
def api_manager_get_promotions(
    user: dict[str, Any] = Depends(require_permission("business_config.view")),
):
    """UC-04.2..4: Lấy danh sách toàn bộ khuyến mãi (kể cả tạm ngưng)"""
    promos = list_promotions()
    return {"status": "ok", "promotions": promos}


@router.post("/manager/promotions")
def api_manager_add_promotion(
    promo: dict[str, Any],
    request: Request,
    user: dict[str, Any] = Depends(require_permission("business_config.update")),
):
    """UC-04.2: Thêm mới chương trình khuyến mãi"""
    try:
        new_p = add_promotion(promo)
        record_audit(
            request=request,
            user=user,
            action="PROMO_CREATE",
            entity_type="PROMOTION",
            entity_id=new_p["code"],
            description=f"Quản lý chuỗi tạo khuyến mãi mới: {new_p['code']} ({new_p['name']})",
        )
        return {"status": "ok", "message": f"Thêm khuyến mãi '{new_p['code']}' thành công!", "promotion": new_p}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@router.put("/manager/promotions/{code}")
def api_manager_update_promotion(
    code: str,
    promo: dict[str, Any],
    request: Request,
    user: dict[str, Any] = Depends(require_permission("business_config.update")),
):
    """UC-04.3: Cập nhật chương trình khuyến mãi"""
    try:
        updated = update_promotion(code, promo)
        record_audit(
            request=request,
            user=user,
            action="PROMO_UPDATE",
            entity_type="PROMOTION",
            entity_id=code,
            description=f"Quản lý chuỗi cập nhật khuyến mãi: {code}",
        )
        return {"status": "ok", "message": f"Cập nhật khuyến mãi '{code}' thành công!", "promotion": updated}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@router.post("/manager/promotions/{code}/toggle")
def api_manager_toggle_promotion(
    code: str,
    request: Request,
    user: dict[str, Any] = Depends(require_permission("business_config.update")),
):
    """UC-04.4: Bật / Tắt trạng thái khuyến mãi"""
    try:
        target = toggle_promotion_status(code)
        st_text = "kích hoạt" if target.get("active") else "tạm ngừng"
        record_audit(
            request=request,
            user=user,
            action="PROMO_TOGGLE",
            entity_type="PROMOTION",
            entity_id=code,
            description=f"Quản lý chuỗi {st_text} chương trình khuyến mãi: {code}",
        )
        return {"status": "ok", "message": f"Đã {st_text} khuyến mãi '{code}'!", "promotion": target}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


# 4. QUẢN LÝ CHÍNH SÁCH KINH DOANH (UC-04.5, UC-04.6, UC-04.7)
@router.get("/manager/policies")
def api_manager_get_policies(
    user: dict[str, Any] = Depends(require_permission("business_config.view")),
):
    """UC-04.5..7: Lấy danh sách quy định & chính sách kinh doanh"""
    policies = list_business_policies()
    return {"status": "ok", "policies": policies}


@router.post("/manager/policies")
def api_manager_add_policy(
    policy_data: dict[str, Any],
    request: Request,
    user: dict[str, Any] = Depends(require_permission("business_config.update")),
):
    """UC-04.5: Thêm điều khoản chính sách kinh doanh mới"""
    try:
        created = add_business_policy(policy_data, created_by=user.get("full_name") or "Quản lý chuỗi")
        record_audit(
            request=request,
            user=user,
            action="POLICY_CREATE",
            entity_type="POLICY",
            entity_id=created["policy_id"],
            description=f"Quản lý chuỗi ban hành chính sách mới: {created['policy_id']} ({created['title']})",
        )
        return {"status": "ok", "message": f"Ban hành chính sách '{created['policy_id']}' thành công!", "policy": created}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@router.put("/manager/policies/{policy_id}")
def api_manager_update_policy(
    policy_id: str,
    policy_data: dict[str, Any],
    request: Request,
    user: dict[str, Any] = Depends(require_permission("business_config.update")),
):
    """UC-04.6: Cập nhật điều khoản chính sách kinh doanh"""
    try:
        updated = update_business_policy(policy_id, policy_data, updated_by=user.get("full_name") or "Quản lý chuỗi")
        record_audit(
            request=request,
            user=user,
            action="POLICY_UPDATE",
            entity_type="POLICY",
            entity_id=policy_id,
            description=f"Quản lý chuỗi cập nhật chính sách {policy_id} lên phiên bản {updated['version']}",
        )
        return {"status": "ok", "message": f"Cập nhật chính sách '{policy_id}' thành công!", "policy": updated}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@router.post("/manager/policies/{policy_id}/toggle")
def api_manager_toggle_policy(
    policy_id: str,
    request: Request,
    user: dict[str, Any] = Depends(require_permission("business_config.update")),
):
    """UC-04.7: Bật / Tắt hiệu lực chính sách kinh doanh"""
    try:
        target = toggle_business_policy(policy_id)
        st_text = "áp dụng" if target.get("active") else "ngừng áp dụng"
        record_audit(
            request=request,
            user=user,
            action="POLICY_TOGGLE",
            entity_type="POLICY",
            entity_id=policy_id,
            description=f"Quản lý chuỗi chuyển trạng thái chính sách {policy_id} sang '{st_text}'",
        )
        return {"status": "ok", "message": f"Đã chuyển chính sách '{policy_id}' sang '{st_text}'!", "policy": target}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))



# -------------------------------------------------------------
# 6. Legacy / User Admin Compatibility Endpoints
# -------------------------------------------------------------
@router.get("/users")
def get_all_users(user: dict[str, Any] = Depends(require_permission("user.view"))):
    return {"users": list_users()}


@router.post("/users/{user_id}/unlock")
def api_unlock_user(
    user_id: int,
    request: Request,
    user: dict[str, Any] = Depends(require_permission("user.unlock")),
):
    unlock_user(user_id)
    record_audit(
        request=request,
        user=user,
        action="ADMIN_UNLOCK_USER",
        entity_type="USER",
        entity_id=str(user_id),
        description=f"Quản trị viên đã mở khóa tài khoản #{user_id}",
    )
    return {"status": "ok", "message": "Đã mở khóa tài khoản thành công!"}


@router.post("/users/{user_id}")
def update_user_role_scope(
    user_id: int,
    req: dict[str, Any],
    request: Request,
    user: dict[str, Any] = Depends(require_permission("user.assign_role")),
):
    new_role = req.get("role")
    new_branch = req.get("branch_id")
    if not new_role:
        raise HTTPException(status_code=400, detail="Thiếu vai trò cần phân quyền.")

    if new_role in ("Lễ tân", "Buồng phòng", "Nhân viên buồng phòng") and not new_branch:
        raise HTTPException(status_code=400, detail=f"Vai trò '{new_role}' bắt buộc phải chọn chi nhánh phân công.")

    set_user_scope(user_id, new_role, new_branch)
    if "active" in req:
        set_user_active(user_id, bool(req["active"]))

    record_audit(
        request=request,
        user=user,
        action="ADMIN_ASSIGN_ROLE",
        entity_type="USER",
        entity_id=str(user_id),
        description=f"Phân quyền tài khoản #{user_id}: Vai trò '{new_role}', Chi nhánh '{new_branch or 'Toàn chuỗi'}'",
    )
    return {"status": "ok", "message": "Cập nhật phân quyền người dùng thành công."}


# -------------------------------------------------------------
# 6. PHÂN HỆ KẾ TOÁN & ĐỐI SOÁT DÒNG TIỀN (ACCOUNTING PORTAL)
# Nghiệp vụ: BR-09, UC-06: Xem giao dịch, tra cứu đơn, hoàn tiền,
# đối soát giao dịch, doanh thu theo ngày/tháng/chi nhánh/loại phòng, xuất báo cáo.
# -------------------------------------------------------------

def _resolve_acc_dates(period: str, from_date: str | None = None, to_date: str | None = None) -> tuple[str, str]:
    today = date.today()
    if period == "today":
        return today.isoformat(), today.isoformat()
    elif period == "7days":
        return (today - timedelta(days=6)).isoformat(), today.isoformat()
    elif period == "month":
        start = today.replace(day=1)
        next_month = today.replace(day=28) + timedelta(days=4)
        end = next_month - timedelta(days=next_month.day)
        return start.isoformat(), end.isoformat()
    elif period == "custom" and from_date and to_date:
        return from_date, to_date
    else:  # 30days default
        return (today - timedelta(days=29)).isoformat(), today.isoformat()


@router.get("/accounting/overview")
def get_accounting_overview(
    period: str = "30days",
    from_date: str | None = None,
    to_date: str | None = None,
    branch_id: str | None = None,
    user: dict[str, Any] = Depends(require_permission("transaction.view")),
):
    """
    Tổng hợp các chỉ số KPI tài chính cho Kế toán
    """
    start_str, end_str = _resolve_acc_dates(period, from_date, to_date)
    tx_start = f"{start_str}T00:00:00"
    tx_end = f"{end_str}T23:59:59"

    with connect() as conn:
        tx_where = "WHERE t.created_at >= ? AND t.created_at <= ?"
        params: list[Any] = [tx_start, tx_end]
        if branch_id and branch_id != "ALL":
            tx_where += " AND b.branch_id = ?"
            params.append(branch_id)

        rows = conn.execute(
            f"""
            SELECT t.*, b.branch_id, b.room_id
            FROM transactions t
            LEFT JOIN bookings b ON t.booking_code = b.booking_code
            {tx_where}
            ORDER BY t.id DESC
            """,
            params,
        ).fetchall()
        tx_list = [dict(r) for r in rows]

    gross_paid = sum(t["amount"] for t in tx_list if t["tx_type"] in ("Thanh toán", "Gia hạn") and t["status"] in ("Thành công", "Đã đối soát"))
    total_refunds = sum(abs(t["amount"]) for t in tx_list if t["tx_type"] == "Hoàn tiền")
    net_revenue = max(0, gross_paid - total_refunds)

    reconciled_txs = [t for t in tx_list if t["reconciled"] == 1]
    pending_txs = [t for t in tx_list if t["reconciled"] == 0]

    reconciled_amount = sum(t["amount"] for t in reconciled_txs if t["amount"] > 0)
    pending_amount = sum(t["amount"] for t in pending_txs if t["amount"] > 0)

    refund_txs = [t for t in tx_list if t["tx_type"] == "Hoàn tiền"]

    return {
        "status": "ok",
        "period": period,
        "date_range": {"from": start_str, "to": end_str},
        "branch_id": branch_id or "ALL",
        "summary": {
            "net_revenue": net_revenue,
            "gross_revenue": gross_paid,
            "total_refunds": total_refunds,
            "total_transactions": len(tx_list),
            "reconciled_count": len(reconciled_txs),
            "reconciled_amount": reconciled_amount,
            "pending_count": len(pending_txs),
            "pending_amount": pending_amount,
            "refund_count": len(refund_txs),
        }
    }


# -------------------------------------------------------------
# Reconciliation Periods & Matching (UC-08.2)
# -------------------------------------------------------------
@router.get("/accounting/periods")
def get_accounting_periods(
    user: dict[str, Any] = Depends(require_permission("transaction.view")),
):
    """
    Danh sách các kỳ đối soát theo UC-08.2 kèm số liệu tổng hợp động.
    """
    periods = list_reconciliation_periods()
    with connect() as conn:
        all_tx = conn.execute("SELECT id, amount, tx_type, status, reconciled, created_at FROM transactions").fetchall()

    enriched = []
    for p in periods:
        from_str = p["from_date"] + "T00:00:00"
        to_str = p["to_date"] + "T23:59:59"
        txs_in_p = [t for t in all_tx if from_str <= t["created_at"] <= to_str]
        
        tot_cnt = len(txs_in_p)
        rec_cnt = sum(1 for t in txs_in_p if t["reconciled"] == 1)
        tot_amt = sum(t["amount"] for t in txs_in_p if t["tx_type"] in ("Thanh toán", "Gia hạn"))
        
        p_dict = dict(p)
        p_dict["is_closed"] = 1 if p["status"] == "Đã khóa sổ" else 0
        p_dict["tx_count"] = tot_cnt
        p_dict["total_tx_count"] = tot_cnt
        p_dict["reconciled_count"] = rec_cnt
        p_dict["pending_count"] = tot_cnt - rec_cnt
        p_dict["total_amount"] = tot_amt
        p_dict["total_revenue"] = tot_amt
        enriched.append(p_dict)

    return {"status": "ok", "periods": enriched}


@router.post("/accounting/periods/close")
def post_close_accounting_period(
    req: dict[str, Any],
    request: Request,
    user: dict[str, Any] = Depends(require_permission("transaction.reconcile")),
):
    """
    Khóa sổ & Xác nhận kỳ đối soát (UC-08.2 Bước 6-7).
    Ghi nhận thời điểm, người chốt và lưu vết kiểm toán.
    """
    period_code = req.get("period_code")
    note = req.get("note", "").strip()
    if not period_code:
        raise HTTPException(status_code=400, detail="Thiếu mã kỳ đối soát.")

    staff_name = user.get("full_name") or user.get("email") or "Kế toán"

    # Kiểm tra xem kỳ còn giao dịch chưa đối soát hay không
    period = get_reconciliation_period(period_code)
    if not period:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy kỳ đối soát {period_code}.")

    if period["status"] == "Đã khóa sổ":
        raise HTTPException(status_code=400, detail=f"Kỳ {period_code} đã được khóa sổ trước đó bởi {period.get('closed_by')} lúc {period.get('closed_at')}.")

    from_str = period["from_date"] + "T00:00:00"
    to_str = period["to_date"] + "T23:59:59"

    with connect() as conn:
        pending_rows = conn.execute(
            "SELECT count(*) FROM transactions WHERE created_at >= ? AND created_at <= ? AND reconciled = 0",
            (from_str, to_str)
        ).fetchone()[0]

    # Cho phép khóa sổ nhưng ghi rõ cảnh báo nếu còn giao dịch chưa đối soát
    if not note and pending_rows > 0:
        note = f"Khóa sổ kỳ đối soát khi còn {pending_rows} giao dịch chờ xử lý."
    elif not note:
        note = "Đã đối chiếu khớp đúng 100% toàn bộ giao dịch trong kỳ."

    updated = close_reconciliation_period(period_code, staff_name, note)

    record_audit(
        request=request,
        user=user,
        action="CLOSE_RECONCILIATION_PERIOD",
        entity_type="RECONCILIATION_PERIOD",
        entity_id=period_code,
        description=f"Kế toán {staff_name} đã khóa sổ & xác nhận kỳ đối soát '{period['period_name']}' ({period_code}). Ghi chú: {note}",
        old_value="Đang mở",
        new_value="Đã khóa sổ",
    )

    return {
        "status": "ok",
        "message": f"Đã khóa sổ & xác nhận thành công kỳ đối soát '{period['period_name']}'.",
        "period": updated,
        "unreconciled_warning": pending_rows if pending_rows > 0 else None,
    }


@router.post("/accounting/periods/create")
def post_create_accounting_period(
    req: dict[str, Any],
    request: Request,
    user: dict[str, Any] = Depends(require_permission("transaction.reconcile")),
):
    """
    Tạo kỳ đối soát tùy chỉnh mới
    """
    period_code = req.get("period_code", "").strip()
    period_name = req.get("period_name", "").strip()
    from_date = req.get("from_date", "").strip()
    to_date = req.get("to_date", "").strip()
    note = req.get("note", "").strip()

    if not period_name or not from_date or not to_date:
        raise HTTPException(status_code=400, detail="Vui lòng cung cấp đầy đủ tên kỳ và khoảng ngày đối soát.")

    if not period_code:
        period_code = f"KY-{from_date.replace('-', '')}-{to_date.replace('-', '')}"

    try:
        created = create_reconciliation_period(period_code, period_name, from_date, to_date, note)
        return {"status": "ok", "message": f"Đã tạo kỳ đối soát '{period_name}' thành công.", "period": created}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/accounting/transactions")
def get_accounting_transactions(
    period_code: str | None = None,
    tx_type: str | None = None,
    reconciled: int | None = None,
    match_filter: str | None = None,
    branch_id: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    search: str | None = None,
    user: dict[str, Any] = Depends(require_permission("transaction.view")),
):
    """
    Danh sách giao dịch chi tiết phục vụ đối soát theo kỳ, đối chiếu giao dịch và nhận diện chênh lệch (UC-08.2).
    """
    room_map = {r["room_id"]: r for r in all_rooms()}
    branch_names = {"BT": "Bến Thành", "TD": "Thảo Điền", "PMH": "Phú Mỹ Hưng"}

    # Nếu có chọn kỳ đối soát, lấy phạm vi ngày của kỳ
    active_period = None
    if period_code and period_code != "all":
        active_period = get_reconciliation_period(period_code)
        if active_period:
            from_date = active_period["from_date"]
            to_date = active_period["to_date"]

    sql = """
        SELECT t.*, 
               b.room_id, b.branch_id, b.customer_name, b.customer_phone, 
               b.booking_date, b.khung_code, b.status AS booking_status,
               b.amount AS booking_amount, b.created_at AS booking_created_at
        FROM transactions t
        LEFT JOIN bookings b ON t.booking_code = b.booking_code
        WHERE 1=1
    """
    params: list[Any] = []

    if tx_type and tx_type != "ALL":
        sql += " AND t.tx_type = ?"
        params.append(tx_type)

    if reconciled is not None:
        sql += " AND t.reconciled = ?"
        params.append(reconciled)

    if branch_id and branch_id != "ALL":
        sql += " AND b.branch_id = ?"
        params.append(branch_id)

    if from_date:
        sql += " AND t.created_at >= ?"
        params.append(f"{from_date}T00:00:00")

    if to_date:
        sql += " AND t.created_at <= ?"
        params.append(f"{to_date}T23:59:59")

    sql += " ORDER BY t.id DESC"

    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
        # Tính tổng thanh toán của từng đơn để đối chiếu chính xác
        all_paid_rows = conn.execute(
            "SELECT booking_code, SUM(amount) as total_paid FROM transactions WHERE tx_type IN ('Thanh toán', 'Gia hạn') AND status IN ('Thành công', 'Đã đối soát') GROUP BY booking_code"
        ).fetchall()
        booking_paid_map = {r["booking_code"]: r["total_paid"] for r in all_paid_rows}

    results = []
    search_term = (search or "").strip().lower()

    matched_cnt = 0
    discrepancy_cnt = 0
    reconciled_cnt = 0
    pending_cnt = 0
    total_rev = 0
    total_ref = 0

    for r in rows:
        d = dict(r)
        r_info = room_map.get(d.get("room_id") or "")
        d["room_name"] = r_info.get("room_name") if r_info else (d.get("room_id") or "—")
        d["room_type"] = r_info.get("room_type") if r_info else "Standard"
        d["branch_name"] = branch_names.get(d.get("branch_id") or "", d.get("branch_id") or "—")
        d["payment_method"] = d.get("method") or "VietQR"

        # Lọc tìm kiếm
        if search_term:
            combined = f"{d.get('id')} {d.get('booking_code')} {d.get('customer_name')} {d.get('customer_phone')} {d.get('room_name')} {d.get('branch_name')}".lower()
            if search_term not in combined:
                continue

        # Logic đối chiếu giao dịch & nhận diện chênh lệch (UC-08.2)
        b_amt = d.get("booking_amount")
        t_amt = d.get("amount") or 0
        t_type = d.get("tx_type") or "Thanh toán"
        is_rec = d.get("reconciled") == 1

        if is_rec:
            reconciled_cnt += 1
        else:
            pending_cnt += 1

        if t_type == "Hoàn tiền":
            total_ref += abs(t_amt)
            d["match_status"] = "Khớp hoàn tiền"
            d["is_discrepancy"] = False
            d["discrepancy_amount"] = 0
            d["process_status"] = "Đã hoàn tất đối soát" if is_rec else "Chờ giải ngân hoàn tiền"
            matched_cnt += 1
        else:
            total_rev += t_amt
            tot_paid = booking_paid_map.get(d.get("booking_code"), t_amt)
            if b_amt is None:
                d["match_status"] = "Không có đơn phòng"
                d["is_discrepancy"] = True
                d["discrepancy_amount"] = t_amt
                d["process_status"] = "Chênh lệch - Cần kiểm tra"
                discrepancy_cnt += 1
            elif tot_paid == b_amt:
                d["match_status"] = "Khớp đúng (100%)"
                d["is_discrepancy"] = False
                d["discrepancy_amount"] = 0
                d["process_status"] = "Đã đối soát" if is_rec else "Khớp đúng - Chờ duyệt"
                matched_cnt += 1
            elif tot_paid < b_amt:
                diff = b_amt - tot_paid
                d["match_status"] = f"Thiếu {diff:,} ₫"
                d["is_discrepancy"] = True
                d["discrepancy_amount"] = -diff
                d["process_status"] = "Chênh lệch - Cần thu thêm"
                discrepancy_cnt += 1
            else:
                diff = tot_paid - b_amt
                d["match_status"] = f"Thừa {diff:,} ₫"
                d["is_discrepancy"] = True
                d["discrepancy_amount"] = diff
                d["process_status"] = "Chênh lệch - Cần kiểm tra"
                discrepancy_cnt += 1

        # Lọc theo trạng thái đối chiếu nếu có
        if match_filter == "discrepancy" and not d["is_discrepancy"]:
            continue
        if match_filter == "matched" and d["is_discrepancy"]:
            continue
        if match_filter == "refund" and t_type != "Hoàn tiền":
            continue

        results.append(d)

    summary = {
        "total_revenue": total_rev,
        "total_refunds": total_ref,
        "reconciled_count": reconciled_cnt,
        "pending_count": pending_cnt,
        "discrepancy_count": discrepancy_cnt,
        "matched_count": matched_cnt,
        "total_transactions": len(results),
    }

    return {
        "status": "ok",
        "total": len(results),
        "period": active_period,
        "summary": summary,
        "transactions": results,
    }


@router.get("/accounting/reconcile-detail/{tx_id}")
def get_accounting_reconcile_detail(
    tx_id: int,
    user: dict[str, Any] = Depends(require_permission("transaction.view")),
):
    """
    Chi tiết đối chiếu 2 cột song song giữa Đơn đặt phòng và Giao dịch thanh toán cổng/ngân hàng.
    """
    with connect() as conn:
        tx = conn.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,)).fetchone()
        if not tx:
            raise HTTPException(status_code=404, detail="Không tìm thấy giao dịch.")
        tx_dict = dict(tx)
        tx_dict["payment_method"] = tx_dict.get("method") or "VietQR"

        b_code = tx_dict.get("booking_code")
        booking = conn.execute("SELECT * FROM bookings WHERE booking_code = ?", (b_code,)).fetchone()
        b_dict = dict(booking) if booking else None

        related_txs = conn.execute("SELECT * FROM transactions WHERE booking_code = ? ORDER BY id ASC", (b_code,)).fetchall()
        extensions = conn.execute("SELECT * FROM booking_extensions WHERE booking_code = ? ORDER BY id ASC", (b_code,)).fetchall()

    room_map = {r["room_id"]: r for r in all_rooms()}
    r_info = room_map.get(b_dict.get("room_id") or "") if b_dict else None

    # Phân tích độ khớp
    is_refund = tx_dict["tx_type"] == "Hoàn tiền"
    tot_paid = sum(t["amount"] for t in related_txs if t["tx_type"] in ("Thanh toán", "Gia hạn") and t["status"] in ("Thành công", "Đã đối soát"))
    b_amt = b_dict.get("amount") if b_dict else None

    if is_refund:
        match_analysis = {
            "status": "Khớp hoàn tiền",
            "is_matched": True,
            "discrepancy_amount": 0,
            "note": "Khoản hoàn tiền được hạch toán sau khi khách hàng hủy đơn phòng hợp lệ theo chính sách BR-05.",
        }
    elif b_amt is None:
        match_analysis = {
            "status": "Không có đơn phòng",
            "is_matched": False,
            "discrepancy_amount": tx_dict["amount"],
            "note": "Giao dịch ghi nhận trên cổng thanh toán nhưng không có mã đơn tương ứng trong cơ sở dữ liệu PMS.",
        }
    elif tot_paid == b_amt:
        match_analysis = {
            "status": "Khớp đúng (100%)",
            "is_matched": True,
            "discrepancy_amount": 0,
            "note": f"Tổng tiền giao dịch ghi nhận ({tot_paid:,} ₫) khớp hoàn toàn với số tiền trên đơn đặt phòng ({b_amt:,} ₫).",
        }
    elif tot_paid < b_amt:
        diff = b_amt - tot_paid
        match_analysis = {
            "status": f"Chênh lệch thiếu (-{diff:,} ₫)",
            "is_matched": False,
            "discrepancy_amount": -diff,
            "note": f"Khách hàng mới thanh toán {tot_paid:,} ₫ / {b_amt:,} ₫. Còn thiếu {diff:,} ₫ cần thu tại quầy khi check-in hoặc check-out.",
        }
    else:
        diff = tot_paid - b_amt
        match_analysis = {
            "status": f"Chênh lệch thừa (+{diff:,} ₫)",
            "is_matched": False,
            "discrepancy_amount": diff,
            "note": f"Tổng tiền giao dịch ({tot_paid:,} ₫) lớn hơn số tiền trên đơn ({b_amt:,} ₫). Cần đối soát lại với cổng thanh toán để xử lý hoàn khoản dư thừa.",
        }

    rel_tx_dicts = []
    for t in related_txs:
        td = dict(t)
        td["payment_method"] = td.get("method") or "VietQR"
        rel_tx_dicts.append(td)

    is_disc = not match_analysis["is_matched"]
    return {
        "status": "ok",
        "transaction": tx_dict,
        "booking": {
            **b_dict,
            "room_name": r_info.get("room_name") if r_info else b_dict.get("room_id"),
            "room_type": r_info.get("room_type") if r_info else "Standard",
        } if b_dict else None,
        "related_transactions": rel_tx_dicts,
        "extensions": [dict(e) for e in extensions],
        "match_analysis": match_analysis,
        "match_status": match_analysis["status"],
        "is_discrepancy": is_disc,
        "discrepancy_reason": match_analysis["note"],
        "discrepancy_amount": match_analysis["discrepancy_amount"],
    }


@router.get("/accounting/booking-detail/{booking_code}")
def get_accounting_booking_detail(
    booking_code: str,
    user: dict[str, Any] = Depends(require_permission("transaction.view")),
):
    """
    Tra cứu chi tiết toàn bộ lượt đặt phòng liên quan đến giao dịch
    """
    booking = get_booking_by_code(booking_code)
    if not booking:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy lượt đặt phòng {booking_code}")

    room_map = {r["room_id"]: r for r in all_rooms()}
    r_info = room_map.get(booking.get("room_id") or "")

    branch_names = {
        "BT": "CozyHome Bến Thành (128 Lê Lai, Quận 1)",
        "TD": "CozyHome Thảo Điền (45 Xuân Thủy, TP. Thủ Đức)",
        "PMH": "CozyHome Phú Mỹ Hưng (88 Nguyễn Đức Cảnh, Quận 7)",
    }

    # Lấy toàn bộ giao dịch của lượt đặt này
    with connect() as conn:
        tx_rows = conn.execute(
            "SELECT * FROM transactions WHERE booking_code = ? ORDER BY id ASC",
            (booking_code,),
        ).fetchall()
        ext_rows = conn.execute(
            "SELECT * FROM booking_extensions WHERE booking_code = ? ORDER BY id ASC",
            (booking_code,),
        ).fetchall()

    return {
        "status": "ok",
        "booking": {
            **booking,
            "room_name": r_info.get("room_name") if r_info else booking.get("room_id"),
            "room_type": r_info.get("room_type") if r_info else "Standard",
            "concept": r_info.get("concept") if r_info else "",
            "branch_full_name": branch_names.get(booking.get("branch_id") or "", booking.get("branch_id")),
        },
        "transactions": [dict(t) for t in tx_rows],
        "extensions": [dict(e) for e in ext_rows],
    }


@router.post("/accounting/reconcile-batch")
def post_accounting_reconcile_batch(
    req: dict[str, Any],
    request: Request,
    user: dict[str, Any] = Depends(require_permission("transaction.reconcile")),
):
    """
    Đối soát hàng loạt giao dịch
    """
    reconciled_by = user.get("full_name") or user.get("email") or "Kế toán"
    reconcile_all = req.get("reconcile_all_pending", False)
    tx_ids = req.get("tx_ids", [])

    if reconcile_all:
        with connect() as conn:
            pending_rows = conn.execute("SELECT id FROM transactions WHERE reconciled = 0").fetchall()
            tx_ids = [r["id"] for r in pending_rows]

    if not tx_ids:
        return {"status": "ok", "message": "Không có giao dịch nào cần đối soát.", "updated_count": 0}

    updated_count = reconcile_transactions_batch(tx_ids, reconciled_by)

    record_audit(
        request=request,
        user=user,
        action="ACCOUNTING_RECONCILE_BATCH",
        entity_type="TRANSACTION",
        entity_id=f"BATCH_{len(tx_ids)}",
        description=f"Kế toán {reconciled_by} đã hoàn tất đối soát hàng loạt {updated_count} giao dịch.",
        new_value=f"{updated_count} giao dịch đã đối soát",
    )

    return {
        "status": "ok",
        "message": f"Đã hoàn tất đối soát thành công {updated_count} giao dịch.",
        "updated_count": updated_count,
    }


@router.get("/accounting/revenue-breakdown")
def get_accounting_revenue_breakdown(
    period: str = "30days",
    from_date: str | None = None,
    to_date: str | None = None,
    branch_id: str | None = None,
    user: dict[str, Any] = Depends(require_permission("transaction.view")),
):
    """
    Báo cáo phân tích doanh thu 3 chiều:
    1. Theo chuỗi thời gian (ngày/tháng)
    2. Theo chi nhánh (BT, TD, PMH)
    3. Theo loại phòng (Standard, Deluxe, Family)
    """
    start_str, end_str = _resolve_acc_dates(period, from_date, to_date)
    start_d = datetime.strptime(start_str, "%Y-%m-%d").date()
    end_d = datetime.strptime(end_str, "%Y-%m-%d").date()

    all_room_list = all_rooms()
    room_map = {r["room_id"]: r for r in all_room_list}

    branch_meta = {
        "BT": {"name": "CozyHome Bến Thành", "address": "Quận 1"},
        "TD": {"name": "CozyHome Thảo Điền", "address": "TP. Thủ Đức"},
        "PMH": {"name": "CozyHome Phú Mỹ Hưng", "address": "Quận 7"},
    }

    with connect() as conn:
        tx_where = "WHERE t.created_at >= ? AND t.created_at <= ?"
        params: list[Any] = [f"{start_str}T00:00:00", f"{end_str}T23:59:59"]
        if branch_id and branch_id != "ALL":
            tx_where += " AND b.branch_id = ?"
            params.append(branch_id)

        rows = conn.execute(
            f"""
            SELECT t.*, b.branch_id, b.room_id, b.booking_date
            FROM transactions t
            LEFT JOIN bookings b ON t.booking_code = b.booking_code
            {tx_where}
            ORDER BY t.created_at ASC
            """,
            params,
        ).fetchall()
        tx_list = [dict(r) for r in rows]

    # 1. Timeline theo ngày
    timeline_map: dict[str, dict[str, Any]] = {}
    curr_d = start_d
    while curr_d <= end_d:
        d_str = curr_d.isoformat()
        timeline_map[d_str] = {
            "date": d_str,
            "label": curr_d.strftime("%d/%m"),
            "gross": 0,
            "refunds": 0,
            "revenue": 0,
            "tx_count": 0,
        }
        curr_d += timedelta(days=1)

    for t in tx_list:
        c_date = t["created_at"][:10]
        if c_date in timeline_map:
            amt = t["amount"]
            timeline_map[c_date]["tx_count"] += 1
            if t["tx_type"] in ("Thanh toán", "Gia hạn") and t["status"] in ("Thành công", "Đã đối soát"):
                timeline_map[c_date]["gross"] += amt
                timeline_map[c_date]["revenue"] += amt
            elif t["tx_type"] == "Hoàn tiền":
                timeline_map[c_date]["refunds"] += abs(amt)
                timeline_map[c_date]["revenue"] -= abs(amt)

    # 2. Phân tích theo Chi nhánh
    branch_agg: dict[str, dict[str, Any]] = {
        b_code: {
            "branch_id": b_code,
            "branch_name": b_data["name"],
            "gross": 0,
            "refunds": 0,
            "net_revenue": 0,
            "tx_count": 0,
            "paid_count": 0,
            "refund_count": 0,
        }
        for b_code, b_data in branch_meta.items()
    }

    # 3. Phân tích theo Loại phòng
    room_type_agg: dict[str, dict[str, Any]] = {
        "Standard": {"room_type": "Standard", "name": "Hạng Standard", "gross": 0, "refunds": 0, "net_revenue": 0, "tx_count": 0},
        "Deluxe": {"room_type": "Deluxe", "name": "Hạng Deluxe", "gross": 0, "refunds": 0, "net_revenue": 0, "tx_count": 0},
        "Family": {"room_type": "Family", "name": "Hạng Family", "gross": 0, "refunds": 0, "net_revenue": 0, "tx_count": 0},
    }

    for t in tx_list:
        b_code = t.get("branch_id")
        r_id = t.get("room_id")
        amt = t["amount"]
        is_paid = t["tx_type"] in ("Thanh toán", "Gia hạn") and t["status"] in ("Thành công", "Đã đối soát")
        is_refund = t["tx_type"] == "Hoàn tiền"

        # Tích lũy theo chi nhánh
        if b_code and b_code in branch_agg:
            branch_agg[b_code]["tx_count"] += 1
            if is_paid:
                branch_agg[b_code]["gross"] += amt
                branch_agg[b_code]["net_revenue"] += amt
                branch_agg[b_code]["paid_count"] += 1
            elif is_refund:
                branch_agg[b_code]["refunds"] += abs(amt)
                branch_agg[b_code]["net_revenue"] -= abs(amt)
                branch_agg[b_code]["refund_count"] += 1

        # Tích lũy theo loại phòng
        r_type = "Standard"
        if r_id and r_id in room_map:
            r_type = room_map[r_id].get("room_type") or "Standard"
        if r_type not in room_type_agg:
            room_type_agg[r_type] = {"room_type": r_type, "name": f"Hạng {r_type}", "gross": 0, "refunds": 0, "net_revenue": 0, "tx_count": 0}

        room_type_agg[r_type]["tx_count"] += 1
        if is_paid:
            room_type_agg[r_type]["gross"] += amt
            room_type_agg[r_type]["net_revenue"] += amt
        elif is_refund:
            room_type_agg[r_type]["refunds"] += abs(amt)
            room_type_agg[r_type]["net_revenue"] -= abs(amt)

    # Đảm bảo net_revenue không âm
    for b in branch_agg.values():
        b["net_revenue"] = max(0, b["net_revenue"])
    for rt in room_type_agg.values():
        rt["net_revenue"] = max(0, rt["net_revenue"])

    return {
        "status": "ok",
        "date_range": {"from": start_str, "to": end_str},
        "timeline": list(timeline_map.values()),
        "by_branch": list(branch_agg.values()),
        "by_room_type": list(room_type_agg.values()),
    }


@router.get("/accounting/export")
def export_accounting_transactions(
    period: str = "30days",
    from_date: str | None = None,
    to_date: str | None = None,
    branch_id: str | None = None,
    tx_type: str | None = None,
    reconciled: int | None = None,
    user: dict[str, Any] = Depends(require_permission("report.export")),
):
    """
    Xuất báo cáo đối soát giao dịch ra định dạng CSV (UTF-8 BOM hỗ trợ Excel tiếng Việt tuyệt đối)
    """
    start_str, end_str = _resolve_acc_dates(period, from_date, to_date)
    room_map = {r["room_id"]: r for r in all_rooms()}
    branch_names = {"BT": "Bến Thành", "TD": "Thảo Điền", "PMH": "Phú Mỹ Hưng"}

    sql = """
        SELECT t.*, 
               b.room_id, b.branch_id, b.customer_name, b.customer_phone, 
               b.booking_date, b.khung_code, b.status AS booking_status
        FROM transactions t
        LEFT JOIN bookings b ON t.booking_code = b.booking_code
        WHERE t.created_at >= ? AND t.created_at <= ?
    """
    params: list[Any] = [f"{start_str}T00:00:00", f"{end_str}T23:59:59"]

    if tx_type and tx_type != "ALL":
        sql += " AND t.tx_type = ?"
        params.append(tx_type)

    if reconciled is not None:
        sql += " AND t.reconciled = ?"
        params.append(reconciled)

    if branch_id and branch_id != "ALL":
        sql += " AND b.branch_id = ?"
        params.append(branch_id)

    sql += " ORDER BY t.id DESC"

    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()

    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    # Header hàng đầu tiên
    writer.writerow([
        "Mã GD",
        "Mã Đơn Đặt",
        "Thời Gian GD",
        "Khách Hàng",
        "Số Điện Thoại",
        "Chi Nhánh",
        "Mã Phòng",
        "Tên Phòng",
        "Hạng Phòng",
        "Loại Giao Dịch",
        "Số Tiền (VNĐ)",
        "Phương Thức TT",
        "Trạng Thái GD",
        "Đối Soát",
        "Người Đối Soát",
        "Thời Gian Đối Soát",
        "Trạng Thái Đơn Đặt",
    ])

    for r in rows:
        d = dict(r)
        r_info = room_map.get(d.get("room_id") or "")
        r_name = r_info.get("room_name") if r_info else (d.get("room_id") or "—")
        r_type = r_info.get("room_type") if r_info else "Standard"
        b_name = branch_names.get(d.get("branch_id") or "", d.get("branch_id") or "—")

        writer.writerow([
            d.get("id"),
            d.get("booking_code") or "",
            (d.get("created_at") or "").replace("T", " "),
            d.get("customer_name") or "",
            d.get("customer_phone") or "",
            b_name,
            d.get("room_id") or "",
            r_name,
            r_type,
            d.get("tx_type") or "",
            d.get("amount") or 0,
            d.get("method") or "VietQR",
            d.get("status") or "",
            "Đã đối soát" if d.get("reconciled") == 1 else "Chờ đối soát",
            d.get("reconciled_by") or "",
            (d.get("reconciled_at") or "").replace("T", " "),
            d.get("booking_status") or "",
        ])

    csv_data = "\ufeff" + output.getvalue()
    filename = f"CozyHome_BaoCao_DoiSoat_{start_str}_den_{end_str}.csv"

    return Response(
        content=csv_data.encode("utf-8-sig"),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
