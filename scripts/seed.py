"""
마스터 데이터 + 샘플 유저 시드 스크립트
실행: uv run python -m scripts.seed

이름/제목 기준으로 중복 체크하므로 재실행해도 안전합니다.
"""
import asyncio
import sys
from datetime import date, timedelta

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy import select, text

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
    ("계란",       "유제품/알류",  "개"),
    ("양파",       "채소",        "개"),
    ("참치",       "수산물",      "캔"),
    ("대파",       "채소",        "g"),
    ("마늘",       "채소",        "쪽"),
    ("두부",       "두부/콩류",   "g"),
    ("돼지고기",   "육류",        "g"),
    ("닭고기",     "육류",        "g"),
    ("당근",       "채소",        "개"),
    ("감자",       "채소",        "개"),
    ("김치",       "발효식품",    "g"),
    ("밥",         "곡류",        "g"),
    ("라면",       "면류",        "개"),
    ("고추장",     "양념",        "g"),
    ("간장",       "양념",        "ml"),
    ("참기름",     "양념",        "ml"),
    ("소금",       "양념",        "g"),
    ("후추",       "양념",        "g"),
    ("식용유",     "양념",        "ml"),
    ("치즈",       "유제품/알류", "장"),
    ("햄",         "가공육",      "g"),
    ("버섯",       "채소",        "g"),
    ("시금치",     "채소",        "g"),
    ("콩나물",     "채소",        "g"),
    ("고추",       "채소",        "개"),
    # 추가 재료
    ("고등어",     "수산물",      "g"),
    ("무",         "채소",        "g"),
    ("소시지",     "가공육",      "g"),
    ("떡",         "곡류",        "g"),
    ("떡국떡",     "곡류",        "g"),
    ("어묵",       "수산물",      "g"),
    ("만두",       "가공식품",    "g"),
    ("황태",       "수산물",      "g"),
    ("양상추",     "채소",        "g"),
    ("오이",       "채소",        "개"),
    ("케첩",       "양념",        "g"),
    ("마요네즈",   "양념",        "g"),
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
            ("계란",   2,   "개",  True,  False),
            ("밥",     200, "g",   True,  False),
            ("간장",   10,  "ml",  True,  False),
            ("식용유", 10,  "ml",  True,  False),
            ("참기름", 5,   "ml",  False, False),
            ("대파",   10,  "g",   False, True),
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
            ("김치",   150, "g",   True,  False),
            ("참치",   1,   "캔",  True,  False),
            ("두부",   100, "g",   False, False),
            ("고추장", 10,  "g",   False, False),
            ("대파",   20,  "g",   False, True),
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
            ("김치",   100, "g",   True,  False),
            ("밥",     200, "g",   True,  False),
            ("식용유", 10,  "ml",  True,  False),
            ("계란",   1,   "개",  False, False),
            ("햄",     50,  "g",   False, False),
            ("참기름", 5,   "ml",  False, True),
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
            ("계란",   3,  "개",  True,  False),
            ("식용유", 5,  "ml",  True,  False),
            ("소금",   2,  "g",   True,  False),
            ("후추",   1,  "g",   False, False),
            ("당근",   30, "g",   False, False),
            ("시금치", 20, "g",   False, False),
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
            ("두부",   200, "g",   True,  False),
            ("간장",   20,  "ml",  True,  False),
            ("마늘",   3,   "쪽",  True,  False),
            ("식용유", 10,  "ml",  True,  False),
            ("고추장", 5,   "g",   False, False),
            ("대파",   15,  "g",   False, True),
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
            ("감자",   2,  "개",  True,  False),
            ("간장",   30, "ml",  True,  False),
            ("식용유", 10, "ml",  True,  False),
            ("참기름", 5,  "ml",  False, False),
            ("마늘",   2,  "쪽",  False, False),
            ("고추",   1,  "개",  False, True),
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
            ("콩나물", 150, "g",   True,  False),
            ("소금",   3,   "g",   True,  False),
            ("마늘",   2,   "쪽",  False, False),
            ("대파",   10,  "g",   False, True),
            ("간장",   5,   "ml",  False, False),
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
            ("버섯",   150, "g",   True,  False),
            ("마늘",   2,   "쪽",  True,  False),
            ("간장",   10,  "ml",  True,  False),
            ("식용유", 10,  "ml",  True,  False),
            ("참기름", 5,   "ml",  False, False),
            ("대파",   10,  "g",   False, True),
        ],
    },
    # ── 신규 레시피 ──
    {
        "title": "닭볶음탕",
        "description": "칼칼한 양념에 닭고기와 채소를 넣고 조리는 한국식 닭찜",
        "cooking_time": 40,
        "difficulty": "medium",
        "tool_tags": ["pot"],
        "dietary_tags": [],
        "steps": [
            {"order": 1, "instruction": "닭고기를 끓는 물에 한 번 데쳐 잡내를 제거한다."},
            {"order": 2, "instruction": "고추장, 간장, 마늘로 양념장을 만든다."},
            {"order": 3, "instruction": "냄비에 닭고기, 감자, 당근, 양파를 넣고 양념장과 함께 물 300ml를 붓는다."},
            {"order": 4, "instruction": "중불에서 30분간 뚜껑을 덮고 조린다."},
            {"order": 5, "instruction": "대파와 고추를 넣고 5분 더 끓인다."},
        ],
        "ingredients": [
            ("닭고기", 500, "g",   True,  False),
            ("감자",   2,   "개",  True,  False),
            ("고추장", 30,  "g",   True,  False),
            ("간장",   20,  "ml",  True,  False),
            ("마늘",   5,   "쪽",  True,  False),
            ("양파",   1,   "개",  False, False),
            ("당근",   1,   "개",  False, False),
            ("고추",   2,   "개",  False, False),
            ("대파",   20,  "g",   False, True),
        ],
    },
    {
        "title": "돼지고기김치찜",
        "description": "돼지고기와 김치를 함께 쪄내는 깊은 맛의 찜 요리",
        "cooking_time": 40,
        "difficulty": "medium",
        "tool_tags": ["pot"],
        "dietary_tags": [],
        "steps": [
            {"order": 1, "instruction": "돼지고기를 큼직하게 썰어 끓는 물에 데친다."},
            {"order": 2, "instruction": "냄비 바닥에 김치를 깔고 돼지고기를 올린다."},
            {"order": 3, "instruction": "마늘, 간장, 참기름을 넣고 물 200ml를 붓는다."},
            {"order": 4, "instruction": "뚜껑을 덮고 중불에서 30분간 찐다."},
            {"order": 5, "instruction": "두부를 넣고 10분 더 끓인다."},
        ],
        "ingredients": [
            ("돼지고기", 400, "g",  True,  False),
            ("김치",     300, "g",  True,  False),
            ("마늘",     4,   "쪽", True,  False),
            ("간장",     15,  "ml", False, False),
            ("참기름",   5,   "ml", False, False),
            ("두부",     150, "g",  False, False),
            ("대파",     20,  "g",  False, True),
        ],
    },
    {
        "title": "고등어조림",
        "description": "간장 양념에 무와 함께 바짝 조리는 밥도둑 반찬",
        "cooking_time": 25,
        "difficulty": "easy",
        "tool_tags": ["pan"],
        "dietary_tags": [],
        "steps": [
            {"order": 1, "instruction": "무를 0.5cm 두께로 썰어 냄비 바닥에 깐다."},
            {"order": 2, "instruction": "고등어를 토막 내 무 위에 올린다."},
            {"order": 3, "instruction": "간장, 고추장, 마늘, 물 150ml로 양념장을 만들어 붓는다."},
            {"order": 4, "instruction": "중불에서 뚜껑 덮고 15분, 뚜껑 열고 5분 조린다."},
            {"order": 5, "instruction": "대파와 고추를 올리고 마무리한다."},
        ],
        "ingredients": [
            ("고등어", 400, "g",  True,  False),
            ("무",     200, "g",  True,  False),
            ("간장",   30,  "ml", True,  False),
            ("고추장", 10,  "g",  True,  False),
            ("마늘",   3,   "쪽", True,  False),
            ("고추",   1,   "개", False, False),
            ("대파",   15,  "g",  False, True),
        ],
    },
    {
        "title": "부대찌개",
        "description": "햄, 소시지, 김치를 한 냄비에 끓이는 푸짐한 찌개",
        "cooking_time": 20,
        "difficulty": "easy",
        "tool_tags": ["pot"],
        "dietary_tags": [],
        "steps": [
            {"order": 1, "instruction": "냄비에 물 600ml를 붓고 끓인다."},
            {"order": 2, "instruction": "햄, 소시지, 김치, 두부를 넣는다."},
            {"order": 3, "instruction": "고추장을 풀고 라면 스프(있다면)로 간한다."},
            {"order": 4, "instruction": "라면 사리를 넣고 3분 더 끓인다."},
            {"order": 5, "instruction": "치즈를 올려 녹으면 완성한다."},
        ],
        "ingredients": [
            ("햄",     100, "g",  True,  False),
            ("김치",   100, "g",  True,  False),
            ("고추장", 15,  "g",  True,  False),
            ("소시지", 80,  "g",  False, False),
            ("두부",   100, "g",  False, False),
            ("라면",   1,   "개", False, False),
            ("치즈",   1,   "장", False, False),
            ("대파",   15,  "g",  False, True),
        ],
    },
    {
        "title": "떡볶이",
        "description": "매콤달콤한 고추장 소스의 국민 간식",
        "cooking_time": 20,
        "difficulty": "easy",
        "tool_tags": ["pan", "pot"],
        "dietary_tags": [],
        "steps": [
            {"order": 1, "instruction": "팬에 물 300ml를 붓고 고추장을 풀어 소스를 만든다."},
            {"order": 2, "instruction": "떡을 넣고 중불에서 끓인다."},
            {"order": 3, "instruction": "어묵을 넣고 5분 더 끓인다."},
            {"order": 4, "instruction": "양파, 대파를 넣고 소스가 걸쭉해질 때까지 졸인다."},
        ],
        "ingredients": [
            ("떡",     300, "g",  True,  False),
            ("고추장", 40,  "g",  True,  False),
            ("어묵",   100, "g",  False, False),
            ("양파",   1,   "개", False, False),
            ("계란",   1,   "개", False, False),
            ("대파",   10,  "g",  False, True),
        ],
    },
    {
        "title": "라볶이",
        "description": "떡과 라면을 함께 넣은 분식집 인기 메뉴",
        "cooking_time": 20,
        "difficulty": "easy",
        "tool_tags": ["pot"],
        "dietary_tags": [],
        "steps": [
            {"order": 1, "instruction": "냄비에 물 400ml를 붓고 고추장을 풀어 끓인다."},
            {"order": 2, "instruction": "떡을 넣고 3분간 끓인다."},
            {"order": 3, "instruction": "라면, 어묵, 양파를 넣고 3분 더 끓인다."},
            {"order": 4, "instruction": "대파를 올리고 마무리한다."},
        ],
        "ingredients": [
            ("떡",     200, "g",  True,  False),
            ("라면",   1,   "개", True,  False),
            ("고추장", 35,  "g",  True,  False),
            ("어묵",   80,  "g",  False, False),
            ("양파",   1,   "개", False, False),
            ("대파",   10,  "g",  False, True),
        ],
    },
    {
        "title": "만둣국",
        "description": "시원한 육수에 만두를 넣어 끓이는 따뜻한 국",
        "cooking_time": 15,
        "difficulty": "easy",
        "tool_tags": ["pot"],
        "dietary_tags": [],
        "steps": [
            {"order": 1, "instruction": "냄비에 물 700ml를 붓고 끓인다."},
            {"order": 2, "instruction": "만두를 넣고 만두가 떠오를 때까지 끓인다."},
            {"order": 3, "instruction": "간장, 소금으로 간을 맞춘다."},
            {"order": 4, "instruction": "풀어둔 계란을 넣고 대파를 올린다."},
        ],
        "ingredients": [
            ("만두",   300, "g",  True,  False),
            ("소금",   3,   "g",  True,  False),
            ("계란",   1,   "개", False, False),
            ("간장",   10,  "ml", False, False),
            ("대파",   15,  "g",  False, True),
        ],
    },
    {
        "title": "떡국",
        "description": "깔끔한 사골 국물에 떡국떡을 넣어 끓이는 설날 음식",
        "cooking_time": 20,
        "difficulty": "easy",
        "tool_tags": ["pot"],
        "dietary_tags": [],
        "steps": [
            {"order": 1, "instruction": "냄비에 물 700ml를 붓고 마늘을 넣어 끓인다."},
            {"order": 2, "instruction": "물에 불려둔 떡국떡을 넣고 끓인다."},
            {"order": 3, "instruction": "간장, 소금으로 간을 맞춘다."},
            {"order": 4, "instruction": "풀어둔 계란을 올리고 대파를 넣어 마무리한다."},
        ],
        "ingredients": [
            ("떡국떡", 300, "g",  True,  False),
            ("소금",   3,   "g",  True,  False),
            ("마늘",   2,   "쪽", False, False),
            ("계란",   1,   "개", False, False),
            ("간장",   10,  "ml", False, False),
            ("대파",   15,  "g",  False, True),
        ],
    },
    {
        "title": "황태해장국",
        "description": "황태와 계란으로 끓이는 시원하고 구수한 해장국",
        "cooking_time": 25,
        "difficulty": "medium",
        "tool_tags": ["pot"],
        "dietary_tags": [],
        "steps": [
            {"order": 1, "instruction": "황태를 물에 30분 불린 후 먹기 좋은 크기로 찢는다."},
            {"order": 2, "instruction": "냄비에 참기름을 두르고 마늘을 볶다가 황태를 넣어 볶는다."},
            {"order": 3, "instruction": "물 700ml를 붓고 끓인다."},
            {"order": 4, "instruction": "계란을 풀어 넣고 소금, 간장으로 간한다."},
            {"order": 5, "instruction": "대파를 넣고 마무리한다."},
        ],
        "ingredients": [
            ("황태",   100, "g",  True,  False),
            ("마늘",   3,   "쪽", True,  False),
            ("참기름", 10,  "ml", True,  False),
            ("소금",   3,   "g",  True,  False),
            ("계란",   1,   "개", False, False),
            ("간장",   5,   "ml", False, False),
            ("대파",   20,  "g",  False, True),
        ],
    },
    {
        "title": "닭가슴살샐러드",
        "description": "담백한 닭가슴살과 채소로 만드는 건강 샐러드",
        "cooking_time": 15,
        "difficulty": "easy",
        "tool_tags": ["pan"],
        "dietary_tags": ["low-calorie"],
        "steps": [
            {"order": 1, "instruction": "닭고기를 소금, 후추로 밑간해 팬에 굽는다."},
            {"order": 2, "instruction": "익힌 닭고기를 결대로 찢는다."},
            {"order": 3, "instruction": "양상추와 오이를 먹기 좋은 크기로 썬다."},
            {"order": 4, "instruction": "마요네즈와 간장을 섞어 드레싱을 만든다."},
            {"order": 5, "instruction": "모든 재료를 드레싱과 버무린다."},
        ],
        "ingredients": [
            ("닭고기",  200, "g",  True,  False),
            ("양상추",  100, "g",  True,  False),
            ("마요네즈", 20, "g",  False, False),
            ("간장",    5,   "ml", False, False),
            ("오이",    1,   "개", False, False),
            ("소금",    2,   "g",  False, False),
            ("후추",    1,   "g",  False, False),
        ],
    },
    {
        "title": "오므라이스",
        "description": "케첩 볶음밥에 계란 오믈렛을 덮은 가정식 오므라이스",
        "cooking_time": 15,
        "difficulty": "easy",
        "tool_tags": ["pan"],
        "dietary_tags": [],
        "steps": [
            {"order": 1, "instruction": "팬에 식용유를 두르고 양파와 햄을 볶는다."},
            {"order": 2, "instruction": "밥을 넣고 케첩 2큰술을 넣어 볶는다."},
            {"order": 3, "instruction": "볶음밥을 그릇에 담아 반원형으로 만든다."},
            {"order": 4, "instruction": "계란 2개를 풀어 얇은 오믈렛을 만들어 볶음밥 위에 덮는다."},
            {"order": 5, "instruction": "케첩을 뿌려 마무리한다."},
        ],
        "ingredients": [
            ("계란",   2,   "개",  True,  False),
            ("밥",     200, "g",   True,  False),
            ("케첩",   30,  "g",   True,  False),
            ("식용유", 10,  "ml",  True,  False),
            ("양파",   1,   "개",  False, False),
            ("햄",     50,  "g",   False, False),
        ],
    },
]

