# -*- coding: utf-8 -*-
# @File    : importers.py
# @Desc    : 把 OpenAPI、Postman 和 HAR 解析成统一的接口定义
# @Author  : xuetang-api
# @Date    : 2026-11-13
# @Update  : 2026-11-13 初始化定义导入

"""接口导入。只做解析，不写数据库。"""

import json
from urllib.parse import urlparse

import yaml

from app.core.exceptions import AppError

BODY_TYPES = {"none", "form", "urlencoded", "json", "raw"}
METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}


def empty_request() -> dict:
    """一份没有参数的请求。"""
    return {"query": [], "headers": [], "path_params": [], "body": {"type": "none", "content": ""}}


def normalize_path(path: str) -> str:
    """补上前导斜杠，并去掉结尾斜杠。根路径保持 /。"""
    text = (path or "").strip() or "/"
    if not text.startswith("/"):
        text = "/" + text
    if len(text) > 1 and text.endswith("/"):
        text = text[:-1]
    return text


def load_document(raw: bytes, filename: str) -> dict:
    """按 JSON 或 YAML 读入文档。Excel 不是导入格式。"""
    name = filename.lower()
    if name.endswith((".xlsx", ".xls")):
        raise AppError("Excel 只用于导出，导入请使用 OpenAPI、Postman 或 HAR", 4004)
    text = raw.decode("utf-8-sig")
    try:
        if name.endswith((".yaml", ".yml")):
            data = yaml.safe_load(text)
        else:
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise AppError("文件不是合法的 JSON 或 YAML", 4004) from exc
    if not isinstance(data, dict):
        raise AppError("文件内容无法识别为接口文档", 4004)
    return data


def parse_document(data: dict) -> list[dict]:
    """
    识别文档类型并返回接口列表。

    每条包含 module、name、method、path、description、request、examples。
    """
    if isinstance(data.get("log"), dict) and isinstance(data["log"].get("entries"), list):
        return _parse_har(data)
    schema = str((data.get("info") or {}).get("schema") or "")
    if "postman" in schema.lower() or _is_postman(data):
        return _parse_postman(data.get("item") or [])
    if str(data.get("swagger") or "") == "2.0":
        return _parse_openapi(data, version=2)
    if str(data.get("openapi") or "").startswith("3."):
        return _parse_openapi(data, version=3)
    if isinstance(data.get("paths"), dict):
        return _parse_openapi(data, version=3)
    raise AppError("只支持 OpenAPI 2、OpenAPI 3、Postman v2.1 和 HAR", 4004)


def _is_postman(data: dict) -> bool:
    """没有 schema 字段时，用 item 里的 request 判断是不是 Postman 集合。"""
    items = data.get("item")
    if not isinstance(items, list):
        return False
    return any(isinstance(item, dict) and "request" in item for item in items)


def _param(name: str, value: str = "", required: bool = False) -> dict:
    return {"name": name, "value": value, "required": required, "description": ""}


def _parse_openapi(data: dict, version: int) -> list[dict]:
    """读取 paths。目录名优先用标签，没有标签时归到「导入」。"""
    rows = []
    paths = data.get("paths") or {}
    for path, item in paths.items():
        if not isinstance(item, dict):
            continue
        shared = item.get("parameters") or []
        for method, operation in item.items():
            if method.upper() not in METHODS or not isinstance(operation, dict):
                continue
            params = list(shared) + list(operation.get("parameters") or [])
            request = empty_request()
            for param in params:
                if not isinstance(param, dict):
                    continue
                location = param.get("in")
                name = str(param.get("name") or "")
                if not name:
                    continue
                slot = {"query": "query", "header": "headers", "path": "path_params"}.get(location)
                if slot:
                    request[slot].append(_param(name, "", bool(param.get("required"))))
                elif version == 2 and location == "body":
                    request["body"] = {"type": "json", "content": param.get("schema") or {}}
            if version == 3:
                request["body"] = _body_from_content((operation.get("requestBody") or {}).get("content"))
            tags = operation.get("tags") or []
            rows.append(
                {
                    "module": str(tags[0]) if tags else "导入",
                    "name": str(operation.get("summary") or operation.get("operationId") or f"{method.upper()} {path}"),
                    "method": method.upper(),
                    "path": normalize_path(str(path)),
                    "description": str(operation.get("description") or ""),
                    "request": request,
                    "examples": _openapi_examples(operation),
                }
            )
    return rows


def _body_from_content(content: dict | None) -> dict:
    """按 Content-Type 映射到五种请求体。"""
    if not content:
        return {"type": "none", "content": ""}
    if "application/json" in content:
        media = content["application/json"]
        example = media.get("example")
        if example is None:
            example = media.get("schema") or ""
        return {"type": "json", "content": example}
    if "application/x-www-form-urlencoded" in content:
        return {"type": "urlencoded", "content": []}
    if "multipart/form-data" in content:
        return {"type": "form", "content": []}
    media = next(iter(content.values()))
    example = media.get("example", "")
    if not isinstance(example, str):
        example = json.dumps(example, ensure_ascii=False)
    return {"type": "raw", "content": example}


