from __future__ import annotations

import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from dotenv import load_dotenv

load_dotenv()


def _str_to_bool(val: str | None, default: bool = False) -> bool:
    if val is None:
        return default
    return val.strip().lower() in ("true", "1", "yes", "t", "y")


def get_smtp_config() -> dict[str, Any]:
    """Đọc và chuẩn hóa toàn bộ biến cấu hình SMTP từ môi trường."""
    user = os.getenv("SMTP_USER", "").strip()
    from_email = os.getenv("SMTP_FROM_EMAIL", "").strip() or user
    return {
        "host": os.getenv("SMTP_HOST", "smtp.gmail.com").strip(),
        "port": int(os.getenv("SMTP_PORT", "587")),
        "use_tls": _str_to_bool(os.getenv("SMTP_USE_TLS"), default=True),
        "user": user,
        "password": os.getenv("SMTP_PASSWORD", "").strip(),
        "from_name": os.getenv("SMTP_FROM_NAME", "CozyHome Homestay").strip(),
        "from_email": from_email,
        "dev_fallback": _str_to_bool(os.getenv("OTP_DEV_FALLBACK"), default=True),
        "app_env": os.getenv("APP_ENV", "development").strip().lower(),
    }


def is_smtp_configured() -> bool:
    """Kiểm tra hệ thống đã có đủ thông tin cấu hình SMTP hay chưa."""
    cfg = get_smtp_config()
    user = cfg["user"]
    password = cfg["password"]
    if not user or not password:
        return False
    # Kiểm tra tránh chuỗi giữ chỗ mẫu
    if "your_" in user or "your_16_char" in password or "your_email" in user:
        return False
    return True


def render_otp_email_plain(to_email: str, otp: str, purpose: str = "register", user_name: str | None = None) -> str:
    """Tạo nội dung text thuần cho email client không hỗ trợ HTML."""
    greeting = f"Xin chào {user_name.strip()}," if user_name and user_name.strip() else "Xin chào quý khách,"
    if purpose == "register":
        subject = "Mã xác thực đăng ký tài khoản CozyHome"
        body = (
            f"{subject}\n\n"
            f"{greeting}\n\n"
            "Cảm ơn bạn đã lựa chọn CozyHome Homestay.\n"
            f"Mã xác thực OTP kích hoạt tài khoản của bạn là: {otp}\n\n"
            "Mã có hiệu lực trong vòng 5 phút kể từ thời điểm phát hành.\n"
            "Vui lòng tuyệt đối không chia sẻ mã này cho bất kỳ ai, kể cả nhân viên CozyHome.\n\n"
            "Nếu bạn không yêu cầu đăng ký tài khoản, vui lòng bỏ qua email này.\n\n"
            "---\n"
            "Đội ngũ CozyHome Homestay\n"
            "Hotline hỗ trợ: 1900 6868 | contact@cozyhome.vn\n"
            "TP. Hồ Chí Minh (Bến Thành - Thảo Điền - Phú Mỹ Hưng)"
        )
    else:
        subject = "Mã xác thực khôi phục mật khẩu CozyHome"
        body = (
            f"{subject}\n\n"
            f"{greeting}\n\n"
            "Hệ thống CozyHome nhận được yêu cầu cấp lại mật khẩu cho tài khoản của bạn.\n"
            f"Mã xác thực OTP của bạn là: {otp}\n\n"
            "Mã có hiệu lực trong vòng 5 phút kể từ thời điểm phát hành.\n"
            "Vui lòng tuyệt đối không chia sẻ mã này cho bất kỳ ai.\n\n"
            "CẢNH BÁO BẢO MẬT: Nếu bạn KHÔNG thực hiện yêu cầu này, vui lòng đổi mật khẩu ngay hoặc liên hệ với chúng tôi để bảo vệ tài khoản.\n\n"
            "---\n"
            "Đội ngũ CozyHome Homestay\n"
            "Hotline hỗ trợ: 1900 6868 | contact@cozyhome.vn\n"
            "TP. Hồ Chí Minh (Bến Thành - Thảo Điền - Phú Mỹ Hưng)"
        )
    return body


