# -*- coding: utf-8 -*-
# @File    : 20261113_0004_api_creator.py
# @Desc    : 接口定义记录创建人，供定义列表展示
# @Author  : xuetang-api
# @Date    : 2026-11-13

"""接口定义增加创建人。"""

import sqlalchemy as sa
from alembic import op

revision = "20261113_0004"
down_revision = "20261113_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """已有接口没有创建人，列表显示为空。"""
    op.add_column(
        "api_definition",
        sa.Column("creator_id", sa.BigInteger(), nullable=True, comment="创建人"),
    )
    op.create_foreign_key("fk_api_definition_creator_id_sys_user", "api_definition", "sys_user", ["creator_id"], ["id"])


def downgrade() -> None:
    """去掉创建人。"""
    op.drop_constraint("fk_api_definition_creator_id_sys_user", "api_definition", type_="foreignkey")
    op.drop_column("api_definition", "creator_id")
