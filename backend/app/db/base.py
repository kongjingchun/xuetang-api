# -*- coding: utf-8 -*-
# @File    : base.py
# @Desc    : SQLAlchemy 声明基类、命名约定和时间戳字段
# @Author  : xuetang-api
# @Date    : 2026-11-12
# @Update  : 2026-11-12 初始化阶段 0 骨架

"""模型基类。业务表都继承 Base，字段注释通过 comment 写入 MySQL。"""

from datetime import datetime

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# 约束名固定下来，后续 Alembic autogenerate 才不会因为匿名约束反复抖动
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """全部业务表的声明基类。"""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def table_args(comment: str, *constraints: object) -> tuple:
    """
    组装表参数，统一字符集和表注释。

    Args:
        comment: 表注释，说明这张表存什么。
        constraints: 唯一约束或索引。
    """
    return (
        *constraints,
        {
            "comment": comment,
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )


class TimestampMixin:
    """创建与更新时间。由数据库默认值兜底，应用层更新时刷新 updated_at。"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        comment="创建时间",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )


class CreatedMixin:
    """只记录创建时间的流水表。"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        comment="创建时间",
    )