def _openapi_examples(operation: dict) -> list[dict]:
    """取第一个成功响应的示例，没有示例时不生成。"""
    responses = operation.get("responses") or {}
    for code, payload in responses.items():
        if not str(code).startswith("2") or not isinstance(payload, dict):
            continue
        body = ""
        content = payload.get("content") or {}
        if isinstance(content, dict):
            for media in content.values():
                if isinstance(media, dict) and media.get("example") is not None:
                    example = media["example"]
                    body = example if isinstance(example, str) else json.dumps(example, ensure_ascii=False)
                    break
        elif payload.get("examples") and isinstance(payload["examples"], dict):
            body = json.dumps(payload["examples"], ensure_ascii=False)
        if not body and not str(code).isdigit():
            continue
        return [
            {
                "name": str(payload.get("description") or "成功"),
                "status_code": int(code) if str(code).isdigit() else 200,
                "headers_json": {},
                "body": body,
                "description": "",
            }
        ]
    return []


def _parse_postman(items: list, module: str = "导入") -> list[dict]:
    """递归读取集合。文件夹名作为目录。"""
    rows = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if isinstance(item.get("item"), list):
            rows.extend(_parse_postman(item["item"], str(item.get("name") or module)))
            continue
        request = item.get("request") or {}
        if isinstance(request, str):
            request = {"url": request, "method": "GET"}
        method = str(request.get("method") or "GET").upper()
        if method not in METHODS:
            continue
        url = request.get("url") or ""
        query = []
        if isinstance(url, str):
            path = urlparse(url).path or "/"
        else:
            path = "/" + "/".join(str(part) for part in (url.get("path") or []))
            for param in url.get("query") or []:
                if isinstance(param, dict) and param.get("key"):
                    query.append(_param(str(param["key"]), str(param.get("value") or "")))
        headers = []
        for header in request.get("header") or []:
            if isinstance(header, dict) and header.get("key"):
                headers.append(_param(str(header["key"]), str(header.get("value") or "")))
        parsed = empty_request()
        parsed["query"] = query
        parsed["headers"] = headers
        parsed["body"] = _postman_body(request.get("body") or {})
        rows.append(
            {
                "module": module,
                "name": str(item.get("name") or f"{method} {path}"),
                "method": method,
                "path": normalize_path(path),
                "description": str(request.get("description") or ""),
                "request": parsed,
                "examples": [],
            }
        )
    return rows


def _postman_body(body: dict) -> dict:
    """Postman 的 body.mode 映射到平台的五种类型。"""
    mode = body.get("mode") or "none"
    if mode == "raw":
        return {"type": "raw", "content": str(body.get("raw") or "")}
    if mode == "urlencoded":
        return {"type": "urlencoded", "content": _pairs(body.get("urlencoded"))}
    if mode == "formdata":
        return {"type": "form", "content": _pairs(body.get("formdata"))}
    if mode == "file":
        return {"type": "form", "content": []}
    return {"type": "none", "content": ""}


def _pairs(rows: list | None) -> list[dict]:
    result = []
    for row in rows or []:
        if isinstance(row, dict) and row.get("key"):
            result.append(_param(str(row["key"]), str(row.get("value") or "")))
    return result


def _parse_har(data: dict) -> list[dict]:
    """HAR 的每条请求变成一个接口。相同方法加路径会在入库时合并。"""
    rows = []
    for entry in data["log"].get("entries") or []:
        request = entry.get("request") or {}
        method = str(request.get("method") or "GET").upper()
        if method not in METHODS:
            continue
        url = str(request.get("url") or "/")
        parsed = empty_request()
        for param in request.get("queryString") or []:
            if param.get("name"):
                parsed["query"].append(_param(str(param["name"]), str(param.get("value") or "")))
        for header in request.get("headers") or []:
            name = str(header.get("name") or "")
            if name and name.lower() not in {"host", "content-length", "cookie", "authorization"}:
                parsed["headers"].append(_param(name, str(header.get("value") or "")))
        post = request.get("postData") or {}
        mime = str(post.get("mimeType") or "")
        text = str(post.get("text") or "")
        if "json" in mime:
            parsed["body"] = {"type": "json", "content": text}
        elif "x-www-form-urlencoded" in mime:
            parsed["body"] = {"type": "urlencoded", "content": []}
        elif text:
            parsed["body"] = {"type": "raw", "content": text}
        path = normalize_path(urlparse(url).path or "/")
        rows.append(
            {
                "module": "导入",
                "name": f"{method} {path}",
                "method": method,
                "path": path,
                "description": "",
                "request": parsed,
                "examples": [],
            }
        )
    return rows
