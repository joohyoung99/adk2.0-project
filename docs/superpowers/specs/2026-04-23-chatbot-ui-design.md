# 냉털쉐프 챗봇 UI 설계

**날짜:** 2026-04-23

## 개요

냉털쉐프 ADK 에이전트를 사용자가 브라우저에서 바로 사용할 수 있는 웹 챗봇 UI를 구현한다.
FastAPI + Jinja2 + Bootstrap 5 (CDN) 스택으로, 빌드 툴 없이 단일 서버로 서빙한다.

## 스택

- **백엔드:** FastAPI (이미 `pyproject.toml` 의존성에 포함)
- **템플릿:** Jinja2 (FastAPI 내장)
- **스타일:** Bootstrap 5 CDN — 별도 npm/빌드 불필요
- **JS:** 바닐라 JavaScript (fetch API + DOM 조작)

## 파일 구조

```
app/
├── web.py                   ← FastAPI 앱 진입점 (uvicorn 실행)
├── api/
│   ├── __init__.py
│   ├── chat.py              ← POST /api/chat
│   └── fridge.py            ← GET /api/fridge/{user_id}
├── templates/
│   └── index.html           ← Jinja2 + Bootstrap 5 단일 페이지
└── static/
    └── app.js               ← 채팅 로직 (fetch, 스피너, 말풍선 렌더링)
```

## API 설계

### `POST /api/chat`

**Request:**
```json
{
  "message": "계란이랑 양파 있는데 뭐 만들지?",
  "session_id": "abc123"
}
```
`session_id` 는 선택값. 없으면 서버가 새 세션을 생성하고 응답에 포함해 반환.

**Response:**
```json
{
  "response": "계란볶음밥을 추천드려요! ...",
  "route": "COOK_NOW",
  "session_id": "abc123"
}
```

내부 동작:
1. `session_id` 없으면 `session_service.create_session()` 으로 신규 세션 생성
2. `session_id` 있으면 기존 세션 재사용 → 대화 이어감 (멀티턴)
3. `USER_ID = "1"` 고정, ADK `Runner.run_async()` 실행
4. 이벤트 스트림에서 마지막 텍스트 파트를 `response` 로 수집
5. 런 완료 후 `session_service.get_session()` 으로 세션 상태를 읽어 `state["best_route"]` 반환
6. `web.py` 모듈 최상단에 `asyncio.WindowsSelectorEventLoopPolicy()` 설정 (psycopg Windows 호환)

### 멀티턴 흐름

```
첫 메시지  → {message} → 서버가 session_id 생성 → {response, session_id} 반환
             브라우저 localStorage에 session_id 저장

이후 메시지 → {message, session_id} → 기존 세션 재사용 → 대화 context 유지
```

브라우저를 새로고침하면 localStorage 의 session_id 를 읽어 이전 대화를 복원한다.

### `GET /api/fridge/{user_id}`

**Response:**
```json
{
  "fridge_items": [
    { "ingredient_name": "계란", "quantity": 6, "unit": "개", "expires_at": "2026-04-30", "freshness_score": 0.9 }
  ],
  "expiring_items": [
    { "ingredient_name": "두부", "expires_at": "2026-04-24" }
  ]
}
```

## UI 구성

### 레이아웃 (Bootstrap grid)

```
┌─────────────────────────────────────────────────┐
│  navbar: 🧊 냉털쉐프                             │
├──────────────┬──────────────────────────────────┤
│  냉장고 재고   │  채팅창                           │
│  (col-md-4)  │  (col-md-8)                      │
│              │                                  │
│  card        │  메시지 버블들                     │
│  - 재고 목록  │                                  │
│  - ⚠️ 임박   │  [입력창] [전송 버튼]              │
└──────────────┴──────────────────────────────────┘
```

### 사이드패널 (냉장고 재고)

- 페이지 로드 시 `GET /api/fridge/1` 자동 호출
- 유통기한 D-3 이내 재료: `badge bg-warning text-dark` + ⚠️ 아이콘
- 신선도 낮음 (freshness_score < 0.4): `badge bg-danger`
- 일반 재료: `badge bg-success`

### 채팅창

- 사용자 메시지: 오른쪽 정렬, `bg-primary text-white` 말풍선
- 에이전트 응답: 왼쪽 정렬, `bg-light border` 말풍선
- 응답 말풍선 상단에 라우트 배지:
  - `COOK_NOW` → `badge bg-success` 🍳 즉시조리
  - `SUBSTITUTION` → `badge bg-warning` 🔄 대체재
  - `SHOPPING_NEEDED` → `badge bg-info` 🛒 장보기
- 전송 후 응답 대기 중: 전송 버튼 비활성화 + `spinner-border` 표시

## 실행 방법

```bash
# 개발
uv run uvicorn app.web:app --reload --port 8000

# VS Code launch.json 에 추가
{
  "name": "냉털쉐프 Web UI",
  "module": "uvicorn",
  "args": ["app.web:app", "--reload", "--port", "8000"]
}
```

## 범위 제외

- 사용자 인증 (USER_ID = "1" 고정)
- 냉장고 재고 추가/삭제 UI (조회만)
- 응답 스트리밍 (로딩 스피너로 대체)
- 모바일 반응형 최적화 (Bootstrap 기본 반응형으로 충분)
