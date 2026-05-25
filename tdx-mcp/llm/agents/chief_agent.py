# tdx-mcp/llm/agents/chief_agent.py
"""沛总 Agent — 交叉验证 + 最终裁决 + 复盘"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from llm.agent_base import BaseAgent
from llm.context_compressor import compress_level2, compress_level3


class ChiefAgent(BaseAgent):
    name = "chief"

    def build_context(
        self,
        intel_output: dict = None,
        technical_output: dict = None,
        discovery_output: dict = None,
        deployment_output: dict = None,
        sector_results: dict = None,
        market_data: dict = None,
        **kwargs,
    ) -> str:
        parts = []

        if intel_output:
            parts.append("## 情报 Agent 输出")
            parts.append(f"高共识: {intel_output.get('high_consensus',[])}")
            parts.append(f"板块方向: {intel_output.get('sector_direction',[])}")
            parts.append(f"市场状态: {intel_output.get('market_state','?')}")
            parts.append(f"漏判: {intel_output.get('missed',[])}")

        if technical_output:
            parts.append("\n## 技术 Agent 输出")
            qualified = technical_output.get('qualified', [])
            vetoed = technical_output.get('vetoed', [])
            parts.append(f"合格: {len(qualified)} 只")
            parts.append(f"否决: {len(vetoed)} 只")
            for q in qualified[:5]:
                parts.append(f"  {q.get('symbol','?')} score={q.get('score',0)} confidence={q.get('confidence','?')}")
            parts.append(f"板块洞察: {technical_output.get('sector_insight','')}")

        if discovery_output:
            parts.append("\n## 发现 Agent 输出")
            parts.append(f"新候选: {len(discovery_output.get('new_candidates',[]))} 只")
            parts.append(f"板块覆盖: {discovery_output.get('sector_coverage','')}")

        if deployment_output:
            parts.append("\n## 调度 Agent 输出")
            parts.append(f"动作: {deployment_output.get('action','?')}")
            parts.append(f"标的: {deployment_output.get('symbol','')}")
            parts.append(f"手数: {deployment_output.get('lots',0)}")
            parts.append(f"理由: {deployment_output.get('reason','')}")
            parts.append(f"风险: {deployment_output.get('risk_note','')}")

        if sector_results:
            parts.append(f"\n## 板块全景\n{compress_level2(sector_results)}")

        if market_data:
            parts.append(f"\n## 市场三指标\n{compress_level3(market_data)}")

        return "\n".join(parts) if parts else "无数据"


class ReviewAgent(BaseAgent):
    """复盘 Agent — 交易完成后总结经验"""
    name = "review"

    def build_context(
        self,
        trade_record: dict = None,
        agent_decisions: dict = None,
        sector_performance: dict = None,
        **kwargs,
    ) -> str:
        parts = []
        if trade_record:
            parts.append("## 交易记录")
            parts.append(f"标的: {trade_record.get('symbol','?')}")
            parts.append(f"买入: {trade_record.get('entry_price',0)} | "
                        f"卖出: {trade_record.get('exit_price',0)} | "
                        f"持仓: {trade_record.get('hold_days',0)}天")
            parts.append(f"盈亏: {trade_record.get('pnl_pct',0):+.2f}%")

        if agent_decisions:
            parts.append("\n## 各 Agent 决策记录")
            for agent_name, decision in agent_decisions.items():
                parts.append(f"- {agent_name}: {json.dumps(decision, ensure_ascii=False)[:200]}")

        if sector_performance:
            parts.append(f"\n## 同期板块表现\n{compress_level2(sector_performance)}")

        return "\n".join(parts) if parts else "无数据"
