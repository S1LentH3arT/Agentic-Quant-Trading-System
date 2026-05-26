#!/usr/bin/env python3
"""
因子注册表 — 管理所有因子的定义、激活、版本。
"""

from dataclasses import dataclass, field
from typing import Callable, Optional
import json
from quant_system.config import get_path


@dataclass
class FactorDefinition:
    """因子定义规范"""
    name: str                           # 因子名，如 "A1X"
    layer: int                          # 1-7 对应选股体系层级
    category: str                       # industry/capital_flow/fundamentals/chip/liquidity/technical/risk_filter
    version: int = 1
    author: str = "system"              # "system" 或 "agent"
    params: dict = field(default_factory=dict)  # {name: {value, range, desc}}
    compute_fn: str = ""                # Python lambda/compute function name
    requires: list = field(default_factory=list)  # 需要的输入列
    output_columns: list = field(default_factory=list)  # 输出的新列名
    layer_weight: float = 0.0           # 层内权重
    hypothesis: str = ""


class FactorRegistry:
    """因子注册表 — 管理全部因子"""

    def __init__(self, param_loader=None):
        self._factors: dict[str, FactorDefinition] = {}
        self._pending: dict[str, FactorDefinition] = {}
        self._active: set[str] = set()
        self._compute_fns: dict[str, Callable] = {}
        self._param_loader = param_loader

    def register(self, fd: FactorDefinition):
        """注册因子。system因子直接激活，agent因子进入pending"""
        if fd.author == "agent":
            self._pending[fd.name] = fd
        else:
            self._factors[fd.name] = fd
            self._active.add(fd.name)

    def validate_pending(self, name: str) -> tuple[bool, str]:
        """校验Agent提交的因子"""
        fd = self._pending.get(name)
        if not fd:
            return False, f"未找到pending因子: {name}"
        # 由 validator 模块完成实际校验
        from quant_system.factors.validator import FactorValidator
        v = FactorValidator()
        result = v.full_validate(fd)
        return result["passed"], "; ".join(
            c["reason"] for c in result["checks"] if not c["passed"]
        )

    def activate(self, name: str) -> bool:
        """pending → active"""
        fd = self._pending.pop(name, None)
        if fd:
            self._factors[name] = fd
            self._active.add(name)
            return True
        return False

    def reject(self, name: str):
        self._pending.pop(name, None)

    def get(self, name: str) -> Optional[FactorDefinition]:
        return self._factors.get(name)

    def list_active(self) -> list[str]:
        return sorted(self._active)

    def list_pending(self) -> list[str]:
        return sorted(self._pending.keys())

    def list_by_layer(self, layer: int) -> list[str]:
        return sorted(
            k for k in self._active
            if self._factors.get(k) and self._factors[k].layer == layer
        )

    def list_all_columns(self) -> set[str]:
        """所有已注册因子的 output_columns 集合"""
        cols = set()
        for fd in self._factors.values():
            cols.update(fd.output_columns)
        return cols

    def get_layer_weights(self, layer: int) -> dict[str, float]:
        """获取某层所有激活因子的权重"""
        return {
            name: fd.layer_weight
            for name in self.list_by_layer(layer)
            if (fd := self.get(name)) is not None
        }

    def set_compute_fn(self, name: str, fn: Callable):
        self._compute_fns[name] = fn

    def get_compute_fn(self, name: str) -> Optional[Callable]:
        return self._compute_fns.get(name)

    def current_params(self, name: str) -> dict:
        """获取因子当前参数值"""
        fd = self.get(name)
        if not fd:
            return {}
        params = {}
        for pname, pspec in fd.params.items():
            val = pspec.get("value", pspec.get("default", 0))
            if self._param_loader:
                val = self._param_loader(
                    f"factors.{fd.category}.{name}.{pname}", val
                )
            params[pname] = val
        return params


# 全局单例
_registry = None

def get_registry() -> FactorRegistry:
    global _registry
    if _registry is None:
        _registry = FactorRegistry()
    return _registry
