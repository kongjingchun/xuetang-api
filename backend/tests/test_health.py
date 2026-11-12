# -*- coding: utf-8 -*-
# @File    : test_health.py
# @Desc    : 健康检查与 Mock 占位的 HTTP 形状。探针被替换，测试不连接真实数据库
# @Author  : xuetang-api
# @Date    : 2026-11-12
# @Update  : 2026-11-12 阶段 0 接口形状测试

"""HTTP 骨架测试。"""

from fastapi.testclient import TestClient

from app.main import app
from app.mock_server.main import app as mock_app


def test_service_info() -> None:
    """前缀根路径返回阶段号。"""
    response = TestClient(app).get("/api/v1")
    assert response.status_code == 200
    assert response.json()["data"]["phase"] == 1


def test_health_ok(monkeypatch) -> None:
    """依赖都可用时返回 200，并带上 Python 3.12。"""
    monkeypatch.setattr("app.api.v1.health._probe_mysql", lambda: "ok")
    monkeypatch.setattr("app.api.v1.health._probe_redis", lambda: "ok")
    response = TestClient(app).get("/api/v1/health")
    body = response.json()
    assert response.status_code == 200
    assert body["code"] == 0
    assert body["data"]["mysql"] == "ok"
    assert body["data"]["redis"] == "ok"
    assert body["data"]["python"].startswith("3.12")


def test_health_failure_hides_secrets(monkeypatch) -> None:
    """依赖失败时返回 503，响应里不出现数据库口令。"""
    monkeypatch.setattr("app.api.v1.health._probe_mysql", lambda: "unavailable")
    monkeypatch.setattr("app.api.v1.health._probe_redis", lambda: "ok")
    response = TestClient(app).get("/api/v1/health")
    assert response.status_code == 503
    assert response.json()["code"] == 5001
    assert "xuetang_pass" not in response.text


def test_mock_placeholder() -> None:
    """Mock 路径在阶段 0 明确返回未启用，而不是空成功。"""
    client = TestClient(mock_app)
    health = client.get("/health")
    assert health.status_code == 200
    missed = client.post("/mock/xuetang/api/v1/u/login")
    assert missed.status_code == 501
    assert missed.json()["data"]["project_code"] == "xuetang"
