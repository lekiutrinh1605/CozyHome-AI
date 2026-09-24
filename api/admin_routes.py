from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

try:
    from services.auth_guard import record_audit, require_permission
    from services.business_service import all_rooms
    from services.storage import (
        admin_system_metrics,
        count_active_admins,
        create_internal_user,
        get_security_settings,
        get_user_by_id,
        latest_room_operations,
        list_audit_logs,
        list_bookings,
        list_transactions,
        list_users,
        reset_failed_attempts,
        set_user_status,
        update_security_setting,
        update_user_admin,
    )
except ImportError:
    from auth_guard import record_audit, require_permission
    from business_service import all_rooms
    from storage import (
        admin_system_metrics,
        count_active_admins,
        create_internal_user,
        get_security_settings,
        get_user_by_id,
        latest_room_operations,
        list_audit_logs,
        list_bookings,
        list_transactions,
        list_users,
        reset_failed_attempts,
        set_user_status,
        update_security_setting,
        update_user_admin,
    )

router = APIRouter(prefix="/api/admin", tags=["System Administrator"])


# -------------------------------------------------------------
# Request Models
# -------------------------------------------------------------
class CreateUserRequest(BaseModel):
    email: str
    password: str
    full_name: str
    phone: str = ""
    role: str
    branch_id: str | None = None


class UpdateUserRequest(BaseModel):
    full_name: str
    phone: str = ""
    role: str
    branch_id: str | None = None
    status: str = "ACTIVE"


class UpdateStatusRequest(BaseModel):
    status: str


class UpdateScopeRequest(BaseModel):
    role: str
    branch_id: str | None = None


class SecuritySettingsRequest(BaseModel):
    settings: dict[str, str]


# -------------------------------------------------------------
# 1. Dashboard Quản Trị Hệ Thống
# -------------------------------------------------------------
@router.get("/dashboard")
def get_admin_dashboard(user: dict[str, Any] = Depends(require_permission("dashboard.view_all"))):
    """
    KPIs Tổng quan toàn hệ thống dành riêng cho Quản trị viên (Read-Only).
    """
    metrics = admin_system_metrics()
    return {"status": "ok", "data": metrics}


# -------------------------------------------------------------
# 2. Quản Lý Tài Khoản (User Management)
# -------------------------------------------------------------
@router.get("/users")
def get_admin_users(
    search: str | None = None,
    role: str | None = None,
    branch_id: str | None = None,
    status: str | None = None,
    sort_by: str | None = None,
    user: dict[str, Any] = Depends(require_permission("user.view")),
):
    users = list_users(search=search, role=role, branch_id=branch_id, status=status, sort_by=sort_by)
    return {"status": "ok", "users": users}


@router.post("/users")
def create_user(
    req: CreateUserRequest,
    request: Request,
    user: dict[str, Any] = Depends(require_permission("user.create")),
):
    ok, msg, new_user = create_internal_user(
        email=req.email,
        password=req.password,
        full_name=req.full_name,
        phone=req.phone,
        role=req.role,
        branch_id=req.branch_id,
    )
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    record_audit(
        request=request,
        user=user,
        action="ADMIN_CREATE_USER",
        entity_type="USER",
        entity_id=new_user["id"],
        description=f"Tạo tài khoản nội bộ: {req.full_name} ({req.email}), vai trò: {req.role}, chi nhánh: {req.branch_id or 'Toàn chuỗi'}",
        new_value=str(new_user),
    )
    return {"status": "ok", "message": msg, "user": new_user}


@router.put("/users/{user_id}")
def update_user_info(
    user_id: int,
    req: UpdateUserRequest,
    request: Request,
    user: dict[str, Any] = Depends(require_permission("user.update")),
):
    target = get_user_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")

    old_val = {"full_name": target["full_name"], "role": target["role"], "branch_id": target["branch_id"], "status": target.get("status")}
    ok, msg = update_user_admin(
        user_id=user_id,
        full_name=req.full_name,
        phone=req.phone,
        role=req.role,
        branch_id=req.branch_id,
        status=req.status,
    )
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    record_audit(
        request=request,
        user=user,
        action="ADMIN_UPDATE_USER",
        entity_type="USER",
        entity_id=user_id,
        description=f"Cập nhật thông tin tài khoản #{user_id} ({target['email']})",
        old_value=str(old_val),
        new_value=str(req.dict()),
    )
    return {"status": "ok", "message": msg}


