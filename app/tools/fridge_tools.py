"""
냉장고 재고 / 사용자 선호 관련 FunctionNode 툴.

FunctionNode(parameter_binding='state') 로 래핑되므로
함수 파라미터 이름이 state 키와 1:1 매핑됩니다.
"""
from app.db.repositories import fridge_repository, user_repository
from app.db.session import AsyncSessionLocal


async def load_user_context(user_id: int) -> dict:
    """
    state["user_id"] 를 받아 DB에서 재고/선호/유통기한 임박 재료를 조회한다.
    반환값은 state에 키별로 저장된다.
    """
    async with AsyncSessionLocal() as session:
        preferences = await user_repository.get_preferences(session, user_id)
        fridge_items = await user_repository.get_fridge_items(session, user_id)
        expiring_items = await user_repository.get_expiring_items(session, user_id, within_days=3)

    return {
        "preferences": preferences.model_dump() if preferences else {},
        "fridge_items": [i.model_dump() for i in fridge_items],
        "expiring_items": [i.model_dump() for i in expiring_items],
    }


async def merge_input_with_fridge(user_id: int, ingredients: list[str]) -> dict:
    """
    state["user_id"], state["ingredients"] 를 받아
    사용자가 언급한 재료와 DB 냉장고 재고를 합쳐 반환한다.
    """
    async with AsyncSessionLocal() as session:
        merged = await fridge_repository.merge_input_with_fridge(
            session, user_id=user_id, input_ingredients=ingredients
        )

    return {"merged_fridge_items": [i.model_dump() for i in merged]}
