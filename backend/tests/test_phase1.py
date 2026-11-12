# -*- coding: utf-8 -*-
# @File    : test_phase1.py
# @Desc    : 登录判定、归档保护、变量优先级和加密掩码
# @Author  : xuetang-api
# @Date    : 2026-11-13
# @Update  : 2026-11-13 阶段 1 规则测试

"""阶段 1 不依赖 MySQL 的规则测试。"""

from types import SimpleNamespace

import pytest

from app.auth.service import evaluate_login, login_log_result
from app.common.variables import VariableValue, resolve_text
from app.core.config import get_settings
from app.core.crypto import decrypt_text, encrypt_text, mask_secret
from app.core.exceptions import AppError
from app.core.security import decode_token, hash_password, verify_password
from app.core.security import create_access_token
from app.services.guard import ensure_project_writable


def test_wrong_password_is_not_success() -> None:
    """错误口令记为失败，不能写成 success。"""
    user = SimpleNamespace(password_hash=hash_password("Admin@123456"), status="enabled")
    outcome = evaluate_login(user, "wrong-password")
    assert outcome == "failed"
    assert login_log_result(outcome) == "failed"


def test_missing_user_is_failed() -> None:
    """用户不存在和口令错误使用同一个失败结果。"""
    assert evaluate_login(None, "whatever") == "failed"


def test_disabled_user_is_not_success() -> None:
    """禁用账号即使口令正确也不算登录成功。"""
    user = SimpleNamespace(password_hash=hash_password("Admin@123456"), status="disabled")
    assert login_log_result(evaluate_login(user, "Admin@123456")) == "failed"


def test_force_password_change_blocks_business_call() -> None:
    """未改密时业务依赖会拒绝。"""
    from app.auth.service import ensure_password_changed

    with pytest.raises(AppError) as caught:
        ensure_password_changed(True)
    assert caught.value.status_code == 403
    ensure_password_changed(False)


def test_archived_project_rejects_write() -> None:
    """归档项目不能再写入。"""
    with pytest.raises(AppError) as caught:
        ensure_project_writable("archived")
    assert caught.value.code == 4031
    ensure_project_writable("normal")


def test_access_token_roundtrip() -> None:
    """访问令牌能解出用户和类型。"""
    token = create_access_token(7, "admin")
    payload = decode_token(token, "access")
    assert payload["sub"] == "7"
    assert payload["typ"] == "access"
    assert verify_password("Admin@123456", hash_password("Admin@123456"))


def test_variable_priority_and_builtins() -> None:
    """执行临时变量覆盖项目变量，内置函数会被替换。"""
    layers = {
        "project": {"name": VariableValue("项目")},
        "runtime": {"name": VariableValue("临时")},
    }
    rendered = resolve_text("hi ${name} ${__uuid} ${__date(YYYY-MM-DD)}", layers)
    assert rendered.startswith("hi 临时 ")
    assert "${name}" not in rendered
    assert "${__uuid}" not in rendered
    assert len(rendered.split()[2]) == 32


def test_encrypted_variable_is_masked() -> None:
    """预览不揭示加密变量。"""
    settings = get_settings()
    settings.fernet_key = "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="
    cipher = encrypt_text("secret-value")
    assert cipher != "secret-value"
    assert decrypt_text(cipher) == "secret-value"
    assert mask_secret(cipher, True) == "******"
    layers = {"project": {"password": VariableValue(cipher, encrypted=True)}}
    assert resolve_text("pw=${password}", layers, reveal_secrets=False) == "pw=******"