# ──────────────────────────────────────────────
# 3. 대체재 매핑
# ──────────────────────────────────────────────
SUBSTITUTIONS = [
    # (original, substitute, ratio, note)
    ("대파",     "양파",     0.8,  "향이 달라지지만 조리 가능"),
    ("양파",     "대파",     1.2,  "단맛이 줄어들 수 있음"),
    ("돼지고기", "닭고기",   1.0,  "담백한 맛으로 대체 가능"),
    ("닭고기",   "돼지고기", 1.0,  "좀 더 진한 맛"),
    ("햄",       "참치",     1.0,  "염분 조절 필요"),
    ("참치",     "햄",       1.0,  "풍미 차이 있음"),
    ("시금치",   "콩나물",   1.0,  "식감이 달라짐"),
    ("콩나물",   "시금치",   1.0,  "부드러운 식감으로 대체"),
    ("버섯",     "두부",     1.0,  "식감이 달라지지만 조리 가능"),
    ("고추장",   "간장",     0.5,  "매운맛 없어짐, 간만 맞춤"),
    ("소시지",   "햄",       1.0,  "햄으로 대체 가능"),
    ("햄",       "소시지",   1.0,  "소시지로 대체 가능"),
    ("어묵",     "두부",     1.0,  "식감 차이 있음"),
    ("떡",       "떡국떡",   1.0,  "모양이 다를 뿐 조리 가능"),
    ("떡국떡",   "떡",       1.0,  "모양이 다를 뿐 조리 가능"),
    ("마요네즈", "간장",     0.5,  "드레싱 풍미 달라짐"),
    ("케첩",     "고추장",   0.7,  "매운맛 추가됨, 단맛 줄어듦"),
    ("양상추",   "시금치",   1.0,  "시금치로 대체 가능"),
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
        print("시드 데이터 삽입 시작...")

        # ── 재료 마스터 (이름 기준 중복 스킵) ──
        existing_ing = {
            row[0]
            for row in (await session.execute(select(Ingredient.name))).all()
        }
        ing_map: dict[str, Ingredient] = {
            row[0]: row[1]
            for row in (
                await session.execute(select(Ingredient.name, Ingredient))
            ).all()
        }
        new_ing_count = 0
        for name, category, unit in INGREDIENTS:
            if name not in existing_ing:
                ing = Ingredient(name=name, category=category, unit=unit)
                session.add(ing)
                ing_map[name] = ing
                new_ing_count += 1
        await session.flush()
        print(f"  재료 {new_ing_count}개 추가 (기존 {len(existing_ing)}개)")

        # ── 대체재 매핑 (중복 스킵) ──
        existing_subs = set(
            (row[0], row[1])
            for row in (
                await session.execute(
                    select(
                        IngredientSubstitution.original_ingredient_id,
                        IngredientSubstitution.substitute_ingredient_id,
                    )
                )
            ).all()
        )
        new_sub_count = 0
        for orig_name, sub_name, ratio, note in SUBSTITUTIONS:
            orig_id = ing_map[orig_name].id
            sub_id = ing_map[sub_name].id
            if (orig_id, sub_id) not in existing_subs:
                session.add(IngredientSubstitution(
                    original_ingredient_id=orig_id,
                    substitute_ingredient_id=sub_id,
                    substitution_ratio=ratio,
                    note=note,
                ))
                new_sub_count += 1
        await session.flush()
        print(f"  대체재 {new_sub_count}개 추가")

        # ── 레시피 마스터 (제목 기준 중복 스킵) ──
        existing_recipes = {
            row[0]
            for row in (await session.execute(select(Recipe.title))).all()
        }
        new_recipe_count = 0
        for r in RECIPES:
            if r["title"] in existing_recipes:
                continue
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
            new_recipe_count += 1
        await session.flush()
        print(f"  레시피 {new_recipe_count}개 추가 (기존 {len(existing_recipes)}개)")

        # ── 샘플 유저 (username 기준 중복 스킵) ──
        existing_user = (
            await session.execute(
                select(User).where(User.username == "sample_user")
            )
        ).scalar_one_or_none()

        if existing_user:
            print(f"  샘플 유저 이미 존재 (id={existing_user.id}), 냉장고 재고 스킵")
        else:
            user = User(username="sample_user", email="sample@fridge2dish.com")
            session.add(user)
            await session.flush()
            print(f"  유저 생성 (id={user.id})")

            session.add(UserPreference(
                user_id=user.id,
                spice_level=2,
                disliked_ingredients=["고수"],
                allergies=[],
                dietary_tags=[],
                cooking_skill="intermediate",
            ))

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


if __name__ == "__main__":
    asyncio.run(seed())
