# -*- coding: utf-8 -*-
# @File    : sso.py
# @Desc    : SSO 适配器接口。具体厂商协议未实现时返回未启用
# @Author  : xuetang-api
# @Date    : 2026-11-13
# @Update  : 2026-11-13 预留 SSO 适配器

"""企业单点登录适配器。阶段 1 只定义接口。"""

from typing import Protocol

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.auth import SsoProvider


class SsoAdapter(Protocol):
    """一种身份源协议需要实现的三个动作。"""

    protocol: str

    def build_authorize_url(self, config: dict, redirect_uri: str) -> str:
        """生成跳转到身份源的地址。"""

    def exchange_user(self, config: dict, code: str) -> dict:
        """用授权码换本地需要的用户资料。"""

    def sync_users(self, config: dict) -> list[dict]:
        """按映射规则同步用户。"""


class UnsupportedSsoAdapter:
    """占位实现。调用任何方法都明确告诉调用方协议还没接上。"""

    def __init__(self, protocol: str) -> None:
        self.protocol = protocol

    def build_authorize_url(self, config: dict, redirect_uri: str) -> str:
        """拒绝生成跳转地址。"""
        raise AppError(f"SSO 协议未启用: {self.protocol}", 5011, 501)

    def exchange_user(self, config: dict, code: str) -> dict:
        """拒绝换取用户。"""
        raise AppError(f"SSO 协议未启用: {self.protocol}", 5011, 501)

    def sync_users(self, config: dict) -> list[dict]:
        """拒绝同步。"""
        raise AppError(f"SSO 协议未启用: {self.protocol}", 5011, 501)


def get_adapter(protocol: str) -> UnsupportedSsoAdapter:
    """按协议名返回适配器。目前全部落在未启用实现上。"""
    return UnsupportedSsoAdapter(protocol)


def list_enabled_providers(session: Session) -> list[dict]:
    """返回已启用的身份源名称，不包含配置里的密钥。"""
    rows = session.query(SsoProvider).filter(SsoProvider.enabled.is_(True)).all()
    return [{"id": row.id, "name": row.name, "protocol": row.protocol} for row in rows]
