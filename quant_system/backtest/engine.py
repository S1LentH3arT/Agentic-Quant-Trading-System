#!/usr/bin/env python3
"""
完整回测引擎 — 与实盘共用 strategy → risk → execution 代码路径。
从 tdx-mcp/backtest_engine.py 迁移，适配 quant_system。
"""

import numpy as np
import pandas as pd
from quant_system.factors.engine import FactorEngine
from quant_system.strategy.scorer import Scorer, get_summary
from quant_system.backtest.metrics import compute_metrics
from quant_system.execution.broker import SimulatedBroker


class FullBacktestEngine:
    """完整回测 — 与实盘同引擎"""

    def __init__(self, initial_capital: float = 100000,
                 slippage: float = 0.001, commission: float = 0.0003):
        self.initial_capital = initial_capital
        self.broker = SimulatedBroker(slippage=slippage, commission=commission)
        self.factor_engine = FactorEngine()
        self.scorer = Scorer()
        self.trades = []
        self.equity_curve = []

    def run(self, df: pd.DataFrame, symbol: str = "") -> dict:
        """
        单标回测。
        df 必须含 OHLCV 列，由因子引擎自动计算指标。
        """
        df = self.factor_engine.compute(df.copy(), layers=[6])
        self.trades = []
        capital = self.initial_capital
        position = 0
        entry_price = 0
        entry_date = None
        self.equity_curve = [capital]

        for i in range(40, len(df)):
            row = df.iloc[i]
            prev = df.iloc[i - 1]
            close = float(row['close'])

            # ── 入场 ──
            if position == 0:
                a1x = float(row.get('A1X', 0))
                a1x_prev = float(prev.get('A1X', 0))
                box_pos = float(row.get('box_position', 100) or 100)
                vol_ratio = float(row.get('vol_ratio', 0) or 0)
                dkx_up = bool(row.get('dkx_up', 0))
                no_zzjc = not bool(row.get('ZZJC', 0))

                a1x_cross = a1x > 0 and a1x_prev <= 0
                box_ok = 0 <= box_pos <= 40
                vol_ok = vol_ratio >= 1.2

                if a1x_cross and box_ok and vol_ok and no_zzjc:
                    position = capital / close
                    entry_price = close
                    entry_date = i
                    capital = 0

            # ── 离场 ──
            elif position > 0:
                zzjc = bool(row.get('ZZJC', 0))
                pnl_pct = (close - entry_price) / entry_price * 100
                hold_days = i - entry_date
                exit_signal = False
                exit_reason = ""

                if pnl_pct <= -11:
                    exit_signal = True
                    exit_reason = "止损"
                elif zzjc:
                    exit_signal = True
                    exit_reason = "ZZJC"
                elif hold_days >= 15 and pnl_pct < 3:
                    exit_signal = True
                    exit_reason = "时间止损"

                if exit_signal:
                    capital = position * close * (1 - 0.0003)
                    self.trades.append({
                        "symbol": symbol,
                        "entry_price": round(entry_price, 2),
                        "exit_price": round(close, 2),
                        "pnl_pct": round(pnl_pct, 2),
                        "hold_days": hold_days,
                        "exit_reason": exit_reason,
                    })
                    position = 0
                    entry_price = 0
                    entry_date = None

            equity = capital + (position * close if position > 0 else 0)
            self.equity_curve.append(equity)

        # 强制平仓
        if position > 0:
            close = float(df.iloc[-1]['close'])
            capital = position * close * (1 - 0.0003)
            pnl_pct = (close - entry_price) / entry_price * 100
            self.trades.append({
                "symbol": symbol,
                "entry_price": round(entry_price, 2),
                "exit_price": round(close, 2),
                "pnl_pct": round(pnl_pct, 2),
                "hold_days": len(df) - entry_date,
                "exit_reason": "持仓到期",
            })

        return compute_metrics(self.trades, self.equity_curve, self.initial_capital)

    def run_multi(self, klines: dict[str, pd.DataFrame]) -> dict:
        """多标回测"""
        all_trades = []
        all_metrics = []

        for sym, df in klines.items():
            if df is None or len(df) < 50:
                continue
            try:
                metrics = self.run(df, sym)
                if metrics.get('trade_count', 0) > 0:
                    all_metrics.append({"symbol": sym, **metrics})
                    all_trades.extend(self.trades)
            except Exception:
                pass

        if not all_metrics:
            return {"error": "无有效回测结果"}

        df_m = pd.DataFrame(all_metrics)
        return {
            "total_tested": len(klines),
            "profitable": int((df_m['total_return_pct'] > 0).sum()),
            "total_trades": int(df_m['trade_count'].sum()),
            "aggregate_metrics": {
                "win_rate": round(df_m['win_rate'].mean(), 1),
                "payoff_ratio": round(df_m['payoff_ratio'].mean(), 2),
                "sharpe_ratio": round(df_m['sharpe_ratio'].mean(), 2),
                "max_drawdown_pct": round(df_m['max_drawdown_pct'].max(), 1),
                "avg_total_return": round(df_m['total_return_pct'].mean(), 1),
            },
            "top_performers": df_m.nlargest(10, 'total_return_pct')[
                ['symbol', 'total_return_pct', 'win_rate', 'sharpe_ratio']
            ].to_dict('records'),
            "all_results": df_m.to_dict('records'),
        }
