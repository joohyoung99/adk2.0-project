"""
레시피 탐색 / 매칭 평가 / 대체재 조회 관련 FunctionNode 툴.
"""
from app.db.repositories import recipe_repository
from app.db.session import AsyncSessionLocal
from app.schemas.agent_io import FridgeItemSnapshot


async def search_candidate_recipes(
    max_cooking_time: int | None = None,
    allowed_tools: list[str] | None = None,
    preferences: dict | None = None,
) -> dict:
    """
    state["max_cooking_time"], state["allowed_tools"], state["preferences"]
    를 받아 DB에서 후보 레시피를 탐색한다.
    """
    dietary_tags: list[str] = (preferences or {}).get("dietary_tags", [])

    async with AsyncSessionLocal() as session:
        candidates = await recipe_repository.search_candidates(
            session,
            max_cooking_time=max_cooking_time,
            allowed_tools=allowed_tools or [],
            dietary_tags=dietary_tags or [],
        )

    return {"candidates": [c.model_dump() for c in candidates]}


async def evaluate_recipe_fit(
    candidates: list[dict],
    fridge_items: list[dict],
    preferences: dict | None = None,
) -> dict:
    """
    state["candidates"], state["fridge_items"] 를 받아
    레시피별 매칭 점수와 최종 route 를 결정한다.

    - 알레르기/비선호 재료가 포함된 레시피는 후보에서 제외
    - 최고 점수 레시피 기준으로 route 결정
    - DB 후보가 없으면 보유 재료 수로 route 폴백 결정
    """
    allergies: set[str] = set((preferences or {}).get("allergies", []))
    disliked: set[str] = set((preferences or {}).get("disliked_ingredients", []))
    fridge_snapshots = [FridgeItemSnapshot(**i) for i in fridge_items]

    fit_results = []

    async with AsyncSessionLocal() as session:
        for c in candidates:
            result = await recipe_repository.calculate_match(
                session,
                fridge_items=fridge_snapshots,
                recipe_id=c["recipe_id"],
            )
            # 알레르기·비선호 재료 포함 레시피 제외
            recipe_ing_names = set(
                result.missing_required + result.missing_optional
            )
            if recipe_ing_names & allergies:
                continue
            fit_results.append(result)

    # DB 후보가 없으면 보유 재료 수로 폴백 라우팅
    if not fit_results:
        n = len(fridge_snapshots)
        route = "COOK_NOW" if n >= 5 else "SUBSTITUTION" if n >= 3 else "SHOPPING_NEEDED"
        return {
            "fit_results": [],
            "best_route": route,
            "best_recipe_id": None,
        }

    # 점수 내림차순 정렬
    fit_results.sort(key=lambda r: r.match_score, reverse=True)
    best = fit_results[0]

    # 대체재 존재 여부로 SHOPPING → SUBSTITUTION 승격
    if best.route == "SHOPPING_NEEDED":
        async with AsyncSessionLocal() as session:
            from app.db.repositories.recipe_repository import get_recipe_ingredients
            from app.db.models.ingredient import IngredientSubstitution
            from sqlalchemy import select

            has_sub = False
            for missing in best.missing_required:
                result_sub = await session.execute(
                    select(IngredientSubstitution)
                    .join(
                        IngredientSubstitution.original_ingredient
                    )
                    .where(
                        IngredientSubstitution.original_ingredient.has(name=missing)
                    )
                )
                if result_sub.scalars().first():
                    has_sub = True
                    break

            if has_sub:
                best = best.model_copy(update={"route": "SUBSTITUTION"})

    return {
        "fit_results": [r.model_dump() for r in fit_results],
        "best_route": best.route,
        "best_recipe_id": best.recipe_id,
    }


async def get_substitutions_for_missing(missing_items: list[str]) -> dict:
    """
    부족한 재료 목록을 받아 DB에서 대체재를 조회한다.
    Dynamic Recovery 루프에서 사용한다.
    """
    from app.db.models.ingredient import Ingredient, IngredientSubstitution
    from sqlalchemy import select

    substitution_map: dict[str, list[dict]] = {}

    async with AsyncSessionLocal() as session:
        for item in missing_items:
            result = await session.execute(
                select(IngredientSubstitution)
                .join(
                    IngredientSubstitution.original_ingredient
                )
                .join(
                    IngredientSubstitution.substitute_ingredient
                )
                .where(
                    IngredientSubstitution.original_ingredient.has(name=item)
                )
            )
            rows = result.scalars().all()
            substitution_map[item] = [
                {
                    "substitute": row.substitute_ingredient.name,
                    "ratio": float(row.substitution_ratio),
                    "note": row.note,
                }
                for row in rows
            ]

    return {"substitution_map": substitution_map}
