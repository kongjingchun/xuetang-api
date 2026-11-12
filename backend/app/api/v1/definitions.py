# -*- coding: utf-8 -*-
# @File    : definitions.py
# @Desc    : 接口目录、接口定义、导入导出和 Mock 规则
# @Author  : xuetang-api
# @Date    : 2026-11-13
# @Update  : 2026-11-13 初始化定义与 Mock 维护接口

"""接口定义。访客可以查看，维护需要 api:manage。"""

import json

from fastapi import APIRouter, Depends, File, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.auth import client_ip
from app.auth.principal import CurrentUser
from app.common.ids import new_public_id
from app.core.deps import get_active_user, require_permissions
from app.core.exceptions import AppError
from app.core.response import ok
from app.db.session import get_db
from app.models.project import Environment, Project, Variable
from app.models.testing import (
    ApiCase,
    ApiDefinition,
    ApiModule,
    ApiResponseExample,
    MockLog,
    MockRule,
    Scenario,
    ScenarioModule,
)
from app.services.audit import write_audit
from app.services.exporters import export_excel, export_json
from app.services.guard import get_visible_project
from app.services.importers import BODY_TYPES, METHODS, load_document, normalize_path, parse_document
from app.common.variables import VariableValue

router = APIRouter(prefix="/projects/{public_id}", tags=["definitions"])


class ModuleIn(BaseModel):
    """新建或重命名目录。"""

    name: str = Field(min_length=1, max_length=128)
    parent_id: int | None = None


class ModulePos(BaseModel):
    """拖拽后的目录位置。"""

    id: int
    parent_id: int | None = None
    sort: int = 0


class ApiPos(BaseModel):
    """拖拽后的接口位置。"""

    id: int
    module_id: int | None = None
    sort: int = 0


class LayoutIn(BaseModel):
    """一次提交整棵树的新顺序。"""

    modules: list[ModulePos] = []
    apis: list[ApiPos] = []


class ExampleIn(BaseModel):
    """响应示例。"""

    name: str = Field(min_length=1, max_length=128)
    status_code: int = 200
    headers_json: dict = {}
    body: str = ""
    description: str = ""


class DefinitionIn(BaseModel):
    """接口定义。request_json 含 query、headers、path_params 和 body。"""

    name: str = Field(min_length=1, max_length=128)
    method: str
    path: str = Field(min_length=1, max_length=512)
    module_id: int | None = None
    tags: str = ""
    description: str = ""
    request_json: dict = {}
    examples: list[ExampleIn] = []


class MockIn(BaseModel):
    """Mock 规则。match_json.path 为空时使用关联接口的路径。"""

    name: str = Field(min_length=1, max_length=128)
    api_id: int | None = None
    priority: int = 100
    status_code: int = 200
    headers_json: dict = {}
    body: str = ""
    delay_ms: int = 0
    match_json: dict = {}
    fault_type: str | None = None
    enabled: bool = True


def _module(db: Session, project_id: int, module_id: int | None) -> ApiModule | None:
    if module_id is None:
        return None
    row = db.get(ApiModule, module_id)
    if row is None or row.project_id != project_id:
        raise AppError("目录不存在", 4040, 404)
    return row


def _definition(db: Session, project_id: int, api_id: int) -> ApiDefinition:
    row = db.get(ApiDefinition, api_id)
    if row is None or row.project_id != project_id:
        raise AppError("接口不存在", 4040, 404)
    return row


def _normalize_request(raw: dict) -> dict:
    """补齐请求结构。JSON 字符串里可以包含变量，所以不强制解析成对象。"""
    body = raw.get("body") if isinstance(raw.get("body"), dict) else {}
    kind = str(body.get("type") or "none")
    if kind not in BODY_TYPES:
        raise AppError("请求体类型不正确", 4004)
    content = body.get("content", "")
    if kind in {"form", "urlencoded"} and not isinstance(content, list):
        content = []
    if kind in {"json", "raw"} and not isinstance(content, str):
        content = json.dumps(content, ensure_ascii=False)
    if kind == "none":
        content = ""
    return {
        "query": list(raw.get("query") or []),
        "headers": list(raw.get("headers") or []),
        "path_params": list(raw.get("path_params") or []),
        "body": {"type": kind, "content": content},
    }


