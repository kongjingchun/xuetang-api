# -*- coding: utf-8 -*-
# @File    : resources.py
# @Desc    : 环境、变量、公共脚本和数据源。归档项目拒绝写入
# @Author  : xuetang-api
# @Date    : 2026-11-13
# @Update  : 2026-11-13 初始化项目配置接口

"""项目内配置。"""

import re

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.auth import client_ip
from app.auth.principal import CurrentUser
from app.common.scripts import run_user_script
from app.common.variables import VariableValue, resolve_text
from app.core.crypto import MASK, decrypt_text, encrypt_text, mask_secret
from app.core.deps import require_permissions
from app.core.exceptions import AppError
from app.core.response import ok
from app.db.session import get_db
from app.models.project import DataSource, Environment, PublicScript, Variable
from app.services.audit import write_audit
from app.services.datasource import ping_database
from app.services.guard import get_visible_project

router = APIRouter(prefix="/projects/{public_id}", tags=["project-config"])
_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class EnvIn(BaseModel):
    """环境。"""

    name: str = Field(min_length=1, max_length=64)
    code: str = Field(min_length=1, max_length=64)
    base_url: str = ""
    enabled: bool = True
    headers_json: dict = {}
    pre_script: str = ""
    description: str = ""


class VarIn(BaseModel):
    """变量。加密变量的 value 传明文，库存密文。"""

    scope: str
    scope_id: int = 0
    name: str
    var_type: str = "string"
    encrypted: bool = False
    value: str = ""
    description: str = ""


class PreviewIn(BaseModel):
    """预览变量替换。加密变量只会变成掩码。"""

    text: str
    env_id: int | None = None
    runtime: dict[str, str] = {}


class ScriptIn(BaseModel):
    """公共脚本。"""

    name: str = Field(min_length=1, max_length=128)
    category: str = "default"
    params_json: dict = {}
    content: str


class DebugIn(BaseModel):
    """脚本调试入参。"""

    params: dict = {}
    timeout: int = 5


class SourceIn(BaseModel):
    """数据源。password 为空表示修改时保留原密文。"""

    name: str = Field(min_length=1, max_length=128)
    db_type: str
    host: str = ""
    port: int = 3306
    database: str = ""
    username: str = ""
    password: str = ""


class PingIn(BaseModel):
    """保存前的连通性探测，密码用明文。"""

    db_type: str
    host: str = ""
    port: int = 3306
    database: str = ""
    username: str = ""
    password: str = ""


def _variable_in_project(db: Session, row: Variable, project_id: int) -> bool:
    """项目变量看 scope_id，环境变量要确认环境属于这个项目。"""
    if row.scope == "project":
        return row.scope_id == project_id
    if row.scope == "env":
        env = db.get(Environment, row.scope_id)
        return env is not None and env.project_id == project_id
    return False


def _check_name(name: str) -> None:
    if not _NAME.match(name):
        raise AppError("变量名只允许字母、数字和下划线", 4004)


def _layers(db: Session, project_id: int, env_id: int | None, runtime: dict[str, str]) -> dict:
    """从库里组装变量层。预览不解密。"""
    layers: dict[str, dict[str, VariableValue]] = {
        "runtime": {key: VariableValue(str(value)) for key, value in runtime.items()}
    }
    rows = db.query(Variable).filter(Variable.scope == "project", Variable.scope_id == project_id).all()
    layers["project"] = {row.name: VariableValue(row.value, row.encrypted) for row in rows}
    if env_id is not None:
        env_rows = db.query(Variable).filter(Variable.scope == "env", Variable.scope_id == env_id).all()
        layers["env"] = {row.name: VariableValue(row.value, row.encrypted) for row in env_rows}
    return layers


@router.get("/environments")
def list_environments(public_id: str, user: CurrentUser = Depends(require_permissions("env:manage")), db: Session = Depends(get_db)):
    """环境列表。"""
    project = get_visible_project(db, user, public_id)
    rows = db.query(Environment).filter(Environment.project_id == project.id).order_by(Environment.id.asc()).all()
    return ok(
        [
            {
                "id": row.id,
                "name": row.name,
                "code": row.code,
                "base_url": row.base_url,
                "enabled": bool(row.enabled),
                "headers_json": row.headers_json,
                "pre_script": row.pre_script,
                "description": row.description,
            }
            for row in rows
        ]
    )


