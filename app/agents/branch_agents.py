"""
조건부 분기 LLM 에이전트 3종.
DB 매칭 결과가 부족할 경우 Gemini 내장 지식으로 레시피를 생성한다.
"""
from google.adk import Agent
from google.adk.tools import google_search

from app.agents.prompts import (
    COOK_NOW_PROMPT,
    IMAGE_SEARCH_PROMPT,
    SHOPPING_PROMPT,
    SUBSTITUTION_PROMPT,
)
from app.tools.agent_tools import get_cooking_history, get_substitutions


cook_now_agent = Agent(
    name="CookNowAgent",
    description="보유 재료만으로 즉시 조리 가능한 레시피를 추천하는 에이전트",
    model="gemini-2.5-flash",
    instruction=COOK_NOW_PROMPT,
    tools=[get_cooking_history],
    output_key="recipe_response",
)

substitution_agent = Agent(
    name="SubstitutionAgent",
    description="부족한 재료를 대체재로 교체해 조리 가능한 레시피를 추천하는 에이전트",
    model="gemini-2.5-flash",
    instruction=SUBSTITUTION_PROMPT,
    tools=[get_cooking_history, get_substitutions],
    output_key="recipe_response",
)

shopping_agent = Agent(
    name="ShoppingAgent",
    description="최소 장보기 목록과 함께 완성 레시피를 추천하는 에이전트",
    model="gemini-2.5-flash",
    instruction=SHOPPING_PROMPT,
    tools=[get_cooking_history],
    output_key="recipe_response",
)


image_search_agent = Agent(
    name="ImageSearchAgent",
    description="추천된 레시피에 어울리는 이미지 URL을 반환하는 에이전트",
    model="gemini-2.5-flash",
    instruction=IMAGE_SEARCH_PROMPT,
    tools=[google_search],
    output_key="recipe_image",
)