@router.post("/users/{user_id}/status")
def change_user_status(
    user_id: int,
    req: UpdateStatusRequest,
    request: Request,
    user: dict[str, Any] = Depends(require_permission("user.lock")),
):
    target = get_user_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")

    # Chống tự vô hiệu hóa tài khoản của chính mình nếu là Admin duy nhất
    current_uid = user.get("user_id") or user.get("id")
    if current_uid == user_id and req.status.upper() in ("LOCKED", "DISABLED"):
        if count_active_admins() <= 1:
            raise HTTPException(
                status_code=400,
                detail="Bạn không thể tự khóa hoặc vô hiệu hóa tài khoản Quản trị viên của chính mình khi không có Admin nào khác.",
            )

    old_status = target.get("status", "ACTIVE")
    ok, msg = set_user_status(user_id, req.status)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    action = f"ADMIN_{req.status.upper()}_USER"
    record_audit(
        request=request,
        user=user,
        action=action,
        entity_type="USER",
        entity_id=user_id,
        description=f"Thay đổi trạng thái tài khoản #{user_id} ({target['email']}) từ {old_status} sang {req.status.upper()}",
        old_value=old_status,
        new_value=req.status.upper(),
    )
    target_updated = get_user_by_id(user_id)
    return {
        "status": "ok",
        "message": msg,
        "updated_at": target_updated.get("updated_at") if target_updated else None,
        "user": target_updated,
    }


@router.post("/users/{user_id}/scope")
def assign_user_scope(
    user_id: int,
    req: UpdateScopeRequest,
    request: Request,
    user: dict[str, Any] = Depends(require_permission("user.assign_role")),
):
    target = get_user_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")

    # Validation: Vai trò Lễ tân và Buồng phòng bắt buộc có branch
    if req.role in ("Lễ tân", "Buồng phòng", "Nhân viên buồng phòng"):
        if not req.branch_id or not req.branch_id.strip():
            raise HTTPException(
                status_code=400,
                detail=f"Lỗi phân quyền: Vai trò '{req.role}' bắt buộc phải phân công một chi nhánh cụ thể (BT, TD hoặc PMH).",
            )
    else:
        # Quản lý chuỗi, Kế toán, Admin có phạm vi Toàn hệ thống
        req.branch_id = None

    old_scope = {"role": target["role"], "branch_id": target["branch_id"]}
    ok, msg = update_user_admin(
        user_id=user_id,
        full_name=target["full_name"],
        phone=target.get("phone") or "",
        role=req.role,
        branch_id=req.branch_id,
        status=target.get("status", "ACTIVE"),
    )
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    record_audit(
        request=request,
        user=user,
        action="ADMIN_ASSIGN_ROLE",
        entity_type="USER",
        entity_id=user_id,
        description=f"Phân quyền tài khoản #{user_id} ({target['email']}): Vai trò '{req.role}', Chi nhánh '{req.branch_id or 'Toàn chuỗi'}'",
        old_value=str(old_scope),
        new_value=f"role={req.role}, branch={req.branch_id or 'ALL'}",
    )
    target_updated = get_user_by_id(user_id)
    return {
        "status": "ok",
        "message": "Đã cập nhật vai trò và phạm vi chi nhánh thành công!",
        "updated_at": target_updated.get("updated_at") if target_updated else None,
        "user": target_updated,
    }


@router.post("/users/{user_id}/reset-fails")
def reset_user_fails(
    user_id: int,
    request: Request,
    user: dict[str, Any] = Depends(require_permission("user.unlock")),
):
    target = get_user_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")

    reset_failed_attempts(user_id)
    record_audit(
        request=request,
        user=user,
        action="ADMIN_RESET_FAILS",
        entity_type="USER",
        entity_id=user_id,
        description=f"Đặt lại số lần đăng nhập sai về 0 cho tài khoản #{user_id} ({target['email']})",
    )
    return {"status": "ok", "message": "Đã đặt lại số lần đăng nhập sai thành công."}


