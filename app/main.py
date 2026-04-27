"""
냉털쉐프 Agent 실행 진입점.

실행: uv run python -m app.main
"""
import asyncio
import os
import sys

# psycopg 는 Windows ProactorEventLoop 과 호환되지 않으므로 임포트 전에 설정
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.sessions.database_session_service import DatabaseSessionService
from google.genai import types

from app.env import load_project_env

load_project_env()

from app.agents.root_workflow import root_workflow

APP_NAME = "fridge2dish"
USER_ID = "1"  # seed 에서 생성한 샘플 유저

SAMPLE_INPUTS = [
    "계란, 양파, 참치 있고 15분 안에 프라이팬으로 만들 수 있는 점심 메뉴 추천해줘",
    "냉장고에 두부랑 김치 있는데 매운거 말고 저녁 뭐 해먹지?",
    "콩나물이랑 대파 있어. 냄비 있고 20분 안에 만들 수 있는 거 알려줘",
]


async def run(user_message: str) -> None:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL is not set in environment variables. Please set it before running the application.")
    # session_service = InMemorySessionService()
    session_service = DatabaseSessionService(db_url = db_url)

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
        parts=[types.Part(text=user_message)],
    )

    print(f"\n{'='*60}")
    print(f"입력: {user_message}")
    print(f"{'='*60}\n")

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

    print(final_response or "(응답 없음)")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="냉털쉐프 Agent")
    parser.add_argument(
        "message",
        nargs="?",
        default=None,
        help="자연어 입력 (생략 시 샘플 입력으로 실행)",
    )
    args = parser.parse_args()

    message = args.message or SAMPLE_INPUTS[0]
    asyncio.run(run(message))


if __name__ == "__main__":
    main()