def _check_method(method: str) -> str:
    value = method.upper()
    if value not in METHODS:
        raise AppError("请求方法不正确", 4004)
    return value


def _dump_example(row: ApiResponseExample) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "status_code": row.status_code,
        "headers_json": row.headers_json or {},
        "body": row.body,
        "description": row.description,
    }


def _dump_api(db: Session, row: ApiDefinition, module_name: str = "", with_examples: bool = False) -> dict:
    payload = {
        "id": row.id,
        "public_id": row.public_id,
        "module_id": row.module_id,
        "module": module_name,
        "name": row.name,
        "method": row.method,
        "path": row.path,
        "tags": row.tags,
        "description": row.description,
        "request": row.request_json or {},
        "revision": row.revision,
        "sort": row.sort,
    }
    if with_examples:
        examples = (
            db.query(ApiResponseExample)
            .filter(ApiResponseExample.api_id == row.id)
            .order_by(ApiResponseExample.id.asc())
            .all()
        )
        payload["examples"] = [_dump_example(item) for item in examples]
    return payload


def _replace_examples(db: Session, api: ApiDefinition, examples: list[ExampleIn]) -> None:
    db.query(ApiResponseExample).filter(ApiResponseExample.api_id == api.id).delete(synchronize_session=False)
    for item in examples:
        db.add(
            ApiResponseExample(
                api_id=api.id,
                name=item.name.strip(),
                status_code=item.status_code,
                headers_json=item.headers_json or {},
                body=item.body,
                description=item.description,
            )
        )


def _module_names(db: Session, project_id: int) -> dict[int, str]:
    rows = db.query(ApiModule).filter(ApiModule.project_id == project_id).all()
    return {row.id: row.name for row in rows}


def _ensure_import_module(db: Session, project_id: int, name: str) -> ApiModule:
    row = (
        db.query(ApiModule)
        .filter(ApiModule.project_id == project_id, ApiModule.parent_id.is_(None), ApiModule.name == name)
        .one_or_none()
    )
    if row is not None:
        return row
    row = ApiModule(project_id=project_id, parent_id=None, name=name[:128], sort=0)
    db.add(row)
    db.flush()
    return row


def _dump_rule(row: MockRule) -> dict:
    return {
        "id": row.id,
        "api_id": row.api_id,
        "name": row.name,
        "priority": row.priority,
        "status_code": row.status_code,
        "headers_json": row.headers_json or {},
        "body": row.body,
        "delay_ms": row.delay_ms,
        "match_json": row.match_json or {},
        "fault_type": row.fault_type,
        "enabled": bool(row.enabled),
    }


def _project_layers(db: Session, project_id: int) -> dict:
    """Mock 回填只使用项目变量。加密值在发送响应时解密。"""
    rows = db.query(Variable).filter(Variable.scope == "project", Variable.scope_id == project_id).all()
    return {"project": {row.name: VariableValue(row.value, row.encrypted) for row in rows}}


@router.get("/modules")
def list_modules(public_id: str, user: CurrentUser = Depends(get_active_user), db: Session = Depends(get_db)):
    """项目下的接口目录。"""
    project = get_visible_project(db, user, public_id)
    rows = db.query(ApiModule).filter(ApiModule.project_id == project.id).order_by(ApiModule.sort.asc(), ApiModule.id.asc()).all()
    return ok(
        [{"id": row.id, "parent_id": row.parent_id, "name": row.name, "sort": row.sort} for row in rows]
    )


@router.post("/modules")
def create_module(
    public_id: str,
    body: ModuleIn,
    request: Request,
    user: CurrentUser = Depends(require_permissions("api:manage")),
    db: Session = Depends(get_db),
):
    """新建目录。"""
    project = get_visible_project(db, user, public_id, writable=True)
    _module(db, project.id, body.parent_id)
    row = ApiModule(project_id=project.id, parent_id=body.parent_id, name=body.name.strip(), sort=0)
    db.add(row)
    write_audit(db, user.id, "definition", "create_module", f"创建目录 {row.name}", client_ip(request), project.id)
    db.commit()
    db.refresh(row)
    return ok({"id": row.id, "parent_id": row.parent_id, "name": row.name, "sort": row.sort})


