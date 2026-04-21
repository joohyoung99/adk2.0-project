# Fridge2Dish Agent

ADK 2.0 기반의 **냉장고 재료 기반 레시피 추천 워크플로우 시스템**입니다.

사용자 자연어 입력, PostgreSQL에 저장된 냉장고 재고/선호 정보를 결합해 **레시피 추천**, **조건부 분기**, **대체재 기반 재시도**를 수행합니다. DB에 없는 레시피는 branch agent가 **Google Search**로 실시간 탐색해 생성합니다.

이 프로젝트는 ADK 2.0 예시의 세 가지 패턴을 함께 반영합니다.

* **Graph-based Workflow**: 전체 파이프라인의 기본 직렬 흐름
* **Conditional Routing**: 추천 가능 상태에 따라 경로 분기
* **Dynamic Workflow**: 대체재 탐색 및 재추천 루프

---

## 📋 개요

이 시스템은 단순한 레시피 추천 챗봇이 아닙니다.

입력 문장을 구조화한 뒤, 사용자 재고와 선호 정보를 조회하고, DB 기반으로 후보 레시피를 1차 탐색합니다. 현재 재료 상태에 따라 **즉시 조리 가능 / 대체재 필요 / 장보기 필요**로 분기하며, 각 branch agent는 DB 결과를 우선 활용하되 **부족하거나 없는 경우 Google Search로 실시간 레시피를 탐색해 생성**합니다. 부족한 재료가 있는 경우에는 동적 루프를 통해 대체재를 탐색하고 재평가합니다.

핵심 목표는 아래와 같습니다.

* 자연어 입력에서 재료와 제약조건을 구조화한다.
* 사용자 냉장고 재고 및 선호를 DB에서 조회한다.
* DB 기반 후보 레시피를 1차 탐색하고 매칭 점수를 계산한다.
* 상태에 따라 조건부 라우팅을 수행한다.
* branch agent가 DB 결과 또는 Google Search로 최종 레시피를 생성한다.
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
[search_candidate_recipes]  ◀── Function Node: DB 기반 후보 레시피 1차 탐색
  ▼
[evaluate_recipe_fit]       ◀── Function Node: 매칭 점수 계산 + route 결정
  ▼
[fit_router]                ◀── Function Node: Event(route=...) 생성
  │
  ├── route="COOK_NOW"        ──▶ [cook_now_agent]        ◀── LLM Node + google_search
  ├── route="SUBSTITUTION"    ──▶ [substitution_agent]    ◀── LLM Node + google_search
  └── route="SHOPPING_NEEDED" ──▶ [shopping_agent]        ◀── LLM Node + google_search
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
   평가 결과를 바탕으로 `Event(route=...)`를 생성합니다.

   * `COOK_NOW`: 보유 재료만으로 즉시 조리 가능
   * `SUBSTITUTION`: 부족 재료가 있지만 대체재로 해결 가능
   * `SHOPPING_NEEDED`: 현재 상태로는 장보기가 필요

9. **Branch Agent (LLM + google_search)**
   선택된 branch agent가 state의 구조화된 데이터를 바탕으로 최종 레시피를 생성합니다.
   **DB 결과가 충분하면 그대로 활용하고, 부족하거나 없으면 `google_search` tool을 호출해 실시간으로 레시피를 탐색·생성**합니다.

   * `cook_now_agent`: 보유 재료로 바로 만들 수 있는 레시피 생성
   * `substitution_agent`: DB 대체재 정보 + 검색 기반 대체 조리법 생성
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

`fit_router`가 `Event(route=...)`를 반환하고, route 라벨에 따라 분기 agent가 달라집니다.

분기 기준 예시:

* `COOK_NOW`: 부족한 필수 재료 없음
* `SUBSTITUTION`: 부족한 필수 재료는 있으나 대체 가능
* `SHOPPING_NEEDED`: 대체해도 조리 불가

### Dynamic Workflow

`RecipeRecoveryWorkflow(BaseNode)`가 `ctx.run_node(...)`로 하위 노드를 반복 실행하며, 대체재 탐색 및 재추천 루프를 수행합니다.

---

## 📁 핵심 파일

| 파일/디렉토리                      | 역할                                                                          |
| ---------------------------- | --------------------------------------------------------------------------- |
| `agents/root_workflow.py`    | root workflow 정의 및 직렬 + 조건부 분기 조립                                           |
| `agents/extractor_agent.py`  | 자연어 입력 구조화 LLM 노드                                                           |
| `agents/branch_agents.py`    | COOK_NOW / SUBSTITUTION / SHOPPING_NEEDED 분기 LLM 노드 (google_search tool 포함) |
| `agents/dynamic_recovery.py` | BaseNode 기반 동적 재추천 루프 템플릿                                                   |
| `schemas/agent_io.py`        | `FridgeRequest`, `RecipeFitResult`, `RecommendationResponse` 등 Pydantic 스키마 |
| `db/models/`                 | SQLAlchemy ORM 모델                                                           |
| `db/repositories/`           | PostgreSQL 조회/저장 로직                                                         |
| `tools/`                     | Function Node 또는 tool wrapper                                               |
| `services/`                  | 점수 계산, 대체재 추천, 후보 랭킹 로직                                                     |

---

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

사용자 조건과 DB 정보를 결합해 후보 레시피를 탐색합니다. 결과가 없어도 워크플로우는 계속 진행되며, branch agent가 Google Search로 보완합니다.

### 6. `evaluate_recipe_fit` — Function Node

아래 값을 계산합니다.

* 레시피별 부족 재료
* 필수/선택 재료 구분
* 매칭 점수
* 추천 route (`COOK_NOW`, `SUBSTITUTION`, `SHOPPING_NEEDED`)

DB 후보가 없는 경우 보유 재료 수와 다양성을 기준으로 route를 결정합니다.

### 7. `fit_router` — Function Node

`Event(route=...)`를 반환해 분기 엣지를 활성화합니다.

### 8. Branch Agents — LLM Nodes (+ google_search)

각 agent는 state의 구조화된 데이터(재고, 선호, 매칭 결과, 대체재)를 프롬프트에 주입받아 최종 레시피를 생성합니다. DB 결과가 충분하면 우선 활용하고, 부족하면 `google_search`를 자율적으로 호출합니다.

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

추천 요청/결과 저장 (Google Search로 생성한 레시피 포함)

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

### Branch Agent 내장 Tool

* `google_search` — ADK 내장 tool. DB 후보 부족 시 branch agent가 자율 호출해 실시간 레시피 탐색

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
 │   ├─ branch_agents.py       ← google_search tool 포함
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
* **DB 우선 + Google Search 보완**: DB 레시피를 캐시로 활용하고, 없으면 branch agent가 실시간 탐색·생성

---

## 📈 확장 아이디어

* Human-in-the-loop 승인 노드 추가
* 유통기한 임박 재료 우선 추천 강화
* 장보기 리스트 자동 생성
* 식단 추천 워크플로우 확장
* 이미지 기반 냉장고 재료 인식 연계
* 동적 워크플로우를 루트 실행 엔진으로 승격
* Google Search로 생성한 레시피를 DB에 자동 저장해 캐시 누적

---

## 📝 발표용 한 줄 소개

**Fridge2Dish Agent는 ADK 2.0의 Graph-based Workflow, Conditional Routing, Dynamic Workflow 패턴을 결합해 자연어 입력 구조화, 사용자 재고 조회, DB 기반 레시피 매칭, 상태별 분기, Google Search를 활용한 실시간 레시피 생성, 대체재 기반 재추천까지 수행하는 냉장고 재료 기반 레시피 추천 시스템이다.**
