# -*- coding: utf-8 -*-
# @File    : test_schema.py
# @Desc    : 核对 65 张表都已登记，并且 MySQL DDL 带有注释
# @Author  : xuetang-api
# @Date    : 2026-11-12
# @Update  : 2026-11-12 阶段 0 模型约束测试

"""模型完整性测试，不连接数据库。"""

from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable

from app.core.version_guard import assert_python_312
from app.db.base import Base
from app.models import EXPECTED_TABLES, assert_schema_complete


def test_python_312() -> None:
    """当前测试进程必须是 3.12。"""
    assert_python_312()


def test_expected_table_count() -> None:
    """计划中的表一个都不能少。"""
    assert_schema_complete()
    assert len(EXPECTED_TABLES) == 65
    assert len(Base.metadata.tables) == 65


def test_mysql_ddl_contains_comments() -> None:
    """每张表的建表语句都要带 COMMENT，保证字段说明能进 MySQL。"""
    dialect = mysql.dialect()
    for table in Base.metadata.sorted_tables:
        sql = str(CreateTable(table).compile(dialect=dialect))
        assert "COMMENT" in sql, table.name
