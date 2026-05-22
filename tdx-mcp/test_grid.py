import sys
sys.path.insert(0, 'F:/working-project/tdx-mcp')
sys.stdout.reconfigure(encoding='utf-8')

from chart_renderer import render_sector_grid, render_chart
from indicator_engine import load_kline, calc_all_indicators, get_summary

# Test sector grid: power grid equipment
grid_symbols = ['600089','600406','601179','600312','000400','600875','300827','600379']
print('Rendering grid...')
path = render_sector_grid(grid_symbols, '电网设备', 'F:/working-project/tdx-mcp/charts/grid_test.png')
print(f'Grid saved: {path}')

# Test individual chart for 601991
print('\nRendering 601991...')
df = load_kline('601991', count=120)
path = render_chart('SSE:601991', df, 'F:/working-project/tdx-mcp/charts/601991_test.png')
print(f'Chart saved: {path}')

print('\nAll tests OK.')
