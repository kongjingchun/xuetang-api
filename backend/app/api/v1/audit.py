# -*- coding: utf-8 -*-
# @File    : audit.py
# @Desc    : 按用户、模块、类型和时间筛选操作审计
# @Author  : xuetang-api
# @Date    : 2026-11-13
# @Update  : 2026-11-13 初始化审计查询

"""审计查询。"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.principal import CurrentUser
from app.core.deps import require_permissions
from app.core.response import ok
from app.db.session import get_db
from app.models.auth import SysAuditLog, SysUser
from app.services.guard import visible_project_ids

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
def list_audit(
    username: str | None = None,
    module: str | None = None,
    action: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    user: CurrentUser = Depends(require_permissions("audit:read")),
    db: Session = Depends(get_db),
    limit: int = Query(default=100, le=200),
):
    """
    查询审计。

    self 只看自己的操作。project 看所在项目和自己的平台级操作。all 不额外限制。
    """
    query = db.query(SysAuditLog, SysUser.username).outerjoin(SysUser, SysUser.id == SysAuditLog.operator_id)
    if user.data_scope == "self":
        query = query.filter(SysAuditLog.operator_id == user.id)
    elif user.data_scope == "project":
        ids = visible_project_ids(db, user) or set()
        query = query.filter((SysAuditLog.project_id.in_(ids or {-1})) | (SysAuditLog.operator_id == user.id))
    if username:
        query = query.filter(SysUser.username == username)
    if module:
        query = query.filter(SysAuditLog.module == module)
    if action:
        query = query.filter(SysAuditLog.action == action)
    if start:
        query = query.filter(SysAuditLog.created_at >= start)
    if end:
        query = query.filter(SysAuditLog.created_at <= end)
    rows = query.order_by(SysAuditLog.id.desc()).limit(limit).all()
    return ok(
        [
            {
                "id": item.id,
                "username": name or "",
                "project_id": item.project_id,
                "module": item.module,
                "action": item.action,
                "content": item.content,
                "ip": item.ip,
                "created_at": item.created_at.isoformat(sep=" ", timespec="seconds") if item.created_at else "",
            }
            for item, name in rows
        ]
    )
