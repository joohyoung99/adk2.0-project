# branch agent 3개에 google_search tool만 추가  
# # [cook_now_agent]        → DB 레시피 있으면 그거 설명
#   [substitution_agent]    → 대체재 정보 + 필요시 검색
#   [shopping_agent]        → 최소 장보기 + 웹 레시피 검색


from google.adk import Agent, Context, Event
from app.agents.prompts import COOK_NOW_PROMPT
from app.schemas.agent_io import FridgeRequest
from google.adk.tools import google_search


from google.adk.workflow import Workflow, FunctionNode, BaseNode, Edge, START



cook_now_agent = Agent(
    name="CookNowAgent",
    description="사용자가 가진 재료로 즉시 조리 가능한 레시피를 추천하는 에이전트입니다.",
    model="gemini-2.5-flash",  
    instruction = COOK_NOW_PROMPT,
    tools = [google_search],
)