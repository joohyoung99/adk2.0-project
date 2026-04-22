from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.fridge import UserFridgeItem
from app.db.models.ingredient import Ingredient
from app.db.models.user import User, UserPreference
from app.schemas.agent_io import FridgeItemSnapshot, UserPreferenceSnapshot


async def get_preferences(session: AsyncSession, user_id: int) -> UserPreferenceSnapshot | None:
    result = await session.execute(
        select(UserPreference).where(UserPreference.user_id == user_id)
    )
    pref = result.scalar_one_or_none()
    if pref is None:
        return None
    return UserPreferenceSnapshot(
        spicy_level=pref.spice_level,
        cooking_skill_level={"beginner": 1, "intermediate": 2, "advanced": 3}.get(pref.cooking_skill, 1),
        disliked_ingredients=pref.disliked_ingredients or [],
        allergies=pref.allergies or [],
        dietary_tags=pref.dietary_tags or [],
    )


async def get_fridge_items(session: AsyncSession, user_id: int) -> list[FridgeItemSnapshot]:
    result = await session.execute(
        select(UserFridgeItem)
        .options(selectinload(UserFridgeItem.ingredient))
        .where(UserFridgeItem.user_id == user_id)
    )
    rows = result.scalars().all()
    return [
        FridgeItemSnapshot(
            ingredient_id=item.ingredient_id,
            ingredient_name=item.ingredient.name,
            quantity=float(item.quantity),
            unit=item.unit,
            storage_type=item.storage_location,
            freshness_score=int(round((item.freshness_score or 1.0) * 5)),
            expires_at=item.expiry_date.isoformat() if item.expiry_date else None,
        )
        for item in rows
    ]


async def get_expiring_items(
    session: AsyncSession, user_id: int, within_days: int = 3
) -> list[FridgeItemSnapshot]:
    cutoff = date.today() + timedelta(days=within_days)
    result = await session.execute(
        select(UserFridgeItem)
        .options(selectinload(UserFridgeItem.ingredient))
        .where(
            UserFridgeItem.user_id == user_id,
            UserFridgeItem.expiry_date != None,  # noqa: E711
            UserFridgeItem.expiry_date <= cutoff,
        )
    )
    rows = result.scalars().all()
    return [
        FridgeItemSnapshot(
            ingredient_id=item.ingredient_id,
            ingredient_name=item.ingredient.name,
            quantity=float(item.quantity),
            unit=item.unit,
            storage_type=item.storage_location,
            freshness_score=int(round((item.freshness_score or 1.0) * 5)),
            expires_at=item.expiry_date.isoformat() if item.expiry_date else None,
        )
        for item in rows
    ]
