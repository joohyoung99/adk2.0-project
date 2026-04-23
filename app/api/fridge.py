from datetime import date

from fastapi import APIRouter
from pydantic import BaseModel

from app.db.repositories import user_repository
from app.db.session import AsyncSessionLocal

router = APIRouter()


class FridgeItemOut(BaseModel):
    ingredient_name: str
    quantity: float | None
    unit: str | None
    freshness_score: int | None
    expires_at: str | None
    days_until_expiry: int | None


class FridgeResponse(BaseModel):
    fridge_items: list[FridgeItemOut]
    expiring_items: list[FridgeItemOut]


def _days_until(expires_at: str | None) -> int | None:
    if not expires_at:
        return None
    delta = date.fromisoformat(expires_at) - date.today()
    return delta.days


@router.get("/api/fridge/{user_id}", response_model=FridgeResponse)
async def get_fridge(user_id: int):
    async with AsyncSessionLocal() as session:
        fridge_items = await user_repository.get_fridge_items(session, user_id)
        expiring_items = await user_repository.get_expiring_items(session, user_id, within_days=3)

    return FridgeResponse(
        fridge_items=[
            FridgeItemOut(
                **item.model_dump(),
                days_until_expiry=_days_until(item.expires_at),
            )
            for item in fridge_items
        ],
        expiring_items=[
            FridgeItemOut(
                **item.model_dump(),
                days_until_expiry=_days_until(item.expires_at),
            )
            for item in expiring_items
        ],
    )
