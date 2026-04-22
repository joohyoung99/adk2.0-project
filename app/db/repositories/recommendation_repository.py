from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.history import CookingHistory, RecommendationLog


async def save_log(
    session: AsyncSession,
    user_id: int,
    request_text: str,
    context_json: dict,
    result_json: dict,
    route: str | None = None,
) -> int:
    log = RecommendationLog(
        user_id=user_id,
        request_text=request_text,
        context_json=context_json,
        result_json=result_json,
        route=route,
    )
    session.add(log)
    await session.flush()
    await session.commit()
    return log.id


async def save_feedback(
    session: AsyncSession,
    user_id: int,
    recipe_id: int,
    rating: int | None,
    liked: bool | None,
    feedback_text: str | None,
) -> int:
    history = CookingHistory(
        user_id=user_id,
        recipe_id=recipe_id,
        rating=rating,
        liked=liked,
        feedback_text=feedback_text,
    )
    session.add(history)
    await session.flush()
    await session.commit()
    return history.id


async def get_recent_history(
    session: AsyncSession, user_id: int, limit: int = 10
) -> list[dict]:
    result = await session.execute(
        select(CookingHistory)
        .where(CookingHistory.user_id == user_id)
        .order_by(CookingHistory.cooked_at.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [
        {
            "id": row.id,
            "recipe_id": row.recipe_id,
            "rating": row.rating,
            "liked": row.liked,
            "feedback_text": row.feedback_text,
            "cooked_at": row.cooked_at.isoformat(),
        }
        for row in rows
    ]
