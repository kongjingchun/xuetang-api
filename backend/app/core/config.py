# -*- coding: utf-8 -*-
# @File    : config.py
# @Desc    : 从环境变量读取运行配置，集中生成 MySQL 与 Redis 连接地址
# @Author  : xuetang-api
# @Date    : 2026-11-12
# @Update  : 2026-11-12 初始化阶段 0 骨架

"""应用配置。字段含义与默认值见仓库根目录 .env.example。"""

from functools import lru_cache
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    进程级配置。

    环境变量名与字段名大小写不敏感，例如 MYSQL_HOST 映射 mysql_host。
    缺失的 .env 文件会被忽略，此时只读取真实环境变量和下面的默认值。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "xuetang-api"
    app_env: str = "dev"
    app_secret_key: str = "dev-only-change-me"
    api_prefix: str = "/api/v1"

    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "xuetang"
    mysql_password: str = "xuetang_pass"
    mysql_database: str = "xuetang_api"

    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_password: str = ""

    admin_username: str = "admin"
    admin_password: str = "Admin@123456"

    jwt_secret: str = "dev-only-change-me-jwt"
    jwt_expire_minutes: int = 120
    # 开发环境示例密钥，仅用于本地加密变量。生产环境必须更换。
    fernet_key: str = ""

    data_dir: str = "/data"

    @property
    def sqlalchemy_url(self) -> str:
        """SQLAlchemy 同步连接串，使用 pymysql 驱动。"""
        user = quote_plus(self.mysql_user)
        password = quote_plus(self.mysql_password)
        return (
            f"mysql+pymysql://{user}:{password}@{self.mysql_host}:{self.mysql_port}"
            f"/{self.mysql_database}?charset=utf8mb4"
        )

    def redis_url(self, db: int) -> str:
        """
        按库号生成 Redis URL。

        Args:
            db: 逻辑库号。0 缓存与锁，1 broker，2 结果，3 任务状态。
        """
        if self.redis_password:
            auth = f":{quote_plus(self.redis_password)}@"
        else:
            auth = ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{db}"


@lru_cache
def get_settings() -> Settings:
    """返回缓存的配置单例，避免重复解析环境变量。"""
    return Settings()
