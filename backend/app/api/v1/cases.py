# -*- coding: utf-8 -*-
# @File    : cases.py
# @Desc    : 单接口用例的维护、版本快照和两版本对比
# @Author  : xuetang-api
# @Date    : 2026-11-13
# @Update  : 2026-11-13 初始化用例接口

"""用例。查看跟随项目可见范围，修改需要 api:manage。"""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.v1.auth import client_ip
from app.auth.principal import CurrentUser
from app.common.ids import new_public_id
from app.core.deps import get_active_user, require_permissions
from app.core.exceptions import AppError
from app.core.response import ok
from app.db.session import get_db
from app.models.auth import SysUser
from app.models.testing import ApiCase, ApiCaseVersion, ApiDefinition
from app.services.audit import write_audit
from app.services.case_diff import KEEP_UNTAGGED, diff_snapshots, versions_to_drop
from app.services.case_eval import ASSERT_TYPES, EXTRACT_TYPES, POST_TYPES, PRE_TYPES
from app.services.guard import get_visible_project
from app.services.importers import BODY_TYPES, METHODS

router = APIRouter(prefix="/projects/{public_id}", tags=["cases"])
PRIORITIES = {"P0", "P1", "P2", "P3"}


class CaseIn(BaseModel):
    """新建或保存用例。request_json 可覆盖所属接口的请求。"""

    name: str = Field(min_length=1, max_length=128)
    api_id: int | None = None
    priority: str = "P2"
    tags: str = ""
    description: str = ""
    request_json: dict = {}
    processors_json: dict = {}
    remark: str = ""


class BatchIn(BaseModel):
    """批量删除、改优先级、改标签或移动到另一个接口。"""

    action: str
    ids: list[int] = Field(min_length=1)
    priority: str | None = None
    tags: str | None = None
    api_id: int | None = None


def _priority(value: str) -> str:
    if value not in PRIORITIES:
        raise AppError("优先级只支持 P0 到 P3", 4004)
    return value


def _case(db: Session, project_id: int, case_id: int) -> ApiCase:
    row = db.get(ApiCase, case_id)
    if row is None or row.project_id != project_id:
        raise AppError("用例不存在", 4040, 404)
    return row


def _api(db: Session, project_id: int, api_id: int | None) -> ApiDefinition | None:
    if api_id is None:
        return None
    row = db.get(ApiDefinition, api_id)
    if row is None or row.project_id != project_id:
        raise AppError("接口不存在", 4040, 404)
    return row


def _normalize_request(raw: dict) -> dict:
    """用例请求可以只覆盖一部分。方法为空表示沿用接口定义。"""
    method = str(raw.get("method") or "").upper()
    if method and method not in METHODS:
        raise AppError("请求方法不正确", 4004)
    body = raw.get("body") if isinstance(raw.get("body"), dict) else {}
    kind = str(body.get("type") or "")
    if kind and kind not in BODY_TYPES:
        raise AppError("请求体类型不正确", 4004)
    return {
        "method": method,
        "path": str(raw.get("path") or ""),
        "query": list(raw.get("query") or []),
        "headers": list(raw.get("headers") or []),
        "path_params": list(raw.get("path_params") or []),
        "body": body if kind else {},
    }


def _normalize_processors(raw: dict) -> dict:
    """只保留已知处理器，避免把任意结构写进快照。"""
    assertions = []
    for item in raw.get("assertions") or []:
        if not isinstance(item, dict) or str(item.get("type") or "") not in ASSERT_TYPES:
            raise AppError("断言类型不正确", 4004)
        assertions.append(dict(item))
    extractors = []
    for item in raw.get("extractors") or []:
        if not isinstance(item, dict) or str(item.get("type") or "") not in EXTRACT_TYPES:
            raise AppError("提取类型不正确", 4004)
        extractors.append(dict(item))
    pre = _steps(raw.get("pre") or [], PRE_TYPES, "前置")
    post = _steps(raw.get("post") or [], POST_TYPES, "后置")
    return {"assertions": assertions, "extractors": extractors, "pre": pre, "post": post}


