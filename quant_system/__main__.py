#!/usr/bin/env python3
"""
Quant System v3 — 主入口
用法: python -m quant_system [command]

Commands:
  test       — 运行系统导入测试 + 因子注册验证
  intel      — 情报采集 (热榜/电报/板块/新高 → 交叉验证 + 市场状态)
  scan       — 运行一次完整决策扫描 (数据 → 因子 → 评分 → 信号)
  backtest   — 对主力池运行回测
  status     — 打印系统状态
"""

import sys
from datetime import datetime


def cmd_test():
    """系统导入测试"""
    print("=" * 60)
    print("  Quant System v3 — 系统测试")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    from quant_system.factors.engine import FactorEngine
    engine = FactorEngine()
    active = engine.registry.list_active()
    print(f"\n  已注册因子: {len(active)}")
    for name in active:
        fd = engine.registry.get(name)
        print(f"    L{fd.layer} {name}: {len(fd.output_columns)} columns")

    from quant_system.backtest.light import LightBacktest
    lb = LightBacktest()
    print(f"\n  轻量回测: OK")

    from quant_system.strategy.pool import PoolManager
    pm = PoolManager()
    pool = pm.get_full_pool()
    print(f"\n  品种池: {len(pool)} 只")
    for sec, syms in pm.get_sector_pool().items():
        print(f"    {sec}: {len(syms)} 只")

    print(f"\n  状态: 系统就绪 [OK]")
    return 0


