import os

from fastapi import APIRouter, HTTPException
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.sessions.database_session_service import DatabaseSessionService
from google.genai import types
from pydantic import BaseModel, Field

from app.agents.root_workflow import root_workflow

router = APIRouter()

APP_NAME = "fridge2dish"
USER_ID = "1"
SESSION_BACKEND = os.getenv("ADK_SESSION_BACKEND", "memory").lower()
MEMORY_SESSION_SERVICE = InMemorySessionService()


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    route: str | None
    session_id: str


async def _get_or_create_session(
    session_service: DatabaseSessionService | InMemorySessionService,
    session_id: str | None,
):
    if session_id:
        session = await session_service.get_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id=session_id,
        )
        if session is not None:
            return session

    return await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        state={"user_id": int(USER_ID)},
    )


def _get_session_service(db_url: str) -> DatabaseSessionService | InMemorySessionService:
    if SESSION_BACKEND == "database":
        return DatabaseSessionService(db_url=db_url)
    return MEMORY_SESSION_SERVICE


@router.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured")

    session_service = _get_session_service(db_url)
    session = await _get_or_create_session(session_service, req.session_id)
    runner = Runner(
        node=root_workflow,
        app_name=APP_NAME,
        session_service=session_service,
    )

    new_message = types.Content(
        role="user",
        parts=[types.Part(text=req.message)],
    )

    async for _ in runner.run_async(
        user_id=USER_ID,
        session_id=session.id,
        new_message=new_message,
    ):
        pass

    updated_session = await session_service.get_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=session.id,
    )
    route = updated_session.state.get("best_route") if updated_session else None
    final_response = updated_session.state.get("recipe_response", "") if updated_session else ""

    return ChatResponse(
        response=final_response or "(응답 없음)",
        route=route,
        session_id=session.id,
    )
