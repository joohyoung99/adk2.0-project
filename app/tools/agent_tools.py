"""
LLM 에이전트가 직접 호출하는 도구 함수.
FunctionNode와 달리 tool_context 파라미터로 ADK가 자동 주입하며,
LLM이 자율적으로 호출 여부를 판단한다.
"""
import json
import os
from pathlib import Path

from google.adk.tools.tool_context import ToolContext

from app.db.repositories import recommendation_repository
from app.db.session import AsyncSessionLocal

_CATALOG_DIR = Path(os.getenv("MARKET_DATA_DIR", "./data/market_catalog"))
_CATALOG_FILES = ["emart.json", "homeplus.json", "lotte_mart.json"]


def _load_aliases() -> dict[str, list[str]]:
    p = _CATALOG_DIR / "ingredient_aliases.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _normalize(name: str, aliases: dict[str, list[str]]) -> str:
    low = name.strip().lower()
    for canonical, vals in aliases.items():
        if low == canonical.lower() or low in {v.lower() for v in vals}:
            return canonical
    return name.strip()


async def get_cooking_history(tool_context: ToolContext, limit: int = 10) -> dict:
    """최근 조리 이력을 조회한다.

    추천 전 반드시 호출해 최근에 만든 레시피를 확인하고 중복 추천을 방지하라.

    Args:
        limit: 조회할 이력 수 (기본 10)

    Returns:
        cooking_history: [{recipe_id, cooked_at, rating, liked}, ...]
    """
    user_id = tool_context.state.get("user_id")
    if not user_id:
        return {"cooking_history": []}

    async with AsyncSessionLocal() as session:
        history = await recommendation_repository.get_recent_history(
            session, user_id=int(user_id), limit=limit
        )

    tool_context.state["cooking_history"] = history
    return {"cooking_history": history}


async def get_substitutions(missing_items: list[str], tool_context: ToolContext) -> dict:
    """부족한 재료의 DB 대체재를 조회한다.

    보유 재료로 만들기 어려운 레시피의 missing 재료에 대해 호출하라.
    substitution_map이 비어있으면 DB에 대체재 없음을 의미한다.

    Args:
        missing_items: 대체재를 찾을 재료명 목록

    Returns:
        substitution_map: {재료명: [{substitute, ratio, note}, ...]}
    """
    from app.db.models.ingredient import IngredientSubstitution
    from sqlalchemy import select

    substitution_map: dict[str, list[dict]] = {}

    async with AsyncSessionLocal() as session:
        for item in missing_items:
            result = await session.execute(
                select(IngredientSubstitution)
                .join(IngredientSubstitution.original_ingredient)
                .join(IngredientSubstitution.substitute_ingredient)
                .where(IngredientSubstitution.original_ingredient.has(name=item))
            )
            rows = result.scalars().all()
            substitution_map[item] = [
                {
                    "substitute": row.substitute_ingredient.name,
                    "ratio": float(row.substitution_ratio),
                    "note": row.note,
                }
                for row in rows
            ]

    tool_context.state["substitution_map"] = substitution_map
    return {"substitution_map": substitution_map}


def compare_market_prices_for_missing(
    tool_context: ToolContext,
    missing_items: list[str] | None = None,
    recipe_title: str | None = None,
) -> dict:
    """부족 재료를 로컬 catalog에서 찾아 마트별 가격 후보를 비교한다.

    missing_items가 비어 있으면 state["missing_items"]를 사용하고,
    그래도 없으면 냉장고에 없는 사용자 요청 재료를 대신 사용한다.

    Args:
        missing_items: 구매가 필요한 재료 목록
        recipe_title: 대상 레시피명 (참고용)

    Returns:
        offers, recommended_market, warnings 포함 dict
    """
    items: list[str] = [i.strip() for i in (missing_items or []) if i and i.strip()]
    if not items:
        items = [i.strip() for i in tool_context.state.get("missing_items", []) if i and i.strip()]
    if not items:
        fridge_names = {
            item.get("ingredient_name")
            for item in tool_context.state.get("fridge_items", [])
            if item.get("quantity") is not None
        }
        seen: set[str] = set()
        for i in tool_context.state.get("ingredients", []):
            n = i.strip()
            if n and n not in fridge_names and n not in seen:
                items.append(n)
                seen.add(n)

    aliases = _load_aliases()
    offers: list[dict] = []
    catalog_missing: set[str] = set()
    preferred: list[str] = []

    for requested in items:
        canonical = _normalize(requested, aliases)
        found = False
        for filename in _CATALOG_FILES:
            path = _CATALOG_DIR / filename
            if not path.exists():
                continue
            catalog = json.loads(path.read_text(encoding="utf-8"))
            market = catalog.get("market", filename.removesuffix(".json"))
            updated_at = catalog.get("updated_at", "")
            for item in catalog.get("items", []):
                names = {item.get("canonical_ingredient", ""), *item.get("aliases", [])}
                if canonical.lower() not in {n.lower() for n in names if n}:
                    continue
                found = True
                offers.append({
                    "ingredient": requested,
                    "canonical_ingredient": item.get("canonical_ingredient", canonical),
                    "market": market,
                    "product_name": item.get("product_name", "N/A"),
                    "observed_price": item.get("price"),
                    "currency": catalog.get("currency", "KRW"),
                    "unit": item.get("unit", "N/A"),
                    "in_stock": bool(item.get("in_stock", False)),
                    "source_file": filename,
                    "updated_at": updated_at,
                    "confidence": "high",
                    "note": item.get("note"),
                })
        if not found:
            catalog_missing.add(requested)
            offers.append({
                "ingredient": requested, "canonical_ingredient": canonical,
                "market": "N/A", "product_name": "N/A", "observed_price": None,
                "currency": "KRW", "unit": "N/A", "in_stock": False,
                "source_file": "local_catalog", "updated_at": "",
                "confidence": "low", "note": "로컬 catalog 미등록",
            })

    preferred_order = {m: i for i, m in enumerate(preferred)}
    market_scores: dict[str, dict] = {}
    for o in offers:
        m = o["market"]
        if m == "N/A":
            continue
        s = market_scores.setdefault(m, {
            "market": m, "covered": set(), "in_stock": 0,
            "total": 0, "rank": preferred_order.get(m, 999),
        })
        s["covered"].add(o["ingredient"])
        if o["in_stock"]:
            s["in_stock"] += 1
        if o["observed_price"] is not None:
            s["total"] += int(o["observed_price"])

    recommended_market = None
    if market_scores:
        best = sorted(
            market_scores.values(),
            key=lambda s: (-len(s["covered"]), -s["in_stock"], s["total"], s["rank"]),
        )[0]
        recommended_market = {
            "market": best["market"],
            "reason": "로컬 catalog에서 구매 필요 재료를 가장 잘 커버합니다.",
            "covered_items": sorted(best["covered"]),
            "missing_items": sorted(catalog_missing),
            "total_estimated_price": best["total"],
            "currency": "원",
        }

    result = {
        "offers": offers,
        "recommended_market": recommended_market,
        "warnings": ["로컬 catalog 기준 가격 후보이며 실제 가격·재고·배송비와 다를 수 있음"],
    }
    tool_context.state["market_plan"] = result
    return result
