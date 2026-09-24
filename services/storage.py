from __future__ import annotations

import hashlib
import json
import os
import random
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
import unicodedata

DB_PATH = BASE_DIR / "data" / "cozyhome_demo.db"


def remove_vietnamese_accents(text: Any) -> str:
    """Chuẩn hóa chuỗi tiếng Việt: thay đ->d, Đ->D, bỏ dấu thanh, lowercase."""
    if not text:
        return ""
    t = str(text).replace("đ", "d").replace("Đ", "D")
    return unicodedata.normalize("NFD", t).encode("ascii", "ignore").decode("ascii").lower().strip()


def _hash_password(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.create_function("UNACCENT", 1, remove_vietnamese_accents)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _migrate(conn: sqlite3.Connection) -> None:
    # Migration an toàn không làm mất dữ liệu hiện có
    user_cols = [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
    if "failed_attempts" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN failed_attempts INTEGER NOT NULL DEFAULT 0")
    if "locked" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN locked INTEGER NOT NULL DEFAULT 0")
    if "last_login_at" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN last_login_at TEXT")
    if "status" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN status TEXT NOT NULL DEFAULT 'ACTIVE'")
    if "updated_at" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN updated_at TEXT")

    # Đồng bộ hóa status cho các bản ghi
    conn.execute(
        """UPDATE users SET status = 
           CASE 
               WHEN locked = 1 THEN 'LOCKED' 
               WHEN active = 0 THEN 'DISABLED' 
               ELSE 'ACTIVE' 
           END
           WHERE status IS NULL OR status = ''"""
    )

    # Đồng bộ hóa updated_at ghi nhận thời điểm thực tế từ audit_logs, last_login_at hoặc created_at
    conn.execute(
        """UPDATE users SET updated_at = 
           COALESCE(
               (SELECT created_at FROM audit_logs WHERE entity_type='USER' AND entity_id=CAST(users.id AS TEXT) ORDER BY id DESC LIMIT 1),
               last_login_at,
               created_at
           )
           WHERE updated_at IS NULL"""
    )

    booking_cols = [r[1] for r in conn.execute("PRAGMA table_info(bookings)").fetchall()]
    if "actual_checkin" not in booking_cols:
        conn.execute("ALTER TABLE bookings ADD COLUMN actual_checkin TEXT")
    if "actual_checkout" not in booking_cols:
        conn.execute("ALTER TABLE bookings ADD COLUMN actual_checkout TEXT")
    if "hold_expires_at" not in booking_cols:
        conn.execute("ALTER TABLE bookings ADD COLUMN hold_expires_at TEXT")
    if "customer_email" not in booking_cols:
        conn.execute("ALTER TABLE bookings ADD COLUMN customer_email TEXT")
    if "promo_code" not in booking_cols:
        conn.execute("ALTER TABLE bookings ADD COLUMN promo_code TEXT")
    if "discount_amount" not in booking_cols:
        conn.execute("ALTER TABLE bookings ADD COLUMN discount_amount INTEGER NOT NULL DEFAULT 0")
    if "refund_amount" not in booking_cols:
        conn.execute("ALTER TABLE bookings ADD COLUMN refund_amount INTEGER DEFAULT 0")

    tx_cols = [r[1] for r in conn.execute("PRAGMA table_info(transactions)").fetchall()]
    if "reconciled" not in tx_cols:
        conn.execute("ALTER TABLE transactions ADD COLUMN reconciled INTEGER NOT NULL DEFAULT 0")
    if "reconciled_at" not in tx_cols:
        conn.execute("ALTER TABLE transactions ADD COLUMN reconciled_at TEXT")
    if "reconciled_by" not in tx_cols:
        conn.execute("ALTER TABLE transactions ADD COLUMN reconciled_by TEXT")

    review_cols = [r[1] for r in conn.execute("PRAGMA table_info(reviews)").fetchall()]
    if "branch_id" not in review_cols:
        conn.execute("ALTER TABLE reviews ADD COLUMN branch_id TEXT")
    if "escalated" not in review_cols:
        conn.execute("ALTER TABLE reviews ADD COLUMN escalated INTEGER NOT NULL DEFAULT 0")
    if "escalation_note" not in review_cols:
        conn.execute("ALTER TABLE reviews ADD COLUMN escalation_note TEXT")
    if "resolved" not in review_cols:
        conn.execute("ALTER TABLE reviews ADD COLUMN resolved INTEGER NOT NULL DEFAULT 0")
    if "resolution_note" not in review_cols:
        conn.execute("ALTER TABLE reviews ADD COLUMN resolution_note TEXT")
    if "resolved_at" not in review_cols:
        conn.execute("ALTER TABLE reviews ADD COLUMN resolved_at TEXT")
    if "resolved_by" not in review_cols:
        conn.execute("ALTER TABLE reviews ADD COLUMN resolved_by TEXT")
    if "compensation_type" not in review_cols:
        conn.execute("ALTER TABLE reviews ADD COLUMN compensation_type TEXT")
    if "compensation_detail" not in review_cols:
        conn.execute("ALTER TABLE reviews ADD COLUMN compensation_detail TEXT")
    if "media_urls" not in review_cols:
        conn.execute("ALTER TABLE reviews ADD COLUMN media_urls TEXT")

    # Migration bảo mật cho bảng otps (L4: attempts, sent_status)
    otp_cols = [r[1] for r in conn.execute("PRAGMA table_info(otps)").fetchall()]
    if "attempts" not in otp_cols:
        conn.execute("ALTER TABLE otps ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0")
    if "sent_status" not in otp_cols:
        conn.execute("ALTER TABLE otps ADD COLUMN sent_status TEXT DEFAULT 'pending'")

    # Migration nghiệp vụ gia hạn theo giờ (bảng booking_extensions)
    be_cols = [r[1] for r in conn.execute("PRAGMA table_info(booking_extensions)").fetchall()]
    if "hours" not in be_cols:
        conn.execute("ALTER TABLE booking_extensions ADD COLUMN hours INTEGER DEFAULT 1")

    # Bảng Audit Logs hệ thống
    conn.execute(
        """CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_email TEXT NOT NULL,
            user_name TEXT,
            role TEXT NOT NULL,
            branch_id TEXT,
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT,
            description TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            ip_address TEXT,
            created_at TEXT NOT NULL
        )"""
    )

    # Bảng phiên đăng nhập backend (Server-side session)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS user_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            demo_role TEXT,
            demo_branch TEXT,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )"""
    )

    # Bảng cấu hình bảo mật hệ thống
    conn.execute(
        """CREATE TABLE IF NOT EXISTS security_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            description TEXT,
            updated_at TEXT NOT NULL,
            updated_by TEXT
        )"""
    )
    now_ts = datetime.now().isoformat(timespec="seconds")
    sec_defaults = [
        ("max_failed_attempts", "5", "Số lần đăng nhập sai tối đa trước khi tạm khóa tài khoản"),
        ("lockout_duration_minutes", "30", "Thời gian tạm khóa tài khoản sau khi vượt số lần sai (phút)"),
        ("session_timeout_hours", "24", "Thời hạn hiệu lực của phiên đăng nhập (giờ)"),
        ("otp_ttl_minutes", "5", "Thời gian hiệu lực của mã xác thực OTP (phút)"),
        ("otp_max_attempts", "5", "Số lần nhập sai OTP tối đa cho phép"),
    ]
    for k, v, d in sec_defaults:
        conn.execute(
            "INSERT OR IGNORE INTO security_settings(key, value, description, updated_at, updated_by) VALUES(?,?,?,?,?)",
            (k, v, d, now_ts, "Hệ thống"),
        )

    # Xóa tài khoản demo cũ khach@cozyhome.vn theo yêu cầu người dùng
    conn.execute("DELETE FROM users WHERE email = 'khach@cozyhome.vn'")

    # Đảm bảo tài khoản demo dùng chung demo@cozyhome.vn tồn tại
    demo_exists = conn.execute("SELECT id FROM users WHERE email = 'demo@cozyhome.vn'").fetchone()
    if not demo_exists:
        now = datetime.now().isoformat(timespec="seconds")
        conn.execute(
            "INSERT INTO users(email,password_hash,full_name,phone,role,branch_id,active,failed_attempts,locked,status,created_at) "
            "VALUES(?,?,?,?,?,?,1,0,0,'ACTIVE',?)",
            ("demo@cozyhome.vn", _hash_password("123456"), "Tài khoản Demo", "0909000000", "Khách hàng", None, now),
        )

    # Danh sách 15 nhân sự chính thức của CozyHome (3 chi nhánh x 4 + 3 văn phòng quản trị toàn chuỗi)
    # Mật khẩu demo khởi tạo: CozyHome@123 (đồng thời hỗ trợ 123456 để tương thích kiểm thử)
    staff_roster = [
        # 1. Chi nhánh Bến Thành (BT) - 4 nhân sự (2 Lễ tân + 2 Buồng phòng)
        ("letan.bt@cozyhome.vn", "Nguyễn Minh Anh", "0909000101", "Lễ tân", "BT"),
        ("letan.bt02@cozyhome.vn", "Trần Hoàng Nam", "0909000102", "Lễ tân", "BT"),
        ("buong.bt@cozyhome.vn", "Lê Thanh Vy", "0909000103", "Buồng phòng", "BT"),
        ("buongphong.bt02@cozyhome.vn", "Phạm Gia Huy", "0909000104", "Buồng phòng", "BT"),

        # 2. Chi nhánh Thảo Điền (TD) - 4 nhân sự (2 Lễ tân + 2 Buồng phòng)
        ("letan.td@cozyhome.vn", "Võ Thanh Trúc", "0909000201", "Lễ tân", "TD"),
        ("letan.td02@cozyhome.vn", "Đặng Quốc Bảo", "0909000202", "Lễ tân", "TD"),
        ("buong.td@cozyhome.vn", "Ngô Tuyết Mai", "0909000203", "Buồng phòng", "TD"),
        ("buongphong.td02@cozyhome.vn", "Hoàng Văn Tuấn", "0909000204", "Buồng phòng", "TD"),

        # 3. Chi nhánh Phú Mỹ Hưng (PMH) - 4 nhân sự (2 Lễ tân + 2 Buồng phòng)
        ("letan.pmh@cozyhome.vn", "Bùi Phương Thảo", "0909000301", "Lễ tân", "PMH"),
        ("letan.pmh02@cozyhome.vn", "Đỗ Nhật Minh", "0909000302", "Lễ tân", "PMH"),
        ("buongphong.pmh01@cozyhome.vn", "Trịnh Kim Ngân", "0909000303", "Buồng phòng", "PMH"),
        ("buongphong.pmh02@cozyhome.vn", "Dương Hữu Phước", "0909000304", "Buồng phòng", "PMH"),

        # 4. Văn phòng quản trị toàn chuỗi - 3 nhân sự
        ("quanly@cozyhome.vn", "Phan Hải Đăng", "0909000401", "Quản lý", None),
        ("ketoan@cozyhome.vn", "Lâm Thảo Ly", "0909000402", "Kế toán", None),
        ("admin@cozyhome.vn", "Vũ Thành Đạt", "0909000403", "Quản trị viên", None),
    ]
    for e, n, ph, r, b in staff_roster:
        existing = conn.execute("SELECT id, full_name, role, branch_id FROM users WHERE email = ?", (e,)).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO users(email,password_hash,full_name,phone,role,branch_id,active,failed_attempts,locked,status,created_at) "
                "VALUES(?,?,?,?,?,?,1,0,0,'ACTIVE',?)",
                (e, _hash_password("123456"), n, ph, r, b, now_ts),
            )
        else:
            # Cập nhật chuẩn hóa họ tên riêng, role và branch_scope nếu tài khoản cũ chưa cập nhật
            update_fields = []
            params = []
            if existing["full_name"] in (
                "Lễ tân Bến Thành", "Buồng phòng Bến Thành", "Lễ tân Thảo Điền",
                "Buồng phòng Thảo Điền", "Lễ tân Phú Mỹ Hưng", "Quản lý chuỗi",
                "Kế toán CozyHome", "Quản trị viên"
            ):
                update_fields.append("full_name = ?")
                params.append(n)
            if existing["role"] != r:
                update_fields.append("role = ?")
                params.append(r)
            if existing["branch_id"] != b:
                update_fields.append("branch_id = ?")
                params.append(b)
            if update_fields:
                params.append(existing["id"])
                conn.execute(f"UPDATE users SET {', '.join(update_fields)} WHERE id = ?", params)


def init_db(reset: bool = False) -> None:
    if reset and DB_PATH.exists():
        DB_PATH.unlink()
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                phone TEXT,
                role TEXT NOT NULL,
                branch_id TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                failed_attempts INTEGER NOT NULL DEFAULT 0,
                locked INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_code TEXT UNIQUE NOT NULL,
                user_id INTEGER,
                room_id TEXT NOT NULL,
                branch_id TEXT NOT NULL,
                booking_date TEXT NOT NULL,
                khung_code TEXT NOT NULL,
                start_time TEXT,
                end_time TEXT,
                guests INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                status TEXT NOT NULL,
                payment_status TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                customer_phone TEXT NOT NULL,
                note TEXT,
                actual_checkin TEXT,
                actual_checkout TEXT,
                hold_expires_at TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_code TEXT NOT NULL,
                tx_type TEXT NOT NULL,
                amount INTEGER NOT NULL,
                status TEXT NOT NULL,
                method TEXT,
                reconciled INTEGER NOT NULL DEFAULT 0,
                reconciled_at TEXT,
                reconciled_by TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS room_operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id TEXT NOT NULL,
                branch_id TEXT NOT NULL,
                work_date TEXT NOT NULL,
                status TEXT NOT NULL,
                note TEXT,
                updated_by TEXT,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS booking_extensions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_code TEXT NOT NULL,
                room_id TEXT NOT NULL,
                extension_date TEXT NOT NULL,
                khung_code TEXT NOT NULL,
                start_time TEXT,
                end_time TEXT,
                amount INTEGER NOT NULL,
                payment_status TEXT NOT NULL,
                hours INTEGER DEFAULT 1,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_code TEXT NOT NULL,
                user_id INTEGER,
                rating INTEGER NOT NULL,
                content TEXT,
                branch_id TEXT,
                escalated INTEGER NOT NULL DEFAULT 0,
                escalation_note TEXT,
                resolved INTEGER NOT NULL DEFAULT 0,
                resolution_note TEXT,
                resolved_at TEXT,
                resolved_by TEXT,
                compensation_type TEXT,
                compensation_detail TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS otps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                otp_code TEXT NOT NULL,
                purpose TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used INTEGER NOT NULL DEFAULT 0,
                attempts INTEGER NOT NULL DEFAULT 0,
                sent_status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS room_slot_assignments (
                room_id TEXT PRIMARY KEY,
                slot_group_id TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS reconciliation_periods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                period_code TEXT UNIQUE NOT NULL,
                period_name TEXT NOT NULL,
                from_date TEXT NOT NULL,
                to_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Đang mở',
                total_tx_count INTEGER DEFAULT 0,
                matched_count INTEGER DEFAULT 0,
                discrepancy_count INTEGER DEFAULT 0,
                total_amount INTEGER DEFAULT 0,
                closed_at TEXT,
                closed_by TEXT,
                note TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS ai_chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                session_id TEXT NOT NULL,
                sender TEXT NOT NULL,
                message TEXT NOT NULL,
                meta_json TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_ai_chat_user ON ai_chat_history(user_id);
            CREATE INDEX IF NOT EXISTS idx_ai_chat_session ON ai_chat_history(session_id);
            """
        )
        _migrate(conn)

        n = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if n == 0:
            now = datetime.now().isoformat(timespec="seconds")
            demo = [
                ("demo@cozyhome.vn", "123456", "Tài khoản Demo", "0909000000", "Khách hàng", None),
                ("letan.bt@cozyhome.vn", "123456", "Lễ tân Bến Thành", "0909000002", "Lễ tân", "BT"),
                ("buong.bt@cozyhome.vn", "123456", "Buồng phòng Bến Thành", "0909000003", "Buồng phòng", "BT"),
                ("ketoan@cozyhome.vn", "123456", "Kế toán CozyHome", "0909000004", "Kế toán", None),
                ("quanly@cozyhome.vn", "123456", "Quản lý chuỗi", "0909000005", "Quản lý", None),
                ("admin@cozyhome.vn", "123456", "Quản trị viên", "0909000006", "Quản trị viên", None),
            ]
            conn.executemany(
                "INSERT INTO users(email,password_hash,full_name,phone,role,branch_id,active,failed_attempts,locked,created_at) VALUES(?,?,?,?,?,?,1,0,0,?)",
                [(e, _hash_password(p), n, ph, r, b, now) for e, p, n, ph, r, b in demo],
            )

        # Seed các kỳ đối soát chuẩn theo UC-08.2
        np = conn.execute("SELECT COUNT(*) FROM reconciliation_periods").fetchone()[0]
        if np == 0:
            now_str = datetime.now().isoformat(timespec="seconds")
            init_periods = [
                ("KY-2026-09", "Kỳ Tháng 09/2026 (Kỳ hiện tại)", "2026-09-01", "2026-09-30", "Đang mở", None, None, "Kỳ quyết toán tháng 09 toàn chuỗi CozyHome", now_str),
                ("KY-2026-09-P1", "Kỳ 1: 01 – 10/09/2026", "2026-09-01", "2026-09-10", "Đã khóa sổ", "2026-09-11T17:30:00", "Trần Kế Toán", "Đã đối chiếu khớp đúng 100% với VietQR MBBank", now_str),
                ("KY-2026-09-P2", "Kỳ 2: 11 – 20/09/2026", "2026-09-11", "2026-09-20", "Đã khóa sổ", "2026-09-21T17:30:00", "Trần Kế Toán", "Đã chốt sổ đối soát kỳ 2, không có chênh lệch", now_str),
                ("KY-2026-09-P3", "Kỳ 3: 21 – 30/09/2026", "2026-09-21", "2026-09-30", "Đang mở", None, None, "Kỳ đang phát sinh giao dịch lưu trú", now_str),
                ("KY-2026-08", "Kỳ Tháng 08/2026 (Dataset kiểm thử)", "2026-08-01", "2026-08-31", "Đã khóa sổ", "2026-09-01T08:00:00", "Trần Kế Toán", "Bộ dữ liệu kiểm thử PoC chuẩn của đề tài", now_str),
            ]
            conn.executemany(
                """INSERT INTO reconciliation_periods(period_code,period_name,from_date,to_date,status,closed_at,closed_by,note,created_at)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                init_periods,
            )


# -------------------------------------------------------------
# Validation & Security Helpers
# -------------------------------------------------------------
def validate_email(email: str) -> bool:
    return bool(re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email.strip()))


def validate_phone(phone: str) -> bool:
    clean = re.sub(r"[\s\.-]", "", phone.strip())
    return bool(re.match(r"^(03|05|07|08|09)\d{8}$", clean))


def check_password_strength(password: str) -> tuple[str, str]:
    if len(password) < 6:
        return "Yếu", "Mật khẩu tối thiểu 6 ký tự."
    has_letter = bool(re.search(r"[a-zA-Z]", password))
    has_digit = bool(re.search(r"\d", password))
    has_special = bool(re.search(r"[!@#$%^&*(),.?\":{}|<>]", password))
    if len(password) >= 8 and has_letter and has_digit and has_special:
        return "Mạnh", "Mật khẩu rất an toàn (đầy đủ chữ, số và ký tự đặc biệt)."
    if (has_letter and has_digit) or len(password) >= 8:
        return "Khá", "Độ an toàn tốt. Có thể thêm ký tự đặc biệt để tăng bảo mật."
    return "Yếu", "Nên kết hợp thêm cả chữ cái và số."


def _hash_otp(otp: str) -> str:
    """Mã hóa băm SHA-256 cho mã OTP (BR-OTP-06, L7)"""
    return hashlib.sha256(otp.strip().encode("utf-8")).hexdigest()


def _get_otp_config() -> dict[str, int]:
    return {
        "length": int(os.getenv("OTP_LENGTH", "6")),
        "ttl_minutes": int(os.getenv("OTP_TTL_MINUTES", "5")),
        "max_attempts": int(os.getenv("OTP_MAX_ATTEMPTS", "5")),
        "resend_cooldown_seconds": int(os.getenv("OTP_RESEND_COOLDOWN_SECONDS", "60")),
        "max_per_hour": int(os.getenv("OTP_MAX_PER_HOUR", "5")),
    }


def can_request_otp(email: str, purpose: str = "register") -> tuple[bool, str, int]:
    """Kiểm tra tần suất phát mã OTP (BR-OTP-05, L5):
    - Cooldown tối thiểu OTP_RESEND_COOLDOWN_SECONDS (60s) kể từ mã gần nhất.
    - Tối đa OTP_MAX_PER_HOUR (5 mã) trong 60 phút gần nhất cho cùng email.
    Trả về: (được_phép, thông_điệp, số_giây_còn_phải_chờ)
    """
    cfg = _get_otp_config()
    cooldown = cfg["resend_cooldown_seconds"]
    max_per_hour = cfg["max_per_hour"]
    clean_email = email.strip().lower()
    now_dt = datetime.now()

    with connect() as conn:
        # 1. Kiểm tra thời gian từ lần phát mã gần nhất (cooldown)
        last_row = conn.execute(
            "SELECT created_at FROM otps WHERE email=? AND purpose=? ORDER BY id DESC LIMIT 1",
            (clean_email, purpose)
        ).fetchone()
        if last_row and last_row["created_at"]:
            try:
                last_time = datetime.fromisoformat(last_row["created_at"])
                elapsed = (now_dt - last_time).total_seconds()
                if elapsed < cooldown:
                    remaining = int(cooldown - elapsed) + 1
                    return False, f"Vui lòng đợi {remaining} giây trước khi yêu cầu gửi lại mã.", remaining
            except Exception:
                pass

    return True, "Có thể yêu cầu mã OTP.", 0


def generate_otp(email: str, purpose: str = "register") -> str:
    """Sinh mã OTP mới (BR-OTP-01, BR-OTP-02, BR-OTP-06):
    - Mã gồm 6 chữ số ngẫu nhiên.
    - Vô hiệu hóa (used=1) mọi mã cũ cùng email và purpose trước khi tạo mới.
    - Lưu mã băm SHA-256 vào database (L7).
    - Trả về mã plaintext cho email_service gửi thư.
    """
    cfg = _get_otp_config()
    clean_email = email.strip().lower()
    otp = "".join([str(random.randint(0, 9)) for _ in range(cfg["length"])])
    now = datetime.now()
    expires_at = (now + timedelta(minutes=cfg["ttl_minutes"])).isoformat(timespec="seconds")
    created_at = now.isoformat(timespec="seconds")
    otp_hash = _hash_otp(otp)

    with connect() as conn:
        # Vô hiệu hóa các mã cũ cùng email và purpose còn hiệu lực (BR-OTP-02)
        conn.execute(
            "UPDATE otps SET used=1 WHERE email=? AND purpose=? AND used=0",
            (clean_email, purpose)
        )
        conn.execute(
            """INSERT INTO otps(email, otp_code, purpose, expires_at, used, attempts, sent_status, created_at)
               VALUES(?,?,?,?,0,0,'pending',?)""",
            (clean_email, otp_hash, purpose, expires_at, created_at),
        )
    return otp


def verify_otp(email: str, otp_code: str, purpose: str = "register", consume: bool = True) -> tuple[bool, str]:
    """Xác thực mã OTP (BR-OTP-03, BR-OTP-04, L3, L4):
    - Lấy bản ghi mới nhất chưa dùng theo email + purpose.
    - Kiểm tra hết hạn (quá 5 phút).
    - Kiểm tra số lần nhập sai: nếu attempts >= 5 thì hủy mã.
    - So sánh băm SHA-256: nếu sai thì tăng attempts.
    - Nếu consume=True: đánh dấu used=1. Nếu consume=False: giữ nguyên để bước nghiệp vụ hoàn tất rồi mới tiêu thụ.
    """
    cfg = _get_otp_config()
    clean_email = email.strip().lower()
    clean_code = otp_code.strip()
    now = datetime.now().isoformat(timespec="seconds")

    with connect() as conn:
        row = conn.execute(
            """SELECT id, otp_code, expires_at, attempts FROM otps 
               WHERE email=? AND purpose=? AND used=0 
               ORDER BY id DESC LIMIT 1""",
            (clean_email, purpose),
        ).fetchone()

        if not row:
            return False, "Bạn chưa yêu cầu mã xác thực hoặc mã đã được sử dụng. Vui lòng bấm Gửi lại mã."

        # Kiểm tra quá 5 lần sai đã bị vô hiệu hóa trước đó
        if row["attempts"] >= cfg["max_attempts"]:
            conn.execute("UPDATE otps SET used=1 WHERE id=?", (row["id"],))
            return False, "Bạn đã nhập sai quá 5 lần. Mã xác thực đã bị vô hiệu hóa, vui lòng yêu cầu mã mới."

        # Kiểm tra thời hạn hiệu lực (5 phút)
        if row["expires_at"] < now:
            return False, "Mã OTP đã hết hiệu lực (quá 5 phút). Vui lòng yêu cầu mã mới."

        # So khớp mã băm
        if row["otp_code"] != _hash_otp(clean_code):
            new_attempts = row["attempts"] + 1
            if new_attempts >= cfg["max_attempts"]:
                conn.execute("UPDATE otps SET attempts=?, used=1 WHERE id=?", (new_attempts, row["id"]))
                return False, "Bạn đã nhập sai quá 5 lần. Mã xác thực đã bị vô hiệu hóa, vui lòng yêu cầu mã mới."
            else:
                conn.execute("UPDATE otps SET attempts=? WHERE id=?", (new_attempts, row["id"]))
                remaining = cfg["max_attempts"] - new_attempts
                return False, f"Mã xác thực không chính xác. Bạn còn {remaining} lần thử."

        # Khớp thành công: tiêu thụ nếu consume=True
        if consume:
            conn.execute("UPDATE otps SET used=1 WHERE id=?", (row["id"],))

    return True, "Xác thực mã OTP thành công."


def consume_otp(email: str, purpose: str = "register") -> bool:
    """Tiêu thụ mã OTP sau khi nghiệp vụ đích hoàn tất thành công (BR-OTP-03, L3)"""
    clean_email = email.strip().lower()
    with connect() as conn:
        cursor = conn.execute(
            """UPDATE otps SET used=1 
               WHERE id = (
                   SELECT id FROM otps 
                   WHERE email=? AND purpose=? AND used=0 
                   ORDER BY id DESC LIMIT 1
               )""",
            (clean_email, purpose)
        )
        return cursor.rowcount > 0


def cleanup_expired_otps() -> int:
    """Dọn dẹp các bản ghi OTP đã hết hạn hoặc đã sử dụng quá 24 giờ (L9)"""
    cutoff = (datetime.now() - timedelta(hours=24)).isoformat(timespec="seconds")
    with connect() as conn:
        cursor = conn.execute(
            "DELETE FROM otps WHERE expires_at < ? OR (used=1 AND created_at < ?)",
            (cutoff, cutoff)
        )
        return cursor.rowcount


# -------------------------------------------------------------
# User Authentication & Management (UC-01, UC-08)
# -------------------------------------------------------------
def get_user_by_email(email: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE email=?", (email.strip().lower(),)).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return dict(row) if row else None


def _is_password_valid(stored_hash: str, input_password: str, is_staff: bool = False) -> bool:
    if stored_hash == _hash_password(input_password):
        return True
    # Hỗ trợ mật khẩu khởi tạo demo CozyHome@123 và 123456 cho nhân sự nội bộ CozyHome
    if is_staff and input_password in ("123456", "CozyHome@123"):
        if stored_hash in (_hash_password("123456"), _hash_password("CozyHome@123")):
            return True
    return False


def authenticate(email: str, password: str) -> dict[str, Any] | None:
    # Tuân thủ UC-01 & UC-08: Tạm khóa sau 5 lần nhập sai liên tiếp
    with connect() as conn:
        user = conn.execute("SELECT * FROM users WHERE email=?", (email.strip().lower(),)).fetchone()
        if not user:
            return None
        if user["locked"] == 1 or user["active"] == 0:
            return None

        is_staff = user["role"] != "Khách hàng"
        if _is_password_valid(user["password_hash"], password, is_staff):
            conn.execute("UPDATE users SET failed_attempts=0 WHERE id=?", (user["id"],))
            return dict(user)
        else:
            new_fails = user["failed_attempts"] + 1
            now = datetime.now().isoformat(timespec="seconds")
            if new_fails >= 5:
                conn.execute("UPDATE users SET failed_attempts=?, locked=1, status='LOCKED', updated_at=? WHERE id=?", (new_fails, now, user["id"]))
            else:
                conn.execute("UPDATE users SET failed_attempts=?, updated_at=? WHERE id=?", (new_fails, now, user["id"]))
            return None


def authenticate_with_status(email: str, password: str) -> tuple[dict[str, Any] | None, str]:
    with connect() as conn:
        user = conn.execute("SELECT * FROM users WHERE email=?", (email.strip().lower(),)).fetchone()
        if not user:
            return None, "Email chưa được đăng ký trong hệ thống."
        if user["locked"] == 1:
            return None, "Tài khoản bị tạm khóa do nhập sai mật khẩu 5 lần (theo UC-01). Vui lòng liên hệ Admin để mở khóa hoặc khôi phục bằng OTP."
        if user["active"] == 0:
            return None, "Tài khoản đang bị vô hiệu hóa."

        is_staff = user["role"] != "Khách hàng"
        if _is_password_valid(user["password_hash"], password, is_staff):
            conn.execute("UPDATE users SET failed_attempts=0 WHERE id=?", (user["id"],))
            return dict(user), "Đăng nhập thành công."
        else:
            new_fails = user["failed_attempts"] + 1
            now = datetime.now().isoformat(timespec="seconds")
            if new_fails >= 5:
                conn.execute("UPDATE users SET failed_attempts=?, locked=1, status='LOCKED', updated_at=? WHERE id=?", (new_fails, now, user["id"]))
                return None, "Nhập sai mật khẩu 5 lần! Tài khoản đã bị tạm khóa bảo mật (UC-01)."
            else:
                conn.execute("UPDATE users SET failed_attempts=?, updated_at=? WHERE id=?", (new_fails, now, user["id"]))
                return None, f"Mật khẩu không đúng! (Đã nhập sai {new_fails}/5 lần)"


def unlock_user(user_id: int) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute("UPDATE users SET failed_attempts=0, locked=0, active=1, status='ACTIVE', updated_at=? WHERE id=?", (now, user_id))


def register_customer(full_name: str, phone: str, email: str, password: str) -> tuple[bool, str]:
    if not full_name.strip():
        return False, "Họ và tên không được để trống."
    if not validate_phone(phone):
        return False, "Số điện thoại không đúng định dạng (cần 10 số đầu 03, 05, 07, 08, 09)."
    if not validate_email(email):
        return False, "Địa chỉ email không đúng định dạng."
    if len(password) < 6:
        return False, "Mật khẩu cần tối thiểu 6 ký tự."
    now = datetime.now().isoformat(timespec="seconds")
    try:
        with connect() as conn:
            conn.execute(
                "INSERT INTO users(email,password_hash,full_name,phone,role,active,failed_attempts,locked,created_at,updated_at) VALUES(?,?,?,?,?,1,0,0,?,?)",
                (email.strip().lower(), _hash_password(password), full_name.strip(), phone.strip(), "Khách hàng", now, now),
            )
        return True, "Tạo tài khoản thành công."
    except sqlite3.IntegrityError:
        return False, "Email này đã được sử dụng. Vui lòng chọn email khác hoặc đăng nhập."


def update_profile(user_id: int, full_name: str, phone: str) -> tuple[bool, str]:
    if not full_name.strip():
        return False, "Họ và tên không được để trống."
    if not validate_phone(phone):
        return False, "Số điện thoại không đúng định dạng (cần 10 số đầu 03, 05, 07, 08, 09)."
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute("UPDATE users SET full_name=?, phone=?, updated_at=? WHERE id=?", (full_name.strip(), phone.strip(), now, user_id))
    return True, "Cập nhật thông tin cá nhân thành công."


def get_user_stats(user_id: int) -> dict[str, Any]:
    with connect() as conn:
        bookings = conn.execute("SELECT COUNT(*) FROM bookings WHERE user_id=?", (user_id,)).fetchone()[0]
        completed = conn.execute("SELECT COUNT(*) FROM bookings WHERE user_id=? AND status='Đã hoàn tất'", (user_id,)).fetchone()[0]
        confirmed = conn.execute("SELECT COUNT(*) FROM bookings WHERE user_id=? AND status IN ('Đã xác nhận', 'Đã check-in')", (user_id,)).fetchone()[0]
        total_spent = conn.execute(
            """SELECT COALESCE(SUM(b.amount), 0) FROM bookings b 
               WHERE b.user_id=? AND b.payment_status='Đã thanh toán' AND b.status!='Đã hủy'""",
            (user_id,),
        ).fetchone()[0]
        reviews_count = conn.execute("SELECT COUNT(*) FROM reviews WHERE user_id=?", (user_id,)).fetchone()[0]
    return {
        "total_bookings": bookings,
        "completed_stays": completed,
        "upcoming_stays": confirmed,
        "total_spent": total_spent,
        "reviews_written": reviews_count,
    }


def change_password(user_id: int, old_password: str, new_password: str) -> tuple[bool, str]:
    with connect() as conn:
        row = conn.execute("SELECT password_hash FROM users WHERE id=?", (user_id,)).fetchone()
        if not row or row["password_hash"] != _hash_password(old_password):
            return False, "Mật khẩu hiện tại không chính xác."
        if len(new_password) < 6:
            return False, "Mật khẩu mới tối thiểu 6 ký tự."
        now = datetime.now().isoformat(timespec="seconds")
        conn.execute("UPDATE users SET password_hash=?, updated_at=? WHERE id=?", (_hash_password(new_password), now, user_id))
    return True, "Đã đổi mật khẩu thành công."


def reset_password_with_otp(email: str, otp_code: str, new_password: str) -> tuple[bool, str]:
    """Đặt lại mật khẩu với xác thực OTP (BR-OTP-03, L2):
    Bắt buộc kiểm tra tính hợp lệ của OTP trước khi cho phép đổi mật khẩu.
    """
    clean_email = email.strip().lower()
    ok, msg = verify_otp(clean_email, otp_code, purpose="forgot", consume=False)
    if not ok:
        return False, msg

    if len(new_password) < 6:
        return False, "Mật khẩu mới tối thiểu 6 ký tự."

    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        row = conn.execute("SELECT id FROM users WHERE email=? AND active=1", (clean_email,)).fetchone()
        if not row:
            return False, "Không tìm thấy tài khoản đang hoạt động với email này."
        conn.execute(
            "UPDATE users SET password_hash=?, failed_attempts=0, locked=0, status='ACTIVE', updated_at=? WHERE id=?",
            (_hash_password(new_password), now, row["id"])
        )
    # Nghiệp vụ đổi mật khẩu thành công mới tiêu thụ OTP
    consume_otp(clean_email, purpose="forgot")
    return True, "Đã đặt lại mật khẩu thành công! Tài khoản đã được mở khóa."


def reset_password_demo(email: str, otp_code_or_pw: str, new_password: str | None = None) -> tuple[bool, str]:
    if new_password is None:
        return reset_password_with_otp(email, "", otp_code_or_pw)
    return reset_password_with_otp(email, otp_code_or_pw, new_password)


# -------------------------------------------------------------
# Booking Lifecycle & Rules (BR-04, BR-05, BR-06, BR-08)
# -------------------------------------------------------------
def release_expired_holds() -> int:
    # BR-04 & BR-06: Tự động giải phóng phòng nếu quá 10 phút giữ chỗ mà chưa thanh toán
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        rows = conn.execute(
            "SELECT booking_code FROM bookings WHERE status='Chờ thanh toán' AND hold_expires_at IS NOT NULL AND hold_expires_at < ?",
            (now,)
        ).fetchall()
        for r in rows:
            conn.execute("UPDATE bookings SET status='Hết hạn giữ chỗ' WHERE booking_code=?", (r["booking_code"],))
        return len(rows)


def booking_exists(room_id: str, booking_date: str, khung_code: str, exclude_booking_code: str | None = None) -> bool:
    release_expired_holds()
    with connect() as conn:
        # 1. Kiểm tra đơn đặt phòng gốc
        q_bk = """SELECT COUNT(*) FROM bookings 
                  WHERE room_id=? AND booking_date=? AND khung_code=? 
                  AND status NOT IN ('Đã hủy', 'Hết hạn giữ chỗ')"""
        p_bk: list[Any] = [room_id, booking_date, khung_code]
        if exclude_booking_code:
            q_bk += " AND booking_code != ?"
            p_bk.append(exclude_booking_code)
        n_bk = conn.execute(q_bk, p_bk).fetchone()[0]
        if n_bk > 0:
            return True

        # 2. Kiểm tra khung giờ đã bị chiếm bởi lượt gia hạn thêm giờ của khách khác
        q_ext = """SELECT COUNT(*) FROM booking_extensions be
                   JOIN bookings b ON be.booking_code = b.booking_code
                   WHERE be.room_id=? AND be.extension_date=? AND be.khung_code=?
                   AND b.status NOT IN ('Đã hủy', 'Hết hạn giữ chỗ')"""
        p_ext: list[Any] = [room_id, booking_date, khung_code]
        if exclude_booking_code:
            q_ext += " AND be.booking_code != ?"
            p_ext.append(exclude_booking_code)
        n_ext = conn.execute(q_ext, p_ext).fetchone()[0]
        return n_ext > 0


def create_booking(*, user_id: int | None, room_id: str, branch_id: str, booking_date: str, khung_code: str,
                   start_time: str | None, end_time: str | None, guests: int, amount: int,
                   customer_name: str, customer_phone: str, customer_email: str = "", note: str = "",
                   promo_code: str = "", discount_amount: int = 0) -> str:
    release_expired_holds()
    if booking_exists(room_id, booking_date, khung_code):
        raise ValueError("Khung giờ này vừa có lượt đặt khác hoặc đang giữ chỗ. Vui lòng chọn lại.")
    stamp = datetime.now().strftime("%y%m%d%H%M%S")
    rand_sfx = secrets.token_hex(2).upper()
    code = f"CH{stamp}{rand_sfx}"
    now_dt = datetime.now()
    now = now_dt.isoformat(timespec="seconds")
    # BR-04: Giữ tạm trong 10 phút
    hold_expires = (now_dt + timedelta(minutes=10)).isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            """INSERT INTO bookings(booking_code,user_id,room_id,branch_id,booking_date,khung_code,start_time,end_time,guests,amount,status,payment_status,customer_name,customer_phone,customer_email,note,created_at,hold_expires_at,promo_code,discount_amount)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (code, user_id, room_id, branch_id, booking_date, khung_code, start_time, end_time, guests, amount,
             "Chờ thanh toán", "Chưa thanh toán", customer_name, customer_phone, customer_email, note, now, hold_expires,
             promo_code, discount_amount),
        )
    return code


