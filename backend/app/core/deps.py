# -*- coding: utf-8 -*-
# @File    : deps.py
# @Desc    : FastAPI 依赖。登录身份在这里解析，执行调度器也只在这里绑定
# @Author  : xuetang-api
# @Date    : 2026-11-12
# @Update  : 2026-11-13 增加登录用户和权限校验

"""请求依赖。"""

from collections.abc import Callable

from fastapi import Depends, Header
from fastapi.security.utils import get_authorization_scheme_param
from sqlalchemy.orm import Session

from app.auth.principal import CurrentUser, load_principal
from app.auth.service import ensure_password_changed
from app.core.exceptions import AppError
from app.core.security import decode_token
from app.core.tokens import token_is_denied
from app.db.session import get_db
from app.execution_engine.dispatcher import ExecutionDispatcher, LocalDispatcher
from app.execution_engine.nodes import LocalNodeDirectory, NodeDirectory


def get_dispatcher() -> ExecutionDispatcher:
    """
    返回当前进程使用的执行调度器。

    阶段 4 之前，本地实现的 submit 会明确拒绝执行。
    多节点上线时只替换这里的返回值。
    """
    return LocalDispatcher()


def get_node_directory() -> NodeDirectory:
    """返回节点目录。当前固定为只认识 local 节点的实现。"""
    return LocalNodeDirectory()


def _read_bearer(authorization: str | None) -> str:
    """从 Authorization 取出访问令牌。缺少或格式不对都视为未登录。"""
    scheme, token = get_authorization_scheme_param(authorization)
    if scheme.lower() != "bearer" or not token:
        raise AppError("未登录", 4010, 401)
    return token


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> CurrentUser:
    """
    解析访问令牌并装载用户。

    已登出的 jti 会在 Redis 黑名单里被拒绝。
    这个依赖不检查是否已改密，改密和登出接口需要它。
    """
    token = _read_bearer(authorization)
    payload = decode_token(token, "access")
    if token_is_denied(str(payload.get("jti", ""))):
        raise AppError("登录已失效", 4010, 401)
    return load_principal(db, int(payload["sub"]))


def get_active_user(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """在登录有效的基础上，要求已经完成首次改密。"""
    ensure_password_changed(user.must_change_password)
    return user


def require_permissions(*codes: str) -> Callable:
    """
    生成一个权限依赖。缺少任一权限码就拒绝。

    Args:
        codes: 稳定的权限编码，例如 user:manage。
    """

    def _checker(user: CurrentUser = Depends(get_active_user)) -> CurrentUser:
        missing = [code for code in codes if not user.has(code)]
        if missing:
            raise AppError("没有权限", 4030, 403)
        return user

    return _checker
