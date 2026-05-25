# tdx-mcp/memory/store.py
"""记忆写入: 复盘报告 + MEMORY.md 索引维护"""
import os
from datetime import date


def save_review(symbol: str, content: str, review_dir: str, trade_date: str = None) -> str:
    """保存一份交易复盘到 reviews/ 目录。review_dir 应为 reviews/ 的绝对路径。"""
    if trade_date is None:
        trade_date = date.today().isoformat()
    os.makedirs(review_dir, exist_ok=True)
    filename = f"{trade_date}_{symbol}_review.md"
    filepath = os.path.join(review_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# 复盘: {symbol} ({trade_date})\n\n")
        f.write(content)
    return filepath


def update_index(symbol: str, filepath: str, index_path: str, sector: str = "", score: int = 0) -> None:
    """在 MEMORY.md 中追加一条索引"""
    os.makedirs(os.path.dirname(index_path), exist_ok=True)
    relative_path = os.path.relpath(filepath, os.path.dirname(index_path))
    line = f"- [{symbol} {date.today().isoformat()}]({relative_path}) — sector={sector} score={score}\n"
    with open(index_path, "a", encoding="utf-8") as f:
        f.write(line)
