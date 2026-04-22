from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.fridge import UserFridgeItem
from app.db.models.ingredient import Ingredient
from app.schemas.agent_io import FridgeItemSnapshot


async def merge_input_with_fridge(
    session: AsyncSession,
    user_id: int,
    input_ingredients: list[str],
) -> list[FridgeItemSnapshot]:
    """
    사용자가 직접 언급한 재료와 DB 냉장고 재고를 합쳐 반환한다.
    - DB에 있는 재료는 DB 정보(수량·유통기한·신선도)를 사용
    - DB에 없는 언급 재료는 수량/유통기한 미상으로 추가
    - 중복은 DB 데이터를 우선
    """
    # DB 재고 조회
    result = await session.execute(
        select(UserFridgeItem)
        .options(selectinload(UserFridgeItem.ingredient))
        .where(UserFridgeItem.user_id == user_id)
    )
    db_items = result.scalars().all()

    merged: dict[str, FridgeItemSnapshot] = {
        item.ingredient.name: FridgeItemSnapshot(
            ingredient_id=item.ingredient_id,
            ingredient_name=item.ingredient.name,
            quantity=float(item.quantity),
            unit=item.unit,
            storage_type=item.storage_location,
            freshness_score=int(round((item.freshness_score or 1.0) * 5)),
            expires_at=item.expiry_date.isoformat() if item.expiry_date else None,
        )
        for item in db_items
    }

    # 언급 재료 중 DB에 없는 것을 보조로 추가
    for name in input_ingredients:
        normalized = name.strip()
        if normalized and normalized not in merged:
            # 재료 마스터에서 ID 조회 (없으면 None)
            ing_result = await session.execute(
                select(Ingredient).where(Ingredient.name == normalized)
            )
            ing = ing_result.scalar_one_or_none()
            merged[normalized] = FridgeItemSnapshot(
                ingredient_id=ing.id if ing else None,
                ingredient_name=normalized,
                quantity=None,
                unit=None,
                storage_type=None,
                freshness_score=None,
                expires_at=None,
            )

    return list(merged.values())
