"""
마스터 데이터 + 샘플 유저 시드 스크립트
실행: uv run python -m scripts.seed
"""
import asyncio
import sys
from datetime import date, timedelta

# Windows에서 psycopg3 async 사용 시 필요
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy import text

from app.db.base import Base
from app.db.models import (
    CookingHistory,
    Ingredient,
    IngredientSubstitution,
    Recipe,
    RecipeIngredient,
    RecommendationLog,
    User,
    UserFridgeItem,
    UserPreference,
)
from app.db.session import AsyncSessionLocal, engine


# ──────────────────────────────────────────────
# 1. 재료 마스터
# ──────────────────────────────────────────────
INGREDIENTS = [
    # (name, category, unit)
    ("계란",     "유제품/알류",  "개"),
    ("양파",     "채소",        "개"),
    ("참치",     "수산물",      "캔"),
    ("대파",     "채소",        "g"),
    ("마늘",     "채소",        "쪽"),
    ("두부",     "두부/콩류",   "g"),
    ("돼지고기", "육류",        "g"),
    ("닭고기",   "육류",        "g"),
    ("당근",     "채소",        "개"),
    ("감자",     "채소",        "개"),
    ("김치",     "발효식품",    "g"),
    ("밥",       "곡류",        "g"),
    ("라면",     "면류",        "개"),
    ("고추장",   "양념",        "g"),
    ("간장",     "양념",        "ml"),
    ("참기름",   "양념",        "ml"),
    ("소금",     "양념",        "g"),
    ("후추",     "양념",        "g"),
    ("식용유",   "양념",        "ml"),
    ("치즈",     "유제품/알류", "장"),
    ("햄",       "가공육",      "g"),
    ("버섯",     "채소",        "g"),
    ("시금치",   "채소",        "g"),
    ("콩나물",   "채소",        "g"),
    ("고추",     "채소",        "개"),
]

