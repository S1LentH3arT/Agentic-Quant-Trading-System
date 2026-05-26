#!/usr/bin/env python3
"""
L8 价值分类器 — 标的分为: 价值趋势股 / 拐点反转股 / 低位潜伏股
"""


class Classifier:
    """
    L8 价值分类:
    · 价值趋势股: L3≥0.7 + L2≥0.6 + L6≥0.5 → 中长线持有
    · 拐点反转股: L3≥0.5 + L2≥0.7 + L6拐点共振 → 核心主攻
    · 低位潜伏股: L3≥0.6 + PE分位低 + L4≥0.5 + L2待启动 → 轻仓埋伏
    """

    def classify(self, layer_scores: dict[str, float],
                 extra_signals: dict = None) -> str:
        """
        输入:
          layer_scores: {"L1": 0.6, "L2": 0.8, "L3": 0.5, "L4": 0.4, "L5": 0.3, "L6": 0.7}
          extra_signals: {"DZT": True, "box_breakout": True, "pe_percentile": 15}
        返回: "价值趋势" | "拐点反转" | "低位潜伏" | "未分类"
        """
        extra = extra_signals or {}

        l2 = layer_scores.get("L2", 0)
        l3 = layer_scores.get("L3", 0)
        l4 = layer_scores.get("L4", 0)
        l6 = layer_scores.get("L6", 0)

        has_breakout = extra.get("DZT", False) or extra.get("box_breakout", False)
        pe_low = extra.get("pe_percentile", 50) < 20

        # 价值趋势: 优质 + 稳健
        if l3 >= 0.7 and l2 >= 0.6 and l6 >= 0.5:
            return "价值趋势"

        # 拐点反转: 资金强 + 技术共振
        if l3 >= 0.5 and l2 >= 0.7 and has_breakout:
            return "拐点反转"

        # 低位潜伏: 低估 + 筹码集中
        if l3 >= 0.6 and pe_low and l4 >= 0.5:
            return "低位潜伏"

        return "未分类"

    def classify_batch(self, scored_results: list[dict]) -> dict[str, str]:
        """批量分类"""
        results = {}
        for r in scored_results:
            sym = r.get("symbol", "")
            layer_scores = r.get("layer_scores", {})
            extra = {
                "DZT": r.get("summary", {}).get("DZT", False),
                "box_breakout": r.get("summary", {}).get("box_breakout", False),
            }
            results[sym] = self.classify(layer_scores, extra)
        return results