def render_otp_email_html(to_email: str, otp: str, purpose: str = "register", user_name: str | None = None) -> str:
    """Tạo giao diện email HTML tối ưu tương thích mọi email client (Gmail, Outlook, Apple Mail).
    Tuân thủ bảng màu và phong cách nhận diện CozyHome (tone nâu cam trung tính, không gradient, không màu rực).
    """
    greeting = f"Xin chào <b>{user_name.strip()}</b>," if user_name and user_name.strip() else "Xin chào quý khách,"

    if purpose == "register":
        title = "Xác thực đăng ký tài khoản CozyHome"
        sub_desc = "Cảm ơn bạn đã lựa chọn trải nghiệm dịch vụ homestay đô thị tại CozyHome. Vui lòng sử dụng mã bên dưới để hoàn tất kích hoạt tài khoản của bạn:"
        warning_box = """
        <tr>
          <td style="padding:14px 18px;background-color:#fff8eb;border:1px solid #fed7aa;border-radius:8px;font-size:12.5px;color:#786457;line-height:1.5;">
            ⏰ <b>Lưu ý:</b> Mã xác thực có hiệu lực trong <b>5 phút</b>. Tuyệt đối không cung cấp mã OTP cho bất kỳ ai khác để đảm bảo an toàn tài khoản.
          </td>
        </tr>
        """
    else:
        title = "Khôi phục mật khẩu tài khoản CozyHome"
        sub_desc = "Chúng tôi vừa nhận được yêu cầu đặt lại mật khẩu cho tài khoản liên kết với địa chỉ email này. Vui lòng sử dụng mã xác thực dưới đây để hoàn tất:"
        warning_box = """
        <tr>
          <td style="padding:14px 18px;background-color:#fff8eb;border:1px solid #fed7aa;border-radius:8px;font-size:12.5px;color:#786457;line-height:1.5;">
            ⚠️ <b>Cảnh báo bảo mật:</b> Nếu bạn <b>không</b> gửi yêu cầu này, vui lòng bỏ qua email này hoặc liên hệ hotline để được hỗ trợ khóa tài khoản khẩn cấp.
          </td>
        </tr>
        """

    html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background-color:#fef8f2;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#2b1d16;">
  <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color:#fef8f2;padding:30px 10px;">
    <tr>
      <td align="center">
        <!-- Container chính 600px -->
        <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width:580px;background-color:#ffffff;border:1px solid #ebd8c8;border-radius:12px;overflow:hidden;box-shadow:0 4px 16px rgba(58,34,21,0.06);">
          
          <!-- Header thương hiệu -->
          <tr>
            <td style="background-color:#3a2215;padding:24px 30px;text-align:center;">
              <div style="font-size:26px;font-weight:800;color:#ffffff;letter-spacing:1px;margin:0;">
                🏠 Cozy<span style="color:#b96b35;">Home</span>
              </div>
              <div style="font-size:12px;color:#ebd8c8;margin-top:4px;letter-spacing:0.5px;">
                Chuỗi Homestay Đô Thị TP. Hồ Chí Minh
              </div>
            </td>
          </tr>

          <!-- Nội dung chính -->
          <tr>
            <td style="padding:32px 30px 24px 30px;">
              <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
                <tr>
                  <td style="font-size:18px;font-weight:700;color:#3a2215;padding-bottom:12px;">
                    {title}
                  </td>
                </tr>
                <tr>
                  <td style="font-size:14px;line-height:1.6;color:#2b1d16;padding-bottom:16px;">
                    {greeting}
                  </td>
                </tr>
                <tr>
                  <td style="font-size:14px;line-height:1.6;color:#786457;padding-bottom:24px;">
                    {sub_desc}
                  </td>
                </tr>

                <!-- Khối hiển thị mã OTP nổi bật -->
                <tr>
                  <td align="center" style="padding-bottom:24px;">
                    <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="background-color:#fef8f2;border:2px dashed #b96b35;border-radius:10px;margin:0 auto;width:100%;max-width:360px;">
                      <tr>
                        <td align="center" style="padding:16px 20px;">
                          <div style="font-size:12px;font-weight:700;color:#786457;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">
                            MÃ XÁC THỰC CỦA BẠN
                          </div>
                          <div style="font-size:34px;font-weight:800;letter-spacing:10px;color:#b96b35;font-family:Consolas,monaco,'Courier New',Courier,monospace;padding:6px 0;">
                            {otp}
                          </div>
                          <div style="font-size:12px;color:#a89487;margin-top:4px;">
                            Hiệu lực trong vòng 5 phút
                          </div>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>

                <!-- Cảnh báo an toàn -->
                {warning_box}

              </table>
            </td>
          </tr>

          <!-- Footer thông tin hỗ trợ -->
          <tr>
            <td style="background-color:#fef8f2;border-top:1px solid #ebd8c8;padding:20px 30px;font-size:12px;color:#786457;line-height:1.6;">
              <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
                <tr>
                  <td>
                    <b>CozyHome Homestay Hospitality</b><br>
                    📍 Chi nhánh Bến Thành: 123 Lê Thánh Tôn, Quận 1, TP.HCM<br>
                    📍 Chi nhánh Thảo Điền: 45 Xuân Thủy, TP. Thủ Đức, TP.HCM<br>
                    📍 Chi nhánh Phú Mỹ Hưng: 78 Nguyễn Đức Cảnh, Quận 7, TP.HCM<br>
                    ☎️ Hotline hỗ trợ 24/7: <b>1900 6868</b> | Email: contact@cozyhome.vn
                  </td>
                </tr>
                <tr>
                  <td style="padding-top:12px;font-size:11px;color:#a89487;text-align:center;">
                    Email này được gửi tự động từ hệ thống đặt phòng CozyHome. Vui lòng không trả lời thư này.
                  </td>
                </tr>
              </table>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""
    return html


