from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

try:
    from services.auth_guard import get_client_ip
    from services.storage import (
        add_audit_log,
        authenticate,
        authenticate_with_status,
        can_request_otp,
        change_password,
        consume_otp,
        create_session,
        delete_session,
        generate_otp,
        get_user_by_email,
        get_user_by_id,
        get_user_stats,
        register_customer,
        reset_password_with_otp,
        update_profile,
        validate_email,
        validate_phone,
        verify_otp,
    )
    from services import email_service
except ImportError:
    from auth_guard import get_client_ip
    from storage import (
        add_audit_log,
        authenticate,
        authenticate_with_status,
        can_request_otp,
        change_password,
        consume_otp,
        create_session,
        delete_session,
        generate_otp,
        get_user_by_email,
        get_user_by_id,
        get_user_stats,
        register_customer,
        reset_password_with_otp,
        update_profile,
        validate_email,
        validate_phone,
        verify_otp,
    )
    import email_service

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def _mask_email(email: str) -> str:
    """Che mờ địa chỉ email để bảo mật thông tin khi hiển thị (vd: nguyenvannam@gmail.com -> ngu***am@gmail.com)"""
    clean = email.strip().lower()
    if "@" not in clean:
        return clean
    name_part, domain_part = clean.split("@", 1)
    if len(name_part) <= 3:
        masked_name = name_part[0] + "***" if name_part else "***"
    elif len(name_part) <= 5:
        masked_name = name_part[:2] + "***" + name_part[-1]
    else:
        masked_name = name_part[:3] + "***" + name_part[-2:]
    return f"{masked_name}@{domain_part}"


class RegisterRequest(BaseModel):
    full_name: str
    phone: str
    email: str
    password: str


class VerifyOtpRequest(BaseModel):
    email: str
    otp: str
    purpose: str = "register"
    full_name: str | None = None
    phone: str | None = None
    password: str | None = None


class ResendOtpRequest(BaseModel):
    email: str
    purpose: str = "register"


class LoginRequest(BaseModel):
    email: str
    password: str


class ForgotRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    email: str
    otp: str
    new_password: str


class UpdateProfileRequest(BaseModel):
    user_id: int
    full_name: str
    phone: str


class ChangePasswordRequest(BaseModel):
    user_id: int
    old_password: str
    new_password: str


@router.post("/login")
def login(req: LoginRequest, request: Request):
    user, msg = authenticate_with_status(req.email, req.password)
    client_ip = get_client_ip(request)

    if not user:
        # Kiểm tra xem tài khoản có vừa bị tạm khóa không
        u_record = get_user_by_email(req.email)
        action = "ACCOUNT_LOCKED" if u_record and u_record.get("locked") == 1 else "LOGIN_FAILED"
        add_audit_log(
            user_id=u_record["id"] if u_record else None,
            user_email=req.email.strip().lower(),
            user_name=u_record["full_name"] if u_record else None,
            role=u_record["role"] if u_record else "Unknown",
            branch_id=u_record.get("branch_id") if u_record else None,
            action=action,
            entity_type="AUTH",
            entity_id=str(u_record["id"]) if u_record else None,
            description=f"Đăng nhập thất bại: {msg}",
            ip_address=client_ip,
        )
        raise HTTPException(status_code=400, detail=msg)

    # Đăng nhập thành công -> Tạo Server-Side Session Token
    token = create_session(user["id"])
    add_audit_log(
        user_id=user["id"],
        user_email=user["email"],
        user_name=user["full_name"],
        role=user["role"],
        branch_id=user.get("branch_id"),
        action="LOGIN",
        entity_type="AUTH",
        entity_id=str(user["id"]),
        description=f"Đăng nhập thành công với vai trò '{user['role']}'",
        ip_address=client_ip,
    )

    user_dict = dict(user)
    user_dict.pop("password_hash", None)
    return {
        "status": "ok",
        "message": msg,
        "user": user_dict,
        "token": token,
    }


@router.post("/logout")
def logout(request: Request):
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        delete_session(token)
    return {"status": "ok", "message": "Đã đăng xuất thành công."}


