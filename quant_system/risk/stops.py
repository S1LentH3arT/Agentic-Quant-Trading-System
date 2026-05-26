#!/usr/bin/env python3
"""
止损管理 — 四维度止损 (从 tdx-mcp/heartbeat.py 迁移概念)
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass


@dataclass
class StopLevels:
    hard_stop: float = 0        # 硬止损 -11%
    atr_stop: float = 0         # ATR动态止损
    trailing_stop: float = 0    # DZT跟踪止损 -5%
    time_stop_days: int = 15    # 时间止损天数
    time_stop_pct: float = 3.0  # 持仓15天盈利<3%触发


class StopManager:
    """四维度止损计算"""

    def compute_all(self, df: pd.DataFrame, entry_price: float,
                    atr_period: int = 14) -> StopLevels:
        """返回四个止损价"""
        return StopLevels(
            hard_stop=round(entry_price * 0.89, 2),
            atr_stop=self._atr_stop(df, atr_period),
            trailing_stop=self._trailing_stop(df, entry_price),
            time_stop_days=15,
            time_stop_pct=3.0,
        )

    def active_stop(self, levels: StopLevels, days_held: int,
                    current_pnl_pct: float) -> float:
        """返回当前应使用的实际止损价 (最紧的)"""
        candidates = []
        if levels.hard_stop > 0:
            candidates.append(levels.hard_stop)
        if levels.atr_stop > 0:
            candidates.append(levels.atr_stop)
        if levels.trailing_stop > 0:
            candidates.append(levels.trailing_stop)

        if days_held > levels.time_stop_days and current_pnl_pct < levels.time_stop_pct:
            return -1  # 时间止损触发信号

        return max(candidates) if candidates else levels.hard_stop

    def _atr_stop(self, df: pd.DataFrame, period: int = 14, mult: float = 2.0) -> float:
        """ATR动态止损: 收盘价 - mult*ATR"""
        if len(df) < period:
            return 0
        h, l, c = df['high'], df['low'], df['close']
        tr = pd.concat([
            h - l,
            (h - c.shift(1)).abs(),
            (l - c.shift(1)).abs(),
        ], axis=1).max(axis=1)
        atr = tr.rolling(period).mean().iloc[-1]
        close = float(c.iloc[-1])
        return round(close - mult * atr, 2) if atr > 0 else 0

    def _trailing_stop(self, df: pd.DataFrame, entry_price: float) -> float:
        """DZT跟踪止损: 入场价*(1-5%)"""
        from quant_system.evolution.param_loader import get_param
        stop_pct = get_param('indicator_engine.stop_loss_pct', 5)
        return round(entry_price * (1 - stop_pct / 100), 2)
