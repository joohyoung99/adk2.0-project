# 냉털쉐프 챗봇 UI 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** FastAPI + Bootstrap 5 기반의 냉장고 재고 사이드패널 + 채팅 UI를 구현한다.

**Architecture:** FastAPI가 Jinja2 템플릿과 static 파일을 서빙하며, `/api/chat`은 ADK Runner를 실행하고 `/api/fridge/{user_id}`는 DB에서 재고를 조회한다. 프론트엔드는 바닐라 JS로 fetch API를 통해 두 엔드포인트를 호출한다.

**Tech Stack:** FastAPI, Jinja2, Bootstrap 5 CDN, 바닐라 JavaScript, AsyncSession (psycopg3), Google ADK 2.0

---

## 파일 구조

```
app/
├── web.py                    ← 신규: FastAPI 앱 + 라우터 등록
├── api/
│   ├── __init__.py           ← 신규: 빈 파일
│   ├── chat.py               ← 신규: POST /api/chat
│   └── fridge.py             ← 신규: GET /api/fridge/{user_id}
├── templates/
│   └── index.html            ← 신규: Bootstrap 5 단일 페이지
└── static/
    └── app.js                ← 신규: 채팅 로직 (fetch, 스피너, 말풍선)

pyproject.toml                ← 수정: jinja2 의존성 추가
.vscode/launch.json           ← 수정: uvicorn 실행 설정 추가
tests/
└── test_fridge_api.py        ← 신규: 냉장고 API 유닛 테스트
```

---

## Task 1: 의존성 추가

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: jinja2 의존성 추가**

`pyproject.toml` 의 `dependencies` 에 추가:

```toml
[project]
dependencies = [
    "fastapi>=0.136.0",
    "google-adk>=2.0.0a3",
    "jinja2>=3.1.0",
    "psycopg[binary]>=3.3.3",
    "pydantic>=2.13.3",
    "python-dotenv>=1.2.2",
    "sqlalchemy[asyncio]>=2.1.0b2",
]
```

- [ ] **Step 2: 의존성 설치**

```powershell
uv sync
```

Expected: `jinja2` 패키지가 `.venv`에 설치됨

- [ ] **Step 3: 커밋**

```powershell
git add pyproject.toml uv.lock
git commit -m "chore: add jinja2 dependency for web UI"
```

---

## Task 2: FastAPI 앱 뼈대

**Files:**
- Create: `app/web.py`
- Create: `app/api/__init__.py`
- Create: `app/templates/` (디렉토리)
- Create: `app/static/` (디렉토리)

- [ ] **Step 1: 디렉토리 생성**

```powershell
New-Item -ItemType Directory -Path "app\templates" -Force
New-Item -ItemType Directory -Path "app\static" -Force
New-Item -ItemType Directory -Path "app\api" -Force
New-Item -Path "app\api\__init__.py" -ItemType File -Force
```

- [ ] **Step 2: `app/web.py` 작성**

```python
"""
냉털쉐프 Web UI 진입점.

실행: uv run uvicorn app.web:app --reload --port 8000
"""
import asyncio
import sys

# psycopg 는 Windows ProactorEventLoop 과 호환되지 않으므로 임포트 전에 설정
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request

from app.api.fridge import router as fridge_router
from app.api.chat import router as chat_router

BASE_DIR = Path(__file__).parent

app = FastAPI(title="냉털쉐프")

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

app.include_router(fridge_router)
app.include_router(chat_router)


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
```

- [ ] **Step 3: 서버 기동 확인 (임시 빈 라우터로)**

`app/api/fridge.py` 와 `app/api/chat.py` 가 없어서 임포트 오류가 날 것이므로 Task 3, 4 완료 후 이 단계를 실행한다. 지금은 건너뜀.

- [ ] **Step 4: 커밋**

```powershell
git add app/web.py app/api/__init__.py
git commit -m "feat: add FastAPI web app skeleton"
```

---

## Task 3: 냉장고 API

**Files:**
- Create: `app/api/fridge.py`
- Create: `tests/test_fridge_api.py`

- [ ] **Step 1: 테스트 디렉토리 생성 및 테스트 작성**