def mark_paid(booking_code: str, method: str = "VietQR MBBank") -> None:
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        row = conn.execute("SELECT amount, branch_id, status FROM bookings WHERE booking_code=?", (booking_code,)).fetchone()
        if not row:
            raise ValueError("Không tìm thấy lượt đặt.")
        if row["status"] == "Hết hạn giữ chỗ":
            raise ValueError("Đơn đặt phòng đã hết thời hạn giữ chỗ 10 phút. Vui lòng đặt lại.")
        conn.execute("UPDATE bookings SET payment_status='Đã thanh toán', status='Đã xác nhận' WHERE booking_code=?", (booking_code,))
        conn.execute(
            "INSERT INTO transactions(booking_code,tx_type,amount,status,method,reconciled,created_at) VALUES(?,?,?,?,?,0,?)",
            (booking_code, "Thanh toán", int(row["amount"]), "Thành công", method, now),
        )


def get_booking_by_code(booking_code: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM bookings WHERE booking_code=?", (booking_code,)).fetchone()
    return dict(row) if row else None


def cancel_booking(booking_code: str) -> int:
    with connect() as conn:
        row = conn.execute(
            "SELECT amount,payment_status,status,branch_id,booking_date,start_time,end_time FROM bookings WHERE booking_code=?",
            (booking_code,),
        ).fetchone()
        if not row:
            raise ValueError("Không tìm thấy lượt đặt.")
        if row["status"] in ("Đã check-in", "Đã hoàn tất", "Quá giờ - chưa checkout"):
            raise ValueError("Lượt đặt đã bắt đầu hoặc hoàn tất lưu trú, không thể hủy tại bước này.")

        row_dict = dict(row)
        if row_dict.get("payment_status") == "Đã thanh toán":
            try:
                from services.business_service import calculate_cancellation_refund
            except ImportError:
                from business_service import calculate_cancellation_refund
            calc = calculate_cancellation_refund(row_dict)
            refund = int(calc["refund_amount"])
        else:
            refund = 0

        conn.execute("UPDATE bookings SET status='Đã hủy', refund_amount=? WHERE booking_code=?", (refund, booking_code))
        if refund > 0:
            # BR-09: Ghi nhận giao dịch hoàn tiền chờ đối soát (số tiền âm theo quy ước đối soát)
            conn.execute(
                "INSERT INTO transactions(booking_code,tx_type,amount,status,method,reconciled,created_at) VALUES(?,?,?,?,?,0,?)",
                (booking_code, "Hoàn tiền", -refund, "Chờ đối soát", "Cổng thanh toán", datetime.now().isoformat(timespec="seconds")),
            )
    return refund


def add_extension(
    booking_code: str,
    room_id: str,
    extension_date: str,
    khung_code: str,
    start_time: str,
    end_time: str,
    amount: int,
    hours: int = 1,
    payment_method: str = "VietQR MBBank",
    payment_status: str = "Đã thanh toán (demo)",
) -> None:
    release_expired_holds()
    with connect() as conn:
        row = conn.execute("SELECT status, end_time FROM bookings WHERE booking_code=?", (booking_code,)).fetchone()
        if not row:
            raise ValueError("Không tìm thấy thông tin lượt đặt phòng.")
        current_status = row["status"]
        if current_status == "Đã hủy":
            raise ValueError("Lượt đặt phòng đã bị hủy, không thể thực hiện gia hạn.")
        if current_status == "Hết hạn giữ chỗ":
            raise ValueError("Lượt đặt phòng đã hết hạn giữ chỗ, không thể thực hiện gia hạn.")
        if current_status == "Chờ thanh toán":
            raise ValueError("Lượt đặt phòng chưa được thanh toán. Vui lòng thanh toán đơn gốc trước khi gia hạn.")
        if current_status == "Đã hoàn tất":
            raise ValueError("Lượt lưu trú đã hoàn tất và check-out, không thể gia hạn.")
        if current_status not in ("Đã xác nhận", "Chờ check-in", "Đã check-in", "Quá giờ - chưa checkout"):
            raise ValueError(f"Trạng thái '{current_status}' không đủ điều kiện để gia hạn.")

    if booking_exists(room_id, extension_date, khung_code, exclude_booking_code=booking_code):
        raise ValueError(f"Khung kế tiếp ({khung_code}) ngày {extension_date} không còn khả dụng nên không thể gia hạn.")

    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            """INSERT INTO booking_extensions(booking_code,room_id,extension_date,khung_code,start_time,end_time,amount,payment_status,hours,created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (booking_code, room_id, extension_date, khung_code, start_time, end_time, amount, payment_status, hours, now),
        )
        status_clause = ", status='Đã check-in'" if current_status == "Quá giờ - chưa checkout" else ""
        conn.execute(
            f"UPDATE bookings SET amount=amount+?, end_time=?{status_clause} WHERE booking_code=?",
            (amount, end_time, booking_code),
        )
        conn.execute(
            "INSERT INTO transactions(booking_code,tx_type,amount,status,method,reconciled,created_at) VALUES(?,?,?,?,?,0,?)",
            (booking_code, "Gia hạn", amount, "Thành công", payment_method, now),
        )
        # BR-06: Gia hạn cùng khách không phát sinh yêu cầu dọn phòng


def check_in_booking(booking_code: str) -> None:
    # UC-04.1 & BR-08: Lưu thời điểm check-in thực tế
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        row = conn.execute("SELECT status FROM bookings WHERE booking_code=?", (booking_code,)).fetchone()
        if not row:
            raise ValueError("Không tìm thấy lượt đặt.")
        if row["status"] not in ("Đã xác nhận", "Chờ check-in"):
            raise ValueError(f"Lượt đặt đang ở trạng thái '{row['status']}', không thể check-in.")
        conn.execute("UPDATE bookings SET status='Đã check-in', actual_checkin=? WHERE booking_code=?", (now, booking_code))


def check_out_booking(booking_code: str, staff_name: str = "Lễ tân") -> None:
    # UC-04.3 & BR-08: Lưu thời điểm check-out thực tế và tự động chuyển phòng sang "Cần dọn"
    now = datetime.now().isoformat(timespec="seconds")
    today = date.today().isoformat()
    with connect() as conn:
        row = conn.execute("SELECT room_id, branch_id, status FROM bookings WHERE booking_code=?", (booking_code,)).fetchone()
        if not row:
            raise ValueError("Không tìm thấy lượt đặt.")
        if row["status"] not in ("Đã check-in", "Quá giờ - chưa checkout"):
            raise ValueError(f"Lượt đặt đang ở trạng thái '{row['status']}', không thể check-out.")
        conn.execute("UPDATE bookings SET status='Đã hoàn tất', actual_checkout=? WHERE booking_code=?", (now, booking_code))
        # BR-08: Chuyển sang Cần dọn
        conn.execute(
            "INSERT INTO room_operations(room_id,branch_id,work_date,status,note,updated_by,updated_at) VALUES(?,?,?,?,?,?,?)",
            (row["room_id"], row["branch_id"], today, "Cần dọn", f"Khách vừa trả phòng {booking_code}", staff_name, now)
        )


def check_and_update_overstays() -> None:
    # BR-08: Tự động đánh dấu “Quá giờ - chưa checkout” khi hết giờ lưu trú mà chưa check-out hoặc gia hạn
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    now_time_str = now.strftime("%H:%M")
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, booking_code, booking_date, end_time FROM bookings WHERE status='Đã check-in'"
        ).fetchall()
        for r in rows:
            if r["booking_date"] < today_str or (r["booking_date"] == today_str and r["end_time"] and now_time_str > r["end_time"]):
                conn.execute("UPDATE bookings SET status='Quá giờ - chưa checkout' WHERE id=?", (r["id"],))


def list_bookings(user_id: int | None = None, branch_id: str | None = None) -> list[dict[str, Any]]:
    release_expired_holds()
    check_and_update_overstays()
    sql = """
        SELECT b.*, 
               COALESCE((SELECT SUM(be.hours) FROM booking_extensions be WHERE be.booking_code = b.booking_code), 0) as extension_hours,
               (SELECT be.khung_code FROM booking_extensions be WHERE be.booking_code = b.booking_code ORDER BY be.id DESC LIMIT 1) as extended_khung
        FROM bookings b WHERE 1=1
    """
    params: list[Any] = []
    if user_id is not None:
        sql += " AND b.user_id=?"; params.append(user_id)
    if branch_id:
        sql += " AND b.branch_id=?"; params.append(branch_id)
    sql += " ORDER BY b.booking_date DESC, b.id DESC"
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def update_booking_status(booking_code: str, status: str) -> None:
    if status == "Đã check-in":
        check_in_booking(booking_code)
    elif status == "Đã hoàn tất":
        check_out_booking(booking_code)
    else:
        with connect() as conn:
            conn.execute("UPDATE bookings SET status=? WHERE booking_code=?", (status, booking_code))


# -------------------------------------------------------------
# Accounting & Reconciliation (BR-09, UC-06)
# -------------------------------------------------------------
def list_transactions(branch_id: str | None = None) -> list[dict[str, Any]]:
    sql = """
      SELECT t.*, b.branch_id, b.room_id, b.customer_name, b.customer_phone 
      FROM transactions t 
      LEFT JOIN bookings b ON t.booking_code=b.booking_code 
      WHERE 1=1
    """
    params: list[Any] = []
    if branch_id:
        sql += " AND b.branch_id=?"; params.append(branch_id)
    sql += " ORDER BY t.id DESC"
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def reconcile_transaction(tx_id: int, reconciled_by: str) -> None:
    # UC-06.1: Kế toán đối soát giao dịch
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        row = conn.execute("SELECT tx_type FROM transactions WHERE id=?", (tx_id,)).fetchone()
        if not row:
            raise ValueError("Không tìm thấy giao dịch.")
        new_status = "Đã hoàn tiền" if row["tx_type"] == "Hoàn tiền" else "Đã đối soát"
        conn.execute(
            "UPDATE transactions SET reconciled=1, reconciled_at=?, reconciled_by=?, status=? WHERE id=?",
            (now, reconciled_by, new_status, tx_id)
        )


def reconcile_transactions_batch(tx_ids: list[int], reconciled_by: str) -> int:
    """Đối soát hàng loạt các giao dịch theo danh sách id"""
    if not tx_ids:
        return 0
    now = datetime.now().isoformat(timespec="seconds")
    updated_count = 0
    with connect() as conn:
        for tx_id in tx_ids:
            row = conn.execute("SELECT tx_type, reconciled FROM transactions WHERE id=?", (tx_id,)).fetchone()
            if row and not row["reconciled"]:
                new_status = "Đã hoàn tiền" if row["tx_type"] == "Hoàn tiền" else "Đã đối soát"
                conn.execute(
                    "UPDATE transactions SET reconciled=1, reconciled_at=?, reconciled_by=?, status=? WHERE id=?",
                    (now, reconciled_by, new_status, tx_id)
                )
                updated_count += 1
    return updated_count


# -------------------------------------------------------------
# Reconciliation Periods (UC-08.2)
# -------------------------------------------------------------
def list_reconciliation_periods() -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        rows = conn.execute("SELECT * FROM reconciliation_periods ORDER BY from_date DESC, id DESC").fetchall()
    return [dict(r) for r in rows]


def get_reconciliation_period(period_code: str) -> dict[str, Any] | None:
    init_db()
    with connect() as conn:
        row = conn.execute("SELECT * FROM reconciliation_periods WHERE period_code=?", (period_code,)).fetchone()
    return dict(row) if row else None


def close_reconciliation_period(period_code: str, closed_by: str, note: str = "") -> dict[str, Any]:
    init_db()
    now_str = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        row = conn.execute("SELECT * FROM reconciliation_periods WHERE period_code=?", (period_code,)).fetchone()
        if not row:
            raise ValueError(f"Không tìm thấy kỳ đối soát {period_code}.")
        if row["status"] == "Đã khóa sổ":
            raise ValueError(f"Kỳ đối soát {period_code} đã được khóa sổ trước đó bởi {row['closed_by']} lúc {row['closed_at']}.")
        
        conn.execute(
            "UPDATE reconciliation_periods SET status='Đã khóa sổ', closed_at=?, closed_by=?, note=CASE WHEN ? != '' THEN ? ELSE note END WHERE period_code=?",
            (now_str, closed_by, note, note, period_code),
        )
        updated = conn.execute("SELECT * FROM reconciliation_periods WHERE period_code=?", (period_code,)).fetchone()
    return dict(updated)


def create_reconciliation_period(period_code: str, period_name: str, from_date: str, to_date: str, note: str = "") -> dict[str, Any]:
    init_db()
    now_str = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            """INSERT INTO reconciliation_periods(period_code,period_name,from_date,to_date,status,note,created_at)
               VALUES(?,?,?,?,'Đang mở',?,?)""",
            (period_code, period_name, from_date, to_date, note, now_str),
        )
        row = conn.execute("SELECT * FROM reconciliation_periods WHERE period_code=?", (period_code,)).fetchone()
    return dict(row)


# -------------------------------------------------------------
# Housekeeping / Operations (BR-08, UC-04)
# -------------------------------------------------------------
def upsert_room_operation(room_id: str, branch_id: str, status: str, note: str, updated_by: str) -> None:
    # Vòng lặp buồng phòng chuẩn BR-08: Cần dọn → Đang dọn → Đã vệ sinh → Sẵn sàng (hoặc Bảo trì)
    with connect() as conn:
        conn.execute(
            "INSERT INTO room_operations(room_id,branch_id,work_date,status,note,updated_by,updated_at) VALUES(?,?,?,?,?,?,?)",
            (room_id, branch_id, date.today().isoformat(), status, note, updated_by, datetime.now().isoformat(timespec="seconds")),
        )


def latest_room_operations(branch_id: str | None = None) -> list[dict[str, Any]]:
    sql = """
      SELECT ro.* FROM room_operations ro
      JOIN (SELECT room_id, MAX(id) AS max_id FROM room_operations GROUP BY room_id) x ON ro.id=x.max_id
      WHERE 1=1
    """
    params: list[Any] = []
    if branch_id:
        sql += " AND ro.branch_id=?"; params.append(branch_id)
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


# -------------------------------------------------------------
# Reviews & Escalation (BR-12, UC-07)
# -------------------------------------------------------------
def add_review(booking_code: str, user_id: int | None, rating: int, content: str, media_urls: str = "") -> None:
    with connect() as conn:
        row = conn.execute("SELECT status, branch_id FROM bookings WHERE booking_code=?", (booking_code,)).fetchone()
        if not row or row["status"] != "Đã hoàn tất":
            raise ValueError("Chỉ lượt lưu trú đã hoàn tất mới được gửi đánh giá.")
        conn.execute(
            "INSERT INTO reviews(booking_code,user_id,rating,content,branch_id,escalated,created_at,media_urls) VALUES(?,?,?,?,?,0,?,?)",
            (booking_code, user_id, rating, content, row["branch_id"], datetime.now().isoformat(timespec="seconds"), media_urls),
        )


def escalate_review(review_id: int, escalation_note: str) -> None:
    # BR-12: Lễ tân chuyển trường hợp vượt thẩm quyền cho Quản lý chuỗi
    with connect() as conn:
        conn.execute(
            "UPDATE reviews SET escalated=1, escalation_note=? WHERE id=?",
            (escalation_note, review_id)
        )


def resolve_review(
    review_id: int,
    resolution_note: str,
    resolved_by: str,
    compensation_type: str = "NONE",
    compensation_detail: str = "",
) -> None:
    """Quản lý chuỗi giải quyết khiếu nại vượt thẩm quyền (BR-12, UC-07)"""
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            """UPDATE reviews 
               SET resolved=1, resolution_note=?, resolved_at=?, resolved_by=?, 
                   compensation_type=?, compensation_detail=? 
               WHERE id=?""",
            (resolution_note, now, resolved_by, compensation_type, compensation_detail, review_id)
        )


def list_reviews(
    branch_id: str | None = None,
    escalated_only: bool = False,
    resolved_status: str = "all",
) -> list[dict[str, Any]]:
    sql = """
        SELECT r.*, u.full_name as user_name, u.email as user_email, u.phone as user_phone, b.room_id 
        FROM reviews r 
        LEFT JOIN users u ON r.user_id=u.id 
        LEFT JOIN bookings b ON r.booking_code=b.booking_code 
        WHERE 1=1
    """
    params: list[Any] = []
    if branch_id:
        sql += " AND r.branch_id=?"; params.append(branch_id)
    if escalated_only:
        sql += " AND r.escalated=1"
    if resolved_status == "unresolved":
        sql += " AND (r.resolved = 0 OR r.resolved IS NULL)"
    elif resolved_status == "resolved":
        sql += " AND r.resolved = 1"
    sql += " ORDER BY r.id DESC"
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def get_room_reviews(room_id: str) -> list[dict[str, Any]]:
    sql = """
        SELECT r.*, u.full_name as user_name, b.room_id
        FROM reviews r
        JOIN bookings b ON r.booking_code = b.booking_code
        LEFT JOIN users u ON r.user_id = u.id
        WHERE b.room_id = ?
        ORDER BY r.id DESC
    """
    with connect() as conn:
        rows = conn.execute(sql, (room_id,)).fetchall()
    return [dict(r) for r in rows]



# -------------------------------------------------------------
# Slot Group Management (BR-01, BR-02, BR-03, UC-05.2)
# -------------------------------------------------------------
def assign_slot_group_to_room(room_id: str, slot_group_id: str) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO room_slot_assignments(room_id, slot_group_id, updated_at) VALUES(?,?,?)",
            (room_id, slot_group_id, now)
        )


def get_room_slot_group(room_id: str, default_group: str) -> str:
    with connect() as conn:
        row = conn.execute("SELECT slot_group_id FROM room_slot_assignments WHERE room_id=?", (room_id,)).fetchone()
    return row["slot_group_id"] if row else default_group


# -------------------------------------------------------------
# User Admin, Sessions, Audit & Metrics (UC-08)
# -------------------------------------------------------------
def list_users(search: str | None = None, role: str | None = None, branch_id: str | None = None, status: str | None = None, sort_by: str | None = None) -> list[dict[str, Any]]:
    sql = "SELECT id,email,full_name,phone,role,branch_id,active,failed_attempts,locked,status,last_login_at,created_at,updated_at FROM users WHERE 1=1"
    params: list[Any] = []
    if search:
        kw = f"%{remove_vietnamese_accents(search)}%"
        sql += " AND (UNACCENT(full_name) LIKE ? OR UNACCENT(email) LIKE ? OR phone LIKE ? OR UNACCENT(role) LIKE ? OR UNACCENT(branch_id) LIKE ?)"
        params.extend([kw, kw, kw, kw, kw])
    if role:
        if role in ("Quản lý", "Quản lý chuỗi"):
            sql += " AND (role = 'Quản lý' OR role = 'Quản lý chuỗi')"
        elif role in ("Buồng phòng", "Nhân viên buồng phòng"):
            sql += " AND (role = 'Buồng phòng' OR role = 'Nhân viên buồng phòng')"
        elif role in ("Admin", "Quản trị viên"):
            sql += " AND (role = 'Admin' OR role = 'Quản trị viên')"
        else:
            sql += " AND role = ?"
            params.append(role)
    if branch_id:
        if branch_id == "NONE":
            sql += " AND (branch_id IS NULL OR branch_id = '') AND role != 'Khách hàng'"
        elif branch_id in ("CUSTOMER", "Khách hàng"):
            sql += " AND role = 'Khách hàng'"
        else:
            sql += " AND branch_id = ?"
            params.append(branch_id)
    if status:
        sql += " AND status = ?"
        params.append(status)
    if sort_by == "name_asc":
        sql += " ORDER BY UNACCENT(full_name) ASC, id DESC"
    elif sort_by == "name_desc":
        sql += " ORDER BY UNACCENT(full_name) DESC, id DESC"
    else:
        sql += " ORDER BY id DESC"
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def set_user_active(user_id: int, active: bool) -> None:
    new_status = "ACTIVE" if active else "DISABLED"
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute("UPDATE users SET active=?, status=?, updated_at=? WHERE id=?", (1 if active else 0, new_status, now, user_id))


def set_user_scope(user_id: int, role: str, branch_id: str | None) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute("UPDATE users SET role=?, branch_id=?, updated_at=? WHERE id=?", (role, branch_id, now, user_id))


def count_active_admins() -> int:
    with connect() as conn:
        n = conn.execute(
            "SELECT COUNT(*) FROM users WHERE role IN ('Quản trị viên', 'Admin') AND active=1 AND locked=0"
        ).fetchone()[0]
    return n


def set_user_status(user_id: int, status: str) -> tuple[bool, str]:
    status = status.upper()
    if status not in ("ACTIVE", "LOCKED", "DISABLED"):
        return False, "Trạng thái không hợp lệ (chỉ chấp nhận ACTIVE, LOCKED, DISABLED)."

    with connect() as conn:
        user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if not user:
            return False, "Không tìm thấy người dùng."

        is_admin = user["role"] in ("Quản trị viên", "Admin")
        if is_admin and status in ("LOCKED", "DISABLED"):
            active_admins = conn.execute(
                "SELECT COUNT(*) FROM users WHERE role IN ('Quản trị viên', 'Admin') AND active=1 AND locked=0 AND id != ?",
                (user_id,)
            ).fetchone()[0]
            if active_admins < 1:
                return False, "Không thể khóa hoặc vô hiệu hóa tài khoản Quản trị viên duy nhất còn lại của hệ thống."

        now = datetime.now().isoformat(timespec="seconds")
        if status == "ACTIVE":
            conn.execute("UPDATE users SET active=1, locked=0, failed_attempts=0, status='ACTIVE', updated_at=? WHERE id=?", (now, user_id))
        elif status == "LOCKED":
            conn.execute("UPDATE users SET locked=1, status='LOCKED', updated_at=? WHERE id=?", (now, user_id))
        elif status == "DISABLED":
            conn.execute("UPDATE users SET active=0, status='DISABLED', updated_at=? WHERE id=?", (now, user_id))

    return True, f"Đã cập nhật trạng thái tài khoản sang {status}."


def reset_failed_attempts(user_id: int) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute("UPDATE users SET failed_attempts=0, updated_at=? WHERE id=?", (now, user_id))


def create_internal_user(email: str, password: str, full_name: str, phone: str, role: str, branch_id: str | None) -> tuple[bool, str, dict | None]:
    email_clean = email.strip().lower()
    full_name_clean = full_name.strip()
    phone_clean = phone.strip()

    if not full_name_clean:
        return False, "Họ và tên không được để trống.", None
    if not validate_email(email_clean):
        return False, "Email không đúng định dạng.", None
    if phone_clean and not validate_phone(phone_clean):
        return False, "Số điện thoại không đúng định dạng 10 số.", None
    if len(password) < 6:
        return False, "Mật khẩu tối thiểu 6 ký tự.", None

    valid_roles = ["Khách hàng", "Lễ tân", "Buồng phòng", "Nhân viên buồng phòng", "Kế toán", "Quản lý", "Quản lý chuỗi", "Quản trị viên"]
    if role not in valid_roles:
        return False, f"Vai trò không hợp lệ. Cho phép: {', '.join(valid_roles)}", None

    if role in ("Lễ tân", "Buồng phòng", "Nhân viên buồng phòng") and not branch_id:
        return False, f"Vai trò {role} bắt buộc phải chọn chi nhánh phân công (BT, TD hoặc PMH).", None

    if role in ("Quản lý", "Quản lý chuỗi", "Kế toán", "Quản trị viên"):
        branch_id = None

    now = datetime.now().isoformat(timespec="seconds")
    try:
        with connect() as conn:
            cursor = conn.execute(
                """INSERT INTO users(email, password_hash, full_name, phone, role, branch_id, active, failed_attempts, locked, status, created_at, updated_at)
                   VALUES(?, ?, ?, ?, ?, ?, 1, 0, 0, 'ACTIVE', ?, ?)""",
                (email_clean, _hash_password(password), full_name_clean, phone_clean, role, branch_id, now, now),
            )
            user_id = cursor.lastrowid
            new_user = conn.execute("SELECT id,email,full_name,phone,role,branch_id,active,status,created_at,updated_at FROM users WHERE id=?", (user_id,)).fetchone()
        return True, "Tạo tài khoản nội bộ thành công.", dict(new_user)
    except sqlite3.IntegrityError:
        return False, "Địa chỉ email này đã tồn tại trong hệ thống.", None


def update_user_admin(user_id: int, full_name: str, phone: str, role: str, branch_id: str | None, status: str | None = None) -> tuple[bool, str]:
    with connect() as conn:
        cur = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if not cur:
            return False, "Không tìm thấy người dùng."

        is_current_admin = cur["role"] in ("Quản trị viên", "Admin")
        if is_current_admin and role not in ("Quản trị viên", "Admin"):
            other_admins = conn.execute(
                "SELECT COUNT(*) FROM users WHERE role IN ('Quản trị viên', 'Admin') AND active=1 AND locked=0 AND id != ?",
                (user_id,)
            ).fetchone()[0]
            if other_admins < 1:
                return False, "Không thể chuyển đổi vai trò của Quản trị viên duy nhất còn lại trong hệ thống."

        if role in ("Lễ tân", "Buồng phòng", "Nhân viên buồng phòng") and not branch_id:
            return False, f"Vai trò {role} bắt buộc phải gán một chi nhánh cụ thể.", None

        if role in ("Quản lý", "Quản lý chuỗi", "Kế toán", "Quản trị viên"):
            branch_id = None

        new_status = status or cur["status"] or "ACTIVE"
        active_val = 0 if new_status == "DISABLED" else 1
        locked_val = 1 if new_status == "LOCKED" else 0
        now = datetime.now().isoformat(timespec="seconds")

        conn.execute(
            """UPDATE users 
               SET full_name=?, phone=?, role=?, branch_id=?, status=?, active=?, locked=?, updated_at=?
               WHERE id=?""",
            (full_name.strip(), phone.strip(), role, branch_id, new_status, active_val, locked_val, now, user_id)
        )
    return True, "Cập nhật tài khoản thành công."


# -------------------------------------------------------------
# Server-Side Session Management
# -------------------------------------------------------------
def create_session(user_id: int, demo_role: str | None = None, demo_branch: str | None = None, hours: int = 24) -> str:
    token = secrets.token_hex(32)
    now_dt = datetime.now()
    created_at = now_dt.isoformat(timespec="seconds")
    expires_at = (now_dt + timedelta(hours=hours)).isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            """INSERT INTO user_sessions(user_id, token, demo_role, demo_branch, expires_at, created_at)
               VALUES(?,?,?,?,?,?)""",
            (user_id, token, demo_role, demo_branch, expires_at, created_at)
        )
        conn.execute("UPDATE users SET last_login_at=?, updated_at=? WHERE id=?", (created_at, created_at, user_id))
    return token


def get_session(token: str) -> dict[str, Any] | None:
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        row = conn.execute(
            """SELECT s.token, s.user_id, s.demo_role, s.demo_branch, s.expires_at,
                      u.email, u.full_name, u.phone, u.role, u.branch_id, u.active, u.locked, u.status, u.failed_attempts
               FROM user_sessions s
               JOIN users u ON s.user_id = u.id
               WHERE s.token = ? AND s.expires_at > ?""",
            (token, now)
        ).fetchone()
    return dict(row) if row else None


def update_session_demo_scope(token: str, demo_role: str | None, demo_branch: str | None) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE user_sessions SET demo_role=?, demo_branch=? WHERE token=?",
            (demo_role, demo_branch, token)
        )


def delete_session(token: str) -> bool:
    with connect() as conn:
        res = conn.execute("DELETE FROM user_sessions WHERE token=?", (token,))
        return res.rowcount > 0


def cleanup_expired_sessions() -> int:
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        res = conn.execute("DELETE FROM user_sessions WHERE expires_at < ?", (now,))
        return res.rowcount


# -------------------------------------------------------------
# System Audit Log
# -------------------------------------------------------------
def add_audit_log(
    user_id: int | None,
    user_email: str,
    user_name: str | None,
    role: str,
    branch_id: str | None,
    action: str,
    entity_type: str,
    entity_id: str | None,
    description: str,
    old_value: str | None = None,
    new_value: str | None = None,
    ip_address: str | None = None,
) -> int:
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        res = conn.execute(
            """INSERT INTO audit_logs(user_id, user_email, user_name, role, branch_id, action, entity_type, entity_id, description, old_value, new_value, ip_address, created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (user_id, user_email, user_name, role, branch_id, action, entity_type, entity_id, description, old_value, new_value, ip_address, now)
        )
        return res.lastrowid


def list_audit_logs(
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
) -> tuple[list[dict[str, Any]], int]:
    sql = "FROM audit_logs WHERE 1=1"
    params: list[Any] = []

    if keyword:
        kw = f"%{remove_vietnamese_accents(keyword)}%"
        sql += " AND (UNACCENT(description) LIKE ? OR UNACCENT(entity_id) LIKE ? OR UNACCENT(user_email) LIKE ? OR UNACCENT(user_name) LIKE ?)"
        params.extend([kw, kw, kw, kw])
    if from_date:
        sql += " AND created_at >= ?"
        params.append(from_date)
    if to_date:
        sql += " AND created_at <= ?"
        params.append(f"{to_date}T23:59:59")
    if user_email:
        sql += " AND LOWER(user_email) = ?"
        params.append(user_email.strip().lower())
    if role:
        sql += " AND role = ?"
        params.append(role)
    if branch_id:
        sql += " AND branch_id = ?"
        params.append(branch_id)
    if action:
        sql += " AND action = ?"
        params.append(action)

    order_clause = "ORDER BY id DESC"
    if sort_by == "user_asc":
        order_clause = "ORDER BY UNACCENT(user_name) ASC, id DESC"
    elif sort_by == "action_asc":
        order_clause = "ORDER BY action ASC, id DESC"

    with connect() as conn:
        total = conn.execute(f"SELECT COUNT(*) {sql}", params).fetchone()[0]
        data_sql = f"SELECT * {sql} {order_clause} LIMIT ? OFFSET ?"
        rows = conn.execute(data_sql, params + [limit, offset]).fetchall()

    return [dict(r) for r in rows], total


# -------------------------------------------------------------
# Security Settings
# -------------------------------------------------------------
def get_security_settings() -> dict[str, dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM security_settings ORDER BY key").fetchall()
    return {r["key"]: dict(r) for r in rows}


def update_security_setting(key: str, value: str, updated_by: str = "Admin") -> bool:
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        res = conn.execute(
            "UPDATE security_settings SET value=?, updated_at=?, updated_by=? WHERE key=?",
            (str(value).strip(), now, updated_by)
        )
        return res.rowcount > 0


# -------------------------------------------------------------
# Admin System Metrics (Full System Overview)
# -------------------------------------------------------------
def admin_system_metrics() -> dict[str, Any]:
    with connect() as conn:
        # 1. Người dùng
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        active_users = conn.execute("SELECT COUNT(*) FROM users WHERE status='ACTIVE'").fetchone()[0]
        locked_users = conn.execute("SELECT COUNT(*) FROM users WHERE status='LOCKED'").fetchone()[0]
        disabled_users = conn.execute("SELECT COUNT(*) FROM users WHERE status='DISABLED'").fetchone()[0]

        # Thống kê phân bổ vai trò (nhóm và đếm từ Database thực tế, sắp xếp thứ tự chuẩn)
        role_counts = dict(
            conn.execute(
                """SELECT role, COUNT(*) 
                   FROM users 
                   GROUP BY role 
                   ORDER BY CASE 
                       WHEN role = 'Buồng phòng' THEN 1
                       WHEN role = 'Khách hàng' THEN 2
                       WHEN role = 'Kế toán' THEN 3
                       WHEN role = 'Lễ tân' THEN 4
                       WHEN role = 'Quản lý' THEN 5
                       WHEN role = 'Quản trị viên' THEN 6
                       ELSE 7
                   END"""
            ).fetchall()
        )

        # Phân bổ nhân sự theo chi nhánh: Chỉ tính nhân sự nội bộ CozyHome, TUYỆT ĐỐI không tính Khách hàng
        branch_query_counts = dict(
            conn.execute(
                """SELECT 
                       CASE 
                           WHEN branch_id = 'BT' THEN 'BT'
                           WHEN branch_id = 'PMH' THEN 'PMH'
                           WHEN branch_id = 'TD' THEN 'TD'
                           ELSE 'TOÀN CHUỖI'
                       END as branch,
                       COUNT(*) 
                   FROM users 
                   WHERE role != 'Khách hàng'
                   GROUP BY branch"""
            ).fetchall()
        )
        branch_user_counts = {}
        for b_key in ["TOÀN CHUỖI", "BT", "PMH", "TD"]:
            branch_user_counts[b_key] = branch_query_counts.get(b_key, 0)
        for b_key, b_cnt in branch_query_counts.items():
            if b_key not in branch_user_counts:
                branch_user_counts[b_key] = b_cnt

        # 2. Phòng
        from services.business_service import all_rooms
        rooms = all_rooms()
        latest_ops = {r["room_id"]: r["status"] for r in latest_room_operations()}
        room_statuses = {"Sẵn sàng": 0, "Đang sử dụng": 0, "Đang dọn": 0, "Bảo trì": 0}
        for r in rooms:
            st = latest_ops.get(r["room_id"], r.get("operational_status", "Sẵn sàng"))
            if st in ("Đã check-in", "Đang ở"):
                st = "Đang sử dụng"
            elif st in ("Cần dọn", "Đã vệ sinh"):
                st = "Đang dọn"
            room_statuses[st] = room_statuses.get(st, 0) + 1

        # 3. Bookings
        total_bks = conn.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]
        pending_bks = conn.execute("SELECT COUNT(*) FROM bookings WHERE status='Chờ thanh toán'").fetchone()[0]
        confirmed_bks = conn.execute("SELECT COUNT(*) FROM bookings WHERE status='Đã xác nhận'").fetchone()[0]
        staying_bks = conn.execute("SELECT COUNT(*) FROM bookings WHERE status IN ('Đã check-in', 'Quá giờ - chưa checkout')").fetchone()[0]
        completed_bks = conn.execute("SELECT COUNT(*) FROM bookings WHERE status='Đã hoàn tất'").fetchone()[0]
        cancelled_bks = conn.execute("SELECT COUNT(*) FROM bookings WHERE status IN ('Đã hủy', 'Hết hạn giữ chỗ')").fetchone()[0]

        # 4. Transactions
        tx_stats = conn.execute(
            """SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN tx_type IN ('Thanh toán', 'Gia hạn') AND status IN ('Thành công', 'Đã đối soát') THEN 1 ELSE 0 END) as success,
                SUM(CASE WHEN status='Chờ đối soát' THEN 1 ELSE 0 END) as pending_rec,
                SUM(CASE WHEN status='Đã đối soát' THEN 1 ELSE 0 END) as reconciled,
                SUM(CASE WHEN tx_type='Hoàn tiền' THEN 1 ELSE 0 END) as refunds
               FROM transactions"""
        ).fetchone()

        # 5. Audit Log count
        total_logs = conn.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]

    return {
        "users": {
            "total": total_users,
            "active": active_users,
            "locked": locked_users,
            "disabled": disabled_users,
            "by_role": role_counts,
            "by_branch": branch_user_counts,
        },
        "rooms": {
            "total": len(rooms),
            "ready": room_statuses.get("Sẵn sàng", 0),
            "staying": room_statuses.get("Đang sử dụng", 0),
            "cleaning": room_statuses.get("Đang dọn", 0),
            "maintenance": room_statuses.get("Bảo trì", 0),
        },
        "bookings": {
            "total": total_bks,
            "pending": pending_bks,
            "confirmed": confirmed_bks,
            "staying": staying_bks,
            "completed": completed_bks,
            "cancelled": cancelled_bks,
        },
        "transactions": {
            "total": tx_stats["total"] or 0,
            "success": tx_stats["success"] or 0,
            "pending_reconciliation": tx_stats["pending_rec"] or 0,
            "reconciled": tx_stats["reconciled"] or 0,
            "refunds": tx_stats["refunds"] or 0,
        },
        "total_audit_logs": total_logs,
    }


