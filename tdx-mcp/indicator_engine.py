#!/usr/bin/env python3
"""
综合决策王 量化版 — Python 原生实现
绕过 TradingView 会员限制, 基于 TDX 数据直接计算所有指标 + 出图
"""

import numpy as np
import pandas as pd
from datetime import datetime
from typing import Optional

# ============================================================
# 参数 (与 Pine Script 版本完全一致)
# ============================================================
N = 13             # 箱体周期
VOL_MULT1 = 1.5    # 放量基准
VOL_MULT2 = 2.0    # 强走势放量
ANGLE_STRONG = 15  # 强走势角度
ANGLE_WEAK = 10    # 弱走势角度
ZF_WEAK_LOW = 3    # 弱走势涨幅下限
ZF_WEAK_HIGH = 5   # 弱走势涨幅上限
HIGH_RISE = 30     # 高位预警30日涨幅
STOP_LOSS = 5      # 止损幅度

# ============================================================
# 数据加载
# ============================================================

def load_kline(symbol: str, count: int = 300) -> pd.DataFrame:
    """从数据适配器拉取日线 (TDX主源 + AKShare备用)"""
    from data_adapter import load_kline as adapter_load
    symbol = _clean(symbol)
    return adapter_load(symbol, count)


def _clean(symbol: str) -> str:
    return symbol.replace("SZSE:", "").replace("SSE:", "").replace(".SZ", "").replace(".SH", "").split(":")[-1]


# ============================================================
# 指标计算
# ============================================================

def calc_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """计算全部综合决策王指标，附加到 DataFrame"""
    o, h, l, c, v = df['open'], df['high'], df['low'], df['close'], df['volume']

    # ── DKX 多空线 ──
    dkjz = (3*c + o + l + h) / 6
    dkx = pd.Series(0.0, index=df.index)
    weights = list(range(20, 0, -1))  # 20,19,...,1
    for i in range(20, len(dkx)):
        num = sum(weights[j] * dkjz.iloc[i - j] for j in range(20))
        dkx.iloc[i] = num / 210
    dkx.iloc[:20] = np.nan
    df['DKX'] = dkx
    df['SMX'] = dkx.rolling(5).mean()
    df['dkx_up'] = dkx > dkx.shift(1)

    # ── A1X 资金动量 ──
    ema10 = c.ewm(span=10, adjust=False).mean()
    ema14 = c.ewm(span=14, adjust=False).mean()
    df['A1X'] = (ema10 - ema14.shift(1)) / ema14.shift(1) * 100
    df['DZT'] = (df['A1X'] > 0) & (df['A1X'].shift(1) <= 0)   # 上穿
    df['ZZJC'] = (df['A1X'] < 0) & (df['A1X'].shift(1) >= 0)  # 下穿

    # ── 箱体 ──
    df['box_high'] = h.rolling(N).max()
    df['box_low'] = l.rolling(N).min()
    df['box_position'] = (c - df['box_low']) / (df['box_high'] - df['box_low']) * 100

    # ── 均线 & 角度 ──
    ma5 = c.rolling(5).mean()
    ma10 = c.rolling(10).mean()
    ma20 = c.rolling(20).mean()
    df['MA5_ANGLE'] = np.degrees(np.arctan((ma5/ma5.shift(1) - 1) * 100))
    df['MA10_ANGLE'] = np.degrees(np.arctan((ma10/ma10.shift(1) - 1) * 100))
    df['MA20_ANGLE'] = np.degrees(np.arctan((ma20/ma20.shift(1) - 1) * 100))

    # ── 量能 ──
    vol5 = v.rolling(5).mean()
    df['vol_ratio'] = v / vol5
    df['FANGLIANG15'] = df['vol_ratio'] >= VOL_MULT1
    df['FANGLIANG2'] = df['vol_ratio'] >= VOL_MULT2
    df['WULIANG'] = df['vol_ratio'] < VOL_MULT1

    # ── 涨幅 ──
    df['ZF'] = (c - c.shift(1)) / c.shift(1) * 100
    df['RISE30'] = (c - c.shift(30)) / c.shift(30) * 100
    zt_price = c.shift(1) * 1.10
    df['ZT'] = c >= (zt_price - 0.005)

    # ── 走势分类 ──
    angle_strong = (df['MA5_ANGLE'] > ANGLE_STRONG) & (df['MA10_ANGLE'] > ANGLE_STRONG) & (df['MA20_ANGLE'] > ANGLE_STRONG)
    angle_weak = (df['MA5_ANGLE'] > ANGLE_WEAK) & (df['MA5_ANGLE'] <= ANGLE_WEAK) & \
                 (df['MA10_ANGLE'] > ANGLE_WEAK) & (df['MA10_ANGLE'] <= ANGLE_WEAK) & \
                 (df['MA20_ANGLE'] > ANGLE_WEAK) & (df['MA20_ANGLE'] <= ANGLE_WEAK)
    df['STRONG'] = df['DZT'] & df['FANGLIANG2'] & df['ZT'] & angle_strong & (c > df['box_high'])
    df['WEAK'] = df['DZT'] & df['FANGLIANG15'] & (~df['FANGLIANG2']) & \
                 (df['ZF'] >= ZF_WEAK_LOW) & (df['ZF'] <= ZF_WEAK_HIGH) & angle_weak & (c > df['box_high'])
    df['FAKE'] = df['DZT'] & (df['WULIANG'] | (df['RISE30'] > HIGH_RISE))

    # ── 止损线 (简化: DZT触发后按收盘价−5%) ──
    buy_price = np.nan
    stop_line_series = pd.Series(np.nan, index=df.index)
    bars_since = 0
    for i in df.index:
        if df.loc[i, 'DZT']:
            buy_price = df.loc[i, 'close']
            bars_since = 0
        elif pd.notna(buy_price):
            bars_since += 1
        if pd.notna(buy_price) and bars_since <= 5 and not df.loc[i, 'ZZJC']:
            stop_line_series.loc[i] = buy_price * (1 - STOP_LOSS/100)
    df['stop_line'] = stop_line_series

    return df


