import sys
sys.path.insert(0, 'F:/working-project/tdx-mcp')
sys.stdout.reconfigure(encoding='utf-8')

from indicator_engine import load_kline, calc_all_indicators, get_summary, score_stock
from chart_renderer import render_chart

# Test 600863
print('Loading 600863...')
df = load_kline('600863', count=120)
df = calc_all_indicators(df)
s = get_summary(df, '600863')

print(f'Close: {s["close"]}')
print(f'DKX: {s["DKX"]} {s["dkx_direction"]}')
print(f'A1X: {s["A1X"]} {s["a1x_direction"]}')
print(f'Box: {s["box_low"]}-{s["box_high"]} (pos {s["box_position_pct"]}%)')
print(f'Vol ratio: {s["vol_ratio"]}x (avg {s["vol_20_avg"]})')
print(f'DZT: {s["DZT"]} | ZZJC: {s["ZZJC"]}')
print(f'Strong: {s["strong_trend"]} | Weak: {s["weak_trend"]}')

sc = score_stock(df)
print(f'Score: {sc["score"]} pts')
for d in sc['details']:
    print(f'  - {d}')

print('\nRendering chart...')
path = render_chart('SSE:600863', df, 'F:/working-project/tdx-mcp/charts/600863_test.png')
print(f'Chart saved: {path}')
print('Pipeline OK.')
