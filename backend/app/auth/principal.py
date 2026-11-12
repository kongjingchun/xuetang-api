# -*- coding: utf-8 -*-
# @File    : principal.py
# @Desc    : 当前登录用户及其权限码、数据范围
# @Author  : xuetang-api
# @Date    : 2026-11-13
# @Update  : 2026-11-13 初始化登录身份

"""请求内的登录身份。"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.auth import SysPermission, SysRole, SysRolePermission, SysUser, SysUserRole

_SCOPE_RANK = {"self": 1, "project": 2, "all": 3}


@dataclass
class CurrentUser:
    """一次请求里用到的身份。权限码来自用户的全部全局角色。"""

    id: int
    username: str
    real_name: str
    must_change_password: bool
    permission_codes: set[str]
    role_codes: set[str]
    data_scope: str

    def has(self, code: str) -> bool:
        """是否拥有某个权限码。"""
        return code in self.permission_codes


def load_principal(session: Session, user_id: int) -> CurrentUser:
    """
    从数据库装载用户、角色和权限。

    Args:
        session: 当前事务。
        user_id: 令牌里的用户主键。

    Raises:
        AppError: 用户不存在或已禁用。
    """
    user = session.get(SysUser, user_id)
    if user is None or user.status != "enabled":
        raise AppError("登录已失效", 4010, 401)
    roles = (
        session.query(SysRole)
        .join(SysUserRole, SysUserRole.role_id == SysRole.id)
        .filter(SysUserRole.user_id == user.id)
        .all()
    )
    scope = "self"
    codes: set[str] = set()
    role_codes: set[str] = set()
    for role in roles:
        role_codes.add(role.code)
        if _SCOPE_RANK.get(role.data_scope, 1) > _SCOPE_RANK.get(scope, 1):
            scope = role.data_scope
        rows = (
            session.query(SysPermission.code)
            .join(SysRolePermission, SysRolePermission.permission_id == SysPermission.id)
            .filter(SysRolePermission.role_id == role.id)
            .all()
        )
        codes.update(item[0] for item in rows)
    return CurrentUser(
        id=user.id,
        username=user.username,
        real_name=user.real_name,
        must_change_password=bool(user.must_change_password),
        permission_codes=codes,
        role_codes=role_codes,
        data_scope=scope,
    )
