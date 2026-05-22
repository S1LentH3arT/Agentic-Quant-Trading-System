#!/usr/bin/env python3
"""
心跳机制 — 盘中定时唤醒, 检查所有警报价位, 弹窗直到确认
"""

import sys, time, json, os, ctypes
sys.path.insert(0, 'F:/working-project/tdx-mcp')
from mootdx.quotes import StdQuotes
from datetime import datetime

# ============================================================
# 配置
# ============================================================
POSITIONS = {
    "600863": {"name": "内蒙华电", "cost": 5.7926, "lots": 4,
               "alerts": [
                   {"price": 5.15, "level": "L4", "msg": "硬止损-11%! 立即全清!"},
                   {"price": 5.42, "level": "L3", "msg": "涨停价破位! 减仓2手!"},
                   {"price": 5.96, "level": "L1", "msg": "突破前高! 可移动止盈!"},
               ]},
    "601991": {"name": "大唐发电", "cost": 7.8701, "lots": 1, "status": "待离场",
               "alerts": [
                   {"price": 7.00, "level": "L5", "msg": "止损离场! 集合竞价挂单!"},
               ]},
    "000070": {"name": "特发信息", "cost": 20.69, "lots": 1, "status": "待离场",
               "alerts": [
                   {"price": 18.42, "level": "L5", "msg": "止损离场! 集合竞价全清!"},
               ]},
}

# 盘中心跳时间点 (CST)
HEARTBEAT_TIMES = ["09:25", "09:45", "10:15", "10:45", "11:15", "13:05", "13:45", "14:15", "14:45", "14:55"]

ALERT_LOG = "F:/working-project/tdx-mcp/alerts/heartbeat_log.txt"

MB_TOPMOST = 0x40000
MB_SETFOREGROUND = 0x10000

# ============================================================
def popup(title: str, message: str, level: str = "INFO"):
    """弹窗 — 阻塞直到用户点确定"""
    prefix = {"L5": "!!! ", "L4": "!! ", "L3": "! ", "L2": "* ", "L1": ""}.get(level, "")
    flags = 0 | 64 | MB_TOPMOST | MB_SETFOREGROUND
    ctypes.windll.user32.MessageBoxW(0, prefix + message, title, flags)
    _log(f"POPUP [{level}] {title}: {message}")


def _log(msg: str):
    os.makedirs(os.path.dirname(ALERT_LOG), exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(ALERT_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")
    print(f"[{ts}] {msg}")


def check_all(client) -> list:
    """检查所有持仓的警报价位, 返回触发的警报列表"""
    triggered = []
    symbols = list(POSITIONS.keys())
    try:
        data = client.quotes(symbol=symbols)
        prices = {}
        if data is not None and hasattr(data, 'iterrows'):
            for _, r in data.iterrows():
                prices[str(r.get('code', ''))] = float(r.get('price', 0) or 0)

        for sym, cfg in POSITIONS.items():
            price = prices.get(sym, 0)
            if price == 0:
                continue
            cost = cfg["cost"]
            pnl = (price - cost) / cost * 100
            for a in cfg["alerts"]:
                hit = price <= a["price"]
                if hit:
                    triggered.append({
                        "symbol": sym, "name": cfg["name"], "price": price,
                        "alert_price": a["price"], "level": a["level"],
                        "msg": a["msg"], "pnl": round(pnl, 1),
                        "status": cfg.get("status", ""),
                    })
        return triggered
    except Exception as e:
        _log(f"check error: {e}")
        return []


def heartbeat_loop():
    """主循环 — 在心跳时间点检查并弹窗"""
    print("=" * 50)
    print("  HEARTBEAT MONITOR STARTED")
    print(f"  {len(POSITIONS)} positions | {sum(1 for c in POSITIONS.values() for _ in c['alerts'])} alerts")
    print("=" * 50)

    client = StdQuotes(host='218.6.170.47', port=7709, timeout=5)

    # 启动时初始检查
    triggered = check_all(client)
    if triggered:
        _log(f"STARTUP: {len(triggered)} alerts triggered!")
        for t in triggered:
            popup(f"{t['symbol']} {t['name']}", f"当前价{t['price']} 触发{t['alert_price']}\n{t['msg']}\n浮亏{t['pnl']}%", t['level'])

    alerted_today = set()  # 今天已经弹过的警报

    while True:
        now = datetime.now()
        time_str = now.strftime("%H:%M")
        weekday = now.weekday()

        # 仅交易日运行
        if weekday >= 5:
            _log("周末, 心跳暂停")
            time.sleep(3600)
            continue

        # 仅盘中运行 (9:00-15:10 CST = 1:00-7:10 UTC)
        hour = now.hour
        if hour < 1 or (hour >= 7 and now.minute > 10):
            _log(f"非盘中({time_str}), 心跳休眠")
            time.sleep(300)
            continue

        # 在心跳时间点检查
        if time_str in HEARTBEAT_TIMES:
            triggered = check_all(client)
            status_line = " | ".join([f"{sym}:{prices.get(sym,0):.2f}" for sym in POSITIONS]) if 'prices' in dir() else "checking..."
            _log(f"[{time_str}] scan: {len(triggered)} triggered | {status_line}")

            for t in triggered:
                key = f"{t['symbol']}_{t['alert_price']}"
                if key not in alerted_today:
                    alerted_today.add(key)
                    # 根据级别决定弹窗频率
                    if t['level'] in ('L5', 'L4'):
                        # 最高级别: 弹3次, 间隔2秒
                        for i in range(3):
                            popup(f"!!! {t['symbol']} {t['name']}",
                                  f"当前价{t['price']} 触发{t['alert_price']}\n{t['msg']}\n浮亏{t['pnl']}%",
                                  t['level'])
                            time.sleep(2)
                    else:
                        # 普通级别: 弹1次
                        popup(f"{t['symbol']} {t['name']}",
                              f"当前价{t['price']} 触发{t['alert_price']}\n{t['msg']}",
                              t['level'])

            if not triggered:
                # 整点报平安
                pos_status = []
                for sym, cfg in POSITIONS.items():
                    price = prices.get(sym, 0) if 'prices' in dir() else 0
                    if price:
                        pnl = (price - cfg['cost']) / cfg['cost'] * 100
                        pos_status.append(f"{sym}:{price}({pnl:+.1f}%)")
                _log(f"[{time_str}] all clear | {' | '.join(pos_status)}")

            # 休眠60秒避免重复触发
            time.sleep(60)

        time.sleep(10)


if __name__ == "__main__":
    heartbeat_loop()
