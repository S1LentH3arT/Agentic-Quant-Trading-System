#!/usr/bin/env python3
"""
Pipeline Runner — 按顺序执行 Agent 流水线
情报 → 技术 → 发现 → 调度 (前一环节输出=下一环节输入)
"""

import sys, json, os
sys.path.insert(0, 'F:/working-project/tdx-mcp')
sys.stdout.reconfigure(encoding='utf-8')
from datetime import datetime, date

OUTPUT_DIR = "F:/working-project/agents/output"
os.makedirs(OUTPUT_DIR, exist_ok=True)
TODAY = date.today().isoformat()

# ============================================================
# 通用: 读取前序输出
# ============================================================
def read_previous(agent_name: str) -> dict:
    fpath = f"{OUTPUT_DIR}/{agent_name}_{TODAY}.json"
    if os.path.exists(fpath):
        with open(fpath, encoding='utf-8') as f:
            return json.load(f)
    return {}

# ============================================================
# Step 1: 情报 Agent
# ============================================================
def run_intelligence():
    print("[Pipeline 1/4] 情报 Agent — 输出共识标的+板块方向")
    # 模拟: 在实际 cron 中由 WebSearch 提供, 这里用已知数据
    output = {
        "timestamp": str(datetime.now()),
        "high_consensus": ["000725", "002050", "001896"],
        "sector_direction": ["液冷", "玻璃基板", "大金融"],
        "missed": ["000725", "002050", "001896"],
        "market_state": "收缩",
        "note": "上证-2.04%, 845亿主力流出, 防御为主"
    }
    with open(f"{OUTPUT_DIR}/intelligence_{TODAY}.json", "w", encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"  → 共识{len(output['high_consensus'])}只, 漏判{len(output['missed'])}只")
    return output

# ============================================================
# Step 2: 技术 Agent (使用增强评分)
# ============================================================
def run_technical(intel: dict):
    print("[Pipeline 2/4] 技术 Agent — 增强评分(含DKX否决)")
    from indicator_engine import load_kline, calc_all_indicators, get_summary, score_stock
    from rolling_capital import get_full_pool

    # 读取漏判 → 优先入库
    missed = intel.get('missed', [])
    pool = get_full_pool()

    # 漏判标的加入扫描
    all_candidates = list(dict.fromkeys(missed + pool))

    qualified = []
    vetoed = []
    for sym in all_candidates[:100]:
        try:
            df = load_kline(sym, count=60)
            df = calc_all_indicators(df)
            s = get_summary(df, sym)
            sc = score_stock(df)
            if sc.get('veto'):
                vetoed.append({"symbol": sym, "reason": sc['details'][0]})
            elif sc['score'] >= 5:
                qualified.append({
                    "symbol": sym, "score": sc['score'],
                    "A1X": s['A1X'], "a1x_dir": s['a1x_direction'],
                    "box_pos": s['box_position_pct'], "close": s['close'],
                    "DZT": s['DZT'], "ZZJC": s['ZZJC']
                })
        except:
            pass

    qualified.sort(key=lambda x: x['score'], reverse=True)
    top = qualified[0] if qualified else None

    output = {
        "timestamp": str(datetime.now()),
        "pool_total": len(all_candidates),
        "scanned": len(qualified) + len(vetoed),
        "qualified_count": len(qualified),
        "vetoed_count": len(vetoed),
        "qualified": qualified[:20],
        "vetoed": vetoed[:20],
        "top_pick": top,
    }
    with open(f"{OUTPUT_DIR}/technical_{TODAY}.json", "w", encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"  → 合格{len(qualified)}只, 否决{len(vetoed)}只, TOP={top['symbol'] if top else '无'}")
    return output

# ============================================================
# Step 3: 发现 Agent
# ============================================================
def run_discovery(tech: dict, intel: dict):
    print("[Pipeline 3/4] 发现 Agent — 板块狙击+入库")
    from discovery_engine import run_discovery
    result = run_discovery(max_scan=300)
    return result

# ============================================================
# Step 4: 调度 Agent (只读技术 Agent 的已验证评分)
# ============================================================
def run_deployment(tech: dict):
    print("[Pipeline 4/4] 调度 Agent — 基于已验证评分部署")

    # 核心: 只读 technical Agent 的 qualified 列表
    qualified = tech.get('qualified', [])
    # 排除 A1X 方向向下的
    valid = [q for q in qualified if q.get('a1x_dir') == '↑']
    valid.sort(key=lambda x: x['score'], reverse=True)

    cash = 6304  # 明日离场后

    if not valid:
        output = {
            "timestamp": str(datetime.now()),
            "capital_status": {"cash": cash, "idle_days": 0},
            "deploy": {"action": "HOLD_CASH", "reason": "无评分>=5且A1X↑的候选"},
        }
    else:
        top = valid[0]
        price = top['close']
        max_lots = min(int(cash / (price * 100)), 4)
        output = {
            "timestamp": str(datetime.now()),
            "capital_status": {"cash": cash, "idle_days": 0},
            "deploy": {
                "action": "DEPLOY" if max_lots > 0 else "HOLD_CASH",
                "symbol": top['symbol'],
                "price": price,
                "lots": max_lots,
                "score": top['score'],
                "A1X": top['A1X'],
                "reason": f"评分{top['score']}/A1X={top['A1X']}/箱体{top['box_pos']}%"
            } if max_lots > 0 else {"action": "HOLD_CASH", "reason": "价格超资金上限"},
        }

    with open(f"{OUTPUT_DIR}/deployment_{TODAY}.json", "w", encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    dep = output['deploy']
    print(f"  → {dep['action']}: {dep.get('reason','')}")
    return output

# ============================================================
# Pipeline 主控
# ============================================================
def run_pipeline():
    print("=" * 60)
    print(f"  Pipeline Runner — {TODAY}")
    print(f"  情报 → 技术 → 发现 → 调度")
    print("=" * 60)

    intel = run_intelligence()
    tech = run_technical(intel)
    disc = run_discovery(tech, intel)
    dep = run_deployment(tech)

    # 最终交叉验证
    print(f"\n{'='*60}")
    print(f"  Pipeline 完成")
    print(f"{'='*60}")
    print(f"  情报: {len(intel['high_consensus'])}共识 + {len(intel['missed'])}漏判")
    print(f"  技术: {tech['qualified_count']}合格 + {tech['vetoed_count']}否决")
    print(f"  部署: {dep['deploy']['action']}")
    return {"intel": intel, "tech": tech, "discovery": disc, "deployment": dep}

if __name__ == "__main__":
    run_pipeline()
