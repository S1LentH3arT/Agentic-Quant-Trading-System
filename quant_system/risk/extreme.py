#!/usr/bin/env python3
"""
极端场景检测 — 5种停机条件 (从 tdx-mcp/rolling_capital.py 迁移)
"""

from quant_system.evolution.param_loader import get_param


class ExtremeDetector:
    """5种停机条件 + Agent风险特征叠加"""

    def check(self, sh_pct: float, monthly_dd_pct: float,
              consecutive_losses: int, agent_risk: dict = None) -> dict:
        """
        返回: {extreme: bool, reason: str, action: str, suspend_days: int}
        action: "LIQUIDATE" | "HOLD_CASH" | None
        """
        agent_risk = agent_risk or {}
        triggers = []

        index_drop = get_param('rolling_capital.extreme_index_drop', -5)
        dd_limit = get_param('rolling_capital.extreme_drawdown', 15)
        suspend = get_param('rolling_capital.suspend_days', 3)

        # 1. 上证暴跌
        if sh_pct <= index_drop:
            triggers.append((f"上证跌幅{sh_pct}% > {index_drop}%", "全仓卖出停3天"))

        # 2. 月度回撤
        if monthly_dd_pct <= -dd_limit:
            triggers.append((f"月度回撤{monthly_dd_pct}% > {dd_limit}%", "暂停3天"))

        # 3. 连续止损
        if consecutive_losses >= 3:
            triggers.append(("连续3笔止损", "暂停1天"))

        # 4. Agent: 全板块双杀
        drawdown_sectors = agent_risk.get("sector_drawdown_flag", [])
        if len(drawdown_sectors) >= 3:
            triggers.append(("全板块双杀", "持现等信号"))

        # 5. Agent: 补偿性反弹
        if agent_risk.get("compensatory_rally"):
            return {"extreme": True,
                    "reason": "补偿性反弹: 昨日普跌+今日反弹，不参与",
                    "action": "HOLD_CASH", "suspend_days": 0}

        if triggers:
            first_trigger = triggers[0]
            action = "LIQUIDATE" if "暴跌" in first_trigger[0] else "HOLD_CASH"
            days = 3 if "大跌" in first_trigger[0] or "回撤" in first_trigger[0] else 1
            return {
                "extreme": True,
                "reason": "; ".join(f"{t}: {r}" for t, r in triggers),
                "action": action,
                "suspend_days": days,
            }

        return {"extreme": False, "reason": "", "action": None, "suspend_days": 0}
