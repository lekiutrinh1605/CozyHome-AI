from __future__ import annotations

import os
from typing import Any
from fastapi import APIRouter
from pydantic import BaseModel

try:
    from services.chatbot_engine import ChatbotEngine, SessionManager
except ImportError:
    from chatbot_engine import ChatbotEngine, SessionManager

router = APIRouter(prefix="/api/ai", tags=["Cozy AI"])


class ChatAiRequest(BaseModel):
    session_id: str = ""
    query: str = ""
    user_id: int | None = None
    branch_id: str | None = None
    guests: int | None = None
    date: str | None = None
    khung_code: str | None = None
    budget_max: int | None = None


class ResetSessionRequest(BaseModel):
    session_id: str


class ClearHistoryRequest(BaseModel):
    user_id: int | None = None
    session_id: str | None = None


@router.post("/chat")
def ai_chat(req: ChatAiRequest):
    # Đảm bảo session_id tồn tại
    session_id = req.session_id.strip() if req.session_id else f"sess_{os.urandom(6).hex()}"

    # Nếu người dùng có gửi kèm filter tường minh (ví dụ từ search bar), cập nhật vào context
    context_updates = {}
    if req.branch_id and req.branch_id in ["BT", "TD", "PMH"]:
        context_updates["branch_id"] = req.branch_id
    if req.guests and req.guests > 0:
        context_updates["guests"] = req.guests
    if req.date and len(req.date) >= 10:
        context_updates["date"] = req.date
    if req.khung_code and req.khung_code in ["K1", "K2", "K3", "QD"]:
        context_updates["khung_code"] = req.khung_code
    if req.budget_max and req.budget_max > 0:
        context_updates["budget_max"] = req.budget_max

    if context_updates:
        SessionManager.update_context(session_id, context_updates)

    # Xử lý qua Chatbot Engine có gắn kèm user_id nếu đã đăng nhập
    result = ChatbotEngine.process_message(session_id, req.query, user_id=req.user_id)
    return result


@router.get("/history")
def get_chat_history(user_id: int | None = None, session_id: str | None = None, limit: int = 50):
    try:
        from services.storage import get_user_chat_history
    except ImportError:
        from storage import get_user_chat_history
    history = get_user_chat_history(user_id=user_id, session_id=session_id, limit=limit)
    return {"status": "ok", "history": history}


@router.post("/clear-history")
def clear_history_endpoint(req: ClearHistoryRequest):
    try:
        from services.storage import clear_chat_history
    except ImportError:
        from storage import clear_chat_history
    count = clear_chat_history(user_id=req.user_id, session_id=req.session_id)
    if req.session_id:
        SessionManager.reset_session(req.session_id)
    return {"status": "ok", "deleted_count": count, "message": "Lịch sử trò chuyện đã được làm sạch."}


@router.post("/reset")
def reset_chat_session(req: ResetSessionRequest):
    SessionManager.reset_session(req.session_id)
    return {"status": "ok", "message": "Phiên trò chuyện đã được làm mới."}
