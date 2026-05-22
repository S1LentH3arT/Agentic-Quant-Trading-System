#!/usr/bin/env python3
"""
全市场回测引擎 — 客观量化7个核心维度
胜率/赔率/仓位率/出手频率/容错率/回撤率/稳定率

策略: 综合决策王 (DKX + A1X + 箱体 + 量能)
"""

import sys, os, json, math
sys.path.insert(0, 'F:/working-project/tdx-mcp')
import numpy as np
import pandas as pd
from datetime import datetime, date, timedelta
from indicator_engine import load_kline, calc_all_indicators, _clean
from mootdx.quotes import StdQuotes

# ============================================================
# 策略参数（与 Pine Script 完全一致）
# ============================================================
STRATEGY_PARAMS = {
    "fastLen": 12, "slowLen": 26, "sigLen": 9,  # MACD
    "rsiLen": 14, "volAvgLen": 20,                # RSI + Vol
    "stop_loss_pct": 11,                           # 硬止损 %
    "max_hold_days": 15,                           # 最大持仓天数
}

# ============================================================
# 回测引擎
# ============================================================
class BacktestEngine:
    def __init__(self, initial_capital: float = 100000, commission: float = 0.0003):
        self.initial_capital = initial_capital
        self.commission = commission
        self.trades = []
        self.equity_curve = []

    def run(self, df: pd.DataFrame, symbol: str = "") -> dict:
        """在单只标的上运行策略, 返回交易记录"""
        df = calc_all_indicators(df.copy())
        self.trades = []
        capital = self.initial_capital
        position = 0
        entry_price = 0
        entry_date = None
        self.equity_curve = [capital]

        for i in range(40, len(df)):  # 前40根用于指标计算
            row = df.iloc[i]
            prev = df.iloc[i-1]
            close = float(row['close'])

            # ── 入场条件 ──
            if position == 0:
                a1x = float(row['A1X'])
                a1x_prev = float(prev['A1X'])
                box_pos = float(row['box_position']) if pd.notna(row['box_position']) else 100
                vol_ratio = float(row['vol_ratio']) if pd.notna(row['vol_ratio']) else 0
                dkx_up = bool(row['dkx_up']) if pd.notna(row['dkx_up']) else False

                # 条件: A1X金叉 + 箱体中低位 + 放量 + 无ZZJC
                a1x_cross = (a1x > 0 and a1x_prev <= 0)
                box_ok = 0 <= box_pos <= 40
                vol_ok = vol_ratio >= 1.2
                no_zzjc = not bool(row['ZZJC'])

                if a1x_cross and box_ok and vol_ok and no_zzjc:
                    position = capital / close
                    entry_price = close
                    entry_date = i
                    capital = 0

            # ── 离场条件 ──
            elif position > 0:
                a1x = float(row['A1X'])
                zzjc = bool(row['ZZJC'])
                pnl_pct = (close - entry_price) / entry_price * 100
                hold_days = i - entry_date

                exit_signal = False
                exit_reason = ""

                # 硬止损
                if pnl_pct <= -STRATEGY_PARAMS["stop_loss_pct"]:
                    exit_signal = True
                    exit_reason = "止损"
                # ZZJC离场
                elif zzjc:
                    exit_signal = True
                    exit_reason = "ZZJC"
                # 时间止损
                elif hold_days >= STRATEGY_PARAMS["max_hold_days"] and pnl_pct < 3:
                    exit_signal = True
                    exit_reason = "时间止损"

                if exit_signal:
                    capital = position * close * (1 - self.commission)
                    self.trades.append({
                        "symbol": symbol,
                        "entry_date": str(df.index[entry_date]) if hasattr(df.index[entry_date], 'strftime') else str(entry_date),
                        "exit_date": str(df.index[i]) if hasattr(df.index[i], 'strftime') else str(i),
                        "entry_price": round(entry_price, 2),
                        "exit_price": round(close, 2),
                        "pnl_pct": round(pnl_pct, 2),
                        "hold_days": hold_days,
                        "exit_reason": exit_reason,
                    })
                    position = 0
                    entry_price = 0
                    entry_date = None

            # 记录权益曲线
            equity = capital + (position * close if position > 0 else 0)
            self.equity_curve.append(equity)

        # 强制平仓
        if position > 0:
            close = float(df.iloc[-1]['close'])
            capital = position * close * (1 - self.commission)
            pnl_pct = (close - entry_price) / entry_price * 100
            self.trades.append({
                "symbol": symbol,
                "entry_date": str(entry_date),
                "exit_date": str(len(df)-1),
                "entry_price": round(entry_price, 2),
                "exit_price": round(close, 2),
                "pnl_pct": round(pnl_pct, 2),
                "hold_days": len(df) - entry_date,
                "exit_reason": "持仓到期",
            })

        return self.compute_metrics()

    def compute_metrics(self) -> dict:
        """计算7个客观维度"""
        if not self.trades:
            return {"trade_count": 0, "error": "无交易"}

        wins = [t for t in self.trades if t['pnl_pct'] > 0]
        losses = [t for t in self.trades if t['pnl_pct'] <= 0]

        n = len(self.trades)
        n_wins = len(wins)

        # 1. 胜率
        win_rate = n_wins / n * 100 if n > 0 else 0

        # 2. 赔率 (平均盈利 / 平均亏损)
        avg_win = np.mean([t['pnl_pct'] for t in wins]) if wins else 0
        avg_loss = abs(np.mean([t['pnl_pct'] for t in losses])) if losses else 1
        payoff_ratio = avg_win / avg_loss if avg_loss > 0 else 0

        # 3. 仓位率 (Kelly公式)
        if payoff_ratio > 0:
            kelly_f = (win_rate/100 * (payoff_ratio + 1) - 1) / payoff_ratio
            kelly_f = max(0, min(kelly_f, 0.25))  # 上限25%
        else:
            kelly_f = 0

        # 4. 出手频率 (日均交易次数)
        # 估算: 交易次数 / 回测天数
        trade_freq = n / max(1, 250)  # 年化

        # 5. 容错率 (连续亏损容忍度)
        max_consecutive_loss = 1
        current_streak = 0
        for t in self.trades:
            if t['pnl_pct'] <= 0:
                current_streak += 1
                max_consecutive_loss = max(max_consecutive_loss, current_streak)
            else:
                current_streak = 0
        ruin_threshold = self.initial_capital * 0.3  # 30%回撤即毁灭
        avg_loss_amount = avg_loss / 100 * self.initial_capital * kelly_f
        error_tolerance = ruin_threshold / avg_loss_amount if avg_loss_amount > 0 else 999

        # 6. 回撤率
        equity_arr = np.array(self.equity_curve)
        peak = np.maximum.accumulate(equity_arr)
        drawdown = (equity_arr - peak) / peak * 100
        max_dd = abs(np.min(drawdown))

        # 7. 稳定率 (Sharpe-like)
        returns = np.diff(self.equity_curve) / self.equity_curve[:-1]
        returns = returns[np.isfinite(returns)]
        if len(returns) > 1 and np.std(returns) > 0:
            sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252)
        else:
            sharpe = 0

        total_return = (self.equity_curve[-1] - self.initial_capital) / self.initial_capital * 100

        return {
            "trade_count": n,
            "win_count": n_wins,
            "loss_count": n - n_wins,
            "win_rate": round(win_rate, 1),           # 1. 胜率 %
            "payoff_ratio": round(payoff_ratio, 2),    # 2. 赔率
            "kelly_fraction": round(kelly_f * 100, 1), # 3. 仓位率 %
            "trade_freq_per_year": round(trade_freq, 1), # 4. 出手频率
            "max_consecutive_loss": max_consecutive_loss, # 5a. 最大连续亏损
            "error_tolerance": round(error_tolerance, 1),  # 5b. 容错率(笔)
            "max_drawdown_pct": round(max_dd, 1),      # 6. 回撤率 %
            "sharpe_ratio": round(sharpe, 2),           # 7. 稳定率
            "total_return_pct": round(total_return, 1),
            "avg_win_pct": round(avg_win, 2),
            "avg_loss_pct": round(avg_loss, 2),
        }


