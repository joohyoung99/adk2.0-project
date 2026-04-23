"""
Root Workflow — 전체 파이프라인 조립.

직렬 흐름:
  START
  → input_extractor (LLM)
  → unpack_request  (@node)
  → parse_input     (@node)
  → load_context    (@node)
  → merge_fridge    (@node)
  → search_recipes  (@node)
  → evaluate_fit    (@node)
  → rank_candidates (@node)
  → dynamic_recovery(@node)  ← 대체재로 COOK_NOW 승격 시도
  → fit_router      (@node)  ← ctx.route 세팅
      ├─ COOK_NOW        → cook_now_agent    (LLM + google_search)
      ├─ SUBSTITUTION    → substitution_agent(LLM + google_search)
      └─ SHOPPING_NEEDED → shopping_agent   (LLM + google_search)
  → save_log        (@node)
  → image_search    (LLM + google_search)
  END
"""
from google.adk import Context
from google.adk.workflow import START, Workflow, node

from app.agents.branch_agents import (
    cook_now_agent,
    image_search_agent,
    shopping_agent,
    substitution_agent,
)
from app.agents.dynamic_recovery import dynamic_recovery
from app.agents.extractor_agent import input_extractor, parse_input, unpack_request
from app.services.ranking_service import rank_candidates as _rank_fn
from app.tools.fridge_tools import load_user_context, merge_input_with_fridge
from app.tools.history_tools import save_recommendation_log
from app.tools.recipe_tools import evaluate_recipe_fit, search_candidate_recipes


@node
def fit_router(best_route: str, ctx: Context) -> None:
    """state["best_route"] 값을 ctx.route 에 세팅해 분기 Edge를 활성화한다."""
    ctx.route = best_route


@node(name="rank_candidates")
def rank_candidates_fn(
    fit_results: list[dict],
    expiring_items: list[dict],
    preferences: dict,
    fridge_items: list[dict],
    ctx: Context,
) -> dict:
    """ranking_service 를 노드로 래핑. 재정렬된 fit_results 를 덮어쓴다."""
    ranked = _rank_fn(fit_results, expiring_items, preferences, fridge_items)
    ctx.state["fit_results"] = ranked
    return {"fit_results": ranked}


# ── Root Workflow ─────────────────────────────────────────────
root_workflow = Workflow(
    name="Fridge2DishWorkflow",
    edges=[
        # 직렬 흐름
        (START,                  input_extractor),
        (input_extractor,        unpack_request),
        (unpack_request,         parse_input),
        (parse_input,            load_user_context),
        (load_user_context,      merge_input_with_fridge),
        (merge_input_with_fridge, search_candidate_recipes),
        (search_candidate_recipes, evaluate_recipe_fit),
        (evaluate_recipe_fit,    rank_candidates_fn),
        (rank_candidates_fn,     dynamic_recovery),
        (dynamic_recovery,       fit_router),

        # 조건부 분기
        (fit_router, {
            "COOK_NOW":        cook_now_agent,
            "SUBSTITUTION":    substitution_agent,
            "SHOPPING_NEEDED": shopping_agent,
        }),

        # 분기 후 로그 저장
        (cook_now_agent,     save_recommendation_log),
        (substitution_agent, save_recommendation_log),
        (shopping_agent,     save_recommendation_log),

        # 레시피 이미지 찾아오기
        (save_recommendation_log, image_search_agent),
    ],
)
