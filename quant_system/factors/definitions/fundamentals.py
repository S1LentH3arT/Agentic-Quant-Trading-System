#!/usr/bin/env python3
"""
L3 财报内核因子 — 扣非/毛利/现金流/商誉/质押/PE分位
部分由系统计算(PE分位)，部分由Agent/AKShare财报API填充。
"""

import numpy as np
import pandas as pd
from quant_system.factors.registry import FactorDefinition, get_registry

R = get_registry()


def _compute_pe_pb_percentile(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """PE/PB 估值分位标记 — Agent/AKShare填充"""
    result = pd.DataFrame(index=df.index)
    result['pe_percentile'] = 50.0    # PE近5年分位 (越小越低估)
    result['pb_percentile'] = 50.0    # PB近5年分位
    result['undervalue_signal'] = 0   # 分位<20% 标记
    return result


def _compute_deducted_quality(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """扣非利润质量 — Agent填充"""
    result = pd.DataFrame(index=df.index)
    result['deducted_np_growth'] = 0   # 扣非净利润增速
    result['revenue_growth'] = 0       # 营收增速
    result['quarterly_acceleration'] = 0  # 季度环比加速
    return result


def _compute_gross_margin(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """毛利率趋势 — Agent填充"""
    result = pd.DataFrame(index=df.index)
    result['gross_margin'] = 0
    result['margin_trend'] = 0  # 1上升 0平稳 -1下降
    return result


def _compute_cf_quality(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """经营现金流质量 — Agent填充"""
    result = pd.DataFrame(index=df.index)
    result['op_cf_positive'] = 0    # 经营现金流>0
    result['cf_match_profit'] = 0   # 现金流匹配利润
    return result


def _compute_risk_flags(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """商誉/质押风险 — Agent填充"""
    result = pd.DataFrame(index=df.index)
    result['goodwill_ratio'] = 0      # 商誉/总资产
    result['pledge_ratio'] = 0        # 质押率
    result['debt_risk'] = 0           # 大额负债风险
    return result


PE_PB = FactorDefinition(
    name="PE_PB", layer=3, category="fundamentals",
    params={}, requires=[],
    output_columns=["pe_percentile", "pb_percentile", "undervalue_signal"],
    layer_weight=0.20,
)
R.register(PE_PB)
R.set_compute_fn("PE_PB", _compute_pe_pb_percentile)

DEDUCTED_QUALITY = FactorDefinition(
    name="DEDUCTED_QUALITY", layer=3, category="fundamentals",
    params={}, requires=[],
    output_columns=["deducted_np_growth", "revenue_growth", "quarterly_acceleration"],
    layer_weight=0.25,
)
R.register(DEDUCTED_QUALITY)
R.set_compute_fn("DEDUCTED_QUALITY", _compute_deducted_quality)

GROSS_MARGIN = FactorDefinition(
    name="GROSS_MARGIN", layer=3, category="fundamentals",
    params={}, requires=[],
    output_columns=["gross_margin", "margin_trend"],
    layer_weight=0.20,
)
R.register(GROSS_MARGIN)
R.set_compute_fn("GROSS_MARGIN", _compute_gross_margin)

CF_QUALITY = FactorDefinition(
    name="CF_QUALITY", layer=3, category="fundamentals",
    params={}, requires=[],
    output_columns=["op_cf_positive", "cf_match_profit"],
    layer_weight=0.20,
)
R.register(CF_QUALITY)
R.set_compute_fn("CF_QUALITY", _compute_cf_quality)

RISK_FLAGS = FactorDefinition(
    name="RISK_FLAGS", layer=3, category="fundamentals",
    params={}, requires=[],
    output_columns=["goodwill_ratio", "pledge_ratio", "debt_risk"],
    layer_weight=0.15,
)
R.register(RISK_FLAGS)
R.set_compute_fn("RISK_FLAGS", _compute_risk_flags)
