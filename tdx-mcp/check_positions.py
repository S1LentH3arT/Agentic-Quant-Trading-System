import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')
from indicator_engine import load_kline, calc_all_indicators, get_summary, score_stock
from mootdx.quotes import StdQuotes

c = StdQuotes(host='218.6.170.47', port=7709, timeout=5)
data = c.quotes(symbol=['600863','601991','000070'])
print('=== realtime ===')
for _, r in data.iterrows():
    code = str(r.get('code',''))
    name = str(r.get('name',''))
    price = float(r.get('price',0) or 0)
    o = float(r.get('open',0) or 0)
    h = float(r.get('high',0) or 0)
    l = float(r.get('low',0) or 0)
    chg = round(float(r.get('change_pct',0) or 0), 2)
    vol = int(r.get('vol',0) or 0)
    print(f'{code} {name}: price={price} open={o} high={h} low={l} chg={chg}% vol={vol}')

print()
print('=== indicator ===')
costs = {'600863': 5.7926, '601991': 7.8701, '000070': 20.69}
for sym in ['600863','601991','000070']:
    try:
        df = load_kline(sym, count=60)
        df = calc_all_indicators(df)
        s = get_summary(df, sym)
        sc = score_stock(df)
        pnl = (s['close'] - costs[sym]) / costs[sym] * 100
        print(f'{sym}: close={s["close"]:.2f} DKX={s["DKX"]:.2f}({s["dkx_direction"]}) A1X={s["A1X"]:.2f}({s["a1x_direction"]}) box={s["box_position_pct"]:.0f}% vol={s["vol_ratio"]:.1f}x score={sc["score"]}pnl={pnl:+.1f}% DZT={s["DZT"]} ZZJC={s["ZZJC"]}')
        for d in sc['details']:
            print(f'  - {d}')
    except Exception as e:
        print(f'{sym}: ERROR {e}')
