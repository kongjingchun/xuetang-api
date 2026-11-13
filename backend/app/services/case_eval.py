# -*- coding: utf-8 -*-
# @File    : case_eval.py
# @Desc    : 断言、提取和前后置的求值。脚本与 SQL 由调用方注入，便于单测
# @Author  : xuetang-api
# @Date    : 2026-11-13
# @Update  : 2026-11-13 初始化用例断言与处理器

"""用例执行时的纯计算。全部断言通过才算成功。"""

import json
import re
from dataclasses import dataclass, field

from jsonpath_ng.ext import parse as parse_jsonpath
from lxml import etree

ASSERT_TYPES = {"status_code", "header", "jsonpath", "regex", "xpath", "time", "script", "database"}
EXTRACT_TYPES = {"jsonpath", "regex", "header"}
PRE_TYPES = {"assign", "script_ref", "sql", "wait", "script"}
POST_TYPES = {"extract", "script", "sql", "clear"}


@dataclass
class Exchange:
    """一次 HTTP 交换。headers 保留原始大小写，比较时忽略大小写。"""

    status: int
    headers: dict[str, str]
    body: str
    elapsed_ms: int


@dataclass
class StepHooks:
    """脚本、公共脚本、SQL 和等待由外部提供。单测可以换成假实现。"""

    script: callable = lambda _content, _params: {"ok": True, "result": None}
    script_by_id: callable = lambda _script_id: ""
    sql: callable = lambda _source_id, _sql, _query_only: []
    sleep: callable = lambda _ms: None
    logs: list[str] = field(default_factory=list)


def header_value(headers: dict[str, str], name: str) -> str:
    """按名称取响应头，不区分大小写。"""
    target = name.lower()
    for key, value in headers.items():
        if key.lower() == target:
            return "" if value is None else str(value)
    return ""


def jsonpath_text(body: str, expression: str) -> str:
    """取 JSONPath 的第一个匹配。对象和数组压成 JSON 文本。"""
    data = json.loads(body or "null")
    found = parse_jsonpath(expression or "$").find(data)
    if not found:
        return ""
    value = found[0].value
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    if value is None:
        return ""
    return str(value)


def xpath_text(body: str, expression: str) -> str:
    """取 XPath 的第一个节点文本。"""
    root = etree.fromstring(body.encode("utf-8"))
    found = root.xpath(expression)
    if isinstance(found, list):
        if not found:
            return ""
        node = found[0]
    else:
        node = found
    if isinstance(node, etree._Element):
        return "".join(node.itertext())
    return "" if node is None else str(node)


def regex_text(body: str, expression: str) -> str | None:
    """正则匹配。有捕获组时返回第一组，否则返回整个匹配。"""
    matched = re.search(expression or "", body or "")
    if matched is None:
        return None
    if matched.groups():
        return matched.group(1)
    return matched.group(0)


def _cell(rows: list[dict]) -> str:
    """取查询结果第一行第一列，供断言和变量赋值使用。"""
    if not rows:
        return ""
    first = rows[0]
    if not first:
        return ""
    value = next(iter(first.values()))
    return "" if value is None else str(value)


def _expect(value: object) -> str:
    return "" if value is None else str(value)


def evaluate_assertion(item: dict, exchange: Exchange, hooks: StepHooks, variables: dict[str, str]) -> dict:
    """
    计算一条断言。

    Returns:
        type、passed、message、actual。异常也记为失败，不向外抛。
    """
    kind = str(item.get("type") or "")
    expect = item.get("expect")
    actual = ""
    passed = False
    message = ""
    try:
        if kind == "status_code":
            actual = str(exchange.status)
            passed = exchange.status == int(expect)
        elif kind == "header":
            actual = header_value(exchange.headers, str(item.get("name") or ""))
            passed = actual == _expect(expect)
        elif kind == "jsonpath":
            actual = jsonpath_text(exchange.body, str(item.get("expression") or "$"))
            passed = actual == _expect(expect)
        elif kind == "regex":
            actual = regex_text(exchange.body, str(item.get("expression") or "")) or ""
            passed = actual != "" if expect in (None, "") else actual == _expect(expect)
        elif kind == "xpath":
            actual = xpath_text(exchange.body, str(item.get("expression") or ""))
            passed = actual == _expect(expect)
        elif kind == "time":
            actual = str(exchange.elapsed_ms)
            passed = exchange.elapsed_ms <= int(expect)
        elif kind == "script":
            result = hooks.script(str(item.get("script") or ""), _script_params(exchange, variables))
            actual = "" if result.get("result") is None else str(result.get("result"))
            passed = bool(result.get("ok") and result.get("result"))
            message = "" if result.get("ok") else str(result.get("error") or "脚本失败")
        elif kind == "database":
            rows = hooks.sql(int(item.get("datasource_id") or 0), str(item.get("sql") or ""), True)
            actual = _cell(rows)
            passed = actual == _expect(expect)
        else:
            message = "不支持的断言类型"
    except Exception as exc:
        passed = False
        message = str(exc)
    if not message:
        message = "通过" if passed else f"期望 {expect}，实际 {actual}"
    return {"type": kind, "passed": passed, "message": message, "actual": actual}


