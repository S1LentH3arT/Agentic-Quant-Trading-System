#!/usr/bin/env python3
# tdx-mcp/orchestrator.py
"""
编排器 — 情报先行 → 三路并行 → 沛总汇总
默认影子模式 (use_llm=False)，不调 LLM，安全第一
"""
import sys, os, json, time
from datetime import datetime, date
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import get_path, ensure_dir

# LLM Agent 层
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from llm.agents.intelligence_agent import IntelligenceAgent
from llm.agents.technical_agent import TechnicalAgent
from llm.agents.discovery_agent import DiscoveryAgent
from llm.agents.deployment_agent import DeploymentAgent
from llm.agents.chief_agent import ChiefAgent


def _collect_intelligence_data() -> dict:
    """收集情报 Agent 需要的原始数据 (AKShare)"""
    hot = []
    news = []
    sector_flow = []

    # 东方财富热榜
    try:
        import akshare as ak
        df = ak.stock_hot_rank_em()
        if df is not None and len(df) > 0:
            for _, row in df.head(30).iterrows():
                hot.append({
                    "code": str(row.get('代码', '')).strip(),
                    "name": str(row.get('名称', '')).strip(),
                    "price": row.get('最新价', 0),
                    "change_pct": float(row.get('涨跌幅', 0) or 0),
                })
    except Exception as e:
        print(f"  [WARN] 热榜获取失败: {e}")

    # 财联社电报
    try:
        import akshare as ak
        import re
        df = ak.stock_info_global_cls()
        if df is not None and len(df) > 0:
            for _, row in df.head(10).iterrows():
                title = str(row.get('标题', ''))
                if title:
                    news.append(title)
    except Exception as e:
        print(f"  [WARN] 电报获取失败: {e}")

    # 行业板块
    try:
        import akshare as ak
        df = ak.stock_board_industry_name_em()
        if df is not None and len(df) > 0:
            for _, row in df.head(5).iterrows():
                sector_flow.append(str(row.get('板块名称', '')))
    except Exception as e:
        print(f"  [WARN] 板块获取失败: {e}")

    return {"hot_rank": hot, "cls_news": news, "sector_flow": sector_flow}


def _collect_technical_data(intel_output: dict) -> dict:
    """收集技术 Agent 需要的数据: 主力池全量计算"""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from indicator_engine import load_kline, calc_all_indicators, get_summary, score_stock

    # 22只主力池
    main_pool = [
        "600863","601991","000070","600089","600406","601179","600312","000400",
        "600875","300827","600379","600900","600011","300903","600183","002463",
        "601698","603881","300608","688500","002272","002892","002421"
    ]

    # 加上情报漏判
    missed = intel_output.get("missed", [])
    candidates = list(dict.fromkeys(missed + main_pool))

    results = []
    for sym in candidates[:30]:
        try:
            df = load_kline(sym, count=120)
            df = calc_all_indicators(df)
            s = get_summary(df, sym)
            sc = score_stock(df)
            results.append({
                "symbol": sym, "summary": s, "score": sc["score"],
                "details": sc.get("details", []), "veto": sc.get("veto", False),
            })
        except Exception as e:
            pass

    # 板块聚合
    sector_results = {}
    try:
        from decision_engine import rank_all_sectors
        scan = rank_all_sectors()
        sector_results = {
            k: {"avg_score": v["avg_score"], "rankings": v["rankings"][:8]}
            for k, v in scan.items()
        }
    except Exception as e:
        print(f"  [WARN] 板块扫描失败: {e}")

    return {"main_pool_results": results, "sector_results": sector_results}


def _collect_discovery_data(intel_output: dict) -> dict:
    """收集发现 Agent 需要的数据: 全市场粗筛"""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from discovery_engine import coarse_filter, quick_scan
        from mootdx.quotes import StdQuotes
        client = StdQuotes(host='218.6.170.47', port=7709, timeout=8)
        candidates = coarse_filter(client)
        discoveries = quick_scan(candidates, max_scan=200)
        return {
            "scan_results": discoveries[:30],
            "sector_direction": intel_output.get("sector_direction", []),
        }
    except Exception as e:
        print(f"  [WARN] 发现扫描失败: {e}")
        return {"scan_results": [], "sector_direction": [], "error": str(e)}


