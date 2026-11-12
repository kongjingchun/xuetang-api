# -*- coding: utf-8 -*-
# @File    : mock_match.py
# @Desc    : 按优先级匹配 Mock 规则，并生成延迟、变量和异常模拟后的响应
# @Author  : xuetang-api
# @Date    : 2026-11-13
# @Update  : 2026-11-13 初始化 Mock 匹配

"""Mock 匹配。第一条命中的规则生效，后面的规则不再看。"""

import json
from dataclasses import dataclass

from app.common.variables import resolve_text
from app.services.importers import normalize_path

FAULTS = {"timeout", "error_code", "disconnect", "slow_start", "repeat"}


@dataclass
class MockDecision:
    """一次匹配结果。未命中时 matched 为假，由调用方记日志并返回 404。"""

    matched: bool
    rule_id: int | None
    status_code: int
    headers: dict[str, str]
    body: str
    delay_ms: int
    fault: str | None


def evaluate_mock(
    rules: list[dict],
    method: str,
    path: str,
    query: dict[str, str],
    headers: dict[str, str],
    body: str,
    layers: dict | None = None,
) -> MockDecision:
    """
    选择规则并渲染响应。

    Args:
        rules: 已启用的规则。每条含 id、priority、status_code、headers、body、delay_ms、match、fault。
        layers: 变量层。响应体在异常模拟之后再替换变量。
    """
    ordered = sorted(rules, key=lambda item: (int(item.get("priority") or 100), int(item.get("id") or 0)))
    for rule in ordered:
        if _matches(rule, method, path, query, headers, body):
            return _render(rule, layers or {})
    return MockDecision(False, None, 404, {}, "", 0, None)


def _matches(rule: dict, method: str, path: str, query: dict[str, str], headers: dict[str, str], body: str) -> bool:
    """方法、路径、Query、Header 和请求体片段都要满足。空条件表示不限制。"""
    spec = rule.get("match") or {}
    expected_method = str(spec.get("method") or "").upper()
    if expected_method and expected_method != method.upper():
        return False
    pattern = str(spec.get("path") or "")
    if not pattern or not _path_matches(pattern, path):
        return False
    for key, value in (spec.get("query") or {}).items():
        if str(query.get(str(key), "")) != str(value):
            return False
    actual_headers = {str(key).lower(): str(value) for key, value in headers.items()}
    for key, value in (spec.get("headers") or {}).items():
        if actual_headers.get(str(key).lower()) != str(value):
            return False
    snippet = str(spec.get("body_contains") or "")
    if snippet and snippet not in body:
        return False
    return True


def _path_matches(pattern: str, actual: str) -> bool:
    """{id} 和 :id 匹配一个路径段。"""
    left = normalize_path(pattern).split("/")
    right = normalize_path(actual).split("/")
    if len(left) != len(right):
        return False
    for pattern_part, actual_part in zip(left, right):
        if pattern_part.startswith("{") and pattern_part.endswith("}"):
            continue
        if pattern_part.startswith(":"):
            continue
        if pattern_part != actual_part:
            return False
    return True


def _render(rule: dict, layers: dict) -> MockDecision:
    """按异常类型改状态码、延迟和响应体，再回填变量。"""
    fault = rule.get("fault") or None
    if fault not in FAULTS:
        fault = None
    status = int(rule.get("status_code") or 200)
    delay = max(0, int(rule.get("delay_ms") or 0))
    text = str(rule.get("body") or "")
    headers = {str(key): str(value) for key, value in (rule.get("headers") or {}).items()}
    if fault == "timeout":
        status = 504
        delay = max(delay, 3000)
        text = '{"message":"模拟超时"}'
    elif fault == "error_code":
        if status < 400:
            status = 500
    elif fault == "disconnect":
        status = 499
        text = ""
        delay = 0
    elif fault == "slow_start":
        delay = max(delay, 800)
    elif fault == "repeat":
        text = _repeat(text)
    rendered = resolve_text(text, layers, reveal_secrets=True)
    header_text = resolve_text(json.dumps(headers, ensure_ascii=False), layers, reveal_secrets=True)
    try:
        headers = {str(key): str(value) for key, value in json.loads(header_text).items()}
    except json.JSONDecodeError:
        headers = headers
    if rendered[:1] in "{[" and "content-type" not in {key.lower() for key in headers}:
        headers["Content-Type"] = "application/json"
    return MockDecision(True, int(rule["id"]), status, headers, rendered, min(delay, 10000), fault)


def _repeat(text: str) -> str:
    """响应体重复一次。JSON 变成两条相同元素的数组，普通文本直接拼接。"""
    try:
        parsed = json.loads(text) if text else ""
    except json.JSONDecodeError:
        return text + text
    return json.dumps([parsed, parsed], ensure_ascii=False)
