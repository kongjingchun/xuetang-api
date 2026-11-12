# -*- coding: utf-8 -*-
# @File    : roles.py
# @Desc    : 自定义角色和权限点勾选。内置角色不能删除
# @Author  : xuetang-api
# @Date    : 2026-11-13
# @Update  : 2026-11-13 初始化角色管理

"""角色权限。"""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.auth import client_ip
from app.auth.principal import CurrentUser
from app.core.deps import get_active_user, require_permissions
from app.core.exceptions import AppError
from app.core.response import ok
from app.db.session import get_db
from app.models.auth import SysPermission, SysRole, SysRolePermission
from app.services.audit import write_audit

router = APIRouter(tags=["roles"])


class RoleIn(BaseModel):
    """新建或修改角色。"""

    name: str = Field(min_length=1, max_length=64)
    code: str = Field(min_length=1, max_length=64)
    data_scope: str = "project"
    description: str = ""
    permission_codes: list[str] = []


def _codes(db: Session, role_id: int) -> list[str]:
    rows = (
        db.query(SysPermission.code)
        .join(SysRolePermission, SysRolePermission.permission_id == SysPermission.id)
        .filter(SysRolePermission.role_id == role_id)
        .all()
    )
    return sorted(item[0] for item in rows)


def _dump(role: SysRole, codes: list[str]) -> dict:
    return {
        "id": role.id,
        "name": role.name,
        "code": role.code,
        "builtin": bool(role.builtin),
        "data_scope": role.data_scope,
        "description": role.description,
        "permission_codes": codes,
    }


def _replace_permissions(db: Session, role: SysRole, codes: list[str]) -> None:
    """按编码重写角色权限。未知编码直接拒绝，避免写进脏数据。"""
    unique_codes = sorted(set(codes))
    rows = db.query(SysPermission).filter(SysPermission.code.in_(unique_codes)).all() if unique_codes else []
    found = {row.code: row for row in rows}
    missing = [code for code in unique_codes if code not in found]
    if missing:
        raise AppError("权限点不存在", 4040, 404)
    db.query(SysRolePermission).filter(SysRolePermission.role_id == role.id).delete()
    for code in unique_codes:
        db.add(SysRolePermission(role_id=role.id, permission_id=found[code].id))


@router.get("/permissions")
def list_permissions(user: CurrentUser = Depends(get_active_user), db: Session = Depends(get_db)):
    """权限点清单，供角色勾选。登录用户都可以读，改角色另有权限。"""
    del user
    rows = db.query(SysPermission).order_by(SysPermission.sort.asc(), SysPermission.id.asc()).all()
    return ok(
        [{"id": row.id, "name": row.name, "code": row.code, "type": row.type, "parent_id": row.parent_id} for row in rows]
    )


def _can_read_roles(user: CurrentUser = Depends(get_active_user)) -> CurrentUser:
    """创建用户时也要能选择角色，所以用户维护权限可以读取角色列表。"""
    if user.has("role:manage") or user.has("user:manage"):
        return user
    raise AppError("没有权限", 4030, 403)


@router.get("/roles")
def list_roles(
    user: CurrentUser = Depends(_can_read_roles),
    db: Session = Depends(get_db),
):
    """角色列表。"""
    del user
    rows = db.query(SysRole).order_by(SysRole.id.asc()).all()
    return ok([_dump(row, _codes(db, row.id)) for row in rows])


@router.post("/roles")
def create_role(
    body: RoleIn,
    request: Request,
    user: CurrentUser = Depends(require_permissions("role:manage")),
    db: Session = Depends(get_db),
):
    """创建自定义角色。"""
    if body.data_scope not in {"all", "project", "self"}:
        raise AppError("数据范围不正确", 4004)
    if db.query(SysRole).filter(SysRole.code == body.code).one_or_none():
        raise AppError("角色编码已存在", 4090, 409)
    role = SysRole(
        name=body.name,
        code=body.code,
        builtin=False,
        data_scope=body.data_scope,
        description=body.description,
    )
    db.add(role)
    db.flush()
    _replace_permissions(db, role, body.permission_codes)
    write_audit(db, user.id, "role", "create", f"创建角色 {role.code}", client_ip(request))
    db.commit()
    return ok(_dump(role, body.permission_codes))


@router.put("/roles/{role_id}")
def update_role(
    role_id: int,
    body: RoleIn,
    request: Request,
    user: CurrentUser = Depends(require_permissions("role:manage")),
    db: Session = Depends(get_db),
):
    """修改角色。内置角色可以改权限，不能改编码。"""
    role = db.get(SysRole, role_id)
    if role is None:
        raise AppError("角色不存在", 4040, 404)
    if body.data_scope not in {"all", "project", "self"}:
        raise AppError("数据范围不正确", 4004)
    if role.builtin and body.code != role.code:
        raise AppError("内置角色不能修改编码", 4004)
    role.name = body.name
    role.code = body.code
    role.data_scope = body.data_scope
    role.description = body.description
    _replace_permissions(db, role, body.permission_codes)
    write_audit(db, user.id, "role", "update", f"更新角色 {role.code}", client_ip(request))
    db.commit()
    return ok(_dump(role, sorted(set(body.permission_codes))))


@router.delete("/roles/{role_id}")
def delete_role(
    role_id: int,
    request: Request,
    user: CurrentUser = Depends(require_permissions("role:manage")),
    db: Session = Depends(get_db),
):
    """删除自定义角色。内置四种角色不可删除。"""
    role = db.get(SysRole, role_id)
    if role is None:
        raise AppError("角色不存在", 4040, 404)
    if role.builtin:
        raise AppError("系统默认角色不能删除", 4004)
    name = role.name
    db.query(SysRolePermission).filter(SysRolePermission.role_id == role.id).delete()
    write_audit(db, user.id, "role", "delete", f"删除角色 {name}", client_ip(request))
    db.delete(role)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError("角色仍被用户或项目成员使用，不能删除", 4090, 409)
    return ok({"id": role_id})
