#!/usr/bin/env python3
"""
品种池管理 — 主力池 + 发现池 + 黑名单
"""

import json
import os
from datetime import date
from quant_system.config import get_path, ensure_dir


class PoolManager:
    """品种池管理"""

    # 主力池 (静态核心池)
    STATIC_POOL = {
        "电网设备": ["600089", "600406", "601179", "600312", "000400", "600875", "300827", "600379"],
        "电能":     ["601991", "600863", "600900", "600011"],
        "AI通信":   ["300903", "600183", "002463", "601698", "000070"],
        "算力":     ["603881", "300608", "688500", "002421"],
        "液冷":     ["002272", "002892", "300499"],
    }

    def __init__(self):
        ensure_dir("storage", "state")
        self._discovery_file = get_path("storage", "state", "discovery_pool.json")

    def get_full_pool(self) -> list[str]:
        """获取完整候选池: 主力池 + 发现池 + 今日狙击"""
        symbols = []
        for sec_syms in self.STATIC_POOL.values():
            symbols.extend(sec_syms)
        symbols.extend(self._load_discoveries())
        return list(dict.fromkeys(symbols))  # 去重保序

    def get_sector_pool(self, sector: str = None) -> dict | list:
        """获取板块品种池"""
        if sector:
            return self.STATIC_POOL.get(sector, [])
        return dict(self.STATIC_POOL)

    def get_static_symbols(self) -> set[str]:
        """获取所有静态池标的"""
        return {s for ss in self.STATIC_POOL.values() for s in ss}

    def _load_discoveries(self) -> list[str]:
        """加载发现池标的"""
        if not os.path.exists(self._discovery_file):
            return []
        try:
            with open(self._discovery_file, encoding='utf-8') as f:
                data = json.load(f)
            return list(data.keys()) if isinstance(data, dict) else []
        except Exception:
            return []

    def add_agent_candidates(self, candidates: list[dict]) -> list[str]:
        """
        Agent 提交的候选 → 校验后合并入发现池。
        返回: 成功添加的代码列表
        """
        from quant_system.validation.pool_check import PoolCheck
        checker = PoolCheck()
        valid, violations = checker.validate(candidates)

        added = []
        for c in valid:
            sym = c["symbol"]
            self._add_to_discovery(sym, c.get("source", "agent"))
            added.append(sym)

        return added

    def _add_to_discovery(self, symbol: str, source: str):
        """添加标的到发现池"""
        existing = {}
        if os.path.exists(self._discovery_file):
            try:
                with open(self._discovery_file, encoding='utf-8') as f:
                    existing = json.load(f)
            except Exception:
                pass

        today = date.today().isoformat()
        if symbol in existing:
            existing[symbol]["last_seen"] = today
        else:
            existing[symbol] = {
                "first_found": today, "last_seen": today,
                "source": source,
            }

        with open(self._discovery_file, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

    def blacklist(self, symbol: str, reason: str):
        """加入黑名单"""
        bl_file = get_path("storage", "state", "blacklist.json")
        bl = {}
        if os.path.exists(bl_file):
            try:
                with open(bl_file, encoding='utf-8') as f:
                    bl = json.load(f)
            except Exception:
                pass
        bl[symbol] = {"date": date.today().isoformat(), "reason": reason}
        with open(bl_file, "w", encoding="utf-8") as f:
            json.dump(bl, f, ensure_ascii=False, indent=2)

    def is_blacklisted(self, symbol: str) -> bool:
        bl_file = get_path("storage", "state", "blacklist.json")
        if not os.path.exists(bl_file):
            return False
        try:
            with open(bl_file, encoding='utf-8') as f:
                return symbol in json.load(f)
        except Exception:
            return False
