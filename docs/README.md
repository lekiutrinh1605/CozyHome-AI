# CozyHome — Hệ Thống Đặt Phòng Chuỗi Homestay Đô Thị & Tư Vấn AI

> **Phiên bản:** 2.0.0 (Clean Modular Architecture)  
> **Backend:** Python FastAPI (REST API JSON)  
> **Frontend:** Single Page Application (HTML5, Vanilla CSS Design System, Modular ES6 JS)  
> **Database:** SQLite với đầy đủ ràng buộc toàn vẹn & tự động đối soát  
> **AI Engine:** Kiến trúc V3 (Python lọc điều kiện cứng ➜ LLM xếp hạng định tính ➜ Guardrails kiểm định)

---

## 1. Tổng quan Dự án

CozyHome là giải pháp đặt phòng trực tuyến dành cho chuỗi homestay tại TP.HCM (gồm 3 chi nhánh: **Bến Thành**, **Thảo Điền**, **Phú Mỹ Hưng**). Hệ thống được phát triển bám sát 100% tài liệu phân tích nghiệp vụ, mô hình BPMN, Use Case và hệ thống Business Rules (BR-01 đến BR-13).

### Điểm nổi bật:
1. **Lịch phòng 4 nhóm khung giờ (BR-01, BR-02, BR-03):** Áp dụng 4 ca linh hoạt (Sáng K1, Chiều K2, Chiều/Tối K3, Qua đêm QD) với khoảng đệm dọn vệ sinh 30–60 phút và dàn đều giờ cao điểm (N1 đến N4).
2. **Quy trình giữ chỗ 10 phút & VietQR MBBank (BR-04):** Đơn đặt mới được tự động giữ chỗ trong 10 phút kèm đồng hồ đếm ngược thời gian thực và mã QR chuyển khoản động.
3. **Gia hạn thêm giờ liền mạch (BR-06):** Khách đang lưu trú có thể gia hạn sang khung tiếp theo của chính căn phòng đó nếu khung sau còn trống, không phát sinh yêu cầu dọn phòng.
4. **Quy trình Vận hành 5 vai trò (RBAC - BR-08, BR-09, BR-11, BR-12):**
   - **Lễ tân:** Check-in, Check-out (tự động chuyển phòng sang "Cần dọn"), giám sát quá giờ, chuyển khiếu nại lên Quản lý.
   - **Buồng phòng:** Quy trình 5 bước (`Cần dọn` ➜ `Đang dọn` ➜ `Đã vệ sinh` ➜ `Sẵn sàng` / `Bảo trì`).
   - **Kế toán:** Đối soát các giao dịch thanh toán và các khoản hoàn tiền demo do hủy phòng.
   - **Quản lý chuỗi:** Giám sát KPI, đổi nhóm khung giờ hoạt động N1-N4 cho từng phòng, giải quyết khiếu nại khách hàng.
   - **Quản trị viên:** Mở khóa tài khoản bị khóa sau 5 lần nhập sai mật khẩu (UC-01), phân quyền chi nhánh và vai trò.
5. **Trợ lý ảo Cozy AI V3 (BR-13):** Tư vấn an toàn, chỉ đề xuất từ tập phòng đã lọc cứng qua Python, tuyệt đối không tự ý thực hiện giao dịch hay bịa dữ liệu.

---

## 2. Cấu trúc Mã nguồn (Modular Architecture)