@router.put("/modules/{module_id}")
def update_module(
    public_id: str,
    module_id: int,
    body: ModuleIn,
    request: Request,
    user: CurrentUser = Depends(require_permissions("api:manage")),
    db: Session = Depends(get_db),
):
    """修改目录名称和父级。"""
    project = get_visible_project(db, user, public_id, writable=True)
    row = _module(db, project.id, module_id)
    if body.parent_id == row.id:
        raise AppError("目录不能放到自己下面", 4004)
    _module(db, project.id, body.parent_id)
    _reject_cycle(db, project.id, row.id, body.parent_id)
    row.name = body.name.strip()
    row.parent_id = body.parent_id
    write_audit(db, user.id, "definition", "update_module", f"修改目录 {row.name}", client_ip(request), project.id)
    db.commit()
    return ok({"id": row.id, "parent_id": row.parent_id, "name": row.name, "sort": row.sort})


@router.delete("/modules/{module_id}")
def delete_module(
    public_id: str,
    module_id: int,
    request: Request,
    user: CurrentUser = Depends(require_permissions("api:manage")),
    db: Session = Depends(get_db),
):
    """空目录才能删除。"""
    project = get_visible_project(db, user, public_id, writable=True)
    row = _module(db, project.id, module_id)
    children = db.query(ApiModule).filter(ApiModule.parent_id == row.id).count()
    apis = db.query(ApiDefinition).filter(ApiDefinition.module_id == row.id).count()
    if children or apis:
        raise AppError("目录下还有子目录或接口，不能删除", 4004)
    name = row.name
    write_audit(db, user.id, "definition", "delete_module", f"删除目录 {name}", client_ip(request), project.id)
    db.delete(row)
    db.commit()
    return ok({"id": module_id})


@router.put("/definitions/layout")
def save_layout(
    public_id: str,
    body: LayoutIn,
    request: Request,
    user: CurrentUser = Depends(require_permissions("api:manage")),
    db: Session = Depends(get_db),
):
    """保存拖拽后的目录和接口顺序。"""
    project = get_visible_project(db, user, public_id, writable=True)
    for item in body.modules:
        row = _module(db, project.id, item.id)
        if item.parent_id == row.id:
            raise AppError("目录不能放到自己下面", 4004)
        _module(db, project.id, item.parent_id)
        _reject_cycle(db, project.id, row.id, item.parent_id)
        row.parent_id = item.parent_id
        row.sort = item.sort
    for item in body.apis:
        row = _definition(db, project.id, item.id)
        _module(db, project.id, item.module_id)
        row.module_id = item.module_id
        row.sort = item.sort
    write_audit(db, user.id, "definition", "layout", "调整接口目录", client_ip(request), project.id)
    db.commit()
    return ok({"modules": len(body.modules), "apis": len(body.apis)})


def _reject_cycle(db: Session, project_id: int, module_id: int, parent_id: int | None) -> None:
    """父链往上走，碰到自己就拒绝。"""
    cursor = parent_id
    seen = set()
    while cursor is not None:
        if cursor == module_id or cursor in seen:
            raise AppError("目录不能放到自己的子目录下", 4004)
        seen.add(cursor)
        parent = db.get(ApiModule, cursor)
        if parent is None or parent.project_id != project_id:
            raise AppError("目录不存在", 4040, 404)
        cursor = parent.parent_id


@router.get("/definitions")
def list_definitions(public_id: str, user: CurrentUser = Depends(get_active_user), db: Session = Depends(get_db)):
    """接口列表，不含响应示例。"""
    project = get_visible_project(db, user, public_id)
    names = _module_names(db, project.id)
    rows = (
        db.query(ApiDefinition)
        .filter(ApiDefinition.project_id == project.id)
        .order_by(ApiDefinition.sort.asc(), ApiDefinition.id.asc())
        .all()
    )
    return ok([_dump_api(db, row, names.get(row.module_id or 0, "")) for row in rows])


