# -*- coding: utf-8 -*-
# @File    : variables.py
# @Desc    : 按作用域优先级解析 ${变量} 和内置函数。加密变量默认替换成掩码
# @Author  : xuetang-api
# @Date    : 2026-11-13
# @Update  : 2026-11-13 初始化变量引擎

"""变量解析。优先级：执行临时 > 场景 > 环境 > 项目 > 系统。"""

import re
import uuid
from dataclasses import dataclass
from datetime import datetime

from app.core.crypto import MASK, decrypt_text

_VAR = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
_FUNC = re.compile(r"\$\{__([A-Za-z]+)(?:\((.*?)\))?\}")
# 从高到低。前面的层命中后不再看后面的层。
LAYER_ORDER = ("runtime", "scenario", "env", "project", "system")


@dataclass
class VariableValue:
    """一个已解析前的变量。encrypted 为真时 text 是密文。"""

    text: str
    encrypted: bool = False


def _random_int(args: str) -> str:
    """解析 __random(min,max)，两端都包含。"""
    parts = [item.strip() for item in args.split(",")]
    if len(parts) != 2:
        raise ValueError("随机函数需要两个整数")
    low = int(parts[0])
    high = int(parts[1])
    if low > high:
        low, high = high, low
    import random

    return str(random.randint(low, high))


def _format_date(fmt: str) -> str:
    """只替换约定的日期记号，不把用户格式直接交给 strftime。"""
    now = datetime.now()
    mapping = {
        "YYYY": f"{now.year:04d}",
        "MM": f"{now.month:02d}",
        "DD": f"{now.day:02d}",
        "HH": f"{now.hour:02d}",
        "mm": f"{now.minute:02d}",
        "ss": f"{now.second:02d}",
    }
    result = fmt or "YYYY-MM-DD"
    for token, value in mapping.items():
        result = result.replace(token, value)
    return result


def _call_builtin(name: str, args: str) -> str:
    """执行内置函数。未知函数保持原样，方便发现拼写错误。"""
    if name == "uuid":
        return uuid.uuid4().hex
    if name == "timestamp":
        return str(int(datetime.now().timestamp()))
    if name == "random":
        return _random_int(args)
    if name == "date":
        return _format_date(args)
    return "${__" + name + (f"({args})" if args else "") + "}"


def _lookup(name: str, layers: dict[str, dict[str, VariableValue]], reveal_secrets: bool) -> str | None:
    """按优先级找变量。加密值在不揭示时返回掩码。"""
    for layer in LAYER_ORDER:
        found = layers.get(layer, {}).get(name)
        if found is None:
            continue
        if found.encrypted and not reveal_secrets:
            return MASK
        if found.encrypted:
            return decrypt_text(found.text)
        return found.text
    return None


def resolve_text(
    template: str,
    layers: dict[str, dict[str, VariableValue]] | None = None,
    reveal_secrets: bool = False,
) -> str:
    """
    替换模板中的变量和内置函数。

    Args:
        template: 原始文本。
        layers: 各作用域的变量表。
        reveal_secrets: 为真时解密后替换。预览接口必须保持假，避免把密文回显成明文。

    Returns:
        替换后的文本。找不到的 ${name} 保持原样。
    """
    layers = layers or {}

    def replace_func(match: re.Match) -> str:
        name = match.group(1)
        args = match.group(2) or ""
        try:
            return _call_builtin(name, args)
        except ValueError:
            return match.group(0)

    # 先替换函数，避免 ${__uuid} 被当成普通变量名。
    rendered = _FUNC.sub(replace_func, template)

    def replace_var(match: re.Match) -> str:
        value = _lookup(match.group(1), layers, reveal_secrets)
        if value is None:
            return match.group(0)
        return value

    return _VAR.sub(replace_var, rendered)
