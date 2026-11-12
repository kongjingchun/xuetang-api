# -*- coding: utf-8 -*-
# @File    : main.py
# @Desc    : 独立 Mock 进程入口。阶段 0 只保留路径和明确的未启用响应
# @Author  : xuetang-api
# @Date    : 2026-11-12
# @Update  : 2026-11-12 初始化 Mock 占位服务

"""Mock 服务。与主服务分开进程，端口 8001。"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.core.logging import setup_logging
from app.core.response import fail, ok
from app.core.version_guard import assert_python_312

assert_python_312()
setup_logging()

app = FastAPI(title="xuetang-api-mock", version="0.1.0", docs_url=None)


@app.get("/health")
def health():
    """Mock 进程自身健康，不探测业务库。"""
    return ok({"status": "ok", "service": "mock", "phase": 0})


@app.api_route(
    "/mock/{project_code}/{full_path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
)
def mock_placeholder(project_code: str, full_path: str):
    """
    占位匹配。

    阶段 2 会在这里按优先级读取 mock_rule。当前返回 501，避免调用方把占位当成规则命中。

    Args:
        project_code: 项目标识。
        full_path: 接口路径。
    """
    return JSONResponse(
        status_code=501,
        content=fail(
            "Mock 规则将在阶段 2 启用",
            5010,
            {"project_code": project_code, "path": "/" + full_path},
        ),
    )
