# -*- coding: utf-8 -*-
# @File    : test_dispatcher.py
# @Desc    : 本地调度器在阶段 0 会选中 local 节点，然后明确拒绝执行
# @Author  : xuetang-api
# @Date    : 2026-11-12
# @Update  : 2026-11-12 阶段 0 调度预留测试

"""调度器与协议注册表测试。"""

import pytest

from app.core.exceptions import AppError
from app.execution_engine.dispatcher import ExecutionTaskSpec, LocalDispatcher
from app.protocol_ext.registry import ProtocolRegistry


class _FakeDirectory:
    """不访问数据库的节点目录，只用来验证选节点路径。"""

    def list_online(self, labels: list[str] | None = None) -> list[dict]:
        if labels and "missing" in labels:
            return []
        return [{"id": 1, "name": "local", "address": "local://celery", "capacity": 10, "labels": ["default"]}]

    def heartbeat(self, node_id: int, metrics: dict) -> None:
        return None


def test_submit_names_local_node_and_refuses_execution() -> None:
    """submit 必须先选定 local，再以 5010 拒绝入队。"""
    dispatcher = LocalDispatcher(_FakeDirectory())
    with pytest.raises(AppError) as caught:
        dispatcher.submit(ExecutionTaskSpec(project_id=1, task_type="scenario"))
    assert caught.value.code == 5010
    assert "local" in caught.value.message


def test_submit_without_node() -> None:
    """标签没有命中节点时，不能假装执行成功。"""
    dispatcher = LocalDispatcher(_FakeDirectory())
    with pytest.raises(AppError) as caught:
        dispatcher.submit(ExecutionTaskSpec(project_id=1, task_type="scenario", node_labels=["missing"]))
    assert caught.value.code == 5030


def test_protocol_registry_rejects_unknown() -> None:
    """阶段 0 不预注册 http，未登记协议要给出明确错误。"""
    registry = ProtocolRegistry()
    with pytest.raises(AppError) as caught:
        registry.get("http")
    assert caught.value.code == 4004