def send_otp_email(
    to_email: str,
    otp: str,
    purpose: str = "register",
    user_name: str | None = None
) -> dict[str, Any]:
    """Gửi email chứa mã OTP qua giao thức SMTP (TLS/SSL).
    
    Trả về dict thống nhất:
    {
        "success": bool,
        "message": str,
        "error": str | None,
        "smtp_configured": bool,
        "delivery": "sent" | "dev_console" | "failed"
    }
    """
    cfg = get_smtp_config()
    clean_to = to_email.strip().lower()

    # Phân nhánh khi chưa cấu hình SMTP
    if not is_smtp_configured():
        if cfg["dev_fallback"]:
            # Chế độ dự phòng khi bảo vệ đồ án offline (không có internet / chưa có App Password)
            # Chỉ ghi ra server console, tuyệt đối không trả về client
            print(f"[CozyHome SMTP] Chưa cấu hình SMTP. OTP '{otp}' gửi tới '{clean_to}' được chuyển về chế độ Demo.")
            return {
                "success": False,
                "message": "Chưa cấu hình máy chủ gửi thư (SMTP). Hệ thống đang chạy ở chế độ Demo dành cho môi trường phát triển.",
                "error": "SMTP_NOT_CONFIGURED",
                "smtp_configured": False,
                "delivery": "dev_console",
            }
        else:
            return {
                "success": False,
                "message": "Dịch vụ gửi email chưa được cấu hình. Vui lòng liên hệ ban quản trị hệ thống.",
                "error": "SMTP_NOT_CONFIGURED",
                "smtp_configured": False,
                "delivery": "failed",
            }

    # Tiêu đề email
    if purpose == "register":
        subject = "CozyHome - Mã xác thực đăng ký tài khoản"
    else:
        subject = "CozyHome - Mã xác thực khôi phục mật khẩu"

    # Tạo MIME message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    from_name = cfg["from_name"]
    from_email = cfg["from_email"]
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = clean_to

    # Tạo nội dung text và html
    plain_text = render_otp_email_plain(clean_to, otp, purpose=purpose, user_name=user_name)
    html_text = render_otp_email_html(clean_to, otp, purpose=purpose, user_name=user_name)

    msg.attach(MIMEText(plain_text, "plain", "utf-8"))
    msg.attach(MIMEText(html_text, "html", "utf-8"))

    host = cfg["host"]
    port = cfg["port"]
    user = cfg["user"]
    password = cfg["password"]
    use_tls = cfg["use_tls"]

    try:
        ssl_context = ssl.create_default_context()

        # Port 465 dùng SMTP_SSL trực tiếp
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=10, context=ssl_context) as server:
                server.login(user, password)
                server.send_message(msg)
        else:
            # Port 587 (hoặc thông thường) dùng STARTTLS
            with smtplib.SMTP(host, port, timeout=10) as server:
                if use_tls:
                    server.starttls(context=ssl_context)
                server.login(user, password)
                server.send_message(msg)

        return {
            "success": True,
            "message": "Mã xác thực đã được gửi tới hộp thư của bạn thành công.",
            "error": None,
            "smtp_configured": True,
            "delivery": "sent",
        }

    except smtplib.SMTPAuthenticationError as e:
        error_msg = str(e)
        return {
            "success": False,
            "message": "Xác thực tài khoản SMTP thất bại. Với Gmail, vui lòng sử dụng App Password 16 ký tự thay vì mật khẩu thông thường.",
            "error": f"SMTPAuthenticationError: {error_msg}",
            "smtp_configured": True,
            "delivery": "failed",
        }
    except (smtplib.SMTPConnectError, TimeoutError, OSError) as e:
        return {
            "success": False,
            "message": "Không thể kết nối tới máy chủ gửi thư SMTP. Vui lòng kiểm tra lại kết nối mạng hoặc thử lại sau.",
            "error": f"ConnectionError: {type(e).__name__} - {str(e)}",
            "smtp_configured": True,
            "delivery": "failed",
        }
    except Exception as e:
        return {
            "success": False,
            "message": "Đã xảy ra lỗi khi gửi mã xác thực qua email. Vui lòng thử lại sau.",
            "error": f"SMTPException: {type(e).__name__} - {str(e)}",
            "smtp_configured": True,
            "delivery": "failed",
        }


