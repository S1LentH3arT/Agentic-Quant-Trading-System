#!/usr/bin/env python3
"""
共识引擎 — 多源交叉验证, 缩小搜索空间, 提高命中率

逻辑:
1. 每天抓取官方媒体热榜 + 平台推荐
2. 与自发现标的 + 品种池做交叉
3. 多源一致的标的 → 高置信度 → 优先入库
4. 减少漏判、错判
"""

import sys, json, os
sys.path.insert(0, 'F:/working-project/tdx-mcp')
from datetime import datetime, date

# ============================================================
# 热榜源配置
# ============================================================
HOT_SOURCES = {
    "eastmoney_hot": {
        "name": "东方财富热榜",
        "search": "东方财富 热门股票 资金流向 热榜",
        "weight": 1.0,
    },
    "cls_hot": {
        "name": "财联社热榜",
        "search": "财联社 热门板块 涨停 龙头",
        "weight": 1.0,
    },
    "tonghuashun_hot": {
        "name": "同花顺热度",
        "search": "同花顺 热门股票 人气榜",
        "weight": 0.8,
    },
    "sector_wind": {
        "name": "板块风向",
        "search": "今日热点板块 资金流入 领涨",
        "weight": 1.2,
    },
    "broker_recommend": {
        "name": "券商推荐",
        "search": "券商推荐 个股 研报 买入评级",
        "weight": 0.9,
    },
}

# ============================================================
# 交叉验证逻辑
# ============================================================
def cross_validate(hot_symbols: set, discovery_symbols: list, pool_symbols: list) -> dict:
    """
    三层交叉:
    - 热榜出现 + 品种池已有 = 高置信 (主力标的正在被市场关注)
    - 热榜出现 + 发现池新标的 = 值得入库 (市场验证了系统判断)
    - 热榜出现 + 品种池没有 + 发现池没有 = 漏判 (系统没抓到, 需要手动关注)
    """
    pool_set = set(pool_symbols)
    discovery_set = set(d.get('symbol', '') for d in discovery_symbols)

    high_confidence = hot_symbols & pool_set        # 热榜 ∩ 品种池
    new_discovery = hot_symbols & discovery_set      # 热榜 ∩ 发现池
    missed = hot_symbols - pool_set - discovery_set  # 漏判

    return {
        "high_confidence": list(high_confidence),  # 优先级最高
        "new_discovery": list(new_discovery),       # 值得跟进
        "missed": list(missed),                     # 需要入库
        "hot_total": len(hot_symbols),
        "covered": len(high_confidence) + len(new_discovery),
        "missed_count": len(missed),
    }


# ============================================================
# 提取热榜标的 (从 WebSearch 结果中解析)
# ============================================================
def extract_symbols_from_text(text: str) -> set:
    """从搜索文本中提取6位股票代码"""
    import re
    codes = set()
    # 匹配6位数字代码 (0/3/6开头)
    for match in re.finditer(r'\b([036]\d{5})\b', text):
        codes.add(match.group(1))
    return codes


# ============================================================
# 资金效率检查
# ============================================================
def check_capital_efficiency(cash_amount: float, days_idle: int, last_action_date: str = None) -> dict:
    """
    资金不能停着不动。
    - 现金 > 1000 且空闲 > 1天 → 升级提醒
    - 现金 > 2000 且空闲 > 2天 → 强迫扫描
    """
    if days_idle <= 0:
        return {"status": "正常", "action": None}

    if cash_amount > 2000 and days_idle >= 2:
        return {
            "status": "强迫轮动",
            "action": "现金>2000且空闲>=2天, 必须24h内部署",
            "priority": "HIGH",
        }
    elif cash_amount > 1000 and days_idle >= 1:
        return {
            "status": "升级提醒",
            "action": "现金>1000且空闲>=1天, 今日复盘优先推荐替补",
            "priority": "MEDIUM",
        }
    return {"status": "正常", "action": None}


# ============================================================
# 共识报告生成
# ============================================================
def build_consensus_report(market_hot: str, pool: list, discoveries: list) -> dict:
    """
    生成每日共识报告:
    1. 从市场热榜提取标的
    2. 与品种池+发现池交叉
    3. 输出三层结果
    """
    hot_set = extract_symbols_from_text(market_hot)

    pool_symbols = [p for p in pool if isinstance(p, str)]
    result = cross_validate(hot_set, discoveries, pool_symbols)

    # 资金检查
    cash_check = check_capital_efficiency(
        cash_amount=3800,  # 当前现金
        days_idle=1,        # 明天执行离场后释放更多
    )

    result['cash_check'] = cash_check
    result['timestamp'] = str(datetime.now())
    return result
