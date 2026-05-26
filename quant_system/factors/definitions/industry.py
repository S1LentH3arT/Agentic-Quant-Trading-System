#!/usr/bin/env python3
"""
L1 产业宏观因子 — 板块景气度/资金流向方向/行业动量
基于 AKShare 行业板块数据计算，Agent 特征叠加。
"""

import numpy as np
import pandas as pd
from quant_system.factors.registry import FactorDefinition, get_registry

R = get_registry()


def _compute_sector_momentum(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """板块动量 — 基于板块内标的的平均趋势方向"""
    result = pd.DataFrame(index=df.index)
    if 'DKX' in df.columns and 'SMX' in df.columns:
        # DKX > SMX = 多头，持续天数越长动量越强
        dkx = df['DKX']
        smx = df['SMX']
        result['sector_momentum'] = ((dkx > smx).astype(int).rolling(10).sum() / 10)
    else:
        result['sector_momentum'] = 0.5
    return result


def _compute_industry_prosperity(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """行业景气度 — 板块涨幅排名 + 成交额占比"""
    result = pd.DataFrame(index=df.index)
    if 'A1X' in df.columns:
        a1x = df['A1X']
        # A1X > 0 且上升 = 景气上行
        result['prosperity_score'] = ((a1x > 0) & (a1x > a1x.shift(3))).astype(int).rolling(5).mean()
    else:
        result['prosperity_score'] = 0.5

    # 成交额趋势 (量增=景气)
    if 'volume' in df.columns:
        v = df['volume']
        result['volume_trend'] = (v.rolling(5).mean() / v.rolling(20).mean() - 1)
    else:
        result['volume_trend'] = 0

    return result


def _compute_policy_signal(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """政策底信号 — Agent填充，此处预留给结构化特征"""
    result = pd.DataFrame(index=df.index)
    result['policy_support'] = 0  # Agent: -1/0/+1
    result['research_catalyst'] = 0  # Agent: 0~1
    result['avoid_sector'] = 0  # Agent: 下行赛道标记
    return result


SECTOR_MOMENTUM = FactorDefinition(
    name="SECTOR_MOMENTUM", layer=1, category="industry",
    params={}, requires=["DKX", "SMX"],
    output_columns=["sector_momentum"],
    layer_weight=0.35,
)
R.register(SECTOR_MOMENTUM)
R.set_compute_fn("SECTOR_MOMENTUM", _compute_sector_momentum)

PROSPERITY = FactorDefinition(
    name="PROSPERITY", layer=1, category="industry",
    params={}, requires=["A1X", "volume"],
    output_columns=["prosperity_score", "volume_trend"],
    layer_weight=0.35,
)
R.register(PROSPERITY)
R.set_compute_fn("PROSPERITY", _compute_industry_prosperity)

POLICY_SIGNAL = FactorDefinition(
    name="POLICY_SIGNAL", layer=1, category="industry",
    params={}, requires=[],
    output_columns=["policy_support", "research_catalyst", "avoid_sector"],
    layer_weight=0.30,
)
R.register(POLICY_SIGNAL)
R.set_compute_fn("POLICY_SIGNAL", _compute_policy_signal)
