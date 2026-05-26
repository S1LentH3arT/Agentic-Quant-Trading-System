#!/usr/bin/env python3
"""
交易日志 — SQLite 持久化所有交易记录

用法:
    from quant_system.storage.journal import save_order, get_trade_history, get_pnl_summary

    order_id = save_order(order, status='PENDING')
    update_order_status(order_id, 'FILLED')
    trades = get_trade_history(days=30)
"""

import sqlite3
import csv
import os
from datetime import datetime, date, timedelta
from typing import Optional

from quant_system.config import get_path, ensure_dir

DB_PATH = get_path("storage", "state", "trades.db")


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = _connect()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            action TEXT NOT NULL CHECK(action IN ('BUY', 'SELL')),
            symbol TEXT NOT NULL,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            lots INTEGER NOT NULL,
            capital REAL NOT NULL,
            score INTEGER DEFAULT 0,
            a1x REAL DEFAULT 0,
            a1x_dir TEXT DEFAULT '',
            box_pos REAL DEFAULT 0,
            reason TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING'
                CHECK(status IN ('PENDING', 'FILLED', 'PARTIAL', 'CANCELLED', 'REJECTED')),
            filled_price REAL,
            filled_lots INTEGER DEFAULT 0,
            filled_at TEXT,
            sync_at TEXT
        );

        CREATE TABLE IF NOT EXISTS daily_snapshot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL UNIQUE,
            total_asset REAL,
            available_cash REAL,
            market_value REAL,
            position_count INTEGER DEFAULT 0,
            daily_pnl REAL DEFAULT 0,
            daily_pnl_pct REAL DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS position_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER REFERENCES orders(id),
            symbol TEXT NOT NULL,
            cost REAL,
            price REAL,
            lots INTEGER,
            pnl REAL,
            pnl_pct REAL,
            recorded_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at);
        CREATE INDEX IF NOT EXISTS idx_orders_symbol ON orders(symbol);
        CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
        CREATE INDEX IF NOT EXISTS idx_snapshot_date ON daily_snapshot(date);
    """)
    conn.commit()
    conn.close()


# ── 写入 ──

def save_order(order, status: str = 'PENDING') -> int:
    init_db()
    conn = _connect()
    try:
        cur = conn.execute("""
            INSERT INTO orders (created_at, action, symbol, name, price, lots,
                                capital, score, a1x, a1x_dir, box_pos, reason, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            order.timestamp if hasattr(order, 'timestamp') else datetime.now().isoformat(),
            order.action, order.symbol, order.name, order.price, order.lots,
            order.capital, getattr(order, 'score', 0), getattr(order, 'a1x', 0),
            getattr(order, 'a1x_dir', ''), getattr(order, 'box_pos', 0),
            order.reason, status,
        ))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def save_order_raw(action: str, symbol: str, name: str, price: float,
                   lots: int, capital: float, reason: str,
                   status: str = 'PENDING', score: int = 0) -> int:
    init_db()
    conn = _connect()
    try:
        cur = conn.execute("""
            INSERT INTO orders (created_at, action, symbol, name, price, lots,
                                capital, score, reason, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(), action, symbol, name, price, lots,
            capital, score, reason, status,
        ))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_order_status(order_id: int, status: str,
                        filled_price: Optional[float] = None,
                        filled_lots: int = 0):
    conn = _connect()
    try:
        fields = ["status = ?", "sync_at = ?"]
        values = [status, datetime.now().isoformat()]
        if filled_price is not None:
            fields.append("filled_price = ?"); values.append(filled_price)
        if filled_lots > 0:
            fields.append("filled_lots = ?"); values.append(filled_lots)
        if status in ('FILLED', 'PARTIAL'):
            fields.append("filled_at = ?"); values.append(datetime.now().isoformat())
        values.append(order_id)
        conn.execute(f"UPDATE orders SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()
    finally:
        conn.close()


def record_daily_snapshot():
    try:
        from quant_system.execution.broker import get_account, get_positions
        acct = get_account()
        positions = get_positions()
    except Exception:
        return

    today = date.today().isoformat()
    daily_pnl = 0.0
    daily_pnl_pct = 0.0
    prev = _get_latest_snapshot()
    if prev:
        prev_total = prev['total_asset']
        if prev_total > 0:
            daily_pnl = acct.get('total', 0) - prev_total
            daily_pnl_pct = daily_pnl / prev_total * 100

    conn = _connect()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO daily_snapshot
                (date, total_asset, available_cash, market_value,
                 position_count, daily_pnl, daily_pnl_pct, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            today, acct.get('total', 0), acct.get('available', 0),
            acct.get('market_value', 0), len(positions),
            round(daily_pnl, 2), round(daily_pnl_pct, 4),
            datetime.now().isoformat(),
        ))
        conn.commit()
    finally:
        conn.close()


def _get_latest_snapshot() -> Optional[dict]:
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM daily_snapshot ORDER BY date DESC LIMIT 1").fetchone()
        return dict(row) if row else None
    except Exception:
        return None
    finally:
        conn.close()


# ── 查询 ──

def get_trade_history(days: int = 30) -> list[dict]:
    since = (datetime.now() - timedelta(days=days)).isoformat()
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM orders WHERE created_at >= ? ORDER BY created_at DESC",
            (since,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_open_orders() -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM orders WHERE status IN ('PENDING', 'PARTIAL') ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_pnl_summary(days: int = 30) -> dict:
    since = (datetime.now() - timedelta(days=days)).isoformat()
    conn = _connect()
    try:
        row = conn.execute("""
            SELECT
                COUNT(*) as total_trades,
                SUM(CASE WHEN action = 'BUY' THEN 1 ELSE 0 END) as buys,
                SUM(CASE WHEN action = 'SELL' THEN 1 ELSE 0 END) as sells,
                SUM(CASE WHEN action = 'SELL' THEN capital ELSE 0 END) as total_sell_capital,
                SUM(CASE WHEN action = 'BUY' THEN capital ELSE 0 END) as total_buy_capital
            FROM orders WHERE created_at >= ? AND status = 'FILLED'
        """, (since,)).fetchone()
        return {
            'period_days': days, 'total_trades': row['total_trades'] or 0,
            'buys': row['buys'] or 0, 'sells': row['sells'] or 0,
            'realized_pnl': round((row['total_sell_capital'] or 0) - (row['total_buy_capital'] or 0), 2),
        }
    finally:
        conn.close()


def get_trades_by_symbol(symbol: str, days: int = 90) -> list[dict]:
    since = (datetime.now() - timedelta(days=days)).isoformat()
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM orders WHERE symbol = ? AND created_at >= ? ORDER BY created_at DESC",
            (symbol, since)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def export_trades_csv(filepath: Optional[str] = None) -> str:
    if filepath is None:
        filepath = get_path("storage", "state", "trades_export.csv")
    conn = _connect()
    try:
        rows = conn.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()
        if not rows:
            return filepath
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows([dict(r) for r in rows])
        return filepath
    finally:
        conn.close()


def get_trade_stats(days: int = 90) -> dict:
    since = (datetime.now() - timedelta(days=days)).isoformat()
    conn = _connect()
    try:
        freq = conn.execute("""
            SELECT date(created_at) as trade_date, COUNT(*) as cnt
            FROM orders WHERE created_at >= ?
            GROUP BY trade_date ORDER BY trade_date
        """, (since,)).fetchall()
        total_days = len(freq)
        total_trades = sum(r['cnt'] for r in freq)
        return {
            'period_days': days, 'trade_days': total_days,
            'total_trades': total_trades,
            'avg_trades_per_day': round(total_trades / max(total_days, 1), 1),
        }
    finally:
        conn.close()


init_db()
