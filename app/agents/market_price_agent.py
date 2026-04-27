"""
MarketPriceAgent — 로컬 market catalog 기반 구매처/가격 후보 비교 에이전트.
data/market_catalog/*.json 파일만 읽는다.
"""
import json
import os
from pathlib import Path

from google.adk import Agent

from app.env import load_project_env
from app.agents.prompts import MARKET_PLAN_PROMPT

load_project_env()

MARKET_DATA_DIR = os.getenv("MARKET_DATA_DIR", "./data/market_catalog")
MARKET_DATA_ABS = str(Path(MARKET_DATA_DIR).resolve())
CATALOG_FILES = ["emart.json", "homeplus.json", "lotte_mart.json"]


def _normalize_ingredient(name: str, aliases: dict[str, list[str]]) -> str:
    normalized = name.strip()
    lowered = normalized.lower()
    for canonical, values in aliases.items():
        if lowered == canonical.lower() or lowered in {v.lower() for v in values}:
            return canonical
    return normalized


def compare_market_prices(
    missing_items: list[str],
    recipe_title: str | None = None,
    preferred_markets: list[str] | None = None,
    location: str | None = None,
) -> dict:
    """Compare missing ingredients against local market catalog JSON files.

    Args:
        missing_items: 구매가 필요한 재료 목록.
        recipe_title: 대상 레시피명. 비교 로직에는 사용하지 않고 호출 맥락용으로 받는다.
        preferred_markets: 선호 마트 목록. 현재는 동점 처리에만 참고한다.
        location: 위치 정보. 로컬 catalog라 가격 계산에는 사용하지 않는다.

    Returns:
        MarketPlan 형태의 dict.
    """
    del recipe_title, location

    catalog_dir = Path(MARKET_DATA_ABS)
    aliases_path = catalog_dir / "ingredient_aliases.json"
    aliases = json.loads(aliases_path.read_text(encoding="utf-8")) if aliases_path.exists() else {}

    catalogs = []
    for filename in CATALOG_FILES:
        path = catalog_dir / filename
        if path.exists():
            catalogs.append((filename, json.loads(path.read_text(encoding="utf-8"))))

    offers: list[dict] = []
    catalog_missing: set[str] = set()
    preferred_order = {name: idx for idx, name in enumerate(preferred_markets or [])}

    for requested in missing_items:
        canonical = _normalize_ingredient(requested, aliases)
        found = False

        for filename, catalog in catalogs:
            market = catalog.get("market", filename.removesuffix(".json"))
            updated_at = catalog.get("updated_at", "")
            currency = catalog.get("currency", "KRW")

            for item in catalog.get("items", []):
                item_aliases = item.get("aliases", [])
                item_names = {
                    item.get("canonical_ingredient", ""),
                    *item_aliases,
                }
                if canonical.lower() not in {name.lower() for name in item_names if name}:
                    continue

                found = True
                offers.append({
                    "ingredient": requested,
                    "canonical_ingredient": item.get("canonical_ingredient", canonical),
                    "market": market,
                    "product_name": item.get("product_name", "N/A"),
                    "observed_price": item.get("price"),
                    "currency": currency,
                    "unit": item.get("unit", "N/A"),
                    "quantity_value": item.get("quantity_value"),
                    "quantity_unit": item.get("quantity_unit"),
                    "in_stock": bool(item.get("in_stock", False)),
                    "source_file": filename,
                    "updated_at": updated_at,
                    "confidence": "high",
                    "note": item.get("note"),
                })

        if not found:
            catalog_missing.add(requested)
            offers.append({
                "ingredient": requested,
                "canonical_ingredient": canonical,
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
            })

    market_scores: dict[str, dict] = {}
    for offer in offers:
        market = offer["market"]
        if market == "N/A":
            continue
        score = market_scores.setdefault(
            market,
            {
                "market": market,
                "covered_items": set(),
                "in_stock_count": 0,
                "total_estimated_price": 0,
                "preferred_rank": preferred_order.get(market, 999),
            },
        )
        score["covered_items"].add(offer["ingredient"])
        if offer["in_stock"]:
            score["in_stock_count"] += 1
        if offer["observed_price"] is not None:
            score["total_estimated_price"] += int(offer["observed_price"])

    recommended_market = None
    if market_scores:
        best = sorted(
            market_scores.values(),
            key=lambda s: (
                -len(s["covered_items"]),
                -s["in_stock_count"],
                s["total_estimated_price"],
                s["preferred_rank"],
            ),
        )[0]
        recommended_market = {
            "market": best["market"],
            "reason": "로컬 catalog에서 구매 필요 재료를 가장 잘 커버합니다.",
            "covered_items": sorted(best["covered_items"]),
            "missing_items": sorted(catalog_missing),
            "total_estimated_price": best["total_estimated_price"],
            "currency": "KRW",
        }
    elif catalog_missing:
        recommended_market = {
            "market": "N/A",
            "reason": "로컬 catalog에서 구매 필요 재료를 찾지 못해 추천 마트를 선정할 수 없습니다.",
            "covered_items": [],
            "missing_items": sorted(catalog_missing),
            "total_estimated_price": None,
            "currency": "KRW",
        }

    return {
        "offers": offers,
        "recommended_market": recommended_market,
        "warnings": [
            "로컬 catalog 기준 가격 후보이며 실제 가격/재고/배송비와 다를 수 있음",
            "가격이 null인 항목은 합계에서 제외됨",
        ],
    }




market_price_agent = Agent(
    name="MarketPriceAgent",
    description="부족 식재료의 로컬 catalog 기반 구매처와 가격 후보를 비교하는 에이전트.",
    model="gemini-2.5-flash",
    instruction=MARKET_PLAN_PROMPT,
    tools=[compare_market_prices],
    output_key="market_plan",
)
