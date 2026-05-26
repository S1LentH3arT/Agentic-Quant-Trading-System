#!/usr/bin/env python3
"""
弹窗确认 — Windows MessageBox
宪法规约: 每笔交易必须弹窗确认，永不静默下单。
"""

import ctypes


def confirm(order: dict) -> bool:
    """
    弹窗确认交易。
    order: {symbol, action, price, lots, stop_price, reason}
    返回: True=用户确认, False=取消
    """
    MB_YESNO = 4
    MB_ICONQUESTION = 32
    MB_TOPMOST = 0x40000

    direction = "买入" if order.get("action") == "BUY" else "卖出"
    icon = "⚡" if order.get("action") == "BUY" else "🔴"

    msg = (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  {direction}: {order.get('symbol', '')}\n"
        f"  价格: {order.get('price', 0):.2f} 元\n"
        f"  手数: {order.get('lots', 0)} 手\n"
        f"  资金: {order.get('price', 0) * order.get('lots', 0) * 100:.0f} 元\n"
        f"  止损: {order.get('stop_price', 0):.2f}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  逻辑: {order.get('reason', '')}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  点[是]确认   点[否]取消"
    )

    result = ctypes.windll.user32.MessageBoxW(
        0, msg, f"{icon} {direction}确认 — {order.get('symbol', '')}",
        MB_YESNO | MB_ICONQUESTION | MB_TOPMOST
    )
    return result == 6
