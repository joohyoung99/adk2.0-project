
from google.adk import Agent, Context, Event
from app.agents.prompts import EXTRACT_AGENT_PROMPT
from app.schemas.agent_io import FridgeRequest


from google.adk.workflow import Workflow, FunctionNode, BaseNode, Edge, START

## 자연어 -> FridgeRequest 객체로 변환하는 에이전트
input_extractor = Agent(
    name = "FridgeRequestExtractor",
    description = "사용자의 자연어 입력에서 FridgeRequest 객체로 필요한 정보를 추출하는 에이전트입니다.",
    model = "gemini-2.5-flash",
    instruction=EXTRACT_AGENT_PROMPT,
    output_schema=FridgeRequest,
    output_key="fridge_request",
)


def unpack_request(ctx: Context) -> dict:
    """Read `fridge_request` from state and promote each field."""
    req = ctx.state.get("fridge_request", {})
    if hasattr(req, "model_dump"):
        req = req.model_dump()
    if isinstance(req, dict):
        for key in ("user_id","ingredients", "max_cooking_time", "allowed_tools", "excluded_ingredients", "meal_context"):
            if key in req:
                ctx.state[key] = req[key]
    return req if isinstance(req, dict) else {}


def parse_input(ctx: Context) -> dict:
    """입력 검증 + 정규화"""
    req = ctx.state.get("fridge_request", {})
    if not isinstance(req, dict):
        raise ValueError("fridge_request must be a dict")
    

    return 