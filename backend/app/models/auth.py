# -*- coding: utf-8 -*-
# @File    : auth.py
# @Desc    : 用户、角色、权限、登录日志、审计日志与 SSO 配置表
# @Author  : xuetang-api
# @Date    : 2026-11-12
# @Update  : 2026-11-12 初始化阶段 0 全量表结构

"""账号与权限模型。"""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedMixin, TimestampMixin, table_args


class SysUser(TimestampMixin, Base):
    """本地用户。口令只存 bcrypt 哈希，首次登录由 must_change_password 强制改密。"""

    __tablename__ = "sys_user"
    __table_args__ = table_args("用户表")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, comment="登录用户名")
    email: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True, comment="邮箱")
    real_name: Mapped[str] = mapped_column(String(64), nullable=False, default="", server_default="", comment="真实姓名")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False, comment="bcrypt 密码哈希")
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="enabled", server_default="enabled", comment="状态：enabled 启用，disabled 禁用"
    )
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("1"), comment="是否首次登录强制改密"
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="最后登录时间")


class SysRole(TimestampMixin, Base):
    """角色。内置四种：系统管理员、项目管理员、测试工程师、访客，也允许自定义。"""

    __tablename__ = "sys_role"
    __table_args__ = table_args("角色表")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    name: Mapped[str] = mapped_column(String(64), nullable=False, comment="角色名称")
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, comment="角色编码，程序按编码识别内置角色")
    builtin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("0"), comment="是否内置角色，内置角色不可删除"
    )
    data_scope: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="project",
        server_default="project",
        comment="数据范围：all 全部，project 所属项目，self 仅本人",
    )
    description: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="", comment="说明")


class SysPermission(TimestampMixin, Base):
    """权限点。type 取 menu、button、data，code 一旦发布就保持稳定。"""

    __tablename__ = "sys_permission"
    __table_args__ = table_args("权限点表")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    name: Mapped[str] = mapped_column(String(64), nullable=False, comment="权限名称")
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, comment="权限编码")
    type: Mapped[str] = mapped_column(String(16), nullable=False, comment="类型：menu 菜单，button 按钮，data 数据")
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("sys_permission.id"), nullable=True, comment="父权限，菜单树使用"
    )
    sort: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default=text("0"), comment="排序，小的在前")


class SysRolePermission(Base):
    """角色与权限的多对多关系。"""

    __tablename__ = "sys_role_permission"
    __table_args__ = table_args(
        "角色权限关系",
        UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    role_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sys_role.id"), nullable=False, comment="角色")
    permission_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sys_permission.id"), nullable=False, comment="权限点")


class SysUserRole(Base):
    """用户的全局角色。项目内角色另存在 project_member。"""

    __tablename__ = "sys_user_role"
    __table_args__ = table_args(
        "用户全局角色关系",
        UniqueConstraint("user_id", "role_id", name="uq_user_role"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sys_user.id"), nullable=False, comment="用户")
    role_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sys_role.id"), nullable=False, comment="角色")


class SysLoginLog(CreatedMixin, Base):
    """登录尝试记录，包含失败尝试，因此 user_id 可空。"""

    __tablename__ = "sys_login_log"
    __table_args__ = table_args("登录日志")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sys_user.id"), nullable=True, comment="用户，失败时可能为空")
    username: Mapped[str] = mapped_column(String(64), nullable=False, default="", server_default="", comment="尝试使用的用户名")
    ip: Mapped[str] = mapped_column(String(64), nullable=False, default="", server_default="", comment="来源 IP")
    user_agent: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="", comment="客户端标识")
    result: Mapped[str] = mapped_column(String(16), nullable=False, comment="结果：success 或 failed")
    message: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="", comment="结果说明")


class SysAuditLog(CreatedMixin, Base):
    """全量操作审计，供按用户、模块、类型筛选。"""

    __tablename__ = "sys_audit_log"
    __table_args__ = table_args("操作审计日志")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    operator_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sys_user.id"), nullable=True, comment="操作人")
    project_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True, comment="所属项目，平台级操作为空")
    module: Mapped[str] = mapped_column(String(64), nullable=False, comment="模块名")
    action: Mapped[str] = mapped_column(String(64), nullable=False, comment="操作类型")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="操作内容")
    ip: Mapped[str] = mapped_column(String(64), nullable=False, default="", server_default="", comment="来源 IP")


class SsoProvider(TimestampMixin, Base):
    """企业 SSO 配置。阶段 0 只建表，具体协议在后续阶段接入。"""

    __tablename__ = "sso_provider"
    __table_args__ = table_args("SSO 身份源配置")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    name: Mapped[str] = mapped_column(String(64), nullable=False, comment="显示名称")
    protocol: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="协议：oauth2、ldap、wecom、feishu、dingtalk、cas"
    )
    config_json: Mapped[dict] = mapped_column(JSON, nullable=False, comment="协议参数，密钥字段须加密后写入")
    mapping_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, comment="部门到项目角色的映射规则")
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("0"), comment="是否启用"
    )
