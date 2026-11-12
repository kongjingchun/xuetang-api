# -*- coding: utf-8 -*-
# @File    : main.py
# @Desc    : 独立 Mock 进程。按项目读取规则，命中第一条后返回
# @Author  : xuetang-api
# @Date    : 2026-11-12
# @Update  : 2026-11-13 按优先级匹配规则并记录调用

"""Mock 服务。与主服务分开进程，端口 8001。"""

import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from app.core.logging import setup_logging
from app.core.response import fail, ok
from app.core.version_guard import assert_python_312
from app.db.session import SessionLocal
from app.models.project import Project
from app.models.testing import MockLog, MockRule
from app.services.importers import normalize_path
from app.services.mock_match import evaluate_mock
from app.api.v1.definitions import project_layers

assert_python_312()
setup_logging()

app = FastAPI(title="xuetang-api-mock", version="0.1.0", docs_url=None)


@app.get("/health")
def health():
    """Mock 进程自身健康，不探测业务库。"""
    return ok({"status": "ok", "service": "mock", "phase": 2})


@app.api_route(
    "/mock/{project_code}/{full_path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
)
async def serve_mock(project_code: str, full_path: str, request: Request):
    """
    按优先级匹配规则。

    未命中返回 404。异常模拟里的断开使用 499，超时使用 504。
    """
    started = time.perf_counter()
    path = normalize_path("/" + full_path)
    raw = (await request.body()).decode("utf-8", errors="replace")
    query = {key: value for key, value in request.query_params.items()}
    headers = {key: value for key, value in request.headers.items() if key.lower() not in {"authorization", "cookie"}}
    session = SessionLocal()
    try:
        project = session.query(Project).filter(Project.code == project_code).one_or_none()
        if project is None:
            return JSONResponse(status_code=404, content=fail("项目不存在", 4040, {"project_code": project_code}))
        rows = (
            session.query(MockRule)
            .filter(MockRule.project_id == project.id, MockRule.enabled.is_(True))
            .all()
        )
        rules = [
            {
                "id": row.id,
                "priority": row.priority,
                "status_code": row.status_code,
                "headers": row.headers_json or {},
                "body": row.body,
                "delay_ms": row.delay_ms,
                "match": row.match_json or {},
                "fault": row.fault_type,
            }
            for row in rows
        ]
        decision = evaluate_mock(rules, request.method, path, query, headers, raw, project_layers(session, project.id))
        elapsed = int((time.perf_counter() - started) * 1000) + decision.delay_ms
        session.add(
            MockLog(
                project_id=project.id,
                path=path[:512],
                rule_id=decision.rule_id,
                elapsed_ms=elapsed,
                request_digest=f"{request.method} {path}"[:1000],
            )
        )
        session.commit()
    finally:
        session.close()
    if not decision.matched:
        return JSONResponse(
            status_code=404,
            content=fail("没有匹配的 Mock 规则", 4041, {"method": request.method, "path": path}),
        )
    if decision.delay_ms:
        time.sleep(decision.delay_ms / 1000)
    return Response(content=decision.body, status_code=decision.status_code, headers=decision.headers)
