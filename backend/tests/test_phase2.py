# -*- coding: utf-8 -*-
# @File    : test_phase2.py
# @Desc    : 导入解析和 Mock 匹配不依赖数据库
# @Author  : xuetang-api
# @Date    : 2026-11-13
# @Update  : 2026-11-13 覆盖 OpenAPI、Postman、HAR 和规则优先级

"""阶段 2 纯函数测试。"""

from app.services.importers import parse_document
from app.services.mock_match import evaluate_mock


def test_openapi3_and_swagger2() -> None:
    """两种 OpenAPI 都能读出方法和路径。"""
    newer = parse_document(
        {
            "openapi": "3.0.3",
            "paths": {
                "/courses/{id}": {
                    "get": {
                        "tags": ["课程"],
                        "summary": "课程详情",
                        "parameters": [{"name": "id", "in": "path", "required": True}],
                        "responses": {"200": {"description": "成功", "content": {"application/json": {"example": {"id": 1}}}}},
                    }
                }
            },
        }
    )
    assert newer[0]["module"] == "课程"
    assert newer[0]["method"] == "GET"
    assert newer[0]["path"] == "/courses/{id}"
    assert newer[0]["examples"][0]["status_code"] == 200
    older = parse_document({"swagger": "2.0", "paths": {"/login": {"post": {"summary": "登录"}}}})
    assert older[0]["method"] == "POST"
    assert older[0]["path"] == "/login"


def test_postman_and_har() -> None:
    """Postman 文件夹成为目录，HAR 去掉鉴权头。"""
    postman = parse_document(
        {
            "info": {"schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"},
            "item": [
                {
                    "name": "用户端",
                    "item": [
                        {
                            "name": "登录",
                            "request": {
                                "method": "POST",
                                "url": {"path": ["api", "v1", "u", "login"], "query": [{"key": "lang", "value": "zh"}]},
                                "body": {"mode": "raw", "raw": "{}"},
                            },
                        }
                    ],
                }
            ],
        }
    )
    assert postman[0]["module"] == "用户端"
    assert postman[0]["path"] == "/api/v1/u/login"
    assert postman[0]["request"]["body"]["type"] == "raw"
    har = parse_document(
        {
            "log": {
                "entries": [
                    {
                        "request": {
                            "method": "GET",
                            "url": "http://demo.local/health",
                            "headers": [{"name": "Authorization", "value": "secret"}, {"name": "X-Debug", "value": "1"}],
                            "queryString": [],
                        }
                    }
                ]
            }
        }
    )
    names = [item["name"] for item in har[0]["request"]["headers"]]
    assert "Authorization" not in names
    assert "X-Debug" in names


def test_mock_priority_path_and_fault() -> None:
    """数值更小的优先级先命中，路径参数和重复异常按约定生效。"""
    rules = [
        {
            "id": 2,
            "priority": 50,
            "status_code": 200,
            "headers": {},
            "body": "later",
            "delay_ms": 0,
            "match": {"method": "GET", "path": "/courses/{id}"},
            "fault": None,
        },
        {
            "id": 1,
            "priority": 10,
            "status_code": 200,
            "headers": {},
            "body": '{"token":"${__uuid}"}',
            "delay_ms": 0,
            "match": {"method": "GET", "path": "/courses/:id", "query": {"lang": "zh"}},
            "fault": "repeat",
        },
    ]
    missed = evaluate_mock(rules, "GET", "/missing", {}, {}, "", None)
    assert missed.matched is False
    plain = evaluate_mock(rules, "GET", "/courses/9", {}, {}, "", None)
    assert plain.rule_id == 2
    hit = evaluate_mock(rules, "GET", "/courses/9", {"lang": "zh"}, {}, "", None)
    assert hit.rule_id == 1
    assert hit.body.startswith("[")
    assert "${__uuid}" not in hit.body
    timeout = evaluate_mock(
        [{**rules[0], "id": 3, "priority": 1, "fault": "timeout", "match": {"path": "/slow"}}],
        "GET",
        "/slow",
        {},
        {},
        "",
        None,
    )
    assert timeout.status_code == 504
    assert timeout.delay_ms == 3000