@router.post("/environments")
def create_environment(
    public_id: str,
    body: EnvIn,
    request: Request,
    user: CurrentUser = Depends(require_permissions("env:manage")),
    db: Session = Depends(get_db),
):
    """新建环境。"""
    project = get_visible_project(db, user, public_id, writable=True)
    exists = (
        db.query(Environment)
        .filter(Environment.project_id == project.id, Environment.code == body.code)
        .one_or_none()
    )
    if exists:
        raise AppError("环境编码已存在", 4090, 409)
    row = Environment(project_id=project.id, **body.model_dump())
    db.add(row)
    db.flush()
    write_audit(db, user.id, "environment", "create", f"创建环境 {body.code}", client_ip(request), project.id)
    db.commit()
    return ok({"id": row.id, "code": row.code})


@router.put("/environments/{env_id}")
def update_environment(
    public_id: str,
    env_id: int,
    body: EnvIn,
    request: Request,
    user: CurrentUser = Depends(require_permissions("env:manage")),
    db: Session = Depends(get_db),
):
    """修改环境。"""
    project = get_visible_project(db, user, public_id, writable=True)
    row = db.get(Environment, env_id)
    if row is None or row.project_id != project.id:
        raise AppError("环境不存在", 4040, 404)
    conflict = (
        db.query(Environment)
        .filter(Environment.project_id == project.id, Environment.code == body.code, Environment.id != row.id)
        .one_or_none()
    )
    if conflict:
        raise AppError("环境编码已存在", 4090, 409)
    for key, value in body.model_dump().items():
        setattr(row, key, value)
    write_audit(db, user.id, "environment", "update", f"更新环境 {row.code}", client_ip(request), project.id)
    db.commit()
    return ok({"id": row.id})