```powershell
New-Item -ItemType Directory -Path "tests" -Force
New-Item -Path "tests\__init__.py" -ItemType File -Force
```

`tests/test_fridge_api.py`:

```python
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.web import app
from app.schemas.agent_io import FridgeItemSnapshot

client = TestClient(app)

MOCK_FRIDGE = [
    FridgeItemSnapshot(
        ingredient_id=1,
        ingredient_name="계란",
        quantity=6.0,
        unit="개",
        freshness_score=5,
        expires_at=(date.today() + timedelta(days=10)).isoformat(),
    ),
    FridgeItemSnapshot(
        ingredient_id=2,
        ingredient_name="두부",
        quantity=1.0,
        unit="모",
        freshness_score=3,
        expires_at=(date.today() + timedelta(days=1)).isoformat(),  # 임박
    ),
]

MOCK_EXPIRING = [MOCK_FRIDGE[1]]


@patch("app.api.fridge.user_repository.get_fridge_items", new_callable=AsyncMock)
@patch("app.api.fridge.user_repository.get_expiring_items", new_callable=AsyncMock)
@patch("app.api.fridge.AsyncSessionLocal")
def test_fridge_returns_items_and_expiring(mock_session, mock_expiring, mock_fridge):
    mock_fridge.return_value = MOCK_FRIDGE
    mock_expiring.return_value = MOCK_EXPIRING
    mock_session.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    mock_session.return_value.__aexit__ = AsyncMock(return_value=False)

    response = client.get("/api/fridge/1")

    assert response.status_code == 200
    data = response.json()
    assert len(data["fridge_items"]) == 2
    assert len(data["expiring_items"]) == 1
    assert data["expiring_items"][0]["ingredient_name"] == "두부"
    assert data["expiring_items"][0]["days_until_expiry"] == 1
```

- [ ] **Step 2: 테스트 실행 (실패 확인)**

```powershell
uv run pytest tests/test_fridge_api.py -v
```

Expected: `ImportError` 또는 `404` — `app/api/fridge.py` 미존재

- [ ] **Step 3: `app/api/fridge.py` 구현**

```python
from datetime import date

from fastapi import APIRouter
from pydantic import BaseModel

from app.db.repositories import user_repository
from app.db.session import AsyncSessionLocal

router = APIRouter()


class FridgeItemOut(BaseModel):
    ingredient_name: str
    quantity: float | None
    unit: str | None
    freshness_score: int | None
    expires_at: str | None
    days_until_expiry: int | None


class FridgeResponse(BaseModel):
    fridge_items: list[FridgeItemOut]
    expiring_items: list[FridgeItemOut]


def _days_until(expires_at: str | None) -> int | None:
    if not expires_at:
        return None
    delta = date.fromisoformat(expires_at) - date.today()
    return delta.days


@router.get("/api/fridge/{user_id}", response_model=FridgeResponse)
async def get_fridge(user_id: int):
    async with AsyncSessionLocal() as session:
        fridge_items = await user_repository.get_fridge_items(session, user_id)
        expiring_items = await user_repository.get_expiring_items(session, user_id, within_days=3)

    return FridgeResponse(
        fridge_items=[
            FridgeItemOut(
                **item.model_dump(),
                days_until_expiry=_days_until(item.expires_at),
            )
            for item in fridge_items
        ],
        expiring_items=[
            FridgeItemOut(
                **item.model_dump(),
                days_until_expiry=_days_until(item.expires_at),
            )
            for item in expiring_items
        ],
    )
```

- [ ] **Step 4: 테스트 실행 (통과 확인)**

```powershell
uv run pytest tests/test_fridge_api.py -v
```

Expected: `PASSED`

- [ ] **Step 5: 커밋**

```powershell
git add app/api/fridge.py tests/test_fridge_api.py tests/__init__.py
git commit -m "feat: add fridge API endpoint GET /api/fridge/{user_id}"
```

---

## Task 4: 채팅 API

**Files:**
- Create: `app/api/chat.py`

- [ ] **Step 1: `app/api/chat.py` 구현**

