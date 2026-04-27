import json

from app.services.response_formatter import ensure_user_facing_response


def test_market_plan_json_is_converted_to_user_facing_recipe():
    raw_response = json.dumps({
        "offers": [
            {
                "ingredient": "오리",
                "canonical_ingredient": "오리",
                "market": "N/A",
                "product_name": "N/A",
                "observed_price": None,
                "currency": "KRW",
                "unit": "N/A",
                "quantity_value": None,
                "quantity_unit": None,
                "in_stock": False,
                "source_file": "local_catalog",
                "updated_at": "",
                "confidence": "low",
                "note": "로컬 catalog에서 해당 재료를 찾지 못했습니다.",
            }
        ],
        "recommended_market": None,
        "warnings": ["로컬 catalog 기준 가격 후보이며 실제 가격/재고/배송비와 다를 수 있음"],
    }, ensure_ascii=False)

    formatted = ensure_user_facing_response(
        raw_response,
        {
            "ingredients": ["오리"],
            "missing_items": ["오리"],
            "allowed_tools": ["oven"],
        },
    )

    assert not formatted.lstrip().startswith("{")
    assert "오븐 오리구이" in formatted
    assert "추가 구매 재료" in formatted
    assert "로컬 catalog" in formatted


def test_non_json_response_is_preserved():
    response = "### 1. 추천 레시피\n오븐 오리구이"

    assert ensure_user_facing_response(response, {}) == response
