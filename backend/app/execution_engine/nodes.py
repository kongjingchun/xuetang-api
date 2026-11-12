# -*- coding: utf-8 -*-
# @File    : nodes.py
# @Desc    : 执行节点目录。本期只管理 local 节点，集群实现以后替换本类
# @Author  : xuetang-api
# @Date    : 2026-11-12
# @Update  : 2026-11-12 预留心跳与标签查询

"""节点目录协议与本地实现。"""

from datetime import datetime
from typing import Protocol

from app.db.session import SessionLocal
from app.models.platform import ExecNode, ExecNodeLabel


class NodeDirectory(Protocol):
    """
    节点查询与心跳。

    执行调度器只依赖这两个方法。后续 ClusterNodeDirectory 实现同一协议即可替换。
    """

    def list_online(self, labels: list[str] | None = None) -> list[dict]:
        """返回在线节点。labels 非空时，节点必须具备全部标签。"""

    def heartbeat(self, node_id: int, metrics: dict) -> None:
        """写入心跳时间和指标。"""


class LocalNodeDirectory:
    """
    单机节点目录。

    只返回 name=local 的节点，因此即使表里以后写入了其他节点，
    在替换为集群目录之前也不会被选中。
    """

    def list_online(self, labels: list[str] | None = None) -> list[dict]:
        """
        查询在线的 local 节点。

        Args:
            labels: 期望标签。为空时不按标签过滤。

        Returns:
            节点摘要列表，含 id、name、address、capacity、labels。
        """
        wanted = set(labels or [])
        with SessionLocal() as session:
            # 名称过滤是本期边界。集群目录会改成按状态和负载选择，不改返回字段。
            nodes = (
                session.query(ExecNode)
                .filter(ExecNode.name == "local", ExecNode.status == "online")
                .all()
            )
            result: list[dict] = []
            for node in nodes:
                node_labels = [
                    row.label
                    for row in session.query(ExecNodeLabel).filter(ExecNodeLabel.node_id == node.id).all()
                ]
                if wanted and not wanted.issubset(node_labels):
                    continue
                result.append(
                    {
                        "id": node.id,
                        "name": node.name,
                        "address": node.address,
                        "capacity": node.capacity,
                        "labels": node_labels,
                    }
                )
            return result

    def heartbeat(self, node_id: int, metrics: dict) -> None:
        """
        更新节点心跳。

        Args:
            node_id: exec_node 主键。
            metrics: 线程池、队列长度等指标，结构由调用方约定。

        Raises:
            LookupError: 节点不存在。
        """
        with SessionLocal() as session:
            node = session.get(ExecNode, node_id)
            if node is None:
                raise LookupError(f"执行节点不存在: {node_id}")
            node.last_heartbeat_at = datetime.now()
            node.metrics_json = metrics
            node.status = "online"
            session.commit()
