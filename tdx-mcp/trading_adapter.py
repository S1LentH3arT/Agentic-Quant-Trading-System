#!/usr/bin/env python3
"""
交易适配器 v2 — 实盘直连
easytrader → 同花顺xiadan.exe → 中金财富
系统生成指令 → 弹窗确认 → 自动下单 → 实时同步持仓
"""
import sys
import os
import ctypes
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import get_path, ensure_dir
from datetime import datetime, date
from dataclasses import dataclass, asdict
from typing import Optional

STATE_DIR = ensure_dir("tdx-mcp", "state")
ORDER_FILE = f"{STATE_DIR}/pending_order.json"
os.makedirs(STATE_DIR, exist_ok=True)

# ============================================================
# 实盘连接 (单例)
# ============================================================
_trader = None

def get_trader():
    """获取或创建 easytrader 连接"""
    global _trader
    if _trader is None:
        from easytrader import use
        _trader = use('ths')
        _trader.connect(r'C:\同花顺软件\同花顺\xiadan.exe')
    return _trader

def sync_from_live():
    """从实盘同步账户状态"""
    t = get_trader()
    try:
        balance = t.balance
    except Exception:
        balance = None
    try:
        positions = t.position
    except Exception:
        positions = None
    return balance, positions

# ============================================================
# 数据结构
# ============================================================
@dataclass
class TradeOrder:
    action: str
    symbol: str
    name: str
    price: float
    lots: int
    capital: float
    score: int
    a1x: float
    a1x_dir: str
    box_pos: float
    reason: str
    timestamp: str

# ============================================================
# 资金 & 持仓 → 从实盘读
# ============================================================
def get_account() -> dict:
    """读取实盘账户概览"""
    t = get_trader()
    try:
        b = t.balance
        if b:
            return {
                'total': float(b.get('总资产', 0)),
                'available': float(b.get('可用金额', 0)),
                'balance': float(b.get('资金余额', 0)),
                'market_value': float(b.get('股票市值', 0)),
            }
    except Exception:
        pass
    return {'total': 0, 'available': 0, 'balance': 0, 'market_value': 0}

def get_positions() -> list[dict]:
    """读取实盘持仓列表"""
    t = get_trader()
    try:
        raw = t.position
        if not raw:
            return []
        result = []
        for p in raw:
            shares = int(p.get('当前拥股', 0))
            if shares > 0:
                result.append({
                    'symbol': str(p.get('证券代码', '')),
                    'name': str(p.get('证券名称', '')),
                    'lots': shares // 100,
                    'cost': float(p.get('成本价', 0)),
                    'price': float(p.get('市价', 0)),
                    'market_value': float(p.get('市值', 0)),
                    'pnl': float(p.get('盈亏', 0)),
                    'pnl_pct': float(p.get('盈亏比例(%)', 0)),
                })
        return result
    except Exception:
        return []

def get_today_orders() -> list[dict]:
    """读取今日委托"""
    t = get_trader()
    try:
        return t.today_entrusts
    except Exception:
        return []

# ============================================================
# 下单执行 (实盘)
# ============================================================
def _confirm(title: str, msg: str) -> bool:
    """弹窗确认"""
    MB_YESNO = 4
    MB_ICONQUESTION = 32
    MB_TOPMOST = 0x40000
    result = ctypes.windll.user32.MessageBoxW(0, msg, title, MB_YESNO | MB_ICONQUESTION | MB_TOPMOST)
    return result == 6

def live_buy(symbol: str, price: float, lots: int, reason: str = "") -> bool:
    """
    实盘买入 (需确认)
    返回 True=已下单, False=用户取消
    """
    msg = (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  标的: {symbol}\n"
        f"  价格: {price:.2f} 元 (限价)\n"
        f"  手数: {lots} 手\n"
        f"  资金: {price * lots * 100:.0f} 元\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  逻辑: {reason}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  点[是]确认下单\n"
        f"  点[否]取消"
    )

    if not _confirm(f"⚡ 买入确认 — {symbol}", msg):
        print("用户取消买入")
        return False

    t = get_trader()
    try:
        t.buy(symbol, price, lots * 100)
        print(f"✓ 买入委托已提交: {symbol} {lots}手 @ {price:.2f}")
        return True
    except Exception as e:
        print(f"✗ 买入失败: {e}")
        return False