```python
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from google.adk import Runner
from google.adk.sessions.database_session_service import DatabaseSessionService
from google.genai import types

from app.agents.root_workflow import root_workflow

router = APIRouter()

APP_NAME = "fridge2dish"
USER_ID = "1"


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    route: str | None
    session_id: str


@router.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured")

    session_service = DatabaseSessionService(db_url=db_url)

    # 세션 재사용 또는 신규 생성
    session = None
    if req.session_id:
        session = await session_service.get_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id=req.session_id,
        )
    if session is None:
        session = await session_service.create_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            state={"user_id": int(USER_ID)},
        )

    runner = Runner(
        node=root_workflow,
        app_name=APP_NAME,
        session_service=session_service,
    )

    new_message = types.Content(
        role="user",
        parts=[types.Part(text=req.message)],
    )

    final_response = ""
    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=session.id,
        new_message=new_message,
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    final_response = part.text

    # 세션 state 에서 best_route 읽기
    updated = await session_service.get_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=session.id,
    )
    route = updated.state.get("best_route") if updated else None

    return ChatResponse(
        response=final_response or "(응답 없음)",
        route=route,
        session_id=session.id,
    )
```

- [ ] **Step 2: 서버 기동 확인**

```powershell
uv run uvicorn app.web:app --reload --port 8000
```

Expected: `Application startup complete.` — 오류 없이 기동