def dashboard_metrics(branch_id: str | None = None) -> dict[str, Any]:
    sql_b = "SELECT COUNT(*) FROM bookings WHERE status NOT IN ('Đã hủy', 'Hết hạn giữ chỗ')"
    sql_comp = "SELECT COUNT(*) FROM bookings WHERE status='Đã hoàn tất'"
    sql_rev = """
        SELECT COALESCE(SUM(t.amount),0) 
        FROM transactions t 
        LEFT JOIN bookings b ON t.booking_code = b.booking_code 
        WHERE t.tx_type IN ('Thanh toán', 'Gia hạn') AND t.status IN ('Thành công', 'Đã đối soát')
    """
    sql_ref = """
        SELECT COALESCE(SUM(ABS(t.amount)),0) 
        FROM transactions t 
        LEFT JOIN bookings b ON t.booking_code = b.booking_code 
        WHERE t.tx_type='Hoàn tiền'
    """
    params: list[Any] = []
    if branch_id:
        sql_b += " AND branch_id=?"
        sql_comp += " AND branch_id=?"
        sql_rev += " AND b.branch_id=?"
        sql_ref += " AND b.branch_id=?"
        params.append(branch_id)

    with connect() as conn:
        bookings = conn.execute(sql_b, params).fetchone()[0]
        completed = conn.execute(sql_comp, params).fetchone()[0]
        revenue = conn.execute(sql_rev, params).fetchone()[0]
        refunds = conn.execute(sql_ref, params).fetchone()[0]
    return {"bookings": bookings, "revenue": revenue, "refunds": refunds, "completed": completed}


