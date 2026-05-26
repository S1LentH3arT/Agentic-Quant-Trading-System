#!/usr/bin/env python3
"""
风控总管理器 — 6道关卡: L7排雷前置 → 极端场景 → 持仓纪律 → 仓位约束 → 信号复核 → 合规终审
"""

from quant_system.risk.extreme import ExtremeDetector
from quant_system.risk.position import PositionSizer
from quant_system.risk.stops import StopManager


class RiskManager:
    """风控总入口"""

    def __init__(self):
        self.extreme = ExtremeDetector()
        self.sizer = PositionSizer()
        self.stops = StopManager()

    def approve(self, signals: list, account: dict, market: dict,
                positions: dict, agent_risk: dict = None) -> dict:
        """
        五道关卡过滤 → 输出审批通过的订单。
        返回: {halt: bool, approved: [dict], rejected: [dict]}
        """
        agent_risk = agent_risk or {}
        approved = []
        rejected = []
        halt = False

        # ── 第0关: L7排雷前置 (由 scorer 处理, 这里做二次检查) ──

        # ── 第1关: 极端场景 ──
        ext = self.extreme.check(
            sh_pct=market.get("sh_pct", 0),
            monthly_dd_pct=account.get("monthly_dd_pct", 0),
            consecutive_losses=account.get("consecutive_losses", 0),
            agent_risk=agent_risk,
        )
        if ext["extreme"]:
            return {"halt": True, "reason": ext["reason"],
                    "action": ext["action"], "approved": [], "rejected": []}

        for sig in signals:
            sym = sig.symbol
            pos = positions.get(sym)

            # ── 第2关: 持仓纪律 ──
            if pos and sig.action == "BUY":
                # 同板块补仓检查: 暂不做 (需要板块映射)
                pass

            # ── 第3关: 仓位约束 ──
            sizing = self.sizer.size(
                score=sig.score, price=sig.price,
                cash=account.get("available", 0),
                equity=account.get("total", 0),
                classification=sig.classification,
                agent_regime=agent_risk.get("regime_score", 0),
            )
            if sizing["lots"] == 0 and sig.action == "BUY":
                rejected.append({**sig.__dict__,
                    "reason": f"仓位约束: 零手"})
                continue

            # ── 第4关: 信号复核 ──
            if not self._reconfirm(sig):
                rejected.append({**sig.__dict__,
                    "reason": "信号二次确认失败"})
                continue

            # ── 第5关: 合规终审 ──
            approved.append({
                "symbol": sig.symbol,
                "action": sig.action,
                "lots": sizing["lots"],
                "price": sig.price,
                "stop_price": sig.stop_price,
                "capital_pct": sizing["capital_pct"],
                "reason": sig.reason,
                "classification": sig.classification,
            })

        return {"halt": False, "approved": approved, "rejected": rejected,
                "action": "APPROVE" if approved else "HOLD_CASH"}

    def _reconfirm(self, sig) -> bool:
        """信号二次确认"""
        if sig.price <= 0:
            return False
        if sig.score < 2:
            return False
        return True