def _steps(items: list, allowed: set[str], label: str) -> list[dict]:
    rows = []
    for item in items:
        if not isinstance(item, dict) or str(item.get("type") or "") not in allowed:
            raise AppError(f"{label}类型不正确", 4004)
        step = dict(item)
        if step.get("type") == "wait":
            step["ms"] = min(max(int(step.get("ms") or 0), 0), 10000)
        rows.append(step)
    return rows


def _dump(row: ApiCase, api_name: str = "") -> dict:
    return {
        "id": row.id,
        "public_id": row.public_id,
        "api_id": row.api_id,
        "api_name": api_name,
        "name": row.name,
        "priority": row.priority,
        "tags": row.tags,
        "owner_id": row.owner_id,
        "description": row.description,
        "request": row.request_json or {},
        "processors": row.processors_json or {},
        "api_changed": bool(row.api_changed),
        "change": row.change_json or {},
    }


def _snapshot(row: ApiCase) -> dict:
    return {
        "name": row.name,
        "api_id": row.api_id,
        "priority": row.priority,
        "tags": row.tags,
        "description": row.description,
        "request_json": row.request_json or {},
        "processors_json": row.processors_json or {},
    }


def _write_version(db: Session, row: ApiCase, operator_id: int | None, remark: str) -> ApiCaseVersion:
    """保存即快照，并丢掉超出 30 条的未标签版本。"""
    current = db.query(func.max(ApiCaseVersion.version_no)).filter(ApiCaseVersion.case_id == row.id).scalar()
    version = ApiCaseVersion(
        case_id=row.id,
        version_no=int(current or 0) + 1,
        snapshot_json=_snapshot(row),
        remark=remark[:255],
        tagged=False,
        operator_id=operator_id,
    )
    db.add(version)
    db.flush()
    versions = (
        db.query(ApiCaseVersion)
        .filter(ApiCaseVersion.case_id == row.id)
        .order_by(ApiCaseVersion.version_no.desc())
        .all()
    )
    drop_ids = versions_to_drop([(item.id, bool(item.tagged)) for item in versions], KEEP_UNTAGGED)
    if drop_ids:
        db.query(ApiCaseVersion).filter(ApiCaseVersion.id.in_(drop_ids)).delete(synchronize_session=False)
    return version


def _apply(db: Session, project_id: int, row: ApiCase, body: CaseIn, owner_id: int | None) -> None:
    _api(db, project_id, body.api_id)
    row.api_id = body.api_id
    row.name = body.name.strip()
    row.priority = _priority(body.priority)
    row.tags = body.tags
    row.description = body.description
    row.request_json = _normalize_request(body.request_json)
    row.processors_json = _normalize_processors(body.processors_json)
    row.api_changed = False
    row.change_json = {}
    if row.owner_id is None:
        row.owner_id = owner_id


@router.get("/cases")
def list_cases(
    public_id: str,
    api_id: int | None = None,
    user: CurrentUser = Depends(get_active_user),
    db: Session = Depends(get_db),
):
    """用例列表。传入 api_id 时只看该接口，否则包含空白用例。"""
    project = get_visible_project(db, user, public_id)
    query = db.query(ApiCase).filter(ApiCase.project_id == project.id)
    if api_id is not None:
        query = query.filter(ApiCase.api_id == api_id)
    rows = query.order_by(ApiCase.id.desc()).all()
    names = {
        item.id: item.name
        for item in db.query(ApiDefinition).filter(ApiDefinition.project_id == project.id).all()
    }
    return ok([_dump(row, names.get(row.api_id or 0, "")) for row in rows])


@router.post("/cases")
def create_case(
    public_id: str,
    body: CaseIn,
    request: Request,
    user: CurrentUser = Depends(require_permissions("api:manage")),
    db: Session = Depends(get_db),
):
    """新建用例，并写下第一个版本。"""
    project = get_visible_project(db, user, public_id, writable=True)
    row = ApiCase(
        public_id=new_public_id("CASE_"),
        project_id=project.id,
        name="",
        request_json={},
        processors_json={},
        description="",
        tags="",
        change_json={},
    )
    _apply(db, project.id, row, body, user.id)
    db.add(row)
    db.flush()
    _write_version(db, row, user.id, body.remark or "创建用例")
    write_audit(db, user.id, "case", "create", f"创建用例 {row.name}", client_ip(request), project.id)
    db.commit()
    db.refresh(row)
    return ok(_dump(row))


