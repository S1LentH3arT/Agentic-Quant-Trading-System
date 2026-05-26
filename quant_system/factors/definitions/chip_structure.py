#!/usr/bin/env python3
"""
L4 筹码结构因子 — 股本/股东人数/机构占比/解禁
大部分由Agent/AKShare填充，系统做范围校验。
"""

import numpy as np
import pandas as pd
from quant_system.factors.registry import FactorDefinition, get_registry

R = get_registry()


def _compute_share_capital(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """股本适中标记"""
    result = pd.DataFrame(index=df.index)
    result['market_cap'] = 0          # 总市值(亿) — Agent填充
    result['cap_fit_score'] = 0       # 1=适中(50-500亿) 0=过小/过大
    return result


def _compute_holder_structure(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """股东人数变化 — Agent填充"""
    result = pd.DataFrame(index=df.index)
    result['holder_count'] = 0
    result['holder_decline_q'] = 0    # 连续4季递减
    result['holder_concentration'] = 0  # 0~1 筹码集中度
    return result


def _compute_institutional_ratio(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """机构持仓占比 — Agent填充"""
    result = pd.DataFrame(index=df.index)
    result['inst_holder_ratio'] = 0   # 机构占总流通比
    result['inst_quality'] = 0        # 0~1 机构质量(基金>险资>牛散)
    return result


def _compute_lockup_risk(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """解禁压力 — Agent填充"""
    result = pd.DataFrame(index=df.index)
    result['near_lockup'] = 0         # 近1月有限售解禁
    result['lockup_ratio'] = 0        # 解禁数量/流通股
    result['insider_reduction'] = 0   # 近1月减持公告
    return result


SHARE_CAP = FactorDefinition(
    name="SHARE_CAP", layer=4, category="chip_structure",
    params={}, requires=[],
    output_columns=["market_cap", "cap_fit_score"],
    layer_weight=0.25,
)
R.register(SHARE_CAP)
R.set_compute_fn("SHARE_CAP", _compute_share_capital)

HOLDER_STRUCTURE = FactorDefinition(
    name="HOLDER_STRUCTURE", layer=4, category="chip_structure",
    params={}, requires=[],
    output_columns=["holder_count", "holder_decline_q", "holder_concentration"],
    layer_weight=0.30,
)
R.register(HOLDER_STRUCTURE)
R.set_compute_fn("HOLDER_STRUCTURE", _compute_holder_structure)

INST_RATIO = FactorDefinition(
    name="INST_RATIO", layer=4, category="chip_structure",
    params={}, requires=[],
    output_columns=["inst_holder_ratio", "inst_quality"],
    layer_weight=0.25,
)
R.register(INST_RATIO)
R.set_compute_fn("INST_RATIO", _compute_institutional_ratio)

LOCKUP_RISK = FactorDefinition(
    name="LOCKUP_RISK", layer=4, category="chip_structure",
    params={}, requires=[],
    output_columns=["near_lockup", "lockup_ratio", "insider_reduction"],
    layer_weight=0.20,
)
R.register(LOCKUP_RISK)
R.set_compute_fn("LOCKUP_RISK", _compute_lockup_risk)
