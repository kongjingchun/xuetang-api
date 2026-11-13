# -*- coding: utf-8 -*-
# @File    : debug.py
# @Desc    : 按环境由服务端发送一次 HTTP 请求，并保存调试历史
# @Author  : xuetang-api
# @Date    : 2026-11-13
# @Update  : 2026-11-13 初始化调试发送与历史

"""在线调试。加密变量只在发出前解密，历史里保持掩码。"""

import json
import time
from urllib.parse import quote, urlencode, urlsplit

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.principal import CurrentUser
from app.common.scripts import run_user_script
from app.common.variables import VariableValue, resolve_text
from app.core.crypto import decrypt_text
from app.core.deps import get_active_user
from app.core.exceptions import AppError
from app.core.response import ok
from app.db.session import get_db
from app.models.project import DataSource, Environment, PublicScript, Variable
from app.models.testing import ApiCase, DebugHistory
from app.services.case_eval import (
    Exchange,
    StepHooks,
    apply_extractors,
    apply_steps,
    assertions_passed,
    evaluate_assertions,
)
from app.services.datasource import execute_sql
from app.services.guard import get_visible_project
from app.services.importers import METHODS

router = APIRouter(prefix="/projects/{public_id}", tags=["debug"])
BODY_LIMIT = 200000


class DebugIn(BaseModel):
    """调试请求。url 可以是绝对地址，也可以是拼到环境基础地址上的路径。"""

    env_id: int | None = None
    method: str
    url: str = ""
    headers: list[dict] = []
    query: list[dict] = []
    rest: list[dict] = []
    body_type: str = "none"
    body_text: str = ""
    target_type: str = "api"
    target_id: int = 0
    case_id: int | None = None


def _layers(db: Session, project_id: int, env_id: int | None, runtime: dict[str, str]) -> dict:
    """临时变量优先于环境变量和项目变量。"""
    layers: dict[str, dict[str, VariableValue]] = {
        "runtime": {key: VariableValue(str(value)) for key, value in runtime.items()}
    }
    rows = db.query(Variable).filter(Variable.scope == "project", Variable.scope_id == project_id).all()
    layers["project"] = {row.name: VariableValue(row.value, row.encrypted) for row in rows}
    if env_id is not None:
        env_rows = db.query(Variable).filter(Variable.scope == "env", Variable.scope_id == env_id).all()
        layers["env"] = {row.name: VariableValue(row.value, row.encrypted) for row in env_rows}
    return layers


def _render(text: str, layers: dict, reveal: bool) -> str:
    return resolve_text(text or "", layers, reveal_secrets=reveal)


def _enabled(item: dict) -> bool:
    return item.get("enabled", True) is not False and bool(str(item.get("name") or "").strip())


def _env_headers(raw: object) -> list[tuple[str, str]]:
    """环境公共头兼容对象和列表两种存法。"""
    if isinstance(raw, dict):
        return [(str(key), str(value)) for key, value in raw.items()]
    if isinstance(raw, list):
        return [
            (str(item.get("name") or ""), str(item.get("value") or ""))
            for item in raw
            if isinstance(item, dict) and item.get("name")
        ]
    return []


