#!/usr/bin/env python3
"""
数据适配器 — 多源数据入口 (Tencent 主力 + AKShare 备用)。
Tencent API 直连走 HTTP，速度快且不依赖 SSL 敏感 CDN。
"""

import json
import os
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from typing import Optional
import time
import requests


class DataProvider:
    """多源数据适配器。K线主用 Tencent API，备用 AKShare。"""

    # ── K线 (Tencent 主力) ──

    @staticmethod
    def _symbol_to_tencent(symbol: str) -> str:
        """600863 → sh600863, 000070 → sz000070"""
        if symbol.startswith(('6', '5')):
            return f'sh{symbol}'
        return f'sz{symbol}'

    def _fetch_kline_tencent(self, symbol: str, count: int = 120,
                              period: str = 'daily') -> Optional[pd.DataFrame]:
        """通过腾讯 API 获取K线 (免费, 无频率限制)"""
        tenc_sym = self._symbol_to_tencent(symbol)
        period_map = {'daily': 'day', 'weekly': 'week', 'monthly': 'month'}
        ktype = period_map.get(period, 'day')

        url = (f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get'
               f'?param={tenc_sym},{ktype},,,{count},qfq')

        try:
            resp = requests.get(url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0',
                'Referer': 'https://gu.qq.com/',
            })
            data = resp.json()
            klines = (data.get('data', {}).get(tenc_sym, {})
                      .get(f'qfq{ktype}', []) or
                      data.get('data', {}).get(tenc_sym, {})
                      .get(ktype, []))
            if not klines:
                return None

            # Tencent format: [date, open, close, high, low, volume]
            rows = []
            for k in klines:
                rows.append({
                    'date': k[0],
                    'open': float(k[1]),
                    'close': float(k[2]),
                    'high': float(k[3]),
                    'low': float(k[4]),
                    'volume': float(k[5]),
                })

            df = pd.DataFrame(rows)
            if len(df) == 0:
                return None
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date').sort_index()
            return df.tail(count)

        except Exception:
            return None

    def _fetch_kline_akshare(self, symbol: str, count: int = 120,
                              period: str = 'daily') -> Optional[pd.DataFrame]:
        """AKShare 备用K线获取"""
        try:
            import akshare as ak

            end_date = date.today().strftime('%Y%m%d')
            start_date = (date.today() - timedelta(days=count * 3)).strftime('%Y%m%d')

            df = ak.stock_zh_a_hist(
                symbol=symbol, period=period,
                start_date=start_date, end_date=end_date,
                adjust='qfq'
            )
            if df is None or len(df) == 0:
                return None

            df = df.rename(columns={
                '开盘': 'open', '最高': 'high', '最低': 'low',
                '收盘': 'close', '成交量': 'volume',
            })
            for col in ['open', 'high', 'low', 'close', 'volume']:
                if col in df.columns:
                    df[col] = df[col].astype(float)
            return df.tail(count) if len(df) > count else df
        except Exception:
            return None

    def _cache_path(self, symbol: str, period: str) -> str:
        """K线本地缓存路径"""
        from quant_system.config import ensure_dir
        cache_dir = ensure_dir("storage", "state", "kline_cache")
        return os.path.join(cache_dir, f"{symbol}_{period}.csv")

    def _load_cache(self, symbol: str, period: str, count: int) -> Optional[pd.DataFrame]:
        """读取本地缓存的K线"""
        path = self._cache_path(symbol, period)
        if not os.path.exists(path):
            return None
        try:
            df = pd.read_csv(path, index_col=0, parse_dates=True)
            if len(df) >= 5:
                return df.tail(count)
        except Exception:
            pass
        return None

    def _save_cache(self, df: pd.DataFrame, symbol: str, period: str):
        """保存K线到本地缓存"""
        try:
            path = self._cache_path(symbol, period)
            df.to_csv(path)
        except Exception:
            pass

    def fetch_kline(self, symbol: str, count: int = 120,
                    period: str = 'daily', adjust: str = 'qfq') -> pd.DataFrame:
        """
        获取K线数据 (Tencent → AKShare → 本地缓存)。
        period: 'daily' | 'weekly' | 'monthly'
        """
        # 主力: Tencent API
        df = self._fetch_kline_tencent(symbol, count, period)
        if df is not None and len(df) >= 5:
            self._save_cache(df, symbol, period)
            return df

        # 备用: AKShare → EastMoney
        df = self._fetch_kline_akshare(symbol, count, period)
        if df is not None and len(df) >= 5:
            self._save_cache(df, symbol, period)
            return df

        # 兜底: 本地缓存
        df = self._load_cache(symbol, period, count)
        if df is not None:
            age_days = (date.today() - df.index[-1].date()).days
            tag = " [STALE!]" if age_days > 3 else ""
            print(f"  [DATA] {symbol}: API均失败, 缓存 {df.index[-1].strftime('%Y-%m-%d')} (距今{age_days}天){tag}")
            return df

        raise RuntimeError(f'无法获取 {symbol} 的{period}K线数据 (API+缓存均失败)')

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

    # ── 实时行情 (TDX 主力 → Tencent 备用 → AKShare 兜底) ──

    def _fetch_realtime_tdx(self, symbols: list[str]) -> list[dict]:
        """通过 TDX TCP 协议获取实时行情 (交易日 9:00-15:10 可用)"""
        try:
            from mootdx.quotes import StdQuotes
            client = StdQuotes(host='218.6.170.47', port=7709, timeout=8)
            data = client.quotes(symbol=symbols)
            results = []
            for _, r in data.iterrows():
                results.append({
                    'symbol': str(r.get('code', '')),
                    'name': str(r.get('name', '')),
                    'price': float(r.get('price', 0) or 0),
                    'open': float(r.get('open', 0) or 0),
                    'high': float(r.get('high', 0) or 0),
                    'low': float(r.get('low', 0) or 0),
                    'pre_close': float(r.get('last_close', 0) or 0),
                    'change_pct': float(r.get('change_pct', 0) or 0),
                    'volume': float(r.get('volume', 0) or 0),
                    'amount': float(r.get('amount', 0) or 0),
                })
            return results
        except Exception:
            return []

    def _fetch_realtime_tencent(self, symbols: list[str]) -> list[dict]:
        """通过腾讯 qt.gtimg.cn 获取实时行情"""
        try:
            tenc_syms = [self._symbol_to_tencent(s) for s in symbols]
            url = f'https://qt.gtimg.cn/q={",".join(tenc_syms)}'
            resp = requests.get(url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0',
                'Referer': 'https://gu.qq.com/',
            })
            results = []
            for line in resp.text.strip().split('\n'):
                if '=' not in line:
                    continue
                _, val = line.split('=', 1)
                parts = val.strip('" ;\n').split('~')
                if len(parts) < 40:
                    continue
                results.append({
                    'symbol': parts[2],
                    'name': parts[1],
                    'price': float(parts[3] or 0),
                    'pre_close': float(parts[4] or 0),
                    'open': float(parts[5] or 0),
                    'volume': float(parts[6] or 0),
                    'high': float(parts[33] or 0),
                    'low': float(parts[34] or 0),
                    'change_pct': float(parts[32] or 0),
                    'amount': float(parts[37] or 0),
                })
            return results
        except Exception:
            return []

    def fetch_realtime(self, symbols: list[str]) -> list[dict]:
        """获取实时行情 (TDX → Tencent → AKShare 自动切换)"""
        # 1) TDX TCP (最快，含盘口深度)
        results = self._fetch_realtime_tdx(symbols)
        if results:
            return results

        # 2) Tencent HTTP
        results = self._fetch_realtime_tencent(symbols)
        if results:
            return results

        # 3) AKShare / EastMoney (偶尔被墙)
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            if df is not None and len(df) > 0:
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
                        })
                return results
        except Exception:
            pass

        return []

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