# ============================================================
# 全市场扫描回测
# ============================================================
def get_stock_universe(market: str = "all") -> list[str]:
    """获取A股全市场标的列表"""
    try:
        client = StdQuotes(host='218.6.170.47', port=7709, timeout=8)
        # market=1 → 深沪A股
        data = client.stocks(market=1)
        if data is None or (hasattr(data, 'empty') and data.empty):
            return []
        codes = []
        if hasattr(data, 'iterrows'):
            for _, r in data.iterrows():
                code = str(r.get('code', ''))
                if code and len(code) == 6 and code[0] in '036':
                    codes.append(code)
        return codes[:500]  # 限制500只, 防止运行时间过长
    except Exception as e:
        print(f"获取股票列表失败: {e}")
        # 回退: 使用22只主力池
        return ["600863","601991","000070","600089","600406","601179","600312","000400",
                "600875","300827","600379","600900","600011","300903","600183","002463",
                "601698","603881","300608","688500","002272","002892"]


def run_market_backtest(symbols: list[str] = None, max_stocks: int = 100) -> dict:
    """全市场批量回测"""
    if symbols is None:
        symbols = get_stock_universe()
        symbols = symbols[:max_stocks]

    all_trades = []
    all_metrics = []
    print(f"回测 {len(symbols)} 只标的...")

    for idx, sym in enumerate(symbols):
        try:
            df = load_kline(sym, count=300)
            if df is None or len(df) < 50:
                continue
            engine = BacktestEngine()
            metrics = engine.run(df, sym)
            if metrics.get('trade_count', 0) > 0:
                all_metrics.append({"symbol": sym, **metrics})
                all_trades.extend(engine.trades)
            if idx % 20 == 0:
                print(f"  {idx}/{len(symbols)}...")
        except Exception as e:
            pass

    if not all_metrics:
        return {"error": "无有效回测结果"}

    # 汇总统计
    df_m = pd.DataFrame(all_metrics)
    agg = {
        "total_stocks_tested": len(symbols),
        "profitable_stocks": int((df_m['total_return_pct'] > 0).sum()),
        "total_trades": int(df_m['trade_count'].sum()),
        "aggregate_metrics": {
            "win_rate": round(df_m['win_rate'].mean(), 1),
            "payoff_ratio": round(df_m['payoff_ratio'].mean(), 2),
            "kelly_fraction": round(df_m['kelly_fraction'].mean(), 1),
            "trade_freq_per_year": round(df_m['trade_freq_per_year'].mean(), 1),
            "max_consecutive_loss": int(df_m['max_consecutive_loss'].max()),
            "error_tolerance": round(df_m['error_tolerance'].mean(), 1),
            "max_drawdown_pct": round(df_m['max_drawdown_pct'].mean(), 1),
            "sharpe_ratio": round(df_m['sharpe_ratio'].mean(), 2),
            "avg_total_return": round(df_m['total_return_pct'].mean(), 1),
        },
        "top_performers": df_m.nlargest(10, 'total_return_pct')[
            ['symbol', 'total_return_pct', 'win_rate', 'payoff_ratio', 'sharpe_ratio']
        ].to_dict('records'),
        "all_results": df_m.to_dict('records'),
    }
    return agg
