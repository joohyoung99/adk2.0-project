# 냉장고 기반 레시피 추천 및 장보기 최적화 멀티에이전트 시스템

ADK 2.0 기반의 **냉장고 기반 레시피 추천 및 장보기 최적화 멀티에이전트 시스템**입니다.

사용자 자연어 입력, PostgreSQL에 저장된 냉장고 재고/선호 정보를 결합해 **레시피 추천**, **조건부 분기**, **대체재 기반 재시도**를 수행합니다. DB 후보가 부족한 경우 branch agent가 LLM 지식으로 직접 레시피를 제안합니다. 
이 프로젝트는 ADK 2.0 예시의 세 가지 패턴을 함께 반영합니다.

* **Graph-based Workflow**: 전체 파이프라인의 기본 직렬 흐름
* **Conditional Routing**: 추천 가능 상태에 따라 경로 분기
* **Dynamic Workflow**: 대체재 탐색 및 재추천 루프

---

## 📋 개요

이 시스템은 단순한 레시피 추천 챗봇이 아닙니다.

입력 문장을 구조화한 뒤, 사용자 재고와 선호 정보를 조회하고, DB 기반으로 후보 레시피를 1차 탐색합니다. 현재 재료 상태에 따라 **즉시 조리 가능 / 대체재 필요 / 장보기 필요**로 분기하며, 각 branch agent는 DB 결과를 우선 활용하되 **부족하거나 없는 경우 LLM 지식을 바탕으로 직접 레시피를 제안**합니다. 부족한 재료가 있는 경우에는 동적 루프를 통해 대체재를 탐색하고 재평가합니다. 

핵심 목표는 아래와 같습니다.

* 자연어 입력에서 재료와 제약조건을 구조화한다.
* 사용자 냉장고 재고 및 선호를 DB에서 조회한다.
* DB 기반 후보 레시피를 1차 탐색하고 매칭 점수를 계산한다.
* 상태에 따라 조건부 라우팅을 수행한다.
* branch agent가 DB 결과 또는 LLM 지식으로 직접 레시피를 생성한다.
* 대체재 기반 재시도 루프를 수행한다.
* 최종 추천 결과와 로그를 저장한다.

---

## 🏗️ 아키텍처

### 1) Root Workflow

```text
START
  │
  ▼
[input_extractor]           ◀── LLM Node: 자연어 → FridgeRequest JSON
  │                            output_schema=FridgeRequest, output_key="fridge_request"
  ▼
[unpack_request]            ◀── Function Node: fridge_request 를 state 개별 키로 승격
  ▼
[parse_input]               ◀── Function Node: 입력 검증 + 정규화
  ▼
[load_user_context]         ◀── Function Node: PostgreSQL 에서 재고/선호/유통기한 조회
  ▼
[merge_input_with_fridge]   ◀── Function Node: 입력 재료와 냉장고 재고 병합
  ▼
[search_candidate_recipes]  ◀── Function Node: DB 기반 후보 레시피 1차 탐색
  ▼
[evaluate_recipe_fit]       ◀── Function Node: 매칭 점수 계산 + route 결정
  ▼
[rank_candidates]           ◀── Function Node: 유통기한·선호 반영 최종 랭킹
  ▼
[dynamic_recovery]          ◀── Dynamic BaseNode: 대체재 탐색 재시도 루프 (MAX 3회)
  ▼
[fit_router]                ◀── Function Node: ctx.route = "..." 세팅
  │
  ├── route="COOK_NOW"        ──▶ [cook_now_agent]        ◀── LLM Node
  ├── route="SUBSTITUTION"    ──▶ [substitution_agent]    ◀── LLM Node
  └── route="SHOPPING_NEEDED" ──▶ [shopping_agent]        ◀── LLM Node
  │
  ▼
[save_recommendation_log]   ◀── Function Node: 결과 저장
  ▼
END
```

### 2) Dynamic Workflow — 재추천 루프 템플릿

