# -*- coding: utf-8 -*-
# @File    : scripts.py
# @Desc    : 在独立子进程里调试公共脚本，限制可导入模块并在超时后结束进程
# @Author  : xuetang-api
# @Date    : 2026-11-13
# @Update  : 2026-11-13 初始化脚本沙箱

"""公共脚本调试。用户代码不在 API 进程内执行。"""

import json
import subprocess
import sys
import textwrap

from app.core.exceptions import AppError

MAX_SCRIPT_CHARS = 20000
DEFAULT_TIMEOUT = 5
# 子进程里允许 import 的模块。不包含 os、subprocess、socket。
ALLOWED_MODULES = ("json", "math", "re", "datetime", "hashlib", "uuid")

_WRAPPER = textwrap.dedent(
    """
    import json
    import sys

    payload = json.loads(sys.stdin.read() or "{}")
    params = payload.get("params") or {}
    allowed = set(payload.get("allowed") or [])
    real_import = __import__

    def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
        # 只放行白名单根模块，阻止脚本借 import 访问系统。
        root = name.split(".")[0]
        if root not in allowed:
            raise ImportError("模块不在白名单: " + name)
        return real_import(name, globals, locals, fromlist, level)

    safe_builtins = {
        "len": len, "range": range, "str": str, "int": int, "float": float,
        "bool": bool, "list": list, "dict": dict, "tuple": tuple, "set": set,
        "min": min, "max": max, "sum": sum, "abs": abs, "round": round,
        "enumerate": enumerate, "zip": zip, "print": print,
        "__import__": safe_import,
    }
    namespace = {"__builtins__": safe_builtins, "params": params, "result": None}
    try:
        exec(payload.get("content") or "", namespace, namespace)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        sys.exit(0)
    print(json.dumps({"ok": True, "result": namespace.get("result")}, ensure_ascii=False, default=str))
    """
)


def run_user_script(content: str, params: dict | None = None, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """
    运行一段用户脚本。

    Args:
        content: 脚本正文。可用 params 读取入参，用 result 返回值。
        params: 入参，必须能序列化成 JSON。
        timeout: 超时秒数，最大 10 秒。

    Returns:
        包含 ok、result 或 error 的字典。

    Raises:
        AppError: 脚本过长、超时或子进程没有返回 JSON。
    """
    if len(content) > MAX_SCRIPT_CHARS:
        raise AppError("脚本超过长度限制", 4004)
    seconds = min(max(int(timeout), 1), 10)
    try:
        proc = subprocess.run(
            [sys.executable, "-I", "-c", _WRAPPER],
            input=json.dumps(
                {"content": content, "params": params or {}, "allowed": list(ALLOWED_MODULES)},
                ensure_ascii=False,
            ),
            capture_output=True,
            text=True,
            timeout=seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise AppError("脚本执行超时", 4004) from exc
    # TimeoutExpired 由调用方转成业务错误，避免线程一直占着。
    line = (proc.stdout or "").strip().splitlines()
    if not line:
        detail = (proc.stderr or "").strip()[:500]
        raise AppError(detail or "脚本没有输出", 4004)
    try:
        return json.loads(line[-1])
    except json.JSONDecodeError as exc:
        raise AppError("脚本输出无法解析", 4004) from exc
