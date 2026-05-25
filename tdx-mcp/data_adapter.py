#!/usr/bin/env python3
"""
数据适配器 — TDX主源 + AKShare备用源
TDX不可用时自动降级到AKShare(东财), 保证Pipeline永不断线
"""
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import time

# ============================================================
# 源1: TDX (mootdx) — 主源
# ============================================================
def _try_tdx_kline(symbol: str, count: int = 60):
    """尝试从TDX获取K线"""
    try:
        from mootdx.quotes import StdQuotes
        client = StdQuotes(host='218.6.170.47', port=7709, timeout=5)
        # bars() 是 StdQuotes 的正确方法; frequency=9 为日线
        df = client.bars(symbol=symbol, frequency=9, offset=count)
        if df is not None and len(df) > 0:
            # bars() 返回的列名可能是 date/open/high/low/close/volume
            rename_map = {}
            for col in df.columns:
                col_lower = col.lower()
                if col_lower in ('open', 'high', 'low', 'close', 'volume'):
                    rename_map[col] = col_lower
            if rename_map:
                df = df.rename(columns=rename_map)
            for col in ['open', 'high', 'low', 'close', 'volume']:
                if col not in df.columns:
                    return None
            return df[['open', 'high', 'low', 'close', 'volume']]
    except Exception:
        pass
    return None

# ============================================================
# 源2: AKShare (东方财富) — 备用源
# ============================================================
def _try_akshare_kline(symbol: str, count: int = 60):
    """从AKShare(东财)获取K线"""
    try:
        import akshare as ak
        # 计算起止日期
        end_date = date.today().strftime('%Y%m%d')
        start_date = (date.today() - timedelta(days=count * 2)).strftime('%Y%m%d')

        df = ak.stock_zh_a_hist(
            symbol=symbol, period='daily',
            start_date=start_date, end_date=end_date,
            adjust='qfq'
        )
        if df is not None and len(df) > 0:
            df = df.rename(columns={
                '开盘': 'open', '最高': 'high', '最低': 'low',
                '收盘': 'close', '成交量': 'volume'
            })
            df = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
            return df.tail(count)
    except Exception:
        pass
    return None

# ============================================================
# 统一接口
# ============================================================
def load_kline(symbol: str, count: int = 60) -> pd.DataFrame:
    """
    加载K线数据, TDX优先, AKShare备用
    返回标准DataFrame: [open, high, low, close, volume]
    """
    # 优先TDX
    df = _try_tdx_kline(symbol, count)
    if df is not None and len(df) >= 20:
        return df

    # 降级AKShare
    df = _try_akshare_kline(symbol, count)
    if df is not None and len(df) >= 20:
        return df

    raise RuntimeError(f"无法获取 {symbol} 的K线数据: TDX和AKShare均失败")

def load_multi_klines(symbols: list[str], count: int = 60) -> dict[str, pd.DataFrame]:
    """批量加载多只标的K线"""
    results = {}
    for sym in symbols:
        try:
            results[sym] = load_kline(sym, count)
            time.sleep(0.1)  # 避免触发反爬
        except Exception as e:
            print(f"  {sym}: {e}")
    return results

def get_realtime_quotes(symbols: list[str]) -> list[dict]:
    """获取实时行情 (TDX优先, AKShare备用)"""
    # 先试TDX
    try:
        from mootdx.quotes import StdQuotes
        client = StdQuotes(host='218.6.170.47', port=7709, timeout=5)
        data = client.quotes(symbol=symbols)
        results = []
        for _, r in data.iterrows():
            price = float(r.get('price', 0) or 0)
            if price > 0:
                results.append({
                    'symbol': str(r.get('code', '')),
                    'name': str(r.get('name', '')),
                    'price': price,
                    'open': float(r.get('open', 0) or 0),
                    'high': float(r.get('high', 0) or 0),
                    'low': float(r.get('low', 0) or 0),
                    'pre_close': float(r.get('pre_close', 0) or 0),
                    'change_pct': float(r.get('change_pct', 0) or 0),
                    'volume': float(r.get('volume', 0) or 0),
                })
        if results:
            return results
    except Exception:
        pass

    # 降级AKShare
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        results = []
        for sym in symbols:
            row = df[df['代码'] == sym]
            if not row.empty:
                r = row.iloc[0]
                results.append({
                    'symbol': sym,
                    'name': str(r['名称']),
                    'price': float(r['最新价']),
                    'open': float(r['今开']),
                    'high': float(r['最高']),
                    'low': float(r['最低']),
                    'pre_close': float(r['昨收']),
                    'change_pct': float(r['涨跌幅']),
                    'volume': float(r['成交量']),
                })
        return results
    except Exception as e:
        raise RuntimeError(f"实时行情获取失败: {e}")

# ============================================================
# 健康检查
# ============================================================
def health_check() -> dict:
    """检查各数据源状态"""
    status = {'tdx': False, 'akshare': False}

    # TDX
    if _try_tdx_kline('600863', 5) is not None:
        status['tdx'] = True

    # AKShare
    if _try_akshare_kline('600863', 5) is not None:
        status['akshare'] = True

    status['ok'] = status['tdx'] or status['akshare']
    return status

if __name__ == '__main__':
    print("=" * 50)
    print("  数据适配器 健康检查")
    print("=" * 50)
    hc = health_check()
    print(f"  TDX:     {'✓ 在线' if hc['tdx'] else '✗ 离线'}")
    print(f"  AKShare: {'✓ 在线' if hc['akshare'] else '✗ 离线'}")
    print(f"  状态:    {'可运行' if hc['ok'] else '全部离线'}")
    print()

    if hc['akshare']:
        print("  测试AKShare实时行情...")
        quotes = get_realtime_quotes(['002747', '000725'])
        for q in quotes:
            print(f"  {q['symbol']} {q['name']} {q['price']} {q['change_pct']:+.2f}%")