- [ ] **Step 3: 엔드포인트 smoke test (curl)**

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/fridge/1" -Method GET | ConvertTo-Json
```

Expected: `fridge_items` 배열과 `expiring_items` 배열 반환

- [ ] **Step 4: 커밋**

```powershell
git add app/api/chat.py
git commit -m "feat: add chat API endpoint POST /api/chat"
```

---

## Task 5: HTML 템플릿

**Files:**
- Create: `app/templates/index.html`

- [ ] **Step 1: `app/templates/index.html` 작성**

```html
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>냉털쉐프 🧊</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body { background-color: #f8f9fa; }
    .chat-container {
      height: calc(100vh - 160px);
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 12px;
      padding: 16px;
    }
    .fridge-panel {
      height: calc(100vh - 120px);
      overflow-y: auto;
    }
    .bubble-user {
      align-self: flex-end;
      max-width: 75%;
    }
    .bubble-agent {
      align-self: flex-start;
      max-width: 85%;
    }
    .fridge-item { font-size: 0.875rem; }
    .navbar-brand { font-size: 1.25rem; font-weight: 700; }
    #chat-input { resize: none; }
  </style>
</head>
<body>

<nav class="navbar navbar-light bg-white border-bottom shadow-sm px-3">
  <span class="navbar-brand">🧊 냉털쉐프</span>
  <span class="text-muted small" id="session-label"></span>
</nav>

<div class="container-fluid mt-3">
  <div class="row g-3">

    <!-- 냉장고 재고 패널 -->
    <div class="col-md-4">
      <div class="card h-100">
        <div class="card-header d-flex justify-content-between align-items-center">
          <strong>🧊 냉장고 재고</strong>
          <button class="btn btn-sm btn-outline-secondary" onclick="loadFridge()">↻</button>
        </div>
        <div class="card-body fridge-panel p-2" id="fridge-list">
          <div class="text-center text-muted py-4">
            <div class="spinner-border spinner-border-sm" role="status"></div>
            <div class="mt-1 small">재고 로딩 중...</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 채팅 패널 -->
    <div class="col-md-8">
      <div class="card">
        <div class="card-header">
          <strong>💬 대화</strong>
          <button class="btn btn-sm btn-outline-danger float-end" onclick="resetSession()">새 대화</button>
        </div>
        <div class="chat-container" id="chat-container">
          <div class="bubble-agent">
            <div class="bg-light border rounded p-3">
              안녕하세요! 냉털쉐프입니다 🍳<br>
              냉장고에 있는 재료를 알려주시면 메뉴를 추천해드릴게요.
            </div>
          </div>
        </div>
        <div class="card-footer bg-white">
          <div class="input-group">
            <textarea
              id="chat-input"
              class="form-control"
              rows="2"
              placeholder="예: 계란이랑 김치 있는데 점심 뭐 만들지?"
            ></textarea>
            <button class="btn btn-primary" id="send-btn" onclick="sendMessage()">
              전송
            </button>
          </div>
        </div>
      </div>
    </div>

  </div>
</div>

<script src="/static/app.js"></script>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
```

- [ ] **Step 2: 브라우저 확인**

서버가 실행 중인 상태에서 `http://localhost:8000` 접속.
Expected: 냉장고 패널(로딩 스피너), 채팅창 레이아웃이 보여야 함. JS 없어서 아직 동작 안 함.

- [ ] **Step 3: 커밋**

```powershell
git add app/templates/index.html
git commit -m "feat: add Bootstrap 5 chatbot UI template"
```

---

## Task 6: 프론트엔드 JS

**Files:**
- Create: `app/static/app.js`

- [ ] **Step 1: `app/static/app.js` 작성**

```javascript
const ROUTE_LABELS = {
  COOK_NOW:        { text: "🍳 즉시조리", cls: "bg-success" },
  SUBSTITUTION:    { text: "🔄 대체재",   cls: "bg-warning text-dark" },
  SHOPPING_NEEDED: { text: "🛒 장보기",   cls: "bg-info text-dark" },
};

// ── 세션 관리 ─────────────────────────────────────────────────
function getSessionId() {
  return localStorage.getItem("fridge2dish_session_id");
}
function setSessionId(id) {
  localStorage.setItem("fridge2dish_session_id", id);
  document.getElementById("session-label").textContent = "세션: " + id.slice(0, 8) + "…";
}
function resetSession() {
  localStorage.removeItem("fridge2dish_session_id");
  document.getElementById("session-label").textContent = "";
  const container = document.getElementById("chat-container");
  container.innerHTML = `
    <div class="bubble-agent">
      <div class="bg-light border rounded p-3">
        새 대화를 시작합니다 🍳<br>냉장고에 있는 재료를 알려주세요!
      </div>
    </div>`;
}

// ── 냉장고 재고 로드 ──────────────────────────────────────────
async function loadFridge() {
  const list = document.getElementById("fridge-list");
  list.innerHTML = `<div class="text-center text-muted py-4">
    <div class="spinner-border spinner-border-sm" role="status"></div>
    <div class="mt-1 small">재고 로딩 중...</div>
  </div>`;

  try {
    const res = await fetch("/api/fridge/1");
    const data = await res.json();

    if (!data.fridge_items.length) {
      list.innerHTML = `<p class="text-muted text-center small py-3">등록된 재료가 없습니다.</p>`;
      return;
    }

    list.innerHTML = data.fridge_items.map(item => {
      const d = item.days_until_expiry;
      let badge = `<span class="badge bg-success">신선</span>`;
      if (d !== null && d <= 1) badge = `<span class="badge bg-danger">⚠️ D-${d}</span>`;
      else if (d !== null && d <= 3) badge = `<span class="badge bg-warning text-dark">⚠️ D-${d}</span>`;

      const qty = item.quantity != null ? `${item.quantity}${item.unit || ""}` : "";
      return `<div class="fridge-item d-flex justify-content-between align-items-center border-bottom py-1 px-2">
        <span>${item.ingredient_name} <small class="text-muted">${qty}</small></span>
        ${badge}
      </div>`;
    }).join("");
  } catch (e) {
    list.innerHTML = `<p class="text-danger small text-center py-3">재고 로드 실패</p>`;
  }
}

// ── 채팅 메시지 전송 ──────────────────────────────────────────
async function sendMessage() {
  const input = document.getElementById("chat-input");
  const message = input.value.trim();
  if (!message) return;

  appendUserBubble(message);
  input.value = "";

  const btn = document.getElementById("send-btn");
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner-border spinner-border-sm" role="status"></span>`;

  const thinkingId = appendThinkingBubble();

  try {
    const body = { message };
    const sid = getSessionId();
    if (sid) body.session_id = sid;

    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();

    setSessionId(data.session_id);
    removeThinkingBubble(thinkingId);
    appendAgentBubble(data.response, data.route);
  } catch (e) {
    removeThinkingBubble(thinkingId);
    appendAgentBubble("오류가 발생했습니다. 다시 시도해주세요.", null);
  } finally {
    btn.disabled = false;
    btn.innerHTML = "전송";
  }
}

