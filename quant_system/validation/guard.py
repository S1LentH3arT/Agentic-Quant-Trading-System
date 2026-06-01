#!/usr/bin/env python3
"""
校验入口 — 统一调用四个子校验模块
"""

import pandas as pd

from quant_system.validation.pool_check import PoolCheck
from quant_system.validation.factor_check import FactorCheck
from quant_system.validation.order_check import OrderCheck


# Agent 特征值合法范围
_FEATURE_RANGES = {
    "policy_support": (-1.0, 1.0),
    "research_catalyst": (0.0, 1.0),
    "north_direction": (-1.0, 1.0),
    "north_duration": (0, 30),
    "institution_phase": (-1, 2),
    "institution_ratio": (0.0, 1.0),
    "pe_percentile": (0.0, 100.0),
    "pb_percentile": (0.0, 100.0),
    "deducted_np_growth": (-100.0, 200.0),
    "revenue_growth": (-100.0, 200.0),
    "gross_margin": (0.0, 100.0),
    "margin_trend": (-1.0, 1.0),
    "goodwill_ratio": (0.0, 1.0),
    "pledge_ratio": (0.0, 1.0),
    "debt_risk": (0.0, 1.0),
    "cap_fit_score": (0.0, 1.0),
    "holder_decline_q": (0, 4),
    "holder_concentration": (0.0, 1.0),
    "inst_holder_ratio": (0.0, 1.0),
    "inst_quality": (0.0, 1.0),
    "lockup_ratio": (0.0, 1.0),
    "insider_reduction": (0.0, 1.0),
    "insider_sell_flag": (0, 1),
    "pledge_risk": (0.0, 1.0),
    "goodwill_risk": (0.0, 1.0),
    "chaos_flag": (0, 1),
    "fraud_risk": (0.0, 1.0),
}

_AGENT_LAYERS = ["L1_industry", "L2_capital", "L3_fundamentals", "L4_chip", "L7_risk"]


class ValidationGuard:
    """全系统唯一校验入口"""

    def __init__(self):
        self.pool_check = PoolCheck()
        self.factor_check = FactorCheck()
        self.order_check = OrderCheck()

    def validate_agent_output(self, data: dict) -> dict:
        """
        Agent 产出 → 入系统前的唯一闸门。
        返回: {passed: bool, sanitized: dict, violations: [str]}
        """
        violations = []

        # 品种池防幻觉
        pool = data.get("pool_candidates", [])
        clean_pool, pool_v = self.pool_check.validate(pool)
        violations.extend(pool_v)

        # 板块名真伪
        sectors = data.get("L1_industry", [])
        clean_sectors, sec_v = self._validate_sectors(sectors)
        violations.extend(sec_v)

        # 数值范围裁剪 (L1-L4-L7 每条记录)
        sanitized = {
            "pool_candidates": clean_pool,
            "L1_industry": clean_sectors,
            "market_features": data.get("market_features", {}),
        }
        for lk in _AGENT_LAYERS:
            items = data.get(lk, [])
            clean_items = []
            for item in items:
                cleaned, item_v = self._clamp_item(item)
                violations.extend(item_v)
                clean_items.append(cleaned)
            sanitized[lk] = clean_items

        passed = len(violations) == 0
        return {
            "passed": passed,
            "sanitized": sanitized,
            "violations": violations,
        }

    def validate_factor_proposal(self, proposal: dict) -> dict:
        """Agent 因子提案 → 校验 → 注册/拒绝"""
        return self.factor_check.validate(proposal)

    def validate_order(self, order: dict, account: dict) -> tuple[bool, str]:
        """订单终审: 资金/手数/价格"""
        return self.order_check.check(order, account)

    def _validate_sectors(self, sectors: list) -> tuple[list, list]:
        """板块名校验"""
        violations = []
        valid_names = set()
        try:
            from quant_system.data.bus import get_bus
            bus = get_bus()
            flow = bus.get_sector_flow()
            valid_names = {s.get('name', '') for s in flow}
        except Exception:
            pass

        clean = []
        for s in sectors:
            name = s.get("sector", "")
            if valid_names and name not in valid_names:
                violations.append(f"板块名无效: {name}")
            else:
                clean.append(s)
        return clean, violations

    def _validate_features(self, features: dict) -> tuple[dict, list]:
        """market_features 范围检查"""
        violations = []
        for key, val in features.items():
            if isinstance(val, (int, float)) and pd.notna(val):
                if abs(val) > 1e6:
                    violations.append(f"特征值异常: {key}={val}")
        return features, violations

    def _clamp_item(self, item: dict) -> tuple[dict, list]:
        """单条特征记录的范围裁剪。超出范围→裁到边界+警告。"""
        violations = []
        cleaned = dict(item)
        for field, (lo, hi) in _FEATURE_RANGES.items():
            if field in cleaned and cleaned[field] is not None:
                try:
                    v = float(cleaned[field])
                    if v < lo:
                        violations.append(f"{item.get('symbol', item.get('sector', '?'))}.{field}={v} < {lo}, 裁剪至{lo}")
                        cleaned[field] = lo
                    elif v > hi:
                        violations.append(f"{item.get('symbol', item.get('sector', '?'))}.{field}={v} > {hi}, 裁剪至{hi}")
                        cleaned[field] = hi
                except (ValueError, TypeError):
                    violations.append(f"{item.get('symbol', item.get('sector', '?'))}.{field} 非数值: {cleaned[field]}")
                    cleaned[field] = 0  # 非数值归零
        return cleaned, violations
