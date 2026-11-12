# -*- coding: utf-8 -*-
# @File    : 20261113_0002_api_sort.py
# @Desc    : 给接口定义增加同级排序，供定义页拖拽后保存位置
# @Author  : xuetang-api
# @Date    : 2026-11-13
# @Update  : 2026-11-13 增加 api_definition.sort

"""接口定义增加 sort。"""

import sqlalchemy as sa
from alembic import op

revision = "20261113_0002"
down_revision = "20261112_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """已有接口默认排在 0，和目录的 sort 用法一致。"""
    op.add_column(
        "api_definition",
        sa.Column("sort", sa.Integer(), nullable=False, server_default="0", comment="同级排序"),
    )


def downgrade() -> None:
    """去掉排序列。"""
    op.drop_column("api_definition", "sort")