```text
class RecipeRecoveryWorkflow(BaseNode):
    MAX_ITERATIONS = 3

    async def _run_impl(ctx, node_input):
        for i in 1..3:
            await ctx.run_node(search_candidate_recipes)
            await ctx.run_node(evaluate_recipe_fit)
            if best_route == "COOK_NOW":
                break
            await ctx.run_node(find_substitutions)
            await ctx.run_node(apply_substitutions)
        yield {"status": ..., "iterations": ...}
```

안정적인 제출용 root workflow는 직렬 + 조건부 분기 구조로 운영하고, **대체재 재탐색 루프는 BaseNode 기반 동적 워크플로우 템플릿**으로 분리합니다.

---

## 🔄 데이터 처리 흐름

### A. Root Workflow

1. **자연어 입력**
   예: `계란, 양파, 참치 있고 15분 안에 프라이팬으로 만들 수 있는 점심 메뉴 추천해줘`

2. **Extractor (LLM)**
   사용자 문장에서 재료, 시간 제한, 허용 도구, 제외 재료, 식사 맥락을 파싱해 `FridgeRequest` JSON을 생성하고 `state["fridge_request"]`에 저장합니다.

3. **Unpack (Function)**
   `fridge_request`를 개별 필드로 state에 올립니다. 이후 Function Node가 자동 파라미터 바인딩으로 필요한 값을 직접 받습니다.

4. **Parse (Function)**
   Pydantic으로 요청값을 검증하고 정규화합니다.

5. **Load Context (Function)**
   PostgreSQL에서 사용자 냉장고 재고, 선호 정보, 알레르기, 유통기한 임박 재료를 조회합니다.

6. **Search Candidates (Function)**
   조리 시간, 도구, 선호 태그를 반영해 DB에서 후보 레시피를 1차 탐색합니다.

7. **Evaluate Fit (Function)**
   레시피별 부족 재료, 필수 재료, 매칭 점수, 추천 가능 상태를 계산합니다.

8. **Router (Function)**
   평가 결과를 바탕으로 `ctx.route`에 값을 세팅합니다.

   * `COOK_NOW`: 보유 재료만으로 즉시 조리 가능
   * `SUBSTITUTION`: 부족 재료가 있지만 대체재로 해결 가능
   * `SHOPPING_NEEDED`: 현재 상태로는 장보기가 필요

9. **Branch Agent (LLM)**
   선택된 branch agent가 state의 구조화된 데이터를 바탕으로 최종 레시피를 생성합니다.
   DB 결과가 충분하면 우선 활용하고, 부족하거나 없으면 LLM 지식으로 직접 레시피를 제안합니다.

   * `cook_now_agent`: 보유 재료로 바로 만들 수 있는 레시피 생성
   * `substitution_agent`: DB 대체재 정보 + LLM 지식 기반 대체 조리법 생성
   * `shopping_agent`: 최소 장보기 목록 + 완성 레시피 생성

10. **Save Log (Function)**
    요청 원문, 컨텍스트, 추천 결과를 저장합니다.

### B. Dynamic Workflow

동적 루프는 아래 상황에서 사용합니다.

* 후보 레시피는 있으나 바로 조리가 안 되는 경우
* 대체재를 적용하면 조리 가능성이 생기는 경우
* 1차 추천 결과가 너무 약해 재탐색이 필요한 경우

루프 흐름은 아래와 같습니다.

1. 후보 레시피 재탐색
2. 부족 재료 평가
3. 대체재 탐색
4. 대체재 적용 후 재계산
5. 기준 충족 시 종료, 아니면 최대 반복 횟수까지 재시도

---

## 🌿 워크플로우 패턴 반영 방식

### Graph-based Workflow

기본 실행 파이프라인은 `extractor → unpack → parse → search → evaluate → branch` 형태의 직렬 그래프로 구성합니다.

### Conditional Routing

`fit_router`가 `ctx.route`에 값을 세팅하면, `Edge(from_node, to_node, route=...)` 조건에 따라 분기 agent가 달라집니다.