# ──────────────────────────────────────────────
# 2. 레시피 마스터
# ──────────────────────────────────────────────
RECIPES = [
    {
        "title": "계란볶음밥",
        "description": "냉장고 속 재료로 뚝딱 만드는 간단 볶음밥",
        "cooking_time": 10,
        "difficulty": "easy",
        "tool_tags": ["pan"],
        "dietary_tags": [],
        "steps": [
            {"order": 1, "instruction": "팬에 식용유를 두르고 계란을 스크램블한다."},
            {"order": 2, "instruction": "밥을 넣고 계란과 함께 볶는다."},
            {"order": 3, "instruction": "간장, 소금으로 간하고 참기름을 두른다."},
        ],
        "ingredients": [
            ("계란", 2, "개", True, False),
            ("밥", 200, "g", True, False),
            ("간장", 10, "ml", True, False),
            ("식용유", 10, "ml", True, False),
            ("참기름", 5, "ml", False, False),
            ("대파", 10, "g", False, True),
        ],
    },
    {
        "title": "참치김치찌개",
        "description": "참치와 묵은지로 끓이는 얼큰한 찌개",
        "cooking_time": 20,
        "difficulty": "easy",
        "tool_tags": ["pot"],
        "dietary_tags": [],
        "steps": [
            {"order": 1, "instruction": "냄비에 식용유를 두르고 김치를 볶는다."},
            {"order": 2, "instruction": "물 500ml를 붓고 끓인다."},
            {"order": 3, "instruction": "참치를 넣고 두부를 썰어 넣는다."},
            {"order": 4, "instruction": "소금, 고추장으로 간을 맞춘다."},
        ],
        "ingredients": [
            ("김치", 150, "g", True, False),
            ("참치", 1, "캔", True, False),
            ("두부", 100, "g", False, False),
            ("고추장", 10, "g", False, False),
            ("대파", 20, "g", False, True),
        ],
    },
    {
        "title": "김치볶음밥",
        "description": "짭조름한 김치와 햄으로 만드는 볶음밥",
        "cooking_time": 15,
        "difficulty": "easy",
        "tool_tags": ["pan"],
        "dietary_tags": [],
        "steps": [
            {"order": 1, "instruction": "팬에 식용유를 두르고 김치와 햄을 볶는다."},
            {"order": 2, "instruction": "밥을 넣고 함께 볶는다."},
            {"order": 3, "instruction": "계란 프라이를 올려 마무리한다."},
        ],
        "ingredients": [
            ("김치", 100, "g", True, False),
            ("밥", 200, "g", True, False),
            ("식용유", 10, "ml", True, False),
            ("계란", 1, "개", False, False),
            ("햄", 50, "g", False, False),
            ("참기름", 5, "ml", False, True),
        ],
    },
    {
        "title": "계란말이",
        "description": "촉촉하고 부드러운 기본 계란말이",
        "cooking_time": 10,
        "difficulty": "easy",
        "tool_tags": ["pan"],
        "dietary_tags": [],
        "steps": [
            {"order": 1, "instruction": "계란을 풀어 소금, 후추로 간한다."},
            {"order": 2, "instruction": "팬에 식용유를 두르고 계란물을 부어 천천히 말아준다."},
            {"order": 3, "instruction": "먹기 좋은 크기로 썬다."},
        ],
        "ingredients": [
            ("계란", 3, "개", True, False),
            ("식용유", 5, "ml", True, False),
            ("소금", 2, "g", True, False),
            ("후추", 1, "g", False, False),
            ("당근", 30, "g", False, False),
            ("시금치", 20, "g", False, False),
        ],
    },
    {
        "title": "두부조림",
        "description": "간장 양념으로 짭조름하게 조린 두부",
        "cooking_time": 20,
        "difficulty": "easy",
        "tool_tags": ["pan"],
        "dietary_tags": ["vegan"],
        "steps": [
            {"order": 1, "instruction": "두부를 1cm 두께로 썰어 소금을 뿌려둔다."},
            {"order": 2, "instruction": "팬에 식용유를 두르고 두부를 노릇하게 굽는다."},
            {"order": 3, "instruction": "간장, 고추장, 마늘 양념을 넣고 조린다."},
        ],
        "ingredients": [
            ("두부", 200, "g", True, False),
            ("간장", 20, "ml", True, False),
            ("마늘", 3, "쪽", True, False),
            ("식용유", 10, "ml", True, False),
            ("고추장", 5, "g", False, False),
            ("대파", 15, "g", False, True),
        ],
    },
    {
        "title": "감자조림",
        "description": "달콤짭짤한 반찬용 감자조림",
        "cooking_time": 25,
        "difficulty": "easy",
        "tool_tags": ["pot"],
        "dietary_tags": ["vegan"],
        "steps": [
            {"order": 1, "instruction": "감자를 깍둑썰기 한다."},
            {"order": 2, "instruction": "냄비에 감자, 간장, 설탕, 물을 넣고 조린다."},
            {"order": 3, "instruction": "참기름을 두르고 마무리한다."},
        ],
        "ingredients": [
            ("감자", 2, "개", True, False),
            ("간장", 30, "ml", True, False),
            ("식용유", 10, "ml", True, False),
            ("참기름", 5, "ml", False, False),
            ("마늘", 2, "쪽", False, False),
            ("고추", 1, "개", False, True),
        ],
    },
    {
        "title": "콩나물국",
        "description": "시원하고 깔끔한 해장 콩나물국",
        "cooking_time": 15,
        "difficulty": "easy",
        "tool_tags": ["pot"],
        "dietary_tags": ["vegan"],
        "steps": [
            {"order": 1, "instruction": "냄비에 물을 넣고 콩나물을 넣어 끓인다."},
            {"order": 2, "instruction": "소금, 간장으로 간을 맞춘다."},
            {"order": 3, "instruction": "대파와 마늘을 넣고 마무리한다."},
        ],
        "ingredients": [
            ("콩나물", 150, "g", True, False),
            ("소금", 3, "g", True, False),
            ("마늘", 2, "쪽", False, False),
            ("대파", 10, "g", False, True),
            ("간장", 5, "ml", False, False),
        ],
    },
    {
        "title": "버섯볶음",
        "description": "버터 없이 간장으로 볶는 담백한 버섯볶음",
        "cooking_time": 10,
        "difficulty": "easy",
        "tool_tags": ["pan"],
        "dietary_tags": ["vegan"],
        "steps": [
            {"order": 1, "instruction": "버섯을 먹기 좋은 크기로 뜯는다."},
            {"order": 2, "instruction": "팬에 식용유를 두르고 마늘을 볶다가 버섯을 넣는다."},
            {"order": 3, "instruction": "간장, 참기름으로 간하고 마무리한다."},
        ],
        "ingredients": [
            ("버섯", 150, "g", True, False),
            ("마늘", 2, "쪽", True, False),
            ("간장", 10, "ml", True, False),
            ("식용유", 10, "ml", True, False),
            ("참기름", 5, "ml", False, False),
            ("대파", 10, "g", False, True),
        ],
    },
]

# ──────────────────────────────────────────────
# 3. 대체재 매핑 (원재료명 → 대체재명)
# ──────────────────────────────────────────────
SUBSTITUTIONS = [
    # (original, substitute, ratio, note)
    ("대파",   "양파",   0.8,  "향이 달라지지만 조리 가능"),
    ("양파",   "대파",   1.2,  "단맛이 줄어들 수 있음"),
    ("돼지고기", "닭고기", 1.0, "담백한 맛으로 대체 가능"),
    ("닭고기", "돼지고기", 1.0, "좀 더 진한 맛"),
    ("햄",     "참치",   1.0,  "염분 조절 필요"),
    ("참치",   "햄",     1.0,  "풍미 차이 있음"),
    ("시금치", "콩나물",  1.0,  "식감이 달라짐"),
    ("콩나물", "시금치",  1.0,  "부드러운 식감으로 대체"),
    ("버섯",   "두부",   1.0,  "식감이 달라지지만 조리 가능"),
    ("고추장", "간장",   0.5,  "매운맛 없어짐, 간만 맞춤"),
]