# -------------------------------------------------------------
# 3. Nhật Ký Hệ Thống (Audit Logs)
# -------------------------------------------------------------
@router.get("/audit-logs")
def get_audit_logs(
    keyword: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    user_email: str | None = None,
    role: str | None = None,
    branch_id: str | None = None,
    action: str | None = None,
    sort_by: str | None = None,
    limit: int = 50,
    offset: int = 0,
    user: dict[str, Any] = Depends(require_permission("audit.view")),
):
    logs, total = list_audit_logs(
        keyword=keyword,
        from_date=from_date,
        to_date=to_date,
        user_email=user_email,
        role=role,
        branch_id=branch_id,
        action=action,
        sort_by=sort_by,
        limit=limit,
        offset=offset,
    )
    return {
        "status": "ok",
        "logs": logs,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# -------------------------------------------------------------
# 4. Bảo Mật & Truy Cập (Security Settings)
# -------------------------------------------------------------
@router.get("/security")
def get_security_config(user: dict[str, Any] = Depends(require_permission("security.manage"))):
    settings = get_security_settings()
    return {"status": "ok", "settings": settings}


@router.post("/security")
def update_security_config(
    req: SecuritySettingsRequest,
    request: Request,
    user: dict[str, Any] = Depends(require_permission("security.manage")),
):
    admin_name = user.get("full_name", "Admin")
    old_settings = get_security_settings()

    for k, v in req.settings.items():
        update_security_setting(k, v, updated_by=admin_name)

    record_audit(
        request=request,
        user=user,
        action="SECURITY_CONFIG_CHANGE",
        entity_type="SYSTEM",
        entity_id="SECURITY",
        description="Cập nhật cấu hình bảo mật hệ thống",
        old_value=str({k: old_settings.get(k, {}).get("value") for k in req.settings}),
        new_value=str(req.settings),
    )
    return {"status": "ok", "message": "Đã lưu cấu hình bảo mật thành công!"}


# -------------------------------------------------------------
# 5. Tra Cứu Vận Hành (Read-Only Operations Lookup)
# Admin CHỈ ĐƯỢC XEM, không check-in/out, không dọn phòng, không đối soát
# -------------------------------------------------------------
@router.get("/operations/rooms")
def get_admin_rooms(
    branch_id: str | None = None,
    user: dict[str, Any] = Depends(require_permission("operations.read_all")),
):
    rooms = [r for r in all_rooms() if not branch_id or r["branch_id"] == branch_id]
    ops = latest_room_operations(branch_id)
    op_map = {o["room_id"]: o for o in ops}

    results = []
    for r in rooms:
        item = dict(r)
        cur_op = op_map.get(r["room_id"])
        item["operational_status"] = cur_op["status"] if cur_op else r.get("operational_status", "Sẵn sàng")
        item["last_cleaned_by"] = cur_op["updated_by"] if cur_op else None
        item["last_cleaned_at"] = cur_op["updated_at"] if cur_op else None
        results.append(item)
    return {"status": "ok", "rooms": results}


@router.get("/operations/bookings")
def get_admin_bookings(
    branch_id: str | None = None,
    status: str | None = None,
    keyword: str | None = None,
    sort_by: str | None = None,
    user: dict[str, Any] = Depends(require_permission("operations.read_all")),
):
    from services.storage import remove_vietnamese_accents

    bookings = list_bookings(branch_id=branch_id)
    if status:
        bookings = [b for b in bookings if b["status"] == status]
    if keyword:
        kw = remove_vietnamese_accents(keyword)
        bookings = [
            b for b in bookings
            if kw in remove_vietnamese_accents(b.get("booking_code") or "")
            or kw in remove_vietnamese_accents(b.get("room_id") or "")
            or kw in remove_vietnamese_accents(b.get("customer_name") or "")
            or kw in (b.get("customer_phone") or "").lower()
        ]
    if sort_by == "customer_asc":
        bookings.sort(key=lambda b: remove_vietnamese_accents(b.get("customer_name") or ""))
    elif sort_by == "code_asc":
        bookings.sort(key=lambda b: (b.get("booking_code") or "").lower())
    return {"status": "ok", "bookings": bookings}


@router.get("/operations/transactions")
def get_admin_transactions(
    branch_id: str | None = None,
    user: dict[str, Any] = Depends(require_permission("operations.read_all")),
):
    transactions = list_transactions(branch_id=branch_id)
    return {"status": "ok", "transactions": transactions}
