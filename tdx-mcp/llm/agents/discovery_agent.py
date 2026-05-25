# tdx-mcp/llm/agents/discovery_agent.py
"""发现 Agent — Python 粗筛 → LLM 模式识别"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from llm.agent_base import BaseAgent
from llm.context_compressor import compress_level1


class DiscoveryAgent(BaseAgent):
    name = "discovery"

    def build_context(self, scan_results: list = None,
                      sector_direction: list = None, **kwargs) -> str:
        parts = []
        if scan_results:
            parts.append("## 快速扫描 TOP30")
            parts.append(compress_level1(scan_results, max_items=30, fields=[
                "A1X", "a1x_dir", "box_pos", "vol_ratio", "DZT"
            ]))
        if sector_direction:
            parts.append(f"\n## 热点板块方向\n{', '.join(sector_direction)}")
        return "\n".join(parts) if parts else "无数据"