@router.post("/cases/batch")
def batch_cases(
    public_id: str,
    body: BatchIn,
    request: Request,
    user: CurrentUser = Depends(require_permissions("api:manage")),
    db: Session = Depends(get_db),
):
    """批量删除、改优先级、改标签或移动。"""
    project = get_visible_project(db, user, public_id, writable=True)
    rows = (
        db.query(ApiCase)
        .filter(ApiCase.project_id == project.id, ApiCase.id.in_(body.ids))
        .all()
    )
    if len(rows) != len(set(body.ids)):
        raise AppError("有用例不存在", 4040, 404)
    if body.action == "delete":
        ids = [row.id for row in rows]
        db.query(ApiCaseVersion).filter(ApiCaseVersion.case_id.in_(ids)).delete(synchronize_session=False)
        for row in rows:
            db.delete(row)
    elif body.action == "priority":
        priority = _priority(body.priority or "")
        for row in rows:
            row.priority = priority
    elif body.action == "tags":
        for row in rows:
            row.tags = body.tags or ""
    elif body.action == "move":
        _api(db, project.id, body.api_id)
        for row in rows:
            row.api_id = body.api_id
    else:
        raise AppError("不支持的批量操作", 4004)
    write_audit(db, user.id, "case", body.action, f"批量{body.action} {len(rows)} 条用例", client_ip(request), project.id)
    db.commit()
    return ok({"count": len(rows)})


@router.get("/cases/{case_id}")
def get_case(
    public_id: str,
    case_id: int,
    user: CurrentUser = Depends(get_active_user),
    db: Session = Depends(get_db),
):
    """用例详情。"""
    project = get_visible_project(db, user, public_id)
    row = _case(db, project.id, case_id)
    api = _api(db, project.id, row.api_id)
    return ok(_dump(row, "" if api is None else api.name))


@router.put("/cases/{case_id}")
def update_case(
    public_id: str,
    case_id: int,
    body: CaseIn,
    request: Request,
    user: CurrentUser = Depends(require_permissions("api:manage")),
    db: Session = Depends(get_db),
):
    """保存用例。保存后清除接口变更标记，并追加一个版本。"""
    project = get_visible_project(db, user, public_id, writable=True)
    row = _case(db, project.id, case_id)
    _apply(db, project.id, row, body, user.id)
    _write_version(db, row, user.id, body.remark or "保存用例")
    write_audit(db, user.id, "case", "update", f"修改用例 {row.name}", client_ip(request), project.id)
    db.commit()
    return ok(_dump(row))


@router.delete("/cases/{case_id}")
def delete_case(
    public_id: str,
    case_id: int,
    request: Request,
    user: CurrentUser = Depends(require_permissions("api:manage")),
    db: Session = Depends(get_db),
):
    """删除用例及其全部版本。"""
    project = get_visible_project(db, user, public_id, writable=True)
    row = _case(db, project.id, case_id)
    db.query(ApiCaseVersion).filter(ApiCaseVersion.case_id == row.id).delete(synchronize_session=False)
    write_audit(db, user.id, "case", "delete", f"删除用例 {row.name}", client_ip(request), project.id)
    db.delete(row)
    db.commit()
    return ok({"id": case_id})


@router.post("/cases/{case_id}/copy")
def copy_case(
    public_id: str,
    case_id: int,
    request: Request,
    user: CurrentUser = Depends(require_permissions("api:manage")),
    db: Session = Depends(get_db),
):
    """复制用例。副本从版本 1 重新计数，不继承变更标记。"""
    project = get_visible_project(db, user, public_id, writable=True)
    source = _case(db, project.id, case_id)
    row = ApiCase(
        public_id=new_public_id("CASE_"),
        project_id=project.id,
        api_id=source.api_id,
        name=f"{source.name} 副本"[:128],
        priority=source.priority,
        tags=source.tags,
        owner_id=user.id,
        description=source.description,
        request_json=source.request_json or {},
        processors_json=source.processors_json or {},
        api_changed=False,
        change_json={},
    )
    db.add(row)
    db.flush()
    _write_version(db, row, user.id, "复制用例")
    write_audit(db, user.id, "case", "copy", f"复制用例 {source.name}", client_ip(request), project.id)
    db.commit()
    db.refresh(row)
    return ok(_dump(row))