# ============================================================
# 最新信号摘要
# ============================================================

def get_summary(df: pd.DataFrame, symbol: str = "") -> dict:
    """从指标 DataFrame 提取最新信号"""
    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else last

    def safe(v, default=0):
        return float(v) if pd.notna(v) else default

    dkx_val = safe(last['DKX'])
    dkx_prev = safe(prev['DKX'])
    a1x_val = safe(last['A1X'])
    a1x_prev = safe(prev['A1X'])
    vol20 = df['volume'].tail(20).mean()

    return {
        "symbol": symbol,
        "date": str(last.name) if hasattr(last, 'name') else "",
        "close": safe(last['close']),
        "DKX": round(dkx_val, 2),
        "dkx_direction": "↑" if dkx_val > dkx_prev else "↓" if dkx_val < dkx_prev else "→",
        "SMX": round(safe(last['SMX']), 2),
        "A1X": round(a1x_val, 2),
        "a1x_direction": "↑" if a1x_val > a1x_prev else "↓" if a1x_val < a1x_prev else "→",
        "DZT": bool(last['DZT']),
        "ZZJC": bool(last['ZZJC']),
        "box_high": round(safe(last['box_high']), 2),
        "box_low": round(safe(last['box_low']), 2),
        "box_position_pct": round(safe(last['box_position']), 1),
        "vol_ratio": round(safe(last['vol_ratio']), 2),
        "vol_20_avg": int(vol20),
        "change_pct": round(safe(last['ZF']), 2),
        "strong_trend": bool(last['STRONG']),
        "weak_trend": bool(last['WEAK']),
        "fake_break": bool(last['FAKE']),
        "stop_loss": round(safe(last['stop_line']), 2),
        "ma5_angle": round(safe(last['MA5_ANGLE']), 1),
    }


# ============================================================
# 筛选评分 (来自 sector_rotation_playbook)
# ============================================================

def score_stock(df: pd.DataFrame) -> dict:
    """按铁律滤网评分 — 加强版: DKX趋势+日内结构+量价配合"""
    s = get_summary(df)
    score = 0
    details = []

    # === 前置否决条件 ===
    # DKX连续3日下降 → 一票否决
    dkx_vals = df['DKX'].tail(5).dropna()
    if len(dkx_vals) >= 4:
        dkx_trend = all(dkx_vals.iloc[i] > dkx_vals.iloc[i+1] for i in range(len(dkx_vals)-2))
        if dkx_trend:
            return {"score": 0, "details": ["否决: DKX连续下降,空头趋势"], "summary": s, "veto": True}

    # 日内冲高回落: 今日最高>开+2% 且 收<开 → 量价背离
    last = df.iloc[-1]
    intraday_pump = (last['high'] - last['open']) / last['open'] > 0.02 and last['close'] < last['open']
    if intraday_pump and float(last['vol_ratio']) > 1.2:
        score -= 2
        details.append("扣分: 放量冲高回落,疑似出货")

    # === 滤网2: A1X (3日趋势, 非单日) ===
    a1x = s['A1X']
    a1x_vals = df['A1X'].tail(3).dropna()
    a1x_rising = len(a1x_vals) >= 2 and a1x_vals.iloc[-1] > a1x_vals.iloc[-2] and a1x_vals.iloc[-2] >= a1x_vals.iloc[-3]
    if -3 <= a1x <= 2 and a1x_rising:
        score += 3; details.append(f"A1X={a1x:.2f} 金叉区且3日上升(A级)")
    elif -5 <= a1x < -1 and a1x_rising:
        score += 2; details.append(f"A1X={a1x:.2f} 深水反弹,3日上升(B级)")
    elif -3 <= a1x <= 2:
        score += 1; details.append(f"A1X={a1x:.2f} 金叉区但未确认上升(B级)")
    elif a1x > 2:
        score += 1; details.append(f"A1X={a1x:.2f} 追晚(C级)")

    # === 滤网3: 箱体位置 ===
    pos = s['box_position_pct']
    if 0 <= pos <= 15:
        score += 3; details.append(f"箱体{pos:.0f}% 安全(A级)")
    elif 15 < pos <= 35:
        score += 2; details.append(f"箱体{pos:.0f}% 可接受(B级)")
    elif 35 < pos <= 60:
        score += 1; details.append(f"箱体{pos:.0f}% 偏高(C级)")

    # === 滤网4: 量能 ===
    vr = s['vol_ratio']
    chg_pct = s['change_pct']
    if 1.5 <= vr <= 2.5 and chg_pct > 0:
        score += 3; details.append(f"量能{vr:.1f}x 放量收阳(A级)")
    elif 1.5 <= vr <= 2.5:
        score += 2; details.append(f"量能{vr:.1f}x 放量但收阴(B级)")
    elif 1.0 <= vr < 1.5:
        score += 2; details.append(f"量能{vr:.1f}x 温和放量(B级)")
    elif vr > 2.5 and chg_pct > 0:
        score += 2; details.append(f"量能{vr:.1f}x 天量收阳(B级)")
    elif vr > 2.5:
        score += 1; details.append(f"量能{vr:.1f}x 天量阴线(C级)")

    return {"score": max(0, score), "details": details, "summary": s, "veto": False}
