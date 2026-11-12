# -*- coding: utf-8 -*-
# @File    : session.py
# @Desc    : 同步引擎与会话工厂。API 与 Celery 共用这一套，避免两套会话模型
# @Author  : xuetang-api
# @Date    : 2026-11-12
# @Update  : 2026-11-12 初始化阶段 0 骨架

"""数据库会话。"""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

# pool_pre_ping 在取连接前探测，避免 MySQL 等待超时后继续使用失效连接
engine = create_engine(
    settings.sqlalchemy_url,
    pool_pre_ping=True,
    pool_recycle=3600,
    future=True,
    # 连不上时尽快失败，避免健康检查和启动等待把超时拖到几十秒
    connect_args={"connect_timeout": 3},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """
    FastAPI 依赖：提供一次请求范围的会话。

    Yields:
        用完即关闭的 Session。提交由业务代码显式完成。
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
