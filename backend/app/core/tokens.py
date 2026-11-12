# -*- coding: utf-8 -*-
# @File    : tokens.py
# @Desc    : 把登出和轮换掉的 JWT 写入 Redis 0 号库，直到令牌原过期时间
# @Author  : xuetang-api
# @Date    : 2026-11-13
# @Update  : 2026-11-13 初始化令牌黑名单

"""JWT 黑名单。Redis 不可用时认证接口失败，避免把已登出的令牌当成有效。"""

from datetime import UTC, datetime

import redis

from app.core.config import get_settings
from app.core.exceptions import AppError


def _client() -> redis.Redis:
    """连接缓存库。socket 超时短一些，避免登录链路被挂住。"""
    return redis.Redis.from_url(get_settings().redis_url(0), socket_connect_timeout=2)


def deny_token(jti: str, exp: int) -> None:
    """
    拉黑一个令牌。

    Args:
        jti: JWT 的唯一编号。
        exp: 令牌过期时间戳。剩余时间作为 Redis TTL。

    Raises:
        AppError: Redis 不可用。
    """
    ttl = max(int(exp - datetime.now(UTC).timestamp()), 1)
    try:
        _client().setex(f"jwt:deny:{jti}", ttl, "1")
    except redis.RedisError as exc:
        raise AppError("认证服务暂不可用", 5031, 503) from exc


def token_is_denied(jti: str) -> bool:
    """
    查询令牌是否已登出。

    Raises:
        AppError: Redis 不可用。
    """
    try:
        return bool(_client().exists(f"jwt:deny:{jti}"))
    except redis.RedisError as exc:
        raise AppError("认证服务暂不可用", 5031, 503) from exc
