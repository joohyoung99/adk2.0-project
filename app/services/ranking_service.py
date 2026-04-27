"""
레시피 후보 랭킹 서비스.
DB 호출 없는 순수 계산 — 매칭 점수에 유통기한·선호 보정을 더해 재정렬한다.
"""

EXPIRING_BONUS = 0.10    # 유통기한 임박 재료 1개당 보너스
DISLIKED_PENALTY = 0.05  # 비선호 재료 1개당 페널티
USER_MENTION_BONUS = 0.12  # 사용자가 직접 언급한 재료 1개당 보너스 (유통기한보다 우선)


def rank_candidates(
    fit_results: list[dict],
    expiring_items: list[dict],
    preferences: dict,
    fridge_items: list[dict] | None = None,
    user_ingredients: list[str] | None = None,
) -> list[dict]:
    """
    fit_results 를 최종 점수 기준으로 내림차순 정렬해 반환한다.

    최종점수 = match_score
             + 사용자 언급 재료 사용 수 * USER_MENTION_BONUS
             + 유통기한 임박 재료 사용 수 * EXPIRING_BONUS
             - 비선호 재료 포함 수 * DISLIKED_PENALTY
    """
    expiring_names: set[str] = {i["ingredient_name"] for i in expiring_items}
    disliked_names: set[str] = set(preferences.get("disliked_ingredients", []))
    fridge_names: set[str] = {i["ingredient_name"] for i in (fridge_items or [])}
    mentioned_names: set[str] = set(user_ingredients or [])

    ranked = []
    for result in fit_results:
        missing_all = set(result.get("missing_required", []) + result.get("missing_optional", []))
        missing_required = set(result.get("missing_required", []))

        # 보유 재료 중 레시피에서 사용되는 것 = 냉장고에 있는데 missing이 아닌 것
        used_from_fridge = fridge_names - missing_all

        user_mention_bonus = len(mentioned_names & used_from_fridge) * USER_MENTION_BONUS
        expiring_bonus = len(expiring_names & used_from_fridge) * EXPIRING_BONUS
        disliked_penalty = len(
            disliked_names & (missing_required | used_from_fridge)
        ) * DISLIKED_PENALTY

        final_score = result["match_score"] + user_mention_bonus + expiring_bonus - disliked_penalty
        ranked.append({**result, "final_score": round(final_score, 4)})

    ranked.sort(key=lambda r: r["final_score"], reverse=True)
    return ranked
