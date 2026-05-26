#!/usr/bin/env python3
"""
项目全局配置 — 集中管理所有路径
所有模块通过此文件获取路径，不再硬编码

用法:
    from quant_system.config import PROJECT_ROOT, get_path, ensure_dir

    save_dir = get_path('backtest')
    ensure_dir('strategy')
"""

import os
import sys

# ── 项目根目录: 自动检测 ──
PROJECT_ROOT = os.environ.get(
    "QUANT_PROJECT_ROOT",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
).replace("\\", "/")

# quant_system 自身目录
SYSTEM_ROOT = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")


def get_path(*parts: str) -> str:
    """返回相对于 quant_system 目录的绝对路径"""
    return os.path.join(SYSTEM_ROOT, *parts).replace("\\", "/")


def ensure_dir(*parts: str) -> str:
    """创建目录（如不存在）并返回路径"""
    path = get_path(*parts)
    os.makedirs(path, exist_ok=True)
    return path


# ── 常用目录映射 ──
DIRS = {
    "system_root":     SYSTEM_ROOT,
    "data":            get_path("data"),
    "factors":         get_path("factors"),
    "strategy":        get_path("strategy"),
    "risk":            get_path("risk"),
    "execution":       get_path("execution"),
    "backtest":        get_path("backtest"),
    "agents":          get_path("agents"),
    "validation":      get_path("validation"),
    "evolution":       get_path("evolution"),
    "storage":         get_path("storage"),
    "state":           get_path("storage", "state"),
    "trade_db":        get_path("storage", "state", "trades.db"),
}


def print_config():
    """打印当前配置（调试用）"""
    print(f"PROJECT_ROOT = {PROJECT_ROOT}")
    print(f"SYSTEM_ROOT  = {SYSTEM_ROOT}")
    print(f"Python = {sys.executable}")
    for k, v in DIRS.items():
        exists = "✓" if os.path.exists(v) else "✗"
        print(f"  {k:20s} {exists} {v}")


if __name__ == "__main__":
    print_config()
