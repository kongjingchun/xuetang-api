# -*- coding: utf-8 -*-
# @File    : test_security.py
# @Desc    : 口令哈希往返，以及统一响应字段
# @Author  : xuetang-api
# @Date    : 2026-11-12
# @Update  : 2026-11-12 阶段 0 基础函数测试

"""安全与响应包装测试。"""

from app.core.response import fail, ok
from app.core.security import hash_password, verify_password


def test_password_roundtrip() -> None:
    """bcrypt 哈希可以校验原文，错误口令不通过。"""
    hashed = hash_password("Admin@123456")
    assert hashed != "Admin@123456"
    assert verify_password("Admin@123456", hashed)
    assert not verify_password("wrong", hashed)


def test_response_shape() -> None:
    """成功和失败都带 code、message、data。"""
    assert ok({"mysql": "ok"})["code"] == 0
    body = fail("依赖不可用", 5001, {"mysql": "unavailable"})
    assert body["code"] == 5001
    assert "password" not in str(body)
