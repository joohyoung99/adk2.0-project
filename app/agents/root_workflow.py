"""
Root Workflow — 전체 파이프라인 조립.

직렬 흐름:
  START
  → input_extractor (LLM)
  → unpack_request  (Function)
  → parse_input     (Function)
  → load_context    (Function)
  → merge_fridge    (Function)
  → search_recipes  (Function)
  → evaluate_fit    (Function)
  → rank_candidates (Function)
  → fit_router      (Function)  ← ctx.route 세팅
      ├─ COOK_NOW        → cook_now_agent    (LLM + google_search)
      ├─ SUBSTITUTION    → substitution_agent(LLM + google_search)
      └─ SHOPPING_NEEDED → shopping_agent   (LLM + google_search)
  → save_log        (Function)
  END
"""
from google.adk import Context
from google.adk.workflow import Edge, FunctionNode, START, Workflow

from app.agents.branch_agents import cook_now_agent, shopping_agent, substitution_agent
from app.agents.extractor_agent import input_extractor, parse_input, unpack_request
from app.services.ranking_service import rank_candidates as _rank_fn
from app.tools.fridge_tools import load_user_context, merge_input_with_fridge
from app.tools.history_tools import save_recommendation_log
from app.tools.recipe_tools import evaluate_recipe_fit, search_candidate_recipes


# ── 라우터 함수 ──────────────────────────────────────────────
def fit_router(best_route: str, ctx: Context) -> None:
    """state["best_route"] 값을 ctx.route 에 세팅해 분기 Edge를 활성화한다."""
    ctx.route = best_route


# ── 랭킹 래퍼 (services → FunctionNode 용) ───────────────────
def rank_candidates_fn(
    fit_results: list[dict],
    expiring_items: list[dict],
    preferences: dict,
) -> dict:
    """ranking_service 를 FunctionNode 로 래핑. 재정렬된 fit_results 를 덮어쓴다."""
    ranked = _rank_fn(fit_results, expiring_items, preferences)
    return {"fit_results": ranked}


# ── FunctionNode 인스턴스 ─────────────────────────────────────
unpack_node = FunctionNode(unpack_request,            name="unpack_request")
parse_node = FunctionNode(parse_input,                name="parse_input")
load_context_node = FunctionNode(load_user_context,   name="load_user_context")
merge_fridge_node = FunctionNode(merge_input_with_fridge, name="merge_fridge")
search_node = FunctionNode(search_candidate_recipes,  name="search_candidate_recipes")
evaluate_node = FunctionNode(evaluate_recipe_fit,     name="evaluate_recipe_fit")
rank_node = FunctionNode(rank_candidates_fn,          name="rank_candidates")
router_node = FunctionNode(fit_router,                name="fit_router")
save_log_node = FunctionNode(save_recommendation_log, name="save_recommendation_log")


# ── Root Workflow ─────────────────────────────────────────────
root_workflow = Workflow(
    name="Fridge2DishWorkflow",
    edges=[
        # 직렬 흐름
        (START,              input_extractor),
        (input_extractor,    unpack_node),
        (unpack_node,        parse_node),
        (parse_node,         load_context_node),
        (load_context_node,  merge_fridge_node),
        (merge_fridge_node,  search_node),
        (search_node,        evaluate_node),
        (evaluate_node,      rank_node),
        (rank_node,          router_node),

        # 조건부 분기 — 튜플 딕셔너리 형식 (Agent 는 BaseNode 가 아니므로 Edge 불가)
        (router_node, {
            "COOK_NOW":        cook_now_agent,
            "SUBSTITUTION":    substitution_agent,
            "SHOPPING_NEEDED": shopping_agent,
        }),

        # 분기 후 로그 저장
        (cook_now_agent,     save_log_node),
        (substitution_agent, save_log_node),
        (shopping_agent,     save_log_node),
    ],
)
