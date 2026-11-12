# -*- coding: utf-8 -*-
# @File    : datasource.py
# @Desc    : 探测 MySQL、PostgreSQL 和 SQLite 是否可连接。密码只在探测时解密
# @Author  : xuetang-api
# @Date    : 2026-11-13
# @Update  : 2026-11-13 初始化数据源连通性

"""数据源连通性。"""

import os
import sqlite3

from app.core.config import get_settings
from app.core.exceptions import AppError


def assert_sqlite_path(database: str) -> str:
    """
    SQLite 只允许数据目录内的文件或 :memory:。

    Raises:
        AppError: 路径越出数据目录。
    """
    if database == ":memory:":
        return database
    root = os.path.realpath(get_settings().data_dir)
    target = os.path.realpath(database)
    if target != root and not target.startswith(root + os.sep):
        raise AppError("SQLite 路径必须位于数据目录", 4004)
    return target


def ping_database(db_type: str, host: str, port: int, database: str, username: str, password: str) -> str:
    """
    做一次短连接并执行 SELECT 1。

    Args:
        db_type: mysql、postgresql 或 sqlite。
        host: 主机，sqlite 可空。
        port: 端口。
        database: 库名，sqlite 时为文件路径。
        username: 用户名。
        password: 明文密码，调用方负责解密。

    Returns:
        成功说明。

    Raises:
        AppError: 类型不支持或连接失败。失败信息截断，避免回传过长的驱动堆栈。
    """
    kind = db_type.lower()
    try:
        if kind == "mysql":
            import pymysql

            conn = pymysql.connect(
                host=host,
                port=port,
                user=username,
                password=password,
                database=database,
                connect_timeout=3,
            )
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
            finally:
                conn.close()
        elif kind == "postgresql":
            import psycopg

            conn = psycopg.connect(
                host=host,
                port=port,
                user=username,
                password=password,
                dbname=database,
                connect_timeout=3,
            )
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
            finally:
                conn.close()
        elif kind == "sqlite":
            path = assert_sqlite_path(database)
            conn = sqlite3.connect(path, timeout=3)
            try:
                conn.execute("SELECT 1")
            finally:
                conn.close()
        else:
            raise AppError("不支持的数据源类型", 4004)
    except AppError:
        raise
    except Exception as exc:
        raise AppError(f"连接失败: {exc.__class__.__name__}", 4004) from exc
    return "连接成功"
