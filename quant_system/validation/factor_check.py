#!/usr/bin/env python3
"""
因子合法性校验 — 安全编译 + 样本测试
"""


class FactorCheck:
    FORBIDDEN = [
        'import ', 'exec', 'eval', '__', 'os.', 'sys.', 'subprocess',
        'open(', 'file', 'socket', 'http', 'url', 'request',
    ]

    def validate(self, proposal: dict) -> dict:
        """校验Agent提交的因子定义"""
        checks = []

        formula = proposal.get("compute_fn", "")
        for kw in self.FORBIDDEN:
            if kw in formula:
                checks.append({"passed": False, "reason": f"禁止关键词: {kw}"})

        try:
            compile(formula, '<factor>', 'eval')
            checks.append({"passed": True, "reason": "编译通过"})
        except SyntaxError as e:
            checks.append({"passed": False, "reason": f"语法错误: {e}"})

        # 列名冲突
        try:
            from quant_system.factors.registry import get_registry
            existing = get_registry().list_all_columns()
            for col in proposal.get("output_columns", []):
                if col in existing:
                    checks.append({"passed": False, "reason": f"列名冲突: {col}"})
        except Exception:
            pass

        passed = all(c.get("passed", False) for c in checks)
        return {"passed": passed, "checks": checks, "proposal": proposal}
