# -*- coding: utf-8 -*-
# @File    : main.py
# @Desc    : FastAPI 入口。启动时校验 Python 3.12，并登记全部数据模型
# @Author  : xuetang-api
# @Date    : 2026-11-12
# @Update  : 2026-11-12 初始化阶段 0 应用工厂

"""主服务入口。"""

import logging

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api.v1 import router as api_router
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import setup_logging
from app.core.response import fail
from app.core.version_guard import assert_python_312

assert_python_312()
setup_logging()
# 导入模型以核对 65 张表都已登记。迁移和种子也会导入同一份 metadata。
import app.models  # noqa: E402,F401

logger = logging.getLogger(__name__)
settings = get_settings()


def create_app() -> FastAPI:
    """
    创建应用。

    开发环境允许本机前端源跨域。生产环境由同源 Nginx 反代，不放开任意源。
    """
    app = FastAPI(title="xuetang-api", version=__version__, docs_url=f"{settings.api_prefix}/docs")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:8080",
            "http://127.0.0.1:8080",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix=settings.api_prefix)

    @app.exception_handler(AppError)
    async def handle_app_error(_request, exc: AppError):
        """业务错误转为统一响应，不附带堆栈。"""
        return JSONResponse(status_code=exc.status_code, content=fail(exc.message, exc.code))

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_request, exc: RequestValidationError):
        """参数校验失败时指出字段，避免只返回一句看不出原因的提示。"""
        names = {
            "username": "用户名",
            "password": "密码",
            "old_password": "原密码",
            "new_password": "新密码",
            "real_name": "姓名",
            "name": "名称",
            "code": "编码",
        }
        messages: list[str] = []
        for err in exc.errors():
            loc = err.get("loc") or ()
            field = str(loc[-1]) if loc else ""
            label = names.get(field, field or "参数")
            if err.get("type") == "string_too_short" and "password" in field:
                messages.append(f"{label}至少 8 位")
            elif err.get("type") in {"string_too_short", "missing"}:
                messages.append(f"请填写{label}")
            else:
                messages.append(f"{label}不正确")
        return JSONResponse(status_code=422, content=fail("；".join(messages) or "请求参数不正确", 4001))

    @app.exception_handler(HTTPException)
    async def handle_http(_request, exc: HTTPException):
        """把框架的 HTTP 异常也收成 code/message/data。"""
        message = exc.detail if isinstance(exc.detail, str) else "请求错误"
        return JSONResponse(status_code=exc.status_code, content=fail(message, exc.status_code))

    @app.exception_handler(Exception)
    async def handle_unexpected(_request, exc: Exception):
        """未预料的错误只记日志，响应里不出现堆栈。"""
        logger.exception("未处理异常: %s", exc.__class__.__name__)
        return JSONResponse(status_code=500, content=fail("服务器内部错误", 5000))

    @app.middleware("http")
    async def access_log(request, call_next):
        """记录访问。健康检查频率高，跳过以免淹没排障日志。"""
        response = await call_next(request)
        if request.url.path != f"{settings.api_prefix}/health":
            logger.info("%s %s -> %s", request.method, request.url.path, response.status_code)
        return response

    logger.info("xuetang-api %s 已加载，阶段 0", __version__)
    return app


app = create_app()
