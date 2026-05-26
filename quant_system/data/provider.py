#!/usr/bin/env python3
"""
数据适配器 — AKShare 统一数据入口。
纯 AKShare 实现，移除 TDX(mootdx) 依赖。
"""

import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from typing import Optional
import time


class DataProvider:
    """AKShare 统一数据适配器"""

    # ── K线 ──

    def fetch_kline(self, symbol: str, count: int = 120,
                    period: str = 'daily', adjust: str = 'qfq') -> pd.DataFrame:
        """
        获取K线数据。
        period: 'daily' | 'weekly' | 'monthly'
        adjust: 'qfq'(前复权) | 'hfq'(后复权) | ''(不复权)
        """
        import akshare as ak

        end_date = date.today().strftime('%Y%m%d')
        start_date = (date.today() - timedelta(days=count * 3)).strftime('%Y%m%d')

        df = ak.stock_zh_a_hist(
            symbol=symbol, period=period,
            start_date=start_date, end_date=end_date,
            adjust=adjust
        )
        if df is None or len(df) == 0:
            raise RuntimeError(f"AKShare 无法获取 {symbol} 的{period}K线数据")

        df = df.rename(columns={
            '开盘': 'open', '最高': 'high', '最低': 'low',
            '收盘': 'close', '成交量': 'volume',
            '成交额': 'amount', '换手率': 'turnover',
            '振幅': 'amplitude', '涨跌幅': 'change_pct',
            '涨跌额': 'change_amount',
        })

        # 标准列
        std_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in std_cols:
            if col in df.columns:
                df[col] = df[col].astype(float)

        return df.tail(count) if len(df) > count else df

    def fetch_multi_klines(self, symbols: list[str], count: int = 120,
                           period: str = 'daily') -> dict[str, pd.DataFrame]:
        """批量获取K线"""
        results = {}
        for sym in symbols:
            try:
                results[sym] = self.fetch_kline(sym, count, period)
                time.sleep(0.2)
            except Exception as e:
                print(f"  [DATA] {sym}: {e}")
                results[sym] = None
        return results

    # ── 实时行情 ──

    def fetch_realtime(self, symbols: list[str]) -> list[dict]:
        """获取实时行情"""
        import akshare as ak

        df = ak.stock_zh_a_spot_em()
        if df is None or len(df) == 0:
            return []

        results = []
        for sym in symbols:
            row = df[df['代码'] == sym]
            if not row.empty:
                r = row.iloc[0]
                results.append({
                    'symbol': sym,
                    'name': str(r.get('名称', '')),
                    'price': float(r.get('最新价', 0)),
                    'open': float(r.get('今开', 0)),
                    'high': float(r.get('最高', 0)),
                    'low': float(r.get('最低', 0)),
                    'pre_close': float(r.get('昨收', 0)),
                    'change_pct': float(r.get('涨跌幅', 0)),
                    'volume': float(r.get('成交量', 0)),
                    'amount': float(r.get('成交额', 0)),
                    'turnover': float(r.get('换手率', 0)),
                })
        return results

    # ── 热榜 ──

    def fetch_hot_rank(self, limit: int = 30) -> list[dict]:
        """东方财富热榜"""
        import akshare as ak
        df = ak.stock_hot_rank_em()
        if df is None or len(df) == 0:
            return []
        results = []
        for _, row in df.head(limit).iterrows():
            results.append({
                'code': str(row.get('代码', '')).strip(),
                'name': str(row.get('名称', '')).strip(),
                'price': float(row.get('最新价', 0) or 0),
                'change_pct': float(row.get('涨跌幅', 0) or 0),
            })
        return results

    # ── 行业板块 ──

    def fetch_sector_flow(self, limit: int = 10) -> list[dict]:
        """行业板块资金流向"""
        import akshare as ak
        df = ak.stock_board_industry_name_em()
        if df is None or len(df) == 0:
            return []
        results = []
        for _, row in df.head(limit).iterrows():
            results.append({
                'name': str(row.get('板块名称', '')),
                'change_pct': float(row.get('涨跌幅', 0) or 0),
                'main_flow': float(row.get('主力净流入', 0) or 0),
            })
        return results

    # ── 北向资金 ──

    def fetch_north_flow(self, days: int = 30) -> pd.DataFrame:
        """北向资金流向历史"""
        import akshare as ak
        try:
            df = ak.stock_hsgt_hist_em(symbol="沪股通")
            if df is not None and len(df) > 0:
                return df.tail(days)
        except Exception:
            pass
        return pd.DataFrame()

    # ── 全A股代码 ──

    def fetch_all_codes(self) -> set[str]:
        """全A股代码集合"""
        import akshare as ak
        try:
            df = ak.stock_info_a_code_name()
            return set(str(c).zfill(6) for c in df['code'])
        except Exception:
            return set()

    # ── 健康检查 ──

    def health_check(self) -> dict:
        """检查数据源状态"""
        status = {'akshare': False}
        try:
            df = self.fetch_kline('000001', 5, 'daily')
            if df is not None and len(df) >= 3:
                status['akshare'] = True
        except Exception:
            pass
        status['ok'] = status['akshare']
        return status


if __name__ == '__main__':
    print("=" * 50)
    print("  数据适配器 健康检查")
    print("=" * 50)
    p = DataProvider()
    hc = p.health_check()
    print(f"  AKShare: {'✓ 在线' if hc['akshare'] else '✗ 离线'}")
    print(f"  状态:    {'可运行' if hc['ok'] else '全部离线'}")

    if hc['akshare']:
        print("\n  测试实时行情...")
        quotes = p.fetch_realtime(['000001', '000002'])
        for q in quotes:
            print(f"  {q['symbol']} {q['name']} {q['price']} {q['change_pct']:+.2f}%")
