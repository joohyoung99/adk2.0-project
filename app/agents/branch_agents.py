"""
조건부 분기 LLM 에이전트 3종.
DB 매칭 결과가 부족할 경우 Gemini 내장 지식으로 레시피를 생성한다.
"""
from google.adk import Agent

from app.agents.prompts import (
    COOK_NOW_PROMPT,
    SHOPPING_PROMPT,
    SUBSTITUTION_PROMPT,
    USER_FACING_RESPONSE_STYLE,
)
from app.agents.remote_agents import market_price_remote_agent
from app.tools.agent_tools import (
    compare_market_prices_for_missing,
    get_cooking_history,
    get_substitutions,
)


cook_now_agent = Agent(
    name="CookNowAgent",
    description="보유 재료만으로 즉시 조리 가능한 레시피를 추천하는 에이전트",
    model="gemini-2.5-flash",
    instruction=COOK_NOW_PROMPT + USER_FACING_RESPONSE_STYLE,
    tools=[get_cooking_history],
    output_key="recipe_response",
)

substitution_agent = Agent(
    name="SubstitutionAgent",
    description="부족한 재료를 대체재로 교체해 조리 가능한 레시피를 추천하는 에이전트",
    model="gemini-2.5-flash",
    instruction=SUBSTITUTION_PROMPT + USER_FACING_RESPONSE_STYLE,
    tools=[get_cooking_history, get_substitutions],
    output_key="recipe_response",
)

shopping_agent = Agent(
    name="ShoppingAgent",
    description="최소 장보기 목록과 함께 완성 레시피를 추천하는 에이전트",
    model="gemini-2.5-flash",
    instruction=SHOPPING_PROMPT + USER_FACING_RESPONSE_STYLE,
    tools=[get_cooking_history, compare_market_prices_for_missing],
    sub_agents=[market_price_remote_agent],
    output_key="recipe_response",
)

