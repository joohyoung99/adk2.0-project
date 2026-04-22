from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.ingredient import Ingredient
from app.db.models.recipe import Recipe, RecipeIngredient
from app.schemas.agent_io import FridgeItemSnapshot, RecipeCandidate, RecipeFitResult


async def search_candidates(
    session: AsyncSession,
    max_cooking_time: int | None = None,
    allowed_tools: list[str] | None = None,
    dietary_tags: list[str] | None = None,
) -> list[RecipeCandidate]:
    stmt = select(Recipe)

    if max_cooking_time is not None:
        stmt = stmt.where(Recipe.cooking_time <= max_cooking_time)

    if allowed_tools:
        # 레시피 tool_tags 중 하나라도 allowed_tools에 포함되면 선택
        stmt = stmt.where(Recipe.tool_tags.overlap(allowed_tools))

    if dietary_tags:
        stmt = stmt.where(Recipe.dietary_tags.contains(dietary_tags))

    result = await session.execute(stmt)
    recipes = result.scalars().all()

    return [
        RecipeCandidate(
            recipe_id=r.id,
            title=r.title,
            description=r.description,
            cooking_time_min=r.cooking_time,
            difficulty={"easy": 1, "medium": 2, "hard": 3}.get(r.difficulty, 1),
            tool_tags=r.tool_tags or [],
            dietary_tags=r.dietary_tags or [],
        )
        for r in recipes
    ]


async def get_recipe_ingredients(
    session: AsyncSession, recipe_id: int
) -> list[dict]:
    result = await session.execute(
        select(RecipeIngredient)
        .options(selectinload(RecipeIngredient.ingredient))
        .where(RecipeIngredient.recipe_id == recipe_id)
    )
    rows = result.scalars().all()
    return [
        {
            "ingredient_id": row.ingredient_id,
            "ingredient_name": row.ingredient.name,
            "quantity": float(row.quantity),
            "unit": row.unit,
            "is_required": row.is_required,
            "is_garnish": row.is_garnish,
        }
        for row in rows
    ]


async def calculate_match(
    session: AsyncSession,
    fridge_items: list[FridgeItemSnapshot],
    recipe_id: int,
) -> RecipeFitResult:
    """
    보유 재료와 레시피 필요 재료를 비교해 매칭 점수와 route를 계산한다.

    점수 산정:
    - 필수 재료 보유 여부가 핵심
    - match_score = 보유 재료 수 / 전체 재료 수 (garnish 제외)
    route 결정:
    - missing_required == 0           → COOK_NOW
    - missing_required > 0, 대체재 있음 → SUBSTITUTION  (대체재 조회는 services 레이어)
    - missing_required > 0            → SHOPPING_NEEDED
    """
    recipe_ings = await get_recipe_ingredients(session, recipe_id)

    fridge_names = {item.ingredient_name for item in fridge_items}

    # 레시피 제목 조회
    recipe_result = await session.execute(select(Recipe).where(Recipe.id == recipe_id))
    recipe = recipe_result.scalar_one()

    non_garnish = [r for r in recipe_ings if not r["is_garnish"]]
    required = [r for r in non_garnish if r["is_required"]]
    optional = [r for r in non_garnish if not r["is_required"]]

    missing_required = [r["ingredient_name"] for r in required if r["ingredient_name"] not in fridge_names]
    missing_optional = [r["ingredient_name"] for r in optional if r["ingredient_name"] not in fridge_names]

    total = len(non_garnish) or 1
    have = total - len(missing_required) - len(missing_optional)
    match_score = round(have / total, 2)

    if not missing_required:
        route = "COOK_NOW"
        cookable = True
    else:
        # 대체재 가능 여부는 services 레이어에서 처리 — 여기선 SHOPPING_NEEDED로 마킹
        route = "SHOPPING_NEEDED"
        cookable = False

    return RecipeFitResult(
        recipe_id=recipe_id,
        title=recipe.title,
        match_score=match_score,
        missing_required=missing_required,
        missing_optional=missing_optional,
        route=route,
        cookable_now=cookable,
    )