def evaluate_assertions(items: list[dict], exchange: Exchange, hooks: StepHooks, variables: dict[str, str]) -> list[dict]:
    """逐条断言。没有断言时视为通过。"""
    return [evaluate_assertion(item, exchange, hooks, variables) for item in items]


def assertions_passed(results: list[dict]) -> bool:
    """全部通过才算用例通过。空列表也算通过。"""
    return all(item["passed"] for item in results)


def extract_text(item: dict, exchange: Exchange) -> str | None:
    """从响应提取一个值。提取不到时返回 None，不覆盖已有变量。"""
    kind = str(item.get("type") or "")
    if kind == "jsonpath":
        return jsonpath_text(exchange.body, str(item.get("expression") or "$"))
    if kind == "regex":
        return regex_text(exchange.body, str(item.get("expression") or ""))
    if kind == "header":
        return header_value(exchange.headers, str(item.get("source") or item.get("expression") or item.get("name") or ""))
    return None


def apply_steps(steps: list[dict], variables: dict[str, str], exchange: Exchange | None, hooks: StepHooks) -> None:
    """按顺序执行前置或后置。等待最长 10 秒，避免处理器把请求拖住。"""
    for step in steps:
        kind = str(step.get("type") or "")
        name = str(step.get("name") or "")
        if kind == "assign" and name:
            variables[name] = str(step.get("value") or "")
            hooks.logs.append(f"赋值 {name}")
        elif kind == "wait":
            waited = min(max(int(step.get("ms") or 0), 0), 10000)
            hooks.sleep(waited)
            hooks.logs.append(f"等待 {waited} ms")
        elif kind == "script":
            result = hooks.script(str(step.get("script") or ""), _script_params(exchange, variables))
            _record_script(hooks, "脚本", result)
            if name and result.get("ok") and result.get("result") is not None:
                variables[name] = str(result.get("result"))
        elif kind == "script_ref":
            content = hooks.script_by_id(int(step.get("script_id") or 0))
            result = hooks.script(content, _script_params(exchange, variables))
            _record_script(hooks, "公共脚本", result)
            if name and result.get("ok") and result.get("result") is not None:
                variables[name] = str(result.get("result"))
        elif kind == "sql":
            rows = hooks.sql(int(step.get("datasource_id") or 0), str(step.get("sql") or ""), exchange is None)
            if name:
                variables[name] = _cell(rows)
            hooks.logs.append(f"SQL 返回 {len(rows)} 行")
        elif kind == "extract" and exchange is not None and name:
            value = extract_text(step, exchange)
            if value is not None:
                variables[name] = value
                hooks.logs.append(f"提取 {name}")
        elif kind == "clear" and name:
            variables.pop(name, None)
            hooks.logs.append(f"清除 {name}")


def apply_extractors(items: list[dict], variables: dict[str, str], exchange: Exchange) -> None:
    """响应之后把提取结果写入本次临时变量。"""
    for item in items:
        name = str(item.get("name") or "")
        if not name:
            continue
        value = extract_text(item, exchange)
        if value is not None:
            variables[name] = value


def _record_script(hooks: StepHooks, label: str, result: dict) -> None:
    """把脚本打印和结果写进控制台。"""
    for item in result.get("logs") or []:
        hooks.logs.append(str(item))
    if result.get("ok"):
        hooks.logs.append(f"{label}完成")
    else:
        hooks.logs.append(f"{label}失败: {result.get('error') or ''}")


def _script_params(exchange: Exchange | None, variables: dict[str, str]) -> dict:
    """传给脚本的入参。脚本里用 params 读取，用 result 返回。"""
    return {
        "status": 0 if exchange is None else exchange.status,
        "headers": {} if exchange is None else exchange.headers,
        "body": "" if exchange is None else exchange.body,
        "elapsed_ms": 0 if exchange is None else exchange.elapsed_ms,
        "variables": dict(variables),
    }
