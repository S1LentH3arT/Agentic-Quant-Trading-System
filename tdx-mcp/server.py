#!/usr/bin/env python3
"""
通达信 MCP Server — Claude Code 直连通达信行情系统
基于 mootdx 协议, 提供实时行情/板块/选股/财务数据
"""

import json
import sys
import asyncio
from typing import Any

# ============================================================
# 数据层 — 尝试加载 mootdx
# ============================================================
try:
    from mootdx.quotes import StdQuotes
    TDX_READY = True
    # 直连速度最快的服务器(已验证连通)
    client = StdQuotes(host='218.6.170.47', port=7709, timeout=8)
except Exception:
    try:
        client = StdQuotes(host='110.41.147.114', port=7709, timeout=8)
        TDX_READY = True
    except Exception:
        TDX_READY = False
        client = None

# ============================================================
# 工具函数
# ============================================================

def _tdx_quote(symbols: list[str]) -> dict:
    """实时行情"""
    if not TDX_READY:
        return {"error": "mootdx 未安装或连接失败"}
    try:
        data = client.quotes(symbol=[_clean(s) for s in symbols])
        if data is None or (hasattr(data, 'empty') and data.empty):
            return {"error": "无数据"}
        result = []
        # mootdx returns pandas DataFrame
        if hasattr(data, 'iterrows'):
            for _, row in data.iterrows():
                result.append({
                    "code": str(row.get("code", "")),
                    "name": str(row.get("name", "")),
                    "price": float(row.get("price", 0) or 0),
                    "open": float(row.get("open", 0) or 0),
                    "high": float(row.get("high", 0) or 0),
                    "low": float(row.get("low", 0) or 0),
                    "volume": float(row.get("vol", 0) or 0),
                    "change_pct": round(float(row.get("change_pct", 0) or 0), 2),
                })
        else:
            for row in (data or []):
                result.append({
                "code": row.get("code", ""),
                "name": row.get("name", ""),
                "price": row.get("price", 0),
                "open": row.get("open", 0),
                "high": row.get("high", 0),
                "low": row.get("low", 0),
                "volume": row.get("volume", 0),
                "amount": row.get("amount", 0),
                "change_pct": round(row.get("change_pct", 0) or 0, 2),
                "pe": row.get("pe", 0),
            })
        return {"quotes": result}
    except Exception as e:
        return {"error": str(e)}

def _tdx_kline(symbol: str, period: str = "day", count: int = 60) -> dict:
    """K线数据"""
    if not TDX_READY:
        return {"error": "mootdx 未安装或连接失败"}
    freq_map = {"min1": 8, "min5": 0, "min15": 1, "min30": 2, "min60": 3, "day": 9, "week": 5, "month": 6}
    freq = freq_map.get(period, 9)
    try:
        data = client.bars(symbol=_clean(symbol), frequency=freq, offset=count)
        if data is None or (hasattr(data, 'empty') and data.empty):
            return {"error": "无数据"}
        bars = []
        rows = data.iterrows() if hasattr(data, 'iterrows') else data
        for row in (rows if not hasattr(data, 'iterrows') else [(None, r) for _, r in data.iterrows()]):
            r = row[1] if isinstance(row, tuple) else row
                "date": str(row.get("date", "")),
                "open": float(row.get("open", 0)),
                "high": float(row.get("high", 0)),
                "low": float(row.get("low", 0)),
                "close": float(row.get("close", 0)),
                "volume": float(row.get("volume", 0)),
            })
        last = bars[-1] if bars else {}
        prev = bars[-2] if len(bars) > 1 else {}
        chg = (last["close"] - prev["close"]) / prev["close"] * 100 if prev else 0
        hi = max(b["high"] for b in bars[-count:])
        lo = min(b["low"] for b in bars[-count:])
        avg_vol = sum(b["volume"] for b in bars[-20:]) / min(20, len(bars))
        return {
            "symbol": symbol,
            "period": period,
            "bars": bars[-count:],
            "summary": {
                "close": last.get("close", 0),
                "change_pct": round(chg, 2),
                "high_N": round(hi, 2),
                "low_N": round(lo, 2),
                "avg_vol_20": int(avg_vol),
            }
        }
    except Exception as e:
        return {"error": str(e)}