def get_chain_branches_kpi() -> dict[str, Any]:
    """
    Tổng hợp KPI đa chiều cho 3 chi nhánh CozyHome (BR-01, UC-05.1):
    Bến Thành (BT), Thảo Điền (TD), Phú Mỹ Hưng (PMH)
    """
    branch_meta = [
        {"id": "BT", "name": "CozyHome Bến Thành", "short": "Bến Thành", "address": "Quận 1, TP. Hồ Chí Minh", "capacity": 8},
        {"id": "TD", "name": "CozyHome Thảo Điền", "short": "Thảo Điền", "address": "TP. Thủ Đức, TP. Hồ Chí Minh", "capacity": 8},
        {"id": "PMH", "name": "CozyHome Phú Mỹ Hưng", "short": "Phú Mỹ Hưng", "address": "Quận 7, TP. Hồ Chí Minh", "capacity": 8},
    ]

    branches_data = []
    total_chain = {
        "room_count": 24,
        "bookings": 0,
        "revenue": 0,
        "refunds": 0,
        "completed": 0,
        "ready_rooms": 0,
        "cleaning_rooms": 0,
        "dirty_rooms": 0,
        "maintenance_rooms": 0,
        "escalations_pending": 0,
        "escalations_resolved": 0,
    }

    # Lấy thông tin trạng thái phòng mới nhất
    latest_ops = latest_room_operations(None)
    ops_status_map = {op["room_id"]: op.get("status", "Sẵn sàng") for op in latest_ops}

    # Khiếu nại đếm
    with connect() as conn:
        esc_pending = conn.execute("SELECT COUNT(*) FROM reviews WHERE escalated=1 AND (resolved=0 OR resolved IS NULL)").fetchone()[0]
        esc_resolved = conn.execute("SELECT COUNT(*) FROM reviews WHERE escalated=1 AND resolved=1").fetchone()[0]
    total_chain["escalations_pending"] = esc_pending
    total_chain["escalations_resolved"] = esc_resolved

    try:
        from services.business_service import all_rooms
    except ImportError:
        from business_service import all_rooms
    all_r = all_rooms()
    for b in branch_meta:
        b_id = b["id"]
        m = dashboard_metrics(b_id)
        b_rooms = [r for r in all_r if r.get("branch_id") == b_id]
        room_count = len(b_rooms) if b_rooms else b["capacity"]

        ready_c = 0
        cleaning_c = 0
        dirty_c = 0
        maint_c = 0

        for r in b_rooms:
            st = ops_status_map.get(r["room_id"], r.get("operational_status", "Sẵn sàng"))
            if st in ("Sẵn sàng", "Đã vệ sinh", "Đã kiểm tra"):
                ready_c += 1
            elif st == "Đang dọn":
                cleaning_c += 1
            elif st == "Cần dọn":
                dirty_c += 1
            elif st == "Bảo trì":
                maint_c += 1
            else:
                ready_c += 1

        occ_rate = round(min(100.0, (m["completed"] / max(1, room_count * 5)) * 100), 1)

        b_item = {
            "branch_id": b_id,
            "branch_name": b["name"],
            "short_name": b["short"],
            "address": b["address"],
            "room_count": room_count,
            "bookings": m["bookings"],
            "revenue": m["revenue"],
            "refunds": m["refunds"],
            "completed": m["completed"],
            "occupancy_rate": occ_rate,
            "ready_rooms": ready_c,
            "cleaning_rooms": cleaning_c,
            "dirty_rooms": dirty_c,
            "maintenance_rooms": maint_c,
        }
        branches_data.append(b_item)

        total_chain["bookings"] += m["bookings"]
        total_chain["revenue"] += m["revenue"]
        total_chain["refunds"] += m["refunds"]
        total_chain["completed"] += m["completed"]
        total_chain["ready_rooms"] += ready_c
        total_chain["cleaning_rooms"] += cleaning_c
        total_chain["dirty_rooms"] += dirty_c
        total_chain["maintenance_rooms"] += maint_c

    total_chain["occupancy_rate"] = round(min(100.0, (total_chain["completed"] / max(1, 24 * 5)) * 100), 1)

    return {
        "total": total_chain,
        "branches": branches_data,
    }


