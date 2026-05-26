#!/usr/bin/env python3
"""
因子计算引擎 — 对 DataFrame 批量运行已激活因子。
"""

import pandas as pd
import numpy as np
from typing import Callable

from quant_system.factors.registry import FactorRegistry, get_registry


class FactorEngine:
    """因子计算引擎"""

    def __init__(self, registry: FactorRegistry = None):
        self.registry = registry or get_registry()
        self._load_all_compute_fns()

    def _load_all_compute_fns(self):
        """导入所有因子定义文件，触发注册"""
        import quant_system.factors.definitions.technical  # L6 核心
        import quant_system.factors.definitions.industry    # L1
        import quant_system.factors.definitions.capital_flow  # L2
        import quant_system.factors.definitions.fundamentals  # L3
        import quant_system.factors.definitions.chip_structure  # L4
        import quant_system.factors.definitions.liquidity     # L5
        import quant_system.factors.definitions.risk_filter   # L7

    def compute(self, df: pd.DataFrame, layers: list[int] = None) -> pd.DataFrame:
        """对单个 DataFrame 跑已激活因子"""
        active = self.registry.list_active()
        for name in active:
            fd = self.registry.get(name)
            if fd is None:
                continue
            if layers and fd.layer not in layers:
                continue
            if not self._requirements_met(df, fd.requires):
                continue
            fn = self.registry.get_compute_fn(name)
            if fn is None:
                continue
            try:
                params = self.registry.current_params(name)
                result = fn(df, params)
                for col in fd.output_columns:
                    if col in result.columns:
                        df[col] = result[col]
            except Exception as e:
                pass  # 单因子失败不影响其他因子
        return df

    def compute_batch(self, klines: dict[str, pd.DataFrame],
                      layers: list[int] = None) -> dict[str, pd.DataFrame]:
        """批量计算"""
        results = {}
        for sym, df in klines.items():
            if df is not None and len(df) > 0:
                results[sym] = self.compute(df.copy(), layers)
        return results

    def _requirements_met(self, df: pd.DataFrame, required: list) -> bool:
        return all(r in df.columns for r in required)

    def get_layer_scores(self, df: pd.DataFrame, symbol: str) -> dict:
        """获取各层因子值 (用于评分引擎)"""
        layer_scores = {}
        for layer in range(1, 8):
            names = self.registry.list_by_layer(layer)
            values = {}
            for name in names:
                fd = self.registry.get(name)
                if fd:
                    for col in fd.output_columns:
                        if col in df.columns:
                            values[col] = float(df[col].iloc[-1]) if len(df) > 0 else 0.0
            layer_scores[f"L{layer}"] = values
        return layer_scores
