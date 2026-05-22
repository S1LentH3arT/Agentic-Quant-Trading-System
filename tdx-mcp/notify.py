#!/usr/bin/env python3
"""
Windows 系统弹窗 — 使用原生 MessageBox API, 100% 可靠
用法: python notify.py "标题" "消息内容"
"""

import sys
import ctypes

MB_OK = 0
MB_ICONINFORMATION = 64
MB_TOPMOST = 0x40000
MB_SETFOREGROUND = 0x10000


def popup(title: str, message: str):
    """Windows MessageBox — 阻塞弹窗, 用户必须点确定"""
    flags = MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND
    ctypes.windll.user32.MessageBoxW(0, message, title, flags)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python notify.py \"标题\" \"消息\"")
        sys.exit(1)
    title = sys.argv[1]
    msg = sys.argv[2]
    popup(title, msg)
    print("ok")
