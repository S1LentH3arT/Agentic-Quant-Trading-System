#!/usr/bin/env python3
"""
项目全局配置 — 集中管理所有路径
所有模块通过此文件获取路径，不再硬编码

用法:
    from config import PROJECT_ROOT, get_path, ensure_dir

    sys.path.insert(0, get_path('tdx-mcp'))
    save_dir = get_path('tdx-mcp', 'scans')
    ensure_dir('tdx-mcp', 'charts')
"""

import os
import sys

# ── 项目根目录: 自动检测 ──
# 优先级: 环境变量 > 本文件所在目录
PROJECT_ROOT = os.environ.get(
    "QUANT_PROJECT_ROOT",
    os.path.dirname(os.path.abspath(__file__))
).replace("\\", "/")


def get_path(*parts: str) -> str:
    """返回相对于项目根目录的绝对路径"""
    return os.path.join(PROJECT_ROOT, *parts).replace("\\", "/")


def ensure_dir(*parts: str) -> str:
    """创建目录（如不存在）并返回路径"""
    path = get_path(*parts)
    os.makedirs(path, exist_ok=True)
    return path


# ── 常用目录映射 ──
DIRS = {
    "tdx_mcp":       get_path("tdx-mcp"),
    "scans":         get_path("tdx-mcp", "scans"),
    "charts":        get_path("tdx-mcp", "charts"),
    "discoveries":   get_path("tdx-mcp", "discoveries"),
    "state":         get_path("tdx-mcp", "state"),
    "alerts":        get_path("tdx-mcp", "alerts"),
    "agents_output": get_path("agents", "output"),
    "meta_storage":  get_path("meta-evolution", "storage"),
    "knowledge":     get_path("knowledge"),
    "rules":         get_path("knowledge", "rules"),
    "memory":        get_path("memory"),
}


def print_config():
    """打印当前配置（调试用）"""
    print(f"PROJECT_ROOT = {PROJECT_ROOT}")
    print(f"Python = {sys.executable}")
    for k, v in DIRS.items():
        exists = "✓" if os.path.exists(v) else "✗"
        print(f"  {k:20s} {exists} {v}")


if __name__ == "__main__":
    print_config()
