"""
냉장고 재고 / 사용자 선호 관련 FunctionNode 툴.

FunctionNode(parameter_binding='state') 로 래핑되므로
함수 파라미터 이름이 state 키와 1:1 매핑됩니다.
ctx 는 ADK 가 자동 주입하며, 명시적 state 기록에 사용합니다.
"""
from google.adk import Context

from app.db.repositories import fridge_repository, user_repository
from app.db.session import AsyncSessionLocal


async def load_user_context(user_id: int, ctx: Context) -> dict:
    """
    state["user_id"] 를 받아 DB에서 재고/선호/유통기한 임박 재료를 조회한다.
    """
    async with AsyncSessionLocal() as session:
        preferences = await user_repository.get_preferences(session, user_id)
        fridge_items = await user_repository.get_fridge_items(session, user_id)
        expiring_items = await user_repository.get_expiring_items(session, user_id, within_days=3)

    prefs_dict = preferences.model_dump() if preferences else {}
    fridge_list = [i.model_dump() for i in fridge_items]
    expiring_list = [i.model_dump() for i in expiring_items]

    ctx.state["preferences"] = prefs_dict
    ctx.state["fridge_items"] = fridge_list
    ctx.state["expiring_items"] = expiring_list

    return {
        "preferences": prefs_dict,
        "fridge_items": fridge_list,
        "expiring_items": expiring_list,
    }


async def merge_input_with_fridge(user_id: int, ingredients: list[str], ctx: Context) -> dict:
    """
    state["user_id"], state["ingredients"] 를 받아
    사용자가 언급한 재료와 DB 냉장고 재고를 합쳐 반환한다.
    """
    async with AsyncSessionLocal() as session:
        merged = await fridge_repository.merge_input_with_fridge(
            session, user_id=user_id, input_ingredients=ingredients
        )

    fridge_list = [i.model_dump() for i in merged]
    ctx.state["fridge_items"] = fridge_list

    return {"fridge_items": fridge_list}