@router.get("/definitions/export")
def export_definitions(
    public_id: str,
    format: str = "json",
    user: CurrentUser = Depends(get_active_user),
    db: Session = Depends(get_db),
):
    """导出 JSON 或 Excel。内容以 base64 返回，避免下载接口绕过统一响应。"""
    project = get_visible_project(db, user, public_id)
    names = _module_names(db, project.id)
    rows = (
        db.query(ApiDefinition)
        .filter(ApiDefinition.project_id == project.id)
        .order_by(ApiDefinition.sort.asc(), ApiDefinition.id.asc())
        .all()
    )
    payload = [_dump_api(db, row, names.get(row.module_id or 0, "")) for row in rows]
    if format == "xlsx":
        return ok(export_excel(payload))
    if format == "json":
        return ok(export_json(payload))
    raise AppError("只支持导出 json 或 xlsx", 4004)


@router.get("/definitions/{api_id}")
def get_definition(
    public_id: str,
    api_id: int,
    user: CurrentUser = Depends(get_active_user),
    db: Session = Depends(get_db),
):
    """接口详情，带响应示例。"""
    project = get_visible_project(db, user, public_id)
    row = _definition(db, project.id, api_id)
    names = _module_names(db, project.id)
    return ok(_dump_api(db, row, names.get(row.module_id or 0, ""), with_examples=True))


@router.post("/definitions")
def create_definition(
    public_id: str,
    body: DefinitionIn,
    request: Request,
    user: CurrentUser = Depends(require_permissions("api:manage")),
    db: Session = Depends(get_db),
):
    """新建接口。"""
    project = get_visible_project(db, user, public_id, writable=True)
    row = _insert_definition(db, project, body)
    _replace_examples(db, row, body.examples)
    write_audit(db, user.id, "definition", "create", f"创建接口 {row.method} {row.path}", client_ip(request), project.id)
    db.commit()
    db.refresh(row)
    return ok(_dump_api(db, row, "", with_examples=True))


@router.put("/definitions/{api_id}")
def update_definition(
    public_id: str,
    api_id: int,
    body: DefinitionIn,
    request: Request,
    user: CurrentUser = Depends(require_permissions("api:manage")),
    db: Session = Depends(get_db),
):
    """修改接口。每次保存让 revision 加一，供后续用例标记变更。"""
    project = get_visible_project(db, user, public_id, writable=True)
    row = _definition(db, project.id, api_id)
    _apply_definition(db, project, row, body)
    row.revision += 1
    _replace_examples(db, row, body.examples)
    write_audit(db, user.id, "definition", "update", f"修改接口 {row.method} {row.path}", client_ip(request), project.id)
    db.commit()
    return ok(_dump_api(db, row, "", with_examples=True))


@router.delete("/definitions/{api_id}")
def delete_definition(
    public_id: str,
    api_id: int,
    request: Request,
    user: CurrentUser = Depends(require_permissions("api:manage")),
    db: Session = Depends(get_db),
):
    """删除接口。仍被用例引用时拒绝。"""
    project = get_visible_project(db, user, public_id, writable=True)
    row = _definition(db, project.id, api_id)
    if db.query(ApiCase).filter(ApiCase.api_id == row.id).count():
        raise AppError("接口仍被用例使用，不能删除", 4004)
    db.query(ApiResponseExample).filter(ApiResponseExample.api_id == row.id).delete(synchronize_session=False)
    db.query(MockRule).filter(MockRule.api_id == row.id).update({MockRule.api_id: None}, synchronize_session=False)
    label = f"{row.method} {row.path}"
    write_audit(db, user.id, "definition", "delete", f"删除接口 {label}", client_ip(request), project.id)
    db.delete(row)
    db.commit()
    return ok({"id": api_id})


def _insert_definition(db: Session, project: Project, body: DefinitionIn) -> ApiDefinition:
    row = ApiDefinition(
        public_id=new_public_id("API_"),
        project_id=project.id,
        revision=1,
        request_json={},
        description="",
        tags="",
        name="",
        method="GET",
        path="/",
    )
    _apply_definition(db, project, row, body)
    db.add(row)
    db.flush()
    return row


