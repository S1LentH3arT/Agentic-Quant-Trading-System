#!/usr/bin/env python3
"""
校验入口 — 统一调用四个子校验模块
"""

from quant_system.validation.pool_check import PoolCheck
from quant_system.validation.factor_check import FactorCheck
from quant_system.validation.order_check import OrderCheck


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

        # 特征值范围
        features = data.get("market_features", {})
        _, feat_v = self._validate_features(features)
        violations.extend(feat_v)

        passed = len(violations) == 0
        return {
            "passed": passed,
            "sanitized": {
                **data,
                "pool_candidates": clean_pool,
                "L1_industry": clean_sectors,
            },
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
        """特征值范围检查"""
        violations = []
        # 基础范围检查
        for key, val in features.items():
            if isinstance(val, (int, float)) and pd.notna(val):
                if abs(val) > 1e6:
                    violations.append(f"特征值异常: {key}={val}")
        return features, violations