def _build_target(env: Environment | None, body: DebugIn, layers: dict, reveal: bool) -> tuple[str, dict[str, str], str]:
    """拼出最终 URL、请求头和请求体。reveal 为假时加密变量变成掩码，只用于历史。"""
    method = body.method.upper()
    if method not in METHODS:
        raise AppError("请求方法不正确", 4004)
    address = body.url.strip()
    for item in body.rest:
        if not _enabled(item):
            continue
        value = quote(_render(str(item.get("value") or ""), layers, reveal), safe="")
        address = address.replace("{" + str(item.get("name")).strip() + "}", value)
    address = _render(address, layers, reveal)
    if not address.startswith("http://") and not address.startswith("https://"):
        if env is None or not env.base_url:
            raise AppError("相对路径需要选择带基础地址的环境", 4004)
        address = env.base_url.rstrip("/") + "/" + address.lstrip("/")
        address = _render(address, layers, reveal)
    parts = urlsplit(address)
    if parts.scheme not in {"http", "https"}:
        raise AppError("只允许 http 或 https", 4004)
    query = [(str(item.get("name")).strip(), _render(str(item.get("value") or ""), layers, reveal)) for item in body.query if _enabled(item)]
    if query:
        joiner = "&" if parts.query else "?"
        address = address + joiner + urlencode(query)
    headers: dict[str, str] = {}
    if env is not None:
        for name, value in _env_headers(env.headers_json):
            headers[name] = _render(value, layers, reveal)
    for item in body.headers:
        if not _enabled(item):
            continue
        headers[str(item.get("name")).strip()] = _render(str(item.get("value") or ""), layers, reveal)
    if body.body_type == "json" and not any(key.lower() == "content-type" for key in headers):
        headers["Content-Type"] = "application/json"
    if body.body_type in {"urlencoded", "x-www-form-urlencoded"} and not any(key.lower() == "content-type" for key in headers):
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    payload = _render(body.body_text, layers, reveal) if body.body_type != "none" else ""
    return address, headers, payload


