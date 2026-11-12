# -*- coding: utf-8 -*-
# @File    : service.py
# @Desc    : 登录判定、改密和登录日志。失败结果不会记成 success
# @Author  : xuetang-api
# @Date    : 2026-11-13
# @Update  : 2026-11-13 初始化登录服务

"""登录与改密。"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.security import create_access_token, create_refresh_token, hash_password, verify_password
from app.models.auth import SysLoginLog, SysUser


def evaluate_login(user: SysUser | None, password: str) -> str:
    """
    判断这次登录能不能通过。

    Returns:
        success、failed 或 disabled。用户不存在和口令错误都是 failed，避免区分账号是否存在。
    """
    if user is None or not user.password_hash:
        return "failed"
    if not verify_password(password, user.password_hash):
        return "failed"
    if user.status != "enabled":
        return "disabled"
    return "success"


def login_log_result(outcome: str) -> str:
    """登录日志只记 success 或 failed。口令错误必须落成 failed。"""
    return "success" if outcome == "success" else "failed"


def write_login_log(
    session: Session,
    user: SysUser | None,
    username: str,
    outcome: str,
    ip: str,
    user_agent: str,
) -> None:
    """写入一条登录日志。"""
    message = {"success": "登录成功", "disabled": "账号已禁用", "failed": "用户名或密码错误"}[outcome]
    session.add(
        SysLoginLog(
            user_id=user.id if user else None,
            username=username[:64],
            ip=ip[:64],
            user_agent=user_agent[:255],
            result=login_log_result(outcome),
            message=message,
        )
    )


def issue_tokens(user: SysUser) -> dict:
    """为已通过校验的用户签发一对令牌。"""
    return {
        "access_token": create_access_token(user.id, user.username),
        "refresh_token": create_refresh_token(user.id, user.username),
        "token_type": "bearer",
        "must_change_password": bool(user.must_change_password),
    }


def change_password(session: Session, user: SysUser, old_password: str, new_password: str) -> None:
    """
    修改自己的密码。

    Raises:
        AppError: 原密码不对，或新密码太短。
    """
    if not verify_password(old_password, user.password_hash):
        raise AppError("原密码不正确", 4003)
    if len(new_password) < 8:
        raise AppError("新密码至少 8 位", 4003)
    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    user.updated_at = datetime.now()


def ensure_password_changed(must_change: bool) -> None:
    """首次登录尚未改密时，拦截除改密和登出以外的业务接口。"""
    if must_change:
        raise AppError("请先修改密码", 4032, 403)
