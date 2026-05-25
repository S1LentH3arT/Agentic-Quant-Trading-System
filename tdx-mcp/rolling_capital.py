#!/usr/bin/env python3
"""
资金滚动引擎 — 唯一使命: 钱不能停
现金>1000且闲置>24h → 强迫轮动
5种极端场景外, 永远在滚动
"""

import sys, json, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import get_path, ensure_dir
sys.stdout.reconfigure(encoding='utf-8')
from mootdx.quotes import StdQuotes
from indicator_engine import load_kline, calc_all_indicators, get_summary, score_stock
from datetime import datetime, date, timedelta

# ============================================================
# 配置
# ============================================================
POSITIONS = {}
CASH = 7895.73
TOTAL_CAPITAL = 7895.73
IDLE_SINCE = "2026-05-22"
STATE_FILE = get_path("tdx-mcp", "state", "rolling_state.json")

# 极端场景检测
def detect_extreme() -> dict:
    """检查是否触发停机条件"""
    client = StdQuotes(host='218.6.170.47', port=7709, timeout=5)
    try:
        data = client.quotes(symbol=['000001'])
        if hasattr(data, 'iterrows'):
            for _, r in data.iterrows():
                chg = float(r.get('change_pct', 0) or 0)
                if chg <= -5:
                    return {"extreme": True, "reason": "上证暴跌>5%", "action": "全清+暂停3天"}
    except:
        pass

    try:
        scan_dir = get_path("tdx-mcp", "scans")
        if os.path.exists(scan_dir):
            files = sorted([f for f in os.listdir(scan_dir) if f.endswith('.json') and not f.startswith('week')])
            if files:
                with open(f"{scan_dir}/{files[-1]}", encoding='utf-8') as f:
                    latest = json.load(f)
                metrics = latest.get('objective_metrics', {}).get('metrics', {})
                if metrics.get('max_drawdown_pct', 0) >= 15:
                    return {"extreme": True, "reason": "月回撤>15%", "action": "暂停3天"}
    except:
        pass

    return {"extreme": False, "reason": None, "action": None}

# 资金状态
def capital_status() -> dict:
    """当前资金部署状态"""
    client = StdQuotes(host='218.6.170.47', port=7709, timeout=5)
    data = client.quotes(symbol=list(POSITIONS.keys()))

    deployed = 0
    sellable = 0
    for _, r in data.iterrows():
        sym = str(r.get('code', ''))
        price = float(r.get('price', 0) or 0)
        cfg = POSITIONS.get(sym, {})
        lots = cfg.get('lots', 0)
        mv = price * lots * 100
        deployed += mv
        if cfg.get('status') == 'SELL':
            sellable += mv

    effective_cash = CASH + sellable
    days_idle = (date.today() - date.fromisoformat(IDLE_SINCE)).days

    idle_too_long = effective_cash > 1000 and days_idle >= 1
    forced_rotation = effective_cash > 2000 and days_idle >= 2

    return {
        "total_capital": round(deployed + CASH, 0),
        "deployed": round(deployed, 0),
        "cash": CASH,
        "sellable_cash": round(sellable, 0),
        "effective_cash": round(effective_cash, 0),
        "days_idle": days_idle,
        "idle_too_long": idle_too_long,
        "forced_rotation": forced_rotation,
    }

