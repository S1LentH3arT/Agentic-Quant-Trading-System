#!/usr/bin/env python3
"""
L2 资金追踪因子 — 北向资金/主力大单方向/量价资金结构
"""

import numpy as np
import pandas as pd
from quant_system.factors.registry import FactorDefinition, get_registry

R = get_registry()


def _compute_main_force(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """主力大单行为: 阴线吸筹+阳线拉升, 下跌缩量+上涨放量"""
    result = pd.DataFrame(index=df.index)
    o, c, v = df['open'], df['close'], df['volume']
    ma20 = v.rolling(20).mean()

    # 阴线 (收<开) 但放量 → 潜在吸筹
    down_day = (c < o)
    up_day = (c >= o)

    # 吸筹信号: 阴线+放量(>MA20的1.5倍)
    result['accumulation'] = (down_day & (v > ma20 * 1.5)).astype(int)
    # 拉升信号: 阳线+放量(>MA20的2倍)
    result['push_up'] = (up_day & (v > ma20 * 2.0)).astype(int)
    # 出货信号: 阳线+缩量(<MA20的0.5倍)
    result['distribution'] = (up_day & (v < ma20 * 0.5)).astype(int)

    # 资金阶段判定: 5日吸筹次数 vs 出货次数
    acc5 = result['accumulation'].rolling(5).sum()
    dis5 = result['distribution'].rolling(5).sum()
    result['capital_phase'] = np.where(acc5 > dis5, 1,  # 吸筹
                                np.where(dis5 > acc5, -1, 0))  # 出货

    # 量价健康度: 上涨日成交量/下跌日成交量
    vol_up_sum = (v * up_day.astype(int)).rolling(10).sum()
    vol_down_sum = (v * down_day.astype(int)).rolling(10).sum()
    result['vol_health'] = vol_up_sum / (vol_down_sum + 1)
    return result


def _compute_north_flow(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """北向资金标记 — Agent/AKShare填充"""
    result = pd.DataFrame(index=df.index)
    result['north_direction'] = 0     # -1流出 0震荡 1流入
    result['north_duration'] = 0      # 连续加仓天数
    result['north_accumulated'] = 0   # 累计净买
    return result


def _compute_institution(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """机构持仓标记 — Agent/AKShare填充"""
    result = pd.DataFrame(index=df.index)
    result['institution_phase'] = 0   # -1减仓 0不变 1建仓 2加仓
    result['institution_ratio'] = 0   # 机构持仓比例
    return result


MAIN_FORCE = FactorDefinition(
    name="MAIN_FORCE", layer=2, category="capital_flow",
    params={}, requires=["open", "close", "volume"],
    output_columns=["accumulation", "push_up", "distribution", "capital_phase", "vol_health"],
    layer_weight=0.40,
)
R.register(MAIN_FORCE)
R.set_compute_fn("MAIN_FORCE", _compute_main_force)

NORTH_FLOW = FactorDefinition(
    name="NORTH_FLOW", layer=2, category="capital_flow",
    params={}, requires=[],
    output_columns=["north_direction", "north_duration", "north_accumulated"],
    layer_weight=0.30,
)
R.register(NORTH_FLOW)
R.set_compute_fn("NORTH_FLOW", _compute_north_flow)

INSTITUTION = FactorDefinition(
    name="INSTITUTION", layer=2, category="capital_flow",
    params={}, requires=[],
    output_columns=["institution_phase", "institution_ratio"],
    layer_weight=0.30,
)
R.register(INSTITUTION)
R.set_compute_fn("INSTITUTION", _compute_institution)
