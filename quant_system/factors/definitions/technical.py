#!/usr/bin/env python3
"""
L6 技术趋势因子 — DKX/A1X/箱体/均线角度/量能/多周期共振
从 tdx-mcp/indicator_engine.py 核心算法迁移。
"""

import numpy as np
import pandas as pd
from quant_system.factors.registry import FactorDefinition, get_registry

R = get_registry()

# ── 参数 ──
def _p(path: str, default):
    try:
        from quant_system.evolution.param_loader import get_param
        return get_param(path, default)
    except Exception:
        return default

BOX_N = _p('indicator_engine.box_period', 13)
VOL_MULT1 = _p('indicator_engine.vol_mult1', 1.5)
VOL_MULT2 = _p('indicator_engine.vol_mult2', 2.0)
ANGLE_STRONG = _p('indicator_engine.angle_strong', 15)
ANGLE_WEAK = _p('indicator_engine.angle_weak', 10)
ZF_WEAK_LOW = 3
ZF_WEAK_HIGH = 5
HIGH_RISE = _p('indicator_engine.high_rise_warn', 30)
STOP_LOSS_PCT = _p('indicator_engine.stop_loss_pct', 5)


# ═══════════════════════════════════════════════
# 因子计算函数
# ═══════════════════════════════════════════════

