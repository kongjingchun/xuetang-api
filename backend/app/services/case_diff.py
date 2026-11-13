# -*- coding: utf-8 -*-
# @File    : case_diff.py
# @Desc    : 用例版本对比，以及接口定义变更后要标到关联用例上的字段
# @Author  : xuetang-api
# @Date    : 2026-11-13
# @Update  : 2026-11-13 初始化版本对比和变更标记

"""版本差异。新增、删除、修改分开，方便界面上色。"""

KEEP_UNTAGGED = 30

FIELD_LABELS = (
    ("method", "方法"),
    ("path", "URL"),
    ("headers", "Header"),
    ("query", "Query"),
    ("body", "请求体"),
    ("assertions", "断言"),
    ("pre", "前置"),
    ("post", "后置"),
)


def definition_signature(method: str, path: str, request_json: dict | None) -> dict:
    """抽出接口上会影响用例的字段。名称和说明变化不算变更。"""
    request = request_json or {}
    return {
        "method": method,
        "path": path,
        "query": request.get("query") or [],
        "headers": request.get("headers") or [],
        "path_params": request.get("path_params") or [],
        "body": request.get("body") or {},
    }


def change_items(before: dict, after: dict) -> list[dict]:
    """接口前后签名不一致的字段。相同则返回空列表，调用方不必标记用例。"""
    labels = {
        "method": "方法",
        "path": "路径",
        "query": "Query",
        "headers": "Header",
        "path_params": "REST",
        "body": "请求体",
    }
    items = []
    for key, label in labels.items():
        if before.get(key) != after.get(key):
            items.append({"field": label, "before": before.get(key), "after": after.get(key)})
    return items


def case_view(snapshot: dict) -> dict:
    """把快照收成可对比的平面字段。"""
    request = snapshot.get("request_json") or {}
    processors = snapshot.get("processors_json") or {}
    return {
        "method": str(request.get("method") or ""),
        "path": str(request.get("path") or ""),
        "headers": request.get("headers") or [],
        "query": request.get("query") or [],
        "body": request.get("body") or {},
        "assertions": processors.get("assertions") or [],
        "pre": processors.get("pre") or [],
        "post": {"extractors": processors.get("extractors") or [], "steps": processors.get("post") or []},
    }


def diff_snapshots(left: dict, right: dict) -> list[dict]:
    """
    对比两份快照。

    change 取值 added、removed、modified、same。left 是较旧的一侧。
    """
    older = case_view(left)
    newer = case_view(right)
    rows = []
    for key, label in FIELD_LABELS:
        before = older.get(key)
        after = newer.get(key)
        if before == after:
            change = "same"
        elif _blank(before) and not _blank(after):
            change = "added"
        elif not _blank(before) and _blank(after):
            change = "removed"
        else:
            change = "modified"
        rows.append({"field": key, "label": label, "change": change, "left": before, "right": after})
    return rows


def versions_to_drop(versions: list[tuple[int, bool]], keep: int = KEEP_UNTAGGED) -> list[int]:
    """
    决定要删掉的版本。

    Args:
        versions: (版本主键, 是否打标签)，按版本号从新到旧。
        keep: 未打标签的保留条数。打过标签的不删。
    """
    untagged = [item_id for item_id, tagged in versions if not tagged]
    return untagged[keep:]


def _blank(value: object) -> bool:
    return value in (None, "", [], {})
