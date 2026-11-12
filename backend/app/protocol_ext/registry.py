# -*- coding: utf-8 -*-
# @File    : registry.py
# @Desc    : 协议适配器注册表。新增协议只注册适配器，不改场景解释器主循环
# @Author  : xuetang-api
# @Date    : 2026-11-12
# @Update  : 2026-11-12 初始化空注册表

"""协议注册表。"""

from abc import ABC, abstractmethod

from app.core.exceptions import AppError


class ProtocolAdapter(ABC):
    """一种协议的执行适配器。解释器只调用 execute。"""

    protocol: str

    @abstractmethod
    def execute(self, step: dict, ctx: dict) -> dict:
        """
        执行一步请求。

        Args:
            step: 步骤配置。
            ctx: 本次执行上下文，含变量。

        Returns:
            交换记录，至少包含 status_code、elapsed_ms、body。

        Raises:
            AppError: 协议调用失败。
        """


class ProtocolRegistry:
    """按协议名保存适配器。后注册的同名适配器覆盖先前的，便于测试替换。"""

    def __init__(self) -> None:
        self._items: dict[str, ProtocolAdapter] = {}

    def register(self, adapter: ProtocolAdapter) -> None:
        """登记适配器。protocol 为空时拒绝，避免解释器拿到无法路由的对象。"""
        if not adapter.protocol:
            raise AppError("协议适配器缺少 protocol 名称", code=4004)
        self._items[adapter.protocol] = adapter

    def get(self, protocol: str) -> ProtocolAdapter:
        """
        取出适配器。

        Args:
            protocol: 协议名，例如 http。

        Raises:
            AppError: 尚未注册。阶段 0 的 http 也走这条错误，阶段 4 才会登记。
        """
        adapter = self._items.get(protocol)
        if adapter is None:
            raise AppError(f"协议未注册: {protocol}", code=4004)
        return adapter

    def names(self) -> list[str]:
        """返回已注册协议名，监控页后续用它展示能力。"""
        return sorted(self._items)


registry = ProtocolRegistry()