def _collect_deployment_data(technical_output: dict) -> dict:
    """收集调度 Agent 需要的数据: 账户 + Kelly"""
    qualified = technical_output.get("qualified", [])
    cash = 7896  # fallback

    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from trading_adapter import get_account
        acct = get_account()
        cash = acct.get("available", cash)
    except Exception:
        pass

    # Kelly 仓位计算 (纯数学, 不经过 LLM)
    top = qualified[0] if qualified else None
    kelly = {"fraction": 0, "lots": 0}
    if top and top.get("close", 0) > 0:
        price = top["close"]
        score = top.get("score", 0)
        if score >= 6:
            kelly_frac = min(0.10 + (score - 6) * 0.05, 0.25)
            lots = min(int(cash * kelly_frac / (price * 100)), 4)
            kelly = {"fraction": round(kelly_frac * 100, 1), "lots": max(lots, 1)}

    # 极端场景
    extreme = {"extreme": False, "reason": None, "action": None}
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from rolling_capital import detect_extreme
        extreme = detect_extreme()
    except Exception:
        pass

    return {
        "qualified_top5": qualified[:5],
        "account": {"available": cash, "total": cash, "idle_days": 0},
        "kelly_result": kelly,
        "extreme": extreme,
    }


def run_orchestrator(use_llm: bool = False) -> dict:
    """
    一键运行完整 Pipeline。
    use_llm=False (默认) → 影子模式，仅 Python 计算
    use_llm=True → LLM 增强模式
    """
    print("=" * 60)
    print(f"  Orchestrator — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  LLM: {'ON' if use_llm else 'OFF (shadow mode)'}")
    print("=" * 60)

    # ── Step 1: 情报 Agent (单线程) ──
    print("\n[1/3] 情报 Agent...")
    t0 = time.time()
    intel_data = _collect_intelligence_data()

    if use_llm:
        try:
            intel_agent = IntelligenceAgent()
            intel_output = intel_agent.run(**intel_data)
        except Exception as e:
            print(f"  [WARN] LLM 情报失败, 降级: {e}")
            intel_output = _shadow_intel(intel_data)
    else:
        intel_output = _shadow_intel(intel_data)

    print(f"  → {len(intel_output.get('high_consensus',[]))} 共识标的 ({time.time()-t0:.1f}s)")

    # ── Step 2: 三路并行 ──
    print("\n[2/3] 技术 + 发现 + 调度 (并行)...")
    t0 = time.time()

    # Python 数据收集 (主线程, 避免 mootdx 连接冲突)
    tech_data = _collect_technical_data(intel_output)
    disc_data = _collect_discovery_data(intel_output)
    depl_data = _collect_deployment_data({
        "qualified": [
            r for r in tech_data["main_pool_results"]
            if not r.get("veto") and r.get("score", 0) >= 5
        ]
    })

    results = {"technical": {}, "discovery": {}, "deployment": {}}

    if use_llm:
        agents_map = {
            "technical": (TechnicalAgent(), tech_data),
            "discovery": (DiscoveryAgent(), disc_data),
            "deployment": (DeploymentAgent(), depl_data),
        }
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {}
            for name, (agent, data) in agents_map.items():
                futures[pool.submit(agent.run, **data)] = name
            for future in as_completed(futures):
                name = futures[future]
                try:
                    results[name] = future.result(timeout=30)
                except Exception as e:
                    print(f"  [WARN] {name} Agent 失败: {e}")
                    results[name] = {"error": str(e), "fallback": True}
    else:
        results["technical"] = _shadow_technical(tech_data)
        results["discovery"] = _shadow_discovery(disc_data)
        results["deployment"] = _shadow_deployment(depl_data)

    print(f"  → 完成 ({time.time()-t0:.1f}s)")

    # ── Step 3: 沛总 Agent ──
    print("\n[3/3] 沛总 Agent...")
    t0 = time.time()

    market_data = _collect_market_data()

    if use_llm:
        try:
            chief = ChiefAgent()
            final = chief.run(
                intel_output=intel_output,
                technical_output=results["technical"],
                discovery_output=results["discovery"],
                deployment_output=results["deployment"],
                sector_results=tech_data.get("sector_results", {}),
                market_data=market_data,
            )
        except Exception as e:
            print(f"  [WARN] 沛总 LLM 失败, 降级: {e}")
            final = _shadow_chief(results)
    else:
        final = _shadow_chief(results)

    print(f"  → 最终裁决: {final.get('final_action','?')} ({time.time()-t0:.1f}s)")

    # ── 保存结果 ──
    today = date.today().isoformat()
    output_dir = ensure_dir("tdx-mcp", "shadows" if not use_llm else "agents", "output")
    output_file = os.path.join(output_dir, f"pipeline_{today}.json")
    full_output = {
        "timestamp": str(datetime.now()),
        "use_llm": use_llm,
        "intelligence": intel_output,
        **results,
        "chief_decision": final,
    }
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(full_output, f, ensure_ascii=False, indent=2)
    print(f"\n  → 保存至 {output_file}")

    return full_output


