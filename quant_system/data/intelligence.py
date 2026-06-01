#!/usr/bin/env python3
"""
情报采集 — AKShare 多源数据拉取 + 交叉验证 + 市场状态判定。
从 tdx-mcp/orchestrator.py:collect_intelligence() 迁移，适配 quant_system 架构。

早报 (08:57) 和 Pipeline (09:32) 共用入口。
"""

import json
import re
from datetime import datetime, date

from quant_system.config import ensure_dir
from quant_system.evolution.param_loader import get_param


def collect_intelligence(save: bool = True) -> dict:
    """
    情报采集 — 从 AKShare 拉取热榜/电报/板块/新高，交叉验证，判定市场状态。

    返回 dict:
        hot_rank:         东方财富热榜 TOP30
        cls_news:         财联社电报标题
        sector_flow:      行业板块 TOP10
        high_consensus:   三共识标的 (热榜 ∩ 电报 ∩ 新高) 或双共识
        missed:           热榜中存在但电报未提及的标的 (漏判)
        market_state:     强势 / 震荡 / 收缩
        sh_index_change:  上证涨跌幅%
        sector_direction: 板块方向 TOP5
    """
    import akshare as ak

    hot = []
    news = []
    sector_flow = []
    cls_codes: set = set()
    high_codes: set = set()

    # 1. 东方财富热榜
    try:
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

    # 2. 财联社电报
    try:
        df = ak.stock_info_global_cls()
        if df is not None and len(df) > 0:
            for _, row in df.head(50).iterrows():
                title = str(row.get('标题', ''))
                content = str(row.get('内容', ''))
                text = title + content
                if title:
                    news.append(title)
                for match in re.finditer(r'\b([036]\d{5})\b', text):
                    cls_codes.add(match.group(1))
    except Exception as e:
        print(f"  [WARN] 电报获取失败: {e}")

    # 3. 行业板块
    try:
        df = ak.stock_board_industry_name_em()
        if df is not None and len(df) > 0:
            for _, row in df.head(10).iterrows():
                sector_flow.append(str(row.get('板块名称', '')))
    except Exception as e:
        print(f"  [WARN] 板块获取失败: {e}")

    # 4. 创 60 日新高标的
    try:
        df = ak.stock_rank_ljqs_em()
        if df is not None and len(df) > 0:
            for _, row in df.head(20).iterrows():
                code = str(row.get('代码', '')).strip()
                if code.isdigit() and len(code) == 6:
                    high_codes.add(code)
    except Exception:
        pass

    # 5. 交叉验证
    hot_codes = {h.get("code", "") for h in hot if h.get("code")}
    dual_hit = list(hot_codes & cls_codes)
    triple_hit = list(hot_codes & cls_codes & high_codes)
    missed = list(hot_codes - cls_codes)

    # 6. 市场状态 (上证)
    sh_pct = 0
    try:
        df_idx = ak.stock_zh_index_daily_em(symbol="sh000001")
        if df_idx is not None and len(df_idx) > 0:
            latest = df_idx.iloc[-1]
            sh_chg = float(latest.get('close', 0)) / float(latest.get('open', 1)) - 1
            sh_pct = round(sh_chg * 100, 2)
    except Exception:
        pass

    # 市场状态阈值从 params.json 读取
    bull = get_param('orchestrator.market_bull', 1.0)
    bear = get_param('orchestrator.market_bear', -1.0)

    market_state = "震荡"
    if sh_pct > bull:
        market_state = "强势"
    elif sh_pct < bear:
        market_state = "收缩"

    result = {
        "hot_rank": hot,
        "cls_news": news,
        "sector_flow": sector_flow,
        "high_consensus": triple_hit[:10] or dual_hit[:10],
        "missed": missed[:10],
        "market_state": market_state,
        "sh_index_change": sh_pct,
        "sector_direction": sector_flow[:5],
        "reasoning": "规则交叉验证 — 无 LLM 语义分析",
        "timestamp": str(datetime.now()),
    }

    # 保存到 storage/state/ 供复盘等消费
    if save:
        output_dir = ensure_dir("storage", "state")
        today = date.today().isoformat()
        fpath = f"{output_dir}/intelligence_{today}.json"
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    return result


if __name__ == "__main__":
    print("=" * 60)
    print(f"  Intelligence — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    result = collect_intelligence(save=True)
    print(f"\n  市场状态: {result['market_state']} (上证 {result['sh_index_change']:+.2f}%)")
    print(f"  共识标的: {len(result['high_consensus'])} 只")
    print(f"  漏判标的: {len(result['missed'])} 只")
    print(f"  板块方向: {', '.join(result['sector_direction'][:5])}")
    print(f"  热榜覆盖: {len(result['hot_rank'])} 只")
