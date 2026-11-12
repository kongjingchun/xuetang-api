# -*- coding: utf-8 -*-
# @File    : users.py
# @Desc    : 用户增删改查、启用禁用和重置密码
# @Author  : xuetang-api
# @Date    : 2026-11-13
# @Update  : 2026-11-13 增加用户删除，禁用改为独立接口并保留审计

"""用户管理。禁用只改状态；删除会解除关联后移除账号，并写入审计。"""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.auth import client_ip
from app.auth.principal import CurrentUser
from app.core.config import get_settings
from app.core.deps import get_active_user, require_permissions
from app.core.exceptions import AppError
from app.core.response import ok
from app.core.security import hash_password
from app.db.session import get_db
from app.models.auth import SysAuditLog, SysLoginLog, SysRole, SysUser, SysUserRole
from app.models.platform import (
    CollaborationComment,
    ExecTask,
    NotifyMessage,
    RecordTask,
    ReviewOpinion,
    ReviewOrder,
    TestRound,
)
from app.models.project import ProjectMember
from app.models.testing import ApiCase, ApiCaseVersion, DebugHistory, Scenario
from app.services.audit import write_audit

router = APIRouter(prefix="/users", tags=["users"])


class UserIn(BaseModel):
    """新建用户。"""

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    email: str | None = None
    real_name: str = ""
    role_code: str = "tester"
    status: str = "enabled"


class UserUpdate(BaseModel):
    """修改用户资料。口令走单独的重置接口。"""

    email: str | None = None
    real_name: str = ""
    role_code: str = "tester"
    status: str = "enabled"


class ResetIn(BaseModel):
    """管理员重置口令后，用户下次登录必须修改。"""

    password: str = Field(min_length=8, max_length=128)


def _role(db: Session, code: str) -> SysRole:
    role = db.query(SysRole).filter(SysRole.code == code).one_or_none()
    if role is None:
        raise AppError("角色不存在", 4040, 404)
    return role


def _assign_role(db: Session, user: SysUser, role: SysRole) -> None:
    """一个用户在阶段 1 保留一个全局角色，避免数据范围互相覆盖后难以解释。"""
    db.query(SysUserRole).filter(SysUserRole.user_id == user.id).delete()
    db.add(SysUserRole(user_id=user.id, role_id=role.id))


def _dump(user: SysUser, role_code: str, role_name: str) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "real_name": user.real_name,
        "status": user.status,
        "must_change_password": bool(user.must_change_password),
        "role_code": role_code,
        "role_name": role_name,
        "protected": user.username == get_settings().admin_username,
    }


def _role_info(db: Session, user_id: int) -> tuple[str, str]:
    """返回角色编码和中文名称。列表展示用名称，提交表单仍用编码。"""
    row = (
        db.query(SysRole.code, SysRole.name)
        .join(SysUserRole, SysUserRole.role_id == SysRole.id)
        .filter(SysUserRole.user_id == user_id)
        .first()
    )
    return (row[0], row[1]) if row else ("", "")


def _can_read_users(user: CurrentUser = Depends(get_active_user)) -> CurrentUser:
    """用户维护和项目成员维护都需要看见用户名单。"""
    if user.has("user:manage") or user.has("member:manage"):
        return user
    raise AppError("没有权限", 4030, 403)


@router.get("")
def list_users(
    user: CurrentUser = Depends(_can_read_users),
    db: Session = Depends(get_db),
):
    """用户列表。self 数据范围只能看见自己。"""
    query = db.query(SysUser)
    if user.data_scope == "self":
        query = query.filter(SysUser.id == user.id)
    rows = query.order_by(SysUser.id.asc()).limit(200).all()
    return ok([_dump(item, *_role_info(db, item.id)) for item in rows])


@router.post("")
def create_user(
    body: UserIn,
    request: Request,
    user: CurrentUser = Depends(require_permissions("user:manage")),
    db: Session = Depends(get_db),
):
    """创建用户。初始口令会要求首次登录修改。"""
    username = body.username.strip()
    if db.query(SysUser).filter(SysUser.username == username).one_or_none():
        raise AppError("用户名已存在", 4090, 409)
    if body.status not in {"enabled", "disabled"}:
        raise AppError("状态不正确", 4004)
    created = SysUser(
        username=username,
        email=body.email or None,
        real_name=body.real_name,
        password_hash=hash_password(body.password),
        status=body.status,
        must_change_password=True,
    )
    db.add(created)
    db.flush()
    role = _role(db, body.role_code)
    _assign_role(db, created, role)
    write_audit(db, user.id, "user", "create", f"创建用户 {username}", client_ip(request))
    db.commit()
    return ok(_dump(created, role.code, role.name))