def _format_body(text: str) -> str:
    """JSON 响应排版。不是 JSON 时原样返回。"""
    stripped = text.strip()
    if not stripped or stripped[0] not in "{[":
        return text
    try:
        return json.dumps(json.loads(stripped), ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        return text


def _hooks(db: Session, project_id: int) -> StepHooks:
    """把脚本子进程和项目数据源接到处理器上。"""

    def script(content: str, params: dict) -> dict:
        try:
            return run_user_script(content, params)
        except AppError as exc:
            return {"ok": False, "error": exc.message}

    def script_by_id(script_id: int) -> str:
        row = db.get(PublicScript, script_id)
        if row is None or (row.project_id not in (None, project_id)):
            raise AppError("公共脚本不存在", 4040, 404)
        return row.content

    def sql(source_id: int, statement: str, query_only: bool) -> list[dict]:
        row = db.get(DataSource, source_id)
        if row is None or row.project_id != project_id:
            raise AppError("数据源不存在", 4040, 404)
        password = decrypt_text(row.password_cipher) if row.password_cipher else ""
        return execute_sql(row.db_type, row.host, row.port, row.database, row.username, password, statement, query_only)

    return StepHooks(script=script, script_by_id=script_by_id, sql=sql, sleep=lambda ms: time.sleep(ms / 1000))


@router.get("/debug/environments")
def debug_environments(public_id: str, user: CurrentUser = Depends(get_active_user), db: Session = Depends(get_db)):
    """调试页可选的环境，不要求环境管理权限。"""
    project = get_visible_project(db, user, public_id)
    rows = (
        db.query(Environment)
        .filter(Environment.project_id == project.id, Environment.enabled.is_(True))
        .order_by(Environment.id.asc())
        .all()
    )
    return ok([{"id": row.id, "name": row.name, "base_url": row.base_url} for row in rows])


@router.get("/debug/history")
def list_history(public_id: str, user: CurrentUser = Depends(get_active_user), db: Session = Depends(get_db)):
    """最近 50 条调试历史，列表不带响应正文。"""
    project = get_visible_project(db, user, public_id)
    rows = (
        db.query(DebugHistory)
        .filter(DebugHistory.project_id == project.id, DebugHistory.user_id == user.id)
        .order_by(DebugHistory.id.desc())
        .limit(50)
        .all()
    )
    return ok([_dump_history(row, brief=True) for row in rows])


@router.get("/debug/history/{history_id}")
def get_history(
    public_id: str,
    history_id: int,
    user: CurrentUser = Depends(get_active_user),
    db: Session = Depends(get_db),
):
    """一条历史的请求和响应，用于回放到调试页。"""
    project = get_visible_project(db, user, public_id)
    row = db.get(DebugHistory, history_id)
    if row is None or row.project_id != project.id or row.user_id != user.id:
        raise AppError("调试历史不存在", 4040, 404)
    return ok(_dump_history(row, brief=False))


@router.post("/debug/send")
def send_debug(
    public_id: str,
    body: DebugIn,
    user: CurrentUser = Depends(get_active_user),
    db: Session = Depends(get_db),
):
    """服务端发送一次请求。来自用例时同时跑前后置和断言。"""
    project = get_visible_project(db, user, public_id)
    env = None
    if body.env_id is not None:
        env = db.get(Environment, body.env_id)
        if env is None or env.project_id != project.id or not env.enabled:
            raise AppError("环境不存在", 4040, 404)
    case = None
    processors: dict = {}
    if body.case_id is not None:
        case = db.get(ApiCase, body.case_id)
        if case is None or case.project_id != project.id:
            raise AppError("用例不存在", 4040, 404)
        processors = case.processors_json or {}
    runtime: dict[str, str] = {}
    hooks = _hooks(db, project.id)
    status = 0
    response_headers: dict[str, str] = {}
    response_body = ""
    error = ""
    address = body.url
    headers: dict[str, str] = {}
    payload = ""
    masked_url = body.url
    masked_headers: dict[str, str] = {}
    masked_body = ""
    started = time.perf_counter()
    try:
        if processors:
            apply_steps(list(processors.get("pre") or []), runtime, None, hooks)
        layers = _layers(db, project.id, env.id if env else None, runtime)
        address, headers, payload = _build_target(env, body, layers, True)
        masked_url, masked_headers, masked_body = _build_target(env, body, layers, False)
        with httpx.Client(timeout=30, follow_redirects=False) as client:
            response = client.request(
                body.method.upper(),
                address,
                headers=headers,
                content=payload.encode("utf-8") if payload else None,
            )
        status = response.status_code
        response_headers = dict(response.headers)
        response_body = response.text[:BODY_LIMIT]
    except AppError as exc:
        error = exc.message
    except httpx.HTTPError as exc:
        error = exc.__class__.__name__
    elapsed = int((time.perf_counter() - started) * 1000)
    exchange = Exchange(status, response_headers, response_body, elapsed)
    assertions: list[dict] = []
    if processors and not error:
        try:
            apply_extractors(list(processors.get("extractors") or []), runtime, exchange)
            apply_steps(list(processors.get("post") or []), runtime, exchange, hooks)
            assertions = evaluate_assertions(list(processors.get("assertions") or []), exchange, hooks, runtime)
        except AppError as exc:
            error = exc.message
    history = DebugHistory(
        project_id=project.id,
        user_id=user.id,
        target_type="case" if case is not None else (body.target_type or "api"),
        target_id=case.id if case is not None else body.target_id,
        env_id=env.id if env else None,
        request_json={
            "method": body.method.upper(),
            "url": masked_url,
            "headers": masked_headers,
            "body_type": body.body_type,
            "body": masked_body,
        },
        response_json={
            "status": status,
            "headers": response_headers,
            "body": response_body,
            "error": error,
            "assertions": assertions,
            "passed": assertions_passed(assertions),
        },
        elapsed_ms=elapsed,
    )
    db.add(history)
    db.commit()
    db.refresh(history)
    return ok(
        {
            "history_id": history.id,
            "status": status,
            "elapsed_ms": elapsed,
            "headers": response_headers,
            "body": _format_body(response_body),
            "error": error,
            "assertions": assertions,
            "passed": assertions_passed(assertions),
        }
    )


def _dump_history(row: DebugHistory, brief: bool) -> dict:
    request = row.request_json or {}
    response = row.response_json or {}
    payload = {
        "id": row.id,
        "method": request.get("method") or "",
        "url": request.get("url") or "",
        "status": response.get("status") or 0,
        "elapsed_ms": row.elapsed_ms,
        "target_type": row.target_type,
        "target_id": row.target_id,
        "created_at": row.created_at.isoformat(sep=" ", timespec="seconds") if row.created_at else "",
    }
    if not brief:
        payload["request"] = request
        payload["response"] = response
    return payload
