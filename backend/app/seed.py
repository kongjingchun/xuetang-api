# -*- coding: utf-8 -*-
# @File    : seed.py
# @Desc    : 幂等种子数据。重复执行不覆盖已改过的管理员密码，也不复制演示项目
# @Author  : xuetang-api
# @Date    : 2026-11-12
# @Update  : 2026-11-12 初始化角色、管理员、local 节点和学堂在线示例

"""启动种子。由容器入口在迁移之后调用。"""

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.security import hash_password
from app.core.version_guard import assert_python_312
from app.db.session import SessionLocal
from app.models.auth import SysPermission, SysRole, SysRolePermission, SysUser, SysUserRole
from app.models.platform import BizTemplate, ExecNode, ExecNodeLabel, RetentionPolicy
from app.models.project import Environment, Project, ProjectMember, ProjectSetting, Variable
from app.models.testing import (
    ApiCase,
    ApiDefinition,
    ApiModule,
    ApiResponseExample,
    Scenario,
    ScenarioModule,
    ScenarioStep,
)

logger = logging.getLogger(__name__)

MENU_PERMISSIONS = (
    ("menu:dashboard", "工作台", "menu", 10),
    ("menu:api-test", "接口测试", "menu", 20),
    ("menu:test-plan", "测试计划", "menu", 30),
    ("menu:review", "用例评审", "menu", 40),
    ("menu:traffic", "流量录制", "menu", 50),
    ("menu:data-factory", "数据工厂", "menu", 60),
    ("menu:statistics", "统计看板", "menu", 70),
    ("menu:settings", "系统设置", "menu", 80),
    ("user:manage", "用户维护", "button", 110),
    ("role:manage", "角色维护", "button", 120),
    ("project:archive", "项目归档", "button", 130),
    ("member:manage", "成员维护", "button", 140),
    ("env:manage", "环境维护", "button", 150),
    ("variable:manage", "变量维护", "button", 160),
    ("script:manage", "脚本维护", "button", 170),
    ("datasource:manage", "数据源维护", "button", 180),
    ("audit:read", "审计查询", "button", 190),
)

ROLES = (
    ("system_admin", "系统管理员", "all", "平台全部数据"),
    ("project_admin", "项目管理员", "project", "所在项目的数据"),
    ("tester", "测试工程师", "project", "所在项目内编写和执行"),
    ("guest", "访客", "self", "只读本人可见数据"),
)


def _root_module(session: Session, model, project_id: int, name: str):
    """按父目录为空加名称查找演示目录。同名子目录不会让种子匹配到多行。"""
    row = (
        session.query(model)
        .filter(model.project_id == project_id, model.name == name, model.parent_id.is_(None))
        .one_or_none()
    )
    if row is not None:
        return row
    row = model(project_id=project_id, name=name, parent_id=None, sort=0)
    session.add(row)
    session.flush()
    return row


def get_or_create(session: Session, model, lookup: dict, defaults: dict | None = None):
    """
    按业务键查找，不存在则插入并 flush 出主键。

    Returns:
        (实例, 是否新建)。
    """
    instance = session.query(model).filter_by(**lookup).one_or_none()
    if instance is not None:
        return instance, False
    payload = dict(lookup)
    payload.update(defaults or {})
    instance = model(**payload)
    session.add(instance)
    session.flush()
    return instance, True


def ensure_link(session: Session, model, lookup: dict) -> None:
    """关系表缺行时补一行。"""
    if session.query(model).filter_by(**lookup).one_or_none() is None:
        session.add(model(**lookup))


def seed_permissions(session: Session) -> list[SysPermission]:
    """写入菜单权限点。按钮级权限在阶段 1 追加，不在这里预占编码。"""
    rows = []
    for code, name, perm_type, sort in MENU_PERMISSIONS:
        perm, _ = get_or_create(
            session,
            SysPermission,
            {"code": code},
            {"name": name, "type": perm_type, "sort": sort},
        )
        rows.append(perm)
    return rows