def test_smtp_connection() -> dict[str, Any]:
    """Kiểm tra khả năng kết nối máy chủ SMTP phục vụ endpoint chẩn đoán `/api/auth/smtp-status`.
    Tuyệt đối không để lộ mật khẩu hay thông tin nhạy cảm.
    """
    cfg = get_smtp_config()
    if not is_smtp_configured():
        return {
            "configured": False,
            "reachable": False,
            "message": "Chưa cấu hình thông tin đăng nhập SMTP (SMTP_USER / SMTP_PASSWORD).",
            "host": cfg["host"],
            "port": cfg["port"],
        }

    host = cfg["host"]
    port = cfg["port"]
    user = cfg["user"]
    password = cfg["password"]
    use_tls = cfg["use_tls"]

    try:
        ssl_context = ssl.create_default_context()
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=10, context=ssl_context) as server:
                server.login(user, password)
        else:
            with smtplib.SMTP(host, port, timeout=10) as server:
                if use_tls:
                    server.starttls(context=ssl_context)
                server.login(user, password)

        return {
            "configured": True,
            "reachable": True,
            "message": "Kết nối và xác thực tới máy chủ SMTP thành công.",
            "host": host,
            "port": port,
        }
    except smtplib.SMTPAuthenticationError:
        return {
            "configured": True,
            "reachable": False,
            "message": "Kết nối được máy chủ nhưng xác thực thất bại. Vui lòng kiểm tra lại App Password 16 ký tự Gmail.",
            "host": host,
            "port": port,
        }
    except Exception as e:
        return {
            "configured": True,
            "reachable": False,
            "message": f"Không thể kết nối tới máy chủ SMTP ({type(e).__name__}).",
            "host": host,
            "port": port,
        }
