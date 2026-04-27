"""Market catalog 데이터 파일 스키마 검증 및 shopping 스키마 테스트."""
import json
from pathlib import Path

import pytest

CATALOG_DIR = Path("data/market_catalog")
REQUIRED_ITEM_FIELDS = {"canonical_ingredient", "product_name", "price", "in_stock", "note"}
REQUIRED_TOP_FIELDS = {"market", "updated_at", "currency", "items"}


# ── Catalog 파일 스키마 검증 ─────────────────────────────────────

@pytest.mark.parametrize("filename", ["homeplus.json", "emart.json", "lotte_mart.json"])
def test_catalog_top_level_fields(filename):
    catalog = json.loads((CATALOG_DIR / filename).read_text(encoding="utf-8"))
    assert REQUIRED_TOP_FIELDS.issubset(catalog.keys()), f"{filename} missing fields"


@pytest.mark.parametrize("filename", ["homeplus.json", "emart.json", "lotte_mart.json"])
def test_catalog_items_have_required_fields(filename):
    catalog = json.loads((CATALOG_DIR / filename).read_text(encoding="utf-8"))
    for item in catalog["items"]:
        missing = REQUIRED_ITEM_FIELDS - item.keys()
        assert not missing, f"{filename} item '{item.get('canonical_ingredient')}' missing: {missing}"


@pytest.mark.parametrize("filename", ["homeplus.json", "emart.json", "lotte_mart.json"])
def test_catalog_prices_are_positive_or_null(filename):
    catalog = json.loads((CATALOG_DIR / filename).read_text(encoding="utf-8"))
    for item in catalog["items"]:
        if item["price"] is not None:
            assert item["price"] > 0, f"{filename}: price must be > 0"


def test_ingredient_aliases_schema():
    aliases = json.loads((CATALOG_DIR / "ingredient_aliases.json").read_text(encoding="utf-8"))
    assert isinstance(aliases, dict)
    for key, value in aliases.items():
        assert isinstance(key, str)
        assert isinstance(value, list)
        assert key in value, f"canonical '{key}' must be in its own aliases list"


# ── Shopping 스키마 import 테스트 ──────────────────────────────────

def test_shopping_schema_import():
    from app.schemas.shopping import PriceOffer, RecommendedMarket, MarketPlan  # noqa: F401
    assert True


def test_price_offer_creation():
    from app.schemas.shopping import PriceOffer
    offer = PriceOffer(
        ingredient="대파",
        canonical_ingredient="대파",
        market="Homeplus",
        product_name="국산 대파 1단",
        observed_price=2480,
        currency="KRW",
        unit="1단",
        quantity_value=1.0,
        quantity_unit="bundle",
        in_stock=True,
        source_file="homeplus.json",
        updated_at="2026-04-27",
        confidence="high",
        note="샘플 catalog 데이터",
    )
    assert offer.market == "Homeplus"
    assert offer.observed_price == 2480


def test_price_offer_null_price():
    from app.schemas.shopping import PriceOffer
    offer = PriceOffer(
        ingredient="희귀재료",
        market="Homeplus",
        product_name="N/A",
        observed_price=None,
        currency="KRW",
        unit="N/A",
        in_stock=False,
        source_file="homeplus.json",
        updated_at="2026-04-27",
        confidence="low",
    )
    assert offer.observed_price is None
    assert offer.confidence == "low"


def test_market_plan_creation():
    from app.schemas.shopping import MarketPlan, PriceOffer, RecommendedMarket
    plan = MarketPlan(
        offers=[],
        recommended_market=RecommendedMarket(
            market="Emart",
            reason="가장 많은 재료 커버",
            covered_items=["대파", "양파"],
            missing_items=[],
            total_estimated_price=4460,
            currency="KRW",
        ),
        warnings=["로컬 catalog 기준 가격 후보이며 실제 가격/재고/배송비와 다를 수 있음"],
    )
    assert plan.recommended_market.market == "Emart"
    assert len(plan.warnings) == 1
