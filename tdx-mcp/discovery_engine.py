#!/usr/bin/env python3
"""
发现引擎 — 全市场自主扫描, 挖掘新标的, 自我扩展品种池
不依赖用户推荐, 系统自己从5000+只A股中筛选
"""

import sys, os, json
sys.path.insert(0, 'F:/working-project/tdx-mcp')
from mootdx.quotes import StdQuotes
from indicator_engine import load_kline, calc_all_indicators, get_summary, score_stock
from datetime import datetime, date

# ============================================================
# 第一层: 全市场粗筛 (秒级完成)
# ============================================================
def coarse_filter(client) -> list[str]:
    """从通达信板块成分股中构建候选池: 深市+沪市, 排除指数/ST/高价"""
    print("[1/4] 构建候选池...")
    candidates = set()

    # 方式1: 从深市获取股票 (market=0)
    try:
        sz_stocks = client.stocks(market=0)
        if hasattr(sz_stocks, 'iterrows'):
            for _, r in sz_stocks.iterrows():
                code = str(r.get('code', ''))
                if code.isdigit() and len(code) == 6 and code[0] in '023':
                    name = str(r.get('name', ''))
                    if 'ST' not in name and '指数' not in name and '主板' not in name:
                        candidates.add(code)
        print(f"      深市 {len(candidates)} 只")
    except Exception as e:
        print(f"      深市获取失败: {e}")

    # 方式2: 从沪市获取股票 (market=1)
    try:
        sh_stocks = client.stocks(market=1)
        if hasattr(sh_stocks, 'iterrows'):
            sh_count = 0
            for _, r in sh_stocks.iterrows():
                code = str(r.get('code', ''))
                if code.isdigit() and len(code) == 6 and code[0] == '6':
                    name = str(r.get('name', ''))
                    if 'ST' not in name and '指数' not in name:
                        candidates.add(code)
                        sh_count += 1
            print(f"      沪市 {sh_count} 只")
    except Exception as e:
        print(f"      沪市获取失败: {e}")

    # 方式3: 从板块成分股补充
    try:
        blocks = client.block()
        if hasattr(blocks, 'iterrows'):
            block_codes = set()
            for _, r in blocks.iterrows():
                code = str(r.get('code', ''))
                if code.isdigit() and len(code) == 6 and code[0] in '0236':
                    block_codes.add(code)
            before = len(candidates)
            candidates.update(block_codes)
            print(f"      板块补充 {len(candidates)-before} 只")
    except:
        pass

    total = len(candidates)
    print(f"      候选池总计 {total} 只")

    # 粗筛: 批量为100只, 获取价格过滤
    candidates = list(candidates)
    filtered = []
    batch_size = 100
    for i in range(0, len(candidates), batch_size):
        batch = candidates[i:i+batch_size]
        try:
            data = client.quotes(symbol=batch)
            if hasattr(data, 'iterrows'):
                for _, r in data.iterrows():
                    price = float(r.get('price', 0) or 0)
                    vol = float(r.get('vol', 0) or 0)
                    name = str(r.get('name', ''))
                    if 3 <= price <= 80 and vol > 0 and 'ST' not in name:
                        filtered.append(str(r.get('code', '')))
        except:
            pass

    print(f"      粗筛后 {len(filtered)} 只 (价格3-80, 有量, 非ST)")
    return filtered


# ============================================================
# 第二层: 快速指标扫描 (每只2-3秒, 可并行)
# ============================================================
def quick_scan(symbols: list[str], max_scan: int = 500) -> list[dict]:
    """对候选池做快速指标扫描, 按A1X和箱体位置筛选"""
    print(f"[2/4] 快速扫描 (最多{max_scan}只)...")

    # 按代码均匀采样
    if len(symbols) > max_scan:
        step = len(symbols) // max_scan
        symbols = symbols[::step][:max_scan]

    results = []
    for i, sym in enumerate(symbols):
        try:
            df = load_kline(sym, count=60)
            if df is None or len(df) < 40:
                continue
            df = calc_all_indicators(df)
            s = get_summary(df, sym)
            sc = score_stock(df)

            # 只关注有潜力的
            a1x = s['A1X']
            box = s['box_position_pct']
            vol = s['vol_ratio']

            # 发现条件: A1X在[-3, 3] AND 箱体中低位 AND 有量
            if -3 <= a1x <= 3 and box <= 50 and vol >= 0.8:
                results.append({
                    "symbol": sym,
                    "close": s['close'],
                    "A1X": round(a1x, 2),
                    "a1x_dir": s['a1x_direction'],
                    "box_pos": round(box, 1),
                    "vol_ratio": round(vol, 2),
                    "score": sc['score'],
                    "DZT": s['DZT'],
                    "details": sc['details'],
                })

            if (i+1) % 100 == 0:
                print(f"      {i+1}/{len(symbols)}... found {len(results)}")

        except:
            pass

    return results


