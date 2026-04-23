import os
import json
import re
from typing import Any

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
RECIPE_AGENT_NAMES = {"CookNowAgent", "SubstitutionAgent", "ShoppingAgent"}
SESSION_BACKEND = os.getenv("ADK_SESSION_BACKEND", "memory").lower()
MEMORY_SESSION_SERVICE = InMemorySessionService()


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    route: str | None
    session_id: str
    image_url: str | None = None
    image_source_url: str | None = None
    image_alt: str | None = None


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


def _extract_image_payload(value: Any) -> dict[str, str | None]:
    if not value:
        return {"image_url": None, "source_url": None, "alt": None}

    if isinstance(value, dict):
        data = value
    else:
        text = str(value).strip()
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return {"image_url": None, "source_url": None, "alt": None}

    return {
        "image_url": data.get("image_url"),
        "source_url": data.get("source_url"),
        "alt": data.get("alt"),
    }


def _looks_like_image_payload(text: str) -> bool:
    normalized = text.strip().lower()
    return "image_url" in normalized and ("source_url" in normalized or normalized.startswith("{"))


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

    final_response = ""
    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=session.id,
        new_message=new_message,
    ):
        author = getattr(event, "author", None)
        if event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    if author in RECIPE_AGENT_NAMES:
                        final_response = part.text
                    elif author != "ImageSearchAgent" and not _looks_like_image_payload(part.text):
                        final_response = part.text

    updated_session = await session_service.get_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=session.id,
    )
    route = updated_session.state.get("best_route") if updated_session else None
    if not final_response and updated_session:
        final_response = updated_session.state.get("recipe_response", "")
    image_payload = _extract_image_payload(
        updated_session.state.get("recipe_image") if updated_session else None
    )

    return ChatResponse(
        response=final_response or "(응답 없음)",
        route=route,
        session_id=session.id,
        image_url=image_payload["image_url"],
        image_source_url=image_payload["source_url"],
        image_alt=image_payload["alt"],
    )
