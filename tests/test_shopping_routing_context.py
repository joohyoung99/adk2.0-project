from app.agents.prompts import SHOPPING_PROMPT
from app.schemas.agent_io import FridgeItemSnapshot
from app.tools.recipe_tools import _get_requested_missing_items


def test_requested_missing_items_keeps_user_requested_unknown_ingredients():
    fridge_items = [
        FridgeItemSnapshot(ingredient_name="계란", quantity=6.0),
        FridgeItemSnapshot(ingredient_name="간장", quantity=200.0),
    ]

    missing = _get_requested_missing_items(["연어", "계란", "연어"], fridge_items)

    assert missing == ["연어"]


def test_requested_missing_items_treats_quantity_unknown_as_not_in_fridge():
    fridge_items = [
        FridgeItemSnapshot(ingredient_name="연어", ingredient_id=None, quantity=None),
    ]

    missing = _get_requested_missing_items(["연어"], fridge_items)

    assert missing == ["연어"]


def test_shopping_prompt_includes_original_request_constraints():
    assert "사용자 요청 재료: {ingredients}" in SHOPPING_PROMPT
    assert "사용 가능한 조리 도구: {allowed_tools}" in SHOPPING_PROMPT
    assert "최대 조리 시간(분): {max_cooking_time}" in SHOPPING_PROMPT
    assert "부족/구매 필요 재료: {missing_items}" in SHOPPING_PROMPT
    assert "라우팅 사유: {route_reason}" in SHOPPING_PROMPT


def test_shopping_prompt_forbids_no_purchase_escape_hatch():
    assert "사용자가 특정 재료나 조리 도구를 말한 경우 반드시 그 조건을 우선하세요." in SHOPPING_PROMPT
    assert "사용자 요청 핵심 재료가 냉장고에 없으면 반드시 추가 구매 재료에 포함하세요." in SHOPPING_PROMPT
    assert 'ShoppingAgent 응답에서 "추가 구매 재료 없음"은 금지입니다.' in SHOPPING_PROMPT