```
CozyHome Project Root/
├── server.py                        # FastAPI entrypoint chính (Cổng 8000)
├── app.py                           # Streamlit prototype phụ (Cổng 8501)
├── run_web.bat                      # File thực thi khởi chạy nhanh Website Web App
├── run_streamlit.bat                # File thực thi khởi chạy Streamlit PoC
├── .env                             # Cấu hình môi trường bảo mật
├── .env.example                     # Mẫu cấu hình môi trường không chứa secret
├── requirements.txt                 # Khai báo thư viện phụ thuộc
├── api/                             # Router phân tách theo từng Domain nghiệp vụ
│   ├── auth_routes.py               # UC-01, UC-08: Đăng ký OTP, đăng nhập, profile
│   ├── room_routes.py               # UC-02: Tìm kiếm phòng, chi tiết, lịch 7 ngày
│   ├── booking_routes.py            # UC-03: Giữ chỗ 10p, VietQR MBBank, hoàn tiền, gia hạn
│   ├── operation_routes.py          # UC-04-07: Lễ tân, Buồng phòng, Kế toán, Quản lý, Admin
│   └── ai_routes.py                 # UC-02.4: Chatbot Cozy AI V3 (Gemini 3.7 Flash)
├── services/                        # Toàn bộ Business Logic & AI Services
│   ├── storage.py                   # Quản lý SQLite database (data/cozyhome_demo.db)
│   ├── email_service.py             # Dịch vụ gửi Email OTP qua SMTP chuẩn TLS/SSL (UC-01)
│   ├── business_service.py          # Nghiệp vụ tìm phòng, tính giá, lịch ca
│   ├── recommendation_engine.py     # Lọc dữ liệu phòng từ data/*.csv
│   ├── ai_service.py                # Wrapper gọi Google GenAI / Anthropic
│   ├── booking_guard.py             # Middleware giải phóng phòng giữ 10p (BR-04/BR-08)
│   ├── output_validator.py          # Guardrails kiểm tra JSON output của AI
│   └── prompt_template.py           # Template prompt V2/V3
├── data/                            # Dữ liệu nguồn và Database SQLite
│   ├── cozyhome_demo.db             # Database SQLite chính thức
│   └── *.csv, policies.json         # Dữ liệu phòng, giá, ca, khuyến mại
├── static/                          # Giao diện Frontend Single Page App (SPA)
│   ├── index.html                   # Giao diện chính của website
│   ├── css/                         # Design tokens, components, layout, checkout
│   ├── js/                          # Modular ES6 controllers (state, api, rooms, booking, checkout...)
│   └── images/                      # Banner hero, logo và kho ảnh phòng thực tế (rooms/BT, PMH, TD)
├── assets/                          # Tài nguyên gốc & ảnh raw (raw_images/)
├── scripts/                         # Script tiện ích (scripts_map_images.py)
└── docs/                            # Tài liệu kiến trúc & hướng dẫn phát triển
```

---

## 3. Hướng dẫn Khởi chạy Local

### Cách 1: Dùng File BAT tại thư mục gốc (Khuyến nghị)
Nhấp đúp chuột vào file:
```
D:\Đồ an em\Chay_Website.bat
```
- Chọn **[1]** (hoặc nhấn **Enter**) để khởi chạy Website Full-Stack tại `http://localhost:8000`.
- Chọn **[2]** nếu muốn xem bản Streamlit Prototype tại `http://localhost:8501`.

### Cách 2: Khởi chạy bằng file BAT trong project
Nhấp đúp vào file `run_web.bat` trong thư mục dự án.

### Cách 3: Khởi chạy bằng dòng lệnh
Từ thư mục dự án:
```bash
.venv\Scripts\python.exe server.py
```
Sau đó mở trình duyệt và truy cập: **`http://localhost:8000`**

---

## 4. Tài khoản Trải nghiệm Demo

Hệ thống cung cấp sẵn các tài khoản demo đại diện cho từng vai trò (**Mật khẩu chung:** `123456`):

| Vai trò | Email đăng nhập | Phạm vi công việc |
| :--- | :--- | :--- |
| **Khách hàng** | `demo@cozyhome.vn` | Đặt phòng, thanh toán VietQR, gia hạn khung kế tiếp, đánh giá lưu trú |
| **Lễ tân Bến Thành** | `letan.bt@cozyhome.vn` | Check-in, Check-out, cảnh báo quá giờ, chuyển khiếu nại lên Quản lý |
| **Buồng phòng BT** | `buong.bt@cozyhome.vn` | Cập nhật quy trình vệ sinh phòng 5 bước tại chi nhánh Bến Thành |
| **Kế toán chuỗi** | `ketoan@cozyhome.vn` | Đối soát giao dịch thanh toán và giải ngân hoàn tiền |
| **Quản lý chuỗi** | `quanly@cozyhome.vn` | Xem KPI, đổi Nhóm khung giờ (N1–N4), giải quyết khiếu nại |
| **Quản trị viên** | `admin@cozyhome.vn` | Mở khóa tài khoản bị khóa sau 5 lần nhập sai, phân bổ vai trò |

