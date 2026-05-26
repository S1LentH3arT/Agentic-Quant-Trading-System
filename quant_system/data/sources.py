#!/usr/bin/env python3
"""
数据源定义 — 所有可用数据源及其 schema 定义。
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DataSource:
    """数据源定义"""
    name: str
    description: str
    category: str           # kline / capital / fundamental / chip / macro
    akshare_func: str       # AKShare 函数名 (如 'stock_zh_a_hist')
    update_frequency: str   # daily / weekly / quarterly / realtime
    cache_seconds: int      # 缓存有效期 (秒)


# ── 数据源注册表 ──
SOURCES = {
    # 行情
    "kline_daily": DataSource(
        name="kline_daily",
        description="A股日线K线 (前复权)",
        category="kline",
        akshare_func="stock_zh_a_hist",
        update_frequency="daily",
        cache_seconds=3600,
    ),
    "kline_weekly": DataSource(
        name="kline_weekly",
        description="A股周线K线 (前复权)",
        category="kline",
        akshare_func="stock_zh_a_hist",
        update_frequency="weekly",
        cache_seconds=86400,
    ),
    "kline_monthly": DataSource(
        name="kline_monthly",
        description="A股月线K线 (前复权)",
        category="kline",
        akshare_func="stock_zh_a_hist",
        update_frequency="monthly",
        cache_seconds=86400,
    ),
    "realtime_spot": DataSource(
        name="realtime_spot",
        description="A股实时行情",
        category="kline",
        akshare_func="stock_zh_a_spot_em",
        update_frequency="realtime",
        cache_seconds=30,
    ),
    "hot_rank": DataSource(
        name="hot_rank",
        description="东方财富热榜",
        category="kline",
        akshare_func="stock_hot_rank_em",
        update_frequency="realtime",
        cache_seconds=300,
    ),
    "sector_flow": DataSource(
        name="sector_flow",
        description="行业板块资金流向",
        category="kline",
        akshare_func="stock_board_industry_name_em",
        update_frequency="daily",
        cache_seconds=1800,
    ),

    # 资金
    "north_bound_flow": DataSource(
        name="north_bound_flow",
        description="北向资金流向",
        category="capital",
        akshare_func="stock_hsgt_hist_em",
        update_frequency="daily",
        cache_seconds=3600,
    ),
    "institution_holdings": DataSource(
        name="institution_holdings",
        description="机构持仓 (基金重仓)",
        category="capital",
        akshare_func="stock_report_fund_hold_detail_em",
        update_frequency="quarterly",
        cache_seconds=86400,
    ),

    # 财报
    "financial_indicators": DataSource(
        name="financial_indicators",
        description="财务指标 (利润/毛利/现金流/ROE)",
        category="fundamental",
        akshare_func="stock_financial_analysis_indicator",
        update_frequency="quarterly",
        cache_seconds=86400,
    ),
    "stock_profile": DataSource(
        name="stock_profile",
        description="个股信息 (行业/市盈率/市净率)",
        category="fundamental",
        akshare_func="stock_individual_info_em",
        update_frequency="daily",
        cache_seconds=3600,
    ),
    "pe_pb_history": DataSource(
        name="pe_pb_history",
        description="PE/PB历史分位",
        category="fundamental",
        akshare_func="stock_a_lg_indicator",
        update_frequency="daily",
        cache_seconds=3600,
    ),

    # 筹码
    "shareholder_count": DataSource(
        name="shareholder_count",
        description="股东人数变化",
        category="chip",
        akshare_func="stock_holder_num_em",
        update_frequency="quarterly",
        cache_seconds=86400,
    ),
    "top10_holders": DataSource(
        name="top10_holders",
        description="十大流通股东",
        category="chip",
        akshare_func="stock_gdfx_top_10_em",
        update_frequency="quarterly",
        cache_seconds=86400,
    ),
    "lockup_shares": DataSource(
        name="lockup_shares",
        description="限售解禁",
        category="chip",
        akshare_func="stock_restricted_release_queue_em",
        update_frequency="daily",
        cache_seconds=86400,
    ),

    # 宏观/行业
    "industry_prosperity": DataSource(
        name="industry_prosperity",
        description="行业景气度指标",
        category="macro",
        akshare_func="stock_board_industry_summary_em",
        update_frequency="daily",
        cache_seconds=3600,
    ),
    "all_stock_codes": DataSource(
        name="all_stock_codes",
        description="全A股代码列表",
        category="kline",
        akshare_func="stock_info_a_code_name",
        update_frequency="daily",
        cache_seconds=86400,
    ),
}


def get_source(name: str) -> Optional[DataSource]:
    """获取数据源定义"""
    return SOURCES.get(name)


def list_sources(category: Optional[str] = None) -> list[str]:
    """列出所有/分类数据源"""
    if category:
        return [k for k, v in SOURCES.items() if v.category == category]
    return list(SOURCES.keys())
