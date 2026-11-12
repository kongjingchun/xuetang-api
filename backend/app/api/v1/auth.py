# -*- coding: utf-8 -*-
# @File    : auth.py
# @Desc    : 登录、刷新、登出、改密、当前用户和 SSO 入口
# @Author  : xuetang-api
# @Date    : 2026-11-13
# @Update  : 2026-11-13 接入真实登录

"""认证接口。"""

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.principal import CurrentUser, load_principal
from app.auth.service import change_password, evaluate_login, issue_tokens, write_login_log
from app.auth.sso import get_adapter, list_enabled_providers
from app.core.deps import get_current_user
from app.core.exceptions import AppError
from app.core.response import ok
from app.core.security import decode_token
from app.core.tokens import deny_token, token_is_denied
from app.db.session import get_db
from app.models.auth import SysUser
from app.services.audit import write_audit

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    """账号密码登录。"""

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class RefreshIn(BaseModel):
    """用刷新令牌换新的一对令牌。"""

    refresh_token: str


class PasswordIn(BaseModel):
    """修改自己的密码。"""

    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


def client_ip(request: Request) -> str:
    """优先取反向代理传来的第一段地址。"""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client is None:
        return ""
    return request.client.host


def profile_of(user: CurrentUser) -> dict:
    """返回给前端的身份摘要，不包含口令。"""
    return {
        "id": user.id,
        "username": user.username,
        "real_name": user.real_name,
        "must_change_password": user.must_change_password,
        "permissions": sorted(user.permission_codes),
        "roles": sorted(user.role_codes),
        "data_scope": user.data_scope,
    }


def _bearer(request: Request) -> str:
    """取出已经通过依赖校验的访问令牌，用来读取 jti。"""
    header = request.headers.get("authorization", "")
    parts = header.split(" ", 1)
    if len(parts) != 2:
        raise AppError("未登录", 4010, 401)
    return parts[1].strip()


@router.post("/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    """校验口令。失败和禁用都记 failed，成功才记 success。"""
    username = body.username.strip()
    user = db.query(SysUser).filter(SysUser.username == username).one_or_none()
    outcome = evaluate_login(user, body.password)
    write_login_log(db, user, username, outcome, client_ip(request), request.headers.get("user-agent", ""))
    if outcome != "success" or user is None:
        db.commit()
        raise AppError("用户名或密码错误", 4011, 401)
    user.last_login_at = datetime.now()
    db.commit()
    principal = load_principal(db, user.id)
    return ok({**issue_tokens(user), "user": profile_of(principal)})


@router.post("/refresh")
def refresh(body: RefreshIn, db: Session = Depends(get_db)):
    """轮换刷新令牌。旧的刷新令牌立刻失效。"""
    payload = decode_token(body.refresh_token, "refresh")
    if token_is_denied(str(payload.get("jti", ""))):
        raise AppError("登录已失效", 4010, 401)
    user = db.get(SysUser, int(payload["sub"]))
    if user is None or user.status != "enabled":
        raise AppError("登录已失效", 4010, 401)
    deny_token(str(payload["jti"]), int(payload["exp"]))
    return ok(issue_tokens(user))


@router.post("/logout")
def logout(request: Request, user: CurrentUser = Depends(get_current_user)):
    """把当前访问令牌加入黑名单。尚未改密的用户也可以登出。"""
    payload = decode_token(_bearer(request), "access")
    deny_token(str(payload["jti"]), int(payload["exp"]))
    return ok({"username": user.username})


@router.put("/password")
def update_password(
    body: PasswordIn,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """修改自己的密码，并解除首次登录限制。"""
    stored = db.get(SysUser, user.id)
    if stored is None:
        raise AppError("登录已失效", 4010, 401)
    change_password(db, stored, body.old_password, body.new_password)
    write_audit(db, user.id, "user", "change_password", f"用户 {user.username} 修改了自己的密码", client_ip(request))
    db.commit()
    return ok({"must_change_password": False})


@router.get("/me")
def me(user: CurrentUser = Depends(get_current_user)):
    """返回当前身份。未改密时也允许调用，前端靠它停留在改密页。"""
    return ok(profile_of(user))


@router.get("/sso/providers")
def sso_providers(db: Session = Depends(get_db)):
    """登录页使用。没有启用的身份源时列表为空。"""
    return ok(list_enabled_providers(db))


@router.post("/sso/{protocol}/start")
def sso_start(protocol: str):
    """生成跳转地址。阶段 1 的适配器会返回未启用。"""
    url = get_adapter(protocol).build_authorize_url({}, "")
    return ok({"url": url})
