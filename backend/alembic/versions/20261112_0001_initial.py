# -*- coding: utf-8 -*-
# @File    : 20261112_0001_initial.py
# @Desc    : 初始迁移。按模型 metadata 创建全部业务表，字段注释随模型写入 MySQL
# @Author  : xuetang-api
# @Date    : 2026-11-12
# @Update  : 2026-11-12 创建阶段 0 全量表

"""初始建表。后续结构变化另起迁移，不要再改本文件。"""

from alembic import op

revision = "20261112_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    创建计划中的全部业务表。

    使用 metadata.create_all，是为了让模型上的 comment 原样进 MySQL。
    create_all 不会修改已存在的表，所以这之后的变更必须写新的迁移。
    """
    import app.models  # noqa: F401
    from app.db.base import Base

    bind = op.get_bind()
    # 多进程同时升级时，后启动的一方会看到表已存在并跳过，冲突由入口脚本重试兜底
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    """删除本迁移创建的业务表。alembic_version 由 Alembic 自己维护。"""
    import app.models  # noqa: F401
    from app.db.base import Base

    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