def seed_roles(session: Session, permissions: list[SysPermission]) -> dict[str, SysRole]:
    """写入四个内置角色，并按数据范围补齐菜单权限。"""
    by_code = {item.code: item for item in permissions}
    roles: dict[str, SysRole] = {}
    platform_only = {"menu:settings", "user:manage", "role:manage", "audit:read"}
    project_menus = [code for code in by_code if code.startswith("menu:") and code not in platform_only]
    grants = {
        "system_admin": list(by_code),
        "project_admin": project_menus
        + ["project:archive", "member:manage", "env:manage", "variable:manage", "script:manage", "datasource:manage"],
        "tester": project_menus + ["env:manage", "variable:manage", "script:manage", "datasource:manage"],
        "guest": ["menu:dashboard", "menu:api-test"],
    }
    for code, name, scope, description in ROLES:
        role, _ = get_or_create(
            session,
            SysRole,
            {"code": code},
            {"name": name, "builtin": True, "data_scope": scope, "description": description},
        )
        roles[code] = role
        for perm_code in grants[code]:
            ensure_link(
                session,
                SysRolePermission,
                {"role_id": role.id, "permission_id": by_code[perm_code].id},
            )
    return roles


def seed_admin(session: Session, role: SysRole) -> SysUser:
    """
    创建初始管理员。

    用户已存在时不改密码，避免每次重启把改过的口令打回 .env 中的初始值。
    """
    settings = get_settings()
    user, created = get_or_create(
        session,
        SysUser,
        {"username": settings.admin_username},
        {
            "real_name": "系统管理员",
            "password_hash": hash_password(settings.admin_password),
            "status": "enabled",
            "must_change_password": True,
        },
    )
    if created:
        logger.info("已创建管理员 %s，首次登录需要改密", settings.admin_username)
    ensure_link(session, SysUserRole, {"user_id": user.id, "role_id": role.id})
    return user


def seed_project(session: Session, admin: SysUser, project_role: SysRole) -> Project:
    """学堂在线演示项目、两个环境和一条项目变量。"""
    project, _ = get_or_create(
        session,
        Project,
        {"code": "xuetang"},
        {
            "public_id": "PRJ_XUETANG",
            "name": "学堂在线",
            "description": "阶段 0 演示项目，后续阶段会在此之上补接口与场景操作。",
            "status": "normal",
        },
    )
    ensure_link(
        session,
        ProjectMember,
        {"project_id": project.id, "user_id": admin.id, "role_id": project_role.id},
    )
    setting, _ = get_or_create(
        session,
        ProjectSetting,
        {"project_id": project.id},
        {"retry_times": 1, "report_retention_days": 90, "concurrency_quota": 10},
    )
    dev, _ = get_or_create(
        session,
        Environment,
        {"project_id": project.id, "code": "dev"},
        {"name": "开发", "base_url": "http://dev.xuetang.local", "enabled": True, "headers_json": {}, "pre_script": ""},
    )
    get_or_create(
        session,
        Environment,
        {"project_id": project.id, "code": "test"},
        {"name": "测试", "base_url": "http://test.xuetang.local", "enabled": True, "headers_json": {}, "pre_script": ""},
    )
    if setting.default_env_id is None:
        setting.default_env_id = dev.id
    get_or_create(
        session,
        Variable,
        {"scope": "project", "scope_id": project.id, "name": "app_name"},
        {"var_type": "string", "encrypted": False, "value": "学堂在线", "description": "演示用项目变量"},
    )
    return project