# ── 影子模式 fallback 函数 (纯规则, 不调 LLM) ──

def _shadow_intel(data: dict) -> dict:
    hot = data.get("hot_rank", [])
    return {
        "high_consensus": [h.get("code","") for h in hot[:10] if h.get("code","")],
        "sector_direction": data.get("sector_flow", [])[:3],
        "missed": [],
        "market_state": "震荡",
        "reasoning": "影子模式 — 基于热榜代码提取, 无 LLM 语义分析",
    }

def _shadow_technical(data: dict) -> dict:
    results = data.get("main_pool_results", [])
    qualified = [r for r in results if not r.get("veto") and r.get("score", 0) >= 5]
    vetoed = [r for r in results if r.get("veto")]
    return {
        "qualified": qualified[:10],
        "vetoed": vetoed[:10],
        "sector_insight": "影子模式 — 基于评分排序, 无 LLM 多周期解读",
        "top_pick_analysis": "",
    }

def _shadow_discovery(data: dict) -> dict:
    scan = data.get("scan_results", [])
    return {
        "new_candidates": scan[:10],
        "sector_coverage": "影子模式 — 基于扫描结果, 无 LLM 模式识别",
        "notable_pattern": "",
    }

def _shadow_deployment(data: dict) -> dict:
    q = data.get("qualified_top5", [])
    ext = data.get("extreme", {})
    if ext.get("extreme"):
        return {"action": "HOLD_CASH", "symbol": "", "lots": 0,
                "reason": f"极端场景: {ext.get('reason','')}", "risk_note": ""}
    if not q:
        return {"action": "HOLD_CASH", "symbol": "", "lots": 0,
                "reason": "无评分>=5的候选", "risk_note": ""}
    top = q[0]
    kelly = data.get("kelly_result", {})
    return {
        "action": "DEPLOY" if kelly.get("lots", 0) > 0 else "HOLD_CASH",
        "symbol": top.get("symbol", ""),
        "lots": kelly.get("lots", 0),
        "reason": f"评分{top.get('score',0)}/Kelly={kelly.get('fraction',0)}%",
        "risk_note": "影子模式 — 基于规则计算, 无 LLM 判断",
    }

def _shadow_chief(results: dict) -> dict:
    dep = results.get("deployment", {})
    return {
        "final_action": "APPROVE",
        "approved_deployment": dep,
        "conflicts_found": [],
        "conflicts_resolved": "",
        "daily_review_preview": "影子模式 — 无 LLM 复盘",
        "memory_note": "",
    }

def _collect_market_data() -> dict:
    """收集市场宏观数据"""
    md = {"limit_down_count": 0, "up_count": 0, "market_style": "未知", "sh_index_pct": 0}
    try:
        from mootdx.quotes import StdQuotes
        client = StdQuotes(host='218.6.170.47', port=7709, timeout=5)
        data = client.quotes(symbol=['000001'])
        if hasattr(data, 'iterrows'):
            for _, r in data.iterrows():
                md["sh_index_pct"] = float(r.get('change_pct', 0) or 0)
    except Exception:
        pass
    return md


if __name__ == "__main__":
    # 默认影子模式运行（安全，不产生 API 费用）
    run_orchestrator(use_llm=False)
