from typing import Literal

from pydantic import BaseModel, Field, field_validator

RouteType = Literal["COOK_NOW", "SUBSTITUTION", "SHOPPING_NEEDED"]
MealContextType = Literal["breakfast", "lunch", "dinner", "snack", "late_night"]


class FridgeRequest(BaseModel):
    """자연어 입력에서 추출한 사용자 요청 스키마"""
    user_id: int = Field(..., ge=1, description="사용자 ID")
    ingredients: list[str] = Field(
        default_factory=list,
        description="사용자가 직접 입력한 재료 목록",
    )
    max_cooking_time: int | None = Field(
        default=None,
        ge=1,
        description="최대 조리 가능 시간(분)",
    )
    allowed_tools: list[str] = Field(
        default_factory=list,
        description="사용 가능한 조리 도구 목록. 예: pan, pot, microwave",
    )
    excluded_ingredients: list[str] = Field(
        default_factory=list,
        description="제외해야 하는 재료 목록",
    )
    meal_context: MealContextType | None = Field(
        default=None,
        description="식사 맥락. breakfast/lunch/dinner/snack/late_night",
    )





class UserPreferenceSnapshot(BaseModel):
    """사용자 선호/제약 조회 결과 스냅샷."""

    spicy_level: int = Field(default=0, ge=0, le=3)
    cooking_skill_level: int = Field(default=1, ge=1, le=3)
    preferred_cuisine: str | None = Field(default=None)
    disliked_ingredients: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    dietary_tags: list[str] = Field(default_factory=list)


class FridgeItemSnapshot(BaseModel):
    """냉장고 재고 조회 결과 스냅샷."""

    ingredient_id: int | None = Field(default=None, ge=1)
    ingredient_name: str = Field(..., description="재료명")
    quantity: float | None = Field(default=None, ge=0)
    unit: str | None = Field(default=None)
    storage_type: str | None = Field(default=None)
    freshness_score: int | None = Field(default=None, ge=1, le=5)
    expires_at: str | None = Field(
        default=None,
        description="YYYY-MM-DD 형식 날짜 문자열",
    )


class RecipeCandidate(BaseModel):
    """후보 레시피 기본 정보."""

    recipe_id: int = Field(..., ge=1)
    title: str = Field(..., description="레시피명")
    description: str | None = Field(default=None)
    cooking_time_min: int = Field(..., ge=0)
    difficulty: int = Field(..., ge=1, le=3)
    tool_tags: list[str] = Field(default_factory=list)
    dietary_tags: list[str] = Field(default_factory=list)


class SubstitutionOption(BaseModel):
    """부족 재료에 대한 대체재 정보."""

    missing: str = Field(..., description="부족한 재료")
    substitute: str = Field(..., description="대체 가능한 재료")
    note: str | None = Field(default=None, description="대체 시 참고 메모")
    substitution_ratio: float | None = Field(
        default=None,
        gt=0,
        description="대체 비율",
    )


class RecipeFitResult(BaseModel):
    """레시피 적합도 평가 결과."""

    recipe_id: int = Field(..., ge=1)
    title: str = Field(..., description="레시피명")
    match_score: float = Field(..., ge=0.0, le=1.0, description="재료 매칭 점수")
    missing_required: list[str] = Field(
        default_factory=list,
        description="부족한 필수 재료 목록",
    )
    missing_optional: list[str] = Field(
        default_factory=list,
        description="부족한 선택 재료 목록",
    )
    route: RouteType = Field(..., description="추천 분기 라벨")
    cookable_now: bool = Field(..., description="현재 재료만으로 즉시 조리 가능 여부")


class RecipeRecommendation(BaseModel):
    """최종 사용자 응답에 포함되는 추천 아이템."""

    recipe_id: int = Field(..., ge=1)
    title: str = Field(..., description="레시피명")
    status: Literal["cook_now", "substitution_needed", "shopping_needed"] = Field(
        ...,
        description="사용자 노출용 상태",
    )
    match_score: float = Field(..., ge=0.0, le=1.0)
    why_recommended: list[str] = Field(
        default_factory=list,
        description="추천 이유 목록",
    )
    missing_items: list[str] = Field(
        default_factory=list,
        description="부족 재료 목록",
    )
    substitutions: list[SubstitutionOption] = Field(
        default_factory=list,
        description="대체재 목록",
    )
    instruction_summary: str = Field(
        ...,
        description="간단 조리 요약",
    )


class RecommendationResponse(BaseModel):
    """최종 분기 에이전트가 생성하는 응답 스키마."""

    summary: str = Field(..., description="전체 추천 요약")
    decision: RouteType = Field(..., description="최종 추천 분기")
    recommendations: list[RecipeRecommendation] = Field(
        default_factory=list,
        description="추천 레시피 목록",
    )


class RecoveryLoopResult(BaseModel):
    """동적 재탐색 루프 결과."""

    status: Literal["RECOVERED", "ESCALATED", "FAILED"] = Field(
        ...,
        description="동적 루프 종료 상태",
    )
    iterations: int = Field(..., ge=1, description="반복 횟수")
    final_route: RouteType | None = Field(
        default=None,
        description="최종 라우팅 결과",
    )
    recovered_recipe_id: int | None = Field(
        default=None,
        ge=1,
        description="복구 성공한 레시피 ID",
    )