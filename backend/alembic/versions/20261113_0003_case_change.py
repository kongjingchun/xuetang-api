# -*- coding: utf-8 -*-
# @File    : 20261113_0003_case_change.py
# @Desc    : 用例增加接口变更说明，供定义修改后提示哪些字段受影响
# @Author  : xuetang-api
# @Date    : 2026-11-13
# @Update  : 2026-11-13 增加 api_case.change_json

"""用例增加变更说明。"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision = "20261113_0003"
down_revision = "20261113_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """已有用例默认没有变更说明。"""
    op.add_column(
        "api_case",
        sa.Column(
            "change_json",
            mysql.JSON(),
            nullable=False,
            server_default=sa.text("(JSON_OBJECT())"),
            comment="关联接口相对用例的变更点",
        ),
    )


def downgrade() -> None:
    """去掉变更说明。"""
    op.drop_column("api_case", "change_json")
