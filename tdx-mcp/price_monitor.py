#!/usr/bin/env python3
"""
价格监控器 — 独立于 TradingView, 直连 TDX
精度到分, Windows 系统弹窗通知, 循环监控直到触发或手动停止
"""

import sys, time, json, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import get_path, ensure_dir
from mootdx.quotes import StdQuotes

# ============================================================
# 警报配置
# ============================================================
ALERTS = [
    {"symbol": "600863", "name": "内蒙华电", "condition": "below", "price": 5.15, "msg": "硬止损 -11%! 立即全清!"},
    {"symbol": "600863", "name": "内蒙华电", "condition": "below", "price": 5.42, "msg": "涨停价支撑破位! 减仓2手!"},
    {"symbol": "600863", "name": "内蒙华电", "condition": "above", "price": 5.70, "msg": "成本线收复! 可安心持有!"},
    {"symbol": "000070", "name": "特发信息", "condition": "below", "price": 18.42, "msg": "硬止损 -11%! 立即全清!"},
    {"symbol": "000070", "name": "特发信息", "condition": "above", "price": 21.50, "msg": "突破前高! 可移动止盈!"},
]

CHECK_INTERVAL = 10  # 秒

# ============================================================
# 通知方式
# ============================================================
def send_notification(title: str, message: str):
    """Windows MessageBox — 原生API, 100%可靠"""
    import ctypes
    MB_TOPMOST = 0x40000
    MB_SETFOREGROUND = 0x10000
    flags = 0 | 64 | MB_TOPMOST | MB_SETFOREGROUND  # MB_OK | MB_ICONINFORMATION
    ctypes.windll.user32.MessageBoxW(0, message, title, flags)
    print(f"\a*** ALERT: {title} - {message}")


def log_alert(alert: dict, price: float):
    """记录触发"""
    log_file = get_path("tdx-mcp", "alerts", "alert_log.txt")
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {alert['symbol']} {alert['name']} | {alert['condition']} {alert['price']} | actual={price} | {alert['msg']}\n"
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(line)


# ============================================================
# 主循环
# ============================================================
def monitor():
    print("=" * 60)
    print("  价格监控器 启动")
    print(f"  监控 {len(ALERTS)} 个警报 | 轮询间隔 {CHECK_INTERVAL}s")
    print("=" * 60)
    for a in ALERTS:
        print(f"  {a['symbol']} {a['name']}: {a['condition']} {a['price']}")

    client = StdQuotes(host='218.6.170.47', port=7709, timeout=5)
    triggered = set()
    all_symbols = list(set(a['symbol'] for a in ALERTS))

    try:
        while len(triggered) < len(ALERTS):
            try:
                data = client.quotes(symbol=all_symbols)
                prices = {}
                if data is not None and hasattr(data, 'iterrows'):
                    for _, r in data.iterrows():
                        prices[str(r.get('code', ''))] = float(r.get('price', 0) or 0)

                now = time.strftime('%H:%M:%S')
                status = []
                for i, a in enumerate(ALERTS):
                    if i in triggered:
                        continue
                    price = prices.get(a['symbol'], 0)
                    if price == 0:
                        continue

                    hit = False
                    if a['condition'] == 'below' and price <= a['price']:
                        hit = True
                    elif a['condition'] == 'above' and price >= a['price']:
                        hit = True

                    status.append(f"{a['symbol']}:{price:.2f}")

                    if hit:
                        triggered.add(i)
                        send_notification(f"{a['symbol']} {a['name']}", a['msg'])
                        log_alert(a, price)
                        print(f"\n*** TRIGGERED: [{now}] {a['symbol']} {a['name']} price={price} {a['condition']} {a['price']} ***")

                if status:
                    print(f"[{now}] {' | '.join(status)}", end='\r')

                time.sleep(CHECK_INTERVAL)

            except Exception as e:
                print(f"\n[WARN] {e}")
                time.sleep(CHECK_INTERVAL * 3)

    except KeyboardInterrupt:
        print("\n\n监控已停止。")

    print(f"\n触发 {len(triggered)}/{len(ALERTS)} 个警报。")


if __name__ == "__main__":
    monitor()
