#!/usr/bin/env python3
"""
连接管理 — 通用重连 & 指数退避重试

用法:
    from connection import ConnectionManager, retry

    # 长连接: 自动健康检查 + 断线重建
    conn = ConnectionManager(
        name="easytrader",
        factory=lambda: easytrader.use('ths').connect(r'C:\同花顺...'),
        health_check=lambda t: t.balance is not None,
    )
    trader = conn.get()

    # 短连接: 装饰器自动重试
    @retry(max_attempts=3, backoff_base=2)
    def fetch_data():
        return ak.stock_hot_rank_em()
"""

import time
import functools
import logging
from typing import Callable, Optional, Any

logger = logging.getLogger("connection")


# ============================================================
# 指数退避重试装饰器
# ============================================================

def retry(
    max_attempts: int = 3,
    backoff_base: float = 2.0,
    exceptions: tuple = (Exception,),
    on_retry: Optional[Callable] = None,
):
    """
    指数退避重试装饰器

    延迟序列: backoff_base → backoff_base² → backoff_base³ → ...

    Args:
        max_attempts: 最大尝试次数 (含首次)
        backoff_base: 退避基数 (秒), 默认 2s → 4s → 8s
        exceptions: 触发重试的异常类型
        on_retry: 重试时的回调 (exception, attempt, delay) -> None
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt < max_attempts:
                        delay = backoff_base ** attempt
                        logger.warning(
                            "%s 第 %d/%d 次失败: %s — %.1fs 后重试",
                            func.__name__, attempt, max_attempts, e, delay,
                        )
                        if on_retry:
                            on_retry(e, attempt, delay)
                        time.sleep(delay)
                    else:
                        logger.error(
                            "%s 全部 %d 次尝试均失败: %s",
                            func.__name__, max_attempts, e,
                        )
            raise last_exc
        return wrapper
    return decorator


# ============================================================
# ConnectionManager — 有状态长连接管理
# ============================================================

class ConnectionManager:
    """
    带自动重连的连接管理器

    每次调用 get() 时:
      1. 检查连接是否存在
      2. 如果存在, 运行 health_check
      3. 如果健康检查失败, 重建连接 (最多 max_retries 次)
      4. 返回可用连接

    Usage:
        conn_mgr = ConnectionManager(
            name="mootdx",
            factory=lambda: StdQuotes(host='218.6.170.47', port=7709, timeout=5),
            health_check=lambda c: c is not None,
        )
        client = conn_mgr.get()
    """

    def __init__(
        self,
        name: str,
        factory: Callable,
        health_check: Optional[Callable[[Any], bool]] = None,
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ):
        self.name = name
        self._factory = factory
        self._health_check = health_check or (lambda c: c is not None)
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._conn: Any = None
        self._failure_count = 0

    @property
    def failure_count(self) -> int:
        return self._failure_count

    def get(self) -> Any:
        """获取连接, 必要时重建"""
        if self._conn is not None and self._health_check(self._conn):
            return self._conn

        return self._reconnect()

    def reset(self):
        """强制丢弃当前连接, 下次 get() 时重建"""
        logger.info("[%s] 强制重置连接", self.name)
        self._conn = None

    def is_healthy(self) -> bool:
        """检查连接是否健康"""
        return self._conn is not None and self._health_check(self._conn)

    def _reconnect(self) -> Any:
        """尝试重建连接, 最多 max_retries 次"""
        for attempt in range(1, self._max_retries + 1):
            try:
                logger.info("[%s] 正在连接... (第 %d/%d 次)",
                            self.name, attempt, self._max_retries)
                self._conn = self._factory()
                if self._health_check(self._conn):
                    logger.info("[%s] 连接成功", self.name)
                    self._failure_count = 0
                    return self._conn
                else:
                    logger.warning("[%s] 连接建立但健康检查失败", self.name)
            except Exception as e:
                logger.warning("[%s] 连接失败 (第 %d/%d 次): %s",
                               self.name, attempt, self._max_retries, e)

            if attempt < self._max_retries:
                logger.info("[%s] %.1fs 后重试...", self.name, self._retry_delay)
                time.sleep(self._retry_delay)

        # 全部重试失败
        self._failure_count += 1
        logger.error("[%s] 全部 %d 次重连均失败", self.name, self._max_retries)
        raise ConnectionError(
            f"[{self.name}] 无法连接: 已尝试 {self._max_retries} 次"
        )

    def __repr__(self) -> str:
        status = "healthy" if self.is_healthy() else "dead"
        return f"ConnectionManager({self.name}, {status}, failures={self._failure_count})"
