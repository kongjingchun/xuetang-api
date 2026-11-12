# -*- coding: utf-8 -*-
# @File    : exporters.py
# @Desc    : 把接口定义导出成 JSON 或 Excel
# @Author  : xuetang-api
# @Date    : 2026-11-13
# @Update  : 2026-11-13 初始化定义导出

"""接口导出。"""

import base64
import json
from io import BytesIO

from openpyxl import Workbook


def export_json(rows: list[dict]) -> dict:
    """JSON 导出放在统一响应的 data 里，前端自行下载。"""
    payload = json.dumps(rows, ensure_ascii=False, indent=2).encode("utf-8")
    return _pack("definitions.json", "application/json", payload)


def export_excel(rows: list[dict]) -> dict:
    """一行一个接口。请求体过长时仍完整写入单元格。"""
    book = Workbook()
    sheet = book.active
    sheet.title = "接口"
    sheet.append(["目录", "名称", "方法", "路径", "说明", "请求体类型", "请求"])
    for row in rows:
        request = row.get("request") or {}
        body = request.get("body") or {}
        sheet.append(
            [
                row.get("module") or "",
                row.get("name") or "",
                row.get("method") or "",
                row.get("path") or "",
                row.get("description") or "",
                body.get("type") or "none",
                json.dumps(request, ensure_ascii=False),
            ]
        )
    buffer = BytesIO()
    book.save(buffer)
    return _pack(
        "definitions.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        buffer.getvalue(),
    )


def _pack(filename: str, media_type: str, payload: bytes) -> dict:
    return {
        "filename": filename,
        "media_type": media_type,
        "content_base64": base64.b64encode(payload).decode("ascii"),
    }