def _apply_definition(db: Session, project: Project, row: ApiDefinition, body: DefinitionIn) -> None:
    _module(db, project.id, body.module_id)
    row.module_id = body.module_id
    row.name = body.name.strip()
    row.method = _check_method(body.method)
    row.path = normalize_path(body.path)
    row.tags = body.tags
    row.description = body.description
    row.request_json = _normalize_request(body.request_json)


@router.post("/definitions/import")
async def import_definitions(
    public_id: str,
    request: Request,
    file: UploadFile = File(...),
    user: CurrentUser = Depends(require_permissions("api:manage")),
    db: Session = Depends(get_db),
):
    """导入 OpenAPI、Postman 或 HAR。相同方法加路径会更新已有接口。"""
    project = get_visible_project(db, user, public_id, writable=True)
    raw = await file.read()
    if len(raw) > 2 * 1024 * 1024:
        raise AppError("导入文件不能超过 2MB", 4004)
    document = load_document(raw, file.filename or "")
    items = parse_document(document)
    created, updated = _upsert_imported(db, project, items)
    write_audit(
        db,
        user.id,
        "definition",
        "import",
        f"导入接口，新增 {created}，更新 {updated}",
        client_ip(request),
        project.id,
    )
    db.commit()
    return ok({"created": created, "updated": updated})


def _upsert_imported(db: Session, project: Project, items: list[dict]) -> tuple[int, int]:
    created = 0
    updated = 0
    for item in items:
        module = _ensure_import_module(db, project.id, str(item.get("module") or "导入")[:128])
        path = normalize_path(str(item["path"]))
        method = _check_method(str(item["method"]))
        row = (
            db.query(ApiDefinition)
            .filter(ApiDefinition.project_id == project.id, ApiDefinition.method == method, ApiDefinition.path == path)
            .one_or_none()
        )
        payload = DefinitionIn(
            name=str(item["name"])[:128],
            method=method,
            path=path,
            module_id=module.id,
            description=str(item.get("description") or ""),
            request_json=item.get("request") or {},
            examples=[ExampleIn(**example) for example in item.get("examples") or []],
        )
        if row is None:
            row = _insert_definition(db, project, payload)
            created += 1
        else:
            _apply_definition(db, project, row, payload)
            row.revision += 1
            updated += 1
        if payload.examples:
            _replace_examples(db, row, payload.examples)
    return created, updated


@router.get("/mock-rules/stats")
def mock_stats(public_id: str, user: CurrentUser = Depends(get_active_user), db: Session = Depends(get_db)):
    """调用次数。未命中的日志 rule_id 为空。"""
    project = get_visible_project(db, user, public_id)
    rows = db.query(MockLog).filter(MockLog.project_id == project.id).all()
    hits: dict[int, int] = {}
    missed = 0
    for row in rows:
        if row.rule_id is None:
            missed += 1
        else:
            hits[row.rule_id] = hits.get(row.rule_id, 0) + 1
    return ok({"total": len(rows), "missed": missed, "hits": {str(key): value for key, value in hits.items()}})


@router.get("/mock-rules")
def list_mock_rules(public_id: str, user: CurrentUser = Depends(get_active_user), db: Session = Depends(get_db)):
    """项目 Mock 规则，按优先级排列。"""
    project = get_visible_project(db, user, public_id)
    rows = (
        db.query(MockRule)
        .filter(MockRule.project_id == project.id)
        .order_by(MockRule.priority.asc(), MockRule.id.asc())
        .all()
    )
    return ok([_dump_rule(row) for row in rows])


@router.post("/mock-rules")
def create_mock_rule(
    public_id: str,
    body: MockIn,
    request: Request,
    user: CurrentUser = Depends(require_permissions("api:manage")),
    db: Session = Depends(get_db),
):
    """新建 Mock 规则。"""
    project = get_visible_project(db, user, public_id, writable=True)
    row = MockRule(project_id=project.id, name="", body="", status_code=200, priority=100)
    _apply_rule(db, project, row, body)
    db.add(row)
    write_audit(db, user.id, "mock", "create", f"创建 Mock 规则 {row.name}", client_ip(request), project.id)
    db.commit()
    db.refresh(row)
    return ok(_dump_rule(row))


