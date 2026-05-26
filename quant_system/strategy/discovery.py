#!/usr/bin/env python3
"""
发现引擎 — 全市场自主扫描 (从 tdx-mcp/discovery_engine.py 迁移)
使用 AKShare 代替 TDX，走 quant_system 数据总线。
"""

import json
from datetime import datetime, date
from quant_system.config import get_path, ensure_dir
from quant_system.data.bus import get_bus
from quant_system.factors.engine import FactorEngine
from quant_system.strategy.scorer import Scorer, get_summary
from quant_system.evolution.param_loader import get_param


def coarse_filter() -> list[str]:
    """全市场粗筛: 价格区间 + 有量 + 非ST"""
    print("[1/4] 构建候选池...")
    bus = get_bus()
    all_codes = bus.get_all_stock_codes()

    pmin = get_param('discovery_engine.price_min', 3)
    pmax = get_param('discovery_engine.price_max', 80)

    # 从全A股代码筛选: 非688(科创板) + 非ST
    candidates = sorted(
        c for c in all_codes
        if not c.startswith('688')
        and len(c) == 6
        and c[0] in '0236'
    )
    print(f"      候选池总计 {len(candidates)} 只")
    return candidates


def quick_scan(symbols: list[str], max_scan: int = 200) -> list[dict]:
    """快速扫描 — 对各标的计算L6技术指标+评分"""
    max_scan = get_param('discovery_engine.scan_max', max_scan)
    print(f"[2/4] 快速扫描 (最多{max_scan}只)...")

    if len(symbols) > max_scan:
        step = max(1, len(symbols) // max_scan)
        symbols = symbols[::step][:max_scan]

    bus = get_bus()
    engine = FactorEngine()
    scorer = Scorer()

    results = []
    batch_size = get_param('discovery_engine.batch_size', 100)

    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i+batch_size]
        klines = bus.get_daily(batch, count=60)
        for sym, df in klines.items():
            if df is None or len(df) < get_param('discovery_engine.min_klines', 40):
                continue
            try:
                df = engine.compute(df, layers=[6])
                s = get_summary(df, sym)
                sc = scorer.score(df, sym)

                if sc.get("veto"):
                    continue

                # 发现条件
                a1x = s.get('A1X', 0)
                box = s.get('box_position_pct', 100)
                vol = s.get('vol_ratio', 0)

                a1x_lo = get_param('discovery_engine.a1x_min', -3)
                a1x_hi = get_param('discovery_engine.a1x_max', 3)
                box_max = get_param('discovery_engine.box_pos_max', 50)
                vol_min = get_param('discovery_engine.vol_ratio_min', 0.8)

                if a1x_lo <= a1x <= a1x_hi and box <= box_max and vol >= vol_min:
                    results.append({
                        "symbol": sym, "close": s['close'],
                        "A1X": round(a1x, 2), "a1x_dir": s['a1x_direction'],
                        "box_pos": round(box, 1), "vol_ratio": round(vol, 2),
                        "score": sc['score'], "DZT": s['DZT'],
                        "details": sc['details'],
                    })
            except Exception:
                pass

        if (i + batch_size) % 500 == 0:
            print(f"      {min(i+batch_size, len(symbols))}/{len(symbols)}... found {len(results)}")

    return results


def filter_existing(discoveries: list[dict], existing_pool: set) -> list[dict]:
    """排除已在品种池中的标的"""
    new = [d for d in discoveries if d['symbol'] not in existing_pool]
    print(f"[3/4] 新发现 {len(new)} 只 (排除{len(discoveries)-len(new)}只已有)")
    return new


def save_discoveries(discoveries: list[dict], top_n: int = 20):
    """保存发现结果"""
    top_n = get_param('discovery_engine.save_top_n', top_n)
    today = date.today().isoformat()
    save_dir = ensure_dir("storage", "state")

    discoveries.sort(key=lambda d: d['score'], reverse=True)

    record = {
        "date": today, "timestamp": str(datetime.now()),
        "total_scanned": len(discoveries),
        "top_discoveries": discoveries[:top_n],
    }
    with open(f"{save_dir}/discovery_{today}.json", "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    # 更新发现池
    pool_file = get_path("storage", "state", "discovery_pool.json")
    existing_pool = {}
    if __import__('os').path.exists(pool_file):
        with open(pool_file, encoding='utf-8') as f:
            existing_pool = json.load(f)

    for d in discoveries[:top_n]:
        sym = d['symbol']
        if sym not in existing_pool:
            existing_pool[sym] = {
                "first_found": today, "last_seen": today,
                "peak_score": d['score'], "latest_A1X": d['A1X'],
                "latest_box": d['box_pos'],
            }
        else:
            existing_pool[sym]['last_seen'] = today
            existing_pool[sym]['peak_score'] = max(
                existing_pool[sym].get('peak_score', 0), d['score'])

    with open(pool_file, "w", encoding="utf-8") as f:
        json.dump(existing_pool, f, ensure_ascii=False, indent=2)

    print(f"[4/4] 保存 {min(len(discoveries), top_n)} 只到发现池, 总计 {len(existing_pool)} 只")
    return record


def run_discovery(existing_symbols: list[str] = None, max_scan: int = 200):
    """全市场自主发现 — 一键运行"""
    print("=" * 60)
    print("  发现引擎 — 全市场自主挖掘")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    candidates = coarse_filter()
    discoveries = quick_scan(candidates, max_scan=max_scan)

    if existing_symbols is None:
        existing_symbols = [
            "600863","601991","000070","600089","600406","601179","600312","000400",
            "600875","300827","600379","600900","600011","300903","600183","002463",
            "601698","603881","300608","002272","002892","002421"
        ]
    existing_set = set(existing_symbols)
    new_discoveries = filter_existing(discoveries, existing_set)
    record = save_discoveries(new_discoveries)

    top = new_discoveries[:10]
    if top:
        print(f"\n  TOP 新发现:")
        for i, d in enumerate(top):
            print(f"  {i+1:>2}. {d['symbol']} A1X={d['A1X']} box={d['box_pos']}% "
                  f"vol={d['vol_ratio']}x score={d['score']}")
    return record


if __name__ == "__main__":
    run_discovery()