분기 기준 예시:

* `COOK_NOW`: 부족한 필수 재료 없음
* `SUBSTITUTION`: 부족한 필수 재료는 있으나 대체 가능
* `SHOPPING_NEEDED`: 대체해도 조리 불가

### Dynamic Workflow

`RecipeRecoveryWorkflow(BaseNode)`가 `ctx.run_node(...)`로 하위 노드를 반복 실행하며, 대체재 탐색 및 재추천 루프를 수행합니다.

---

<h3>Workflow</h3>
<p align="center">
  <img src="./adk2.0_flowchart.png" alt="ADK2.0 Project Workflow" width="900"/>
</p>

## 🧩 노드 구성

### 1. `input_extractor` — LLM Node

사용자 자연어를 `FridgeRequest` 스키마로 구조화합니다.

추출 대상:

* `user_id`
* `ingredients`
* `max_cooking_time`
* `allowed_tools`
* `excluded_ingredients`
* `meal_context`

### 2. `unpack_request` — Function Node

`state["fridge_request"]`를 개별 키로 승격합니다.

### 3. `parse_input` — Function Node

입력값을 Pydantic으로 검증하고 정규화합니다.

### 4. `load_user_context` — Function Node

다음 정보를 DB에서 조회합니다.

* 냉장고 재고
* 사용자 선호
* 비선호 재료
* 알레르기
* 유통기한 임박 재료

### 5. `search_candidate_recipes` — Function Node

사용자 조건과 DB 정보를 결합해 후보 레시피를 탐색합니다. 결과가 없어도 워크플로우는 계속 진행되며, branch agent가 LLM 지식으로 직접 레시피를 제안합니다.

### 6. `evaluate_recipe_fit` — Function Node

아래 값을 계산합니다.

* 레시피별 부족 재료
* 필수/선택 재료 구분
* 매칭 점수
* 추천 route (`COOK_NOW`, `SUBSTITUTION`, `SHOPPING_NEEDED`)

DB 후보가 없는 경우 보유 재료 수와 다양성을 기준으로 route를 결정합니다.

### 7. `fit_router` — Function Node

`ctx.route`에 값을 세팅해 `Edge`의 `route` 조건을 활성화합니다.

### 8. Branch Agents — LLM Nodes

각 agent는 state의 구조화된 데이터(재고, 선호, 매칭 결과, 대체재)를 프롬프트에 주입받아 최종 레시피를 생성합니다. DB 결과가 충분하면 우선 활용하고, 부족하면 LLM 지식으로 직접 제안합니다.

* `cook_now_agent`: 보유 재료만으로 만들 수 있는 레시피 생성
* `substitution_agent`: 대체재 정보 포함 조리법 생성
* `shopping_agent`: 최소 장보기 목록 + 완성 레시피 생성

### 9. `save_recommendation_log` — Function Node

추천 요청 및 결과를 저장합니다.


### 10. `RecipeRecoveryWorkflow` — Dynamic BaseNode

재료 부족 상황에서 대체재 탐색과 후보 재계산을 반복합니다.

---

## 🗄️ 데이터베이스 구조

### `users`

사용자 기본 정보

### `user_preferences`

사용자 선호/제약 정보

* 맵기 허용 수준
* 비선호 재료
* 알레르기
* 식단 태그
* 요리 숙련도

### `ingredients`

재료 마스터

### `user_fridge_items`

사용자 냉장고 재고

* 재료
* 수량
* 단위
* 유통기한
* 보관 위치
* 신선도 점수

### `recipes`

레시피 마스터 (DB 캐시 역할 — branch agent가 생성한 레시피도 저장 가능)

* 제목
* 설명
* 조리 시간
* 난이도
* 조리 순서
* 도구 태그
* 식단 태그

### `recipe_ingredients`

레시피-재료 매핑

* 필요 재료
* 수량
* 필수 여부
* garnish 여부

