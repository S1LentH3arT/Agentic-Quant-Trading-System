#!/usr/bin/env python3
"""
订单管理器 — 订单生命周期: PENDING → CONFIRMED → SENT → FILLED/CANCELLED
"""

from datetime import datetime
from quant_system.execution.confirm import confirm
from quant_system.storage.journal import save_order_raw


class OrderManager:
    """订单管理器"""

    def __init__(self, broker):
        self.broker = broker

    def execute(self, approved: list[dict]) -> list[dict]:
        """
        对风控通过的订单逐一: 弹窗确认 → 发送 → 记录
        返回: [{accepted, symbol, error, ...}]
        """
        results = []
        for order in approved:
            # 同花顺断开 → 不下单
            if not self.broker.is_ready():
                results.append({"accepted": False, "symbol": order.get("symbol", ""),
                                "error": "同花顺未连接"})
                continue

            # 弹窗确认
            if not confirm(order):
                results.append({"accepted": False, "symbol": order.get("symbol", ""),
                                "error": "用户取消"})
                continue

            # 发送
            result = self.broker.send(order)

            # 记录日志
            if result.get("accepted"):
                try:
                    save_order_raw(
                        action=order["action"],
                        symbol=order["symbol"],
                        name="",
                        price=order["price"],
                        lots=order["lots"],
                        capital=order["price"] * order["lots"] * 100,
                        reason=order.get("reason", ""),
                        status="PENDING",
                    )
                except Exception:
                    pass

            results.append({**result, "symbol": order.get("symbol", "")})

        return results
