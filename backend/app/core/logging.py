# -*- coding: utf-8 -*-
# @File    : logging.py
# @Desc    : 把应用日志打到标准输出，便于容器采集和排障
# @Author  : xuetang-api
# @Date    : 2026-11-12
# @Update  : 2026-11-12 初始化阶段 0 骨架

"""统一日志格式。"""

import logging
import sys


def setup_logging() -> None:
    """初始化根日志。重复调用不会叠加 handler。"""
    root = logging.getLogger()
    if getattr(root, "_xuetang_configured", False):
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    )
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    # uvicorn 与 celery 仍使用各自的 logger，这里只保证业务日志格式一致
    root._xuetang_configured = True  # type: ignore[attr-defined]