# ──────────────────────────────────────────────
# 4. 샘플 유저 냉장고 재고
# ──────────────────────────────────────────────
today = date.today()
FRIDGE_ITEMS = [
    # (ingredient_name, quantity, unit, expiry_days_from_today, storage, freshness)
    ("계란",   6,   "개",  14,  "fridge",  0.95),
    ("양파",   2,   "개",  20,  "pantry",  0.90),
    ("참치",   2,   "캔",  180, "pantry",  1.00),
    ("대파",   50,  "g",   5,   "fridge",  0.70),   # 유통기한 임박
    ("마늘",   10,  "쪽",  30,  "fridge",  0.85),
    ("두부",   200, "g",   3,   "fridge",  0.60),   # 유통기한 매우 임박
    ("김치",   300, "g",   60,  "fridge",  0.95),
    ("밥",     400, "g",   1,   "fridge",  0.80),   # 오늘 남은 밥
    ("간장",   200, "ml",  365, "pantry",  1.00),
    ("참기름", 50,  "ml",  180, "pantry",  1.00),
    ("소금",   100, "g",   None, "pantry", 1.00),
    ("후추",   20,  "g",   None, "pantry", 1.00),
    ("식용유", 300, "ml",  365, "pantry",  1.00),
    ("햄",     100, "g",   7,   "fridge",  0.85),
    ("콩나물", 100, "g",   2,   "fridge",  0.65),   # 유통기한 임박
]


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        # 중복 실행 방지: users 테이블에 이미 데이터 있으면 스킵
        result = await session.execute(text("SELECT COUNT(*) FROM users"))
        if result.scalar() > 0:
            print("이미 시드 데이터가 존재합니다. 스킵합니다.")
            return

        print("시드 데이터 삽입 시작...")

        # ── 재료 마스터 ──
        ing_map: dict[str, Ingredient] = {}
        for name, category, unit in INGREDIENTS:
            ing = Ingredient(name=name, category=category, unit=unit)
            session.add(ing)
            ing_map[name] = ing
        await session.flush()
        print(f"  재료 {len(ing_map)}개 삽입")

        # ── 대체재 매핑 ──
        for orig_name, sub_name, ratio, note in SUBSTITUTIONS:
            session.add(IngredientSubstitution(
                original_ingredient_id=ing_map[orig_name].id,
                substitute_ingredient_id=ing_map[sub_name].id,
                substitution_ratio=ratio,
                note=note,
            ))
        await session.flush()
        print(f"  대체재 {len(SUBSTITUTIONS)}개 삽입")

        # ── 레시피 마스터 ──
        for r in RECIPES:
            recipe = Recipe(
                title=r["title"],
                description=r["description"],
                cooking_time=r["cooking_time"],
                difficulty=r["difficulty"],
                tool_tags=r["tool_tags"],
                dietary_tags=r["dietary_tags"],
                steps=r["steps"],
            )
            session.add(recipe)
            await session.flush()

            for ing_name, qty, unit, required, garnish in r["ingredients"]:
                session.add(RecipeIngredient(
                    recipe_id=recipe.id,
                    ingredient_id=ing_map[ing_name].id,
                    quantity=qty,
                    unit=unit,
                    is_required=required,
                    is_garnish=garnish,
                ))
        await session.flush()
        print(f"  레시피 {len(RECIPES)}개 삽입")

        # ── 샘플 유저 ──
        user = User(username="sample_user", email="sample@fridge2dish.com")
        session.add(user)
        await session.flush()
        print(f"  유저 생성 (id={user.id})")

        # ── 유저 선호 ──
        session.add(UserPreference(
            user_id=user.id,
            spice_level=2,
            disliked_ingredients=["고수"],
            allergies=[],
            dietary_tags=[],
            cooking_skill="intermediate",
        ))

        # ── 냉장고 재고 ──
        for ing_name, qty, unit, expiry_days, storage, freshness in FRIDGE_ITEMS:
            expiry = today + timedelta(days=expiry_days) if expiry_days is not None else None
            session.add(UserFridgeItem(
                user_id=user.id,
                ingredient_id=ing_map[ing_name].id,
                quantity=qty,
                unit=unit,
                expiry_date=expiry,
                storage_location=storage,
                freshness_score=freshness,
            ))

        await session.flush()
        print(f"  냉장고 재고 {len(FRIDGE_ITEMS)}개 삽입")

        await session.commit()
        print("\n시드 완료!")
        print(f"  샘플 유저 ID: {user.id}  (user_id=1 로 요청하면 됩니다)")


if __name__ == "__main__":
    asyncio.run(seed())
