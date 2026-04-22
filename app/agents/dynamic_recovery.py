"""
Dynamic Workflow — 대체재 재탐색 루프.
SUBSTITUTION / SHOPPING_NEEDED 상태에서 최대 3회 반복해
COOK_NOW 달성을 시도한다.
"""
from typing import Any, AsyncGenerator

from google.adk import Context
from google.adk.workflow import BaseNode, FunctionNode

from app.services.substitution_service import apply_substitutions_to_all
from app.tools.recipe_tools import (
    evaluate_recipe_fit,
    get_substitutions_for_missing,
    search_candidate_recipes,
)

# Dynamic Recovery 내부에서 사용하는 FunctionNode 인스턴스
_search_node = FunctionNode(search_candidate_recipes, name="recovery_search")
_evaluate_node = FunctionNode(evaluate_recipe_fit, name="recovery_evaluate")
_subs_node = FunctionNode(get_substitutions_for_missing, name="recovery_substitutions")


class RecipeRecoveryWorkflow(BaseNode):
    """
    재료 부족 시 대체재를 적용하며 COOK_NOW 달성을 반복 시도하는 동적 워크플로우.

    루프 흐름:
      1. 후보 레시피 재탐색
      2. 매칭 점수 재평가
      3. COOK_NOW 달성 시 즉시 종료
      4. 부족 재료 기반 대체재 조회
      5. 대체재 적용 후 state 갱신
      6. 최대 MAX_ITERATIONS 회 반복
    """

    MAX_ITERATIONS: int = 3

    async def _run_impl(
        self, *, ctx: Context, node_input: Any
    ) -> AsyncGenerator[Any, None]:
        final_route = ctx.state.get("best_route", "SHOPPING_NEEDED")
        iterations = 0

        for i in range(self.MAX_ITERATIONS):
            iterations = i + 1

            # 1. 후보 재탐색
            await ctx.run_node(_search_node)

            # 2. 매칭 재평가
            await ctx.run_node(_evaluate_node)

            final_route = ctx.state.get("best_route", "SHOPPING_NEEDED")

            # 3. COOK_NOW 달성 시 종료
            if final_route == "COOK_NOW":
                break

            # 4. 부족 재료 대체재 조회
            missing = []
            for r in ctx.state.get("fit_results", []):
                missing.extend(r.get("missing_required", []))
            ctx.state["missing_items"] = list(set(missing))

            await ctx.run_node(_subs_node)

            # 5. 대체재 적용 후 fit_results 갱신
            updated = apply_substitutions_to_all(
                ctx.state.get("fit_results", []),
                ctx.state.get("substitution_map", {}),
                ctx.state.get("fridge_items", []),
            )
            ctx.state["fit_results"] = updated

            # 재평가된 best_route 반영
            if updated:
                routes = [r["route"] for r in updated]
                if "COOK_NOW" in routes:
                    final_route = "COOK_NOW"
                    ctx.state["best_route"] = "COOK_NOW"
                    break
                elif "SUBSTITUTION" in routes:
                    final_route = "SUBSTITUTION"
                    ctx.state["best_route"] = "SUBSTITUTION"

        status = "RECOVERED" if final_route == "COOK_NOW" else "ESCALATED"
        yield {
            "status": status,
            "iterations": iterations,
            "final_route": final_route,
        }
