# tdx-mcp/llm/agents/technical_agent.py
"""技术 Agent — Python 算指标 → LLM 多周期综合解读"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from llm.agent_base import BaseAgent
from llm.context_compressor import compress_level1, compress_level2


class TechnicalAgent(BaseAgent):
    name = "technical"

    def build_context(self, main_pool_results: list = None,
                      sector_results: dict = None, **kwargs) -> str:
        parts = ["## 主力池单日快照 (22只)"]
        if main_pool_results:
            parts.append(compress_level1(main_pool_results, max_items=30))

        parts.append("\n## 板块聚合")
        if sector_results:
            parts.append(compress_level2(sector_results))

        return "\n".join(parts)