@router.put("/{user_id}")
def update_user(
    user_id: int,
    body: UserUpdate,
    request: Request,
    user: CurrentUser = Depends(require_permissions("user:manage")),
    db: Session = Depends(get_db),
):
    """修改资料和状态。不能禁用当前登录用户。"""
    target = db.get(SysUser, user_id)
    if target is None:
        raise AppError("用户不存在", 4040, 404)
    if body.status not in {"enabled", "disabled"}:
        raise AppError("状态不正确", 4004)
    if target.id == user.id and body.status != "enabled":
        raise AppError("不能禁用当前用户", 4004)
    if target.username == get_settings().admin_username and body.status != "enabled":
        raise AppError("系统默认用户不能禁用", 4004)
    target.email = body.email or None
    target.real_name = body.real_name
    target.status = body.status
    role = _role(db, body.role_code)
    _assign_role(db, target, role)
    write_audit(db, user.id, "user", "update", f"更新用户 {target.username}", client_ip(request))
    db.commit()
    return ok(_dump(target, role.code, role.name))


@router.post("/{user_id}/reset-password")
def reset_password(
    user_id: int,
    body: ResetIn,
    request: Request,
    user: CurrentUser = Depends(require_permissions("user:manage")),
    db: Session = Depends(get_db),
):
    """重置口令，并要求对方下次登录修改。"""
    target = db.get(SysUser, user_id)
    if target is None:
        raise AppError("用户不存在", 4040, 404)
    target.password_hash = hash_password(body.password)
    target.must_change_password = True
    write_audit(db, user.id, "user", "reset_password", f"重置用户 {target.username} 的密码", client_ip(request))
    db.commit()
    return ok({"id": target.id, "must_change_password": True})


def _require_other_user(target: SysUser | None, operator_id: int, action: str) -> SysUser:
    """禁止操作自己。目标不存在时返回 404。"""
    if target is None:
        raise AppError("用户不存在", 4040, 404)
    if target.id == operator_id:
        raise AppError(f"不能{action}当前用户", 4004)
    return target


def _detach_user(db: Session, user_id: int) -> None:
    """去掉指向该用户的外键，否则 MySQL 会拒绝删除账号。"""
    db.query(ProjectMember).filter(ProjectMember.user_id == user_id).delete(synchronize_session=False)
    db.query(SysUserRole).filter(SysUserRole.user_id == user_id).delete(synchronize_session=False)
    nullable_refs = (
        (SysLoginLog, SysLoginLog.user_id),
        (SysAuditLog, SysAuditLog.operator_id),
        (ExecTask, ExecTask.creator_id),
        (RecordTask, RecordTask.creator_id),
        (TestRound, TestRound.executor_id),
        (ReviewOrder, ReviewOrder.creator_id),
        (ReviewOpinion, ReviewOpinion.user_id),
        (CollaborationComment, CollaborationComment.user_id),
        (NotifyMessage, NotifyMessage.user_id),
        (ApiCase, ApiCase.owner_id),
        (ApiCaseVersion, ApiCaseVersion.operator_id),
        (Scenario, Scenario.creator_id),
        (DebugHistory, DebugHistory.user_id),
    )
    for model, column in nullable_refs:
        db.query(model).filter(column == user_id).update({column: None}, synchronize_session=False)


@router.post("/{user_id}/disable")
def disable_user(
    user_id: int,
    request: Request,
    user: CurrentUser = Depends(require_permissions("user:manage")),
    db: Session = Depends(get_db),
):
    """禁用用户。账号和历史记录都保留。系统默认用户不能禁用。"""
    target = _require_other_user(db.get(SysUser, user_id), user.id, "禁用")
    if target.username == get_settings().admin_username:
        raise AppError("系统默认用户不能禁用", 4004)
    target.status = "disabled"
    write_audit(db, user.id, "user", "disable", f"禁用用户 {target.username}", client_ip(request))
    db.commit()
    return ok({"id": target.id, "status": target.status})


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    request: Request,
    user: CurrentUser = Depends(require_permissions("user:manage")),
    db: Session = Depends(get_db),
):
    """
    删除用户。

    先解除项目成员、角色和历史记录上的外键，再写审计，最后删除账号。
    不能删除自己，也不能删除最后一名系统管理员。
    """
    target = _require_other_user(db.get(SysUser, user_id), user.id, "删除")
    if target.username == get_settings().admin_username:
        raise AppError("系统默认用户不能删除", 4004)
    admin_role = db.query(SysRole).filter(SysRole.code == "system_admin").one_or_none()
    if admin_role is not None:
        is_admin = (
            db.query(SysUserRole)
            .filter(SysUserRole.role_id == admin_role.id, SysUserRole.user_id == target.id)
            .count()
        )
        admin_count = db.query(SysUserRole).filter(SysUserRole.role_id == admin_role.id).count()
        if is_admin and admin_count <= 1:
            raise AppError("不能删除最后一名系统管理员", 4004)
    username = target.username
    _detach_user(db, target.id)
    # 审计记在操作人身上，不引用即将删除的用户主键
    write_audit(db, user.id, "user", "delete", f"删除用户 {username}", client_ip(request))
    db.delete(target)
    db.commit()
    return ok({"id": user_id, "username": username})