@router.post("/register-init")
def register_init(req: RegisterRequest):
    if not req.full_name.strip():
        raise HTTPException(status_code=400, detail="Họ và tên không được để trống.")
    if not validate_phone(req.phone):
        raise HTTPException(
            status_code=400,
            detail="Số điện thoại không đúng định dạng (cần 10 số đầu 03, 05, 07, 08, 09)."
        )
    if not validate_email(req.email):
        raise HTTPException(status_code=400, detail="Địa chỉ email không đúng định dạng.")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Mật khẩu tối thiểu 6 ký tự.")
    if get_user_by_email(req.email):
        raise HTTPException(status_code=400, detail="Email này đã được sử dụng. Vui lòng chọn email khác hoặc đăng nhập.")

    # BR-OTP-05, L5: Kiểm tra tần suất yêu cầu OTP
    can, msg_wait, sec_wait = can_request_otp(req.email, purpose="register")
    if not can:
        raise HTTPException(status_code=429, detail=f"{msg_wait} (Thử lại sau {sec_wait} giây)")

    # Sinh OTP (đã lưu hash trong DB)
    otp = generate_otp(req.email, purpose="register")

    # Gửi qua SMTP Email
    send_res = email_service.send_otp_email(
        to_email=req.email,
        otp=otp,
        purpose="register",
        user_name=req.full_name
    )

    email_masked = _mask_email(req.email)
    delivery = send_res.get("delivery", "sent")

    if delivery == "sent":
        message = f"Mã xác thực đã được gửi tới địa chỉ {email_masked}. Mã có hiệu lực trong 5 phút."
    elif delivery == "dev_console":
        message = f"Mã xác thực đã được gửi tới địa chỉ {email_masked}. Mã có hiệu lực trong 5 phút."
    else:
        message = f"Hệ thống gửi thư đang gặp sự cố. Vui lòng thử lại sau hoặc liên hệ hotline hỗ trợ."

    # L1: Tuyệt đối không chứa demo_otp trong response
    return {
        "status": "ok",
        "message": message,
        "email_masked": email_masked,
        "delivery": delivery,
        "expires_in": 300,
        "resend_after": 60,
    }


@router.post("/register-complete")
def register_complete(req: VerifyOtpRequest, request: Request):
    # L3: Kiểm tra thông tin đầy đủ trước
    if not req.full_name or not req.phone or not req.password:
        raise HTTPException(status_code=400, detail="Thiếu thông tin đăng ký.")

    # Kiểm tra email chưa tồn tại
    if get_user_by_email(req.email):
        raise HTTPException(status_code=400, detail="Email này đã được đăng ký.")

    # Kiểm tra tính hợp lệ của OTP nhưng CHƯA tiêu thụ (consume=False)
    ok, msg = verify_otp(req.email, req.otp, purpose=req.purpose, consume=False)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    # Thực hiện đăng ký tài khoản khách hàng
    ok2, msg2 = register_customer(req.full_name, req.phone, req.email, req.password)
    if not ok2:
        raise HTTPException(status_code=400, detail=msg2)

    # Chỉ khi đăng ký thành công mới tiêu thụ OTP (L3)
    consume_otp(req.email, purpose=req.purpose)

    user = authenticate(req.email, req.password)
    token = create_session(user["id"]) if user else ""
    client_ip = get_client_ip(request)
    if user:
        add_audit_log(
            user_id=user["id"],
            user_email=user["email"],
            user_name=user["full_name"],
            role="Khách hàng",
            branch_id=None,
            action="REGISTER",
            entity_type="AUTH",
            entity_id=str(user["id"]),
            description=f"Đăng ký tài khoản khách hàng thành công: {user['full_name']} ({user['email']})",
            ip_address=client_ip,
        )

    user_dict = dict(user) if user else {}
    user_dict.pop("password_hash", None)
    return {
        "status": "ok",
        "message": "Đăng ký thành công!",
        "user": user_dict,
        "token": token,
    }


@router.post("/resend-otp")
def resend_otp(req: ResendOtpRequest):
    """Gửi lại mã xác thực OTP (BR-OTP-02, BR-OTP-05)"""
    if not validate_email(req.email):
        raise HTTPException(status_code=400, detail="Địa chỉ email không đúng định dạng.")

    can, msg_wait, sec_wait = can_request_otp(req.email, purpose=req.purpose)
    if not can:
        raise HTTPException(status_code=429, detail=f"{msg_wait} (Thử lại sau {sec_wait} giây)")

    user = get_user_by_email(req.email)
    if req.purpose == "forgot":
        if not user:
            raise HTTPException(
                status_code=400,
                detail="Địa chỉ email này chưa được đăng ký tài khoản tại CozyHome. Vui lòng kiểm tra lại hoặc đăng ký tài khoản mới."
            )
        if not user.get("active", 1):
            raise HTTPException(
                status_code=400,
                detail="Tài khoản này hiện đang bị tạm khóa. Vui lòng liên hệ quản trị viên CozyHome để được hỗ trợ."
            )

    user_name = user["full_name"] if user else None

    # Sinh mã mới (tự động vô hiệu hóa mã cũ cùng purpose)
    otp = generate_otp(req.email, purpose=req.purpose)

    send_res = email_service.send_otp_email(
        to_email=req.email,
        otp=otp,
        purpose=req.purpose,
        user_name=user_name
    )

    email_masked = _mask_email(req.email)
    delivery = send_res.get("delivery", "sent")

    if delivery == "sent":
        message = f"Mã xác thực mới đã được gửi tới địa chỉ {email_masked}. Mã có hiệu lực trong 5 phút."
    elif delivery == "dev_console":
        message = f"Mã xác thực mới đã được gửi tới địa chỉ {email_masked}. Mã có hiệu lực trong 5 phút."
    else:
        message = f"Hệ thống gửi thư đang gặp sự cố. Vui lòng thử lại sau hoặc liên hệ hotline hỗ trợ."

    return {
        "status": "ok",
        "message": message,
        "email_masked": email_masked,
        "delivery": delivery,
        "expires_in": 300,
        "resend_after": 60,
    }