def _tdx_sector_list() -> dict:
    """通达信板块列表"""
    if not TDX_READY:
        return {"error": "mootdx 未安装或连接失败"}
    try:
        data = client.block()
        return {"sectors": data if data else []}
    except Exception as e:
        return {"error": str(e)}

def _tdx_search(keyword: str) -> dict:
    """搜索股票"""
    if not TDX_READY:
        return {"error": "mootdx 未安装或连接失败"}
    try:
        all_stocks = client.stocks(market=1)  # 深沪A股
        matches = [s for s in (all_stocks or []) if keyword in str(s.get("code","")) or keyword in str(s.get("name",""))]
        return {"matches": matches[:20]}
    except Exception as e:
        return {"error": str(e)}

def _clean(symbol: str) -> str:
    """600183.SH → 600183, SZSE:000070 → 000070"""
    return symbol.replace("SZSE:", "").replace("SSE:", "").replace(".SZ", "").replace(".SH", "").split(":")[-1]

def _tdx_indicator(symbol: str, count: int = 120) -> dict:
    """综合决策王全部指标"""
    try:
        import sys; sys.path.insert(0, 'F:/working-project/tdx-mcp')
        from indicator_engine import load_kline, calc_all_indicators, get_summary, score_stock
        df = load_kline(_clean(symbol), count=count)
        df = calc_all_indicators(df)
        s = get_summary(df, symbol)
        sc = score_stock(df)
        return {"summary": s, "score": sc["score"], "score_details": sc["details"]}
    except Exception as e:
        return {"error": str(e)}

def _tdx_chart(symbol: str, count: int = 120) -> dict:
    """渲染图表"""
    try:
        import sys; sys.path.insert(0, 'F:/working-project/tdx-mcp')
        from indicator_engine import load_kline
        from chart_renderer import render_chart
        df = load_kline(_clean(symbol), count=count)
        path = render_chart(symbol, df)
        return {"chart_path": path, "symbol": symbol}
    except Exception as e:
        return {"error": str(e)}

def _tdx_decision() -> dict:
    """完整决策周期"""
    try:
        import sys; sys.path.insert(0, 'F:/working-project/tdx-mcp')
        from decision_engine import full_decision_cycle
        result = full_decision_cycle()
        return {
            "sector_ranking": result["recommendations"]["sector_ranking"],
            "candidates": result["recommendations"]["candidates"],
            "discipline_alerts": result["discipline"]["alerts"],
            "trend_diff": result.get("diff", {}),
            "saved": result["saved"],
        }
    except Exception as e:
        return {"error": str(e)}

def _tdx_sector_scan(symbols: list[str], sector_name: str = "板块") -> dict:
    """批量扫描+评分"""
    try:
        import sys; sys.path.insert(0, 'F:/working-project/tdx-mcp')
        from indicator_engine import load_kline, calc_all_indicators, get_summary, score_stock
        results = []
        for sym in symbols:
            try:
                df = load_kline(_clean(sym), count=80)
                df = calc_all_indicators(df)
                s = get_summary(df, sym)
                sc = score_stock(df)
                results.append({"symbol": sym, "summary": s, "score": sc["score"], "details": sc["details"]})
            except Exception as e:
                results.append({"symbol": sym, "error": str(e)})
        results.sort(key=lambda r: r.get("score", -99), reverse=True)
        # Render grid chart
        try:
            from chart_renderer import render_sector_grid
            grid_path = render_sector_grid(symbols, sector_name)
        except:
            grid_path = None
        return {"sector": sector_name, "rankings": results, "grid_chart": grid_path}
    except Exception as e:
        return {"error": str(e)}

# ============================================================
# MCP Protocol Handler (manual, no deps)
# ============================================================