@router.get("/cases/{case_id}/versions")
def list_versions(
    public_id: str,
    case_id: int,
    user: CurrentUser = Depends(get_active_user),
    db: Session = Depends(get_db),
):
    """版本列表，从新到旧。"""
    project = get_visible_project(db, user, public_id)
    row = _case(db, project.id, case_id)
    versions = (
        db.query(ApiCaseVersion)
        .filter(ApiCaseVersion.case_id == row.id)
        .order_by(ApiCaseVersion.version_no.desc())
        .all()
    )
    operator_ids = [item.operator_id for item in versions if item.operator_id]
    users = {}
    if operator_ids:
        users = {item.id: item.username for item in db.query(SysUser).filter(SysUser.id.in_(operator_ids)).all()}
    return ok(
        [
            {
                "id": item.id,
                "version_no": item.version_no,
                "remark": item.remark,
                "tagged": bool(item.tagged),
                "operator": users.get(item.operator_id or 0, ""),
                "created_at": item.created_at.isoformat(sep=" ", timespec="seconds") if item.created_at else "",
            }
            for item in versions
        ]
    )


@router.post("/cases/{case_id}/versions/{version_id}/tag")
def tag_version(
    public_id: str,
    case_id: int,
    version_id: int,
    user: CurrentUser = Depends(require_permissions("api:manage")),
    db: Session = Depends(get_db),
):
    """给版本打标签或取消。打过标签的版本不会被 30 条保留策略删掉。"""
    project = get_visible_project(db, user, public_id, writable=True)
    row = _case(db, project.id, case_id)
    version = _version(db, row.id, version_id)
    version.tagged = not bool(version.tagged)
    db.commit()
    return ok({"id": version.id, "tagged": bool(version.tagged)})


@router.post("/cases/{case_id}/versions/{version_id}/rollback")
def rollback_version(
    public_id: str,
    case_id: int,
    version_id: int,
    request: Request,
    user: CurrentUser = Depends(require_permissions("api:manage")),
    db: Session = Depends(get_db),
):
    """回滚到某个版本，并把它再存成一个新版本。"""
    project = get_visible_project(db, user, public_id, writable=True)
    row = _case(db, project.id, case_id)
    version = _version(db, row.id, version_id)
    snap = version.snapshot_json or {}
    row.name = str(snap.get("name") or row.name)
    row.api_id = snap.get("api_id")
    row.priority = str(snap.get("priority") or row.priority)
    row.tags = str(snap.get("tags") or "")
    row.description = str(snap.get("description") or "")
    row.request_json = snap.get("request_json") or {}
    row.processors_json = snap.get("processors_json") or {}
    row.api_changed = False
    row.change_json = {}
    _write_version(db, row, user.id, f"回滚到版本 {version.version_no}")
    write_audit(db, user.id, "case", "rollback", f"回滚用例 {row.name}", client_ip(request), project.id)
    db.commit()
    return ok(_dump(row))


@router.get("/cases/{case_id}/diff")
def diff_versions(
    public_id: str,
    case_id: int,
    left: int,
    right: int,
    user: CurrentUser = Depends(get_active_user),
    db: Session = Depends(get_db),
):
    """对比任意两个版本。left 作为旧版本。"""
    project = get_visible_project(db, user, public_id)
    row = _case(db, project.id, case_id)
    older = _version(db, row.id, left)
    newer = _version(db, row.id, right)
    return ok(
        {
            "left": older.version_no,
            "right": newer.version_no,
            "items": diff_snapshots(older.snapshot_json or {}, newer.snapshot_json or {}),
        }
    )


def _version(db: Session, case_id: int, version_id: int) -> ApiCaseVersion:
    row = db.get(ApiCaseVersion, version_id)
    if row is None or row.case_id != case_id:
        raise AppError("版本不存在", 4040, 404)
    return row
