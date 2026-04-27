"""
RemoteA2aAgent 인스턴스 모음.
ShoppingAgent가 sub_agents로 참조한다.
"""
import os

from google.adk.agents.remote_a2a_agent import RemoteA2aAgent

try:
    from a2a.utils.constants import AGENT_CARD_WELL_KNOWN_PATH
except ImportError:
    try:
        from google.adk.agents.remote_a2a_agent import AGENT_CARD_WELL_KNOWN_PATH
    except ImportError:
        AGENT_CARD_WELL_KNOWN_PATH = "/.well-known/agent.json"

MARKET_A2A_URL = os.getenv("MARKET_A2A_URL", "http://localhost:8001")

market_price_remote_agent = RemoteA2aAgent(
    name="MarketPriceAgent",
    agent_card=MARKET_A2A_URL.rstrip("/") + AGENT_CARD_WELL_KNOWN_PATH,
    description=(
        "부족 식재료의 로컬 catalog 기반 구매처와 가격 후보를 비교하는 에이전트. "
        "filesystem MCP로 data/market_catalog 파일을 읽어 마트별 가격을 비교한다."
    ),
)
