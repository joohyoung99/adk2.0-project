"""
대체재 적용 서비스.
DB 호출 없는 순수 계산 — substitution_map을 보고 missing 재료를 대체재로 교체한다.
"""


def apply_substitutions(
    candidate: dict,
    substitution_map: dict,
    fridge_items: list[dict],
) -> dict:
    """
    부족한 필수 재료에 대해 대체재를 적용하고, route를 재평가한다.

    Args:
        candidate: RecipeFitResult.model_dump() 형태의 dict
        substitution_map: {원재료명: [{substitute, ratio, note}, ...]}
        fridge_items: FridgeItemSnapshot.model_dump() 형태의 리스트

    Returns:
        route, missing_required, applied_substitutions 가 업데이트된 candidate dict
    """
    fridge_names: set[str] = {i["ingredient_name"] for i in fridge_items}
    still_missing: list[str] = []
    applied: list[dict] = []

    for item in candidate.get("missing_required", []):
        subs = substitution_map.get(item, [])
        replaced = False
        for sub in subs:
            if sub["substitute"] in fridge_names:
                applied.append({
                    "missing": item,
                    "substitute": sub["substitute"],
                    "ratio": sub["ratio"],
                    "note": sub["note"],
                })
                replaced = True
                break
        if not replaced:
            still_missing.append(item)

    if not still_missing:
        route = "COOK_NOW"
    elif applied:
        route = "SUBSTITUTION"
    else:
        route = "SHOPPING_NEEDED"

    return {
        **candidate,
        "route": route,
        "cookable_now": route == "COOK_NOW",
        "missing_required": still_missing,
        "applied_substitutions": applied,
    }


def apply_substitutions_to_all(
    fit_results: list[dict],
    substitution_map: dict,
    fridge_items: list[dict],
) -> list[dict]:
    """fit_results 전체에 대해 대체재를 적용한다. Dynamic Recovery 루프용."""
    return [apply_substitutions(r, substitution_map, fridge_items) for r in fit_results]
