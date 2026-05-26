#!/usr/bin/env python3
"""
板块分析 — 产业景气 + 赛道方向 (从 tdx-mcp/sector_sniper.py 迁移)
使用 AKShare 行业板块数据替代 TDX 板块成分股。
"""

import json
from datetime import datetime, date
from quant_system.config import get_path, ensure_dir
from quant_system.data.bus import get_bus
from quant_system.factors.engine import FactorEngine
from quant_system.strategy.scorer import Scorer, get_summary
from quant_system.strategy.pool import PoolManager


def identify_hot_sectors() -> list[dict]:
    """从5个监控板块中识别当日最强方向"""
    pool = PoolManager()
    sectors = pool.get_sector_pool()

    bus = get_bus()
    engine = FactorEngine()
    scorer = Scorer()

    # 加载所有板块标的的K线
    all_symbols = [s for ss in sectors.values() for s in ss]
    klines = bus.get_daily(all_symbols, count=40)

    results = []
    for sec_name, syms in sectors.items():
        scores = []
        rising_a1x = 0
        for sym in syms:
            df = klines.get(sym)
            if df is None or len(df) < 20:
                continue
            try:
                df = engine.compute(df, layers=[6])
                sc = scorer.score(df, sym)
                scores.append(sc['score'])
                s = get_summary(df, sym)
                if s.get('a1x_direction') == '↑':
                    rising_a1x += 1
            except Exception:
                pass
        if scores:
            avg = sum(scores) / len(scores)
            results.append({
                "sector": sec_name,
                "avg_score": round(avg, 1),
                "rising_count": rising_a1x,
                "total": len(scores),
                "hot": avg >= 3.5 or rising_a1x >= len(scores) * 0.4,
            })

    results.sort(key=lambda r: r['avg_score'], reverse=True)
    return results


def detect_sector_trend(scores: list[float], a1x_rising: int, total: int) -> str:
    """板块趋势分类: 共振/启动/分化/退潮/双杀"""
    from quant_system.evolution.param_loader import get_param

    resonance_pct = get_param('decision_engine.sector_resonance_pct', 0.4)
    uptrend_pct = get_param('decision_engine.sector_uptrend_pct', 0.5)
    ebbing_pct = get_param('decision_engine.sector_ebbing_pct', 0.3)
    high_bar = get_param('decision_engine.high_score_bar', 7)

    if total == 0:
        return "无数据"

    high_score = sum(1 for s in scores if s >= high_bar)
    rising_pct = a1x_rising / total

    if high_score >= total * resonance_pct and rising_pct >= uptrend_pct:
        return "共振"
    elif rising_pct >= 0.4:
        return "启动"
    elif high_score >= 1:
        return "分化"
    elif rising_pct < ebbing_pct:
        return "退潮"
    else:
        return "双杀"


def sector_analysis(save: bool = True) -> dict:
    """完整板块分析"""
    print("=" * 60)
    print("  板块分析 — 产业景气+赛道方向")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    hot_sectors = identify_hot_sectors()
    sector_trends = {}

    for hs in hot_sectors:
        tag = "HOT" if hs['hot'] else "   "
        print(f"  [{tag}] {hs['sector']}: avg={hs['avg_score']} "
              f"rising={hs['rising_count']}/{hs['total']}")
        sector_trends[hs['sector']] = {
            "avg_score": hs['avg_score'],
            "hot": hs['hot'],
            "rising_ratio": round(hs['rising_count'] / max(hs['total'], 1), 2),
        }

    if save:
        today = date.today().isoformat()
        save_dir = ensure_dir("storage", "state")
        record = {"date": today, "timestamp": str(datetime.now()),
                  "hot_sectors": hot_sectors, "sector_trends": sector_trends}
        with open(f"{save_dir}/sector_{today}.json", "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)

    return {"hot_sectors": hot_sectors, "sector_trends": sector_trends}


if __name__ == "__main__":
    sector_analysis()
