# -*- coding: utf-8 -*-
# @File    : security.py
# @Desc    : 密码哈希。登录签发令牌在阶段 1 接入，这里只提供种子和后续登录共用的口令函数
# @Author  : xuetang-api
# @Date    : 2026-11-12
# @Update  : 2026-11-13 增加访问令牌、刷新令牌和登出黑名单

"""口令与 JWT。口令使用 bcrypt 原库，不经过 passlib。"""

import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.config import get_settings
from app.core.exceptions import AppError


def hash_password(plain: str) -> str:
    """
    生成 bcrypt 哈希。

    Args:
        plain: 明文口令。

    Returns:
        可写入 password_hash 的 ASCII 字符串。
    """
    hashed = bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """
    校验明文口令。

    Args:
        plain: 用户输入。
        hashed: 库存哈希。

    Returns:
        匹配时为 True。哈希损坏时返回 False，不向外抛底层异常。
    """
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def _encode(user_id: int, username: str, token_type: str, expires_delta: timedelta) -> str:
    """签发带 jti 的令牌。jti 用于登出后写入 Redis 黑名单。"""
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "username": username,
        "typ": token_type,
        "jti": uuid.uuid4().hex,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    return jwt.encode(payload, get_settings().jwt_secret, algorithm="HS256")


def create_access_token(user_id: int, username: str) -> str:
    """签发访问令牌，有效期取配置 jwt_expire_minutes，默认 120 分钟。"""
    minutes = get_settings().jwt_expire_minutes
    return _encode(user_id, username, "access", timedelta(minutes=minutes))


def create_refresh_token(user_id: int, username: str) -> str:
    """签发刷新令牌，固定 7 天。"""
    return _encode(user_id, username, "refresh", timedelta(days=7))


def decode_token(token: str, expected_type: str) -> dict:
    """
    校验签名、过期时间和令牌类型。

    Args:
        token: Bearer 后面的原始字符串。
        expected_type: access 或 refresh。

    Returns:
        JWT 载荷。

    Raises:
        AppError: 签名错误、过期或类型不符。
    """
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise AppError("登录已失效", 4010, 401) from exc
    if payload.get("typ") != expected_type:
        raise AppError("令牌类型不正确", 4010, 401)
    return payload
