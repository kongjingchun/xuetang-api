# -*- coding: utf-8 -*-
# @File    : response.py
# @Desc    : 统一 JSON 响应包装
# @Author  : xuetang-api
# @Date    : 2026-11-12
# @Update  : 2026-11-12 初始化阶段 0 骨架

"""响应体格式固定为 code、message、data。"""

from typing import Any


def ok(data: Any = None, message: str = "success") -> dict[str, Any]:
    """
    成功响应。

    Args:
        data: 业务数据。空值写成空对象，避免调用方判空分叉。
        message: 成功说明。
    """
    return {"code": 0, "message": message, "data": {} if data is None else data}


def fail(message: str, code: int, data: Any = None) -> dict[str, Any]:
    """
    失败响应体。HTTP 状态由调用方单独设置。

    Args:
        message: 失败说明，不包含堆栈。
        code: 非 0 业务码。
        data: 可选的补充信息，例如依赖名称。
    """
    return {"code": code, "message": message, "data": {} if data is None else data}
