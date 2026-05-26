#!/usr/bin/env python3
"""
参数加载器 — 从 params.json 读取可调参数，注入各模块覆盖硬编码默认值。

用法:
    from quant_system.evolution.param_loader import get_param, apply_params, rollback

    kelly_base = get_param('orchestrator.kelly_base', 0.10)
    apply_params()
    rollback()

安全机制:
    - 参数修改不超过当前值的 ±30%
    - 每次变更记录到 param_history.json
    - 支持 --rollback 恢复到上一个版本
"""

import sys, os, json
from datetime import datetime

from quant_system.config import get_path, ensure_dir

PARAMS_FILE = get_path("params.json")
HISTORY_FILE = get_path("storage", "state", "param_history.json")

_params_cache: dict = None
_params_flat: dict = None


def _flatten(section: dict, prefix: str = "") -> dict:
    result = {}
    for key, val in section.items():
        if key.startswith("_"):
            continue
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(val, dict) and "value" in val and "range" in val:
            result[full_key] = val
        elif isinstance(val, dict):
            result.update(_flatten(val, full_key))
    return result


def load_params(force_reload: bool = False) -> dict:
    global _params_cache
    if _params_cache is not None and not force_reload:
        return _params_cache
    try:
        with open(PARAMS_FILE, "r", encoding="utf-8") as f:
            _params_cache = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        _params_cache = {}
    return _params_cache


def get_flat_params() -> dict:
    global _params_flat
    if _params_flat is not None:
        return _params_flat
    params = load_params()
    _params_flat = _flatten(params)
    return _params_flat


def get_param(path: str, default=None):
    flat = get_flat_params()
    entry = flat.get(path)
    if entry and "value" in entry:
        return entry["value"]
    return default


def get_param_entry(path: str) -> dict | None:
    flat = get_flat_params()
    return flat.get(path)


def update_param(path: str, new_value, reason: str = "") -> bool:
    entry = get_param_entry(path)
    if not entry:
        return False
    old_value = entry["value"]
    valid_range = entry.get("range", [])
    if len(valid_range) == 2:
        lo, hi = valid_range
        if not (lo <= new_value <= hi):
            print(f"  [PARAM] 拒绝: {path}={new_value} 超出范围 [{lo}, {hi}]")
            return False
    if old_value != 0:
        change_pct = abs(new_value - old_value) / abs(old_value)
        if change_pct > 0.30:
            print(f"  [PARAM] 拒绝: {path} 变更 {change_pct:.0%} 超过 30% 上限")
            return False
    _record_history(path, old_value, new_value, reason)
    entry["value"] = new_value
    _write_params()
    global _params_flat
    _params_flat = None
    print(f"  [PARAM] 已更新: {path} = {old_value} → {new_value} ({reason})")
    return True


def _record_history(path: str, old_val, new_val, reason: str):
    ensure_dir("storage", "state")
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        history = []
    history.append({
        "timestamp": str(datetime.now()),
        "path": path,
        "old_value": old_val,
        "new_value": new_val,
        "reason": reason,
    })
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def _write_params():
    params = load_params(force_reload=True)
    with open(PARAMS_FILE, "w", encoding="utf-8") as f:
        json.dump(params, f, ensure_ascii=False, indent=2)


def rollback() -> str | None:
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    if not history:
        return None
    last = history.pop()
    path = last["path"]
    old_val = last["old_value"]
    entry = get_param_entry(path)
    if entry:
        entry["value"] = old_val
        _write_params()
        global _params_flat
        _params_flat = None
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        print(f"  [PARAM] 已回滚: {path} = {old_val}")
        return path
    return None


def get_all_param_paths() -> list[str]:
    return sorted(get_flat_params().keys())


def apply_params():
    global _params_cache, _params_flat
    _params_cache = None
    _params_flat = None


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--rollback":
        rolled = rollback()
        print(f"Rolled back: {rolled}" if rolled else "Nothing to rollback")
    elif len(sys.argv) > 1 and sys.argv[1] == "--list":
        for p in get_all_param_paths():
            entry = get_param_entry(p)
            print(f"  {p} = {entry['value']}  [{entry['range'][0]}, {entry['range'][1]}] — {entry['desc']}")
    else:
        paths = get_all_param_paths()
        print(f"参数注册表: {len(paths)} 个可调参数")
        print(f"文件: {PARAMS_FILE}")
