#!/usr/bin/env python3
"""
L5 流动性因子 — 日均成交额/换手率/供需拐点/独立抗跌
纯K线数据计算，不依赖外部API。
"""

import numpy as np
import pandas as pd
from quant_system.factors.registry import FactorDefinition, get_registry

R = get_registry()


def _compute_avg_turnover(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """日均成交额稳定性 (20日均)"""
    v = df['volume']
    c = df['close']
    result = pd.DataFrame(index=df.index)

    # 成交额 = 成交量 × 收盘价 的近似
    amount = v * c
    result['amount_ma20'] = amount.rolling(20).mean()
    # 成交额稳定性: 当日成交额 / 20日均成交额
    result['amount_stability'] = amount / result['amount_ma20']
    # 成交额萎缩警告
    result['amount_shrink'] = (result['amount_stability'] < 0.5).astype(int)
    return result


def _compute_turnover_health(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """换手率适中 — 既无过度炒作也无流动性枯竭"""
    result = pd.DataFrame(index=df.index)

    if 'turnover' in df.columns:
        turnover = df['turnover']
    else:
        # 换手率估算: 成交量/流通股本 (粗略估算)
        v = df['volume']
        turnover = v / v.rolling(60).mean() * 2  # 粗略替代

    result['turnover_ma5'] = turnover.rolling(5).mean()
    # 健康区间: 1%-8% 换手率
    t = result['turnover_ma5']
    result['turnover_healthy'] = ((t >= 1) & (t <= 8)).astype(int)
    # 过度炒作>15% / 死水<0.3%
    result['turnover_extreme'] = ((t > 15) | (t < 0.3)).astype(int)
    return result


def _compute_supply_demand(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """供需拐点: 卖压衰竭+买盘递增"""
    result = pd.DataFrame(index=df.index)
    v = df['volume']
    c = df['close']
    o = df['open']

    # 量价配合: 放量阳线 vs 缩量阴线
    up_day = (c > o).astype(int)
    down_day = (c < o).astype(int)

    # 5日净买盘比例
    vol_up = (v * up_day).rolling(5).sum()
    vol_down = (v * down_day).rolling(5).sum()
    result['buy_pressure'] = vol_up / (vol_up + vol_down + 1)

    # 卖压衰竭: 下跌日缩量至5日均量的50%以下连续2天
    result['sell_exhaustion'] = ((down_day == 1) & (v < v.rolling(5).mean() * 0.5)).rolling(2).sum()
    result['sell_exhaustion'] = (result['sell_exhaustion'] >= 2).astype(int)

    # 供需拐点: 卖压衰竭 + 买盘>50%
    result['supply_demand_inflection'] = (
        (result['sell_exhaustion'] == 1) & (result['buy_pressure'] > 0.55)
    ).astype(int)

    return result


def _compute_independent_strength(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """独立抗跌属性 — 不受大盘涨跌绑架"""
    result = pd.DataFrame(index=df.index)
    c = df['close']

    # 5日连续阳线比例
    up_streak = ((c > c.shift(1)).astype(int).rolling(5).sum())
    result['up_streak_5d'] = up_streak
    # 抗跌得分: 5日中至少3日收阳
    result['independent_score'] = (up_streak >= 3).astype(int)

    # 20日最大回撤 (日内)
    h20 = df['high'].rolling(20).max()
    result['max_dd_20d'] = (c - h20) / h20 * 100

    return result


# ── 注册 L5 因子 ──

AVG_TURNOVER = FactorDefinition(
    name="AVG_TURNOVER", layer=5, category="liquidity",
    params={},
    requires=["volume", "close"],
    output_columns=["amount_ma20", "amount_stability", "amount_shrink"],
    layer_weight=0.25,
)
R.register(AVG_TURNOVER)
R.set_compute_fn("AVG_TURNOVER", _compute_avg_turnover)

TURNOVER_HEALTH = FactorDefinition(
    name="TURNOVER_HEALTH", layer=5, category="liquidity",
    params={},
    requires=["volume"],
    output_columns=["turnover_ma5", "turnover_healthy", "turnover_extreme"],
    layer_weight=0.25,
)
R.register(TURNOVER_HEALTH)
R.set_compute_fn("TURNOVER_HEALTH", _compute_turnover_health)

SUPPLY_DEMAND = FactorDefinition(
    name="SUPPLY_DEMAND", layer=5, category="liquidity",
    params={},
    requires=["open", "close", "volume"],
    output_columns=["buy_pressure", "sell_exhaustion", "supply_demand_inflection"],
    layer_weight=0.25,
)
R.register(SUPPLY_DEMAND)
R.set_compute_fn("SUPPLY_DEMAND", _compute_supply_demand)

INDEPENDENT = FactorDefinition(
    name="INDEPENDENT", layer=5, category="liquidity",
    params={},
    requires=["close", "high"],
    output_columns=["up_streak_5d", "independent_score", "max_dd_20d"],
    layer_weight=0.25,
)
R.register(INDEPENDENT)
R.set_compute_fn("INDEPENDENT", _compute_independent_strength)
