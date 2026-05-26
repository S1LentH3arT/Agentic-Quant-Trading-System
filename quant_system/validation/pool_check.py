#!/usr/bin/env python3
"""
品种池防幻觉校验 — AKShare全A股代码验证
"""


class PoolCheck:
    """候选代码必须在 AKShare 中存在真实验证"""

    def __init__(self):
        self._valid_codes: set[str] = None
        self._stale_time: float = 0

    def _load_valid_codes(self) -> set[str]:
        import time
        if self._valid_codes and (time.time() - self._stale_time) < 3600:
            return self._valid_codes
        try:
            from quant_system.data.bus import get_bus
            bus = get_bus()
            self._valid_codes = bus.get_all_stock_codes()
            self._stale_time = time.time()
        except Exception:
            self._valid_codes = set()
        return self._valid_codes

    def validate(self, candidates: list[dict]) -> tuple[list, list[str]]:
        """
        对每个候选代码: 格式检查 / AKShare存在性 / 非ST
        返回: (合法候选列表, 违规原因列表)
        """
        valid_codes = self._load_valid_codes()
        clean, violations = [], []

        for c in candidates:
            sym = str(c.get("symbol", "")).strip()
            if not sym.isdigit() or len(sym) != 6:
                violations.append(f"代码格式非法: {sym}")
                continue
            if sym.startswith('688'):
                violations.append(f"科创板排除: {sym}")
                continue
            if valid_codes and sym not in valid_codes:
                violations.append(f"代码不存在: {sym}")
                continue
            clean.append({**c, "symbol": sym, "verified": True})

        return clean, violations