def seed_demo_assets(session: Session, project: Project, admin: SysUser) -> None:
    """一条登录接口、一条用例、一条只含引用步骤的场景，以及注册登录模板。"""
    module = _root_module(session, ApiModule, project.id, "用户端")
    api, _ = get_or_create(
        session,
        ApiDefinition,
        {"public_id": "API_LOGIN"},
        {
            "project_id": project.id,
            "module_id": module.id,
            "name": "用户登录",
            "method": "POST",
            "path": "/api/v1/u/login",
            "tags": "用户端",
            "description": "学堂在线用户登录示例。",
            "request_json": {
                "query": [],
                "headers": [{"name": "Content-Type", "required": True, "value": "application/json"}],
                "body": {
                    "type": "raw",
                    "language": "json",
                    "content": {"username": "${username}", "password": "${password}"},
                },
            },
            "revision": 1,
        },
    )
    if session.query(ApiResponseExample).filter_by(api_id=api.id).one_or_none() is None:
        session.add(
            ApiResponseExample(
                api_id=api.id,
                name="登录成功",
                status_code=200,
                headers_json={},
                body='{"code":0,"message":"success","data":{"token":"demo"}}',
                description="示例响应",
            )
        )
    case, _ = get_or_create(
        session,
        ApiCase,
        {"public_id": "CASE_LOGIN_OK"},
        {
            "project_id": project.id,
            "api_id": api.id,
            "name": "登录成功",
            "priority": "P0",
            "tags": "冒烟",
            "owner_id": admin.id,
            "description": "正确口令返回成功码。",
            "request_json": {},
            "processors_json": {
                "assertions": [{"type": "status_code", "expect": 200}],
                "extractors": [],
                "pre": [],
                "post": [],
            },
            "review_status": "draft",
            "api_changed": False,
        },
    )
    scene_module = _root_module(session, ScenarioModule, project.id, "用户端")
    dev = session.query(Environment).filter_by(project_id=project.id, code="dev").one()
    scenario, created_scene = get_or_create(
        session,
        Scenario,
        {"public_id": "SCENE_LOGIN"},
        {
            "project_id": project.id,
            "module_id": scene_module.id,
            "name": "用户登录",
            "level": "P0",
            "status": "enabled",
            "env_id": dev.id,
            "tags": "冒烟",
            "creator_id": admin.id,
            "description": "引用登录成功用例。阶段 4 起可以执行。",
        },
    )
    if created_scene:
        session.add(
            ScenarioStep(
                scenario_id=scenario.id,
                parent_id=None,
                step_type="case_ref",
                name="登录成功",
                config_json={"case_public_id": case.public_id},
                sort=0,
            )
        )
    get_or_create(
        session,
        BizTemplate,
        {"name": "用户注册登录", "version_no": 1, "project_id": None},
        {
            "category": "用户端",
            "snapshot_json": {"steps": ["注册", "登录"]},
        },
    )


def seed_node(session: Session) -> None:
    """保证存在名为 local 的在线节点和 default 标签。"""
    node, _ = get_or_create(
        session,
        ExecNode,
        {"name": "local"},
        {"address": "local://celery", "status": "online", "capacity": 10, "metrics_json": {}},
    )
    ensure_link(session, ExecNodeLabel, {"node_id": node.id, "label": "default"})


def seed_retention(session: Session) -> None:
    """平台默认保留策略。项目级覆盖在后续阶段按项目写入。"""
    exists = session.query(RetentionPolicy).filter(RetentionPolicy.project_id.is_(None)).one_or_none()
    if exists is None:
        session.add(RetentionPolicy(project_id=None, report_days=90, log_days=30, audit_days=180, record_days=30))


def run_seed() -> None:
    """
    在连接级锁内写入种子。

    Raises:
        RuntimeError: 30 秒内没有拿到锁。
    """
    with SessionLocal() as session:
        locked = session.execute(text("SELECT GET_LOCK('xuetang_seed', 30)")).scalar()
        if locked != 1:
            raise RuntimeError("未拿到种子锁 xuetang_seed")
        try:
            permissions = seed_permissions(session)
            roles = seed_roles(session, permissions)
            admin = seed_admin(session, roles["system_admin"])
            project = seed_project(session, admin, roles["project_admin"])
            seed_demo_assets(session, project, admin)
            seed_node(session)
            seed_retention(session)
            session.commit()
            logger.info("种子数据已就绪")
        except Exception:
            session.rollback()
            logger.exception("种子数据写入失败")
            raise
        finally:
            session.execute(text("SELECT RELEASE_LOCK('xuetang_seed')"))
            session.commit()


if __name__ == "__main__":
    assert_python_312()
    setup_logging()
    run_seed()
