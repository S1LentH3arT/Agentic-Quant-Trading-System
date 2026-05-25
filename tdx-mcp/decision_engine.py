#!/usr/bin/env python3
"""
决策引擎 — 全板块自动扫描 → 评分 → 纪律检查 → 操作建议 → 持久化
每日运行, 追踪板块轮动趋势变化
"""

import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import get_path, ensure_dir
import numpy as np
from indicator_engine import load_kline, calc_all_indicators, get_summary, score_stock
from datetime import datetime, date

# ============================================================
# 品种池 — 来自 memory/full_stock_pool.md
# ============================================================
def _get_discovery_symbols() -> list[str]:
    """读取发现池+狙击结果"""
    import json
    symbols = []
    for fname in ["discovery_pool.json"]:
        fpath = os.path.join(get_path("tdx-mcp", "discoveries"), fname)
        if os.path.exists(fpath):
            with open(fpath, encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                symbols.extend(list(data.keys()))
    # 也读取今日狙击结果
    today = date.today().isoformat()
    sniper_file = get_path("tdx-mcp", "discoveries", f"sniper_{today}.json")
    if os.path.exists(sniper_file):
        with open(sniper_file, encoding='utf-8') as f:
            data = json.load(f)
        for item in data.get("new_candidates", []):
            if isinstance(item, dict) and 'symbol' in item:
                symbols.append(item['symbol'])
    return symbols

SECTORS = {
    "电网设备": ["600089", "600406", "601179", "600312", "000400", "600875", "300827", "600379"],
    "电能":     ["601991", "600863", "600900", "600011"],
    "AI通信":   ["300903", "600183", "002463", "601698", "000070"],
    "算力":     ["603881", "300608", "688500", "002421"],
    "液冷":     ["002272", "002892", "300499"],
    "🔍发现池":  _get_discovery_symbols() or ["000099", "000166"],  # 动态加载
}

POSITIONS = ["600863", "601991", "000070"]  # 当前持仓

# ============================================================
# 打分引擎
# ============================================================
def rank_all_sectors() -> dict:
    """扫描全部22只标的, 按板块+综合评分排序"""
    all_results = {}
    for sector, symbols in SECTORS.items():
        sector_results = []
        for sym in symbols:
            try:
                df = load_kline(sym, count=120)
                df = calc_all_indicators(df)
                s = get_summary(df, sym)
                sc = score_stock(df)
                sector_results.append({
                    "symbol": sym,
                    "summary": s,
                    "score": sc["score"],
                    "score_details": sc["details"],
                })
            except Exception as e:
                sector_results.append({"symbol": sym, "error": str(e)})
        sector_results.sort(key=lambda r: r.get("score", -99), reverse=True)
        avg_score = sum(r.get("score", 0) for r in sector_results if "error" not in r) / max(1, sum(1 for r in sector_results if "error" not in r))
        all_results[sector] = {
            "rankings": sector_results,
            "avg_score": round(avg_score, 1),
            "top_pick": sector_results[0] if sector_results else None,
        }
    return all_results


# ============================================================
# 板块趋势检测
# ============================================================
def detect_sector_trend(sector_results: list) -> str:
    """检测板块趋势: 共振/启动/分化/退潮/双杀"""
    high_score = sum(1 for r in sector_results if r.get("score", 0) >= 7)
    rising_a1x = sum(1 for r in sector_results if r.get("summary", {}).get("a1x_direction") == "↑")
    total = len([r for r in sector_results if "error" not in r])

    if total == 0:
        return "无数据"
    if high_score >= total * 0.4 and rising_a1x >= total * 0.5:
        return "共振"
    elif rising_a1x >= total * 0.4:
        return "启动"
    elif high_score >= 1:
        return "分化"
    elif rising_a1x < total * 0.3:
        return "退潮"
    else:
        return "双杀"


# ============================================================
# 纪律检查器
# ============================================================
def discipline_check(scan_results: dict, positions: list[str] = None) -> dict:
    """对扫描结果执行铁律检查"""
    if positions is None:
        positions = POSITIONS
    alerts = []

    for sym in positions:
        stock_data = None
        for sector, data in scan_results.items():
            for r in data["rankings"]:
                if r.get("symbol") == sym:
                    stock_data = r
                    break

        if not stock_data or "error" in stock_data:
            alerts.append({"symbol": sym, "alert": "数据缺失", "level": "⚠️"})
            continue

        s = stock_data.get("summary", {})
        score = stock_data.get("score", 0)

        # Rule 2.1 硬止损 11%
        pnl_pct = None  # 需从持仓成本算, 这里用A1X方向作为代理
        # Rule 2.4 板块龙头跌停
        # Rule 2.5 ZZJC触发
        if s.get("ZZJC"):
            alerts.append({"symbol": sym, "alert": "ZZJC主力减仓触发 → 全清", "level": "🔴"})
        # Rule 3.2 同板块补仓检查
        # 开仓铁律检查 (for candidates)
        if score >= 8 and not s.get("ZZJC"):
            alerts.append({"symbol": sym, "alert": f"开仓条件满足(评分{score})", "level": "🟢"})

    return {"alerts": alerts, "checked_at": str(datetime.now())}


# ============================================================
# 操作建议生成器
# ============================================================
def generate_recommendations(scan_results: dict) -> dict:
    """基于扫描结果生成具体操作建议"""
    recs = []

    # 1. 每个板块的TOP候选
    for sector, data in scan_results.items():
        top = data["top_pick"]
        if top and top.get("score", 0) >= 7:
            s = top["summary"]
            recs.append({
                "sector": sector,
                "symbol": top["symbol"],
                "score": top["score"],
                "action": "开仓候选",
                "entry_zone": f"{s['box_low']}-{s['close']}",
                "stop": f"{s['stop_loss']:.2f}",
                "reason": top.get("score_details", [])[:2],
            })

    # 2. 板块轮动方向
    sector_trends = {}
    for sector, data in scan_results.items():
        trend = detect_sector_trend(data["rankings"])
        sector_trends[sector] = {
            "trend": trend,
            "avg_score": data["avg_score"],
            "top_symbol": data["top_pick"]["symbol"] if data["top_pick"] else None,
        }

    # 3. 板块排序
    sorted_sectors = sorted(sector_trends.items(), key=lambda x: x[1]["avg_score"], reverse=True)

    return {
        "candidates": recs,
        "sector_trends": sector_trends,
        "sector_ranking": [(s[0], s[1]["trend"], s[1]["avg_score"]) for s in sorted_sectors],
    }


# ============================================================
# 持久化 — 保存扫描结果, 追踪趋势变化
# ============================================================
def save_scan(scan_results: dict, recs: dict, save_dir: str = None):
    """保存扫描结果, 支持历史对比"""
    if save_dir is None:
        save_dir = ensure_dir("tdx-mcp", "scans")
    today = date.today().isoformat()

    record = {
        "date": today,
        "timestamp": str(datetime.now()),
        "scan_results": scan_results,
        "recommendations": recs,
    }

    # 保存当日
    with open(f"{save_dir}/{today}.json", "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    # 追加到周记录
    week_file = f"{save_dir}/week_{today}.jsonl"
    with open(week_file, "a", encoding="utf-8") as f:
        f.write(json.dumps({"date": today, "sector_ranking": recs["sector_ranking"]}, ensure_ascii=False) + "\n")

    return f"{save_dir}/{today}.json"


def load_history(days: int = 5) -> list:
    """加载最近N天的扫描记录"""
    save_dir = get_path("tdx-mcp", "scans")
    records = []
    if not os.path.exists(save_dir):
        return records
    for f in sorted(os.listdir(save_dir), reverse=True)[:days]:
        if f.endswith('.json') and not f.startswith('week'):
            try:
                with open(f"{save_dir}/{f}", encoding="utf-8") as fp:
                    records.append(json.load(fp))
            except:
                pass
    return records


def trend_diff(today: dict, yesterday: dict) -> dict:
    """对比两天板块趋势变化"""
    if not yesterday:
        return {"note": "无历史数据"}
    diffs = {}
    today_ranking = today.get("recommendations", {}).get("sector_ranking", [])
    yesterday_ranking = yesterday.get("recommendations", {}).get("sector_ranking", [])
    for (sect, trend, score), (_, y_trend, y_score) in zip(today_ranking, yesterday_ranking):
        diffs[sect] = {
            "score_change": round(score - y_score, 1),
            "trend_today": trend,
            "trend_yesterday": y_trend,
        }
    return diffs


# ============================================================
# 完整决策流程 (一键运行)
# ============================================================
def update_objective_metrics() -> dict:
    """每日更新7维度客观指标（从持久化交易记录中计算）"""
    import json, os
    metrics_file = get_path("tdx-mcp", "scans", "objective_metrics.json")

    # 加载历史交易记录
    all_trades = []
    scan_dir = get_path("tdx-mcp", "scans")
    if os.path.exists(scan_dir):
        for f in sorted(os.listdir(scan_dir)):
            if f.endswith('.json') and not f.startswith('week'):
                try:
                    with open(f"{scan_dir}/{f}", encoding='utf-8') as fp:
                        data = json.load(fp)
                    trades = data.get("trades", [])
                    if trades:
                        all_trades.extend(trades)
                except:
                    pass

    if not all_trades:
        return {"status": "积累中", "trade_count": 0, "note": "交易数据不足,每日自动积累"}

    n = len(all_trades)
    wins = [t for t in all_trades if t.get('pnl_pct', 0) > 0]
    losses = [t for t in all_trades if t.get('pnl_pct', 0) <= 0]
    n_wins = len(wins)

    win_rate = n_wins / n * 100
    avg_win = sum(t['pnl_pct'] for t in wins) / max(1, n_wins)
    avg_loss = abs(sum(t['pnl_pct'] for t in losses) / max(1, n - n_wins))
    payoff_ratio = avg_win / avg_loss if avg_loss > 0 else 0
    kelly = (win_rate/100 * (payoff_ratio + 1) - 1) / payoff_ratio if payoff_ratio > 0 else 0
    kelly = max(0, min(kelly, 0.25))

    # 计算权益曲线和回撤
    capital = 100000
    equity = [capital]
    for t in all_trades:
        capital *= (1 + t.get('pnl_pct', 0) / 100)
        equity.append(capital)
    equity_arr = np.array(equity) if len(equity) > 1 else np.array([100000])
    peak = np.maximum.accumulate(equity_arr)
    drawdown = (equity_arr - peak) / peak * 100
    max_dd = abs(np.min(drawdown))

    returns = np.diff(equity_arr) / equity_arr[:-1]
    returns = returns[np.isfinite(returns)]
    sharpe = float(np.mean(returns) / np.std(returns) * np.sqrt(252)) if len(returns) > 1 and np.std(returns) > 0 else 0

    max_consec = 1
    streak = 0
    for t in all_trades:
        if t['pnl_pct'] <= 0:
            streak += 1
            max_consec = max(max_consec, streak)
        else:
            streak = 0

    metrics = {
        "updated": str(datetime.now()),
        "total_trades": n,
        "data_status": "统计显著" if n >= 30 else f"积累中({n}/30)",
        "metrics": {
            "win_rate": round(win_rate, 1),
            "payoff_ratio": round(payoff_ratio, 2),
            "kelly_fraction": round(kelly * 100, 1),
            "trade_freq_per_month": round(n / max(1, (datetime.now() - datetime(2026,5,20)).days) * 30, 1),
            "max_consecutive_loss": max_consec,
            "max_drawdown_pct": round(max_dd, 1),
            "sharpe_ratio": round(sharpe, 2),
            "total_return_pct": round((capital - 100000) / 1000, 1),
        }
    }

    with open(metrics_file, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    return metrics


def full_decision_cycle() -> dict:
    """完整决策周期: 扫描→评分→纪律→建议→持久化→对比"""
    print("=" * 60)
    print("  综合决策王 决策引擎 v1.0")
    print(f"  运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # Step 1: 扫描
    print("\n[1/5] 扫描全部板块...")
    scan = rank_all_sectors()
    for sector, data in scan.items():
        top = data["top_pick"]
        top_sym = top["symbol"] if top else "N/A"
        top_score = top["score"] if top else 0
        print(f"  {sector:<6} 均分{data['avg_score']:>5.1f}  TOP:{top_sym}({top_score}分)")

    # Step 2: 纪律检查
    print("\n[2/5] 纪律检查...")
    disc = discipline_check(scan)
    for a in disc["alerts"]:
        print(f"  {a['level']} {a['symbol']}: {a['alert']}")

    # Step 3: 生成建议
    print("\n[3/5] 生成操作建议...")
    recs = generate_recommendations(scan)
    for s in recs["sector_ranking"]:
        print(f"  {s[0]:<6} {s[1]:<4} (均分{s[2]})")
    if recs["candidates"]:
        print(f"\n  开仓候选: {len(recs['candidates'])} 只")
        for c in recs["candidates"]:
            print(f"    {c['sector']}/{c['symbol']} 评分{c['score']} → {c['action']}")

    # Step 4: 持久化
    print("\n[4/5] 保存结果...")
    path = save_scan(scan, recs)
    print(f"  → {path}")

    # Step 5: 历史对比
    print("\n[5/5] 历史趋势对比...")
    history = load_history(2)
    diff = trend_diff(history[0] if history else {}, history[1] if len(history) > 1 else {})
    for sect, d in diff.items():
        if isinstance(d, dict) and "score_change" in d:
            arrow = "↑" if d["score_change"] > 0 else "↓" if d["score_change"] < 0 else "→"
            print(f"  {sect:<6} {arrow}{abs(d['score_change']):.1f}  {d['trend_today']}")

    # Step 6: 更新客观指标
    print("\n[6/6] 更新7维度客观指标...")
    obj = update_objective_metrics()
    if obj.get('data_status') == '积累中':
        print(f"  状态: {obj['data_status']} ({obj['total_trades']}笔)")
    else:
        m = obj['metrics']
        print(f"  胜率{m['win_rate']}% | 赔率{m['payoff_ratio']} | Kelly{m['kelly_fraction']}% | Sharpe{m['sharpe_ratio']} | 回撤{m['max_drawdown_pct']}%")

    return {"scan": scan, "discipline": disc, "recommendations": recs, "diff": diff, "saved": path, "objective_metrics": obj}
