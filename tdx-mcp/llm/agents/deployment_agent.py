# tdx-mcp/llm/agents/deployment_agent.py
"""调度 Agent — Python 算仓位 → LLM 判断部署时机"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from llm.agent_base import BaseAgent


class DeploymentAgent(BaseAgent):
    name = "deployment"

    def build_context(self, qualified_top5: list = None, account: dict = None,
                      kelly_result: dict = None, extreme: dict = None, **kwargs) -> str:
        parts = []
        if qualified_top5:
            parts.append("## 技术 Agent 合格 TOP5")
            for i, q in enumerate(qualified_top5[:5]):
                parts.append(f"{i+1}. {q.get('symbol','?')} score={q.get('score',0)} "
                           f"A1X={q.get('A1X',0)}({q.get('a1x_dir','?')}) "
                           f"price={q.get('close',0)} box={q.get('box_pos',0)}%")

        if account:
            parts.append(f"\n## 账户状态\n"
                        f"总资产={account.get('total',0)} | "
                        f"可用={account.get('available',0)} | "
                        f"闲置天数={account.get('idle_days',0)}")

        if kelly_result:
            parts.append(f"\n## Kelly 仓位计算结果\n"
                        f"推荐仓位比例={kelly_result.get('fraction',0)}% | "
                        f"推荐手数={kelly_result.get('lots',0)}")

        if extreme and extreme.get("extreme"):
            parts.append(f"\n## ⚠️ 极端场景\n{extreme.get('reason','')} → {extreme.get('action','')}")

        return "\n".join(parts) if parts else "无数据"