@router.post("/forgot-init")
def forgot_init(req: ForgotRequest):
    if not validate_email(req.email):
        raise HTTPException(status_code=400, detail="Địa chỉ email không đúng định dạng.")

    # Kiểm tra tài khoản trong cơ sở dữ liệu
    user = get_user_by_email(req.email)
    if not user:
        raise HTTPException(
            status_code=400,
            detail="Địa chỉ email này chưa được đăng ký tài khoản tại CozyHome. Vui lòng kiểm tra lại hoặc đăng ký tài khoản mới."
        )
    if not user.get("active", 1):
        raise HTTPException(
            status_code=400,
            detail="Tài khoản này hiện đang bị tạm khóa. Vui lòng liên hệ quản trị viên CozyHome để được hỗ trợ."
        )

    # Kiểm tra tần suất yêu cầu OTP
    can, msg_wait, sec_wait = can_request_otp(req.email, purpose="forgot")
    if not can:
        raise HTTPException(status_code=429, detail=f"{msg_wait} (Thử lại sau {sec_wait} giây)")

    otp = generate_otp(req.email, purpose="forgot")
    email_service.send_otp_email(
        to_email=req.email,
        otp=otp,
        purpose="forgot",
        user_name=user.get("full_name")
    )

    email_masked = _mask_email(req.email)
    return {
        "status": "ok",
        "message": f"Mã xác thực OTP đã được gửi tới hộp thư {email_masked}. Vui lòng kiểm tra email của bạn.",
        "email_masked": email_masked,
        "resend_after": 60,
    }


@router.post("/forgot-verify")
def forgot_verify(req: VerifyOtpRequest):
    ok, msg = verify_otp(req.email, req.otp, purpose="forgot", consume=False)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "ok", "message": "Xác thực OTP thành công. Mời bạn nhập mật khẩu mới."}


@router.post("/forgot-reset")
def forgot_reset(req: ResetPasswordRequest, request: Request):
    # L2: Bắt buộc truyền req.otp xuống tầng storage để xác thực OTP trước khi đổi mật khẩu
    ok, msg = reset_password_with_otp(req.email, req.otp, req.new_password)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    client_ip = get_client_ip(request)
    u_rec = get_user_by_email(req.email)
    add_audit_log(
        user_id=u_rec["id"] if u_rec else None,
        user_email=req.email.strip().lower(),
        user_name=u_rec["full_name"] if u_rec else None,
        role=u_rec["role"] if u_rec else "Khách hàng",
        branch_id=u_rec.get("branch_id") if u_rec else None,
        action="PASSWORD_RESET_OTP",
        entity_type="AUTH",
        entity_id=str(u_rec["id"]) if u_rec else None,
        description=f"Đặt lại mật khẩu thành công qua xác thực OTP cho tài khoản {req.email}",
        ip_address=client_ip,
    )
    return {"status": "ok", "message": msg}


@router.get("/smtp-status")
def get_smtp_status():
    """Endpoint chẩn đoán kết nối SMTP (không tiết lộ thông tin nhạy cảm)"""
    res = email_service.test_smtp_connection()
    return {
        "configured": res.get("configured", False),
        "reachable": res.get("reachable", False),
        "message": res.get("message", ""),
        "host": res.get("host", ""),
        "port": res.get("port", 587),
    }


@router.get("/profile/{user_id}")
def get_profile(user_id: int):
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")
    stats = get_user_stats(user_id)
    return {"user": user, "stats": stats}


@router.put("/profile")
def update_user_profile(req: UpdateProfileRequest):
    ok, msg = update_profile(req.user_id, req.full_name, req.phone)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    user = get_user_by_id(req.user_id)
    return {"status": "ok", "message": msg, "user": user}


@router.post("/change-password")
def change_user_password(req: ChangePasswordRequest):
    ok, msg = change_password(req.user_id, req.old_password, req.new_password)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "ok", "message": msg}