// ── 말풍선 렌더링 헬퍼 ────────────────────────────────────────
function appendUserBubble(text) {
  const container = document.getElementById("chat-container");
  const div = document.createElement("div");
  div.className = "bubble-user";
  div.innerHTML = `<div class="bg-primary text-white rounded p-3">${escapeHtml(text)}</div>`;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function appendThinkingBubble() {
  const container = document.getElementById("chat-container");
  const id = "thinking-" + Date.now();
  const div = document.createElement("div");
  div.id = id;
  div.className = "bubble-agent";
  div.innerHTML = `<div class="bg-light border rounded p-3 text-muted">
    <span class="spinner-border spinner-border-sm me-2" role="status"></span>레시피 분석 중...
  </div>`;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
  return id;
}

function removeThinkingBubble(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

function appendAgentBubble(text, route) {
  const container = document.getElementById("chat-container");
  const div = document.createElement("div");
  div.className = "bubble-agent";

  const routeHtml = route && ROUTE_LABELS[route]
    ? `<span class="badge ${ROUTE_LABELS[route].cls} mb-2">${ROUTE_LABELS[route].text}</span><br>`
    : "";

  div.innerHTML = `<div class="bg-light border rounded p-3">
    ${routeHtml}${escapeHtml(text).replace(/\n/g, "<br>")}
  </div>`;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function escapeHtml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ── Enter 키 전송 (Shift+Enter 는 줄바꿈) ─────────────────────
document.addEventListener("DOMContentLoaded", () => {
  loadFridge();

  // 기존 세션 라벨 복원
  const sid = getSessionId();
  if (sid) {
    document.getElementById("session-label").textContent = "세션: " + sid.slice(0, 8) + "…";
  }

  document.getElementById("chat-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
});
```

- [ ] **Step 2: 전체 동작 테스트**

1. `http://localhost:8000` 접속
2. 냉장고 재고 패널에 DB 재료가 표시되는지 확인
3. "계란이랑 양파 있는데 점심 뭐 만들지?" 입력 후 전송
4. 스피너 표시 → 에이전트 응답 말풍선 + 라우트 배지 확인
5. 두 번째 메시지 전송 → 같은 세션으로 대화 이어지는지 확인
6. "새 대화" 버튼 → 세션 초기화 확인

- [ ] **Step 3: 커밋**

```powershell
git add app/static/app.js
git commit -m "feat: add frontend chat logic with session management"
```

---

## Task 7: VS Code 실행 설정

**Files:**
- Modify: `.vscode/launch.json`

- [ ] **Step 1: uvicorn launch 설정 추가**

`.vscode/launch.json` 의 `configurations` 배열에 추가:

```json
{
  "name": "냉털쉐프 Web UI",
  "type": "debugpy",
  "request": "launch",
  "module": "uvicorn",
  "python": "${workspaceFolder}/.venv/Scripts/python.exe",
  "args": ["app.web:app", "--reload", "--port", "8000"],
  "cwd": "${workspaceFolder}",
  "envFile": "${workspaceFolder}/.env",
  "env": {
    "PYTHONPATH": "${workspaceFolder}",
    "PYTHONUTF8": "1"
  },
  "console": "integratedTerminal",
  "justMyCode": false,
  "timeout": 60000
}
```

- [ ] **Step 2: F5로 실행 확인**

VS Code에서 "냉털쉐프 Web UI" 구성 선택 후 F5.
Expected: 터미널에 `Uvicorn running on http://127.0.0.1:8000` 출력

- [ ] **Step 3: 커밋**

```powershell
git add .vscode/launch.json
git commit -m "chore: add VS Code launch config for web UI"
```

---

## 완료 기준 체크리스트

- [ ] `http://localhost:8000` 접속 시 냉장고+채팅 2열 레이아웃 표시
- [ ] 냉장고 패널에 DB 재고 목록 표시, 유통기한 임박 항목에 ⚠️ 배지
- [ ] 메시지 전송 시 스피너 → 응답 말풍선 + 라우트 배지 표시
- [ ] 멀티턴: 두 번째 메시지가 같은 세션으로 이어짐
- [ ] "새 대화" 버튼으로 세션 초기화
- [ ] F5 (VS Code) 로 서버 실행 가능
