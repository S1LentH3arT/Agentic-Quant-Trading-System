#!/usr/bin/env python3
"""
轻量回测 — Agent 快速实验用，不计仓位/成本，仅评分+因子相关性
"""

import numpy as np
import pandas as pd
from quant_system.factors.engine import FactorEngine
from quant_system.strategy.scorer import Scorer


class LightBacktest:
    """Agent 快速验证用轻量回测"""

    def __init__(self):
        self.engine = FactorEngine()
        self.scorer = Scorer()

    def run(self, klines: dict[str, pd.DataFrame]) -> dict:
        """
        快速评估: 对每只标的每日评分 → 统计信号频率和评分分布
        """
        results = {}
        for sym, df in klines.items():
            if df is None or len(df) < 40:
                continue
            try:
                df = self.engine.compute(df.copy(), layers=[6])
                scores = []
                for i in range(40, len(df)):
                    sc = self.scorer.score(df.iloc[:i+1], sym)
                    if not sc.get("veto"):
                        scores.append(sc["score"])

                if scores:
                    results[sym] = {
                        "avg_score": round(np.mean(scores), 1),
                        "max_score": max(scores),
                        "buy_signals": sum(1 for s in scores if s >= 6),
                        "signal_ratio": round(sum(1 for s in scores if s >= 6) / len(scores) * 100, 1),
                    }
            except Exception:
                pass
        return results

    def quick_ic(self, factor_name: str, symbols: list[str],
                 count: int = 60, forward_days: int = 5) -> dict:
        """快速 IC 测试: factor_t 与 future_N_day_return 的相关系数"""
        from quant_system.data.bus import get_bus
        bus = get_bus()

        ics = []
        for sym in symbols[:30]:
            klines = bus.get_daily([sym], count=count)
            df = klines.get(sym)
            if df is None or len(df) < count - 10:
                continue
            df = self.engine.compute(df, layers=[6])

            fd = self.engine.registry.get(factor_name)
            if not fd or not fd.output_columns:
                continue
            col = fd.output_columns[0]
            if col not in df.columns:
                continue

            factor_vals = df[col].values[:-forward_days]
            fwd_returns = (df['close'].shift(-forward_days) / df['close'] - 1).values[:-forward_days]
            valid = ~(np.isnan(factor_vals) | np.isnan(fwd_returns))
            if valid.sum() > 10:
                ic = np.corrcoef(factor_vals[valid], fwd_returns[valid])[0, 1]
                ics.append(ic)

        if ics:
            return {"mean_ic": round(np.mean(ics), 4), "std_ic": round(np.std(ics), 4),
                    "count": len(ics), "factor": factor_name}
        return {"mean_ic": 0, "std_ic": 0, "count": 0, "factor": factor_name}
