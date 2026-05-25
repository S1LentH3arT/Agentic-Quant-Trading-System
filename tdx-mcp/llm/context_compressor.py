# tdx-mcp/llm/context_compressor.py
"""三层压缩: L1摘要 / L2板块 / L3市场"""


def compress_level1(stock_list: list[dict], fields: list[str] = None, max_items: int = 95) -> str:
    """L1: 单只股票摘要。默认10字段，可按需过滤字段。"""
    if fields is None:
        fields = ["symbol", "close", "score", "DKX", "dkx_dir", "A1X", "a1x_dir",
                   "box_pos", "vol_ratio", "DZT", "ZZJC"]
    lines = []
    for r in stock_list[:max_items]:
        s = r.get("summary", {})
        parts = [f"{r.get('symbol','?')}"]
        for f in fields:
            val = s.get(f, r.get(f, ""))
            if isinstance(val, float):
                val = round(val, 2)
            parts.append(f"{f}={val}")
        parts.append(f"score={r.get('score',0)}")
        if r.get("veto"):
            parts.append("VETO")
        lines.append(" | ".join(parts))
    return "\n".join(lines)


def compress_level2(sector_results: dict) -> str:
    """L2: 板块聚合。每个板块均分+趋势+TOP3。"""
    lines = []
    for sector, data in sector_results.items():
        avg = data.get("avg_score", 0)
        top3 = [r.get("symbol","?") for r in data.get("rankings", [])[:3]]
        lines.append(f"{sector}: avg={avg:.1f} TOP3={','.join(top3)}")
    return "\n".join(lines)


def compress_level3(market_data: dict) -> str:
    """L3: 市场宏观。跌停数/红盘数/风格/上证。"""
    return (
        f"跌停家数={market_data.get('limit_down_count','?')} | "
        f"红盘家数={market_data.get('up_count','?')} | "
        f"盘面风格={market_data.get('market_style','?')} | "
        f"上证={market_data.get('sh_index_pct',0):+.2f}%"
    )


def compress_time_series(df, symbol: str) -> dict:
    """提取技术Agent需要的时间序列。返回Dict而非文本，由Agent自己格式化。"""
    if df is None or len(df) < 5:
        return {}
    tail = df.tail(5)
    return {
        "symbol": symbol,
        "a1x_3d": [round(float(x), 2) for x in tail["A1X"].tail(3).tolist()],
        "dkx_5d": [round(float(x), 2) for x in tail["DKX"].tail(5).dropna().tolist()],
        "vol_5d": [round(float(x), 2) for x in tail["vol_ratio"].tail(5).tolist()],
        "weekly_trend": "↑" if float(tail["close"].iloc[-1]) > float(tail["close"].iloc[-5]) else "↓",
        "strong": bool(tail["STRONG"].iloc[-1]),
        "weak": bool(tail["WEAK"].iloc[-1]),
        "fake": bool(tail["FAKE"].iloc[-1]),
    }
