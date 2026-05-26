#!/usr/bin/env python3
"""
QuantResearchAgent — 非结构化数据 → 结构化量化特征
不做交易决策，不产报告文本。输出可直接计算的纯数值。
"""

from quant_system.agents.base import ResearchAgent


class QuantResearchAgent(ResearchAgent):
    """市场数据 → 量化特征"""

    system_prompt = """
你是一个量化数据解析器。你的任务是把市场原始数据转化为可计算的结构化特征。

规则：
1. 每一项输出必须来源于输入数据，禁止编造数值
2. 不确定的值输出 null，不要猜测
3. 所有数值输出必须落在指定的 [min, max] 区间内
4. 输出严格 JSON，不得包含解释性文字
5. 板块名/代码必须来自输入数据，不得自创
"""

    output_schema = {
        "L1_industry": {"type": "list", "default": []},
        "L2_capital": {"type": "list", "default": []},
        "L3_fundamentals": {"type": "list", "default": []},
        "L4_chip": {"type": "list", "default": []},
        "L7_risk": {"type": "list", "default": []},
        "pool_candidates": {"type": "list", "default": []},
        "market_features": {"type": "dict", "default": {}},
    }

    def analyze(self, hot_rank: list = None, sector_flow: list = None,
                news_headlines: list = None, financials: dict = None) -> dict:
        """
        分析市场数据，返回结构化量化特征。
        所有输入均为从 data/provider 获取的原始数据。
        """
        context = {
            "hot_rank": hot_rank or [],
            "sector_flow": sector_flow or [],
            "news": news_headlines or [],
            "financials": financials or {},
        }
        return self.run(**context)

    def analyze_research(self, report_texts: list[str]) -> dict:
        """
        解析研报/政策文本，提取结构化信号。
        """
        context = {
            "reports": report_texts,
            "task": "extract_catalysts",
        }
        return self.run(**context)
