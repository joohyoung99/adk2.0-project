"""
추천 로그 저장 / 조리 이력 관련 워크플로우 노드.
ctx 는 ADK 가 자동 주입하며, 명시적 state 기록에 사용합니다.
"""
from google.adk import Context
from google.adk.workflow import node

from app.db.repositories import recommendation_repository
from app.db.session import AsyncSessionLocal


@node
async def save_recommendation_log(
    ctx: Context,
    user_id: int,
    user_content: str | None = None,
    fridge_items: list[dict] | None = None,
    preferences: dict | None = None,
    fit_results: list[dict] | None = None,
    best_route: str | None = None,
    best_recipe_id: int | None = None,
) -> dict:
    """
    워크플로우 종료 시점에 state에서 필요한 값을 수집해 DB에 저장한다.

    state 키 매핑:
      user_id         ← state["user_id"]
      user_content    ← state["user_content"]
      fridge_items    ← state["fridge_items"]
      preferences     ← state["preferences"]
      fit_results     ← state["fit_results"]
      best_route      ← state["best_route"]
      best_recipe_id  ← state["best_recipe_id"]
    """
    context_json = {
        "fridge_items": fridge_items or [],
        "preferences": preferences or {},
    }
    result_json = {
        "fit_results": fit_results or [],
        "best_route": best_route,
    }

    async with AsyncSessionLocal() as session:
        log_id = await recommendation_repository.save_log(
            session,
            user_id=user_id,
            request_text=user_content or "",
            context_json=context_json,
            result_json=result_json,
            route=best_route,
        )

    if best_recipe_id:
        async with AsyncSessionLocal() as session:
            await recommendation_repository.save_feedback(
                session,
                user_id=user_id,
                recipe_id=best_recipe_id,
                rating=None,
                liked=None,
                feedback_text=None,
            )

    ctx.state["log_id"] = log_id

    top_titles = [r.get("title") for r in (fit_results or [])[:5] if r.get("title")]
    seen = ctx.state.get("seen_recipe_titles", [])
    ctx.state["seen_recipe_titles"] = (seen + top_titles)[-20:]

    return {"log_id": log_id}


async def save_cooking_feedback(
    user_id: int,
    recipe_id: int,
    rating: int | None = None,
    liked: bool | None = None,
    feedback_text: str | None = None,
) -> dict:
    """조리 피드백을 DB에 저장한다."""
    async with AsyncSessionLocal() as session:
        history_id = await recommendation_repository.save_feedback(
            session,
            user_id=user_id,
            recipe_id=recipe_id,
            rating=rating,
            liked=liked,
            feedback_text=feedback_text,
        )

    return {"history_id": history_id}


async def get_recent_cooking_history(ctx: Context, user_id: int, limit: int = 10) -> dict:
    """최근 조리 이력을 조회해 state["cooking_history"]에 저장한다."""
    async with AsyncSessionLocal() as session:
        history = await recommendation_repository.get_recent_history(
            session, user_id=user_id, limit=limit
        )

    ctx.state["cooking_history"] = history
    return {"cooking_history": history}
