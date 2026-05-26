#!/usr/bin/env python3
"""
评分引擎 — L1-L7 加权综合评分
技术评分 (L6) + Agent特征叠加 (L1-L4) + L7排雷否决
"""

import numpy as np
import pandas as pd
from quant_system.factors.registry import get_registry


class Scorer:
    """8层加权综合评分器"""

    # 各层权重 (设计文档定义)
    LAYER_WEIGHTS = {
        1: 0.15,  # 产业宏观
        2: 0.18,  # 资金追踪
        3: 0.18,  # 财报内核
        4: 0.12,  # 筹码结构
        5: 0.10,  # 流动性
        6: 0.17,  # 技术趋势
        7: 0.00,  # 风控排雷 (否决，不参与加权)
    }

    def __init__(self):
        self.registry = get_registry()

    def score(self, df: pd.DataFrame, symbol: str = "",
              agent_features: dict = None) -> dict:
        """
        综合评分。
        返回 {score: 0-10, layer_scores: {}, veto: bool, veto_reason: "", details: []}
        """
        # L7 排雷 — 先执行
        l7_result = self._score_l7(df, symbol, agent_features)
        if l7_result.get("exclude"):
            return {"score": 0, "layer_scores": {}, "veto": True,
                    "veto_reason": l7_result.get("reason", "L7排雷剔除"),
                    "details": l7_result.get("details", [])}

        # L1-L6 逐层评分
        layer_scores = {}
        details = []

        for layer in range(1, 7):
            ls, ld = self._score_layer(df, symbol, layer, agent_features)
            layer_scores[f"L{layer}"] = ls
            details.extend(ld)

        # 加权综合
        weighted = sum(
            layer_scores.get(f"L{l}", 0) * self.LAYER_WEIGHTS.get(l, 0)
            for l in range(1, 7)
        )

        # 映射到 0-10
        total_score = min(10, round(weighted * 10, 1))

        return {
            "score": total_score,
            "layer_scores": layer_scores,
            "veto": False,
            "veto_reason": "",
            "details": details,
        }

    def _score_layer(self, df: pd.DataFrame, symbol: str, layer: int,
                     agent_features: dict = None) -> tuple[float, list]:
        """对单层因子加权求和出 layer_score → [0,1]"""
        names = self.registry.list_by_layer(layer)
        weights = self.registry.get_layer_weights(layer)
        if not names or not weights:
            return 0.0, []

        total_weight = sum(weights.get(n, 0) for n in names) or 1.0
        raw_score = 0.0
        layer_details = []

        for name in names:
            fd = self.registry.get(name)
            if not fd:
                continue
            w = weights.get(name, 0) / total_weight

            # 从 DataFrame 取因子值
            factor_val = self._extract_factor(df, fd, symbol, agent_features)
            raw_score += factor_val * w
            layer_details.append(f"L{layer}.{name}: {factor_val:.2f} (w={w:.2f})")

        return min(1.0, max(0.0, raw_score)), layer_details

    def _score_l7(self, df: pd.DataFrame, symbol: str,
                  agent_features: dict = None) -> dict:
        """L7 排雷 — 硬性剔除规则"""
        details = []

        # 1. 科创板剔除
        if symbol.startswith('688'):
            return {"exclude": True, "reason": "科创板剔除", "details": ["688开头"]}

        # 2. 高位翻倍
        if 'RISE30' in df.columns:
            val = float(df['RISE30'].iloc[-1]) if len(df) > 0 else 0
            if val > 100:
                return {"exclude": True, "reason": f"60日涨幅{val:.0f}%，高位排除",
                        "details": [f"RISE30={val:.0f}%"]}

        # 3. Agent 标记的排除
        if agent_features:
            l7 = agent_features.get("L7_risk", [])
            for r in l7:
                if r.get("symbol") == symbol and r.get("exclude"):
                    return {"exclude": True,
                            "reason": r.get("exclude_reason", "Agent标记排除"),
                            "details": [r.get("exclude_reason", "")]}

        return {"exclude": False, "reason": "", "details": details}

    def _extract_factor(self, df: pd.DataFrame, fd, symbol: str,
                        agent_features: dict) -> float:
        """从DataFrame或Agent特征中提取因子值，归一化到 [0,1]"""
        col = fd.output_columns[0] if fd.output_columns else ""

        if col in df.columns:
            raw = float(df[col].iloc[-1]) if len(df) > 0 else 0.0

            # L6 因子归一化
            if fd.layer == 6:
                if col == "A1X":
                    return min(1.0, max(0.0, (raw + 5) / 10))
                if col == "box_position":
                    return min(1.0, max(0.0, (70 - raw) / 70))
                if col == "vol_ratio":
                    return min(1.0, max(0.0, (raw - 0.5) / 2.0))
                if col == "DKX" and "SMX" in df.columns:
                    smx = float(df['SMX'].iloc[-1])
                    return 1.0 if raw > smx else 0.3
                if col in ("DZT", "ZT", "FANGLIANG2", "STRONG"):
                    return float(raw > 0)
                if col in ("daily_trend", "above_ma60", "above_ma120", "ma_aligned"):
                    return float(raw > 0)
                return min(1.0, max(0.0, raw)) if pd.notna(raw) else 0.0

            return min(1.0, max(0.0, raw)) if pd.notna(raw) else 0.0

        # Agent 特征取值
        if agent_features and fd.layer in (1, 2, 3, 4):
            layer_key = f"L{fd.layer}_industry" if fd.layer == 1 else \
                        f"L{fd.layer}_capital" if fd.layer == 2 else \
                        f"L{fd.layer}_fundamentals" if fd.layer == 3 else \
                        f"L{fd.layer}_chip"
            items = agent_features.get(layer_key, [])
            for item in items:
                if item.get("symbol") == symbol or item.get("sector"):
                    return float(item.get(col, 0) or 0)
            return 0.0

        return 0.0


def get_summary(df: pd.DataFrame, symbol: str = "") -> dict:
    """从指标 DataFrame 提取最新信号摘要 (兼容原 indicator_engine 接口)"""
    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else last

    def safe(v, default=0):
        return round(float(v), 2) if pd.notna(v) else default

    return {
        "symbol": symbol,
        "close": safe(last.get('close', 0)),
        "DKX": safe(last.get('DKX', 0)),
        "SMX": safe(last.get('SMX', 0)),
        "A1X": safe(last.get('A1X', 0)),
        "a1x_direction": "↑" if safe(last.get('A1X', 0)) > safe(prev.get('A1X', 0)) else "↓",
        "DZT": bool(last.get('DZT', 0)),
        "ZZJC": bool(last.get('ZZJC', 0)),
        "box_high": safe(last.get('box_high', 0)),
        "box_low": safe(last.get('box_low', 0)),
        "box_position_pct": round(safe(last.get('box_position', 0)), 1),
        "vol_ratio": safe(last.get('vol_ratio', 0)),
        "change_pct": safe(last.get('ZF', 0)),
        "strong_trend": bool(last.get('STRONG', 0)),
        "weak_trend": bool(last.get('WEAK', 0)),
        "fake_break": bool(last.get('FAKE', 0)),
        "stop_loss": safe(last.get('stop_line', 0)),
        "ma5_angle": safe(last.get('MA5_ANGLE', 0)),
    }
