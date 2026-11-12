# -*- coding: utf-8 -*-
# @File    : __init__.py
# @Desc    : v1 路由聚合
# @Author  : xuetang-api
# @Date    : 2026-11-12
# @Update  : 2026-11-13 挂载认证、项目和环境接口

"""API v1。"""

from fastapi import APIRouter

from app import __version__
from app.api.v1.audit import router as audit_router
from app.api.v1.auth import router as auth_router
from app.api.v1.health import router as health_router
from app.api.v1.projects import router as project_router
from app.api.v1.resources import router as resource_router
from app.api.v1.roles import router as role_router
from app.api.v1.users import router as user_router
from app.core.response import ok

router = APIRouter()
router.include_router(health_router)
router.include_router(auth_router)
router.include_router(user_router)
router.include_router(role_router)
router.include_router(project_router)
router.include_router(resource_router)
router.include_router(audit_router)


@router.get("")
def service_info():
    """服务标识，便于确认前缀已经挂上。"""
    return ok({"name": "xuetang-api", "version": __version__, "phase": 1})
