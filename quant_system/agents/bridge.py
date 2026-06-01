#!/usr/bin/env python3
"""
Agent 桥接模块 — intel 数据 → QuantResearchAgent → 校验 → scorer 可用的 agent_features。
Agent 失败时优雅降级，不抛异常。
"""

import os
from quant_system.evolution.param_loader import get_param
from quant_system.validation.guard import ValidationGuard


def run_agent_enrichment(intel: dict, symbols: list[str],
                         force: bool = False) -> dict | None:
    """
    intel + symbols → Agent → 校验 → agent_features dict | None。

    force=True: 忽略 params.json 的 enabled 设置，强制启用 Agent。
    失败时返回 None (降级，不影响后续评分)。
    """
    # 1. 检查是否启用
    enabled = force or get_param('agent.enabled', False)
    if not enabled:
        return None

    # 2. 检查 API key
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        print("  [Agent] DEEPSEEK_API_KEY 未设置，跳过 Agent 增强")
        return None

    # 3. 限制送入标的数
    max_stocks = get_param('agent.max_stocks', 20)
    if len(symbols) > max_stocks:
        symbols = symbols[:max_stocks]

    # 4. 提取 intel 数据
    hot_rank = intel.get("hot_rank", [])
    sector_flow = intel.get("sector_flow", []) or intel.get("sector_direction", [])
    news = intel.get("cls_news", [])
    if not news:
        # Fallback: 从 reasoning 提取关键词
        news = [intel.get("reasoning", "")]

    if not hot_rank and not sector_flow:
        print("  [Agent] intel 数据为空，跳过 Agent 增强")
        return None

    # 5. 调用 Agent
    timeout = get_param('agent.timeout_seconds', 60)
    try:
        from quant_system.agents.researcher import QuantResearchAgent
        agent = QuantResearchAgent(timeout=timeout)
        raw = agent.analyze(
            hot_rank=hot_rank[:30],
            sector_flow=sector_flow[:10],
            news_headlines=news[:20],
            scanned_symbols=symbols,
        )
    except Exception as e:
        print(f"  [Agent] API 调用失败 ({e})，降级为系统默认特征")
        return None

    # 6. 校验
    guard = ValidationGuard()
    result = guard.validate_agent_output(raw)
    violations = result.get("violations", [])
    if violations:
        for v in violations[:5]:
            print(f"  [Agent] 校验违规: {v}")
        if len(violations) > 5:
            print(f"  [Agent] ... 共 {len(violations)} 条违规")

    return result["sanitized"]
