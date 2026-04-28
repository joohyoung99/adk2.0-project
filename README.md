# 냉털쉐프 — 냉장고 기반 레시피 추천 멀티에이전트 시스템

**Google ADK 2.0** 기반의 냉장고 재고 조회 → 레시피 추천 → 마트 가격 비교까지 이어지는 멀티에이전트 파이프라인입니다.

ADK 2.0의 세 가지 핵심 패턴을 하나의 시스템에서 구현합니다.

| 패턴 | 역할 |
|------|------|
| **Graph-based Workflow** | 전체 파이프라인 직렬 흐름 |
| **Conditional Routing** | 재고 상태별 분기 (COOK_NOW / SUBSTITUTION / SHOPPING_NEEDED) |
| **Dynamic Recovery** | 대체재 탐색 + 루트 승격 루프 (최대 3회) |

---

## 목차

1. [시스템 개요](#시스템-개요)
2. [전체 아키텍처](#전체-아키텍처)
3. [핵심 에이전트 구성](#핵심-에이전트-구성)
4. [Dynamic Recovery 루프](#dynamic-recovery-루프)
5. [A2A + Filesystem MCP 확장](#a2a--filesystem-mcp-확장)
6. [랭킹 보정 로직](#랭킹-보정-로직)
7. [디렉토리 구조](#디렉토리-구조)
8. [데이터베이스 스키마](#데이터베이스-스키마)
9. [환경 설정 및 실행](#환경-설정-및-실행)
10. [주요 Pydantic 스키마](#주요-pydantic-스키마)

---

## 시스템 개요

사용자가 `"계란이랑 양파 있는데 점심 뭐 해먹지?"` 같은 자연어를 입력하면:

1. **LLM Extractor**가 재료·조리 시간·도구 등을 구조화된 스키마로 파싱
2. **PostgreSQL**에서 냉장고 재고·선호도·유통기한을 조회
3. **DB 후보 레시피** 탐색 → 매칭 점수 계산 → 랭킹 보정
4. 보유 재료 상태에 따라 **3가지 분기**로 최종 레시피 생성
5. 장보기가 필요하면 **A2A → MCP**를 통해 로컬 마트 catalog 가격 비교

---

## 전체 아키텍처

### 메인 워크플로우 (`Fridge2DishWorkflow`)

```mermaid
flowchart TD
    START([▶ START]) --> EX

    subgraph LLM_EXTRACT["LLM Node"]
        EX["input_extractor\ngemini-2.5-flash\n자연어 → FridgeRequest"]
    end

    subgraph PREP["Function Nodes — 전처리"]
        UN["unpack_request\nfridge_request → state 키 승격"]
        PA["parse_input\n도구명 정규화 · 빈값 보정"]
    end

    subgraph DB_LOAD["Function Nodes — DB 조회"]
        LC["load_user_context\nPostgreSQL\n냉장고 재고 · 선호 · 유통기한"]
        MF["merge_input_with_fridge\n사용자 언급 재료 + 냉장고 병합"]
    end

    subgraph EVAL["Function Nodes — 평가"]
        SR["search_candidate_recipes\nDB 후보 레시피 탐색"]
        EF["evaluate_recipe_fit\nmatch_score 계산 + route 결정"]
        RC["rank_candidates\n최종점수 = match_score + 보정값"]
    end

    subgraph DYNAMIC["Dynamic Node — 대체재 루프"]
        DR["dynamic_recovery\n대체재 탐색 · 루트 승격 max 3회"]
    end

    subgraph ROUTE["Function Node — 분기"]
        FR["fit_router\nctx.route 세팅"]
    end

    EX --> UN --> PA --> LC --> MF --> SR --> EF --> RC --> DR --> FR

    subgraph BRANCH["LLM Branch Agents — gemini-2.5-flash"]
        CN["CookNowAgent\n보유 재료만으로\n즉시 조리 가능 레시피"]
        SA["SubstitutionAgent\n대체재 포함\n조리 가능 레시피"]
        SH["ShoppingAgent\n장보기 목록 +\n완성 레시피 + 마트 가격"]
    end

    FR -->|COOK_NOW| CN
    FR -->|SUBSTITUTION| SA
    FR -->|SHOPPING_NEEDED| SH

    CN & SA & SH --> LOG["save_recommendation_log\n결과 DB 저장"]
    LOG --> END([■ END])

    style LLM_EXTRACT fill:#dbeafe,stroke:#3b82f6
    style PREP fill:#f0fdf4,stroke:#22c55e
    style DB_LOAD fill:#fef9c3,stroke:#eab308
    style EVAL fill:#fff7ed,stroke:#f97316
    style DYNAMIC fill:#fdf2f8,stroke:#a855f7
    style ROUTE fill:#f0f9ff,stroke:#0ea5e9
    style BRANCH fill:#dbeafe,stroke:#3b82f6
```

### 분기 결정 기준

| Route | 조건 |
|-------|------|
| `COOK_NOW` | 부족한 필수 재료 없음 |
| `SUBSTITUTION` | 부족 재료 있음, DB 대체재 존재 |
| `SHOPPING_NEEDED` | 대체재로도 해결 불가 |
| *(폴백)* | DB 후보 없을 때: 재료 5개↑→COOK_NOW, 3개↑→SUBSTITUTION, 미만→SHOPPING |

---

## 핵심 에이전트 구성

| 에이전트 | 타입 | 모델 | 역할 |
|---------|------|------|------|
| `FridgeRequestExtractor` | LLM Node | gemini-2.5-flash | 자연어 → FridgeRequest (output_schema) |
| `CookNowAgent` | LLM Node | gemini-2.5-flash | 즉시 조리 레시피 생성 |
| `SubstitutionAgent` | LLM Node | gemini-2.5-flash | 대체재 포함 레시피 생성 |
| `ShoppingAgent` | LLM Node | gemini-2.5-flash | 장보기 목록 + 레시피 + 마트 가격 |
| `MarketPriceAgent` | LLM Node | gemini-2.5-flash | Filesystem MCP로 catalog 조회 |

> `output_schema=FridgeRequest`는 Pydantic BaseModel 서브클래스만 유효합니다.
> 단순 텍스트 응답은 `output_schema` 없이 `output_key`만 사용합니다.

---

## Dynamic Recovery 루프

`COOK_NOW`가 아닌 경우, `dynamic_recovery` 노드가 최대 3회 루프를 돌며 루트 승격을 시도합니다.

```mermaid
flowchart TD
    ENTER["dynamic_recovery 진입"] --> CHK{"best_route\n== COOK_NOW?"}
    CHK -->|예| SKIP["즉시 반환\nrecovery_status: SKIPPED"]

    CHK -->|아니오| EXT["부족 재료 추출\nmissing_required 합집합"]
    EXT --> SUB["DB 대체재 조회\nget_substitutions_for_missing"]
    SUB --> APPLY["대체재 적용 시뮬레이션\napply_substitutions_to_all"]
    APPLY --> REEVAL{"route 재평가"}

    REEVAL -->|COOK_NOW 존재| PROMOTE["best_route = COOK_NOW\nbest_recipe_id 갱신"]
    REEVAL -->|SUBSTITUTION 존재| PARTIAL["best_route = SUBSTITUTION"]
    REEVAL -->|여전히 SHOPPING| ITER{"반복 횟수\n< 3?"}

    ITER -->|예| EXT
    ITER -->|아니오| FINAL["현재 route 확정"]

    PROMOTE --> DONE_R["반환\nrecovery_status: RECOVERED"]
    PARTIAL --> DONE_E["반환\nrecovery_status: ESCALATED"]
    FINAL --> DONE_E

    style PROMOTE fill:#dcfce7,stroke:#16a34a
    style DONE_R fill:#dcfce7,stroke:#16a34a
```

---

## A2A + Filesystem MCP 확장

`SHOPPING_NEEDED` 분기에서 `ShoppingAgent`가 **A2A 프로토콜**로 `MarketPriceAgent`에게 가격 비교를 위임합니다.

### 호출 흐름

```mermaid
flowchart LR
    SH["ShoppingAgent\n(LLM Agent)\ngemini-2.5-flash\n:8000"] 

    subgraph A2A["A2A Protocol (HTTP)"]
        RA["RemoteA2aAgent\n(market_price_remote_agent)\nhttp://localhost:8001"]
    end

    subgraph MCA["MarketPriceAgent A2A Server\n(FastAPI / to_a2a)\nport 8001"]
        MA["MarketPriceAgent\n(LLM Agent)\ngemini-2.5-flash"]
    end

    subgraph MCP["Filesystem MCP (stdio)"]
        FS["npx @modelcontextprotocol/\nserver-filesystem\nread-only"]
    end

    subgraph CAT["data/market_catalog/"]
        HP["homeplus.json"]
        EM["emart.json"]
        LM["lotte_mart.json"]
        IA["ingredient_aliases.json"]
    end

    SH -->|sub_agents| RA
    RA -->|HTTP| MCA
    MA -->|McpToolset\nstdio| FS
    FS -->|read_file\nlist_directory| CAT

    style A2A fill:#eff6ff,stroke:#3b82f6
    style MCA fill:#f0fdf4,stroke:#22c55e
    style MCP fill:#fdf2f8,stroke:#a855f7
    style CAT fill:#fef9c3,stroke:#eab308
```

### MCP 도구 필터 (read-only)

| 허용 | 차단 |
|------|------|
| `read_file` | `write_file` |
| `read_multiple_files` | `edit_file` |
| `list_directory` | `create_directory` |
| `directory_tree` | `move_file` |
| `search_files` | `delete_file` |
| `list_allowed_directories` | |

### market_catalog 파일 형식

```json
{
  "market": "Homeplus",
  "updated_at": "2026-04-27",
  "currency": "KRW",
  "items": [
    {
      "canonical_ingredient": "계란",
      "aliases": ["계란", "달걀", "egg"],
      "product_name": "신선란 10구",
      "unit": "10구",
      "price": 3490,
      "in_stock": true
    }
  ]
}
```

새 마트 추가: 동일 스키마의 JSON 파일을 `data/market_catalog/`에 추가하면 자동 인식됩니다.

---

## 랭킹 보정 로직

`rank_candidates` 노드는 `ranking_service.py`의 순수 계산 함수를 호출합니다.

```
최종점수 = match_score
         + 사용자 직접 언급 재료 수 × 0.12   (USER_MENTION_BONUS)
         + 유통기한 임박 재료 사용 수 × 0.10  (EXPIRING_BONUS)
         - 비선호 재료 포함 수 × 0.05         (DISLIKED_PENALTY)
```

사용자가 명시한 재료(+0.12)가 유통기한 임박(+0.10)보다 우선 반영됩니다.

---

## 디렉토리 구조

```
adk2.0-project/
├── app/
│   ├── agents/
│   │   ├── extractor_agent.py     # input_extractor, unpack_request, parse_input
│   │   ├── branch_agents.py       # CookNowAgent / SubstitutionAgent / ShoppingAgent
│   │   ├── dynamic_recovery.py    # dynamic_recovery @node (대체재 루프)
│   │   ├── root_workflow.py       # Fridge2DishWorkflow 조립
│   │   ├── market_price_agent.py  # MarketPriceAgent (McpToolset)
│   │   ├── market_a2a_app.py      # A2A 서버 진입점 (port 8001)
│   │   ├── remote_agents.py       # RemoteA2aAgent 인스턴스
│   │   └── prompts.py             # 프롬프트 상수 모음
│   ├── api/
│   │   ├── chat.py                # POST /api/chat
│   │   └── fridge.py              # GET /api/fridge/{user_id}
│   ├── db/
│   │   ├── models/                # SQLAlchemy ORM 모델
│   │   └── repositories/         # DB 접근 레포지터리
│   ├── schemas/
│   │   ├── agent_io.py            # FridgeRequest, RecipeFitResult 등
│   │   └── shopping.py            # PriceOffer 스키마
│   ├── services/
│   │   ├── ranking_service.py     # 순수 함수 랭킹 계산
│   │   ├── substitution_service.py
│   │   └── response_formatter.py
│   ├── tools/
│   │   ├── fridge_tools.py        # load_user_context, merge_input_with_fridge
│   │   ├── recipe_tools.py        # search_candidate_recipes, evaluate_recipe_fit
│   │   ├── history_tools.py       # save_recommendation_log
│   │   └── agent_tools.py         # LLM Agent용 Tool 함수
│   ├── web.py                     # FastAPI + Jinja2 Web UI (port 8000)
│   ├── main.py                    # CLI 진입점
│   └── env.py                     # .env 로드 유틸
├── data/
│   └── market_catalog/
│       ├── homeplus.json
│       ├── emart.json
│       ├── lotte_mart.json
│       └── ingredient_aliases.json
├── scripts/
│   ├── schema.sql                 # DB 스키마 정의
│   └── seed.py                    # 시드 데이터 투입
├── tests/
├── .env                           # 환경변수 (커밋 금지)
├── pyproject.toml
└── CLAUDE.md
```

---

## 데이터베이스 스키마

```mermaid
erDiagram
    users ||--o{ user_preferences : has
    users ||--o{ user_fridge_items : owns
    users ||--o{ recommendation_logs : generates
    users ||--o{ cooking_history : records

    ingredients ||--o{ user_fridge_items : stored_as
    ingredients ||--o{ recipe_ingredients : used_in
    ingredients ||--o{ ingredient_substitutions : original
    ingredients ||--o{ ingredient_substitutions : substitute

    recipes ||--o{ recipe_ingredients : requires
    recipes ||--o{ recommendation_logs : recommended_in
    recipes ||--o{ cooking_history : cooked_as

    users {
        int id PK
        string name
    }
    user_preferences {
        int user_id FK
        int spicy_level
        int cooking_skill_level
        string preferred_cuisine
        json disliked_ingredients
        json allergies
        json dietary_tags
    }
    user_fridge_items {
        int user_id FK
        int ingredient_id FK
        float quantity
        string unit
        date expires_at
        string storage_type
        int freshness_score
    }
    recipes {
        int id PK
        string title
        int cooking_time_min
        int difficulty
        json tool_tags
        json dietary_tags
        json steps
    }
    ingredient_substitutions {
        int original_id FK
        int substitute_id FK
        float ratio
        string note
    }
```

---

## 환경 설정 및 실행

### 필수 환경변수 (`.env`)

```env
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/dbname
GOOGLE_API_KEY=your_google_api_key_here
MARKET_A2A_URL=http://localhost:8001
MARKET_A2A_PORT=8001
MARKET_DATA_DIR=./data/market_catalog
ADK_SESSION_BACKEND=memory
```

### 의존성 설치

```bash
uv sync
```

Node.js v18 이상이 필요합니다 (Filesystem MCP 서버용).

```bash
node --version   # v18+
npx --version
```

### DB 초기화

```bash
# 스키마 적용 후 시드 데이터 투입
uv run python scripts/seed.py
```

### 실행 순서

**터미널 1 — MarketPriceAgent A2A 서버**

```bash
uv run uvicorn app.agents.market_a2a_app:app --port 8001
```

Agent Card 확인:

```bash
curl http://localhost:8001/.well-known/agent-card.json
```

**터미널 2 — 메인 Web UI**

```bash
uv run uvicorn app.web:app --reload --port 8000
```

브라우저: `http://localhost:8000`

**CLI 단일 실행**

```bash
uv run python -m app.main "계란이랑 양파 있는데 점심 뭐 해먹지?"
```

### 테스트

```bash
uv run pytest tests/ -v
# 25 passed
```

개별 컴파일 확인:

```bash
uv run python -m py_compile app/agents/root_workflow.py && echo OK
uv run python -m py_compile app/agents/market_price_agent.py && echo OK
```

---

## 주요 Pydantic 스키마

### `FridgeRequest` — Extractor 출력

```python
class FridgeRequest(BaseModel):
    user_id: int | None
    ingredients: list[str]        # 사용자 직접 언급 재료
    max_cooking_time: int | None  # 최대 조리 시간(분)
    allowed_tools: list[str]      # pan, pot, microwave, airfryer ...
    excluded_ingredients: list[str]
    meal_context: Literal["breakfast","lunch","dinner","snack","late_night"] | None
```

### `RecipeFitResult` — 평가 결과

```python
class RecipeFitResult(BaseModel):
    recipe_id: int
    title: str
    match_score: float           # 0.0 ~ 1.0
    missing_required: list[str]
    missing_optional: list[str]
    route: Literal["COOK_NOW","SUBSTITUTION","SHOPPING_NEEDED"]
    cookable_now: bool
```

---

## API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| `GET` | `/` | Web UI (Jinja2) |
| `POST` | `/api/chat` | 메인 에이전트 실행 (`session_id` 없으면 신규 세션) |
| `GET` | `/api/fridge/{user_id}` | 냉장고 재고 + 유통기한 임박 조회 |

---

## 핵심 설계 원칙

- **웹 검색 금지** — Tavily, scraping, 외부 API 미사용. 가격 데이터는 로컬 catalog JSON만 사용
- **ShoppingAgent ≠ McpToolset 직접 보유** — 반드시 RemoteA2aAgent를 통해 MarketPriceAgent에 위임
- **output_schema는 BaseModel 전용** — 단순 텍스트 응답은 output_key만 사용
- **Windows 호환** — psycopg / ProactorEventLoop 충돌 방지를 위해 진입점에서 `WindowsSelectorEventLoopPolicy` 강제 설정
- **세션 격리** — `seen_recipe_titles`를 session state에 누적해 중복 추천 방지
