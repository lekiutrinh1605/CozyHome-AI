from __future__ import annotations

from typing import Any, Callable
from fastapi import Depends, HTTPException, Header, Request, status

try:
    from services.storage import (
        add_audit_log,
        get_session,
        get_user_by_email,
        get_user_by_id,
    )
except ImportError:
    from storage import (
        add_audit_log,
        get_session,
        get_user_by_email,
        get_user_by_id,
    )

# -------------------------------------------------------------
# Permission Matrix Theo Chuẩn Nghiệp Vụ CozyHome
# -------------------------------------------------------------
ROLE_PERMISSIONS: dict[str, set[str]] = {
    "Quản trị viên": {
        "dashboard.view_all",
        "user.view",
        "user.create",
        "user.update",
        "user.lock",
        "user.unlock",
        "user.assign_role",
        "user.assign_branch",
        "audit.view",
        "security.manage",
        "operations.read_all",
        "business_config.view",
        "business_config.update",
    },
    "Admin": {
        "dashboard.view_all",
        "user.view",
        "user.create",
        "user.update",
        "user.lock",
        "user.unlock",
        "user.assign_role",
        "user.assign_branch",
        "audit.view",
        "security.manage",
        "operations.read_all",
        "business_config.view",
        "business_config.update",
    },
    "Lễ tân": {
        "booking.view",
        "booking.check_in",
        "booking.check_out",
        "review.escalate",
        "dashboard.view_branch",
    },
    "Buồng phòng": {
        "housekeeping.view",
        "housekeeping.update",
        "dashboard.view_branch",
    },
    "Nhân viên buồng phòng": {
        "housekeeping.view",
        "housekeeping.update",
        "dashboard.view_branch",
    },
    "Kế toán": {
        "transaction.view",
        "transaction.reconcile",
        "booking.view",
        "dashboard.view_all",
        "report.export",
    },
    "Quản lý": {
        "dashboard.view_all",
        "business_config.view",
        "business_config.update",
        "review.handle",
        "operations.read_all",
    },
    "Quản lý chuỗi": {
        "dashboard.view_all",
        "business_config.view",
        "business_config.update",
        "review.handle",
        "operations.read_all",
    },
    "Khách hàng": {
        "customer.booking",
        "customer.view_self",
        "customer.review",
    },
}

# Các vai trò bị giới hạn theo chi nhánh
BRANCH_SCOPED_ROLES = {"Lễ tân", "Buồng phòng", "Nhân viên buồng phòng"}


