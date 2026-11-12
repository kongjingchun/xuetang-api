# -*- coding: utf-8 -*-
# @File    : tasks.py
# @Desc    : 阶段 0 的占位任务，用来确认 worker 和 beat 能消费队列
# @Author  : xuetang-api
# @Date    : 2026-11-12
# @Update  : 2026-11-12 增加 ping 任务

"""Celery 任务。"""

import logging

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.tasks.ping")
def ping() -> str:
    """
    心跳占位。

    Returns:
        固定字符串 pong。阶段 4 会另有任务把指标写入 exec_node。
    """
    logger.info("celery ping")
    return "pong"
