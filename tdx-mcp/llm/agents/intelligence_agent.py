# tdx-mcp/llm/agents/intelligence_agent.py
"""情报 Agent — AKShare 拉数据 → LLM 交叉验证"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from llm.agent_base import BaseAgent
from llm.context_compressor import compress_level3


class IntelligenceAgent(BaseAgent):
    name = "intelligence"

    def build_context(self, hot_rank: list = None, cls_news: list = None,
                      sector_flow: list = None, market_data: dict = None, **kwargs) -> str:
        parts = []

        if hot_rank:
            parts.append("## 东方财富热榜 TOP30")
            for i, item in enumerate(hot_rank[:30]):
                parts.append(f"{i+1}. {item.get('code','?')} {item.get('name','?')} "
                           f"price={item.get('price','?')} chg={item.get('change_pct',0):+.2f}%")

        if cls_news:
            parts.append("\n## 财联社早间电报")
            for i, item in enumerate(cls_news[:10]):
                parts.append(f"{i+1}. {item}")

        if sector_flow:
            parts.append("\n## 行业板块资金流 TOP5")
            for item in sector_flow[:5]:
                parts.append(f"- {item}")

        if market_data:
            parts.append(f"\n## 市场宏观\n{compress_level3(market_data)}")

        return "\n".join(parts) if parts else "无数据"
