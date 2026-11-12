# -*- coding: utf-8 -*-
# @File    : ids.py
# @Desc    : 生成带前缀的对外 ID，库内主键仍然使用自增整数
# @Author  : xuetang-api
# @Date    : 2026-11-13
# @Update  : 2026-11-13 初始化对外 ID

"""对外 ID。"""

import uuid


def new_public_id(prefix: str) -> str:
    """
    生成对外 ID。

    Args:
        prefix: 已包含下划线的前缀，例如 PRJ_。

    Returns:
        前缀加 12 位大写十六进制，长度适合 String(32)。
    """
    return f"{prefix}{uuid.uuid4().hex[:12].upper()}"