### `ingredient_substitutions`

대체 재료 매핑 — branch agent 프롬프트에 주입되어 LLM의 대체재 판단을 보조

* 원재료
* 대체 재료
* 대체 비율
* 메모

### `recommendation_logs`

추천 요청/결과 저장

### `cooking_history`

조리 이력 및 피드백 저장

---

## 🧪 Pydantic 스키마

### `FridgeRequest`

사용자 요청 스키마

```json
{
  "user_id": 1,
  "ingredients": ["계란", "양파", "참치"],
  "max_cooking_time": 15,
  "allowed_tools": ["pan"],
  "excluded_ingredients": [],
  "meal_context": "lunch"
}
```

### `RecipeFitResult`

레시피 적합도 평가 스키마

```json
{
  "recipe_id": 12,
  "title": "참치계란볶음밥",
  "match_score": 0.86,
  "missing_required": ["대파"],
  "missing_optional": ["후추"],
  "route": "SUBSTITUTION"
}
```

### `RecommendationResponse`

최종 추천 응답 스키마

```json
{
  "summary": "대체재를 활용하면 조리 가능한 메뉴 2개를 찾았습니다.",
  "decision": "SUBSTITUTION",
  "recommendations": [
    {
      "recipe_id": 12,
      "title": "참치계란볶음밥",
      "status": "substitution_needed",
      "match_score": 0.86,
      "missing_items": ["대파"],
      "substitutions": [
        {
          "missing": "대파",
          "substitute": "양파",
          "note": "향은 달라지지만 조리 가능"
        }
      ]
    }
  ]
}
```

---

## 🛠️ Tool / Function 목록

### 사용자 컨텍스트 조회

* `get_user_preferences(user_id: int) -> dict`
* `get_user_fridge_items(user_id: int) -> list[dict]`
* `get_expiring_items(user_id: int, within_days: int = 3) -> list[dict]`
* `merge_input_ingredients_with_fridge(user_id: int, input_ingredients: list[str]) -> list[dict]`

### 레시피 탐색 및 평가

* `search_candidate_recipes(max_cooking_time: int | None, allowed_tools: list[str] | None, dietary_tags: list[str] | None) -> list[dict]`
* `get_recipe_ingredients(recipe_id: int) -> list[dict]`
* `calculate_recipe_match(fridge_items: list[dict], recipe_id: int) -> dict`
* `evaluate_recipe_fit(candidates: list[dict], fridge_items: list[dict]) -> dict`

### 대체재 및 재탐색

* `find_substitutions_for_missing_items(missing_items: list[str]) -> dict`
* `apply_substitutions(candidate: dict, substitutions: dict) -> dict`
* `rank_recipe_candidates(candidates: list[dict], expiring_items: list[dict], preferences: dict) -> list[dict]`

### 저장 및 이력

* `save_recommendation_log(user_id: int, request_text: str, context_json: dict, result_json: dict) -> int`
* `save_cooking_feedback(user_id: int, recipe_id: int, rating: int | None, liked: bool | None, feedback_text: str | None) -> int`
* `get_recent_cooking_history(user_id: int, limit: int = 10) -> list[dict]`

---

## 📂 디렉토리 구조

```text
app/
 ├─ db/
 │   ├─ base.py
 │   ├─ session.py
 │   ├─ models/
 │   │   ├─ user.py
 │   │   ├─ ingredient.py
 │   │   ├─ recipe.py
 │   │   ├─ fridge.py
 │   │   └─ history.py
 │   └─ repositories/
 │       ├─ user_repository.py
 │       ├─ fridge_repository.py
 │       ├─ recipe_repository.py
 │       └─ recommendation_repository.py
 ├─ schemas/
 │   ├─ agent_io.py
 │   ├─ dto.py
 │   └─ response.py
 ├─ agents/
 │   ├─ extractor_agent.py
 │   ├─ branch_agents.py
 │   ├─ dynamic_recovery.py
 │   ├─ root_workflow.py
 │   └─ prompts/
 ├─ tools/
 │   ├─ fridge_tools.py
 │   ├─ recipe_tools.py
 │   └─ history_tools.py
 ├─ services/
 │   ├─ ranking_service.py
 │   └─ substitution_service.py
 └─ main.py
```

