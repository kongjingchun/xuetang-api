# -*- coding: utf-8 -*-
# @File    : health.py
# @Desc    : 健康检查，分别探测 MySQL 与 Redis，错误细节只写日志
# @Author  : xuetang-api
# @Date    : 2026-11-12
# @Update  : 2026-11-12 初始化阶段 0 健康检查

"""依赖健康检查。"""

import logging
import sys

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app import __version__
from app.core.response import fail, ok
from app.db.session import engine

logger = logging.getLogger(__name__)
router = APIRouter()


def _probe_mysql() -> str:
    """执行 SELECT 1。失败时返回 unavailable，不把连接串带回响应。"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        logger.exception("MySQL 健康检查失败")
        return "unavailable"


def _probe_redis() -> str:
    """探测 0 号库。失败时同样只记录日志。"""
    try:
        import redis

        from app.core.config import get_settings

        client = redis.Redis.from_url(get_settings().redis_url(0), socket_connect_timeout=2)
        client.ping()
        return "ok"
    except Exception:
        logger.exception("Redis 健康检查失败")
        return "unavailable"


@router.get("/health")
def health():
    """
    返回进程与依赖状态。

    两边都可用时 HTTP 200；任一不可用时 HTTP 503，业务码 5001。
    """
    mysql_status = _probe_mysql()
    redis_status = _probe_redis()
    healthy = mysql_status == "ok" and redis_status == "ok"
    payload = {
        "status": "ok" if healthy else "degraded",
        "mysql": mysql_status,
        "redis": redis_status,
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "version": __version__,
        "phase": 3,
    }
    if not healthy:
        return JSONResponse(status_code=503, content=fail("依赖不可用", 5001, payload))
    return ok(payload)