def live_sell(symbol: str, price: float, lots: int, reason: str = "") -> bool:
    """
    实盘卖出 (需确认)
    返回 True=已下单, False=用户取消
    """
    msg = (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  标的: {symbol}\n"
        f"  价格: {price:.2f} 元 (限价)\n"
        f"  手数: {lots} 手\n"
        f"  释放: {price * lots * 100:.0f} 元\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  原因: {reason}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  点[是]确认下单\n"
        f"  点[否]取消"
    )

    if not _confirm(f"🔴 卖出确认 — {symbol}", msg):
        print("用户取消卖出")
        return False

    t = get_trader()
    try:
        t.sell(symbol, price, lots * 100)
        print(f"✓ 卖出委托已提交: {symbol} {lots}手 @ {price:.2f}")
        return True
    except Exception as e:
        print(f"✗ 卖出失败: {e}")
        return False

def cancel_all_orders():
    """撤销所有委托"""
    t = get_trader()
    try:
        t.cancel_all_entrusts()
        print("✓ 全部委托已撤销")
    except Exception as e:
        print(f"✗ 撤单失败: {e}")

# ============================================================
# 指令生成 (策略端)
# ============================================================
def create_buy_order(symbol: str, name: str, price: float, score: int,
                     a1x: float, a1x_dir: str, box_pos: float,
                     reason: str) -> TradeOrder:
    """生成买入指令 (资金从实盘读取)"""
    acct = get_account()
    cash = acct['available']

    if score >= 8:
        lots = min(int(cash * 0.25 / (price * 100)), 4)
    elif score >= 7:
        lots = min(int(cash * 0.20 / (price * 100)), 3)
    elif score >= 6:
        lots = min(int(cash * 0.15 / (price * 100)), 2)
    else:
        lots = min(int(cash * 0.10 / (price * 100)), 2)
    lots = max(lots, 1)

    return TradeOrder(
        action="BUY", symbol=symbol, name=name, price=price, lots=lots,
        capital=round(price * lots * 100, 2), score=score,
        a1x=round(a1x, 2), a1x_dir=a1x_dir,
        box_pos=round(box_pos, 1), reason=reason,
        timestamp=str(datetime.now())
    )

def create_sell_order(symbol: str, name: str, price: float,
                      lots: int, reason: str) -> TradeOrder:
    return TradeOrder(
        action="SELL", symbol=symbol, name=name, price=price, lots=lots,
        capital=round(price * lots * 100, 2),
        score=0, a1x=0, a1x_dir='--', box_pos=0,
        reason=reason, timestamp=str(datetime.now())
    )

# ============================================================
# 一键执行
# ============================================================
def execute_buy(order: TradeOrder) -> bool:
    """确认并执行买入 (弹窗确认 → 实盘下单)"""
    return live_buy(order.symbol, order.price, order.lots, order.reason)

def execute_sell(order: TradeOrder) -> bool:
    """确认并执行卖出"""
    return live_sell(order.symbol, order.price, order.lots, order.reason)

# ============================================================
# 状态展示
# ============================================================
def status():
    """显示实时账户状态"""
    print("=" * 55)
    print(f"  交易系统 v2 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 55)

    # 账户
    acct = get_account()
    print(f"\n  总资产: {acct['total']:.2f} | 可用: {acct['available']:.2f} | 市值: {acct['market_value']:.2f}")

    # 持仓
    positions = get_positions()
    if positions:
        print(f"\n  持仓 ({len(positions)}只):")
        for p in positions:
            tag = '🟢' if p['pnl'] > 0 else ('🔴' if p['pnl_pct'] < -3 else '🟡')
            print(f"  {tag} {p['symbol']} {p['name']:6s} {p['lots']}手 "
                  f"成本{p['cost']:.2f} 现{p['price']:.2f} {p['pnl_pct']:+.1f}% "
                  f"市值{p['market_value']:.0f} 盈亏{p['pnl']:+.0f}")
    else:
        print("\n  持仓: 空仓")

    # 今日委托
    try:
        orders = get_today_orders()
        if orders:
            print(f"\n  今日委托 ({len(orders)}笔):")
            for o in orders:
                print(f"  {o}")
    except:
        pass

    print()

if __name__ == "__main__":
    status()