---

## 🚀 실행 예시

```bash
uv run python -m app.main
```

예시 입력:

```text
계란, 양파, 참치 있고 15분 안에 프라이팬으로 만들 수 있는 점심 메뉴 추천해줘
```

예상 분기 예시:

* DB 레시피 매칭 → `COOK_NOW` → cook_now_agent가 레시피 생성
* 재료 일부 부족 → `SUBSTITUTION` → substitution_agent가 대체재 + 검색으로 레시피 생성
* 재료 많이 부족 → `SHOPPING_NEEDED` → shopping_agent가 장보기 목록 + 검색으로 레시피 생성

---

## 🔑 핵심 포인트

* **Graph-based Workflow**로 기본 파이프라인 구성
* **Conditional Routing**으로 추천 상태별 분기 수행
* **Dynamic Workflow(BaseNode)**로 대체재 재탐색 루프 확장
* **Extractor 패턴** 적용: 자연어 입력을 앞단에서 구조화
* **자동 파라미터 바인딩**: Function Node가 state 키를 인자로 주입받아 실행
* **Pydantic 기반 타입 검증**: 입력/평가/응답을 구조화
* **PostgreSQL + SQLAlchemy 연동**: 재고, 선호, 추천 로그를 상태로 관리
* **DB 우선 + LLM 직접 제안**: DB 레시피를 캐시로 활용하고, 없으면 branch agent가 LLM 지식으로 직접 제안

---

## 📈 확장 아이디어

* Human-in-the-loop 승인 노드 추가
* 유통기한 임박 재료 우선 추천 강화
* 장보기 리스트 자동 생성
* 식단 추천 워크플로우 확장
* 이미지 기반 냉장고 재료 인식 연계
* 동적 워크플로우를 루트 실행 엔진으로 승격
* LLM 생성 레시피를 DB에 자동 저장해 캐시 누적

---

## 🔌 A2A + Filesystem MCP 확장

SHOPPING_NEEDED 분기에서 **ShoppingAgent**가 부족 재료의 구매처와 가격을 비교하기 위해 **A2A(Agent-to-Agent) 프로토콜**과 **Filesystem MCP**를 활용합니다.

---

### 아키텍처 개요

```
냉장고 DB 조회
  → 레시피 후보 탐색 (DB)
  → 부족 재료 산출 (match_score 계산)
  → SHOPPING_NEEDED 분기
      → ShoppingAgent (LLM, sub_agents=[market_price_remote_agent])
          │
          │  A2A 프로토콜 (HTTP)
          ▼
      MarketPriceAgent A2A 서버 (localhost:8001)
          │
          │  Filesystem MCP (stdio)
          │  npx @modelcontextprotocol/server-filesystem
          │  allowed: data/market_catalog/
          ▼
      homeplus.json / emart.json / lotte_mart.json
          │
          ▼
      구매 후보 + 추천 구매처 반환 → ShoppingAgent가 최종 응답에 통합
```

---

### 전체 흐름 상세

| 단계 | 담당 | 내용 |
|------|------|------|
| 1 | `load_user_context` | PostgreSQL에서 냉장고 재고·유통기한·선호 조회 |
| 2 | `search_candidate_recipes` | 조리 시간·도구·식단 태그로 DB 레시피 후보 탐색 |
| 3 | `evaluate_recipe_fit` | 레시피별 `match_score` 계산, 부족 재료 목록 산출 |
| 4 | `rank_candidates` | 유통기한·사용자 언급 재료 보정 후 최종 랭킹 |
| 5 | `fit_router` | 부족 재료 상태에 따라 `SHOPPING_NEEDED` 분기 결정 |
| 6 | `ShoppingAgent` (LLM) | 레시피 추천 + MarketPriceAgent에 구매처 비교 위임 |
| 7 | `RemoteA2aAgent` | HTTP로 MarketPriceAgent A2A 서버 호출 |
| 8 | `MarketPriceAgent` | Filesystem MCP로 `data/market_catalog/*.json` 읽기 |
| 9 | MarketPriceAgent 응답 | 마트별 가격 후보 + 추천 구매처 + 주의사항 반환 |
| 10 | ShoppingAgent 최종 응답 | 6섹션 형식으로 레시피·장보기 목록·구매처 통합 출력 |