TOOLS = [
    {"name": "tdx_quote", "description": "获取实时行情（价格/涨跌/量能/PE），支持批量", "inputSchema": {"type": "object", "properties": {"symbols": {"type": "array", "items": {"type": "string"}, "description": "股票代码列表"}}, "required": ["symbols"]}},
    {"name": "tdx_kline", "description": "获取K线数据（日/周/月/分钟），返回K线+摘要（涨跌幅/区间高低/均量）", "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string"}, "period": {"type": "string", "default": "day"}, "count": {"type": "integer", "default": 60}}, "required": ["symbol"]}},
    {"name": "tdx_sector_list", "description": "获取通达信所有板块列表（行业/概念/地域）", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "tdx_search", "description": "按名称或代码搜索A股标的", "inputSchema": {"type": "object", "properties": {"keyword": {"type": "string"}}, "required": ["keyword"]}},
    {"name": "tdx_indicator", "description": "计算综合决策王全部指标（DKX/A1X/箱体/量能/走势分类/止损线），返回最新信号摘要+评分", "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string"}, "count": {"type": "integer", "default": 120}}, "required": ["symbol"]}},
    {"name": "tdx_chart", "description": "渲染综合决策王完整图表（K线+DKX+SMX+箱体+A1X+量能+买卖信号），保存为PNG", "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string"}, "count": {"type": "integer", "default": 120}}, "required": ["symbol"]}},
    {"name": "tdx_sector_scan", "description": "扫描板块所有标的，按综合决策王评分排序，输出表格+推荐", "inputSchema": {"type": "object", "properties": {"symbols": {"type": "array", "items": {"type": "string"}}, "sector_name": {"type": "string", "default": "板块"}}, "required": ["symbols"]}},
    {"name": "tdx_decision", "description": "完整决策周期：扫描全部5板块22只标的→评分排序→纪律检查→操作建议→趋势对比→持久化", "inputSchema": {"type": "object", "properties": {}, "required": []}},
]

def handle_request(req: dict) -> dict | None:
    method = req.get("method", "")
    rid = req.get("id")

    # initialize
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": rid, "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "tdx-mcp", "version": "1.0.0"}}}

    # tools/list
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}}

    # tools/call
    if method == "tools/call":
        name = req.get("params", {}).get("name", "")
        args = req.get("params", {}).get("arguments", {})
        result = None
        if name == "tdx_quote":
            result = _tdx_quote(args.get("symbols", []))
        elif name == "tdx_kline":
            result = _tdx_kline(args.get("symbol", ""), args.get("period", "day"), args.get("count", 60))
        elif name == "tdx_sector_list":
            result = _tdx_sector_list()
        elif name == "tdx_search":
            result = _tdx_search(args.get("keyword", ""))
        elif name == "tdx_indicator":
            result = _tdx_indicator(args.get("symbol", ""), args.get("count", 120))
        elif name == "tdx_chart":
            result = _tdx_chart(args.get("symbol", ""), args.get("count", 120))
        elif name == "tdx_sector_scan":
            result = _tdx_sector_scan(args.get("symbols", []), args.get("sector_name", "板块"))
        elif name == "tdx_decision":
            result = _tdx_decision()
        else:
            result = {"error": f"Unknown tool: {name}"}
        return {"jsonrpc": "2.0", "id": rid, "result": {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}}

    # notifications
    if method == "notifications/initialized" or method == "initialized":
        return None

    return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"Method not found: {method}"}}

async def main():
    reader = asyncio.StreamReader()
    loop = asyncio.get_event_loop()
    # Use stdin as a raw stream
    transport, _ = await loop.connect_read_pipe(lambda: asyncio.StreamReaderProtocol(reader), sys.stdin)
    writer_transport, writer = await loop.connect_write_pipe(lambda: asyncio.StreamWriter, sys.stdout)

    buf = b""
    while True:
        chunk = await reader.read(65536)
        if not chunk:
            break
        buf += chunk
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
                resp = handle_request(req)
                if resp:
                    writer.write((json.dumps(resp, ensure_ascii=False) + "\n").encode())
                    await writer.drain()
            except json.JSONDecodeError:
                pass

if __name__ == "__main__":
    asyncio.run(main())
