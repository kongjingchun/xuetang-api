# -*- coding: utf-8 -*-
# @File    : celery_app.py
# @Desc    : Celery 应用。预先声明 p0-p3 与 perf 队列，执行引擎阶段直接往这些队列投递
# @Author  : xuetang-api
# @Date    : 2026-11-12
# @Update  : 2026-11-12 初始化队列和心跳占位任务

"""Celery 实例。broker 使用 Redis 1 号库，结果使用 2 号库。"""

from celery import Celery
from kombu import Queue

from app.core.config import get_settings
from app.core.version_guard import assert_python_312

assert_python_312()
settings = get_settings()

celery_app = Celery(
    "xuetang",
    broker=settings.redis_url(1),
    backend=settings.redis_url(2),
)

# 功能任务按优先级分队列，压测独占 perf，避免压测占满功能执行。
celery_app.conf.task_queues = (
    Queue("p0"),
    Queue("p1"),
    Queue("p2"),
    Queue("p3"),
    Queue("perf"),
)
celery_app.conf.task_default_queue = "p1"
# 一条消息处理完再取下一条，阶段 4 的长任务不会在单个进程里堆住整批消息
celery_app.conf.worker_prefetch_multiplier = 1
celery_app.conf.task_acks_late = True
celery_app.conf.timezone = "Asia/Shanghai"
celery_app.conf.enable_utc = False
celery_app.conf.beat_schedule = {
    "worker-ping": {
        "task": "app.workers.tasks.ping",
        "schedule": 60.0,
    }
}

# 放在实例创建之后再导入，避免 tasks 回导入时拿到未赋值的 celery_app
from app.workers import tasks as _tasks  # noqa: E402,F401
