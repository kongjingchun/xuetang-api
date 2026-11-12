# -*- coding: utf-8 -*-
# @File    : wait_for_deps.py
# @Desc    : 容器启动时等待 MySQL 与 Redis 就绪，再执行迁移
# @Author  : xuetang-api
# @Date    : 2026-11-12
# @Update  : 2026-11-12 初始化阶段 0 骨架

"""依赖就绪等待。"""

import logging
import time

from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import engine

logger = logging.getLogger(__name__)


def wait_for_dependencies(timeout_seconds: int = 90) -> None:
    """
    轮询 MySQL 与 Redis，直到两者都可连接。

    Args:
        timeout_seconds: 最长等待秒数。

    Raises:
        TimeoutError: 超时仍不可用。异常信息只包含组件名，不包含连接串。
    """
    import redis

    settings = get_settings()
    deadline = time.time() + timeout_seconds
    pending = "mysql,redis"
    while time.time() < deadline:
        mysql_ok = False
        redis_ok = False
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            mysql_ok = True
        except Exception:
            logger.info("等待 MySQL 就绪")
        try:
            client = redis.Redis.from_url(settings.redis_url(0), socket_connect_timeout=2)
            client.ping()
            redis_ok = True
        except Exception:
            logger.info("等待 Redis 就绪")
        if mysql_ok and redis_ok:
            logger.info("MySQL 与 Redis 已就绪")
            return
        pending = ",".join(
            name for name, ok in (("mysql", mysql_ok), ("redis", redis_ok)) if not ok
        )
        time.sleep(2)
    raise TimeoutError(f"依赖在 {timeout_seconds} 秒内未就绪: {pending}")


if __name__ == "__main__":
    from app.core.logging import setup_logging
    from app.core.version_guard import assert_python_312

    assert_python_312()
    setup_logging()
    wait_for_dependencies()