def _compute_dkx(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """DKX 多空线"""
    o, h, l, c = df['open'], df['high'], df['low'], df['close']
    period = params.get('period', 20)
    smooth = params.get('smooth', 5)

    dkjz = (3*c + o + l + h) / 6
    dkx = pd.Series(0.0, index=df.index)
    weights = list(range(period, 0, -1))
    for i in range(period, len(dkx)):
        num = sum(weights[j] * dkjz.iloc[i - j] for j in range(period))
        dkx.iloc[i] = num / sum(range(1, period+1))
    dkx.iloc[:period] = np.nan

    result = pd.DataFrame(index=df.index)
    result['DKX'] = dkx
    result['SMX'] = dkx.rolling(smooth).mean()
    result['dkx_up'] = (dkx > dkx.shift(1)).astype(int)
    return result


def _compute_a1x(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """A1X 资金动量 + DZT/ZZJC 金叉死叉"""
    c = df['close']
    fast = params.get('fast', 10)
    slow = params.get('slow', 14)
    shift = params.get('shift', 1)

    ema_fast = c.ewm(span=fast, adjust=False).mean()
    ema_slow = c.ewm(span=slow, adjust=False).mean()
    a1x = (ema_fast - ema_slow.shift(shift)) / ema_slow.shift(shift) * 100

    result = pd.DataFrame(index=df.index)
    result['A1X'] = a1x
    result['DZT'] = ((a1x > 0) & (a1x.shift(1) <= 0)).astype(int)
    result['ZZJC'] = ((a1x < 0) & (a1x.shift(1) >= 0)).astype(int)
    result['a1x_direction'] = np.where(a1x > a1x.shift(1), 1,
                                np.where(a1x < a1x.shift(1), -1, 0))
    return result


def _compute_box(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """箱体 (N周期最高/最低/位置百分比)"""
    h, l, c = df['high'], df['low'], df['close']
    period = params.get('period', BOX_N)

    result = pd.DataFrame(index=df.index)
    result['box_high'] = h.rolling(period).max()
    result['box_low'] = l.rolling(period).min()
    result['box_position'] = (c - result['box_low']) / (result['box_high'] - result['box_low']) * 100
    result['box_breakout'] = (c > result['box_high']).astype(int)
    return result


def _compute_ma_angles(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """均线角度 (MA5/MA10/MA20/MA60/MA120, 度)"""
    c = df['close']
    result = pd.DataFrame(index=df.index)
    for p in [5, 10, 20, 60, 120]:
        ma = c.rolling(p).mean()
        angle = np.degrees(np.arctan((ma / ma.shift(1) - 1) * 100))
        result[f'MA{p}'] = ma
        result[f'MA{p}_ANGLE'] = angle
    return result


def _compute_volume_ratio(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """量比 + 放量/缩量标记"""
    v = df['volume']
    vol5 = v.rolling(5).mean()
    vol_ratio = v / vol5

    result = pd.DataFrame(index=df.index)
    result['vol_ratio'] = vol_ratio
    result['FANGLIANG15'] = (vol_ratio >= VOL_MULT1).astype(int)
    result['FANGLIANG2'] = (vol_ratio >= VOL_MULT2).astype(int)
    result['WULIANG'] = (vol_ratio < VOL_MULT1).astype(int)
    return result


def _compute_price_change(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """涨跌幅 + 30日涨幅 + 涨停检测"""
    c = df['close']
    result = pd.DataFrame(index=df.index)
    result['ZF'] = (c - c.shift(1)) / c.shift(1) * 100
    result['RISE30'] = (c - c.shift(30)) / c.shift(30) * 100
    zt_price = c.shift(1) * 1.10
    result['ZT'] = (c >= (zt_price - 0.005)).astype(int)
    return result


def _compute_trend_classify(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """走势分类: STRONG / WEAK / FAKE"""
    result = pd.DataFrame(index=df.index)

    if 'MA5_ANGLE' not in df.columns or 'DZT' not in df.columns:
        return result

    angle_strong = (df['MA5_ANGLE'] > ANGLE_STRONG) & (df['MA10_ANGLE'] > ANGLE_STRONG) & (df['MA20_ANGLE'] > ANGLE_STRONG)

    angle_weak = ((df['MA5_ANGLE'] > ANGLE_WEAK) & (df['MA5_ANGLE'] <= ANGLE_WEAK) &
                  (df['MA10_ANGLE'] > ANGLE_WEAK) & (df['MA10_ANGLE'] <= ANGLE_WEAK) &
                  (df['MA20_ANGLE'] > ANGLE_WEAK) & (df['MA20_ANGLE'] <= ANGLE_WEAK))

    has_vol15 = df.get('FANGLIANG15', pd.Series(0, index=df.index)).astype(bool)
    has_vol2 = df.get('FANGLIANG2', pd.Series(0, index=df.index)).astype(bool)
    has_wuliang = df.get('WULIANG', pd.Series(0, index=df.index)).astype(bool)
    has_zt = df.get('ZT', pd.Series(0, index=df.index)).astype(bool)
    has_dzt = df['DZT'].astype(bool)
    has_rise30 = df['RISE30'] > HIGH_RISE
    has_zf = df['ZF']

    result['STRONG'] = (has_dzt & has_vol2 & has_zt & angle_strong & (df['close'] > df.get('box_high', df['close']))).astype(int)
    result['WEAK'] = (has_dzt & has_vol15 & (~has_vol2) &
                      (has_zf >= ZF_WEAK_LOW) & (has_zf <= ZF_WEAK_HIGH) &
                      angle_weak & (df['close'] > df.get('box_high', df['close']))).astype(int)
    result['FAKE'] = (has_dzt & (has_wuliang | has_rise30)).astype(int)
    return result


def _compute_stop_line(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """跟踪止损线: DZT触发后5日内按收盘-STOP_LOSS_PCT%"""
    stop_pct = params.get('stop_pct', STOP_LOSS_PCT)
    result = pd.DataFrame(index=df.index, data={'stop_line': np.nan})
    buy_price = np.nan
    bars_since = 0
    has_dzt = 'DZT' in df.columns
    has_zzjc = 'ZZJC' in df.columns

    for i in df.index:
        if has_dzt and df.loc[i, 'DZT']:
            buy_price = df.loc[i, 'close']
            bars_since = 0
        elif pd.notna(buy_price):
            bars_since += 1
        if pd.notna(buy_price) and bars_since <= 5:
            if not (has_zzjc and df.loc[i, 'ZZJC']):
                result.loc[i, 'stop_line'] = buy_price * (1 - stop_pct / 100)
    return result


def _compute_multi_period(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """多周期共振: 日/周/月线方向一致标记"""
    result = pd.DataFrame(index=df.index)
    # 日线方向 (5日MA斜率)
    if 'MA5' in df.columns:
        result['daily_trend'] = (df['MA5'] > df['MA5'].shift(5)).astype(int)
    # 站上60/120日均线
    if all(c in df.columns for c in ['MA60', 'MA120']):
        result['above_ma60'] = (df['close'] > df['MA60']).astype(int)
        result['above_ma120'] = (df['close'] > df['MA120']).astype(int)
        result['ma_aligned'] = ((df['MA60'] > df['MA60'].shift(10)) &
                                (df['MA120'] > df['MA120'].shift(10))).astype(int)
    return result


# ═══════════════════════════════════════════════
# 注册 L6 因子
# ═══════════════════════════════════════════════

DKX_FACTOR = FactorDefinition(
    name="DKX", layer=6, category="technical",
    params={"period": {"value": 20, "range": [10, 30], "desc": "DKX周期"},
            "smooth": {"value": 5, "range": [3, 10], "desc": "SMX平滑周期"}},
    requires=["open", "high", "low", "close"],
    output_columns=["DKX", "SMX", "dkx_up"],
    layer_weight=0.20,
)
R.register(DKX_FACTOR)
R.set_compute_fn("DKX", _compute_dkx)

A1X_FACTOR = FactorDefinition(
    name="A1X", layer=6, category="technical",
    params={"fast": {"value": 10, "range": [5, 20], "desc": "快EMA周期"},
            "slow": {"value": 14, "range": [10, 30], "desc": "慢EMA周期"},
            "shift": {"value": 1, "range": [1, 3], "desc": "偏移日数"}},
    requires=["close"],
    output_columns=["A1X", "DZT", "ZZJC", "a1x_direction"],
    layer_weight=0.20,
)
R.register(A1X_FACTOR)
R.set_compute_fn("A1X", _compute_a1x)

BOX_FACTOR = FactorDefinition(
    name="BOX", layer=6, category="technical",
    params={"period": {"value": BOX_N, "range": [8, 20], "desc": "箱体周期"}},
    requires=["high", "low", "close"],
    output_columns=["box_high", "box_low", "box_position", "box_breakout"],
    layer_weight=0.15,
)
R.register(BOX_FACTOR)
R.set_compute_fn("BOX", _compute_box)

MA_ANGLE_FACTOR = FactorDefinition(
    name="MA_ANGLE", layer=6, category="technical",
    params={},
    requires=["close"],
    output_columns=["MA5", "MA10", "MA20", "MA60", "MA120",
                    "MA5_ANGLE", "MA10_ANGLE", "MA20_ANGLE", "MA60_ANGLE", "MA120_ANGLE"],
    layer_weight=0.15,
)
R.register(MA_ANGLE_FACTOR)
R.set_compute_fn("MA_ANGLE", _compute_ma_angles)

VOL_RATIO_FACTOR = FactorDefinition(
    name="VOL_RATIO", layer=6, category="technical",
    params={},
    requires=["volume"],
    output_columns=["vol_ratio", "FANGLIANG15", "FANGLIANG2", "WULIANG"],
    layer_weight=0.10,
)
R.register(VOL_RATIO_FACTOR)
R.set_compute_fn("VOL_RATIO", _compute_volume_ratio)

PRICE_CHG_FACTOR = FactorDefinition(
    name="PRICE_CHG", layer=6, category="technical",
    params={},
    requires=["close"],
    output_columns=["ZF", "RISE30", "ZT"],
    layer_weight=0.05,
)
R.register(PRICE_CHG_FACTOR)
R.set_compute_fn("PRICE_CHG", _compute_price_change)

TREND_CLS_FACTOR = FactorDefinition(
    name="TREND_CLS", layer=6, category="technical",
    params={},
    requires=["close", "DZT", "MA5_ANGLE", "MA10_ANGLE", "MA20_ANGLE"],
    output_columns=["STRONG", "WEAK", "FAKE"],
    layer_weight=0.05,
)
R.register(TREND_CLS_FACTOR)
R.set_compute_fn("TREND_CLS", _compute_trend_classify)

STOP_LINE_FACTOR = FactorDefinition(
    name="STOP_LINE", layer=6, category="technical",
    params={"stop_pct": {"value": STOP_LOSS_PCT, "range": [3, 8], "desc": "止损幅度%"}},
    requires=["close"],
    output_columns=["stop_line"],
    layer_weight=0.05,
)
R.register(STOP_LINE_FACTOR)
R.set_compute_fn("STOP_LINE", _compute_stop_line)

MULTI_PERIOD_FACTOR = FactorDefinition(
    name="MULTI_PERIOD", layer=6, category="technical",
    params={},
    requires=["close", "MA5", "MA60", "MA120"],
    output_columns=["daily_trend", "above_ma60", "above_ma120", "ma_aligned"],
    layer_weight=0.05,
)
R.register(MULTI_PERIOD_FACTOR)
R.set_compute_fn("MULTI_PERIOD", _compute_multi_period)
