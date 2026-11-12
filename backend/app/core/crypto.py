# -*- coding: utf-8 -*-
# @File    : crypto.py
# @Desc    : 用 Fernet 加密变量和数据源密码，读出时对接口只返回掩码
# @Author  : xuetang-api
# @Date    : 2026-11-13
# @Update  : 2026-11-13 初始化加密与掩码

"""敏感字段加密。未配置 FERNET_KEY 时拒绝写入。"""

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings
from app.core.exceptions import AppError

MASK = "******"


def _fernet() -> Fernet:
    """读取配置中的密钥。空密钥不能加密，避免把明文当成密文存进去。"""
    key = get_settings().fernet_key.strip()
    if not key:
        raise AppError("未配置 FERNET_KEY，不能保存敏感字段", 4002)
    try:
        return Fernet(key.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise AppError("FERNET_KEY 格式不正确", 4002) from exc


def encrypt_text(plain: str) -> str:
    """
    加密一段文本。

    Args:
        plain: 明文。

    Returns:
        Fernet 令牌字符串。
    """
    return _fernet().encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_text(cipher: str) -> str:
    """
    解密。

    Args:
        cipher: encrypt_text 的结果。

    Raises:
        AppError: 密钥不匹配或内容损坏。
    """
    try:
        return _fernet().decrypt(cipher.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise AppError("敏感字段无法解密", 4002) from exc


def mask_secret(value: str, encrypted: bool) -> str:
    """
    接口出参加密字段时只返回掩码。

    Args:
        value: 库存原文或密文。
        encrypted: 为真时不把 value 返回给调用方。
    """
    if encrypted:
        return MASK
    return value
