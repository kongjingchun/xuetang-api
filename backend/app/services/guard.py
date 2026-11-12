# -*- coding: utf-8 -*-
# @File    : guard.py
# @Desc    : 项目是否可写、调用方能看见哪些项目
# @Author  : xuetang-api
# @Date    : 2026-11-13
# @Update  : 2026-11-13 初始化项目访问守卫

"""项目读写守卫。"""

from sqlalchemy.orm import Session

from app.auth.principal import CurrentUser
from app.core.exceptions import AppError
from app.models.project import Project, ProjectMember


def ensure_project_writable(status: str) -> None:
    """归档项目只允许查看。写接口在改数据前调用。"""
    if status == "archived":
        raise AppError("项目已归档，不能修改", 4031, 403)


def visible_project_ids(session: Session, user: CurrentUser) -> set[int] | None:
    """
    当前用户能看见的项目主键。

    Returns:
        None 表示不限制。self 和 project 都限制在成员项目内。
    """
    if user.data_scope == "all":
        return None
    rows = session.query(ProjectMember.project_id).filter(ProjectMember.user_id == user.id).all()
    return {item[0] for item in rows}


def get_visible_project(session: Session, user: CurrentUser, public_id: str, writable: bool = False) -> Project:
    """
    按对外 ID 取项目，并检查数据范围。

    Args:
        writable: 为真时归档项目直接拒绝。

    Raises:
        AppError: 项目不存在、不在可见范围，或已归档仍要写入。
    """
    project = session.query(Project).filter(Project.public_id == public_id).one_or_none()
    if project is None:
        raise AppError("项目不存在", 4040, 404)
    allowed = visible_project_ids(session, user)
    if allowed is not None and project.id not in allowed:
        raise AppError("项目不存在", 4040, 404)
    if writable:
        ensure_project_writable(project.status)
    return project
