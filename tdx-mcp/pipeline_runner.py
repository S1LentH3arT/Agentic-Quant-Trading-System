#!/usr/bin/env python3
"""
Pipeline Runner — 按顺序执行 Agent 流水线
情报 → 技术 → 发现 → 调度 (前一环节输出=下一环节输入)
"""

import sys, json, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import get_path, ensure_dir
from datetime import datetime, date

OUTPUT_DIR = ensure_dir("agents", "output")
TODAY = date.today().isoformat()

# ============================================================
# 通用: 读取前序输出
# ============================================================
def read_previous(agent_name: str) -> dict:
    fpath = os.path.join(OUTPUT_DIR, f"{agent_name}_{TODAY}.json")
    if os.path.exists(fpath):
        with open(fpath, encoding='utf-8') as f:
            return json.load(f)
    return {}


# ============================================================
# Step 1: 情报 Agent — 从 AKShare 拉取真实热榜
# ============================================================
def _fetch_hot_rank_em() -> list[str]:
    """从东方财富热榜获取今日热门股票代码"""
    try:
        import akshare as ak
        df = ak.stock_hot_rank_em()
        if df is not None and len(df) > 0:
            codes = []
            for _, row in df.head(30).iterrows():
                code = str(row.get('代码', '')).strip()
                if code.isdigit() and len(code) == 6:
                    codes.append(code)
            return codes
    except Exception as e:
        print(f"  [WARN] 东方财富热榜获取失败: {e}")
    return []


def _fetch_cls_telegraph() -> list[str]:
    """从财联社电报提取提及的股票代码"""
    try:
        import akshare as ak
        df = ak.stock_info_global_cls()
        if df is not None and len(df) > 0:
            codes = set()
            for _, row in df.head(50).iterrows():
                title = str(row.get('标题', ''))
                content = str(row.get('内容', ''))
                text = title + content
                for match in re.finditer(r'\b([036]\d{5})\b', text):
                    codes.add(match.group(1))
            return list(codes)
    except Exception as e:
        print(f"  [WARN] 财联社电报获取失败: {e}")
    return []


def _fetch_sector_flow() -> list[str]:
    """从行业资金流获取领涨板块"""
    try:
        import akshare as ak
        df = ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流")
        if df is not None and len(df) > 0:
            sectors = []
            for _, row in df.head(5).iterrows():
                sectors.append(str(row.get('名称', '')))
            return sectors
    except Exception as e:
        print(f"  [WARN] 板块资金流获取失败: {e}")
    return []


def _fetch_sector_spot_em() -> dict:
    """获取东方财富行业板块行情，返回涨幅TOP板块+成分股"""
    try:
        import akshare as ak
        df = ak.stock_board_industry_name_em()
        if df is not None and len(df) > 0:
            top_sectors = []
            for _, row in df.head(10).iterrows():
                top_sectors.append(str(row.get('板块名称', '')))
            return {"top_sectors": top_sectors}
    except Exception as e:
        print(f"  [WARN] 行业板块获取失败: {e}")
    return {"top_sectors": []}


def _fetch_new_highs() -> list[str]:
    """获取今日创60日新高的标的"""
    try:
        import akshare as ak
        df = ak.stock_rank_ljqs_em()
        if df is not None and len(df) > 0:
            codes = []
            for _, row in df.head(20).iterrows():
                code = str(row.get('代码', '')).strip()
                if code.isdigit() and len(code) == 6:
                    codes.append(code)
            return codes
    except Exception:
        pass
    return []