def cmd_intel():
    """情报采集 — 热榜/电报/板块/新高 → 交叉验证"""
    print("=" * 60)
    print(f"  Quant System — 情报采集 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    from quant_system.data.intelligence import collect_intelligence

    result = collect_intelligence(save=True)
    print(f"\n  市场状态: {result['market_state']} (上证 {result['sh_index_change']:+.2f}%)")
    print(f"  共识标的 ({len(result['high_consensus'])} 只):")
    for code in result['high_consensus'][:10]:
        print(f"    {code}")
    print(f"  漏判标的 ({len(result['missed'])} 只):")
    for code in result['missed'][:5]:
        print(f"    {code}")
    print(f"  板块方向: {', '.join(result['sector_direction'][:5])}")
    print(f"  热榜覆盖: {len(result['hot_rank'])} 只 | 电报: {len(result['cls_news'])} 条")
    return 0


def cmd_scan():
    """一次完整决策扫描。加 --agent 启用 QuantResearchAgent 增强评分。"""
    print("=" * 60)
    print(f"  Quant System — 决策扫描 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    from quant_system.data.bus import get_bus
    from quant_system.data.intelligence import collect_intelligence
    from quant_system.factors.engine import FactorEngine
    from quant_system.strategy.scorer import Scorer, get_summary
    from quant_system.strategy.signals import SignalGenerator
    from quant_system.strategy.pool import PoolManager
    from quant_system.strategy.classifier import Classifier
    from quant_system.agents.bridge import run_agent_enrichment

    use_agent = "--agent" in sys.argv

    # ── 0. 情报采集 ──
    intel = collect_intelligence(save=True)
    print(f"\n  市场状态: {intel['market_state']} (上证 {intel['sh_index_change']:+.2f}%)")
    print(f"  共识标的: {len(intel['high_consensus'])} 只 | 漏判: {len(intel['missed'])} 只")
    print(f"  板块方向: {', '.join(intel['sector_direction'][:5])}")

    bus = get_bus()
    engine = FactorEngine()
    scorer = Scorer()
    classifier = Classifier()

    pool = PoolManager()
    # 共识标的优先入库，漏判标的追加到扫描池
    for code in intel.get('high_consensus', []):
        pool.add(code, source="consensus")
    symbols = pool.get_full_pool()
    # 合并漏判标的到扫描列表
    for code in intel.get('missed', []):
        if code not in symbols:
            symbols.append(code)

    # ── Agent 增强 (可选) ──
    agent_features = run_agent_enrichment(intel, symbols, force=use_agent)
    if agent_features:
        n_sec = len(agent_features.get('L1_industry', []))
        n_cap = len(agent_features.get('L2_capital', []))
        n_fin = len(agent_features.get('L3_fundamentals', []))
        n_chip = len(agent_features.get('L4_chip', []))
        print(f"  Agent: L1={n_sec}板块 L2={n_cap}资金 L3={n_fin}财报 L4={n_chip}筹码 已注入")
    elif use_agent:
        print(f"  Agent: 未启用/调用失败，使用系统默认特征")

    print(f"\n[1/4] 加载数据 ({len(symbols)} 只)...")
    klines = bus.get_daily(symbols, count=120)

    print("[2/4] 计算因子+评分...")
    results = []
    for sym, df in klines.items():
        if df is None or len(df) < 40:
            continue
        df = engine.compute(df)
        s = get_summary(df, sym)
        sc = scorer.score(df, sym, agent_features=agent_features)
        results.append({"symbol": sym, "summary": s, **sc})

    print("[3/4] 分类+生成信号...")
    classifications = classifier.classify_batch(results)
    gen = SignalGenerator()
    signals = gen.generate(results, classifications)

    print(f"[4/4] 完成 — {len(results)} 只评分, {len(signals)} 个信号")

    if signals:
        print("\n  信号列表:")
        for sig in signals[:10]:
            print(f"  {sig.action} {sig.symbol} 评分{sig.score} {sig.classification} | {sig.reason}")

    return 0


def cmd_backtest():
    """主力池回测"""
    print("=" * 60)
    print(f"  Quant System — 回测 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    from quant_system.data.bus import get_bus
    from quant_system.backtest.engine import FullBacktestEngine

    bus = get_bus()
    from quant_system.strategy.pool import PoolManager
    pool = PoolManager()
    symbols = pool.get_full_pool()[:10]

    print(f"\n[1/2] 加载数据 ({len(symbols)} 只)...")
    klines = bus.get_daily(symbols, count=300)

    print("[2/2] 运行回测...")
    engine = FullBacktestEngine()
    result = engine.run_multi({s: df for s, df in klines.items() if df is not None and len(df) >= 50})

    if "error" not in result:
        m = result["aggregate_metrics"]
        print(f"\n  汇总指标:")
        print(f"    标的数: {result['total_tested']} | 盈利: {result['profitable']}")
        print(f"    胜率: {m['win_rate']}% | 赔率: {m['payoff_ratio']}")
        print(f"    夏普: {m['sharpe_ratio']} | 最大回撤: {m['max_drawdown_pct']}%")
        print(f"    平均收益: {m['avg_total_return']}%")

        if result.get('top_performers'):
            print(f"\n  TOP3:")
            for i, p in enumerate(result['top_performers'][:3]):
                print(f"    {i+1}. {p['symbol']} 收益{p['total_return_pct']}% 胜率{p['win_rate']}% 夏普{p['sharpe_ratio']}")

    return 0


def cmd_status():
    """打印系统状态"""
    print("=" * 60)
    print(f"  Quant System v3 — 系统状态")
    print("=" * 60)

    from quant_system.config import print_config
    print_config()

    from quant_system.factors.engine import FactorEngine
    engine = FactorEngine()
    print(f"\n  因子: {len(engine.registry.list_active())} 激活 + {len(engine.registry.list_pending())} 待审核")

    from quant_system.strategy.pool import PoolManager
    pm = PoolManager()
    print(f"  品种池: {len(pm.get_full_pool())} 只")

    print(f"  模块: 全部就绪 [OK]")
    return 0


COMMANDS = {
    "test": cmd_test,
    "intel": cmd_intel,
    "scan": cmd_scan,
    "backtest": cmd_backtest,
    "status": cmd_status,
}

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    fn = COMMANDS.get(cmd)
    if fn:
        sys.exit(fn())
    else:
        print(f"未知命令: {cmd}")
        print(f"可用: {', '.join(COMMANDS.keys())}")
        sys.exit(1)
