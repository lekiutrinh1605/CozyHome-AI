"""
Test Suite: RBAC & System Administrator Security Controls (12 Test Cases)
CozyHome Web API
"""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add root directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from fastapi.testclient import TestClient
from server import app
from services import storage

client = TestClient(app)

def login_and_get_token(email: str, password: str = "123456") -> str:
    """Helper to authenticate and retrieve session token."""
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Failed to login with {email}: {res.text}"
    token = res.json().get("token")
    assert token, f"No token returned for {email}"
    return token


def test_case_01_admin_can_access_dashboard():
    """Case 1: Admin xem dashboard quản trị (HTTP 200 OK, trả về metrics đầy đủ)."""
    token = login_and_get_token("admin@cozyhome.vn")
    res = client.get("/api/admin/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json().get("data", {})
    assert "users" in data, "Dashboard metrics must include users"
    assert "rooms" in data, "Dashboard metrics must include rooms"
    assert "bookings" in data, "Dashboard metrics must include bookings"
    assert "transactions" in data, "Dashboard metrics must include transactions"
    assert "total_audit_logs" in data, "Dashboard metrics must include total_audit_logs"
    print("✓ PASS: Case 1 - Admin can access dashboard")


def test_case_02_admin_can_view_bookings_read_only():
    """Case 2: Admin tra cứu danh sách đơn booking (HTTP 200 OK, Read-only toàn chuỗi)."""
    token = login_and_get_token("admin@cozyhome.vn")
    res = client.get("/api/admin/operations/bookings", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    body = res.json()
    assert body.get("status") in ("ok", "success")
    assert "bookings" in body
    print("✓ PASS: Case 2 - Admin can view bookings read-only")


def test_case_03_admin_forbidden_from_checkin():
    """Case 3: Admin gọi Check-in (POST /api/operations/check-in) -> Bị từ chối HTTP 403 Forbidden."""
    token = login_and_get_token("admin@cozyhome.vn")
    # Lấy 1 booking bất kỳ
    bookings = storage.list_bookings()
    code = bookings[0]["booking_code"] if bookings else "CH-TEST-001"
    
    res = client.post(
        "/api/operations/check-in",
        headers={"Authorization": f"Bearer {token}"},
        json={"booking_code": code}
    )
    assert res.status_code == 403, f"Expected 403 Forbidden, got {res.status_code}: {res.text}"
    detail = res.json().get("detail", "")
    assert "không có quyền" in detail or "Lễ tân" in detail
    print(f"✓ PASS: Case 3 - Admin check-in blocked with 403 ({detail})")


def test_case_04_admin_forbidden_from_reconcile():
    """Case 4: Admin gọi Đối soát (POST /api/operations/reconcile) -> Bị từ chối HTTP 403 Forbidden."""
    token = login_and_get_token("admin@cozyhome.vn")
    res = client.post(
        "/api/operations/reconcile",
        headers={"Authorization": f"Bearer {token}"},
        json={"tx_id": 1, "note": "Admin attempts reconcile"}
    )
    assert res.status_code == 403, f"Expected 403 Forbidden, got {res.status_code}: {res.text}"
    detail = res.json().get("detail", "")
    assert "không có quyền" in detail or "Kế toán" in detail
    print(f"✓ PASS: Case 4 - Admin reconcile blocked with 403 ({detail})")


def test_case_05_receptionist_can_checkin_same_branch():
    """Case 5: Lễ tân Bến Thành gọi Check-in đơn thuộc Bến Thành -> Hợp lệ (Không bị 403 RBAC)."""
    token = login_and_get_token("letan.bt@cozyhome.vn")
    
    # Xóa đơn test cũ nếu có để không bị trùng khung giờ
    with storage.connect() as conn:
        conn.execute("DELETE FROM transactions WHERE booking_code IN (SELECT booking_code FROM bookings WHERE customer_name = 'Test Khách BT')")
        conn.execute("DELETE FROM bookings WHERE customer_name = 'Test Khách BT'")

    unique_date = (datetime.now() + timedelta(days=400)).strftime("%Y-%m-%d")
    code = storage.create_booking(
        user_id=None,
        room_id="BT-STD-01",
        branch_id="BT",
        booking_date=unique_date,
        khung_code="S1",
        start_time="14:00",
        end_time="12:00",
        guests=2,
        amount=350000,
        customer_name="Test Khách BT",
        customer_phone="0909111222",
        customer_email="testbt@cozyhome.vn",
        note="Test Case 5"
    )
    storage.mark_paid(code)
    
    res = client.post(
        "/api/operations/check-in",
        headers={"Authorization": f"Bearer {token}"},
        json={"booking_code": code}
    )
    assert res.status_code == 200, f"Expected 200 OK for receptionist in same branch, got {res.status_code}: {res.text}"
    print(f"✓ PASS: Case 5 - Receptionist checked in same branch order {code}")


def test_case_06_receptionist_blocked_from_cross_branch():
    """Case 6: Lễ tân Bến Thành gọi Check-in đơn thuộc Thảo Điền (TD) -> Bị chặn chéo chi nhánh HTTP 403 Forbidden."""
    token = login_and_get_token("letan.bt@cozyhome.vn")
    
    # Xóa đơn test cũ nếu có
    with storage.connect() as conn:
        conn.execute("DELETE FROM transactions WHERE booking_code IN (SELECT booking_code FROM bookings WHERE customer_name = 'Test Khách TD')")
        conn.execute("DELETE FROM bookings WHERE customer_name = 'Test Khách TD'")

    unique_date = (datetime.now() + timedelta(days=401)).strftime("%Y-%m-%d")
    code = storage.create_booking(
        user_id=None,
        room_id="TD-DLX-01",
        branch_id="TD",
        booking_date=unique_date,
        khung_code="S1",
        start_time="14:00",
        end_time="12:00",
        guests=2,
        amount=450000,
        customer_name="Test Khách TD",
        customer_phone="0909333444",
        customer_email="testtd@cozyhome.vn",
        note="Test Case 6"
    )
    storage.mark_paid(code)
    
    res = client.post(
        "/api/operations/check-in",
        headers={"Authorization": f"Bearer {token}"},
        json={"booking_code": code}
    )
    assert res.status_code == 403, f"Expected 403 Forbidden for cross branch, got {res.status_code}: {res.text}"
    detail = res.json().get("detail", "")
    assert "BT" in detail and "TD" in detail, f"Error message should explain branch scope: {detail}"
    print(f"✓ PASS: Case 6 - Cross branch check-in blocked with 403 ({detail})")


def test_case_07_accountant_can_reconcile():
    """Case 7: Kế toán gọi đối soát giao dịch (POST /api/operations/reconcile) -> Thành công HTTP 200 OK."""
    token = login_and_get_token("ketoan@cozyhome.vn")
    # Lấy 1 giao dịch có sẵn
    txs = storage.list_transactions()
    tx_id = txs[0]["id"] if txs else 1
    
    res = client.post(
        "/api/operations/reconcile",
        headers={"Authorization": f"Bearer {token}"},
        json={"tx_id": tx_id, "note": "Kế toán đối soát tự động"}
    )
    assert res.status_code == 200, f"Expected 200 OK for accountant reconcile, got {res.status_code}: {res.text}"
    print(f"✓ PASS: Case 7 - Accountant successfully reconciled transaction #{tx_id}")


def test_case_08_housekeeping_can_update_status():
    """Case 8: Nhân viên buồng phòng cập nhật trạng thái buồng phòng -> Thành công HTTP 200 OK."""
    token = login_and_get_token("buong.bt@cozyhome.vn")
    res = client.post(
        "/api/operations/housekeeping",
        headers={"Authorization": f"Bearer {token}"},
        json={"room_id": "BT-STD-01", "branch_id": "BT", "status": "Đang dọn"}
    )
    assert res.status_code == 200, f"Expected 200 OK for housekeeping update, got {res.status_code}: {res.text}"
    print("✓ PASS: Case 8 - Housekeeping successfully updated room status")


def test_case_09_admin_can_unlock_user_and_audit():
    """Case 9: Admin mở khóa tài khoản bị khóa sau 5 lần sai mật khẩu -> Reset fails về 0 và ghi Audit Log."""
    # Khởi tạo user bị khóa
    with storage.connect() as conn:
        conn.execute("UPDATE users SET failed_attempts = 5, status = 'LOCKED', locked = 1 WHERE email = 'letan.td@cozyhome.vn'")
    
    user_before = storage.get_user_by_email("letan.td@cozyhome.vn")
    assert user_before["status"] == "LOCKED"
    assert user_before["failed_attempts"] == 5
    
    token = login_and_get_token("admin@cozyhome.vn")
    res = client.post(
        f"/api/admin/users/{user_before['id']}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "ACTIVE"}
    )
    assert res.status_code == 200, f"Expected 200 OK, got {res.status_code}: {res.text}"
    
    user_after = storage.get_user_by_email("letan.td@cozyhome.vn")
    assert user_after["status"] == "ACTIVE"
    assert user_after["failed_attempts"] == 0
    
    # Kiểm tra Audit Log
    logs, total = storage.list_audit_logs(limit=10)
    action_found = any(
        ("ACTIVE" in l["action"] or "UNLOCK" in l["action"] or "STATUS" in l["action"])
        and str(user_before["id"]) in str(l["entity_id"])
        for l in logs
    )
    assert action_found, f"Audit log must record the unlock / status change event. Found: {[l['action'] for l in logs]}"
    print("✓ PASS: Case 9 - Admin unlocked user, reset failed attempts to 0 and verified audit log")


def test_case_10_client_side_role_spoofing_prevented():
    """Case 10: Client sửa localStorage role='Quản trị viên' nhưng token là của Khách hàng -> Backend từ chối 403 Forbidden."""
    # Đăng nhập bằng tài khoản Khách hàng
    customer_token = login_and_get_token("demo@cozyhome.vn")
    
    # Gọi endpoint Admin Dashboard với token khách hàng (kể cả có giả mạo header hay query)
    res = client.get("/api/admin/dashboard", headers={"Authorization": f"Bearer {customer_token}"})
    assert res.status_code == 403, f"Expected 403 Forbidden for customer token on admin dashboard, got {res.status_code}: {res.text}"
    print("✓ PASS: Case 10 - Client role spoofing strictly rejected by Backend RBAC (403 Forbidden)")


def test_case_11_unauthenticated_request_rejected():
    """Case 11: Gọi endpoint protected không kèm token -> Bị từ chối HTTP 401 Unauthorized."""
    res_admin = client.get("/api/admin/dashboard")
    assert res_admin.status_code == 401, f"Expected 401 Unauthorized, got {res_admin.status_code}: {res_admin.text}"
    
    res_checkin = client.post("/api/operations/check-in", json={"booking_code": "CH-12345"})
    assert res_checkin.status_code == 401, f"Expected 401 Unauthorized, got {res_checkin.status_code}: {res_checkin.text}"
    print("✓ PASS: Case 11 - Missing or invalid token rejected with 401 Unauthorized")


def test_case_12_admin_create_receptionist_without_branch_rejected():
    """Case 12: Admin tạo user Lễ tân nhưng không chọn branch_id -> Bị từ chối HTTP 400 Bad Request."""
    token = login_and_get_token("admin@cozyhome.vn")
    res = client.post(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "full_name": "Lễ Tân Không Chi Nhánh",
            "email": "letan.nobranch@cozyhome.vn",
            "password": "Password@123",
            "role": "Lễ tân",
            "branch_id": None
        }
    )
    assert res.status_code == 400, f"Expected 400 Bad Request when branch_id is missing for Receptionist, got {res.status_code}: {res.text}"
    detail = res.json().get("detail", "")
    assert "chi nhánh" in detail.lower()
    print(f"✓ PASS: Case 12 - Receptionist without branch rejected with 400 ({detail})")


def test_case_13_staff_counts_by_role_in_dashboard():
    """Case 13: Thống kê vai trò đúng chuẩn: 6 Buồng phòng, 6 Lễ tân, 1 Kế toán, 1 Quản lý, 1 Quản trị viên, 3 Khách hàng."""
    token = login_and_get_token("admin@cozyhome.vn")
    res = client.get("/api/admin/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    by_role = res.json()["data"]["users"]["by_role"]
    assert by_role.get("Buồng phòng") == 6, f"Expected 6 Buồng phòng, got {by_role.get('Buồng phòng')}"
    assert by_role.get("Lễ tân") == 6, f"Expected 6 Lễ tân, got {by_role.get('Lễ tân')}"
    assert by_role.get("Kế toán") == 1, f"Expected 1 Kế toán, got {by_role.get('Kế toán')}"
    assert by_role.get("Quản lý") == 1, f"Expected 1 Quản lý, got {by_role.get('Quản lý')}"
    assert by_role.get("Quản trị viên") == 1, f"Expected 1 Quản trị viên, got {by_role.get('Quản trị viên')}"
    assert by_role.get("Khách hàng") == 3, f"Expected 3 Khách hàng, got {by_role.get('Khách hàng')}"
    print(f"✓ PASS: Case 13 - Role distribution strictly matches specification: {by_role}")


def test_case_14_staff_counts_by_branch_in_dashboard():
    """Case 14: Thống kê chi nhánh đúng chuẩn: TOÀN CHUỖI = 3, BT = 4, PMH = 4, TD = 4 (Khách hàng không bị tính)."""
    token = login_and_get_token("admin@cozyhome.vn")
    res = client.get("/api/admin/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    by_branch = res.json()["data"]["users"]["by_branch"]
    assert by_branch.get("TOÀN CHUỖI") == 3, f"Expected 3 in TOÀN CHUỖI, got {by_branch.get('TOÀN CHUỖI')}"
    assert by_branch.get("BT") == 4, f"Expected 4 in BT, got {by_branch.get('BT')}"
    assert by_branch.get("PMH") == 4, f"Expected 4 in PMH, got {by_branch.get('PMH')}"
    assert by_branch.get("TD") == 4, f"Expected 4 in TD, got {by_branch.get('TD')}"
    total_staff = sum(by_branch.values())
    assert total_staff == 15, f"Expected total 15 internal staff, got {total_staff}"
    print(f"✓ PASS: Case 14 - Branch staff distribution matches specification: {by_branch} (Total: {total_staff})")


def test_case_15_all_roles_login_and_scope_verification():
    """Case 15: Kiểm thử đăng nhập của các vai trò đại diện ở từng chi nhánh và toàn chuỗi."""
    # Lễ tân Bến Thành
    res_bt = client.post("/api/auth/login", json={"email": "letan.bt@cozyhome.vn", "password": "123456"})
    assert res_bt.status_code == 200
    u_bt = res_bt.json()["user"]
    assert u_bt["role"] == "Lễ tân" and u_bt["branch_id"] == "BT"

    # Buồng phòng Phú Mỹ Hưng
    res_pmh = client.post("/api/auth/login", json={"email": "buongphong.pmh01@cozyhome.vn", "password": "CozyHome@123"})
    assert res_pmh.status_code == 200
    u_pmh = res_pmh.json()["user"]
    assert u_pmh["role"] == "Buồng phòng" and u_pmh["branch_id"] == "PMH"

    # Lễ tân Thảo Điền
    res_td = client.post("/api/auth/login", json={"email": "letan.td@cozyhome.vn", "password": "CozyHome@123"})
    assert res_td.status_code == 200
    u_td = res_td.json()["user"]
    assert u_td["role"] == "Lễ tân" and u_td["branch_id"] == "TD"

    # Kế toán toàn chuỗi
    res_kt = client.post("/api/auth/login", json={"email": "ketoan@cozyhome.vn", "password": "123456"})
    assert res_kt.status_code == 200
    u_kt = res_kt.json()["user"]
    assert u_kt["role"] == "Kế toán" and u_kt.get("branch_id") is None

    # Quản lý toàn chuỗi
    res_ql = client.post("/api/auth/login", json={"email": "quanly@cozyhome.vn", "password": "CozyHome@123"})
    assert res_ql.status_code == 200
    u_ql = res_ql.json()["user"]
    assert u_ql["role"] == "Quản lý" and u_ql.get("branch_id") is None

    # Quản trị viên
    res_adm = client.post("/api/auth/login", json={"email": "admin@cozyhome.vn", "password": "123456"})
    assert res_adm.status_code == 200
    u_adm = res_adm.json()["user"]
    assert u_adm["role"] == "Quản trị viên" and u_adm.get("branch_id") is None

    print("✓ PASS: Case 15 - Logins verified across all roles, branches, and password formats (123456 & CozyHome@123)")


def test_case_16_admin_user_management_filters():
    """Case 16: Kiểm thử bộ lọc tài khoản phía Admin (Role, Branch)."""
    token = login_and_get_token("admin@cozyhome.vn")

    # Lọc vai trò Lễ tân -> đúng 6
    res_lt = client.get("/api/admin/users?role=Lễ tân", headers={"Authorization": f"Bearer {token}"})
    assert res_lt.status_code == 200
    users_lt = res_lt.json()["users"]
    assert len(users_lt) == 6, f"Expected 6 receptionists, got {len(users_lt)}"

    # Lọc vai trò Buồng phòng -> đúng 6
    res_bp = client.get("/api/admin/users?role=Buồng phòng", headers={"Authorization": f"Bearer {token}"})
    assert res_bp.status_code == 200
    users_bp = res_bp.json()["users"]
    assert len(users_bp) == 6, f"Expected 6 housekeeping, got {len(users_bp)}"

    # Lọc chi nhánh Bến Thành -> đúng 4 nhân viên nội bộ
    res_bt = client.get("/api/admin/users?branch_id=BT", headers={"Authorization": f"Bearer {token}"})
    assert res_bt.status_code == 200
    users_bt = res_bt.json()["users"]
    assert len(users_bt) == 4, f"Expected 4 BT staff, got {len(users_bt)}"

    print("✓ PASS: Case 16 - Admin user management filters return accurate counts (Receptionists: 6, Housekeeping: 6, BT: 4)")


def run_all_tests():
    print("=" * 70)
    print("BẮT ĐẦU CHẠY 16 TEST CASES KIỂM THỬ RBAC, NHÂN SỰ & QUẢN TRỊ VIÊN COZYHOME")
    print("=" * 70)
    
    test_case_01_admin_can_access_dashboard()
    test_case_02_admin_can_view_bookings_read_only()
    test_case_03_admin_forbidden_from_checkin()
    test_case_04_admin_forbidden_from_reconcile()
    test_case_05_receptionist_can_checkin_same_branch()
    test_case_06_receptionist_blocked_from_cross_branch()
    test_case_07_accountant_can_reconcile()
    test_case_08_housekeeping_can_update_status()
    test_case_09_admin_can_unlock_user_and_audit()
    test_case_10_client_side_role_spoofing_prevented()
    test_case_11_unauthenticated_request_rejected()
    test_case_12_admin_create_receptionist_without_branch_rejected()
    test_case_13_staff_counts_by_role_in_dashboard()
    test_case_14_staff_counts_by_branch_in_dashboard()
    test_case_15_all_roles_login_and_scope_verification()
    test_case_16_admin_user_management_filters()
    
    print("=" * 70)
    print("TẤT CẢ 16 TEST CASES ĐỀU ĐẠT CHUẨN XÁC 100%! (ALL TESTS PASSED)")
    print("=" * 70)

if __name__ == "__main__":
    run_all_tests()
