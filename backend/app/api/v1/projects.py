# -*- coding: utf-8 -*-
# @File    : projects.py
# @Desc    : 项目、成员、归档和概览计数
# @Author  : xuetang-api
# @Date    : 2026-11-13
# @Update  : 2026-11-13 初始化项目管理

"""项目管理。"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.auth import client_ip
from app.auth.principal import CurrentUser
from app.common.ids import new_public_id
from app.core.deps import get_active_user, require_permissions
from app.core.exceptions import AppError
from app.core.response import ok
from app.db.session import get_db
from app.models.auth import SysRole, SysUser
from app.models.platform import ExecTask, TestReport
from app.models.project import Project, ProjectMember, ProjectSetting
from app.models.testing import ApiCase, ApiDefinition, Scenario
from app.services.audit import write_audit
from app.services.guard import ensure_project_writable, get_visible_project, visible_project_ids

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectIn(BaseModel):
    """创建项目。"""

    name: str = Field(min_length=1, max_length=128)
    code: str = Field(min_length=2, max_length=64)
    description: str = ""


class ProjectUpdate(BaseModel):
    """修改项目名称和描述。编码创建后不变。"""

    name: str = Field(min_length=1, max_length=128)
    description: str = ""


class MemberIn(BaseModel):
    """添加或调整项目成员。"""

    user_id: int
    role_code: str


def _dump(project: Project) -> dict:
    return {
        "id": project.id,
        "public_id": project.public_id,
        "name": project.name,
        "code": project.code,
        "description": project.description,
        "status": project.status,
    }


def _role(db: Session, code: str) -> SysRole:
    role = db.query(SysRole).filter(SysRole.code == code).one_or_none()
    if role is None:
        raise AppError("角色不存在", 4040, 404)
    return role


@router.get("")
def list_projects(user: CurrentUser = Depends(get_active_user), db: Session = Depends(get_db)):
    """当前用户可见的项目。"""
    query = db.query(Project)
    allowed = visible_project_ids(db, user)
    if allowed is not None:
        query = query.filter(Project.id.in_(allowed or {-1}))
    rows = query.order_by(Project.id.asc()).all()
    return ok([_dump(item) for item in rows])


@router.post("")
def create_project(
    body: ProjectIn,
    request: Request,
    user: CurrentUser = Depends(get_active_user),
    db: Session = Depends(get_db),
):
    """创建项目，并把当前用户加为项目管理员。"""
    if db.query(Project).filter(Project.code == body.code).one_or_none():
        raise AppError("项目标识已存在", 4090, 409)
    project = Project(
        public_id=new_public_id("PRJ_"),
        name=body.name,
        code=body.code,
        description=body.description,
        status="normal",
    )
    db.add(project)
    db.flush()
    db.add(ProjectSetting(project_id=project.id, retry_times=0, report_retention_days=90, concurrency_quota=10))
    db.add(ProjectMember(project_id=project.id, user_id=user.id, role_id=_role(db, "project_admin").id))
    write_audit(db, user.id, "project", "create", f"创建项目 {project.code}", client_ip(request), project.id)
    db.commit()
    return ok(_dump(project))


@router.get("/{public_id}")
def get_project(public_id: str, user: CurrentUser = Depends(get_active_user), db: Session = Depends(get_db)):
    """项目详情。"""
    return ok(_dump(get_visible_project(db, user, public_id)))


@router.put("/{public_id}")
def update_project(
    public_id: str,
    body: ProjectUpdate,
    request: Request,
    user: CurrentUser = Depends(get_active_user),
    db: Session = Depends(get_db),
):
    """修改名称和描述。归档项目拒绝写入。"""
    project = get_visible_project(db, user, public_id, writable=True)
    project.name = body.name
    project.description = body.description
    write_audit(db, user.id, "project", "update", f"更新项目 {project.code}", client_ip(request), project.id)
    db.commit()
    return ok(_dump(project))


@router.post("/{public_id}/archive")
def archive_project(
    public_id: str,
    request: Request,
    user: CurrentUser = Depends(require_permissions("project:archive")),
    db: Session = Depends(get_db),
):
    """归档后只读。"""
    project = get_visible_project(db, user, public_id)
    project.status = "archived"
    write_audit(db, user.id, "project", "archive", f"归档项目 {project.code}", client_ip(request), project.id)
    db.commit()
    return ok(_dump(project))


@router.post("/{public_id}/restore")
def restore_project(
    public_id: str,
    request: Request,
    user: CurrentUser = Depends(require_permissions("project:archive")),
    db: Session = Depends(get_db),
):
    """恢复为可编辑。"""
    project = get_visible_project(db, user, public_id)
    project.status = "normal"
    write_audit(db, user.id, "project", "restore", f"恢复项目 {project.code}", client_ip(request), project.id)
    db.commit()
    return ok(_dump(project))


@router.get("/{public_id}/overview")
def overview(public_id: str, user: CurrentUser = Depends(get_active_user), db: Session = Depends(get_db)):
    """接口、用例、场景、本周执行次数和通过率。没有报告时通过率为 0。"""
    project = get_visible_project(db, user, public_id)
    now = datetime.now()
    week_start = datetime(now.year, now.month, now.day) - timedelta(days=now.weekday())
    reports = (
        db.query(TestReport.pass_rate)
        .filter(TestReport.project_id == project.id, TestReport.created_at >= week_start)
        .all()
    )
    if reports:
        pass_rate = round(sum(float(item[0] or 0) for item in reports) / len(reports), 2)
    else:
        pass_rate = 0
    return ok(
        {
            "api_count": db.query(ApiDefinition).filter(ApiDefinition.project_id == project.id).count(),
            "case_count": db.query(ApiCase).filter(ApiCase.project_id == project.id).count(),
            "scenario_count": db.query(Scenario).filter(Scenario.project_id == project.id).count(),
            "week_exec_count": db.query(ExecTask).filter(ExecTask.project_id == project.id, ExecTask.created_at >= week_start).count(),
            "week_pass_rate": pass_rate,
        }
    )


@router.get("/{public_id}/members")
def list_members(public_id: str, user: CurrentUser = Depends(get_active_user), db: Session = Depends(get_db)):
    """项目成员。"""
    project = get_visible_project(db, user, public_id)
    rows = (
        db.query(ProjectMember, SysUser, SysRole)
        .join(SysUser, SysUser.id == ProjectMember.user_id)
        .join(SysRole, SysRole.id == ProjectMember.role_id)
        .filter(ProjectMember.project_id == project.id)
        .all()
    )
    return ok(
        [
            {
                "user_id": member.user_id,
                "username": account.username,
                "real_name": account.real_name,
                "role_code": role.code,
                "role_name": role.name,
            }
            for member, account, role in rows
        ]
    )


@router.post("/{public_id}/members")
def add_member(
    public_id: str,
    body: MemberIn,
    request: Request,
    user: CurrentUser = Depends(require_permissions("member:manage")),
    db: Session = Depends(get_db),
):
    """添加成员。已存在时改为修改角色。"""
    project = get_visible_project(db, user, public_id, writable=True)
    account = db.get(SysUser, body.user_id)
    if account is None:
        raise AppError("用户不存在", 4040, 404)
    role = _role(db, body.role_code)
    member = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project.id, ProjectMember.user_id == account.id)
        .one_or_none()
    )
    if member is None:
        db.add(ProjectMember(project_id=project.id, user_id=account.id, role_id=role.id))
        action = "add_member"
    else:
        member.role_id = role.id
        action = "update_member"
    write_audit(db, user.id, "project", action, f"{account.username} -> {role.code}", client_ip(request), project.id)
    db.commit()
    return ok({"user_id": account.id, "role_code": role.code})


@router.delete("/{public_id}/members/{user_id}")
def remove_member(
    public_id: str,
    user_id: int,
    request: Request,
    user: CurrentUser = Depends(require_permissions("member:manage")),
    db: Session = Depends(get_db),
):
    """移除项目成员。"""
    project = get_visible_project(db, user, public_id, writable=True)
    member = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project.id, ProjectMember.user_id == user_id)
        .one_or_none()
    )
    if member is None:
        raise AppError("成员不存在", 4040, 404)
    db.delete(member)
    write_audit(db, user.id, "project", "remove_member", f"移除用户 {user_id}", client_ip(request), project.id)
    db.commit()
    return ok({"user_id": user_id})
