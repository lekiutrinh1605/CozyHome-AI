from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

try:
    from services.business_service import list_promotions, validate_promotion
except ImportError:
    from business_service import list_promotions, validate_promotion

router = APIRouter(prefix="/api/promotions", tags=["Promotions & Vouchers"])


class ValidatePromoRequest(BaseModel):
    code: str
    room_id: str = ""
    booking_date: str = ""
    khung_code: str = ""
    amount: int = 0
    user_id: int | None = None


@router.get("")
def get_all_promotions():
    """Lấy danh sách tất cả các chương trình ưu đãi và voucher đang kích hoạt."""
    promos = list_promotions()
    return {"promotions": promos}


@router.post("/validate")
def validate_promo_code(req: ValidatePromoRequest):
    """Kiểm tra điều kiện áp dụng mã khuyến mãi và tính toán số tiền giảm trừ thực tế."""
    res = validate_promotion(
        code=req.code,
        room_id=req.room_id,
        booking_date=req.booking_date,
        khung_code=req.khung_code,
        original_amount=req.amount,
        user_id=req.user_id,
    )
    return res
