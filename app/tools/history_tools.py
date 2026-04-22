"""
추천 로그 저장 / 조리 이력 관련 FunctionNode 툴.
"""
from app.db.repositories import recommendation_repository
from app.db.session import AsyncSessionLocal


async def save_recommendation_log(
    user_id: int,
    user_content: str | None = None,
    fridge_items: list[dict] | None = None,
    preferences: dict | None = None,
    fit_results: list[dict] | None = None,
    best_route: str | None = None,
) -> dict:
    """
    워크플로우 종료 시점에 state에서 필요한 값을 수집해 DB에 저장한다.

    state 키 매핑:
      user_id       ← state["user_id"]
      user_content  ← state["user_content"]  (ADK가 자동 주입하는 사용자 원문)
      fridge_items  ← state["fridge_items"]
      preferences   ← state["preferences"]
      fit_results   ← state["fit_results"]
      best_route    ← state["best_route"]
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


async def get_recent_cooking_history(user_id: int, limit: int = 10) -> dict:
    """최근 조리 이력을 조회한다. branch agent 프롬프트에 컨텍스트로 주입 가능."""
    async with AsyncSessionLocal() as session:
        history = await recommendation_repository.get_recent_history(
            session, user_id=user_id, limit=limit
        )

    return {"cooking_history": history}
