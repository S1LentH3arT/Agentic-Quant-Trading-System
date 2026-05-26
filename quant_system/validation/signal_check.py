#!/usr/bin/env python3
"""
信号合理性校验 (stub — 后续完善)
"""


class SignalCheck:
    def filter(self, signals: list) -> list:
        """过滤不合法信号"""
        return [s for s in signals if self._valid(s)]

    def _valid(self, sig) -> bool:
        return bool(sig.symbol and len(sig.symbol) == 6 and sig.price > 0)
