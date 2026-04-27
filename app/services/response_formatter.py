"""User-facing response formatting safeguards."""
import json
from typing import Any


TOOL_LABELS = {
    "oven": "오븐",
    "pan": "팬",
    "pot": "냄비",
    "microwave": "전자레인지",
    "airfryer": "에어프라이어",
    "grill": "그릴",
}


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        normalized = item.strip()
        if normalized and normalized not in seen:
            result.append(normalized)
            seen.add(normalized)
    return result


def _parse_market_plan_json(response: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(response)
    except (TypeError, json.JSONDecodeError):
        return None

    if not isinstance(parsed, dict):
        return None

    market_plan_keys = {"offers", "recommended_market", "warnings"}
    if not market_plan_keys.issubset(parsed.keys()):
        return None

    return parsed


def ensure_user_facing_response(
    response: str,
    state: dict[str, Any],
) -> str:
    """Prevent raw tool JSON from leaking to the chat UI."""
    market_plan = _parse_market_plan_json(response)
    if market_plan is None:
        return response

    ingredients = _dedupe([str(item) for item in state.get("ingredients", [])])
    missing_items = _dedupe([str(item) for item in state.get("missing_items", [])])
    offer_items = _dedupe([
        str(offer.get("ingredient", ""))
        for offer in market_plan.get("offers", [])
        if isinstance(offer, dict)
    ])
    purchase_items = _dedupe(missing_items + offer_items + ingredients)

    main_ingredient = purchase_items[0] if purchase_items else "주재료"
    allowed_tools = state.get("allowed_tools", []) or []
    tool_label = TOOL_LABELS.get(allowed_tools[0], allowed_tools[0]) if allowed_tools else "기본 조리도구"
    recipe_title = f"{tool_label} {main_ingredient}구이" if tool_label == "오븐" else f"{main_ingredient} 간단 요리"

    offers = [
        offer
        for offer in market_plan.get("offers", [])
        if isinstance(offer, dict)
    ]
    available_offers = [
        offer
        for offer in offers
        if offer.get("market") not in {None, "N/A"} and offer.get("product_name") not in {None, "N/A"}
    ]

    if available_offers:
        offer_lines = [
            f"- {offer['ingredient']}: {offer['market']} / {offer['product_name']} / "
            f"{offer.get('observed_price', '가격 정보 없음')}원 / "
            f"{'재고 있음' if offer.get('in_stock') else '재고 없음'}"
            for offer in available_offers
        ]
    else:
        offer_lines = [
            "- 로컬 catalog에서 해당 재료의 구매 후보를 찾지 못했습니다.",
            "- 재료명이나 catalog 데이터를 추가하면 구매처 비교가 가능합니다.",
        ]

    purchase_lines = [f"- {item}" for item in purchase_items] or ["- 구매 필요 재료를 확인하지 못했습니다."]

    return "\n".join([
        f"### 1. 추천 레시피",
        f"**{recipe_title}**",
        f"{main_ingredient}을(를) 중심으로 요청한 조리 조건을 반영한 장보기 기반 레시피입니다.",
        "",
        "### 2. 보유 재료 활용",
        "냉장고 재료는 보조 재료나 양념으로 활용하고, 요청한 핵심 재료는 구매 목록에 포함합니다.",
        "",
        "### 3. 추가 구매 재료",
        *purchase_lines,
        "",
        "### 4. 간단 조리 순서",
        f"- {main_ingredient}을(를) 손질하고 소금, 후추, 식용유로 밑간합니다.",
        f"- {tool_label}을(를) 예열하거나 준비합니다.",
        f"- {main_ingredient}을(를) 익을 때까지 조리합니다.",
        "- 간을 보고 부족하면 간장이나 소금으로 마무리합니다.",
        "",
        "### 5. 로컬 catalog 기반 구매 후보",
        *offer_lines,
        "",
        "### 6. 가격/재고 변동 주의사항",
        "위 가격 정보는 로컬 catalog 기준 가격 후보이며, 실제 가격·재고·배송비와 다를 수 있습니다.",
    ])
