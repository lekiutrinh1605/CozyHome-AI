from __future__ import annotations

import os
import re
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Đảm bảo đường dẫn import
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "services"))

from fastapi.testclient import TestClient
from server import app
from services import email_service, storage

client = TestClient(app)

TOTAL_CASES = 12
passed_cases = 0


def log_test(num: int, name: str, success: bool, detail: str = ""):
    global passed_cases
    status = "✅ PASS" if success else "❌ FAIL"
    if success:
        passed_cases += 1
    print(f"[{num:02d}/{TOTAL_CASES:02d}] {name:<50} -> {status}")
    if detail:
        print(f"     Chi tiết: {detail}")


def run_all_tests():
    print("=" * 80)
    print("BỘ KIỂM THỬ TỰ ĐỘNG XÁC THỰC OTP QUA EMAIL SMTP & BẢO MẬT (UC-01, L1 - L10)")
    print("=" * 80)

    storage.init_db()

    # -------------------------------------------------------------
    # Ca 1: POST register-init hợp lệ, response KHÔNG chứa demo_otp và không chứa mã 6 số
    # -------------------------------------------------------------
    email1 = f"test_c1_{int(datetime.now().timestamp())}@cozyhome.vn"
    res1 = client.post("/api/auth/register-init", json={
        "full_name": "Nguyen Van Test",
        "phone": "0909123456",
        "email": email1,
        "password": "password123"
    })
    data1 = res1.json()
    c1_ok = (
        res1.status_code == 200
        and "demo_otp" not in data1
        and "demo_otp" not in res1.text
        and not re.search(r'"\d{6}"', res1.text)
        and "email_masked" in data1
    )
    log_test(1, "POST register-init không rò rỉ OTP (L1, BR-OTP-06)", c1_ok,
             f"HTTP {res1.status_code}, delivery: {data1.get('delivery')}, masked: {data1.get('email_masked')}")

    # -------------------------------------------------------------
    # Ca 2: Đọc bảng otps sau Ca 1 -> cột otp_code là hash SHA-256 (64 ký tự)
    # -------------------------------------------------------------
    with storage.connect() as conn:
        row2 = conn.execute(
            "SELECT otp_code, attempts, sent_status FROM otps WHERE email=? ORDER BY id DESC LIMIT 1",
            (email1,)
        ).fetchone()
    c2_ok = (
        row2 is not None
        and len(row2["otp_code"]) == 64
        and not row2["otp_code"].isdigit()
        and "attempts" in row2.keys()
    )
    log_test(2, "Bảng otps lưu mã băm SHA-256 64 ký tự (L7)", c2_ok,
             f"Hash: {row2['otp_code'][:12]}... (độ dài {len(row2['otp_code'])})")

    # -------------------------------------------------------------
    # Ca 3: Gọi register-init 2 lần liên tiếp -> lần 2 trả HTTP 429 (Rate limiting)
    # -------------------------------------------------------------
    email3 = f"test_c3_{int(datetime.now().timestamp())}@cozyhome.vn"
    res3_first = client.post("/api/auth/register-init", json={
        "full_name": "Test Cooldown",
        "phone": "0909123456",
        "email": email3,
        "password": "password123"
    })
    res3_second = client.post("/api/auth/register-init", json={
        "full_name": "Test Cooldown",
        "phone": "0909123456",
        "email": email3,
        "password": "password123"
    })
    c3_ok = (res3_first.status_code == 200 and res3_second.status_code == 429)
    log_test(3, "Gọi register-init liên tiếp bị chặn HTTP 429 (L5, BR-OTP-05)", c3_ok,
             f"Lần 1: {res3_first.status_code}, Lần 2: {res3_second.status_code} ({res3_second.json().get('detail')})")

    # -------------------------------------------------------------
    # Ca 4: Nhập sai OTP 5 lần -> bị vô hiệu hóa; lần 6 dù đúng vẫn thất bại
    # -------------------------------------------------------------
    email4 = f"test_c4_{int(datetime.now().timestamp())}@cozyhome.vn"
    real_otp4 = storage.generate_otp(email4, purpose="register")
    # 4 lần nhập sai
    for i in range(4):
        ok4_try, _ = storage.verify_otp(email4, "000000", purpose="register", consume=False)
        assert not ok4_try
    # Lần 5 nhập sai -> báo vô hiệu hóa
    ok4_5, msg4_5 = storage.verify_otp(email4, "000000", purpose="register", consume=False)
    # Lần 6 nhập ĐÚNG -> vẫn phải thất bại vì mã đã bị vô hiệu hóa
    ok4_6, msg4_6 = storage.verify_otp(email4, real_otp4, purpose="register", consume=False)
    c4_ok = (not ok4_5 and "vô hiệu hóa" in msg4_5 and not ok4_6)
    log_test(4, "Khóa mã OTP sau 5 lần nhập sai liên tiếp (L4, BR-OTP-04)", c4_ok,
             f"Lần 5: '{msg4_5}', Lần 6 (nhập đúng): '{msg4_6}'")

    # -------------------------------------------------------------
    # Ca 5: Nhập đúng OTP nhưng đăng ký trùng email -> đăng ký thất bại và OTP vẫn còn hiệu lực
    # -------------------------------------------------------------
    email5 = "demo@cozyhome.vn" # Email đã có sẵn trong seed database
    otp5 = storage.generate_otp(email5, purpose="register")
    # Xác thực trước xem OTP có hợp lệ không
    ok5_check, _ = storage.verify_otp(email5, otp5, purpose="register", consume=False)
    # Gọi register-complete với email đã tồn tại
    res5 = client.post("/api/auth/register-complete", json={
        "email": email5,
        "otp": otp5,
        "purpose": "register",
        "full_name": "Khách Trùng",
        "phone": "0909999888",
        "password": "password123"
    })
    # Kiểm tra trạng thái OTP trong database: phải còn used=0
    with storage.connect() as conn:
        row5 = conn.execute(
            "SELECT used FROM otps WHERE email=? AND purpose='register' ORDER BY id DESC LIMIT 1",
            (email5,)
        ).fetchone()
    c5_ok = (
        ok5_check
        and res5.status_code == 400
        and row5 is not None
        and row5["used"] == 0
    )
    log_test(5, "Tạo tài khoản thất bại thì không đốt OTP (Vá L3, BR-OTP-03)", c5_ok,
             f"API status: {res5.status_code}, DB OTP used status: {row5['used']}")

    # -------------------------------------------------------------
    # Ca 6: OTP quá 5 phút -> xác thực thất bại do hết hạn
    # -------------------------------------------------------------
    email6 = f"test_c6_{int(datetime.now().timestamp())}@cozyhome.vn"
    otp6 = "654321"
    expired_time = (datetime.now() - timedelta(minutes=6)).isoformat(timespec="seconds")
    with storage.connect() as conn:
        conn.execute(
            """INSERT INTO otps(email, otp_code, purpose, expires_at, used, attempts, sent_status, created_at)
               VALUES(?,?,'register',?,0,0,'sent',?)""",
            (email6, storage._hash_otp(otp6), expired_time, expired_time)
        )
    ok6, msg6 = storage.verify_otp(email6, otp6, purpose="register", consume=False)
    c6_ok = (not ok6 and "hết hiệu lực" in msg6)
    log_test(6, "OTP quá hạn 5 phút bị từ chối xác thực (BR-OTP-01)", c6_ok,
             f"Kết quả: ok={ok6}, msg='{msg6}'")

    # -------------------------------------------------------------
    # Ca 7: POST forgot-reset với OTP sai -> HTTP 400, mật khẩu KHÔNG đổi
    # -------------------------------------------------------------
    email7 = "letan.bt@cozyhome.vn"
    storage.generate_otp(email7, purpose="forgot")
    # Thử gọi forgot-reset với OTP sai "000000"
    res7 = client.post("/api/auth/forgot-reset", json={
        "email": email7,
        "otp": "000000",
        "new_password": "newpassword999"
    })
    # Thử đăng nhập bằng mật khẩu mới (phải thất bại) và mật khẩu cũ (phải thành công)
    user_with_new_pw = storage.authenticate(email7, "newpassword999")
    user_with_old_pw = storage.authenticate(email7, "123456")
    c7_ok = (
        res7.status_code == 400
        and user_with_new_pw is None
        and user_with_old_pw is not None
    )
    log_test(7, "forgot-reset với OTP sai bị chặn 400, không đổi mật khẩu (Vá L2)", c7_ok,
             f"API code: {res7.status_code}, User new pw login: {user_with_new_pw is not None}")

    # -------------------------------------------------------------
    # Ca 8: POST forgot-init: kiểm tra DB, email chưa đăng ký -> HTTP 400; email đã đăng ký -> HTTP 200
    # -------------------------------------------------------------
    email8_nonexist = f"nonexistent_{int(datetime.now().timestamp())}@gmail.com"
    email8_exist = "admin@cozyhome.vn"

    res8_nonexist = client.post("/api/auth/forgot-init", json={"email": email8_nonexist})
    res8_exist = client.post("/api/auth/forgot-init", json={"email": email8_exist})

    c8_ok = (
        res8_nonexist.status_code == 400
        and "chưa được đăng ký" in res8_nonexist.json().get("detail", "").lower()
        and res8_exist.status_code == 200
    )
    log_test(8, "forgot-init kiểm tra DB: chưa đăng ký -> 400, đã đăng ký -> 200", c8_ok,
             f"Email chưa đk: {res8_nonexist.status_code} ({res8_nonexist.json().get('detail')[:45]}...), Email đã đk: {res8_exist.status_code}")

    # -------------------------------------------------------------
    # Ca 9: send_otp_email khi chưa cấu hình SMTP -> trả success=False, không crash
    # -------------------------------------------------------------
    # Tạm gỡ env credentials nếu có để test
    old_user = os.environ.get("SMTP_USER")
    old_pass = os.environ.get("SMTP_PASSWORD")
    try:
        os.environ["SMTP_USER"] = ""
        os.environ["SMTP_PASSWORD"] = ""
        send_res9 = email_service.send_otp_email("test@example.com", "123456", "register")
        c9_ok = (
            send_res9.get("success") is False
            and send_res9.get("smtp_configured") is False
            and send_res9.get("error") == "SMTP_NOT_CONFIGURED"
        )
    finally:
        if old_user: os.environ["SMTP_USER"] = old_user
        if old_pass: os.environ["SMTP_PASSWORD"] = old_pass
    log_test(9, "send_otp_email dự phòng khi chưa có SMTP (5.2)", c9_ok,
             f"success={send_res9.get('success')}, delivery={send_res9.get('delivery')}")

    # -------------------------------------------------------------
    # Ca 10: Quét toàn bộ static/ đảm bảo không còn demo_otp và demo-otp-val
    # -------------------------------------------------------------
    static_dir = BASE_DIR / "static"
    leak_found = []
    for p in static_dir.rglob("*"):
        if p.is_file() and p.suffix in (".html", ".js", ".css"):
            content = p.read_text(encoding="utf-8", errors="ignore")
            if "demo_otp" in content or "demo-otp-val" in content:
                leak_found.append(p.name)
    c10_ok = (len(leak_found) == 0)
    log_test(10, "Quét toàn bộ static/ sạch chuỗi demo OTP (Vá L8)", c10_ok,
             f"Files rò rỉ: {leak_found if leak_found else 'Không có (100% sạch)'}")

    # -------------------------------------------------------------
    # Ca 11: Sinh mã mới khi mã cũ còn hiệu lực -> mã cũ bị đánh dấu used=1
    # -------------------------------------------------------------
    email11 = f"test_c11_{int(datetime.now().timestamp())}@cozyhome.vn"
    otp11_first = storage.generate_otp(email11, purpose="register")
    with storage.connect() as conn:
        row11_first = conn.execute(
            "SELECT id, used FROM otps WHERE email=? AND purpose='register'",
            (email11,)
        ).fetchone()
        first_id = row11_first["id"]
        assert row11_first["used"] == 0

    # Sinh mã thứ hai cho cùng email và purpose
    otp11_second = storage.generate_otp(email11, purpose="register")
    with storage.connect() as conn:
        row11_old = conn.execute("SELECT used FROM otps WHERE id=?", (first_id,)).fetchone()
        row11_new = conn.execute(
            "SELECT id, used FROM otps WHERE email=? AND purpose='register' ORDER BY id DESC LIMIT 1",
            (email11,)
        ).fetchone()
    c11_ok = (row11_old["used"] == 1 and row11_new["used"] == 0 and row11_new["id"] != first_id)
    log_test(11, "Mã cũ tự động vô hiệu hóa khi phát sinh mã mới (BR-OTP-02)", c11_ok,
             f"Mã cũ used={row11_old['used']}, Mã mới used={row11_new['used']}")

    # -------------------------------------------------------------
    # Ca 12: cleanup_expired_otps() xóa bản ghi quá hạn 24h, giữ mã hợp lệ
    # -------------------------------------------------------------
    email12_old = f"test_c12_old_{int(datetime.now().timestamp())}@cozyhome.vn"
    email12_valid = f"test_c12_valid_{int(datetime.now().timestamp())}@cozyhome.vn"
    old_time = (datetime.now() - timedelta(hours=26)).isoformat(timespec="seconds")
    valid_time = (datetime.now() + timedelta(minutes=5)).isoformat(timespec="seconds")

    with storage.connect() as conn:
        conn.execute(
            "INSERT INTO otps(email, otp_code, purpose, expires_at, used, attempts, sent_status, created_at) VALUES(?,?,?,?,1,0,'sent',?)",
            (email12_old, "dummyhash", "register", old_time, old_time)
        )
        conn.execute(
            "INSERT INTO otps(email, otp_code, purpose, expires_at, used, attempts, sent_status, created_at) VALUES(?,?,?,?,0,0,'sent',?)",
            (email12_valid, "dummyhash2", "register", valid_time, datetime.now().isoformat(timespec="seconds"))
        )

    deleted_count = storage.cleanup_expired_otps()
    with storage.connect() as conn:
        remain_old = conn.execute("SELECT COUNT(*) FROM otps WHERE email=?", (email12_old,)).fetchone()[0]
        remain_valid = conn.execute("SELECT COUNT(*) FROM otps WHERE email=?", (email12_valid,)).fetchone()[0]

    c12_ok = (remain_old == 0 and remain_valid == 1 and deleted_count >= 1)
    log_test(12, "Dọn dẹp bản ghi OTP quá hạn 24 giờ (L9, cleanup_expired_otps)", c12_ok,
             f"Đã xóa: {deleted_count}, Bản ghi cũ còn: {remain_old}, Bản ghi hợp lệ còn: {remain_valid}")

    print("=" * 80)
    print(f"KẾT QUẢ: ĐÃ VƯỢT QUA {passed_cases}/{TOTAL_CASES} CA KIỂM THỬ!")
    print("=" * 80)
    assert passed_cases == TOTAL_CASES, f"Chỉ vượt qua {passed_cases}/{TOTAL_CASES} tests!"


if __name__ == "__main__":
    run_all_tests()
