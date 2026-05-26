#!/usr/bin/env python3
"""
仓位计算器 — Kelly + 市场环境调节 + 分类加权
"""

from quant_system.evolution.param_loader import get_param


class PositionSizer:
    """Kelly仓位 + 多层约束"""

    def size(self, score: float, price: float, cash: float,
             equity: float, classification: str = "价值趋势",
             agent_regime: float = 0) -> dict:
        """
        返回: {lots, capital_pct, capital_used, kelly_fraction}
        """
        if price <= 0 or cash <= 0:
            return {"lots": 0, "capital_pct": 0, "capital_used": 0, "kelly_fraction": 0}

        # Kelly 基础
        kelly_base = get_param('orchestrator.kelly_base', 0.10)
        kelly_per = get_param('orchestrator.kelly_per_score', 0.05)
        kelly_cap = get_param('orchestrator.kelly_cap', 0.25)
        min_score = get_param('orchestrator.min_score_deploy', 6)

        if score < min_score:
            return {"lots": 0, "capital_pct": 0, "capital_used": 0, "kelly_fraction": 0}

        kelly_frac = min(kelly_base + (score - min_score) * kelly_per, kelly_cap)

        # 市场环境调节
        if agent_regime > 0.3:
            kelly_frac *= 1.10
        elif agent_regime < -0.3:
            kelly_frac *= 0.70

        # L8 分类加权
        class_mult = {
            "拐点反转": 1.2,
            "价值趋势": 1.0,
            "低位潜伏": 0.6,
        }.get(classification, 1.0)
        kelly_frac *= class_mult

        kelly_frac = max(0, min(kelly_frac, kelly_cap))

        # 合约价值约束
        max_lots = int(cash * kelly_frac / (price * 100))
        max_lots = min(max_lots, get_param('orchestrator.max_lots', 4))

        # 单票总市值不超过总权益30%
        equity_cap_lots = int(equity * 0.30 / (price * 100))
        lots = min(max_lots, equity_cap_lots)
        lots = max(0, lots)

        return {
            "lots": lots,
            "capital_pct": round(kelly_frac * 100, 1),
            "capital_used": round(price * lots * 100, 2),
            "kelly_fraction": round(kelly_frac, 4),
        }