# 候选排名
def get_full_pool() -> list[str]:
    """获取完整候选池 = 22只主力 + 发现池 + 今日狙击发现"""
    pool = []
    main_pool = ["600863","601991","000070","600089","600406","601179","600312","000400","600875","300827","600379","600900","600011","300903","600183","002463","601698","603881","300608","688500","002272","002892","002421"]
    pool.extend(main_pool)
    for fname in ["discovery_pool.json", f"sniper_{date.today().isoformat()}.json"]:
        fpath = get_path("tdx-mcp", "discoveries", fname)
        if os.path.exists(fpath):
            with open(fpath, encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                for key in data:
                    if isinstance(key, str) and key.isdigit() and len(key) == 6:
                        pool.append(key)
                    if isinstance(data[key], dict):
                        if 'symbol' in data[key]:
                            pool.append(data[key]['symbol'])
                        for subkey in data[key]:
                            if isinstance(data[key][subkey], list):
                                for item in data[key][subkey]:
                                    if isinstance(item, dict) and 'symbol' in item:
                                        pool.append(item['symbol'])
    return list(dict.fromkeys(pool))

def rank_candidates() -> list[dict]:
    """从完整候选池中排名所有候选"""
    pool_symbols = get_full_pool()
    results = []
    for sym in pool_symbols:
        try:
            df = load_kline(sym, count=60)
            df = calc_all_indicators(df)
            s = get_summary(df, sym)
            sc = score_stock(df)
            if sc['score'] >= 5:
                results.append({"symbol": sym, "score": sc['score'], "A1X": s['A1X'], "a1x_dir": s['a1x_direction'], "box_pos": s['box_position_pct'], "close": s['close'], "DZT": s['DZT'], "ZZJC": s['ZZJC']})
        except:
            pass
    results.sort(key=lambda x: x['score'], reverse=True)
    return results

def deploy_recommendation(candidates: list[dict], available_cash: float) -> dict:
    """给定候选池和可用资金, 输出部署方案"""
    if not candidates:
        return {"action": "HOLD_CASH", "reason": "无评分>=5的候选"}

    top = candidates[0]
    price = top['close']
    max_lots = int(available_cash / (price * 100))
    if max_lots == 0 and available_cash >= 1000:
        for c in candidates:
            if c['close'] * 100 <= available_cash:
                top = c
                price = c['close']
                max_lots = int(available_cash / (price * 100))
                break

    if max_lots == 0:
        return {"action": "HOLD_CASH", "reason": f"可用{available_cash}不够买最低候选价{price}"}

    return {
        "action": "DEPLOY",
        "symbol": top['symbol'],
        "price": price,
        "lots": min(max_lots, 4),
        "score": top['score'],
        "capital_needed": price * min(max_lots, 4) * 100,
        "A1X": top['A1X'],
        "box_pos": top['box_pos'],
        "reason": f"评分{top['score']}/A1X={top['A1X']}/箱体{top['box_pos']}%"
    }

def check():
    print("=" * 60)
    print("  资金滚动引擎")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    extreme = detect_extreme()
    if extreme['extreme']:
        print(f"\n  STOP: {extreme['reason']} → {extreme['action']}")
        return {"status": "STOPPED", "reason": extreme['reason']}

    cap = capital_status()
    print(f"\n  总资产: {cap['total_capital']:.0f} | 持仓: {cap['deployed']:.0f} | 现金: {cap['cash']:.0f} | 可释放: {cap['sellable_cash']:.0f}")
    print(f"  有效现金: {cap['effective_cash']:.0f} | 闲置: {cap['days_idle']}天")

    if cap['forced_rotation']:
        print(f"\n  !!! 强迫轮动: 现金>{cap['effective_cash']:.0f}闲置>{cap['days_idle']}天")

    print("\n  扫描候选...")
    candidates = rank_candidates()
    print(f"  评分>=5的候选: {len(candidates)} 只")
    if candidates:
        for i, c in enumerate(candidates[:5]):
            tag = "DZT!" if c['DZT'] else ""
            print(f"  {i+1}. {c['symbol']} score={c['score']} A1X={c['A1X']}({c['a1x_dir']}) box={c['box_pos']}% {tag}")

    effective_cash = cap['effective_cash']
    if effective_cash >= 1000:
        deploy = deploy_recommendation(candidates, effective_cash)
        print(f"\n  部署建议: {deploy['action']}")
        if deploy['action'] == 'DEPLOY':
            print(f"  标的: {deploy['symbol']} | 价格: {deploy['price']} | 手数: {deploy['lots']} | 资金: {deploy['capital_needed']:.0f}")
            print(f"  逻辑: {deploy['reason']}")
        else:
            print(f"  原因: {deploy['reason']}")
    elif cap['forced_rotation']:
        print(f"\n  !!! 强迫轮动激活 — 必须24h内部署有效现金{effective_cash:.0f}")

    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    state = {"timestamp": str(datetime.now()), "capital": cap, "extreme": extreme, "candidates_top5": [c['symbol'] for c in candidates[:5]], "deploy": deploy_recommendation(candidates, effective_cash) if effective_cash >= 1000 else None}
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    return state

if __name__ == "__main__":
    check()
