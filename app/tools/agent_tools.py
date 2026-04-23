"""
LLM 에이전트가 직접 호출하는 도구 함수.
FunctionNode와 달리 tool_context 파라미터로 ADK가 자동 주입하며,
LLM이 자율적으로 호출 여부를 판단한다.
"""
from google.adk.tools.tool_context import ToolContext

from app.db.repositories import recommendation_repository
from app.db.session import AsyncSessionLocal


async def get_cooking_history(tool_context: ToolContext, limit: int = 10) -> dict:
    """최근 조리 이력을 조회한다.

    추천 전 반드시 호출해 최근에 만든 레시피를 확인하고 중복 추천을 방지하라.

    Args:
        limit: 조회할 이력 수 (기본 10)

    Returns:
        cooking_history: [{recipe_id, cooked_at, rating, liked}, ...]
    """
    user_id = tool_context.state.get("user_id")
    if not user_id:
        return {"cooking_history": []}

    async with AsyncSessionLocal() as session:
        history = await recommendation_repository.get_recent_history(
            session, user_id=int(user_id), limit=limit
        )

    tool_context.state["cooking_history"] = history
    return {"cooking_history": history}


async def get_substitutions(missing_items: list[str], tool_context: ToolContext) -> dict:
    """부족한 재료의 DB 대체재를 조회한다.

    보유 재료로 만들기 어려운 레시피의 missing 재료에 대해 호출하라.
    substitution_map이 비어있으면 DB에 대체재 없음을 의미한다.

    Args:
        missing_items: 대체재를 찾을 재료명 목록

    Returns:
        substitution_map: {재료명: [{substitute, ratio, note}, ...]}
    """
    from app.db.models.ingredient import IngredientSubstitution
    from sqlalchemy import select

    substitution_map: dict[str, list[dict]] = {}

    async with AsyncSessionLocal() as session:
        for item in missing_items:
            result = await session.execute(
                select(IngredientSubstitution)
                .join(IngredientSubstitution.original_ingredient)
                .join(IngredientSubstitution.substitute_ingredient)
                .where(IngredientSubstitution.original_ingredient.has(name=item))
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

    tool_context.state["substitution_map"] = substitution_map
    return {"substitution_map": substitution_map}