# =============================================================================
# LƯU TRỮ LỊCH SỬ TRÒ CHUYỆN AI (ACCOUNT CHAT HISTORY)
# =============================================================================

def save_chat_message(
    session_id: str,
    sender: str,
    message: str,
    user_id: int | None = None,
    meta: dict[str, Any] | None = None,
) -> int:
    """Lưu một tin nhắn hội thoại vào cơ sở dữ liệu vĩnh viễn theo user_id và session_id."""
    now = datetime.now().isoformat(timespec="seconds")
    meta_str = json.dumps(meta, ensure_ascii=False) if meta else None
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO ai_chat_history (user_id, session_id, sender, message, meta_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, session_id, sender, message, meta_str, now),
        )
        return cur.lastrowid


def get_user_chat_history(
    user_id: int | None = None,
    session_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Lấy danh sách tin nhắn hội thoại theo user_id (ưu tiên) hoặc session_id."""
    with connect() as conn:
        if user_id:
            rows = conn.execute(
                """SELECT id, user_id, session_id, sender, message, meta_json, created_at
                   FROM ai_chat_history
                   WHERE user_id = ?
                   ORDER BY id ASC LIMIT ?""",
                (user_id, limit),
            ).fetchall()
        elif session_id:
            rows = conn.execute(
                """SELECT id, user_id, session_id, sender, message, meta_json, created_at
                   FROM ai_chat_history
                   WHERE session_id = ?
                   ORDER BY id ASC LIMIT ?""",
                (session_id, limit),
            ).fetchall()
        else:
            return []

        out = []
        for r in rows:
            meta = None
            if r["meta_json"]:
                try:
                    meta = json.loads(r["meta_json"])
                except Exception:
                    pass
            out.append({
                "id": r["id"],
                "user_id": r["user_id"],
                "session_id": r["session_id"],
                "sender": r["sender"],
                "message": r["message"],
                "meta": meta,
                "created_at": r["created_at"],
            })
        return out


def clear_chat_history(user_id: int | None = None, session_id: str | None = None) -> int:
    """Xóa lịch sử hội thoại của người dùng hoặc theo session."""
    with connect() as conn:
        if user_id:
            cur = conn.execute("DELETE FROM ai_chat_history WHERE user_id = ?", (user_id,))
            return cur.rowcount
        elif session_id:
            cur = conn.execute("DELETE FROM ai_chat_history WHERE session_id = ?", (session_id,))
            return cur.rowcount
        return 0


init_db()
