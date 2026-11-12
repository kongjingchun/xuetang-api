# -*- coding: utf-8 -*-
# @File    : exceptions.py
# @Desc    : 业务异常。接口层把它转成统一的 code/message/data，不回传堆栈
# @Author  : xuetang-api
# @Date    : 2026-11-12
# @Update  : 2026-11-12 初始化阶段 0 骨架

"""业务异常定义。"""


class AppError(Exception):
    """
    可预期的业务错误。

    Attributes:
        message: 返回给调用方的说明。
        code: 业务错误码，0 表示成功，其余为失败。
        status_code: HTTP 状态码。
    """

    def __init__(self, message: str, code: int = 4000, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
