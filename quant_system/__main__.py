#!/usr/bin/env python3
"""
Quant System v3 — 主入口
用法: python -m quant_system [command]

Commands:
  test       — 运行系统导入测试 + 因子注册验证
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

    print(f"\n  状态: 系统就绪 ✓")
    return 0


def cmd_scan():
    """一次完整决策扫描"""
    print("=" * 60)
    print(f"  Quant System — 决策扫描 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    from quant_system.data.bus import get_bus
    from quant_system.factors.engine import FactorEngine
    from quant_system.strategy.scorer import Scorer, get_summary
    from quant_system.strategy.signals import SignalGenerator
    from quant_system.strategy.pool import PoolManager
    from quant_system.strategy.classifier import Classifier

    bus = get_bus()
    engine = FactorEngine()
    scorer = Scorer()
    classifier = Classifier()

    pool = PoolManager()
    symbols = pool.get_full_pool()

    print(f"\n[1/4] 加载数据 ({len(symbols)} 只)...")
    klines = bus.get_daily(symbols, count=120)

    print("[2/4] 计算因子+评分...")
    results = []
    for sym, df in klines.items():
        if df is None or len(df) < 40:
            continue
        df = engine.compute(df)
        s = get_summary(df, sym)
        sc = scorer.score(df, sym)
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

    print(f"  模块: 全部就绪 ✓")
    return 0


COMMANDS = {
    "test": cmd_test,
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
