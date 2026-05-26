#!/usr/bin/env python3
"""
数据总线 — 统一数据缓存 + 去重 + 订阅推送
所有模块通过 DataBus 获取数据，不直接调 AKShare。
"""

import time
import pandas as pd
from datetime import datetime, date, timedelta
from threading import Lock
from typing import Optional

from quant_system.data.sources import get_source, SOURCES


class DataBus:
    """
    数据总线: 缓存 + 去重 + 分钟级过期。
    与 provider 配合: bus 做缓存，provider 做实际获取。
    """

    def __init__(self):
        self._cache: dict[str, tuple[float, any]] = {}
        self._lock = Lock()
        self._provider = None  # lazy init

    @property
    def provider(self):
        if self._provider is None:
            from quant_system.data.provider import DataProvider
            self._provider = DataProvider()
        return self._provider

    def _cached(self, key: str, max_age_seconds: int) -> Optional[any]:
        """检查缓存是否命中"""
        with self._lock:
            if key in self._cache:
                ts, val = self._cache[key]
                if time.time() - ts < max_age_seconds:
                    return val
        return None

    def _set_cache(self, key: str, val):
        with self._lock:
            self._cache[key] = (time.time(), val)

    def invalidate(self, key: Optional[str] = None):
        """清除缓存"""
        with self._lock:
            if key:
                self._cache.pop(key, None)
            else:
                self._cache.clear()

    # ── 数据接口 ──

    def get_daily(self, symbols: list[str], count: int = 120) -> dict[str, pd.DataFrame]:
        """获取A股日线K线 (带缓存)"""
        results = {}
        for sym in symbols:
            cache_key = f"kline_daily:{sym}:{count}"
            cached = self._cached(cache_key, 3600)
            if cached is not None:
                results[sym] = cached
                continue
            try:
                df = self.provider.fetch_kline(sym, count, period='daily')
                self._set_cache(cache_key, df)
                results[sym] = df
            except Exception as e:
                results[sym] = None
        return results

    def get_weekly(self, symbols: list[str], count: int = 52) -> dict[str, pd.DataFrame]:
        """获取周线K线"""
        results = {}
        for sym in symbols:
            cache_key = f"kline_weekly:{sym}:{count}"
            cached = self._cached(cache_key, 86400)
            if cached is not None:
                results[sym] = cached
                continue
            try:
                df = self.provider.fetch_kline(sym, count, period='weekly')
                self._set_cache(cache_key, df)
                results[sym] = df
            except Exception:
                results[sym] = None
        return results

    def get_monthly(self, symbols: list[str], count: int = 12) -> dict[str, pd.DataFrame]:
        """获取月线K线"""
        results = {}
        for sym in symbols:
            cache_key = f"kline_monthly:{sym}:{count}"
            cached = self._cached(cache_key, 86400)
            if cached is not None:
                results[sym] = cached
                continue
            try:
                df = self.provider.fetch_kline(sym, count, period='monthly')
                self._set_cache(cache_key, df)
                results[sym] = df
            except Exception:
                results[sym] = None
        return results

    def get_realtime(self, symbols: list[str]) -> list[dict]:
        """获取实时行情"""
        cache_key = f"realtime:{','.join(sorted(symbols))}"
        cached = self._cached(cache_key, 30)
        if cached is not None:
            return cached
        quotes = self.provider.fetch_realtime(symbols)
        self._set_cache(cache_key, quotes)
        return quotes

    def get_hot_rank(self, limit: int = 30) -> list[dict]:
        """获取东方财富热榜"""
        cache_key = f"hot_rank:{limit}"
        cached = self._cached(cache_key, 300)
        if cached is not None:
            return cached
        try:
            hot = self.provider.fetch_hot_rank(limit)
            self._set_cache(cache_key, hot)
            return hot
        except Exception:
            return []

    def get_sector_flow(self, limit: int = 10) -> list[dict]:
        """获取行业板块资金流向"""
        cache_key = f"sector_flow:{limit}"
        cached = self._cached(cache_key, 1800)
        if cached is not None:
            return cached
        try:
            sectors = self.provider.fetch_sector_flow(limit)
            self._set_cache(cache_key, sectors)
            return sectors
        except Exception:
            return []

    def get_north_flow(self, days: int = 30) -> pd.DataFrame:
        """获取北向资金流向"""
        cache_key = f"north_flow:{days}"
        cached = self._cached(cache_key, 3600)
        if cached is not None:
            return cached
        try:
            df = self.provider.fetch_north_flow(days)
            self._set_cache(cache_key, df)
            return df
        except Exception:
            return pd.DataFrame()

    def get_all_stock_codes(self) -> set[str]:
        """获取全A股代码集合（缓存1天）"""
        cache_key = "all_stock_codes"
        cached = self._cached(cache_key, 86400)
        if cached is not None:
            return cached
        codes = self.provider.fetch_all_codes()
        self._set_cache(cache_key, codes)
        return codes


# 全局单例
_bus = None

def get_bus() -> DataBus:
    global _bus
    if _bus is None:
        _bus = DataBus()
    return _bus
