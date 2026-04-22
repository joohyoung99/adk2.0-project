
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
    """Read `fridge_request` from state and promote each field.
    user_id is always preserved from the session (never overwritten by LLM output).
    """
    req = ctx.state.get("fridge_request", {})
    if hasattr(req, "model_dump"):
        req = req.model_dump()
    if isinstance(req, dict):
        for key in ("ingredients", "max_cooking_time", "allowed_tools", "excluded_ingredients", "meal_context"):
            if key in req and req[key] is not None:
                ctx.state[key] = req[key]
    return req if isinstance(req, dict) else {}


def parse_input(ctx: Context) -> dict:
    """입력 검증 + 정규화 (도구명 소문자 통일, 빈 리스트 기본값 보정)"""
    tool_aliases = {
        "프라이팬": "pan", "팬": "pan",
        "냄비": "pot", "오븐": "oven",
        "전자레인지": "microwave", "에어프라이어": "airfryer",
        "그릴": "grill",
    }

    allowed_tools = ctx.state.get("allowed_tools") or []
    normalized_tools = [
        tool_aliases.get(t, t.lower()) for t in allowed_tools
    ]
    ctx.state["allowed_tools"] = normalized_tools

    if not ctx.state.get("ingredients"):
        ctx.state["ingredients"] = []
    if not ctx.state.get("excluded_ingredients"):
        ctx.state["excluded_ingredients"] = []

    return {
        "allowed_tools": normalized_tools,
        "ingredients": ctx.state.get("ingredients", []),
        "excluded_ingredients": ctx.state.get("excluded_ingredients", []),
    }