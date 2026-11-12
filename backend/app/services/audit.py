# -*- coding: utf-8 -*-
# @File    : audit.py
# @Desc    : 把用户、角色、项目和环境变更写入操作审计
# @Author  : xuetang-api
# @Date    : 2026-11-13
# @Update  : 2026-11-13 初始化审计写入

"""操作审计。"""

from sqlalchemy.orm import Session

from app.models.auth import SysAuditLog


def write_audit(
    session: Session,
    operator_id: int | None,
    module: str,
    action: str,
    content: str,
    ip: str = "",
    project_id: int | None = None,
) -> None:
    """
    追加一条审计。调用方负责提交事务。

    Args:
        session: 当前事务。
        operator_id: 操作人，匿名时为空。
        module: 模块名，例如 user、project、environment。
        action: 动作，例如 create、update、archive。
        content: 给人看的说明，不写密码和密文。
        ip: 来源 IP。
        project_id: 平台级操作留空。
    """
    session.add(
        SysAuditLog(
            operator_id=operator_id,
            project_id=project_id,
            module=module[:64],
            action=action[:64],
            content=content,
            ip=(ip or "")[:64],
        )
    )
