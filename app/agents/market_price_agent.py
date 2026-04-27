"""
MarketPriceAgent — 로컬 market catalog 기반 구매처/가격 후보 비교 에이전트.
filesystem MCP server를 통해 data/market_catalog/*.json 파일만 읽는다.
Tavily, web search, scraping 사용 금지.
"""
import os
from pathlib import Path

from google.adk import Agent
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, StdioServerParameters

MARKET_DATA_DIR = os.getenv("MARKET_DATA_DIR", "./data/market_catalog")
MARKET_DATA_ABS = str(Path(MARKET_DATA_DIR).resolve())

_READ_ONLY_TOOLS = [
    "list_directory",
    "read_file",
    "read_multiple_files",
    "search_files",
    "list_allowed_directories",
]

MARKET_PLAN_PROMPT = """
당신은 냉털쉐프의 "로컬 catalog 기반 구매처 비교" 에이전트입니다.

## 역할
missing_items 목록을 받아 로컬 market catalog 파일에서 구매 후보를 찾고 비교합니다.
웹 검색, 실시간 가격 조회, scraping은 절대 사용하지 않습니다.
모든 가격 정보는 "로컬 catalog 기준 가격 후보"이며 실제 가격/재고/배송비와 다를 수 있습니다.

## 입력
- missing_items: 구매가 필요한 재료 목록
- recipe_title: (선택) 대상 레시피명
- preferred_markets: (선택) 선호 마트 목록
- location: (선택) 위치 정보

## 작업 순서
1. list_directory로 catalog 디렉터리의 파일 목록을 확인한다.
2. ingredient_aliases.json을 read_file로 읽어 재료명을 canonical_ingredient로 정규화한다.
3. emart.json, homeplus.json, lotte_mart.json을 read_multiple_files로 읽는다.
4. missing_items의 각 재료를 alias로 검색해 각 마트의 가격/재고를 수집한다.
5. catalog에 없는 재료는 observed_price=null, confidence="low"로 처리한다.

## 추천 마트 선정 기준 (우선순위 순)
1순위: missing_items를 가장 많이 커버하는 마트 (covered_items 수)
2순위: in_stock=true인 항목이 많은 마트
3순위: total_estimated_price가 낮은 마트 (null 항목 제외하고 합산)
4순위: updated_at이 최신인 마트

## 출력 형식
반드시 아래 JSON 구조로만 응답하세요. 설명 텍스트 없이 JSON만 반환:

{
  "offers": [
    {
      "ingredient": "입력된 재료명",
      "canonical_ingredient": "정규화된 재료명",
      "market": "마트명",
      "product_name": "상품명",
      "observed_price": 가격(정수) 또는 null,
      "currency": "KRW",
      "unit": "단위",
      "quantity_value": 수량(숫자) 또는 null,
      "quantity_unit": "수량단위" 또는 null,
      "in_stock": true/false,
      "source_file": "파일명.json",
      "updated_at": "YYYY-MM-DD",
      "confidence": "high/medium/low",
      "note": "비고" 또는 null
    }
  ],
  "recommended_market": {
    "market": "추천 마트명",
    "reason": "추천 이유",
    "covered_items": ["커버되는 재료 목록"],
    "missing_items": ["catalog에 없는 재료 목록"],
    "total_estimated_price": 합계(정수) 또는 null,
    "currency": "KRW"
  },
  "warnings": [
    "로컬 catalog 기준 가격 후보이며 실제 가격/재고/배송비와 다를 수 있음",
    "가격이 null인 항목은 합계에서 제외됨"
  ]
}

## 중요 제약
- "실시간 최저가", "현재 최저가", "웹 검색 결과" 표현 사용 금지
- source_file, updated_at, confidence, note 없는 가격 정보는 신뢰하지 않음
- catalog에 없는 재료는 observed_price=null, confidence="low"
- 가격 추측 금지 — catalog에서 찾은 값만 사용
""".strip()


market_price_agent = Agent(
    name="MarketPriceAgent",
    description="부족 식재료의 로컬 catalog 기반 구매처와 가격 후보를 비교하는 에이전트. filesystem MCP로 data/market_catalog 파일만 읽음.",
    model="gemini-2.5-flash",
    instruction=MARKET_PLAN_PROMPT,
    tools=[
        McpToolset(
            connection_params=StdioServerParameters(
                command="npx",
                args=["-y", "@modelcontextprotocol/server-filesystem", MARKET_DATA_ABS],
            ),
            tool_filter=_READ_ONLY_TOOLS,
        )
    ],
    output_key="market_plan",
)
