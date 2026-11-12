# -*- coding: utf-8 -*-
# @File    : version_guard.py
# @Desc    : 启动时拒绝 Python 3.13 及其他非 3.12 解释器
# @Author  : xuetang-api
# @Date    : 2026-11-12
# @Update  : 2026-11-12 初始化阶段 0 骨架

"""解释器版本闸门。镜像、pyproject 与这里三处同时锁定 3.12。"""

import sys


def assert_python_312() -> None:
    """
    确认当前解释器是 3.12 系列。

    Raises:
        RuntimeError: 主版本不是 3.12，包含 3.13 及以上。
    """
    major, minor = sys.version_info[:2]
    if (major, minor) != (3, 12):
        raise RuntimeError(
            f"xuetang-api 只允许 Python 3.12，当前是 {sys.version.split()[0]}。"
            "请使用 python:3.12 镜像或本机 python3.12，不要使用 3.13。"
        )
