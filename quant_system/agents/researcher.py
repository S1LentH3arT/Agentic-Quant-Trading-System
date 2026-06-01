#!/usr/bin/env python3
"""
QuantResearchAgent — 非结构化数据 → 结构化量化特征
不做交易决策，不产报告文本。输出可直接计算的纯数值。
"""

from quant_system.agents.base import ResearchAgent


class QuantResearchAgent(ResearchAgent):
    """市场数据 → 量化特征"""

    system_prompt = """
你是量化数据解析器。把市场原始数据转化为可计算的结构化特征。只输出 JSON，无解释文字。

输出必须用以下列名（与因子引擎列名一致）:

L1_industry — 每板块一条:
  sector: 板块名
  policy_support: -1(打压) 0(中性) 1(扶持), 从 news 推断
  research_catalyst: 0~1 消息催化强度, 从 news 推断
  avoid_flag: 下行/退潮=True

L2_capital — 每股票一条:
  symbol: 6位代码
  north_direction: -1(流出) 0(中性) 1(流入)
  north_duration: 0~30 连续加仓天数, 无数据=0
  institution_phase: -1(减仓) 0(无数据) 1(建仓) 2(加仓)
  institution_ratio: 0~1 机构持仓占比, 无数据=null

L3_fundamentals — 每股票一条:
  symbol: 6位代码
  pe_percentile: 0~100 PE近5年分位, 无数据=50, 越小越低估
  pb_percentile: 0~100 PB近5年分位, 无数据=50
  deducted_np_growth: -100~200 扣非净利润增长%, 无数据=0
  revenue_growth: -100~200 营收增长%, 无数据=0
  gross_margin: 0~100 毛利率%, 无数据=null
  margin_trend: -1(下降) 0(平稳) 1(上升)
  op_cf_positive: 经营现金流>0=True
  cf_match_profit: 现金流匹配利润=True
  goodwill_ratio: 0~1 商誉/总资产比, 无数据=null
  pledge_ratio: 0~1 质押率, 无数据=null
  debt_risk: 0~1 负债风险, 无数据=null

L4_chip — 每股票一条:
  symbol: 6位代码
  cap_fit_score: 0~1 股本适中度, 无数据=0.5
  holder_decline_q: 0~4 连续股东递减季度数, 无数据=0
  holder_concentration: 0~1 筹码集中度, 无数据=0.5
  inst_holder_ratio: 0~1 机构持股占比, 无数据=null
  inst_quality: 0~1 机构持仓质量, 无数据=null
  near_lockup: 近期有解禁=True
  lockup_ratio: 0~1 解禁占总股本比, 无数据=0
  insider_reduction: 0~1 股东减持风险, 无数据=0

L7_risk — 每股票一条:
  symbol: 6位代码
  insider_sell_flag: 频繁减持=True
  pledge_risk: 0~1 高质押>50%风险, 无数据=0
  goodwill_risk: 0~1 商誉暴雷>30%风险, 无数据=0
  chaos_flag: 主营杂乱/跨界=True
  fraud_risk: 0~1 造假嫌疑, 无数据=0
  exclude: 全局排除=True
  exclude_reason: "" 或 排除原因

pool_candidates — 涨幅>5%且有消息催化的:
  symbol: 代码, source: "热榜发现"/"消息催化"/"板块联动"

market_features — {leading_sectors:[], sentiment:"乐观"/"中性"/"悲观", anomaly_flag:false}

规则:
1. 每只 scanned_symbols 必须在 L2-L4-L7 各有一行
2. 每个 sector_flow 必须在 L1_industry 有一行
3. 无数据=null/0/0.5(中性), 不编造
4. pool_candidates 只放涨幅>5%+有催化剂的
5. 输出纯 JSON, 无 markdown 包裹
"""

    output_schema = {
        "L1_industry": {"type": "list", "default": []},
        "L2_capital": {"type": "list", "default": []},
        "L3_fundamentals": {"type": "list", "default": []},
        "L4_chip": {"type": "list", "default": []},
        "L7_risk": {"type": "list", "default": []},
        "pool_candidates": {"type": "list", "default": []},
        "market_features": {"type": "dict", "default": {}},
    }

    def analyze(self, hot_rank: list = None, sector_flow: list = None,
                news_headlines: list = None, financials: dict = None,
                scanned_symbols: list = None) -> dict:
        """
        分析市场数据，返回结构化量化特征。
        scanned_symbols: 当前扫描的股票代码列表，Agent 为每个标的生成 L2-L4-L7 特征。
        """
        context = {
            "hot_rank": hot_rank or [],
            "sector_flow": sector_flow or [],
            "news": news_headlines or [],
            "financials": financials or {},
            "scanned_symbols": scanned_symbols or [],
        }
        return self.run(**context)

    def analyze_research(self, report_texts: list[str]) -> dict:
        """
        解析研报/政策文本，提取结构化信号。
        """
        context = {
            "reports": report_texts,
            "task": "extract_catalysts",
        }
        return self.run(**context)
