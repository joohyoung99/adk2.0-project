from typing import Optional
from pydantic import BaseModel


class PriceOffer(BaseModel):
    ingredient: str
    canonical_ingredient: Optional[str] = None
    market: str
    product_name: str
    observed_price: Optional[int] = None
    currency: str = "KRW"
    unit: str
    quantity_value: Optional[float] = None
    quantity_unit: Optional[str] = None
    in_stock: bool
    source_file: str
    updated_at: str
    confidence: str  # "high" | "medium" | "low"
    note: Optional[str] = None


class RecommendedMarket(BaseModel):
    market: str
    reason: str
    covered_items: list[str]
    missing_items: list[str]
    total_estimated_price: Optional[int] = None
    currency: str = "KRW"


class MarketPlan(BaseModel):
    offers: list[PriceOffer]
    recommended_market: Optional[RecommendedMarket] = None
    warnings: list[str]
