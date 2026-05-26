#!/usr/bin/env python3
"""
券商适配器 — Broker抽象 + THSBroker(easytrader实现)
从 tdx-mcp/trading_adapter.py 迁移。
"""

import sys, os
from quant_system.config import get_path

# 引用 tdx-mcp/connection.py (不碰旧文件)
_tdx_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tdx-mcp")
sys.path.insert(0, _tdx_path)
from connection import ConnectionManager


class Broker:
    """券商适配器抽象基类"""
    def send(self, order: dict) -> dict: raise NotImplementedError
    def get_account(self) -> dict: raise NotImplementedError
    def get_positions(self) -> list[dict]: raise NotImplementedError
    def is_ready(self) -> bool: raise NotImplementedError


class THSBroker(Broker):
    """同花顺 easytrader 实现"""

    def __init__(self, exe_path: str = None):
        self.exe_path = exe_path or r'C:\同花顺软件\同花顺\xiadan.exe'
        self._mgr = ConnectionManager(
            name="easytrader",
            factory=self._create,
            health_check=self._ping,
            max_retries=3,
            retry_delay=3.0,
        )

    def _create(self):
        from easytrader import use
        t = use('ths')
        t.connect(self.exe_path)
        return t

    def _ping(self, t) -> bool:
        try:
            return t.balance is not None
        except Exception:
            return False

    def is_ready(self) -> bool:
        return self._mgr.is_healthy()

    def send(self, order: dict) -> dict:
        """
        order: {symbol, action, price, lots}
        返回: {accepted: bool, error: str}
        """
        t = self._mgr.get()
        try:
            if order["action"] == "BUY":
                t.buy(order["symbol"], order["price"], order["lots"] * 100)
            elif order["action"] == "SELL":
                t.sell(order["symbol"], order["price"], order["lots"] * 100)
            return {"accepted": True, "error": ""}
        except Exception as e:
            return {"accepted": False, "error": str(e)}

    def get_account(self) -> dict:
        t = self._mgr.get()
        try:
            b = t.balance
            return {
                'total': float(b.get('总资产', 0)),
                'available': float(b.get('可用金额', 0)),
                'balance': float(b.get('资金余额', 0)),
                'market_value': float(b.get('股票市值', 0)),
            }
        except Exception:
            return {'total': 0, 'available': 0, 'balance': 0, 'market_value': 0}

    def get_positions(self) -> list[dict]:
        t = self._mgr.get()
        try:
            raw = t.position
            if not raw:
                return []
            result = []
            for p in raw:
                shares = int(p.get('当前拥股', 0))
                if shares > 0:
                    result.append({
                        'symbol': str(p.get('证券代码', '')),
                        'name': str(p.get('证券名称', '')),
                        'lots': shares // 100,
                        'cost': float(p.get('成本价', 0)),
                        'price': float(p.get('市价', 0)),
                        'market_value': float(p.get('市值', 0)),
                        'pnl': float(p.get('盈亏', 0)),
                        'pnl_pct': float(p.get('盈亏比例(%)', 0)),
                    })
            return result
        except Exception:
            return []

    def cancel_all(self):
        t = self._mgr.get()
        try:
            t.cancel_all_entrusts()
        except Exception:
            pass


class SimulatedBroker(Broker):
    """回测用模拟券商 — 次日开盘价撮合"""

    def __init__(self, slippage: float = 0.001, commission: float = 0.0003):
        self.slippage = slippage
        self.commission = commission
        self._account = {'total': 100000, 'available': 100000, 'balance': 100000, 'market_value': 0}
        self._positions = {}

    def is_ready(self) -> bool:
        return True

    def send(self, order: dict) -> dict:
        fill_price = order["price"] * (1 + self.slippage * (1 if order["action"] == "BUY" else -1))
        cost = fill_price * order["lots"] * 100 * (1 + self.commission)

        if order["action"] == "BUY":
            if cost > self._account['available']:
                return {"accepted": False, "error": "资金不足"}
            self._account['available'] -= cost
            self._account['market_value'] += cost
            self._positions[order["symbol"]] = order
        elif order["action"] == "SELL":
            if order["symbol"] in self._positions:
                self._account['available'] += cost
                self._account['market_value'] -= cost
                del self._positions[order["symbol"]]

        self._account['total'] = self._account['available'] + self._account['market_value']
        return {"accepted": True, "error": "", "fill_price": round(fill_price, 2)}

    def get_account(self) -> dict:
        return dict(self._account)

    def get_positions(self) -> list[dict]:
        return list(self._positions.values())