# ============================================================
# 第三层: 去重+排除已有品种池
# ============================================================
def filter_existing(discoveries: list[dict], existing_pool: set) -> list[dict]:
    """排除已在品种池中的标的, 只保留新发现"""
    new = [d for d in discoveries if d['symbol'] not in existing_pool]
    print(f"[3/4] 新发现 {len(new)} 只 (排除{len(discoveries)-len(new)}只已有)")
    return new


# ============================================================
# 第四层: 保存+更新品种池
# ============================================================
def save_discoveries(discoveries: list[dict], top_n: int = 20):
    """保存发现结果, 更新品种池"""
    today = date.today().isoformat()
    save_dir = "F:/working-project/tdx-mcp/discoveries"
    os.makedirs(save_dir, exist_ok=True)

    # 按评分排序
    discoveries.sort(key=lambda d: d['score'], reverse=True)

    # 保存当日发现
    record = {
        "date": today,
        "timestamp": str(datetime.now()),
        "total_scanned": len(discoveries),
        "top_discoveries": discoveries[:top_n],
    }
    with open(f"{save_dir}/{today}.json", "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    # 更新候选池 (追加到品种池的发现层)
    pool_file = "F:/working-project/tdx-mcp/discoveries/discovery_pool.json"
    existing_pool = {}
    if os.path.exists(pool_file):
        with open(pool_file, encoding='utf-8') as f:
            existing_pool = json.load(f)

    for d in discoveries[:top_n]:
        sym = d['symbol']
        if sym not in existing_pool:
            existing_pool[sym] = {
                "first_found": today,
                "last_seen": today,
                "peak_score": d['score'],
                "latest_A1X": d['A1X'],
                "latest_box": d['box_pos'],
            }
        else:
            existing_pool[sym]['last_seen'] = today
            existing_pool[sym]['peak_score'] = max(existing_pool[sym]['peak_score'], d['score'])
            existing_pool[sym]['latest_A1X'] = d['A1X']

    with open(pool_file, "w", encoding='utf-8') as f:
        json.dump(existing_pool, f, ensure_ascii=False, indent=2)

    print(f"[4/4] 保存 {len(discoveries[:top_n])} 只到发现池, 总计 {len(existing_pool)} 只")
    return record


# ============================================================
# 一键发现
# ============================================================
def run_discovery(existing_symbols: list[str] = None, max_scan: int = 500):
    """全市场自主发现 — 一键运行"""
    print("=" * 60)
    print("  发现引擎 — 全市场自主挖掘")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    client = StdQuotes(host='218.6.170.47', port=7709, timeout=8)

    # 第一层
    candidates = coarse_filter(client)
    if candidates is None:
        return {"error": "无法获取全市场列表"}

    # 第二层
    discoveries = quick_scan(candidates, max_scan=max_scan)

    # 第三层
    if existing_symbols is None:
        existing_symbols = [
            "600863","601991","000070","600089","600406","601179","600312","000400",
            "600875","300827","600379","600900","600011","300903","600183","002463",
            "601698","603881","300608","688500","002272","002892","002421"
        ]
    existing_set = set(existing_symbols)
    new_discoveries = filter_existing(discoveries, existing_set)

    # 第四层
    record = save_discoveries(new_discoveries)

    # 输出 TOP10
    top = new_discoveries[:10]
    if top:
        print(f"\n  TOP 新发现:")
        for i, d in enumerate(top):
            print(f"  {i+1:>2}. {d['symbol']} A1X={d['A1X']} box={d['box_pos']}% vol={d['vol_ratio']}x score={d['score']}")

    return record


if __name__ == "__main__":
    run_discovery()
