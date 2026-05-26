#!/usr/bin/env python3
"""
L7 风控排雷因子 — 硬性剔除规则。
科创板/ETF/ST 剔除、亏损剔除、造假/减持/质押/商誉/高位 风险标记。
"""

import numpy as np
import pandas as pd
from quant_system.factors.registry import FactorDefinition, get_registry

R = get_registry()


def _compute_board_exclude(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """科创板(688) + ETF + ST 标记 (在symbol层面处理，此处为DataFrame标记)"""
    result = pd.DataFrame(index=df.index)
    # 由 scorer 在 symbol 层面处理，此处预留
    result['board_exclude'] = 0
    result['is_st'] = 0
    return result


def _compute_loss_exclude(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """业绩亏损标记 — 需配合财报数据"""
    result = pd.DataFrame(index=df.index)
    result['loss_warning'] = 0  # 由Agent L3填充
    result['deducted_negative'] = 0
    return result


def _compute_bubble_exclude(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """高位翻倍风险 + 纯概念无业绩"""
    result = pd.DataFrame(index=df.index)
    c = df['close']

    # 60日涨幅 > 100% 标记
    if len(c) > 60:
        rise60 = (c - c.shift(60)) / c.shift(60) * 100
        result['bubble_risk'] = (rise60 > 100).astype(int)
        result['rise_60d_pct'] = rise60
    else:
        result['bubble_risk'] = 0
        result['rise_60d_pct'] = 0

    # 30日涨幅 > 50% 也算高风险
    if len(c) > 30:
        rise30 = (c - c.shift(30)) / c.shift(30) * 100
        result['bubble_30d'] = (rise30 > 50).astype(int)
    else:
        result['bubble_30d'] = 0

    return result


def _compute_insider_risk(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """内幕风险标记 — 需配合公告数据"""
    result = pd.DataFrame(index=df.index)
    result['insider_sell_flag'] = 0    # 减持标记 (Agent填充)
    result['pledge_risk'] = 0          # 质押>50% (Agent填充)
    result['goodwill_risk'] = 0        # 商誉>30% (Agent填充)
    return result


def _compute_chaos_exclude(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """主营杂乱标记 — Agent填充"""
    result = pd.DataFrame(index=df.index)
    result['chaos_flag'] = 0
    result['fraud_risk'] = 0
    return result


# ── 注册 L7 因子 ──

BOARD_EXCLUDE = FactorDefinition(
    name="BOARD_EXCLUDE", layer=7, category="risk_filter",
    params={}, requires=[],
    output_columns=["board_exclude", "is_st"],
    layer_weight=0.20,
)
R.register(BOARD_EXCLUDE)
R.set_compute_fn("BOARD_EXCLUDE", _compute_board_exclude)

LOSS_EXCLUDE = FactorDefinition(
    name="LOSS_EXCLUDE", layer=7, category="risk_filter",
    params={}, requires=[],
    output_columns=["loss_warning", "deducted_negative"],
    layer_weight=0.20,
)
R.register(LOSS_EXCLUDE)
R.set_compute_fn("LOSS_EXCLUDE", _compute_loss_exclude)

BUBBLE_EXCLUDE = FactorDefinition(
    name="BUBBLE_EXCLUDE", layer=7, category="risk_filter",
    params={}, requires=["close"],
    output_columns=["bubble_risk", "rise_60d_pct", "bubble_30d"],
    layer_weight=0.20,
)
R.register(BUBBLE_EXCLUDE)
R.set_compute_fn("BUBBLE_EXCLUDE", _compute_bubble_exclude)

INSIDER_RISK = FactorDefinition(
    name="INSIDER_RISK", layer=7, category="risk_filter",
    params={}, requires=[],
    output_columns=["insider_sell_flag", "pledge_risk", "goodwill_risk"],
    layer_weight=0.20,
)
R.register(INSIDER_RISK)
R.set_compute_fn("INSIDER_RISK", _compute_insider_risk)

CHAOS_EXCLUDE = FactorDefinition(
    name="CHAOS_EXCLUDE", layer=7, category="risk_filter",
    params={}, requires=[],
    output_columns=["chaos_flag", "fraud_risk"],
    layer_weight=0.20,
)
R.register(CHAOS_EXCLUDE)
R.set_compute_fn("CHAOS_EXCLUDE", _compute_chaos_exclude)
