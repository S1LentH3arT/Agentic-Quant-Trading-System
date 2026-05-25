import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from backtest_engine import run_market_backtest, BacktestEngine
from indicator_engine import load_kline, calc_all_indicators, get_summary

SYMBOLS = [
    "600863","601991","000070","600089","600406","601179","600312","000400",
    "600875","300827","600379","600900","600011","300903","600183","002463",
    "601698","603881","300608","688500","002272","002892","002421"
]

print("=" * 70)
print("  综合决策王 全市场回测 — 7维度客观指标")
print("=" * 70)

result = run_market_backtest(SYMBOLS)
agg = result.get("aggregate_metrics", {})

print(f"\n{'='*70}")
print(f"  回测完成: {result['total_stocks_tested']}只 | {result['total_trades']}笔交易 | {result['profitable_stocks']}只盈利")
print(f"{'='*70}")

m = agg
print(f"""
┌─────────────────────────────────────────────────────────┐
│              7 维度客观指标（全样本汇总）                │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. 胜率:          {m['win_rate']:>6.1f}%                │
│     → 每100笔交易中, {m['win_rate']:.0f}笔盈利           │
│                                                         │
│  2. 赔率:          {m['payoff_ratio']:>6.2f}            │
│     → 每亏1元, 赚回{m['payoff_ratio']:.2f}元             │
│                                                         │
│  3. 仓位率(Kelly):  {m['kelly_fraction']:>6.1f}%         │
│     → 理论最优单笔仓位                                   │
│                                                         │
│  4. 出手频率:      {m['trade_freq_per_year']:>6.1f} 次/年│
│                                                         │
│  5. 容错率:        连续{m['max_consecutive_loss']}笔亏损  │
│     → 可承受{m['error_tolerance']:.0f}笔连续亏损         │
│                                                         │
│  6. 回撤率:        {m['max_drawdown_pct']:>6.1f}%        │
│                                                         │
│  7. 稳定率(Sharpe): {m['sharpe_ratio']:>6.2f}            │
│                                                         │
│  平均总收益:       {m['avg_total_return']:>6.1f}%        │
│                                                         │
└─────────────────────────────────────────────────────────┘
""")

print("\nTOP 10 标的（按总收益排序):")
print("-" * 60)
for i, t in enumerate(result.get("top_performers", [])[:10]):
    print(f"  {i+1:>2}. {t['symbol']:<8} 收益{t['total_return_pct']:>+7.1f}%  "
          f"胜率{t['win_rate']:.0f}%  赔率{t['payoff_ratio']:.2f}  Sharpe{t['sharpe_ratio']:.2f}")

# 按板块汇总
print(f"\n{'='*70}")
print("  板块维度汇总")
print(f"{'='*70}")

sector_map = {
    "电网设备": ["600089","600406","601179","600312","000400","600875","300827","600379"],
    "电能": ["601991","600863","600900","600011"],
    "AI通信": ["300903","600183","002463","601698","000070"],
    "算力": ["603881","300608","688500","002421"],
    "液冷": ["002272","002892"],
}
for sector, syms in sector_map.items():
    sec_results = [r for r in result.get("all_results", []) if r["symbol"] in syms]
    if sec_results:
        avg_ret = sum(r.get("total_return_pct",0) for r in sec_results) / len(sec_results)
        avg_wr = sum(r.get("win_rate",0) for r in sec_results) / len(sec_results)
        avg_pf = sum(r.get("payoff_ratio",0) for r in sec_results) / len(sec_results)
        print(f"  {sector:<6}  {len(sec_results)}只  均收益{avg_ret:>+7.1f}%  均胜率{avg_wr:.0f}%  均赔率{avg_pf:.2f}")
