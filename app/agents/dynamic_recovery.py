"""
Dynamic Recovery — 대체재 기반 라우트 승격.
SUBSTITUTION / SHOPPING_NEEDED 상태에서 대체재를 적용해 COOK_NOW 달성을 시도한다.
"""
from google.adk import Context
from google.adk.workflow import node

from app.services.substitution_service import apply_substitutions_to_all
from app.tools.recipe_tools import get_substitutions_for_missing

MAX_ITERATIONS = 3


@node
async def dynamic_recovery(
    ctx: Context,
    best_route: str,
    fit_results: list[dict],
    fridge_items: list[dict],
) -> dict:
    """
    COOK_NOW 가 아닌 경우 대체재를 적용해 라우트 승격을 시도한다.
    이미 COOK_NOW 면 즉시 반환.
    """
    if best_route == "COOK_NOW":
        return {"best_route": best_route, "recovery_status": "SKIPPED"}

    current_route = best_route

    for _ in range(MAX_ITERATIONS):
        missing = list({
            item
            for r in fit_results
            for item in r.get("missing_required", [])
        })
        if not missing:
            break

        ctx.state["missing_items"] = missing
        await get_substitutions_for_missing(ctx, missing)

        updated = apply_substitutions_to_all(
            fit_results,
            ctx.state.get("substitution_map", {}),
            fridge_items,
        )
        ctx.state["fit_results"] = updated
        fit_results = updated

        routes = [r["route"] for r in updated]
        if "COOK_NOW" in routes:
            current_route = "COOK_NOW"
            ctx.state["best_route"] = "COOK_NOW"
            for r in updated:
                if r["route"] == "COOK_NOW":
                    ctx.state["best_recipe_id"] = r["recipe_id"]
                    break
            break
        elif "SUBSTITUTION" in routes:
            current_route = "SUBSTITUTION"
            ctx.state["best_route"] = "SUBSTITUTION"

        if current_route != "SHOPPING_NEEDED":
            break

    status = "RECOVERED" if current_route == "COOK_NOW" else "ESCALATED"
    return {"best_route": current_route, "recovery_status": status}