---

## 5. Hướng dẫn Triển khai Production (Deployment)

Khi đưa ứng dụng lên máy chủ Production (Linux / Ubuntu / Docker):
1. **Chạy qua Gunicorn + Uvicorn Workers:**
   ```bash
   pip install gunicorn
   gunicorn -w 4 -k uvicorn.workers.UvicornWorker server:app --bind 0.0.0.0:8000
   ```
2. **Cấu hình Reverse Proxy Nginx:**
   Ủy quyền cổng 80/443 sang cổng nội bộ 8000 và bật SSL (Let's Encrypt).
3. **Chuyển đổi Cơ sở dữ liệu:**
   Đổi kết nối SQLite trong `storage.py` sang PostgreSQL nếu có nhu cầu lưu trữ quy mô lớn.

---

## 6. Danh mục Chức năng đã Hoàn tất

- [x] **UC-01:** Xác thực người dùng (Đăng ký OTP qua Email SMTP chuẩn Production, bảo mật mã băm SHA-256, vô hiệu hóa sau 5 lần nhập sai mã, chống brute-force, Rate Limiting 60s cooldown, Đăng nhập, Tự động khóa sau 5 lần sai mật khẩu, Đổi mật khẩu, Quên mật khẩu OTP kiểm tra 2 lớp an toàn).
- [x] **UC-02:** Tìm kiếm đa tiêu chí, Xem ma trận lịch 7 ngày × 4 khung giờ, Trạng thái vận hành thực tế.
- [x] **UC-02.4:** Trợ lý ảo Cozy AI (V3 candidate_rooms fallback an toàn + kết nối Gemini).
- [x] **UC-03:** Tạo đơn giữ chỗ 10 phút (BR-04), Thanh toán VietQR MBBank sinh mã QR động.
- [x] **UC-03.3:** Hủy đơn đặt phòng trước check-in và tự động tạo giao dịch hoàn tiền demo (BR-05).
- [x] **UC-03.4:** Gia hạn sang khung kế tiếp của cùng phòng mà không cần dọn dẹp (BR-06).
- [x] **UC-04.1:** Lễ tân Check-in ghi nhận thời gian thực tế (`actual_checkin`).
- [x] **UC-04.2:** Cảnh báo tự động các đơn `Quá giờ - chưa checkout` (BR-08).
- [x] **UC-04.3:** Lễ tân Check-out tự động chuyển trạng thái phòng sang `Cần dọn` (BR-08).
- [x] **UC-04.4:** Buồng phòng cập nhật quy trình 5 bước (`Cần dọn` ➜ `Đang dọn` ➜ `Đã vệ sinh` ➜ `Sẵn sàng` / `Bảo trì`).
- [x] **UC-05.1:** Quản lý xem Dashboard KPI toàn chuỗi.
- [x] **UC-05.2:** Quản lý cấu hình gán Nhóm khung giờ N1–N4 cho từng phòng (BR-01, BR-02, BR-03).
- [x] **UC-06.1:** Kế toán đối soát giao dịch thanh toán và hoàn tiền (BR-09).
- [x] **UC-07:** Đánh giá trải nghiệm sau lưu trú (BR-12) và chuyển khiếu nại vượt thẩm quyền.
- [x] **UC-08:** Quản trị viên phân quyền chi nhánh và mở khóa tài khoản an toàn (BR-11).
- [x] **UI/UX Responsive:** Kiểm thử mượt mà trên Mobile (375px), Tablet (768px), Laptop (1024px) và Desktop.

---

## 7. Định hướng Phát triển Nâng cao Tiếp theo

1. **Cổng thanh toán tự động (Payment Gateway Webhook):** Kết nối trực tiếp với cổng PayOS/VNPay/MoMo qua Webhook để tự động xác nhận thanh toán thay vì nút mô phỏng.
2. **Hệ thống Thông báo Đa kênh (Notifications):** Gửi email xác nhận đặt phòng và tin nhắn Zalo ZNS khi check-in, check-out hoặc sắp hết giờ lưu trú.
3. **Mở rộng Đa ngôn ngữ (i18n):** Hỗ trợ chuyển đổi song ngữ Tiếng Việt - Tiếng Anh cho khách du lịch quốc tế.
