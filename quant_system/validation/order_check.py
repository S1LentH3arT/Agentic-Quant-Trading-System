#!/usr/bin/env python3
"""
订单终审 — 资金/手数/价格 三重检查
"""

from quant_system.evolution.param_loader import get_param


class OrderCheck:
    def check(self, order: dict, account: dict) -> tuple[bool, str]:
        cost = order.get("price", 0) * order.get("lots", 0) * 100

        # 资金检查
        if order.get("action") == "BUY" and cost > account.get("available", 0):
            return False, f"资金不足: 需{cost:.0f} > 可用{account['available']:.0f}"

        # 手数检查
        lots = order.get("lots", 0)
        if lots < 1:
            return False, f"手数无效: {lots}"
        if lots > get_param('orchestrator.max_lots', 4):
            return False, f"手数超限: {lots}"

        # 价格检查
        price = order.get("price", 0)
        if price <= 0 or price > 10000:
            return False, f"价格异常: {price}"

        # 止损检查
        stop = order.get("stop_price", 0)
        if order.get("action") == "BUY" and stop > 0 and stop >= price:
            return False, f"止损价{stop} >= 买入价{price}"

        return True, "OK"
