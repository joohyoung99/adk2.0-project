"""
MarketPriceAgent — filesystem MCP를 통해 로컬 market catalog를 읽어
구매처/가격 후보를 비교하는 에이전트.
data/market_catalog/*.json 파일만 읽는다 (read-only).
"""
import os
from pathlib import Path

from google.adk import Agent
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

from app.env import load_project_env
from app.agents.prompts import MARKET_PLAN_PROMPT

load_project_env()

MARKET_DATA_DIR = os.getenv("MARKET_DATA_DIR", "./data/market_catalog")
MARKET_DATA_ABS = str(Path(MARKET_DATA_DIR).resolve())

_mcp_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", MARKET_DATA_ABS],
        ),
        timeout=10.0,
    ),
    tool_filter=[
        "read_file",
        "read_multiple_files",
        "list_directory",
        "directory_tree",
        "search_files",
        "get_file_info",
        "list_allowed_directories",
    ],
)

market_price_agent = Agent(
    name="MarketPriceAgent",
    description="부족 식재료의 로컬 catalog 기반 구매처와 가격 후보를 비교하는 에이전트.",
    model="gemini-2.5-flash",
    instruction=MARKET_PLAN_PROMPT,
    tools=[_mcp_toolset],
    output_key="market_plan",
)
