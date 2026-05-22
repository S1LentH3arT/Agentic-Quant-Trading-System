#!/usr/bin/env python3
"""
板块狙击 — 早盘确认板块方向后, 立即全板块挖掘, 不错过当天行情
不是从22只里筛, 是从该板块全量标的中扫
"""

import sys, json, os
sys.path.insert(0, 'F:/working-project/tdx-mcp')
from mootdx.quotes import StdQuotes
from indicator_engine import load_kline, calc_all_indicators, get_summary, score_stock
from datetime import datetime, date

# ============================================================
# 第一步: 识别当日最强板块
# ============================================================
def identify_hot_sectors(client) -> list[dict]:
    """
    从5个监控板块中识别当日最强方向。
    标准: 板块均分变化+多只标的A1X上升
    """
    sectors = {
        "电网设备": ["600089","600406","601179","600312","000400","600875","300827","600379"],
        "电能":     ["601991","600863","600900","600011"],
        "AI通信":   ["300903","600183","002463","601698","000070"],
        "算力":     ["603881","300608","688500","002421"],
        "液冷":     ["002272","002892"],
    }
    results = []
    for sec_name, syms in sectors.items():
        scores = []
        rising_a1x = 0
        for sym in syms:
            try:
                df = load_kline(sym, count=40)
                df = calc_all_indicators(df)
                s = get_summary(df, sym)
                sc = score_stock(df)
                scores.append(sc['score'])
                if s['a1x_direction'] == '↑':
                    rising_a1x += 1
            except:
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


# ============================================================
# 第二步: 全板块深度挖掘 — 不是从22只, 是从全市场
# ============================================================
def deep_sector_scan(client, hot_sectors: list[str], max_scan_per_sector: int = 200) -> dict:
    """
    对当日热门板块做全市场深度扫描。
    从该板块全量标的中筛选: A1X金叉附近 + 箱体低位 + 放量
    """
    print("Deep sector scan for:", hot_sectors)
    # 获取板块全量标的 (从通达信板块成分股)
    try:
        all_blocks = client.block()
    except:
        return {}

    # 板块关键词映射
    sector_keywords = {
        "电网设备": ["电网","电力","电气","特高压","输变电","开关"],
        "电能": ["电力","发电","火电","水电","核电","绿电","能源"],
        "AI通信": ["通信","光模块","光纤","光缆","PCB","电路板","服务器"],
        "算力": ["算力","数据中心","芯片","半导体","存储","IDC"],
        "液冷": ["液冷","散热","冷却","温控","热管理","制冷"],
    }

    results = {}
    for sec in hot_sectors:
        keywords = sector_keywords.get(sec, [sec])
        candidates = set()

        # 从板块成分股中匹配
        if hasattr(all_blocks, 'iterrows'):
            for _, r in all_blocks.iterrows():
                block_name = str(r.get('blockname', ''))
                for kw in keywords:
                    if kw in block_name:
                        code = str(r.get('code', ''))
                        if code.isdigit() and len(code) == 6 and code[0] in '0236':
                            candidates.add(code)
                        break

        print(f"  {sec}: {len(candidates)} candidates from blocks")

        # 如果板块匹配的太少, 从市场列表扩展
        if len(candidates) < 20:
            try:
                market_data = client.stocks(market=0)
                if hasattr(market_data, 'iterrows'):
                    for _, r in market_data.iterrows():
                        code = str(r.get('code', ''))
                        name = str(r.get('name', ''))
                        if code.isdigit() and len(code) == 6 and code[0] in '0236':
                            for kw in keywords:
                                if kw in name:
                                    candidates.add(code)
                                    break
            except:
                pass

        print(f"  {sec}: {len(candidates)} total candidates")

        # 快速扫描 (限制数量)
        candidates = list(candidates)[:max_scan_per_sector]
        scored = []
        for i, sym in enumerate(candidates):
            try:
                df = load_kline(sym, count=40)
                df = calc_all_indicators(df)
                s = get_summary(df, sym)
                sc = score_stock(df)
                # 只看A1X在[-3,3]且箱体中低位且有量的
                if -3 <= s['A1X'] <= 3 and s['box_position_pct'] <= 50 and s['vol_ratio'] >= 0.8:
                    scored.append({
                        "symbol": sym, "A1X": round(s['A1X'],2),
                        "box_pos": round(s['box_position_pct'],1),
                        "vol_ratio": round(s['vol_ratio'],2),
                        "score": sc['score'],
                        "DZT": s['DZT'],
                        "close": s['close'],
                    })
            except:
                pass

        scored.sort(key=lambda x: x['score'], reverse=True)
        results[sec] = scored[:15]  # 每个板块保留TOP15
        print(f"  {sec}: {len(scored)} scored, TOP={scored[0]['symbol']}({scored[0]['score']}分)" if scored else f"  {sec}: no matches")

    return results


# ============================================================
# 一键狙击
# ============================================================
def snipe():
    print("=" * 60)
    print("  板块狙击 — 早盘确认方向 → 全板块挖掘")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    client = StdQuotes(host='218.6.170.47', port=7709, timeout=8)

    # 1. 识别热点
    print("\n[1/3] 识别当日最强板块...")
    hot_sectors = identify_hot_sectors(client)
    for hs in hot_sectors:
        tag = "HOT" if hs['hot'] else "   "
        print(f"  [{tag}] {hs['sector']}: avg={hs['avg_score']} rising={hs['rising_count']}/{hs['total']}")

    # 2. 对热门板块深度挖掘
    hot_names = [hs['sector'] for hs in hot_sectors if hs['hot']]
    if not hot_names:
        hot_names = [hot_sectors[0]['sector']]  # at least the top sector
    print(f"\n[2/3] 深度挖掘: {hot_names}")
    discoveries = deep_sector_scan(client, hot_names)

    # 3. 排除已有品种池
    existing = {"600863","601991","000070","600089","600406","601179","600312","000400",
                "600875","300827","600379","600900","600011","300903","600183","002463",
                "601698","603881","300608","688500","002272","002892","002421"}
    print(f"\n[3/3] 输出候选 (排除22只已有)")
    all_new = []
    for sec, stocks in discoveries.items():
        new = [s for s in stocks if s['symbol'] not in existing]
        print(f"\n  [{sec}] 新发现 {len(new)} 只:")
        for i, s in enumerate(new[:5]):
            print(f"  {i+1}. {s['symbol']} A1X={s['A1X']} box={s['box_pos']}% vol={s['vol_ratio']}x score={s['score']}")
        all_new.extend(new)

    # 保存
    today = date.today().isoformat()
    save_dir = "F:/working-project/tdx-mcp/discoveries"
    os.makedirs(save_dir, exist_ok=True)
    with open(f"{save_dir}/sniper_{today}.json", "w", encoding="utf-8") as f:
        json.dump({"date": today, "hot_sectors": hot_names, "discoveries": discoveries, "new_candidates": all_new[:30]}, f, ensure_ascii=False, indent=2)

    print(f"\n  总计新候选: {len(all_new)} 只, 保存至 sniper_{today}.json")
    return all_new


if __name__ == "__main__":
    snipe()
