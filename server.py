from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Thiết lập đường dẫn Project Root
BASE_DIR = Path(__file__).resolve().parent
SERVICES_DIR = BASE_DIR / "services"
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from services import storage
from services.booking_guard import run_system_maintenance
from api.admin_routes import router as admin_router
from api.ai_routes import router as ai_router
from api.auth_routes import router as auth_router
from api.booking_routes import router as booking_router
from api.operation_routes import router as operation_router
from api.room_routes import router as room_router
from api.promotion_routes import router as promotion_router

# Khởi tạo database nếu chưa có
storage.init_db()

app = FastAPI(
    title="CozyHome Web API",
    description="Hệ thống Backend REST API Chuỗi Homestay Đô thị CozyHome (BR-01 đến BR-13, UC-01 đến UC-08)",
    version="2.0.0",
)

# Cấu hình CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Middleware kiểm tra và giải phóng phòng hết hạn 10 phút trước mỗi request (BR-04, BR-08)
@app.middleware("http")
async def system_guard_middleware(request: Request, call_next):
    # Chỉ chạy bảo trì trên các endpoint API để tối ưu tốc độ
    if request.url.path.startswith("/api/"):
        try:
            run_system_maintenance()
        except Exception:
            pass
    response = await call_next(request)
    # Không cache HTML/JS/CSS ở trình duyệt để cập nhật giao diện ngay lập tức
    if not request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# Nạp các Routers theo từng domain nghiệp vụ
app.include_router(auth_router)
app.include_router(room_router)
app.include_router(booking_router)
app.include_router(operation_router)
app.include_router(admin_router)
app.include_router(ai_router)
app.include_router(promotion_router)

# Mount thư mục Static Files
STATIC_DIR = BASE_DIR / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
@app.get("/auth")
@app.get("/login")
@app.get("/register")
@app.get("/forgot-password")
@app.get("/select-role")
@app.get("/checkout")
@app.get("/bookings")
@app.get("/operations")
@app.get("/admin")
@app.get("/profile")
@app.get("/rooms/{room_id}")
def serve_home():
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return JSONResponse({"message": "CozyHome Web API is active."})


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "CozyHome Web API", "version": "2.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
