# -*- coding: utf-8 -*-
# @File    : project.py
# @Desc    : 项目、成员、环境、变量、公共脚本和数据源表
# @Author  : xuetang-api
# @Date    : 2026-11-12
# @Update  : 2026-11-12 初始化阶段 0 全量表结构

"""项目与环境模型。"""

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, table_args


class Project(TimestampMixin, Base):
    """测试项目。对外使用 public_id，项目间数据按 project_id 隔离。"""

    __tablename__ = "project"
    __table_args__ = table_args("项目表")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    public_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, comment="对外 ID，前缀 PRJ_")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="项目名称")
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, comment="项目唯一标识，用于 Mock 路径")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="项目描述")
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="normal", server_default="normal", comment="状态：normal 正常，archived 归档"
    )


class ProjectMember(TimestampMixin, Base):
    """项目成员及项目内角色。"""

    __tablename__ = "project_member"
    __table_args__ = table_args(
        "项目成员",
        UniqueConstraint("project_id", "user_id", name="uq_project_member"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("project.id"), nullable=False, index=True, comment="项目")
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sys_user.id"), nullable=False, comment="用户")
    role_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sys_role.id"), nullable=False, comment="项目内角色")


class ProjectSetting(TimestampMixin, Base):
    """项目级执行与保留策略。一个项目一行。"""

    __tablename__ = "project_setting"
    __table_args__ = table_args("项目配置")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("project.id"), nullable=False, unique=True, comment="项目"
    )
    default_env_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="默认环境 ID，环境创建后回填")
    retry_times: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0"), comment="失败重试次数"
    )
    report_retention_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=90, server_default=text("90"), comment="报告保留天数"
    )
    concurrency_quota: Mapped[int] = mapped_column(
        Integer, nullable=False, default=10, server_default=text("10"), comment="项目并发任务上限"
    )


class Environment(TimestampMixin, Base):
    """项目环境。公共请求头和前置脚本放在本表，不拆子表。"""

    __tablename__ = "environment"
    __table_args__ = table_args(
        "环境表",
        UniqueConstraint("project_id", "code", name="uq_environment_project_code"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("project.id"), nullable=False, index=True, comment="项目")
    name: Mapped[str] = mapped_column(String(64), nullable=False, comment="环境名称")
    code: Mapped[str] = mapped_column(String(64), nullable=False, comment="环境编码，如 dev、test")
    base_url: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="", comment="基础地址")
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("1"), comment="是否启用"
    )
    headers_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, comment="环境级公共请求头")
    pre_script: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="环境级全局前置脚本")
    description: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="", comment="说明")


class Variable(TimestampMixin, Base):
    """
    变量。

    scope 从低到高为 system、project、env、scenario。
    执行临时变量不入库，只活在一次任务的上下文里。
    """

    __tablename__ = "variable"
    __table_args__ = table_args(
        "变量表",
        UniqueConstraint("scope", "scope_id", "name", name="uq_variable_scope_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    scope: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="作用域：system、project、env、scenario"
    )
    scope_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0"), comment="作用域对象 ID，系统变量为 0"
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="变量名，引用时写作 ${name}")
    var_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="string", server_default="string", comment="类型：string、secret、number、bool"
    )
    encrypted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("0"), comment="是否加密存储，为真时 value 是密文"
    )
    value: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="变量值或密文")
    description: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="", comment="说明")


class PublicScript(TimestampMixin, Base):
    """可复用的 Python 脚本。project_id 为空表示平台级脚本。"""

    __tablename__ = "public_script"
    __table_args__ = table_args("公共脚本库")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    project_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("project.id"), nullable=True, index=True, comment="项目，空为平台级")
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="default", server_default="default", comment="分类")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="脚本名称")
    params_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, comment="入参定义")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="脚本正文")


class DataSource(TimestampMixin, Base):
    """外部数据库连接。密码只存密文，供前置取数和数据库断言使用。"""

    __tablename__ = "datasource"
    __table_args__ = table_args("数据源")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("project.id"), nullable=False, index=True, comment="项目")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="数据源名称")
    db_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="类型：mysql、postgresql、sqlite")
    host: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="", comment="主机")
    port: Mapped[int] = mapped_column(Integer, nullable=False, default=3306, server_default=text("3306"), comment="端口")
    database: Mapped[str] = mapped_column(String(128), nullable=False, default="", server_default="", comment="库名")
    username: Mapped[str] = mapped_column(String(128), nullable=False, default="", server_default="", comment="用户名")
    password_cipher: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="加密后的密码")