---

### 사전 요구사항

#### Python 환경

```bash
# a2a-sdk 포함 의존성 설치
uv sync
# google-adk[a2a]>=2.0.0a3 가 설치됩니다 (a2a-sdk 0.3.x 포함)
```

#### Node.js / npx

Filesystem MCP 서버(`@modelcontextprotocol/server-filesystem`)는 Node.js 환경에서 `npx`로 실행됩니다.

```bash
node --version   # v18 이상 필요
npx --version
```

Node.js가 없으면 [https://nodejs.org](https://nodejs.org) 에서 설치하세요.

---

### 환경변수 설정 (`.env`)

`.env_sample`을 `.env`로 복사한 뒤 실제 값을 채웁니다. `.env` 파일은 절대 커밋하지 않습니다.

```env
# PostgreSQL 연결 URL
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/dbname

# Google AI API Key (Gemini 모델 사용)
GOOGLE_API_KEY=your_google_api_key_here

# ADK 세션 백엔드 (memory | database)
ADK_SESSION_BACKEND=memory

# MarketPriceAgent A2A 서버 URL (기본값: http://localhost:8001)
MARKET_A2A_URL=http://localhost:8001

# MarketPriceAgent A2A 서버 포트 (기본값: 8001)
MARKET_A2A_PORT=8001

# Market catalog 데이터 디렉터리 (기본값: ./data/market_catalog)
MARKET_DATA_DIR=./data/market_catalog
```

---

### 실행 순서

#### 1단계 — 의존성 설치

```bash
uv sync
```

`a2a-sdk 0.3.x`가 설치되었는지 확인합니다.

```bash
uv run python -c "from google.adk.agents.remote_a2a_agent import RemoteA2aAgent; print('OK')"
# OK
```

#### 2단계 — Market catalog 파일 확인

```bash
ls data/market_catalog/
# homeplus.json  emart.json  lotte_mart.json  ingredient_aliases.json
```

각 파일은 아래 구조를 따릅니다.

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
      "in_stock": true,
      "note": "샘플 catalog 데이터"
    }
  ]
}
```

새 마트를 추가하려면 동일한 스키마의 JSON 파일을 `data/market_catalog/`에 생성합니다.

#### 3단계 — MarketPriceAgent A2A 서버 실행 (별도 터미널)

```bash
uv run uvicorn app.agents.market_a2a_app:app --port 8001
```

또는:

```bash
uv run python -m app.agents.market_a2a_app
```

#### 4단계 — Agent Card 확인

A2A 서버가 정상 기동했는지 확인합니다.

```bash
curl http://localhost:8001/.well-known/agent-card.json
```

정상이면 `MarketPriceAgent`의 이름·설명·capabilities가 담긴 JSON을 반환합니다.

#### 5단계 — 메인 앱 실행 (별도 터미널)

```bash
uv run uvicorn app.web:app --reload --port 8000
```

브라우저에서 `http://localhost:8000` 을 열면 Web UI가 나타납니다.

---

### Filesystem MCP 서버 동작 방식

