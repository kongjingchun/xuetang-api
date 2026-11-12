# -*- coding: utf-8 -*-
# @File    : dispatcher.py
# @Desc    : 执行入口。所有触发方只调用 submit/stop/status，不直接操作 Celery
# @Author  : xuetang-api
# @Date    : 2026-11-12
# @Update  : 2026-11-12 本地调度器先完成选节点，入队留到阶段 4

"""执行调度器。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.core.exceptions import AppError
from app.execution_engine.nodes import LocalNodeDirectory, NodeDirectory


@dataclass
class ExecutionTaskSpec:
    """一次执行请求的最小描述，阶段 4 会把它写成 exec_task 并投入优先级队列。"""

    project_id: int
    task_type: str
    priority: str = "P2"
    target_public_id: str = ""
    env_code: str = ""
    variables: dict = field(default_factory=dict)
    node_labels: list[str] = field(default_factory=list)


class ExecutionDispatcher(ABC):
    """调度器抽象。本地与未来的远程实现都实现这三个方法。"""

    @abstractmethod
    def submit(self, spec: ExecutionTaskSpec) -> str:
        """
        提交任务。

        Args:
            spec: 执行请求。

        Returns:
            任务对外 ID。

        Raises:
            AppError: 没有可用节点，或当前阶段尚未开放执行。
        """

    @abstractmethod
    def stop(self, task_id: str) -> None:
        """停止排队中或执行中的任务。"""

    @abstractmethod
    def status(self, task_id: str) -> dict:
        """查询任务状态。阶段 4 起从 Redis 读取，不假设任务在本进程。"""


class LocalDispatcher(ExecutionDispatcher):
    """
    本期唯一调度器。

    选节点逻辑已经走 NodeDirectory，这样阶段 4 只补写入队列，不改调用方。
    """

    def __init__(self, directory: NodeDirectory | None = None) -> None:
        self.directory = directory or LocalNodeDirectory()

    def resolve_node(self, spec: ExecutionTaskSpec) -> dict:
        """
        为任务选定一个节点。

        Args:
            spec: 执行请求，其中 node_labels 传给节点目录。

        Returns:
            节点摘要。

        Raises:
            AppError: 没有满足标签的在线 local 节点。
        """
        nodes = self.directory.list_online(spec.node_labels or None)
        if not nodes:
            raise AppError("没有可用的 local 执行节点", code=5030, status_code=503)
        # 单机只有一个候选。集群实现会在这里按容量挑选，而不是在业务代码里分支。
        return nodes[0]

    def submit(self, spec: ExecutionTaskSpec) -> str:
        """选定 local 节点后拒绝入队。阶段 4 去掉这个拒绝并写入 Celery。"""
        node = self.resolve_node(spec)
        raise AppError(
            f"执行引擎将在阶段 4 启用，已选定节点 {node['name']}",
            code=5010,
            status_code=501,
        )

    def stop(self, task_id: str) -> None:
        """阶段 4 才会按 task_id 到 Redis 发停止信号。"""
        raise AppError(f"任务停止将在阶段 4 启用: {task_id}", code=5010, status_code=501)

    def status(self, task_id: str) -> dict:
        """阶段 4 才会返回 Redis 中的任务状态。"""
        raise AppError(f"任务状态将在阶段 4 启用: {task_id}", code=5010, status_code=501)