@router.delete("/environments/{env_id}")
def delete_environment(
    public_id: str,
    env_id: int,
    request: Request,
    user: CurrentUser = Depends(require_permissions("env:manage")),
    db: Session = Depends(get_db),
):
    """删除环境。"""
    project = get_visible_project(db, user, public_id, writable=True)
    row = db.get(Environment, env_id)
    if row is None or row.project_id != project.id:
        raise AppError("环境不存在", 4040, 404)
    code = row.code
    write_audit(db, user.id, "environment", "delete", f"删除环境 {code}", client_ip(request), project.id)
    db.delete(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError("环境仍被场景或变量使用，不能删除", 4090, 409)
    return ok({"id": env_id})


@router.get("/variables")
def list_variables(public_id: str, user: CurrentUser = Depends(require_permissions("variable:manage")), db: Session = Depends(get_db)):
    """变量列表。加密值只返回掩码。"""
    project = get_visible_project(db, user, public_id)
    env_ids = [row.id for row in db.query(Environment.id).filter(Environment.project_id == project.id).all()]
    scoped = (
        db.query(Variable)
        .filter(
            ((Variable.scope == "project") & (Variable.scope_id == project.id))
            | ((Variable.scope == "env") & (Variable.scope_id.in_(env_ids or [-1])))
        )
        .order_by(Variable.id.asc())
        .all()
    )
    return ok(
        [
            {
                "id": row.id,
                "scope": row.scope,
                "scope_id": row.scope_id,
                "name": row.name,
                "var_type": row.var_type,
                "encrypted": bool(row.encrypted),
                "value": mask_secret(row.value, bool(row.encrypted)),
                "description": row.description,
            }
            for row in scoped
        ]
    )


@router.post("/variables")
def create_variable(
    public_id: str,
    body: VarIn,
    request: Request,
    user: CurrentUser = Depends(require_permissions("variable:manage")),
    db: Session = Depends(get_db),
):
    """新建变量。"""
    project = get_visible_project(db, user, public_id, writable=True)
    _check_name(body.name)
    if body.scope not in {"project", "env"}:
        raise AppError("变量作用域不正确", 4004)
    if body.scope == "env":
        env = db.get(Environment, body.scope_id)
        if env is None or env.project_id != project.id:
            raise AppError("环境不存在", 4040, 404)
    stored = encrypt_text(body.value) if body.encrypted else body.value
    row = Variable(
        scope=body.scope,
        scope_id=project.id if body.scope == "project" else body.scope_id,
        name=body.name,
        var_type=body.var_type,
        encrypted=body.encrypted,
        value=stored,
        description=body.description,
    )
    db.add(row)
    db.flush()
    write_audit(db, user.id, "variable", "create", f"创建变量 {body.name}", client_ip(request), project.id)
    db.commit()
    return ok({"id": row.id, "value": mask_secret(row.value, row.encrypted)})


@router.put("/variables/{var_id}")
def update_variable(
    public_id: str,
    var_id: int,
    body: VarIn,
    request: Request,
    user: CurrentUser = Depends(require_permissions("variable:manage")),
    db: Session = Depends(get_db),
):
    """修改变量。提交掩码时保留原来的密文。"""
    project = get_visible_project(db, user, public_id, writable=True)
    row = db.get(Variable, var_id)
    if row is None or not _variable_in_project(db, row, project.id):
        raise AppError("变量不存在", 4040, 404)
    _check_name(body.name)
    if body.encrypted and body.value == MASK:
        stored = row.value
    elif body.encrypted:
        stored = encrypt_text(body.value)
    else:
        stored = body.value
    row.name = body.name
    row.var_type = body.var_type
    row.encrypted = body.encrypted
    row.value = stored
    row.description = body.description
    write_audit(db, user.id, "variable", "update", f"更新变量 {row.name}", client_ip(request), project.id)
    db.commit()
    return ok({"id": row.id, "value": mask_secret(row.value, bool(row.encrypted))})


@router.delete("/variables/{var_id}")
def delete_variable(
    public_id: str,
    var_id: int,
    request: Request,
    user: CurrentUser = Depends(require_permissions("variable:manage")),
    db: Session = Depends(get_db),
):
    """删除变量，并写入审计。"""
    project = get_visible_project(db, user, public_id, writable=True)
    row = db.get(Variable, var_id)
    if row is None or not _variable_in_project(db, row, project.id):
        raise AppError("变量不存在", 4040, 404)
    name = row.name
    write_audit(db, user.id, "variable", "delete", f"删除变量 {name}", client_ip(request), project.id)
    db.delete(row)
    db.commit()
    return ok({"id": var_id})


@router.post("/variables/preview")
def preview_variables(
    public_id: str,
    body: PreviewIn,
    user: CurrentUser = Depends(require_permissions("variable:manage")),
    db: Session = Depends(get_db),
):
    """解析一段文本。加密变量替换成掩码，不在预览里解密。"""
    project = get_visible_project(db, user, public_id)
    rendered = resolve_text(body.text, _layers(db, project.id, body.env_id, body.runtime), reveal_secrets=False)
    return ok({"text": rendered})


@router.get("/scripts")
def list_scripts(public_id: str, user: CurrentUser = Depends(require_permissions("script:manage")), db: Session = Depends(get_db)):
    """项目脚本。"""
    project = get_visible_project(db, user, public_id)
    rows = db.query(PublicScript).filter(PublicScript.project_id == project.id).order_by(PublicScript.id.asc()).all()
    return ok(
        [
            {"id": row.id, "name": row.name, "category": row.category, "params_json": row.params_json, "content": row.content}
            for row in rows
        ]
    )


@router.post("/scripts")
def create_script(
    public_id: str,
    body: ScriptIn,
    request: Request,
    user: CurrentUser = Depends(require_permissions("script:manage")),
    db: Session = Depends(get_db),
):
    """保存脚本。"""
    project = get_visible_project(db, user, public_id, writable=True)
    row = PublicScript(project_id=project.id, **body.model_dump())
    db.add(row)
    db.flush()
    write_audit(db, user.id, "script", "create", f"创建脚本 {row.name}", client_ip(request), project.id)
    db.commit()
    return ok({"id": row.id})


@router.put("/scripts/{script_id}")
def update_script(
    public_id: str,
    script_id: int,
    body: ScriptIn,
    request: Request,
    user: CurrentUser = Depends(require_permissions("script:manage")),
    db: Session = Depends(get_db),
):
    """修改脚本名称、分类和正文。"""
    project = get_visible_project(db, user, public_id, writable=True)
    row = db.get(PublicScript, script_id)
    if row is None or row.project_id != project.id:
        raise AppError("脚本不存在", 4040, 404)
    row.name = body.name
    row.category = body.category
    row.params_json = body.params_json
    row.content = body.content
    write_audit(db, user.id, "script", "update", f"更新脚本 {row.name}", client_ip(request), project.id)
    db.commit()
    return ok({"id": row.id})


@router.delete("/scripts/{script_id}")
def delete_script(
    public_id: str,
    script_id: int,
    request: Request,
    user: CurrentUser = Depends(require_permissions("script:manage")),
    db: Session = Depends(get_db),
):
    """删除脚本，并写入审计。"""
    project = get_visible_project(db, user, public_id, writable=True)
    row = db.get(PublicScript, script_id)
    if row is None or row.project_id != project.id:
        raise AppError("脚本不存在", 4040, 404)
    name = row.name
    write_audit(db, user.id, "script", "delete", f"删除脚本 {name}", client_ip(request), project.id)
    db.delete(row)
    db.commit()
    return ok({"id": script_id})


@router.post("/scripts/{script_id}/debug")
def debug_script(
    public_id: str,
    script_id: int,
    body: DebugIn,
    user: CurrentUser = Depends(require_permissions("script:manage")),
    db: Session = Depends(get_db),
):
    """在子进程里调试脚本。"""
    project = get_visible_project(db, user, public_id)
    row = db.get(PublicScript, script_id)
    if row is None or row.project_id != project.id:
        raise AppError("脚本不存在", 4040, 404)
    return ok(run_user_script(row.content, body.params, body.timeout))


@router.get("/datasources")
def list_sources(public_id: str, user: CurrentUser = Depends(require_permissions("datasource:manage")), db: Session = Depends(get_db)):
    """数据源列表，不返回密码。"""
    project = get_visible_project(db, user, public_id)
    rows = db.query(DataSource).filter(DataSource.project_id == project.id).order_by(DataSource.id.asc()).all()
    return ok(
        [
            {
                "id": row.id,
                "name": row.name,
                "db_type": row.db_type,
                "host": row.host,
                "port": row.port,
                "database": row.database,
                "username": row.username,
            }
            for row in rows
        ]
    )


@router.post("/datasources")
def create_source(
    public_id: str,
    body: SourceIn,
    request: Request,
    user: CurrentUser = Depends(require_permissions("datasource:manage")),
    db: Session = Depends(get_db),
):
    """保存数据源，密码加密后入库。"""
    project = get_visible_project(db, user, public_id, writable=True)
    row = DataSource(
        project_id=project.id,
        name=body.name,
        db_type=body.db_type,
        host=body.host,
        port=body.port,
        database=body.database,
        username=body.username,
        password_cipher=encrypt_text(body.password) if body.password else "",
    )
    db.add(row)
    db.flush()
    write_audit(db, user.id, "datasource", "create", f"创建数据源 {row.name}", client_ip(request), project.id)
    db.commit()
    return ok({"id": row.id})


@router.put("/datasources/{source_id}")
def update_source(
    public_id: str,
    source_id: int,
    body: SourceIn,
    request: Request,
    user: CurrentUser = Depends(require_permissions("datasource:manage")),
    db: Session = Depends(get_db),
):
    """修改数据源。密码为空时保留原来的密文，避免把空字符串写回。"""
    project = get_visible_project(db, user, public_id, writable=True)
    row = db.get(DataSource, source_id)
    if row is None or row.project_id != project.id:
        raise AppError("数据源不存在", 4040, 404)
    row.name = body.name
    row.db_type = body.db_type
    row.host = body.host
    row.port = body.port
    row.database = body.database
    row.username = body.username
    if body.password:
        row.password_cipher = encrypt_text(body.password)
    write_audit(db, user.id, "datasource", "update", f"更新数据源 {row.name}", client_ip(request), project.id)
    db.commit()
    return ok({"id": row.id})


@router.delete("/datasources/{source_id}")
def delete_source(
    public_id: str,
    source_id: int,
    request: Request,
    user: CurrentUser = Depends(require_permissions("datasource:manage")),
    db: Session = Depends(get_db),
):
    """删除数据源，并写入审计。"""
    project = get_visible_project(db, user, public_id, writable=True)
    row = db.get(DataSource, source_id)
    if row is None or row.project_id != project.id:
        raise AppError("数据源不存在", 4040, 404)
    name = row.name
    write_audit(db, user.id, "datasource", "delete", f"删除数据源 {name}", client_ip(request), project.id)
    db.delete(row)
    db.commit()
    return ok({"id": source_id})


@router.post("/datasources/ping")
def ping_source(
    public_id: str,
    body: PingIn,
    user: CurrentUser = Depends(require_permissions("datasource:manage")),
    db: Session = Depends(get_db),
):
    """用调用方提交的明文做一次连通性探测，不落库。"""
    get_visible_project(db, user, public_id)
    message = ping_database(body.db_type, body.host, body.port, body.database, body.username, body.password)
    return ok({"message": message})


@router.post("/datasources/{source_id}/ping")
def ping_saved_source(
    public_id: str,
    source_id: int,
    user: CurrentUser = Depends(require_permissions("datasource:manage")),
    db: Session = Depends(get_db),
):
    """用已保存的密文探测。"""
    project = get_visible_project(db, user, public_id)
    row = db.get(DataSource, source_id)
    if row is None or row.project_id != project.id:
        raise AppError("数据源不存在", 4040, 404)
    password = decrypt_text(row.password_cipher) if row.password_cipher else ""
    message = ping_database(row.db_type, row.host, row.port, row.database, row.username, password)
    return ok({"message": message})
