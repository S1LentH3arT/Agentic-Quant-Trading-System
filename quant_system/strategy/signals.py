#!/usr/bin/env python3
"""
信号生成器 — 从评分结果生成交易信号
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Signal:
    symbol: str
    action: str          # BUY / SELL / HOLD
    urgency: int         # 0-5, 5=立即执行
    score: float
    price: float
    stop_price: float
    entry_zone: str
    reason: str
    classification: str = ""  # 价值趋势 / 拐点反转 / 低位潜伏
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class SignalGenerator:
    """从评分结果 + 分类生成交易信号"""

    # 分类差异化阈值
    THRESHOLDS = {
        "拐点反转": {"buy": 0.55, "sell": 0.30},   # 最低入场门槛
        "价值趋势": {"buy": 0.65, "sell": 0.30},
        "低位潜伏": {"buy": 0.70, "sell": 0.25},
    }

    def generate(self, scored_results: list[dict],
                 classifications: dict[str, str] = None) -> list[Signal]:
        """
        输入: [{symbol, score, layer_scores, veto, ...}, ...]
        输出: [Signal, ...]
        """
        if classifications is None:
            classifications = {}

        signals = []
        for r in scored_results:
            sym = r.get("symbol", "")
            score = r.get("score", 0)
            veto = r.get("veto", False)

            if veto:
                continue

            cls = classifications.get(sym, "价值趋势")
            thresholds = self.THRESHOLDS.get(cls, self.THRESHOLDS["价值趋势"])

            # 买入信号
            if score >= thresholds["buy"] * 10:
                signals.append(Signal(
                    symbol=sym,
                    action="BUY",
                    urgency=min(5, int(score - 5)),
                    score=score,
                    price=r.get("summary", {}).get("close", 0),
                    stop_price=r.get("summary", {}).get("stop_loss", 0),
                    entry_zone=f"{r.get('summary', {}).get('box_low', 0)}-{r.get('summary', {}).get('close', 0)}",
                    reason=f"综合评分{score}|{cls}",
                    classification=cls,
                ))

            # 卖出信号 (ZZJC触发 + 低分)
            if score <= thresholds["sell"] * 10:
                signals.append(Signal(
                    symbol=sym,
                    action="SELL",
                    urgency=min(5, int(5 - score)),
                    score=score,
                    price=r.get("summary", {}).get("close", 0),
                    stop_price=0,
                    entry_zone="",
                    reason=f"评分过低{score}",
                    classification=cls,
                ))

        # 按紧急度排序
        signals.sort(key=lambda s: s.urgency, reverse=True)
        return signals

    def force_exit_signal(self, symbol: str, reason: str, price: float = 0) -> Signal:
        """生成强制离场信号"""
        return Signal(
            symbol=symbol, action="SELL", urgency=5,
            score=0, price=price, stop_price=0,
            entry_zone="", reason=reason,
        )
