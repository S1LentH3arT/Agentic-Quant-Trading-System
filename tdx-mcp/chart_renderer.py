#!/usr/bin/env python3
"""
综合决策王 图表渲染 — 绕过 TV 限制, 用 TDX 数据直接出图
"""

import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.font_manager as fm
import mplfinance as mpf
import pandas as pd
import numpy as np
import os
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import get_path, ensure_dir
from indicator_engine import calc_all_indicators, get_summary

# 修复中文显示
for fpath in fm.findSystemFonts():
    if 'msyh' in fpath.lower() or 'simhei' in fpath.lower() or 'simsun' in fpath.lower() or 'microsoft yahei' in fpath.lower():
        font_prop = fm.FontProperties(fname=fpath)
        plt.rcParams['font.family'] = font_prop.get_name()
        break
else:
    # 回退: 尝试常见中文字体
    for font_name in ['Microsoft YaHei', 'SimHei', 'SimSun', 'WenQuanYi Micro Hei', 'Noto Sans CJK SC']:
        try:
            plt.rcParams['font.family'] = font_name
            break
        except:
            pass
plt.rcParams['axes.unicode_minus'] = False


def render_chart(symbol: str, df: pd.DataFrame, save_path: str = None) -> str:
    """渲染综合决策王完整图表: K线 + DKX/SMX + 箱体 + A1X副图 + 量能"""
    df = calc_all_indicators(df.copy())
    s = get_summary(df, symbol)

    ohlc = df[['open','high','low','close','volume']].copy()
    if 'date' in df.columns:
        ohlc.index = pd.to_datetime(df['date'])
    elif not isinstance(ohlc.index, pd.DatetimeIndex):
        try:
            ohlc.index = pd.to_datetime(df.index)
        except:
            pass

    # 只显示最后80根K线
    ohlc = ohlc.tail(80)
    idx = ohlc.index
    df_tail = df.loc[idx] if hasattr(df, 'loc') else df.tail(80)

    ap = []
    # 主图叠加
    ap.append(mpf.make_addplot(df_tail['DKX'].values, color='#FFD700', width=1.0, panel=0))
    ap.append(mpf.make_addplot(df_tail['SMX'].values, color='#FF3333', width=1.0, panel=0))
    ap.append(mpf.make_addplot(df_tail['box_high'].values, color='#3366FF', width=0.8, panel=0, linestyle='--'))
    ap.append(mpf.make_addplot(df_tail['box_low'].values, color='#00CCCC', width=0.8, panel=0, linestyle='--'))

    # DZT 信号 (仅在有信号的地方标点)
    dzt_vals = np.full(len(df_tail), np.nan)
    for i, (idx_i, row) in enumerate(df_tail.iterrows()):
        if row['DZT']:
            dzt_vals[i] = row['low'] * 0.97
    if not np.all(np.isnan(dzt_vals)):
        ap.append(mpf.make_addplot(dzt_vals, type='scatter', marker='^', color='#3366FF', markersize=80, panel=0))

    # ZZJC 信号
    zzjc_vals = np.full(len(df_tail), np.nan)
    for i, (idx_i, row) in enumerate(df_tail.iterrows()):
        if row['ZZJC']:
            zzjc_vals[i] = row['high'] * 1.03
    if not np.all(np.isnan(zzjc_vals)):
        ap.append(mpf.make_addplot(zzjc_vals, type='scatter', marker='v', color='#00AA00', markersize=80, panel=0))

    # A1X 副图 (panel 1)
    ap.append(mpf.make_addplot(df_tail['A1X'].values, color='#9966FF', width=1.2, panel=1, ylabel='A1X'))
    ap.append(mpf.make_addplot(np.zeros(len(df_tail)), color='#444444', width=0.5, panel=1))

    # 量能 (panel 2)
    vol5 = df_tail['volume'].rolling(5).mean().values
    ap.append(mpf.make_addplot(vol5, color='#FFAA00', width=1.0, panel=2, ylabel='VOL'))

    title = f"{symbol}  |  DKX:{s['DKX']}{s['dkx_direction']}  A1X:{s['A1X']}{s['a1x_direction']}  箱体:{s['box_position_pct']:.0f}%  量:{s['vol_ratio']}x"

    fig, axes = mpf.plot(
        ohlc, type='candle', style='charles', title=title,
        addplot=ap, panel_ratios=(3, 1.2, 1),
        returnfig=True, figsize=(17, 10),
        warn_too_much_data=len(ohlc) + 50,
    )

    if save_path is None:
        save_path = os.path.join(ensure_dir("tdx-mcp", "charts"), f"{symbol}_{datetime.now().strftime('%Y%m%d_%H%M')}.png")
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    fig.savefig(save_path, dpi=130, bbox_inches='tight', facecolor='#1a1a2e')
    plt.close(fig)
    return save_path


def render_sector_grid(symbols: list[str], sector_name: str, save_path: str = None) -> str:
    """板块扫描表格图"""
    from indicator_engine import load_kline, get_summary as gs, calc_all_indicators as ca

    rows = []
    for sym in symbols:
        try:
            df = load_kline(sym, count=80)
            df = ca(df)
            rows.append(gs(df, sym))
        except Exception as e:
            rows.append({"symbol": sym, "error": str(e)})

    fig, ax = plt.subplots(figsize=(14, max(3.5, len(symbols)*0.55)))
    ax.axis('off')
    ax.set_title(f"{sector_name}  综合决策王 板块扫描", fontsize=14, fontweight='bold', pad=18)

    headers = ["代码", "价格", "涨跌%", "DKX", "A1X", "箱体位%", "量x", "信号"]
    data = []
    for r in rows:
        if 'error' in r:
            data.append([r['symbol'], 'ERR', '', '', '', '', '', r['error'][:25]])
            continue
        sigs = []
        if r['DZT']: sigs.append('DZT')
        if r['ZZJC']: sigs.append('ZZJC')
        if r['strong_trend']: sigs.append('强走势')
        data.append([
            r['symbol'], f"{r['close']:.2f}", f"{r['change_pct']:+.1f}%",
            f"{r['DKX']}{r['dkx_direction']}", f"{r['A1X']}{r['a1x_direction']}",
            f"{r['box_position_pct']:.0f}%", f"{r['vol_ratio']:.1f}x",
            ' '.join(sigs) or '—'
        ])

    tbl = ax.table(cellText=data, colLabels=headers, colWidths=[0.1,0.1,0.08,0.14,0.14,0.12,0.1,0.22],
                   loc='center', cellLoc='center')
    tbl.auto_set_font_size(False); tbl.set_fontsize(9); tbl.scale(1.2, 1.5)

    for i, r in enumerate(rows):
        if 'error' not in r and r.get('DZT'):
            for j in range(len(headers)):
                tbl[(i+1, j)].set_facecolor('#1a3a1a')

    if save_path is None:
        save_path = os.path.join(ensure_dir("tdx-mcp", "charts"), f"sector_{sector_name}_{datetime.now().strftime('%Y%m%d_%H%M')}.png")
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    fig.savefig(save_path, dpi=130, bbox_inches='tight', facecolor='#1a1a2e')
    plt.close(fig)
    return save_path
