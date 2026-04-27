"""
MarketPriceAgent A2A 서버 진입점.

실행:
    uv run uvicorn app.agents.market_a2a_app:app --port 8001
    또는
    uv run python -m app.agents.market_a2a_app
"""
import asyncio
import os
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn
from google.adk.a2a.utils.agent_to_a2a import to_a2a

from app.agents.market_price_agent import market_price_agent

_PORT = int(os.getenv("MARKET_A2A_PORT", "8001"))

app = to_a2a(
    market_price_agent,
    host="localhost",
    port=_PORT,
    protocol="http",
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=_PORT)