| 항목 | 내용 |
|------|------|
| 실행 방식 | `npx -y @modelcontextprotocol/server-filesystem <절대경로>` (stdio) |
| Allowed directory | `data/market_catalog/` 디렉터리만 접근 허용 |
| 허용 도구 | `list_directory`, `read_file`, `read_multiple_files`, `search_files`, `list_allowed_directories` |
| 금지 도구 | `write_file`, `edit_file`, `create_directory`, `move_file`, `delete_file` (tool_filter로 차단) |
| 웹 검색 | 사용 안 함 — 모든 가격 정보는 로컬 JSON 파일 기반 |

MarketPriceAgent는 프로세스 시작 시 `npx`로 MCP 서버를 자동 실행하므로 별도 설치 없이 동작합니다.

---

### 가격 데이터 주의사항

- 모든 가격 정보는 **로컬 catalog 기준 가격 후보**입니다.
- 실제 마트의 가격·재고·배송비와 다를 수 있습니다.
- **실시간 웹 가격 비교가 아닙니다.** Tavily, web scraping, 외부 API를 사용하지 않습니다.
- 응답에는 `source_file`, `updated_at`, `confidence`, `note` 필드가 포함되어 출처와 신뢰도를 명시합니다.
- catalog 가격을 갱신하려면 해당 JSON 파일의 `price`와 `updated_at`을 직접 수정하세요.

---

### 사용 예시

#### 예시 입력

```text
냉장고에 계란 2개, 간장 있는데 소고기 넣은 요리 해먹고 싶어
```

이 경우 소고기가 부족 재료로 산출되어 `SHOPPING_NEEDED` 분기로 진입합니다.

#### ShoppingAgent 예시 응답

```
### 1. 추천 레시피
**소고기 계란 간장 볶음**
- 소고기를 얇게 썰어 간장 양념 후 팬에 볶습니다.
- 계란을 스크램블로 익혀 함께 볶습니다.
- 예상 조리 시간: 15분

### 2. 보유 재료 활용
- 계란 (냉장고 보유)
- 간장 (냉장고 보유)

### 3. 추가 구매 재료
- 소고기 (국거리용 또는 불고기용) 200g

### 4. 로컬 catalog 기반 구매 후보
| 재료 | 마트 | 상품명 | 가격 | 재고 |
|------|------|--------|------|------|
| 소고기 | Emart | 호주산 소고기 국거리용 200g | 6,980원 | 있음 |
| 소고기 | LotteMart | 호주산 소고기 불고기용 200g | 7,200원 | 없음 |

### 5. 추천 구매처와 이유
**Emart** — 소고기 재고 있음, 가격 최저 (6,980원)

### 6. 가격/재고 변동 주의사항
위 가격 정보는 로컬 catalog 기준 가격 후보이며, 실제 가격·재고·배송비와 다를 수 있습니다.
```

---

### 테스트 및 검증

#### 스키마·catalog 유효성 검사

```bash
uv run pytest tests/test_market_catalog.py -v
```

테스트 항목:

- `test_catalog_top_level_fields` — homeplus/emart/lotte_mart 필수 필드 검증
- `test_catalog_items_have_required_fields` — 각 항목의 필수 필드 검증
- `test_catalog_prices_are_positive_or_null` — 가격 양수 검증
- `test_ingredient_aliases_schema` — alias 사전 구조 검증
- `test_price_offer_creation` — PriceOffer Pydantic 모델 생성
- `test_market_price_agent_import` — MarketPriceAgent 정상 임포트
- `test_market_a2a_app_import` — A2A 서버 앱 정상 임포트
- `test_remote_agents_import` — RemoteA2aAgent 정상 임포트
- `test_shopping_agent_has_market_sub_agent` — ShoppingAgent에 sub_agent 연결 확인

#### 전체 테스트 실행

```bash
uv run pytest tests/ -v
# 25 passed
```

#### 개별 파일 컴파일 확인

```bash
uv run python -m py_compile app/agents/market_price_agent.py && echo "OK"
uv run python -m py_compile app/agents/market_a2a_app.py && echo "OK"
uv run python -m py_compile app/agents/remote_agents.py && echo "OK"
uv run python -m py_compile app/agents/branch_agents.py && echo "OK"
```
