"""
조건부 분기 LLM 에이전트 3종.
각 에이전트는 google_search tool을 보유하며,
DB 매칭 결과가 부족할 경우 자율적으로 검색해 레시피를 생성한다.
"""
from google.adk import Agent
from google.adk.tools import google_search

from app.agents.prompts import COOK_NOW_PROMPT, SUBSTITUTION_PROMPT, SHOPPING_PROMPT


cook_now_agent = Agent(
    name="CookNowAgent",
    description="보유 재료만으로 즉시 조리 가능한 레시피를 추천하는 에이전트",
    model="gemini-2.5-flash",
    instruction=COOK_NOW_PROMPT,
    tools=[google_search],
)

substitution_agent = Agent(
    name="SubstitutionAgent",
    description="부족한 재료를 대체재로 교체해 조리 가능한 레시피를 추천하는 에이전트",
    model="gemini-2.5-flash",
    instruction=SUBSTITUTION_PROMPT,
    tools=[google_search],
)

shopping_agent = Agent(
    name="ShoppingAgent",
    description="최소 장보기 목록과 함께 완성 레시피를 추천하는 에이전트",
    model="gemini-2.5-flash",
    instruction=SHOPPING_PROMPT,
    tools=[google_search],
)
