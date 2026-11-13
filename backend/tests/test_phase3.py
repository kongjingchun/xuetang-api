# -*- coding: utf-8 -*-
# @File    : test_phase3.py
# @Desc    : 断言、版本保留和接口变更标记不依赖数据库
# @Author  : xuetang-api
# @Date    : 2026-11-13
# @Update  : 2026-11-13 覆盖断言、对比和版本裁剪

"""阶段 3 纯函数测试。"""

from app.common.scripts import run_user_script
from app.services.case_diff import change_items, definition_signature, diff_snapshots, versions_to_drop
from app.services.case_eval import Exchange, StepHooks, assertions_passed, evaluate_assertions
from app.services.datasource import execute_sql


def _exchange(**kwargs) -> Exchange:
    base = {"status": 200, "headers": {"Content-Type": "application/json"}, "body": '{"code":0,"name":"课程"}', "elapsed_ms": 20}
    base.update(kwargs)
    return Exchange(**base)


def test_assertions_require_all() -> None:
    """状态码、JSONPath、正则、XPath、响应头和耗时都要过。"""
    hooks = StepHooks()
    ok_rows = evaluate_assertions(
        [
            {"type": "status_code", "expect": 200},
            {"type": "header", "name": "Content-Type", "expect": "application/json"},
            {"type": "jsonpath", "expression": "$.code", "expect": "0"},
            {"type": "regex", "expression": '"name":"(.+)"', "expect": "课程"},
            {"type": "time", "expect": 1000},
        ],
        _exchange(),
        hooks,
        {},
    )
    xml_rows = evaluate_assertions(
        [{"type": "xpath", "expression": "/root/code", "expect": "0"}],
        _exchange(body="<root><code>0</code></root>"),
        hooks,
        {},
    )
    assert assertions_passed(ok_rows)
    assert assertions_passed(xml_rows)
    failed = evaluate_assertions(
        [{"type": "status_code", "expect": 200}, {"type": "jsonpath", "expression": "$.code", "expect": "1"}],
        _exchange(),
        hooks,
        {},
    )
    assert not assertions_passed(failed)


def test_script_and_sqlite_assertion() -> None:
    """脚本断言走子进程，数据库断言可以查 sqlite。"""
    script = run_user_script("result = params['status'] == 200")
    assert script["ok"] is True
    assert script["result"] is True
    rows = execute_sql("sqlite", "", 0, ":memory:", "", "", "select 1 as n", True)
    assert rows == [{"n": 1}]


def test_version_diff_and_retention() -> None:
    """新增、删除、修改分开，打过标签的版本不参与裁剪。"""
    items = diff_snapshots(
        {"request_json": {"method": "GET", "path": "/a", "headers": []}, "processors_json": {"assertions": []}},
        {
            "request_json": {"method": "POST", "path": "/a", "headers": [{"name": "A", "value": "1"}]},
            "processors_json": {"assertions": [{"type": "status_code", "expect": 200}]},
        },
    )
    changes = {item["field"]: item["change"] for item in items}
    assert changes["method"] == "modified"
    assert changes["headers"] == "added"
    assert changes["assertions"] == "added"
    removed = diff_snapshots(
        {"request_json": {"path": "/a"}, "processors_json": {}},
        {"request_json": {}, "processors_json": {}},
    )
    assert {item["field"]: item["change"] for item in removed}["path"] == "removed"
    # 版本号从新到旧。未标签只留 2 条，标签版本即使更老也保留。
    drop = versions_to_drop([(5, False), (4, False), (3, True), (2, False)], keep=2)
    assert drop == [2]


def test_definition_change_items() -> None:
    """只有方法、路径、参数或请求体变化才产生标记。"""
    before = definition_signature("GET", "/courses", {"query": [], "body": {"type": "none"}})
    same = definition_signature("GET", "/courses", {"query": [], "body": {"type": "none"}})
    assert change_items(before, same) == []
    after = definition_signature("POST", "/courses/{id}", {"query": [{"name": "page"}], "body": {"type": "json"}})
    fields = [item["field"] for item in change_items(before, after)]
    assert fields == ["方法", "路径", "Query", "请求体"]
