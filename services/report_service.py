from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

try:
    from business_service import all_rooms
    from storage import connect
except ImportError:
    from services.business_service import all_rooms
    from services.storage import connect

BRANCH_NAMES = {
    "BT": "CozyHome Bến Thành",
    "TD": "CozyHome Thảo Điền",
    "PMH": "CozyHome Phú Mỹ Hưng",
}


def _resolve_date_range(
    period: str, from_date: str | None = None, to_date: str | None = None
) -> tuple[str, str]:
    today = date.today()
    if period == "today":
        d_str = today.isoformat()
        return d_str, d_str
    elif period == "7days":
        start = today - timedelta(days=6)
        return start.isoformat(), today.isoformat()
    elif period == "month":
        start = today.replace(day=1)
        # End of current month
        next_month = today.replace(day=28) + timedelta(days=4)
        end = next_month - timedelta(days=next_month.day)
        return start.isoformat(), end.isoformat()
    elif period == "custom" and from_date and to_date:
        return from_date, to_date
    else:  # 30days as default
        start = today - timedelta(days=29)
        return start.isoformat(), today.isoformat()


def get_dashboard_report(
    period: str = "30days",
    from_date: str | None = None,
    to_date: str | None = None,
    branch_id: str | None = None,
) -> dict[str, Any]:
    """
    Tổng hợp dữ liệu báo cáo chuyên sâu cho Admin & Quản lý chuỗi
    Tuân thủ 100% dữ liệu thực từ SQLite và cấu hình phòng CozyHome.
    """
    start_str, end_str = _resolve_date_range(period, from_date, to_date)
    start_d = datetime.strptime(start_str, "%Y-%m-%d").date()
    end_d = datetime.strptime(end_str, "%Y-%m-%d").date()
    days_count = max(1, (end_d - start_d).days + 1)

    all_room_list = all_rooms()
    if branch_id:
        room_list = [r for r in all_room_list if r.get("branch_id") == branch_id]
    else:
        room_list = all_room_list
    total_rooms = len(room_list)
    room_dict = {r.get("room_id"): r for r in all_room_list}

    with connect() as conn:
        # -------------------------------------------------------------
        # 1. KPI TỔNG QUAN
        # -------------------------------------------------------------
        # Điều kiện lọc chi nhánh cho bookings
        bk_where = "WHERE booking_date >= ? AND booking_date <= ?"
        bk_params: list[Any] = [start_str, end_str]
        if branch_id:
            bk_where += " AND branch_id = ?"
            bk_params.append(branch_id)

        # Lượt đặt hợp lệ (không bao gồm hết hạn giữ chỗ)
        bookings_rows = conn.execute(
            f"SELECT * FROM bookings {bk_where} ORDER BY booking_date DESC, id DESC",
            bk_params,
        ).fetchall()
        bookings_list = [dict(r) for r in bookings_rows]

        # Doanh thu thực thu trong kỳ từ transactions
        tx_where = "WHERE t.created_at >= ? AND t.created_at <= ?"
        # format ngày bắt đầu và kết thúc với timestamp
        tx_start = f"{start_str}T00:00:00"
        tx_end = f"{end_str}T23:59:59"
        tx_params: list[Any] = [tx_start, tx_end]
        if branch_id:
            tx_where += " AND b.branch_id = ?"
            tx_params.append(branch_id)

        tx_rows = conn.execute(
            f"""
            SELECT t.*, b.branch_id, b.room_id
            FROM transactions t
            LEFT JOIN bookings b ON t.booking_code = b.booking_code
            {tx_where}
            ORDER BY t.id DESC
            """,
            tx_params,
        ).fetchall()
        tx_list = [dict(r) for r in tx_rows]

        # Tính tổng doanh thu: Thanh toán + Gia hạn - Hoàn tiền
        paid_amount = sum(
            t["amount"]
            for t in tx_list
            if t["tx_type"] in ("Thanh toán", "Gia hạn")
            and t["status"] in ("Thành công", "Đã đối soát")
        )
        refund_amount = sum(
            abs(t["amount"])
            for t in tx_list
            if t["tx_type"] == "Hoàn tiền"
            and t["status"] in ("Đã hoàn tiền", "Thành công", "Chờ đối soát")
        )
        net_revenue = max(0, paid_amount - refund_amount)

        # Tổng lượt đặt không bị hủy hoặc hết hạn
        valid_bookings = [
            b for b in bookings_list if b["status"] not in ("Hết hạn giữ chỗ",)
        ]
        total_bookings_count = len(valid_bookings)
        completed_count = sum(
            1 for b in valid_bookings if b["status"] == "Đã hoàn tất"
        )
        confirmed_count = sum(
            1 for b in valid_bookings if b["status"] == "Đã xác nhận"
        )
        staying_count = sum(
            1
            for b in valid_bookings
            if b["status"] in ("Đã check-in", "Quá giờ - chưa checkout")
        )
        cancelled_count = sum(
            1 for b in bookings_list if b["status"] == "Đã hủy"
        )

        # Số khách đang lưu trú thực tế hiện tại
        today_str = date.today().isoformat()
        in_house_rows = conn.execute(
            """
            SELECT COALESCE(SUM(guests), 0) FROM bookings 
            WHERE status IN ('Đã check-in', 'Quá giờ - chưa checkout')
            AND booking_date = ?
            """
            + (" AND branch_id = ?" if branch_id else ""),
            [today_str, branch_id] if branch_id else [today_str],
        ).fetchone()
        in_house_guests = in_house_rows[0] if in_house_rows else 0

        # Công suất phòng (% Occupancy theo mô hình khung giờ CozyHome)
        # Tổng slot khả dụng trong kỳ = Số phòng x Số ngày x 4 khung
        total_capacity_slots = total_rooms * days_count * 4
        # Số slot đã đặt thành công (không hủy) trong kỳ
        active_booked_slots = sum(
            1
            for b in valid_bookings
            if b["status"]
            in ("Đã xác nhận", "Đã check-in", "Đã hoàn tất", "Chờ thanh toán")
        )
        occupancy_rate = (
            round((active_booked_slots / total_capacity_slots) * 100, 1)
            if total_capacity_slots > 0
            else 0.0
        )

        # -------------------------------------------------------------
        # 2. DOANH THU VÀ LƯỢT ĐẶT THEO THỜI GIAN (TimeSeries)
        # -------------------------------------------------------------
        # Tạo chuỗi ngày liên tục trong khoảng thời gian đã chọn
        time_series_map: dict[str, dict[str, Any]] = {}
        curr_d = start_d
        while curr_d <= end_d:
            d_key = curr_d.isoformat()
            time_series_map[d_key] = {
                "date": d_key,
                "label": curr_d.strftime("%d/%m"),
                "revenue": 0,
                "bookings": 0,
            }
            curr_d += timedelta(days=1)

        # Phân bổ lượt đặt theo ngày booking_date
        for b in valid_bookings:
            bd = b.get("booking_date")
            if bd in time_series_map:
                time_series_map[bd]["bookings"] += 1

        # Phân bổ doanh thu theo ngày giao dịch
        for t in tx_list:
            if t["tx_type"] in ("Thanh toán", "Gia hạn") and t["status"] in (
                "Thành công",
                "Đã đối soát",
            ):
                created_date = (
                    t["created_at"].split("T")[0]
                    if "T" in t["created_at"]
                    else t["created_at"][:10]
                )
                if created_date in time_series_map:
                    time_series_map[created_date]["revenue"] += t["amount"]

        timeline_data = list(time_series_map.values())

        # -------------------------------------------------------------
        # 3. HIỆU QUẢ THEO TỪNG CHI NHÁNH
        # -------------------------------------------------------------
        branch_stats = []
        for b_code, b_name in BRANCH_NAMES.items():
            if branch_id and branch_id != b_code:
                continue
            b_rooms = [r for r in all_room_list if r.get("branch_id") == b_code]
            b_rooms_cnt = len(b_rooms)

            b_bks = [b for b in valid_bookings if b.get("branch_id") == b_code]
            b_bk_count = len(b_bks)

            b_txs = [
                t
                for t in tx_list
                if t.get("branch_id") == b_code
                and t["tx_type"] in ("Thanh toán", "Gia hạn")
                and t["status"] in ("Thành công", "Đã đối soát")
            ]
            b_rev = sum(t["amount"] for t in b_txs)

            b_total_slots = b_rooms_cnt * days_count * 4
            b_booked_slots = sum(
                1
                for b in b_bks
                if b["status"]
                in (
                    "Đã xác nhận",
                    "Đã check-in",
                    "Đã hoàn tất",
                    "Chờ thanh toán",
                )
            )
            b_occ = (
                round((b_booked_slots / b_total_slots) * 100, 1)
                if b_total_slots > 0
                else 0.0
            )

            branch_stats.append({
                "branch_id": b_code,
                "branch_name": b_name,
                "rooms_count": b_rooms_cnt,
                "bookings_count": b_bk_count,
                "revenue": b_rev,
                "occupancy_rate": b_occ,
            })

        # -------------------------------------------------------------
        # 4. CƠ CẤU HÌNH THỨC LƯU TRÚ (Theo giờ vs Qua đêm)
        # -------------------------------------------------------------
        hourly_count = sum(
            1
            for b in valid_bookings
            if b.get("khung_code") in ("K1", "K2", "K3")
        )
        overnight_count = sum(
            1 for b in valid_bookings if b.get("khung_code") in ("K4", "QD")
        )
        total_stay_count = hourly_count + overnight_count
        hourly_pct = (
            round((hourly_count / total_stay_count) * 100, 1)
            if total_stay_count > 0
            else 0.0
        )
        overnight_pct = (
            round((overnight_count / total_stay_count) * 100, 1)
            if total_stay_count > 0
            else 0.0
        )

        stay_type_distribution = [
            {
                "type": "Theo khung giờ (3h)",
                "code": "hourly",
                "count": hourly_count,
                "percentage": hourly_pct,
            },
            {
                "type": "Qua đêm (21:30 - 08:30)",
                "code": "overnight",
                "count": overnight_count,
                "percentage": overnight_pct,
            },
        ]

        # -------------------------------------------------------------
        # 5. TÌNH TRẠNG PHÒNG HIỆN TẠI (24 Phòng)
        # -------------------------------------------------------------
        # Lấy trạng thái phòng mới nhất từ room_operations
        latest_ops_rows = conn.execute(
            """
            SELECT ro.room_id, ro.status, ro.work_date, ro.updated_at
            FROM room_operations ro
            JOIN (
                SELECT room_id, MAX(id) AS max_id 
                FROM room_operations 
                GROUP BY room_id
            ) x ON ro.id = x.max_id
            """
        ).fetchall()
        latest_ops_map = {r["room_id"]: r["status"] for r in latest_ops_rows}

        # Đếm trạng thái của từng phòng
        status_counts = {
            "Sẵn sàng": 0,
            "Đang sử dụng": 0,
            "Đang dọn": 0,
            "Bảo trì": 0,
        }

        # Check phòng nào đang có khách lưu trú hôm nay
        staying_rooms_rows = conn.execute(
            """
            SELECT room_id FROM bookings 
            WHERE status IN ('Đã check-in', 'Quá giờ - chưa checkout') 
            AND booking_date = ?
            """,
            (today_str,),
        ).fetchall()
        staying_room_ids = {r["room_id"] for r in staying_rooms_rows}

        for r in room_list:
            rid = r.get("room_id")
            if rid in staying_room_ids:
                status_counts["Đang sử dụng"] += 1
            else:
                op_status = latest_ops_map.get(rid, "Sẵn sàng")
                if op_status in ("Cần dọn", "Đang dọn", "Đã vệ sinh"):
                    status_counts["Đang dọn"] += 1
                elif op_status == "Bảo trì":
                    status_counts["Bảo trì"] += 1
                else:
                    status_counts["Sẵn sàng"] += 1

        room_status_list = [
            {
                "status": "Sẵn sàng",
                "count": status_counts["Sẵn sàng"],
                "color": "#2e7d32",
                "badge": "badge-success",
            },
            {
                "status": "Đang sử dụng",
                "count": status_counts["Đang sử dụng"],
                "color": "#1565c0",
                "badge": "badge-info",
            },
            {
                "status": "Đang dọn",
                "count": status_counts["Đang dọn"],
                "color": "#e65100",
                "badge": "badge-warning",
            },
            {
                "status": "Bảo trì",
                "count": status_counts["Bảo trì"],
                "color": "#c62828",
                "badge": "badge-danger",
            },
        ]

        # -------------------------------------------------------------
        # 6. HỦY ĐẶT PHÒNG VÀ HOÀN TIỀN (BR-05)
        # -------------------------------------------------------------
        total_attempts = len(bookings_list)
        cancel_rate = (
            round((cancelled_count / total_attempts) * 100, 1)
            if total_attempts > 0
            else 0.0
        )
        refund_tx_count = sum(
            1 for t in tx_list if t["tx_type"] == "Hoàn tiền"
        )

        cancellation_metrics = {
            "cancelled_bookings": cancelled_count,
            "cancellation_rate": cancel_rate,
            "refund_transactions": refund_tx_count,
            "total_refunded_amount": refund_amount,
        }

        # -------------------------------------------------------------
        # 7. PHÒNG ĐƯỢC ĐẶT NHIỀU NHẤT (Top 5 Phòng)
        # -------------------------------------------------------------
        room_booking_agg: dict[str, dict[str, Any]] = {}
        for b in valid_bookings:
            rid = b.get("room_id")
            if not rid:
                continue
            if rid not in room_booking_agg:
                r_obj = room_dict.get(rid)
                room_booking_agg[rid] = {
                    "room_id": rid,
                    "room_name": r_obj.get("room_name") if r_obj else rid,
                    "branch_id": b.get("branch_id")
                    or (r_obj.get("branch_id") if r_obj else ""),
                    "branch_name": BRANCH_NAMES.get(
                        b.get("branch_id"), "CozyHome"
                    ),
                    "room_type": r_obj.get("room_type") if r_obj else "Standard",
                    "concept": r_obj.get("concept", "") if r_obj else "",
                    "bookings_count": 0,
                    "total_revenue": 0,
                }
            room_booking_agg[rid]["bookings_count"] += 1
            room_booking_agg[rid]["total_revenue"] += b.get("amount") or 0

        sorted_top_rooms = sorted(
            room_booking_agg.values(),
            key=lambda x: (x["bookings_count"], x["total_revenue"]),
            reverse=True,
        )[:5]

        # -------------------------------------------------------------
        # 8. BOOKING GẦN ĐÂY (Recent 8 Bookings)
        # -------------------------------------------------------------
        recent_bookings = []
        for b in bookings_list[:8]:
            r_obj = room_dict.get(b.get("room_id"))
            recent_bookings.append({
                "booking_code": b.get("booking_code"),
                "customer_name": b.get("customer_name") or "Khách hàng",
                "customer_phone": b.get("customer_phone") or "",
                "room_id": b.get("room_id"),
                "room_name": r_obj.get("room_name")
                if r_obj
                else (b.get("room_id") or ""),
                "branch_id": b.get("branch_id"),
                "branch_name": BRANCH_NAMES.get(
                    b.get("branch_id"), "CozyHome"
                ),
                "stay_type": (
                    "Qua đêm"
                    if b.get("khung_code") in ("K4", "QD")
                    else "Theo giờ"
                ),
                "booking_date": b.get("booking_date"),
                "khung_code": b.get("khung_code"),
                "start_time": b.get("start_time"),
                "end_time": b.get("end_time"),
                "status": b.get("status"),
                "amount": b.get("amount") or 0,
                "created_at": b.get("created_at"),
            })

    return {
        "period": period,
        "date_range": {"from": start_str, "to": end_str, "days": days_count},
        "branch_id": branch_id or "ALL",
        "summary": {
            "total_revenue": net_revenue,
            "total_bookings": total_bookings_count,
            "occupancy_rate": occupancy_rate,
            "in_house_guests": in_house_guests,
            "completed_bookings": completed_count,
            "confirmed_bookings": confirmed_count,
            "staying_bookings": staying_count,
            "cancelled_bookings": cancelled_count,
            "total_rooms": total_rooms,
        },
        "timeline": timeline_data,
        "branch_performance": branch_stats,
        "stay_type_distribution": stay_type_distribution,
        "room_status": room_status_list,
        "cancellation_metrics": cancellation_metrics,
        "top_rooms": sorted_top_rooms,
        "recent_bookings": recent_bookings,
    }
