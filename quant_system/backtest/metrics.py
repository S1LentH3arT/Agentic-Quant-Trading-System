#!/usr/bin/env python3
"""
绩效指标 — 7+维度: 胜率/赔率/Kelly/交易频率/最大连续亏损/最大回撤/夏普/卡尔玛/索提诺
"""

import numpy as np


def compute_metrics(trades: list[dict], equity_curve: list[float],
                    initial_capital: float = 100000) -> dict:
    """计算全部绩效指标"""
    if not trades:
        return {"trade_count": 0, "error": "无交易"}

    n = len(trades)
    wins = [t for t in trades if t.get('pnl_pct', 0) > 0]
    losses = [t for t in trades if t.get('pnl_pct', 0) <= 0]
    n_wins = len(wins)

    # 胜率
    win_rate = n_wins / n * 100 if n > 0 else 0

    # 赔率
    avg_win = np.mean([t['pnl_pct'] for t in wins]) if wins else 0
    avg_loss = abs(np.mean([t['pnl_pct'] for t in losses])) if losses else 1
    payoff_ratio = avg_win / avg_loss if avg_loss > 0 else 0

    # Kelly
    if payoff_ratio > 0:
        kelly = (win_rate / 100 * (payoff_ratio + 1) - 1) / payoff_ratio
        kelly = max(0, min(kelly, 0.25))
    else:
        kelly = 0

    # 最大连续亏损
    max_consec = 1
    streak = 0
    for t in trades:
        if t['pnl_pct'] <= 0:
            streak += 1
            max_consec = max(max_consec, streak)
        else:
            streak = 0

    # 最大回撤
    eq_arr = np.array(equity_curve) if equity_curve else np.array([initial_capital])
    peak = np.maximum.accumulate(eq_arr)
    drawdown = (eq_arr - peak) / peak * 100
    max_dd = abs(np.min(drawdown))

    # 夏普比率
    returns = np.diff(eq_arr) / eq_arr[:-1] if len(eq_arr) > 1 else np.array([0])
    returns = returns[np.isfinite(returns)]
    sharpe = float(np.mean(returns) / np.std(returns) * np.sqrt(252)) if len(returns) > 1 and np.std(returns) > 0 else 0

    # 卡尔玛比率 (年化收益/MDD)
    total_return = (eq_arr[-1] - initial_capital) / initial_capital
    calmar = round(total_return / (max_dd / 100), 2) if max_dd > 0 else 0

    # 索提诺比率
    downside = returns[returns < 0]
    sortino = float(np.mean(returns) / np.std(downside) * np.sqrt(252)) if len(downside) > 1 and np.std(downside) > 0 else 0

    return {
        "trade_count": n, "win_count": n_wins, "loss_count": n - n_wins,
        "win_rate": round(win_rate, 1),
        "payoff_ratio": round(payoff_ratio, 2),
        "kelly_fraction": round(kelly * 100, 1),
        "max_consecutive_loss": max_consec,
        "max_drawdown_pct": round(max_dd, 1),
        "sharpe_ratio": round(sharpe, 2),
        "calmar_ratio": calmar,
        "sortino_ratio": round(sortino, 2),
        "total_return_pct": round(total_return * 100, 1),
        "avg_win_pct": round(avg_win, 2),
        "avg_loss_pct": round(avg_loss, 2),
    }