def get_client_ip(request: Request) -> str:
    """Trích xuất địa chỉ IP của client gọi API"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


def get_current_user_optional(request: Request) -> dict[str, Any] | None:
    """Lấy thông tin người dùng từ Bearer Token (không bắt buộc đăng nhập)"""
    auth_header = request.headers.get("Authorization", "")
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()

    if not token:
        return None

    session = get_session(token)
    if not session:
        return None

    user = dict(session)

    # Kiểm tra trạng thái tài khoản
    if user.get("locked") == 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản này đang bị tạm khóa bảo mật (nhập sai mật khẩu 5 lần).",
        )
    if user.get("active") == 0 or user.get("status") == "DISABLED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản này đang bị vô hiệu hóa bởi Quản trị viên.",
        )

    # Hỗ trợ Demo Account (demo@cozyhome.vn) trong Training Mode:
    # CHỈ cho phép tài khoản demo mô phỏng vai trò qua header X-Demo-Role
    if user["email"] == "demo@cozyhome.vn":
        from urllib.parse import unquote
        raw_demo_role = request.headers.get("X-Demo-Role")
        demo_role = unquote(raw_demo_role).strip() if raw_demo_role else user.get("demo_role")
        raw_demo_branch = request.headers.get("X-Demo-Branch")
        demo_branch = unquote(raw_demo_branch).strip() if raw_demo_branch else (user.get("demo_branch") or "ALL")
        if demo_role:
            user["effective_role"] = demo_role
            user["effective_branch"] = demo_branch
        else:
            user["effective_role"] = user["role"]
            user["effective_branch"] = user["branch_id"]
    else:
        # Tài khoản thật: Luôn luôn dùng role và branch thật từ cơ sở dữ liệu
        user["effective_role"] = user["role"]
        user["effective_branch"] = user["branch_id"]

    return user


def get_current_user(request: Request) -> dict[str, Any]:
    """Bắt buộc người dùng phải có phiên đăng nhập hợp lệ (401 nếu thiếu hoặc hết hạn)"""
    user = get_current_user_optional(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Phiên đăng nhập không hợp lệ hoặc đã hết hạn. Vui lòng đăng nhập lại.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_permission(required_perm: str) -> Callable:
    """Dependency kiểm tra người dùng có permission tương ứng hay không"""
    def dependency(request: Request, current_user: dict[str, Any] = Depends(get_current_user)):
        effective_role = current_user.get("effective_role", "")
        allowed_perms = ROLE_PERMISSIONS.get(effective_role, set())

        if required_perm not in allowed_perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Bạn không có quyền thực hiện chức năng này (Yêu cầu quyền: {required_perm}).",
            )
        return current_user

    return dependency


def require_role(allowed_roles: list[str]) -> Callable:
    """Dependency kiểm tra người dùng có một trong các roles được phép hay không"""
    def dependency(request: Request, current_user: dict[str, Any] = Depends(get_current_user)):
        effective_role = current_user.get("effective_role", "")
        if effective_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Vai trò '{effective_role}' không được phép truy cập chức năng này.",
            )
        return current_user

    return dependency


def enforce_branch_scope(user: dict[str, Any], requested_branch: str | None) -> str | None:
    """
    Kiểm tra và áp đặt phạm vi chi nhánh (Branch Scope) ở Backend:
    - Nếu là Lễ tân hoặc Buồng phòng của tài khoản thực: Chỉ được truy cập đúng chi nhánh được gán.
    - Nếu là Demo Account hoặc tài khoản có quyền toàn chuỗi (user_branch in ("ALL", None, "")):
      Được phép xem toàn chuỗi (None) hoặc lọc theo chi nhánh yêu cầu.
    - Nếu là Admin / Quản lý chuỗi / Kế toán: Được phép xem toàn chuỗi hoặc lọc theo chi nhánh yêu cầu.
    """
    role = user.get("effective_role", "")
    user_branch = user.get("effective_branch")

    # Tài khoản Demo hoặc tài khoản có quyền toàn hệ thống (user_branch in ("ALL", None, ""))
    if user.get("email") == "demo@cozyhome.vn" or user_branch in ("ALL", None, ""):
        if requested_branch and requested_branch != "ALL":
            return requested_branch
        return None  # None nghĩa là lấy toàn bộ chuỗi

    if role in BRANCH_SCOPED_ROLES:
        if not user_branch:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Tài khoản {role} chưa được phân công chi nhánh cụ thể. Vui lòng liên hệ Admin.",
            )
        if requested_branch and requested_branch != user_branch and requested_branch != "ALL":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Bạn không có quyền truy cập dữ liệu của chi nhánh '{requested_branch}'. Phạm vi của bạn thuộc chi nhánh '{user_branch}'.",
            )
        return user_branch

    # Quản trị viên, Quản lý, Kế toán: data scope = ALL hoặc theo filter
    if requested_branch and requested_branch != "ALL":
        return requested_branch
    return None


def record_audit(
    request: Request,
    user: dict[str, Any],
    action: str,
    entity_type: str,
    entity_id: str | None,
    description: str,
    old_value: str | None = None,
    new_value: str | None = None,
) -> int:
    """Ghi vết hành động quan trọng vào bảng audit_logs"""
    ip = get_client_ip(request)
    return add_audit_log(
        user_id=user.get("user_id") or user.get("id"),
        user_email=user.get("email", "unknown"),
        user_name=user.get("full_name", ""),
        role=user.get("effective_role") or user.get("role", ""),
        branch_id=user.get("effective_branch") or user.get("branch_id"),
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        description=description,
        old_value=str(old_value) if old_value is not None else None,
        new_value=str(new_value) if new_value is not None else None,
        ip_address=ip,
    )
