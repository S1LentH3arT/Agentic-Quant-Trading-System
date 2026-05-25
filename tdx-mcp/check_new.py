import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')
from indicator_engine import load_kline, calc_all_indicators, get_summary, score_stock
from mootdx.quotes import StdQuotes

c = StdQuotes(host='218.6.170.47', port=7709, timeout=5)
data = c.quotes(symbol=['300069','688055'])
print('=== realtime ===')
for _, r in data.iterrows():
    print(f'{r.get("code")} {r.get("name")}: price={r.get("price")} open={r.get("open")} high={r.get("high")} low={r.get("low")} chg={round(float(r.get("change_pct",0) or 0),2)}% vol={r.get("vol")}')

print()
for sym in ['300069','688055']:
    try:
        df = load_kline(sym, count=80)
        df = calc_all_indicators(df)
        s = get_summary(df, sym)
        sc = score_stock(df)
        # last 5 bars
        print(f'--- {sym} {df.iloc[-1].get("name","")} ---')
        print(f'close={s["close"]} DKX={s["DKX"]} A1X={s["A1X"]} box={s["box_position_pct"]}% vol={s["vol_ratio"]}x score={sc["score"]} DZT={s["DZT"]} ZZJC={s["ZZJC"]}')
        print('Last 5 bars:')
        for i in range(-5, 0):
            r = df.iloc[i]
            print(f'  O={r["open"]:.2f} H={r["high"]:.2f} L={r["low"]:.2f} C={r["close"]:.2f} V={r["volume"]:.0f}')
        for d in sc['details']:
            print(f'  {d}')
    except Exception as e:
        import traceback
        print(f'{sym}: {e}')
        traceback.print_exc()
