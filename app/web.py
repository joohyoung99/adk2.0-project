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
