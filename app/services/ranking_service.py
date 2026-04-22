"""
레시피 후보 랭킹 서비스.
DB 호출 없는 순수 계산 — 매칭 점수에 유통기한·선호 보정을 더해 재정렬한다.
"""

EXPIRING_BONUS = 0.10   # 유통기한 임박 재료 1개당 보너스
DISLIKED_PENALTY = 0.05  # 비선호 재료 1개당 페널티


def rank_candidates(
    fit_results: list[dict],
    expiring_items: list[dict],
    preferences: dict,
) -> list[dict]:
    """
    fit_results 를 최종 점수 기준으로 내림차순 정렬해 반환한다.

    최종점수 = match_score
             + 유통기한 임박 재료 사용 수 * EXPIRING_BONUS
             - 비선호 재료 포함 수 * DISLIKED_PENALTY
    """
    expiring_names: set[str] = {i["ingredient_name"] for i in expiring_items}
    disliked_names: set[str] = set(preferences.get("disliked_ingredients", []))

    ranked = []
    for result in fit_results:
        # 레시피에 사용된 재료 = 부족한 것 + 보유한 것(missing 제외하면 보유)
        # missing 목록에 없으면 보유 중 → expiring 교집합으로 보너스 산출
        missing_all = set(result.get("missing_required", []) + result.get("missing_optional", []))

        # 실제로 사용되는 재료 이름을 알 방법이 없으므로
        # "보유 재료 중 유통기한 임박"은 fridge_items 전체와 expiring 교집합으로 근사
        expiring_bonus = len(expiring_names - missing_all) * EXPIRING_BONUS

        disliked_penalty = len(
            disliked_names & missing_all  # 비선호인데 레시피에 필요한 재료
        ) * DISLIKED_PENALTY

        final_score = result["match_score"] + expiring_bonus - disliked_penalty
        ranked.append({**result, "final_score": round(final_score, 4)})

    ranked.sort(key=lambda r: r["final_score"], reverse=True)
    return ranked