@router.put("/mock-rules/{rule_id}")
def update_mock_rule(
    public_id: str,
    rule_id: int,
    body: MockIn,
    request: Request,
    user: CurrentUser = Depends(require_permissions("api:manage")),
    db: Session = Depends(get_db),
):
    """修改 Mock 规则。"""
    project = get_visible_project(db, user, public_id, writable=True)
    row = _rule(db, project.id, rule_id)
    _apply_rule(db, project, row, body)
    write_audit(db, user.id, "mock", "update", f"修改 Mock 规则 {row.name}", client_ip(request), project.id)
    db.commit()
    return ok(_dump_rule(row))


@router.delete("/mock-rules/{rule_id}")
def delete_mock_rule(
    public_id: str,
    rule_id: int,
    request: Request,
    user: CurrentUser = Depends(require_permissions("api:manage")),
    db: Session = Depends(get_db),
):
    """删除 Mock 规则。调用日志保留。"""
    project = get_visible_project(db, user, public_id, writable=True)
    row = _rule(db, project.id, rule_id)
    name = row.name
    db.query(MockLog).filter(MockLog.rule_id == row.id).update({MockLog.rule_id: None}, synchronize_session=False)
    write_audit(db, user.id, "mock", "delete", f"删除 Mock 规则 {name}", client_ip(request), project.id)
    db.delete(row)
    db.commit()
    return ok({"id": rule_id})


def _rule(db: Session, project_id: int, rule_id: int) -> MockRule:
    row = db.get(MockRule, rule_id)
    if row is None or row.project_id != project_id:
        raise AppError("Mock 规则不存在", 4040, 404)
    return row


def _apply_rule(db: Session, project: Project, row: MockRule, body: MockIn) -> None:
    if body.api_id is not None:
        _definition(db, project.id, body.api_id)
    fault = body.fault_type or None
    if fault not in {None, "timeout", "error_code", "disconnect", "slow_start", "repeat"}:
        raise AppError("异常模拟类型不正确", 4004)
    match = dict(body.match_json or {})
    if match.get("path"):
        match["path"] = normalize_path(str(match["path"]))
    elif body.api_id is not None:
        api = _definition(db, project.id, body.api_id)
        match["path"] = api.path
        match.setdefault("method", api.method)
    if not match.get("path"):
        raise AppError("请填写 Mock 匹配路径", 4004)
    row.api_id = body.api_id
    row.name = body.name.strip()
    row.priority = body.priority
    row.status_code = body.status_code
    row.headers_json = body.headers_json or {}
    row.body = body.body
    row.delay_ms = max(0, body.delay_ms)
    row.match_json = match
    row.fault_type = fault
    row.enabled = body.enabled


@router.get("/scenarios")
def list_scenarios(public_id: str, user: CurrentUser = Depends(get_active_user), db: Session = Depends(get_db)):
    """场景目录和场景列表，供场景页按 MeterSphere 的表格展示。"""
    project = get_visible_project(db, user, public_id)
    modules = (
        db.query(ScenarioModule)
        .filter(ScenarioModule.project_id == project.id)
        .order_by(ScenarioModule.sort.asc(), ScenarioModule.id.asc())
        .all()
    )
    rows = db.query(Scenario).filter(Scenario.project_id == project.id).order_by(Scenario.id.asc()).all()
    env_ids = {row.env_id for row in rows if row.env_id}
    env_rows = db.query(Environment).filter(Environment.id.in_(env_ids)).all() if env_ids else []
    env_names = {row.id: row.name for row in env_rows}
    module_names = {row.id: row.name for row in modules}
    return ok(
        {
            "modules": [{"id": row.id, "parent_id": row.parent_id, "name": row.name, "sort": row.sort} for row in modules],
            "items": [
                {
                    "id": row.id,
                    "name": row.name,
                    "level": row.level,
                    "status": "进行中" if row.status == "enabled" else "已禁用",
                    "tags": row.tags,
                    "module_id": row.module_id,
                    "module": module_names.get(row.module_id or 0, "未规划场景"),
                    "env_name": env_names.get(row.env_id or 0, ""),
                    "result": "",
                }
                for row in rows
            ],
        }
    )


def project_layers(db: Session, project_id: int) -> dict:
    """给 Mock 进程复用的变量层。"""
    return _project_layers(db, project_id)