def run_intelligence():
    print("[Pipeline 1/4] 情报 Agent — 从 AKShare 拉取真实热榜+电报")
    print("  → 东方财富热榜...")
    hot_em = _fetch_hot_rank_em()
    print(f"     {len(hot_em)} 只热门")

    print("  → 财联社电报...")
    cls_codes = _fetch_cls_telegraph()
    print(f"     {len(cls_codes)} 只提及")

    print("  → 行业板块行情...")
    sector_info = _fetch_sector_spot_em()
    top_sectors = sector_info.get('top_sectors', [])
    print(f"     TOP板块: {', '.join(top_sectors[:5]) if top_sectors else '无'}")

    print("  → 连涨强势股...")
    high_codes = _fetch_new_highs()
    print(f"     {len(high_codes)} 只")

    # ── 交叉验证: 多源一致 = 高共识 ──
    hot_set = set(hot_em)
    cls_set = set(cls_codes)
    high_set = set(high_codes)

    high_consensus = list(hot_set & cls_set)  # 热榜 + 电报 双重验证
    triple_hit = list(hot_set & cls_set & high_set)  # 三方一致
    missed = list(hot_set - cls_set)  # 热榜有但电报没提

    # ── 判断市场状态 ──
    try:
        import akshare as ak
        df_idx = ak.stock_zh_index_daily_em(symbol="sh000001")
        if df_idx is not None and len(df_idx) > 0:
            latest = df_idx.iloc[-1]
            sh_chg = float(latest.get('close', 0)) / float(latest.get('open', 1)) - 1
            sh_pct = round(sh_chg * 100, 2)
        else:
            sh_pct = 0
    except Exception:
        sh_pct = 0

    market_state = "震荡"
    if sh_pct > 1:
        market_state = "强势"
    elif sh_pct < -1:
        market_state = "收缩"

    output = {
        "timestamp": str(datetime.now()),
        "high_consensus": triple_hit[:10] or high_consensus[:10],
        "hot_rank": hot_em[:20],
        "cls_mentions": cls_codes[:20],
        "high_streak": high_codes[:20],
        "sector_direction": top_sectors[:5],
        "missed": missed[:10],
        "market_state": market_state,
        "sh_index_change": sh_pct,
        "source": "AKShare实时",
    }

    fpath = os.path.join(OUTPUT_DIR, f"intelligence_{TODAY}.json")
    with open(fpath, "w", encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"  → 共识{len(output['high_consensus'])}只, 漏判{len(output['missed'])}只, 市场={market_state}")
    return output


# ============================================================
# Step 2: 技术 Agent (使用增强评分)
# ============================================================
def run_technical(intel: dict):
    print("[Pipeline 2/4] 技术 Agent — 增强评分(含DKX否决)")
    from indicator_engine import load_kline, calc_all_indicators, get_summary, score_stock
    from rolling_capital import get_full_pool

    missed = intel.get('missed', [])
    pool = get_full_pool()
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
        except Exception:
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
    fpath = os.path.join(OUTPUT_DIR, f"technical_{TODAY}.json")
    with open(fpath, "w", encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"  → 合格{len(qualified)}只, 否决{len(vetoed)}只, TOP={top['symbol'] if top else '无'}")
    return output


# ============================================================
# Step 3: 发现 Agent
# ============================================================
def run_discovery(tech: dict, intel: dict):
    print("[Pipeline 3/4] 发现 Agent — 板块狙击+入库")
    from discovery_engine import run_discovery as do_discovery
    result = do_discovery(max_scan=300)
    return result


# ============================================================
# Step 4: 调度 Agent
# ============================================================
def run_deployment(tech: dict):
    print("[Pipeline 4/4] 调度 Agent — 基于已验证评分部署")

    qualified = tech.get('qualified', [])
    valid = [q for q in qualified if q.get('a1x_dir') == '↑']
    valid.sort(key=lambda x: x['score'], reverse=True)

    # 从账户读取实际可用资金（尝试 easytrader，失败则用估算值）
    try:
        from trading_adapter import get_account
        acct = get_account()
        cash = acct.get('available', 0)
        if cash <= 0:
            cash = 7896  # fallback
    except Exception:
        cash = 7896

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

    fpath = os.path.join(OUTPUT_DIR, f"deployment_{TODAY}.json")
    with open(fpath, "w", encoding='utf-8') as f:
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

    print(f"\n{'='*60}")
    print(f"  Pipeline 完成")
    print(f"{'='*60}")
    print(f"  情报: {len(intel['high_consensus'])}共识 + {len(intel['missed'])}漏判")
    print(f"  技术: {tech['qualified_count']}合格 + {tech['vetoed_count']}否决")
    print(f"  部署: {dep['deploy']['action']}")
    return {"intel": intel, "tech": tech, "discovery": disc, "deployment": dep}


if __name__ == "__main__":
    run_pipeline()
