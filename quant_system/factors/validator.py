#!/usr/bin/env python3
"""
因子校验器 — 公式安全编译 + 样本测试 + IC 检查
"""

import numpy as np
import pandas as pd
from quant_system.factors.registry import FactorDefinition


class FactorValidator:
    """校验Agent提交的因子定义"""

    FORBIDDEN = [
        'import ', 'exec', 'eval', '__', 'os.', 'sys.', 'subprocess',
        'open(', 'file', 'socket', 'http', 'url', 'request',
        '__builtins__', '__import__', 'compile(',
    ]

    def check_formula_safety(self, fd: FactorDefinition) -> tuple[bool, str]:
        """公式字符串安全检查"""
        formula = fd.compute_fn or ""
        for kw in self.FORBIDDEN:
            if kw in formula:
                return False, f"公式含禁止关键词: {kw}"
        return True, "安全"

    def check_formula_compiles(self, fd: FactorDefinition) -> tuple[bool, str]:
        """公式可编译为Python表达式"""
        formula = fd.compute_fn or ""
        try:
            compile(formula, '<factor>', 'eval')
            return True, "编译通过"
        except SyntaxError as e:
            return False, f"语法错误: {e}"

    def check_naming(self, fd: FactorDefinition) -> tuple[bool, str]:
        """输出列名不与已有因子冲突"""
        from quant_system.factors.registry import get_registry
        R = get_registry()
        existing = R.list_all_columns()
        for col in fd.output_columns:
            if col in existing:
                return False, f"列名冲突: {col} 已被注册"
        return True, "无冲突"

    def check_params_range(self, fd: FactorDefinition) -> tuple[bool, str]:
        """参数值在合法范围内"""
        for name, spec in fd.params.items():
            val = spec.get("value", spec.get("default", 0))
            rng = spec.get("range", [])
            if len(rng) == 2:
                lo, hi = rng
                if not (lo <= val <= hi):
                    return False, f"参数 {name}={val} 超出 [{lo}, {hi}]"
        return True, "参数合法"

    def test_run(self, fd: FactorDefinition) -> tuple[bool, str]:
        """用随机样本数据实际运行因子"""
        from quant_system.factors.registry import get_registry
        R = get_registry()
        fn = R.get_compute_fn(fd.name)
        if fn is None:
            try:
                fn = eval(fd.compute_fn)
            except Exception:
                return False, "compute_fn 无法eval执行"

        try:
            n = 100
            df = pd.DataFrame({
                'open': np.random.randn(n).cumsum() + 10,
                'high': np.random.randn(n).cumsum() + 11,
                'low': np.random.randn(n).cumsum() + 9,
                'close': np.random.randn(n).cumsum() + 10,
                'volume': np.abs(np.random.randn(n)) * 1e6,
            })
            params = {k: v.get("value", v.get("default", 0)) for k, v in fd.params.items()}
            result = fn(df, params)
            if result is None or len(result) == 0:
                return False, "因子返回空结果"
            return True, f"样本测试通过 (n={n})"
        except Exception as e:
            return False, f"运行异常: {e}"

    def full_validate(self, fd: FactorDefinition) -> dict:
        """全部检查"""
        checks = []
        for check_fn, name in [
            (self.check_formula_safety, "公式安全"),
            (self.check_formula_compiles, "公式编译"),
            (self.check_naming, "命名冲突"),
            (self.check_params_range, "参数范围"),
        ]:
            passed, reason = check_fn(fd)
            checks.append({"name": name, "passed": passed, "reason": reason})

        if all(c["passed"] for c in checks):
            passed, reason = self.test_run(fd)
            checks.append({"name": "样本运行", "passed": passed, "reason": reason})

        passed = all(c["passed"] for c in checks)
        return {"passed": passed, "checks": checks}

    def quick_ic(self, factor_name: str, symbols: list[str],
                 forward_days: int = 5) -> dict:
        """快速 IC 测试"""
        from quant_system.data.bus import get_bus
        from quant_system.factors.registry import get_registry
        from quant_system.factors.engine import FactorEngine

        bus = get_bus()
        engine = FactorEngine()
        ics = []

        for sym in symbols[:20]:
            klines = bus.get_daily([sym], count=120)
            df = klines.get(sym)
            if df is None or len(df) < 60:
                continue
            df = engine.compute(df, layers=[6])

            col = None
            fd = get_registry().get(factor_name)
            if fd and fd.output_columns:
                col = fd.output_columns[0]

            if col and col in df.columns:
                factor_vals = df[col].values[:-forward_days]
                fwd_returns = (df['close'].shift(-forward_days) / df['close'] - 1).values[:-forward_days]
                valid = ~(np.isnan(factor_vals) | np.isnan(fwd_returns))
                if valid.sum() > 10:
                    ic = np.corrcoef(factor_vals[valid], fwd_returns[valid])[0, 1]
                    ics.append(ic)

        if ics:
            return {"mean_ic": round(np.mean(ics), 4), "std_ic": round(np.std(ics), 4),
                    "count": len(ics)}
        return {"mean_ic": 0, "std_ic": 0, "count": 0}
